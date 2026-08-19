# BENCHMARKS.md — Measured Results

Status: **populated progressively during Phases 2–7, 11.** Every number here is measured
on this machine / environment, never estimated.

## Environment

- OS: Windows 11, Python 3.11.15 (root venv), torch 2.11.0+cu128
- GPU: NVIDIA GeForce RTX 5050 Laptop (Blackwell, sm_120, 8 GB VRAM, driver 610.88)
- CPU/RAM targets: Render Free ≈ 0.1 vCPU, 512 MB RAM

## Tokenizer

| metric | value |
| --- | --- |
| vocabulary size | 4096 (filled) |
| trained on | curated corpus (dataset-vNNN) |
| avg tokens/message | TBD |
| OOV on hold-out | TBD |
| BPE merges | TBD |

## Model

| metric | optimist | pessimist |
| --- | --- | --- |
| parameters | 4,987,392 | 4,987,392 |
| checkpoints | TBD | TBD |
| final val loss | TBD | TBD |
| training steps | TBD | TBD |

## Training speed (RTX 5050, fp32/bf16, chunked CE over sequence)

Measured 2026-08-19 with `training/scripts/bench_train.py`. The output head (vocab 4096)
dominates VRAM; chunked cross-entropy over the sequence dimension keeps peaks low.

| config | tokens/sec | VRAM peak | note |
| --- | --- | --- | --- |
| fp32, batch 64, seq 512 | 46.4 ktok/s | 7.6 GB | near VRAM limit; not used |
| bf16, batch 64, seq 512 | 87.2 ktok/s | 7.7 GB | near VRAM limit; not used |
| bf16, batch 32, seq 512, accum 2 | 46.1 ktok/s | **3.9 GB** | chosen default (safe headroom) |
| bf16, batch 64, seq 256, accum 2 | 67.7 ktok/s | 3.9 GB | faster per step; used if packing yields short seqs |

Effective throughput ≈ 46–68 ktok/s → ~165–245 M tokens/hour. A 10M-token corpus trains in
~2–4 minutes per model. Multiple mixtures/experiments are cheap.

## Inference (CPU)

| backend | startup (s) | RSS (MB) | ms/token | 50-token turn (s) |
| --- | --- | --- | --- | --- |
| numpy fp32 | TBD | TBD | TBD | TBD |
| torch cpu fp32 | TBD | TBD | TBD | TBD |

## Debate arena (local, hundreds of debates)

| metric | value |
| --- | --- |
| repetition rate | TBD |
| derailment rate | TBD |
| EOS-stops-within-50-tokens rate | TBD |
| personality stability (judge score) | TBD |

## Resource-constrained simulation (~512 MB / 0.1 CPU)

Method: psutil RSS tracking + single-core affinity + throughput extrapolation (Docker
unavailable; documented approximation). See server/scripts/bench_resource.py.

| phase | RSS (MB) | CPU% | note |
| --- | --- | --- | --- |
| startup | TBD | TBD | TBD |
| steady-state | TBD | TBD | TBD |
| during debate | TBD | TBD | TBD |
| peak | TBD | TBD | TBD |