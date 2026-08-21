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
natural conversation (OASST1 + OASST2 Apache-2.0, PersonaChat MIT, UltraChat MIT,
SODA CC-BY-4.0 — see `training/datasets/SOURCES.md`) plus hand-authored synthetic
personality and adversarial dialogue data. See `training/ARCHITECTURE.md` and
`training/DATA.md`.

## Running locally

1. Backend (Windows example; requires the exported models in `models/optimist|pessimist`):
   ```
   cd server
   python -m venv venv
   venv\Scripts\pip install -r requirements.txt
   set STORAGE_MODE=local
   set DATA_DIR=..\data
   set DEBATE_INTERVAL_SECONDS=10
   venv\Scripts\python -m uvicorn app.main:app --port 8011
   ```
2. Frontend (dev server with API proxy to the backend):
   ```
   cd client
   npm install
   npm run dev          # http://localhost:5173
   ```
   A production build is committed to `client/dist/` and served automatically by the
   backend at `/` when present.

3. Tests (integration suite spawns a real server and runs a full debate over REST + WS):
   ```
   cd server
   venv\Scripts\python -m pip install pytest pytest-timeout websockets
   venv\Scripts\python -m pytest tests -v
   ```

## Deploying (Render Free + Supabase + Upstash)

1. Run `supabase/migrations/001_init.sql` once in the Supabase SQL editor.
2. Create a Supabase project and an Upstash Redis database; copy the URLs/keys.
3. Create a Render web service from this repo (or use `render.yaml`), plan **free**.
   Set these as secret env vars in the Render dashboard:
   `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `JUDGE_MODEL` (optional),
   `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
   `UPSTASH_REDIS_URL`, `UPSTASH_REDIS_TOKEN`.
   `STORAGE_MODE=supabase` and the debate cadence are preconfigured in `render.yaml`.
4. The service self-heals: stale `running` debates are failed on boot, the topic pool
   falls back to 40 curated topics if the LLM is unavailable, Redis is optional
   (degrades gracefully), and records older than `RETENTION_HOURS` (48) are deleted
   automatically every 6 hours.

## Status

Phases 1–11 complete: architecture, data (5 licensed datasets + authored synthetic),
tokenizer-v002, dataset-v002, mixture experiments (winner base 1 : synth 1), final
Optimist + Pessimist models trained (2,000 steps) and exported to `models/`, NumPy CPU
inference engine, full server, React client, integration + resource tests, and a 200-debate
arena verification. Phase 12 (deployment configs) complete. See `training/EVALUATION.md`
for measured results. The only remaining dependency is a live `LLM_API_KEY` in `.env`
for the production topic generator and judge services (not for model training, which is
finished). See PLAN.md.

## Honest limitations

- 5M parameters is tiny by modern LLM standards; these are specialised conversational
  experiments, not general-purpose assistants.
- They may hallucinate, repeat themselves, or drift off topic; they possess no reliable
  world knowledge and are deliberately trained to avoid depending on current affairs or
  factual databases.
- Debates are entertainment/research demonstrations, and the external judge is also a
  model — therefore imperfect.
- The exported models were trained on the final authored-synthetic dataset (dataset-v002);
  the personality split is deliberate but non-caricature — both models acknowledge the
  opponent, so the split shows up as tone and framing rather than stark opposition (see
  `training/EVALUATION.md`).