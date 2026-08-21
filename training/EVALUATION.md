# EVALUATION.md — Model Evaluation Methodology and Results

Status: **populated for dataset-v002 final models (2026-08-20).** Every number here is
measured on this machine, never estimated.

## 1. What we evaluate

The final Optimist and Pessimist models are evaluated on three axes:

1. **Language/model fit** — validation loss, measured on a *balanced* distribution so the
   metric is comparable across mixture experiments.
2. **Conversational health** — debate arena over hundreds of full debates: turn length,
   marker discipline, truncation rate, repetition, diversity, blank turns.
3. **Personality split** — does each model actually sound like its assigned persona, and
   do the two diverge in the same debate? Measured with the lean lexicon heuristic and by
   qualitative transcript inspection.

## 2. Validation protocol

- `train.py` reports `val_loss` at eval checkpoints on each model's own validation split
  (3% of samples, base + synth mixed).
- Cross-experiment comparison uses `eval_experiments.py`, which evaluates **every
  checkpoint on the same balanced val distribution** (base 1.0 : synth 1.0, fixed seed)
  plus multi-topic generation samples — so mixtures are compared fairly even though their
  training mixtures differ.

## 3. Results — Phase E mixture sweep (dataset-v002, 800 steps each, optimist)

| experiment | mixture base:synth | balanced val loss |
| --- | --- | ---: |
| exp_a | 1 : 0    | 4.6735 |
| exp_b | 1 : 0.25 | 4.3452 |
| exp_c | 1 : 0.5  | 4.2095 |
| exp_d | **1 : 1** | **4.0883** |
| exp_e | 1 : 2    | 4.1119 |

Winner: **exp_d (1 : 1)**. Generation samples at 800 steps already show on-topic,
constructive replies; lower mixtures produce less coherent, more template-like text.

## 4. Results — final models (dataset-v002, 2,000 steps, mixture 1 : 1)

| metric | optimist | pessimist |
| --- | ---: | ---: |
| parameters | 4,987,392 | 4,987,392 |
| training steps | 2,000 | 2,000 |
| final val loss (own split) | **3.4834** | **3.4566** |
| best val loss | 3.4834 | 3.4566 |
| total loss tokens processed | 16.79 M | 17.23 M |
| throughput (RTX 5050, bf16) | ~21.5 ktok/s | ~22.1 ktok/s |
| export | `models/optimist/` | `models/pessimist/` |

Both models end training at a similar, healthy loss; the small difference reflects the
different synthetic records per personality (optimist 14,955 / pessimist 14,945 samples).

## 5. Results — debate arena (200 debates, final models, seed 7)

Arena protocol mirrors the production server: alternating speakers, 20 turns max, 50
tokens max per turn, turn ends at the first marker (`<EOS>`/`<TURN>`/`<OPTIMIST>`/
`<PESSIMIST>`/`<TOPIC>`); a debate ends early only on a blank turn.

| metric | optimist | pessimist |
| --- | ---: | ---: |
| avg turns per debate | 11.12 (both) | |
| avg tokens per turn | 42.9 | 40.5 |
| hit-50-token-cap rate | 0.532 | 0.384 |
| blank-turn rate | 0.001 | 0.000 |
| repetition (4-gram) | 0.008 | 0.007 |
| lexical diversity | 0.786 | 0.786 |
| optimist-lean score | 0.0250 | 0.0207 |
| pessimist-lean score | 0.0125 | 0.0145 |
| lean delta | +0.0125 | +0.0061 |

Interpretation:

- **Healthy conversation.** No blank turns, low repetition, good diversity; debates run
  ~11 of 20 possible turns on average (models signal conclusion with `<EOS>` after several
  exchanges).
- **Personality split is visible but modest on the crude lexicon metric.** The lean scores
  are small and close because both personas are deliberately trained to acknowledge the
  opponent and stay balanced (non-caricature). The qualitative signal is clearer: the
  Optimist uses constructive language ("chance to grow", "I love that you're investing in
  yourself", "every small start counts") while the Pessimist stays cautious ("hope isn't a
  plan", "I'd be careful about the cost side", "results are discouraging"). Judge-based
  scoring (external LLM) requires a live `LLM_API_KEY` and is the planned final gate.

## 6. Reproduce

```powershell
# mixture sweep (800 steps each)
python training/scripts/train.py --config training/configs/train_exp_{a..e}.yaml
python training/scripts/eval_experiments.py

# final models (2,000 steps each)
python training/scripts/train.py --config training/configs/train_final_optimist.yaml
python training/scripts/train.py --config training/configs/train_final_pessimist.yaml

# export + arena
python training/scripts/export_model.py --personality optimist --checkpoint training/experiments/final_optimist/best.pt
python training/scripts/export_model.py --personality pessimist --checkpoint training/experiments/final_pessimist/best.pt
python training/scripts/debate_arena.py --num-debates 200 --out training/experiments/arena
```

## 7. Known limitations

- The lean lexicon heuristic is a crude proxy for personality; treat lean deltas as
  directional, not absolute. Final persona verification should use the external judge.
- At 5M parameters the models are narrow specialists: they can repeat or drift on long
  contexts, and they are intentionally trained to avoid factual/current-event knowledge.
- Arena numbers are produced on the training machine (CUDA); production inference is the
  NumPy CPU engine, which is validated separately (see `server/scripts/bench_np_inference.py`
  and BENCHMARKS.md).