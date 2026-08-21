"""Fair comparison of Phase 4 experiments: all models evaluated on the SAME balanced
val distribution (base 1.0 : synth 1.0) + multi-topic sample generation."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import torch

from src.config import ModelConfig
from src.model import TinyGPT
from src.simple_tokenizer import SimpleBPETokenizer

EXPERIMENTS = ["exp_a", "exp_b", "exp_c", "exp_d", "exp_e"]
BALANCED = {"base": 1.0, "synth": 1.0}

SAMPLE_PROMPTS = [
    ("Should people always pursue their passion?", "Passion sounds nice, but most people cannot afford to chase their dreams forever."),
    ("Is technology making us less social?", "Screens keep us from actually talking to each other."),
    ("Would life be better if everyone could read minds?", "Nobody wants their private thoughts exposed."),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="training/datasets/processed/dataset-v002")
    ap.add_argument("--tokenizer", default="training/tokenizer/tokenizer-portable.json")
    ap.add_argument("--checkpoint-root", default="training/experiments")
    args = ap.parse_args()

    tok = SimpleBPETokenizer.from_file(args.tokenizer)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    d = np.load(os.path.join(args.dataset, "optimist_val.npz"))
    meta = np.load(os.path.join(args.dataset, "optimist_val_meta.npz"))
    ids = torch.from_numpy(d["ids"]).to(torch.int64).to(device)
    mask = torch.from_numpy(d["mask"]).to(device)
    is_synth = meta["is_synth"]

    def val_loss(model: TinyGPT, steps: int = 20, bs: int = 16) -> float:
        model.eval()
        rng = np.random.default_rng(0)
        base_idx = np.where(~is_synth)[0]
        synth_idx = np.where(is_synth)[0]
        total, count = 0.0, 0
        with torch.no_grad():
            for _ in range(steps):
                nb = min(bs // 2, len(base_idx))
                ns = bs - nb
                idx = np.concatenate([rng.choice(base_idx, nb, replace=True), rng.choice(synth_idx, ns, replace=True)])
                x = ids[idx][:, :-1]
                t = ids[idx][:, 1:]
                m = mask[idx][:, 1:]
                t = torch.where(m, t, torch.full_like(t, -100))
                with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                    _, loss = model(x, t)
                n = (t != -100).sum().item()
                total += loss.item() * n
                count += n
        model.train()
        return total / max(count, 1)

    def samples(model: TinyGPT) -> list[str]:
        out = []
        for topic, opp in SAMPLE_PROMPTS:
            prompt = f"<BOS><TOPIC> {topic}<TURN><PESSIMIST> {opp}<TURN><OPTIMIST>"
            ids_p = tok.encode(prompt)
            gen = model.generate(
                torch.tensor([ids_p], device=device),
                max_new_tokens=50,
                temperature=0.8,
                top_k=40,
                top_p=0.9,
                repetition_penalty=1.15,
                eos_id=tok.eos_id,
            )
            out.append(tok.decode(gen[0].tolist()))
        return out

    results = {}
    for name in EXPERIMENTS:
        path = os.path.join(args.checkpoint_root, name, "best.pt")
        if not os.path.exists(path):
            print(f"skip {name}: no checkpoint")
            continue
        ck = torch.load(path, map_location=device, weights_only=False)
        model = TinyGPT(ck["cfg"]).to(device).to(torch.bfloat16)
        model.load_state_dict(ck["model"])
        vl = val_loss(model)
        smps = samples(model)
        results[name] = {"val_loss_balanced": round(vl, 4), "samples": smps}
        print(f"{name}: balanced val loss = {vl:.4f}")

    with open(os.path.join(args.checkpoint_root, "experiment_comparison.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)

    for name, r in results.items():
        print(f"\n=== {name} (val {r['val_loss_balanced']}) ===")
        for s in r["samples"]:
            print(" ", s[:160])


if __name__ == "__main__":
    main()