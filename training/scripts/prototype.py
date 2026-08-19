"""Phase 2 prototype verification: build model, check params, forward, loss,
generation, checkpoint save/load. Run after building the tokenizer."""

from __future__ import annotations

import argparse
import os
import sys
import time

import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import ModelConfig
from src.model import TinyGPT
from src.simple_tokenizer import SimpleBPETokenizer

SPECIALS = ["<PAD>", "<UNK>", "<BOS>", "<EOS>", "<TOPIC>", "<OPTIMIST>", "<PESSIMIST>", "<TURN>"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", default="training/tokenizer/tokenizer-portable.json")
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    cfg = ModelConfig()
    tok = SimpleBPETokenizer.from_file(args.tokenizer)
    print(f"vocab size = {tok.vocab['<UNK>'] + len(tok.vocab) if False else len(tok.vocab)}")  # placeholder
    print(f"vocab size = {len(tok.vocab)}")

    print("building model ...")
    t0 = time.time()
    model = TinyGPT(cfg)
    print(f"  params = {model.param_count():,}  (expected {cfg.expected_params():,})")
    assert model.param_count() == cfg.expected_params(), "param count mismatch!"

    device = args.device if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"  device = {device}  (built in {time.time() - t0:.2f}s)")

    # forward + loss
    batch = torch.randint(0, cfg.vocab_size, (2, 64), device=device)
    targets = torch.randint(0, cfg.vocab_size, (2, 64), device=device)
    logits, loss = model(batch, targets)
    print(f"forward ok: logits {tuple(logits.shape)}, loss = {loss.item():.4f}")

    # generation with random weights
    prompt_ids = tok.encode("<BOS><TOPIC> Should people always pursue their passion?<OPTIMIST>")
    prompt = torch.tensor([prompt_ids], device=device)
    out = model.generate(prompt, max_new_tokens=50, temperature=0.8, top_k=40, top_p=0.9, eos_id=tok.eos_id)
    text = tok.decode(out[0].tolist())
    print(f"sample: {text!r}")

    # checkpoint save/load
    torch.save({"model": model.state_dict(), "cfg": cfg}, "training/checkpoints/prototype.pt")
    m2 = TinyGPT(cfg).to(device)
    sd = torch.load("training/checkpoints/prototype.pt", map_location=device, weights_only=False)
    m2.load_state_dict(sd["model"])
    logits2, _ = m2(batch, None)
    assert torch.allclose(logits, logits2, atol=1e-5), "checkpoint roundtrip mismatch"
    print("checkpoint save/load OK")

    print("PROTOTYPE OK")


if __name__ == "__main__":
    main()