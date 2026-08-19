# training/ — From-scratch Tiny Transformer Training

This directory contains everything needed to reproduce the two ~5M-parameter
conversational models. It is **not** deployed to Render.

## Layout

```
training/
├── ARCHITECTURE.md      # exact architecture + parameter accounting
├── DATA.md              # corpus strategy
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
python training/scripts/build_tokenizer.py --config training/configs/tokenizer.yaml

# 3. build dataset mixture
python training/scripts/build_dataset.py --config training/configs/data_vNNN.yaml

# 4. train (Phase 4 experiments or final models)
python training/scripts/train.py --config training/configs/train_optimist.yaml

# 5. evaluate + run local debate arena
python training/scripts/evaluate.py --model models/optimist
python training/scripts/debate_arena.py --config training/configs/generation.yaml
```

## Conventions

- Every run logs config hash + dataset version + tokenizer version for reproducibility.
- Checkpoints are resumable; best-checkpoint is selected on validation loss.
- Final weights export to `models/optimist/` and `models/pessimist/` in NumPy format
  for the lightweight server runtime.