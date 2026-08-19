# Colosseum

Two tiny (≈5M parameter) Transformers — an **Optimist** and a **Pessimist** — trained
**from scratch** to converse, argue and disagree live over WebSockets on the public web.

> This is not "two prompts talking to each other". These are two independently trained
> tiny language models with deliberately different conversational priors, continuously
> participating in an adversarial conversation arena under severe production resource
> constraints (≈512 MB RAM, ≈0.1 CPU).

## The system at a glance

- 12 debate topics are generated every hour by an external LLM (strict JSON schema).
- Every 5 minutes a new 20-turn debate runs: Optimist ×10 turns, Pessimist ×10 turns,
  50 generated tokens max per turn.
- An external LLM judge scores each completed debate (winner, 3 metrics, final score).
- Historical data lives in Supabase PostgreSQL; live state in Upstash Redis.
- The React + TypeScript frontend streams the debate live over WebSockets and auto-
  recovers on reconnect. No accounts, no comments, no user content — visitors only watch.
- A 48-hour rolling retention window keeps the showcase fresh.

## Repos / dirs

| dir | purpose |
| --- | --- |
| `training/` | model architecture, datasets, tokenizer, training, evaluation (local, RTX 5050) |
| `server/` | production Python backend (FastAPI + WebSockets + scheduler + judge + storage) |
| `client/` | React + TypeScript live arena |
| `models/` | exported final weights (optimist / pessimist) |

## Model details

```
optimist parameters = 4,987,392
pessimist parameters = 4,987,392
```

Decoder-only transformer: vocab 4096 (custom BPE), context 512, d_model 256, 8 heads,
6 layers, SwiGLU FFN, RoPE, tied embeddings. Trained from scratch on a curated corpus of
natural conversation (OASST1, Apache-2.0) plus structured synthetic personality and
adversarial dialogue data. See `training/ARCHITECTURE.md` and `training/DATA.md`.

## Honest limitations

- 5M parameters is tiny by modern LLM standards; these are specialised conversational
  experiments, not general-purpose assistants.
- They may hallucinate, repeat themselves, or drift off topic; they possess no reliable
  world knowledge and are deliberately trained to avoid depending on current affairs or
  factual databases.
- Debates are entertainment/research demonstrations, and the external judge is also a
  model — therefore imperfect.

## Status

In progress — Phase 1 (research + environment) complete. See PLAN.md for the full mission.