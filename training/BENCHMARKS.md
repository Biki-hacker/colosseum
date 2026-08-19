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

## Training speed (RTX 5050)

| config | tokens/sec | samples/sec | VRAM peak | wall time |
| --- | --- | --- | --- | --- |
| fp32, batch 64 | TBD | TBD | TBD | TBD |
| bf16, batch 64 | TBD | TBD | TBD | TBD |

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