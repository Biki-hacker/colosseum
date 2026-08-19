"""Export trained checkpoints to deployable format: models/<personality>/
containing model.safetensors + config.json + tokenizer-portable.json + README."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import torch
from safetensors.torch import save_file
import numpy as np

from src.config import ModelConfig
from src.model import TinyGPT

MODELS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))


def export(personality: str, ckpt: str, tokenizer_json: str, out_dir: str) -> None:
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    cfg: ModelConfig = ck["cfg"]
    assert isinstance(cfg, ModelConfig), type(cfg)
    model = TinyGPT(cfg)
    model.load_state_dict(ck["model"])
    model.eval()

    os.makedirs(out_dir, exist_ok=True)
    sd = dict(model.state_dict())
    if cfg.tie_embeddings:
        sd.pop("lm_head.weight", None)  # tied with tok_emb.weight; rebuilt on load
    save_file(sd, os.path.join(out_dir, "model.safetensors"))
    np.savez(os.path.join(out_dir, "model.npz"), **{k: v.float().numpy() for k, v in sd.items()})
    cfg_dict = cfg.__dict__ if hasattr(cfg, "__dict__") else cfg.asdict()
    with open(os.path.join(out_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"model": cfg_dict, "personality": personality}, f, indent=2)
    shutil.copyfile(tokenizer_json, os.path.join(out_dir, "tokenizer-portable.json"))
    with open(os.path.join(out_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write(
            f"# {personality}\n\n"
            f"- params: {sum(p.numel() for p in model.parameters()):,}\n"
            f"- source checkpoint: {os.path.basename(ckpt)}\n"
            f"- steps: {ck.get('step')}  best_val: {ck.get('best_val')}\n"
            f"- files: model.safetensors, config.json, tokenizer-portable.json\n"
        )
    n_params = sum(p.numel() for p in model.parameters())
    print(f"{personality}: exported {n_params:,} params -> {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--personality", required=True, choices=["optimist", "pessimist"])
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--tokenizer", default="training/tokenizer/tokenizer-portable.json")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    out = args.out or os.path.join(MODELS_ROOT, args.personality)
    export(args.personality, args.checkpoint, args.tokenizer, out)


if __name__ == "__main__":
    main()