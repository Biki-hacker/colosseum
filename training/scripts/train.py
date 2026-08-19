"""Train a TinyGPT model from a packed dataset with configurable mixture weights.

Usage:
  python training/scripts/train.py --config training/configs/train_exp_d.yaml

Features: resumable checkpoints, best-checkpoint selection, val-loss evaluation,
periodic sample generation, metric logging (jsonl + console), bf16 autocast,
gradient accumulation, cosine LR schedule with warmup.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import asdict
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import torch
import torch.nn.functional as F
import yaml

from src.config import ModelConfig, TrainConfig
from src.model import TinyGPT
from src.simple_tokenizer import SimpleBPETokenizer

PERSONALITIES = ["optimist", "pessimist"]
OPPONENT = {"optimist": "pessimist", "pessimist": "optimist"}
MARK_FOR = {"optimist": "<OPTIMIST>", "pessimist": "<PESSIMIST>"}


def log(msg: str) -> None:
    print(f"[train] {msg}", flush=True)


class MixedDataset:
    """Samples (ids, mask) batches; per-batch source drawn by mixture weights."""

    def __init__(self, ids: np.ndarray, mask: np.ndarray, is_synth: np.ndarray | None, weights: dict, seed: int):
        self.ids = torch.from_numpy(ids).to(torch.int64)
        self.mask = torch.from_numpy(mask)
        self.rng = np.random.default_rng(seed)
        base_idx = np.arange(len(ids))
        if is_synth is not None:
            self.base_idx = base_idx[~is_synth]
            self.synth_idx = base_idx[is_synth]
        else:
            self.base_idx = base_idx
            self.synth_idx = base_idx
        w_base, w_synth = float(weights.get("base", 1.0)), float(weights.get("synth", 0.0))
        denom = w_base + w_synth
        self.p_synth = w_synth / denom if denom > 0 else 0.0

    def batch(self, n: int) -> tuple[torch.Tensor, torch.Tensor]:
        n_synth = int(self.rng.binomial(n, self.p_synth))
        n_base = n - n_synth
        if n_base and len(self.base_idx):
            bi = self.rng.choice(self.base_idx, size=n_base, replace=True)
        else:
            bi = np.array([], dtype=int)
        if n_synth and len(self.synth_idx):
            si = self.rng.choice(self.synth_idx, size=n_synth, replace=True)
        else:
            si = np.array([], dtype=int)
        idx = np.concatenate([bi, si])
        self.rng.shuffle(idx)
        return self.ids[idx], self.mask[idx]


def make_targets(ids: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """Shift-by-one next-token targets; -100 masks non-loss positions."""
    x = ids[:, :-1]
    t = ids[:, 1:]
    m = mask[:, 1:]
    t = torch.where(m, t, torch.full_like(t, -100))
    return x, t


def eval_loss(model: TinyGPT, ds: MixedDataset, steps: int, precision: str, device: str) -> float:
    model.eval()
    total, count = 0.0, 0
    with torch.no_grad():
        for _ in range(steps):
            ids, mask = ds.batch(16)
            x, t = make_targets(ids.to(device), mask.to(device))
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=precision == "bf16"):
                _, loss = model(x, t)
            n = (t != -100).sum().item()
            total += loss.item() * n
            count += n
    model.train()
    return total / max(count, 1)


@torch.no_grad()
def generate_sample(model: TinyGPT, tok: SimpleBPETokenizer, cfg: dict, device: str) -> str:
    topic = cfg["eval"]["topic"]
    opp_text = cfg["eval"]["opponent_text"]
    own = cfg["personality"]
    opp = OPPONENT[own]
    prompt = (
        f"<BOS><TOPIC> {topic}<TURN><{opp.upper()}> {opp_text}<TURN>{MARK_FOR[own]}"
    )
    ids = tok.encode(prompt)
    idx = torch.tensor([ids], device=device)
    out = model.generate(
        idx,
        max_new_tokens=cfg["eval"].get("max_new_tokens", 50),
        temperature=cfg["eval"].get("temperature", 0.8),
        top_k=cfg["eval"].get("top_k", 40),
        top_p=cfg["eval"].get("top_p", 0.9),
        repetition_penalty=cfg["eval"].get("repetition_penalty", 1.15),
        eos_id=tok.eos_id,
    )
    return tok.decode(out[0].tolist())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--resume", action="store_true", help="resume latest checkpoint")
    ap.add_argument("--steps", type=int, default=0, help="override max_steps")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    tc = TrainConfig(**cfg["train"])
    mc = ModelConfig(**cfg.get("model", {}))
    tag = cfg["tag"]
    personality = cfg["personality"]
    run_dir = os.path.join(tc.checkpoint_dir, tag)
    os.makedirs(run_dir, exist_ok=True)

    with open(os.path.join(run_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=1)

    torch.manual_seed(tc.seed)
    np.random.seed(tc.seed)

    data_dir = cfg["data"]["dataset_dir"]
    tok = SimpleBPETokenizer.from_file(cfg["data"]["tokenizer_json"])

    def load_set(suffix: str) -> MixedDataset:
        d = np.load(os.path.join(data_dir, f"{personality}_{suffix}.npz"))
        meta_path = os.path.join(data_dir, f"{personality}_{suffix}_meta.npz")
        meta = np.load(meta_path) if os.path.exists(meta_path) else None
        is_synth = meta["is_synth"] if meta is not None else None
        return MixedDataset(d["ids"], d["mask"], is_synth, cfg["data"]["mixture"], tc.seed)

    train_ds = load_set("train")
    val_ds = load_set("val")
    log(f"train={len(train_ds.ids)} val={len(val_ds.ids)} mixture={cfg['data']['mixture']}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = TinyGPT(mc).to(device)
    if tc.precision == "bf16":
        model = model.to(torch.bfloat16)

    params = [p for p in model.parameters() if p.requires_grad]
    no_decay = [p for p in params if p.dim() < 2]
    decay = [p for p in params if p.dim() >= 2]
    opt = torch.optim.AdamW(
        [
            {"params": no_decay, "weight_decay": 0.0},
            {"params": decay, "weight_decay": tc.weight_decay},
        ],
        lr=tc.lr,
        betas=(tc.beta1, tc.beta2),
    )

    start_step = 0
    best_val = float("inf")
    best_path = os.path.join(run_dir, "best.pt")
    if args.resume:
        latest = os.path.join(run_dir, "latest.pt")
        if os.path.exists(latest):
            ck = torch.load(latest, map_location=device, weights_only=False)
            model.load_state_dict(ck["model"])
            opt.load_state_dict(ck["optimizer"])
            start_step = ck["step"]
            best_val = ck.get("best_val", float("inf"))
            log(f"resumed from step {start_step} (best_val={best_val:.4f})")

    max_steps = args.steps or tc.max_steps
    log_file = open(os.path.join(run_dir, "metrics.jsonl"), "a", encoding="utf-8")
    total_tokens = 0
    t0 = time.time()

    def lr_at(step: int) -> float:
        if step < tc.warmup_steps:
            return tc.lr * (step + 1) / tc.warmup_steps
        frac = (step - tc.warmup_steps) / max(1, max_steps - tc.warmup_steps)
        return tc.min_lr + 0.5 * (tc.lr - tc.min_lr) * (1 + math.cos(math.pi * min(frac, 1.0)))

    model.train()
    opt.zero_grad(set_to_none=True)
    step_tokens = 0
    for step in range(start_step, max_steps):
        for _ in range(tc.grad_accum):
            ids, mask = train_ds.batch(tc.batch_size)
            ids, mask = ids.to(device), mask.to(device)
            x, t = make_targets(ids, mask)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16, enabled=tc.precision == "bf16"):
                _, loss = model(x, t)
            (loss / tc.grad_accum).backward()
            step_tokens += int((t != -100).sum())

        if tc.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(params, tc.grad_clip)
        for g in opt.param_groups:
            g["lr"] = lr_at(step)
        opt.step()
        opt.zero_grad(set_to_none=True)
        total_tokens += step_tokens
        step_tokens = 0

        if step % tc.log_every == 0 or step == max_steps - 1:
            lr = opt.param_groups[0]["lr"]
            dt = time.time() - t0
            rec = {
                "step": step,
                "loss": round(loss.item(), 4),
                "lr": round(lr, 6),
                "tokens": total_tokens,
                "tok_s": round(total_tokens / max(dt, 1e-9)),
                "elapsed_s": round(dt, 1),
            }
            log(f"step {step:5d} loss {loss.item():.4f} lr {lr:.2e} | {total_tokens/1e6:.2f}M tok @ {rec['tok_s']/1e3:.1f} ktok/s")
            log_file.write(json.dumps(rec) + "\n")
            log_file.flush()

        if (step + 1) % tc.eval_every == 0 or step == max_steps - 1:
            vloss = eval_loss(model, val_ds, tc.eval_samples // 20 + 1, tc.precision, device)
            sample = generate_sample(model, tok, cfg, device)
            rec = {"step": step, "val_loss": round(vloss, 4), "sample": sample}
            log(f"  eval@step {step}: val_loss {vloss:.4f}")
            log(f"  sample: {sample!r}")
            log_file.write(json.dumps(rec) + "\n")
            log_file.flush()
            if vloss < best_val:
                best_val = vloss
                torch.save({"model": model.state_dict(), "cfg": mc, "step": step, "best_val": best_val}, best_path)
                log(f"  new best -> {best_path}")

        if (step + 1) % tc.save_every == 0 or step == max_steps - 1:
            torch.save(
                {"model": model.state_dict(), "optimizer": opt.state_dict(), "step": step + 1, "best_val": best_val},
                os.path.join(run_dir, "latest.pt"),
            )

    log(f"done: {tag} best_val={best_val:.4f} total_tokens={total_tokens}")
    log_file.close()


if __name__ == "__main__":
    main()