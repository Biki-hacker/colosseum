"""Measure training throughput on the local GPU: tokens/sec, VRAM, fwd/bwd time."""

from __future__ import annotations

import os
import sys
import time

import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import ModelConfig
from src.model import TinyGPT


def bench(precision: str, batch: int, seq: int, steps: int = 10, warmup: int = 3) -> None:
    cfg = ModelConfig()
    torch.manual_seed(0)
    model = TinyGPT(cfg).to("cuda")
    opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.1, betas=(0.9, 0.95))
    dtype = torch.bfloat16 if precision == "bf16" else torch.float32
    if precision == "bf16":
        model = model.to(dtype)
    x = torch.randint(0, cfg.vocab_size, (batch, seq), device="cuda")
    t = torch.randint(0, cfg.vocab_size, (batch, seq), device="cuda")

    for i in range(warmup + steps):
        if i == warmup:
            torch.cuda.synchronize()
            t0 = time.perf_counter()
        opt.zero_grad(set_to_none=True)
        with torch.autocast(device_type="cuda", dtype=dtype, enabled=(precision == "bf16")):
            _, loss = model(x, t)
        loss.backward()
        opt.step()
    torch.cuda.synchronize()
    dt = time.perf_counter() - t0
    tokens = batch * seq * steps
    print(f"{precision:5s} batch={batch:3d} seq={seq:3d} | {tokens/dt/1e3:8.1f} ktok/s | {steps/dt:6.2f} step/s | VRAM {torch.cuda.max_memory_allocated()/1e6:7.1f} MB | loss {loss.item():.3f}")


if __name__ == "__main__":
    bench("fp32", 64, 512)
    bench("bf16", 64, 512)
    bench("bf16", 128, 512)