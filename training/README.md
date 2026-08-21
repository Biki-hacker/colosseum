# training/ — From-scratch Tiny Transformer Training

This directory contains everything needed to reproduce the two ~5M-parameter
conversational models. It is **not** deployed to Render.

## Layout

```
training/
├── ARCHITECTURE.md      # exact architecture + parameter accounting
├── DATA.md              # corpus strategy
├── EVALUATION.md        # evaluation methodology + measured results (final models)
├── BENCHMARKS.md        # measured results (training/inference/debate/resource)
├── configs/             # YAML configs: model, data mixture, training, generation
├── datasets/
│   ├── SOURCES.md       # dataset licensing decisions
│   ├── scripts/         # download/filter/build pipelines
│   └── (raw/processed/synthetic build artifacts are gitignored)
├── src/                 # importable package (model, tokenizer, trainer, generation)
├── scripts/             # CLI entrypoints (train, eval, debate_arena, export)
├── tokenizer/           # tokenizer build + saved vocab/merges (gitignored)
├── checkpoints/         # training checkpoints (gitignored)
├── evaluation/          # eval suite + results
├── benchmarks/          # benchmark scripts + results
└── experiments/         # reproducible experiment runs (exp_001…)
```

## Reproduce

```powershell
# 1. env (root venv, CUDA 12.8 build for Blackwell)
pip install -r requirements-train.txt

# 2. build tokenizer on curated corpus
python training/scripts/build_tokenizer.py --files training/tokenizer/corpus-v002.txt --vocab-size 4096 --version tokenizer-v002

# 3. build dataset mixture
python training/scripts/build_dataset.py --config training/configs/data_v002.yaml

# 4. train (mixture experiments or final models)
python training/scripts/train.py --config training/configs/train_exp_a.yaml  # ... e
python training/scripts/train.py --config training/configs/train_final_optimist.yaml
python training/scripts/train.py --config training/configs/train_final_pessimist.yaml

# 5. evaluate + export + run local debate arena
python training/scripts/eval_experiments.py
python training/scripts/export_model.py --personality optimist --checkpoint training/experiments/final_optimist/best.pt
python training/scripts/export_model.py --personality pessimist --checkpoint training/experiments/final_pessimist/best.pt
python training/scripts/debate_arena.py --num-debates 200 --out training/experiments/arena
```

## Conventions

- Every run logs config hash + dataset version + tokenizer version for reproducibility.
- Checkpoints are resumable; best-checkpoint is selected on validation loss.
- Final weights export to `models/optimist/` and `models/pessimist/` in NumPy format
  for the lightweight server runtime.