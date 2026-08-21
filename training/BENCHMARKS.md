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
| version | tokenizer-v002 |
| vocabulary size | 4096 (filled) |
| BPE merges | 3892 |
| special tokens | 8 (`<PAD> <UNK> <BOS> <EOS> <TOPIC> <OPTIMIST> <PESSIMIST> <TURN>`) |
| trained on | `training/tokenizer/corpus-v002.txt` (base_curated.jsonl: 450,802 lines / 11,826,810 words) |
| avg tokens/message | 39.53 (sample n=2255) |
| OOV on hold-out | 0.0000% (<UNK> never emitted on the base corpus) |

## Model

| metric | optimist | pessimist |
| --- | --- | --- |
| parameters | 4,987,392 | 4,987,392 |
| checkpoints | final_optimist/best.pt | final_pessimist/best.pt |
| final val loss | 3.4834 | 3.4566 |
| training steps | 2,000 | 2,000 |
| loss tokens processed | 16.79 M | 17.23 M |
| dataset | dataset-v002 (base 1.0 : synth 1.0) | dataset-v002 (base 1.0 : synth 1.0) |

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

Measured 2026-08-20 on the dev machine (numpy engine from `server/app/np_inference.py`,
torch engine from `training/src/model.py`). One 50-token turn, 3-turn history, fp32.

| backend | startup (s) | RSS (MB) | ms/token | 50-token turn (s) |
| --- | --- | --- | --- | --- |
| numpy fp32 | 0.05 | 96 | ~4.0 (250 tok/s) | ~0.20 |
| torch cpu fp32 | 0.05 | n/a | ~4.8 (208 tok/s) | ~0.24 |

Deployment uses the numpy engine (no torch dependency). RSS stays under the 512 MB free-tier
budget with large headroom.

## Debate arena (200 local debates, final dataset-v002 models, seed 7)

| metric | optimist | pessimist |
| --- | --- | --- |
| avg turns per debate | 11.12 (both) | |
| avg tokens per turn | 42.9 | 40.5 |
| hit-50-token-cap rate | 0.532 | 0.384 |
| blank-turn (derailment) rate | 0.001 | 0.000 |
| repetition (4-gram) rate | 0.008 | 0.007 |
| lexical diversity | 0.786 | 0.786 |
| personality lean delta | +0.0125 | +0.0061 |

Full protocol + interpretation in EVALUATION.md.

## Resource-constrained simulation (~512 MB / 0.1 CPU)

Method: psutil RSS tracking of the whole process tree while the real server runs debates
(local storage, 1 s interval, mock judge). Single-core affinity is not applied on Windows,
so CPU% is the dev machine's multi-core number (documented approximation).

Measured 2026-08-20 with `server/scripts/bench_resource.py` (75 s window):

| phase | RSS (MB) | CPU | note |
| --- | --- | --- | --- |
| peak | 152.8 | 9.48 cores (1 s peak) | budget 512 MB → **OK** |
| mean / steady-state | 137.5 | 2.17 cores mean | budget ~0.1 → HOT on dev cores |
| during debate | ~96–153 | n/a | numpy forward ~4 ms/token |

2 debates completed within the 75 s window at 1 s cadence (debate runtime dominates the
interval). Memory budget is comfortably met; the CPU figure reflects the dev laptop's
multi-core numpy throughput and is expected to be the limiting factor on a 0.1 vCPU Render
instance — the 5-minute debate cadence absorbs it (worst case ~20 turns × ~1–15 s/turn).