# Colosseum

Two tiny (~5M parameter) Transformer language models — an **Optimist** and a **Pessimist** — trained **from scratch** on consumer hardware, debating each other live 24/7 over WebSockets on the public web.

```
                  ┌───────────────────────────────────────────────┐
                  │       External Topic Generator (LLM)          │
                  │       12 hourly topics → Redis cache          │
                  └──────────────────────┬────────────────────────┘
                                         │ (every 5 min)
                                         ▼
                  ┌───────────────────────────────────────────────┐
                  │          Colosseum Server (FastAPI)           │
                  │   NumPy CPU Inference Engine (~96 MB RSS)     │
                  │                                               │
                  │    ┌─────────────────┐   ┌─────────────────┐  │
                  │    │  OPTIMIST (5M)  │ ◄─┤  PESSIMIST (5M) │  │
                  │    │  (SwiGLU/RoPE)  ├──►│  (SwiGLU/RoPE)  │  │
                  │    └─────────────────┘   └─────────────────┘  │
                  │         Alternating 20-Turn Debate Loop       │
                  └──────────────┬─────────────────┬──────────────┘
                                 │                 │
             WebSocket Stream    │                 │ Post-Debate Transcript
                                 ▼                 ▼
             ┌───────────────────────┐   ┌────────────────────────┐
             │   React + TS Arena    │   │  External Judge (LLM)  │
             │  Procedural Audio +   │   │  Scores, Winner & Log  │
             │  Live Canvas Stream   │   └───────────┬────────────┘
             └───────────────────────┘               │
                                                     ▼
                                         ┌────────────────────────┐
                                         │  Supabase (PostgreSQL) │
                                         │  48h Rolling Retention │
                                         └────────────────────────┘
```

> **Not two system prompts talking to each other.**  
> These are two independently initialized and trained causal language models with fundamentally different learned conversational priors. They run under severe production resource constraints (~512 MB RAM, ~0.1 vCPU) with zero PyTorch runtime dependencies in production.

---

## Table of Contents

- [The Core Concept](#the-core-concept)
- [System Architecture & Lifecycle](#system-architecture--lifecycle)
- [Transformer Architecture & Exact Math](#transformer-architecture--exact-math)
- [Data Strategy & Licensing Integrity](#data-strategy--licensing-integrity)
- [The Zero-Torch NumPy Inference Engine](#the-zero-torch-numpy-inference-engine)
- [Server Architecture & Resilience](#server-architecture--resilience)
- [Frontend Experience](#frontend-experience)
- [Repository Structure](#repository-structure)
- [Local Development Guide](#local-development-guide)
- [Training & Model Reproduction](#training--model-reproduction)
- [Deployment (Render Free + Supabase + Upstash)](#deployment-render-free--supabase--upstash)
- [Empirical Benchmarks](#empirical-benchmarks)
- [Honest Limitations](#honest-limitations)

---

## The Core Concept

Most "AI vs AI" demos are API wrappers passing system prompts like `"You are an optimist"` and `"You are a pessimist"` to commercial 70B+ parameter models.

Colosseum takes the opposite path:
1. **Train from scratch**: Build a custom ~5M parameter decoder-only transformer architecture and train two separate model checkpoints from random weights on a single RTX 5050 Laptop GPU.
2. **Embed persona through pretraining distribution**: Give both models a shared foundation in natural English dialogue (grammar, conversational turn-taking, common sense), then steer them with curated and hand-authored synthetic corpora (constructive solution-finding for the Optimist; skepticism, risk awareness, and edge-case dissection for the Pessimist).
3. **Adversarial conversational arena**: Pit them against each other in real-time debates on philosophical, lifestyle, ethical, and hypothetical dilemmas where neither model has an objective "right" answer.
4. **Extreme deployment efficiency**: Run continuous production inference on Render's free tier (512 MB memory limit, fractional CPU) using a hand-coded NumPy inference engine that executes the full transformer forward pass and KV caching without loading heavy ML frameworks.

---

## System Architecture & Lifecycle

Every debate follows an automated, self-healing pipeline:

1. **Topic Generation**: Every hour, an external LLM generates 12 provocative, balanced debate questions adhering to a strict JSON schema. These are filtered for safety/repetition and cached in Upstash Redis. If the LLM is unreachable, the system seamlessly pulls from a curated 40-topic fallback pool.
2. **Scheduling & Coordination**: An asynchronous scheduler kicks off a new debate every 5 minutes (`DEBATE_INTERVAL_SECONDS=300`). Distributed locks in Redis prevent duplicate debate runs during server restarts.
3. **Turn Execution**:
   - The debate runs for up to 20 turns (10 turns per model, 50 new tokens max per turn).
   - The Optimist opens, addressing `<TOPIC> {topic}`.
   - The Pessimist reads the conversation history (within the 512-token context window) and responds.
   - The NumPy engine evaluates logits with top-k (25), top-p (0.90), temperature (0.65), and repetition penalty (1.20).
   - Turns terminate upon generating special tokens (`<EOS>`, `<TURN>`, `<OPTIMIST>`, `<PESSIMIST>`, `<TOPIC>`) or hitting the token limit.
4. **Real-Time Streaming**: Each turn event is published to an internal asyncio pub/sub hub and broadcast over WebSockets (`/ws/debates`) to connected clients.
5. **Post-Debate Judging**: Once finished, the complete debate transcript is evaluated by an external LLM judge. The judge awards a win, scores each model on a 1–10 scale across persuasiveness, rebuttal quality, and persona fidelity, and delivers a concise commentary. (A deterministic heuristic judge acts as an automated fallback if the LLM judge is offline).
6. **Persistence & 48-Hour Pruning**: Completed debates and turns are committed to Supabase PostgreSQL (or local JSON files in dev mode). A background janitor cleans records older than 48 hours every 6 hours.

---

## Transformer Architecture & Exact Math

Both models share an identical decoder-only architecture inspired by modern LLaMA/Mistral design principles, scaled down to fit within a ~5M parameter budget.

### Configuration

| Hyperparameter | Value | Rationale |
| :--- | :--- | :--- |
| **Parameters** | **4,987,392** | Sweet spot for conversational coherence on consumer GPU training |
| **Vocabulary Size** | **4,096** | Custom Byte-Pair Encoding (BPE). Avoids wasting parameter budget on large embedding tables |
| **Context Length** | **512 tokens** | Accommodates topic + ~7–9 prior debate turns for rebuttal context |
| **Layers ($n_{layers}$)** | **6** | Provides sufficient abstraction depth without width starvation |
| **Hidden Dim ($d_{model}$)** | **256** | Balanced width for 5M parameter scale |
| **Attention Heads ($n_{heads}$)** | **8** | Head dimension $d_{head} = 32$; allows multi-faceted attention across speakers |
| **FFN Architecture** | **SwiGLU** | Gated feed-forward network with SiLU activation ($d_{ffn} = 512$) |
| **Positional Embeddings** | **RoPE** | Rotary Position Embeddings ($\theta = 10000$); zero parameter overhead |
| **Normalisation** | **Pre-LayerNorm** | Applied before attention and FFN blocks ($\epsilon = 10^{-5}$) |
| **Embedding Tying** | **Yes** | Input embeddings and output projection head share identical weights |
| **Linear Biases** | **None** | Pure bias-free linear transformations; LayerNorm weights/biases retained |

### Exact Parameter Breakdown

Let $V = 4096$, $D = 256$, $L = 6$, $F = 512$:

$$\text{Total Parameters} = V \cdot D + L \times \left( D \cdot 3D + D \cdot D + 4D + 3 \cdot (D \cdot F) \right) + 2D$$

| Component | Mathematical Formula | Parameter Count |
| :--- | :--- | ---: |
| **Tied Token Embedding / Output Head** | $V \times D = 4096 \times 256$ | 1,048,576 |
| **Per Layer: Query / Key / Value Projections** | $D \times 3D = 256 \times 768$ | 196,608 |
| **Per Layer: Attention Output Projection** | $D \times D = 256 \times 256$ | 65,536 |
| **Per Layer: Pre-Attention & Pre-FFN Norms** | $2 \times (2 \times D) = 2 \times 512$ | 1,024 |
| **Per Layer: SwiGLU Gate Projection** | $D \times F = 256 \times 512$ | 131,072 |
| **Per Layer: SwiGLU Up Projection** | $D \times F = 256 \times 512$ | 131,072 |
| **Per Layer: SwiGLU Down Projection** | $F \times D = 512 \times 256$ | 131,072 |
| **Subtotal Per Transformer Block** | | **656,384** |
| **Total for 6 Transformer Blocks** | $6 \times 656,384$ | 3,938,304 |
| **Final LayerNorm** | $2 \times D = 2 \times 256$ | 512 |
| **Positional Parameters (RoPE)** | Fixed mathematical frequencies | 0 |
| **Grand Total** | | **4,987,392** |

*Note: Embeddings account for ~21.0% of the parameter budget, leaving ~79% of capacity for deep attention and feed-forward routing.*

### Canonical Formatting

Training data and inference prompts use the exact same structured format:

```text
<BOS>
<TOPIC> Is it better to be spontaneous or organized?
<OPTIMIST> Spontaneity invites genuine discovery and keeps daily life from becoming mechanical routine.
<TURN>
<PESSIMIST> Unchecked spontaneity without structure usually results in avoidable chaos and broken commitments.
<TURN>
<OPTIMIST> Structure has its place, but over-indexing on caution kills creativity before it starts.
<TURN>
...
<EOS>
```

Special token mappings: `<PAD>=0`, `<UNK>=1`, `<BOS>=2`, `<EOS>=3`, `<TOPIC>=4`, `<OPTIMIST>=5`, `<PESSIMIST>=6`, `<TURN>=7`.

---

## Data Strategy & Licensing Integrity

At 5M parameters, training on unfiltered web dumps produces incoherent gibberish. The data strategy prioritizes **high signal density** and **strict licensing compliance**.

### 1. The Curated Natural Base Corpus
To establish natural grammar, conversational cadence, and commonsense reasoning, both models share a foundational corpus:
- **OpenAssistant (OASST1 & OASST2)**: Human-authored conversational trees under Apache-2.0.
- **PersonaChat / ConvAI2**: Natural multi-turn dialogue under MIT.
- **UltraChat 200k**: Filtered conversational turns under MIT.
- **SODA (allenai/soda)**: Social commonsense dialogue under CC-BY-4.0 (reservoir sampled).

### 2. Hard License Exclusions
To ensure all model weights and source materials can be openly distributed without legal encumbrances, datasets with Non-Commercial (`CC-BY-NC`), Share-Alike (`CC-BY-SA`), or custom restrictive terms were **strictly excluded**:
- *DailyDialog* (CC-BY-NC-SA 4.0) — Excluded.
- *EmpatheticDialogues* (CC-BY-NC 4.0) — Excluded.
- *HuggingFace no_robots* (CC-BY-NC 4.0) — Excluded.
- *Anthropic HH-RLHF* — Excluded (usage terms advise against dialogue pretraining).
- *LMSYS-Chat-1M* — Excluded (gated license).

### 3. Hand-Authored Synthetic Personality Pipeline
Rather than distilling from OpenAI/Anthropic APIs during pretraining, we built a deterministic synthetic generation engine (`training/datasets/synthetic/`):
- **Type A (Adversarial Exchanges)**: 4,000 full 5-turn debate transcripts across 400 philosophical/lifestyle topics.
- **Type B (Personality Continuations)**: 2,000 prompt pairs leading into optimistic vs pessimistic trajectories.
- **Type C (Contrasting Interpretations)**: 1,200 pairs providing opposite readings of identical life events.
- **Type D (Rebuttals)**: 1,500 target-tagged counterarguments addressing specific opponent claims.
- **Type E (Concessions & Reframing)**: 1,000 agree-and-pivot conversational exchanges.
- **Type F (Topic Banks)**: 400 clean debate prompts spanning 20 non-factual domains.

### 4. Mixture Ratio Experiments
During Phase 4 pretraining sweeps (800 steps each on `dataset-v002`), we benchmarked mixtures of base dialogue vs synthetic personality data on a held-out balanced validation split:

| Experiment | Base : Synth Ratio | Balanced Val Loss | Result |
| :--- | :--- | :--- | :--- |
| `exp_a` | 1.0 : 0.00 | 4.6735 | Weak persona distinction; generic conversation |
| `exp_b` | 1.0 : 0.25 | 4.3452 | Improved coherence |
| `exp_c` | 1.0 : 0.50 | 4.2095 | Stronger debate stance |
| **`exp_d`** | **1.0 : 1.00** | **4.0883** | **Optimal balance of natural English & sharp persona** |
| `exp_e` | 1.0 : 2.00 | 4.1119 | Persona overfitting; repetitive phrasing |

**Winner**: The 1:1 mixture ratio was chosen for the final 2,000-step training run.

---

## The Zero-Torch NumPy Inference Engine

Standard PyTorch builds (with CPU or CUDA binaries) consume 800 MB+ of disk space and push baseline process memory above 300 MB. On a 512 MB free-tier container running FastAPI, Uvicorn, and background tasks, PyTorch triggers Out-Of-Memory (OOM) kills.

To solve this, production inference is powered by a custom pure-Python/NumPy engine ([`server/app/np_inference.py`](file:///d:/colosseum/server/app/np_inference.py)):

- **Weight Storage**: Exported `.npz` files (~19.9 MB per model) loaded as 32-bit floating-point NumPy arrays.
- **KV Caching**: Per-layer key/value state caching for previously generated tokens, transforming generation complexity from $\mathcal{O}(N^2)$ to $\mathcal{O}(N)$.
- **Math Implementation**:
  - Exact Rotary Position Embedding (RoPE) complex vector rotations.
  - Pre-LayerNorm with scaling and epsilon stabilization.
  - SwiGLU gating: $\text{SwiGLU}(x) = (x W_{gate} \cdot \text{SiLU}(x W_{gate})) \odot (x W_{up}) W_{down}$.
  - Logit sampling with temperature, top-k filtering, nucleus (top-p) sampling, and repetition penalty.
- **Memory Footprint**: Process memory sits at **~96 MB RSS steady-state** (peaking at ~152 MB during active debate processing).
- **Latency**: Evaluates at **~4.0 ms per token** (~250 tokens/sec on modern dev CPU), completing a 50-token turn in ~0.2 seconds.

---

## Server Architecture & Resilience

The backend is built with FastAPI, asyncio, and resilient fallback patterns designed for high reliability on ephemeral free-tier infrastructure.

### Resilience & Self-Healing
- **Boot Recovery**: Render free instances sleep after inactivity and restart abruptly. On startup, [`Scheduler.recover()`](file:///d:/colosseum/server/app/scheduler.py) inspects Supabase and Redis, marks orphaned `running` debates as `failed`, and flushes stale Redis locks.
- **Graceful Redis Degradation**: If Upstash Redis is unreachable or credentials are omitted, the server transparently falls back to in-memory state and local sets without crashing.
- **Topic Fallback Cascade**: If the external LLM topic endpoint experiences rate limits or timeouts, the topic provider automatically falls back to an offline pool of 40 hand-curated debate dilemmas.
- **48-Hour Rolling Retention**: Every 6 hours, an automated reaper executes `delete_older_than(48)` across database tables to prevent table bloat.

### REST & WebSocket API Surface

| Endpoint | Method / Protocol | Description |
| :--- | :--- | :--- |
| `/api/health` | `GET` | System telemetry: uptime, storage mode, LLM status, countdown to next debate |
| `/api/debates` | `GET` | Paginated list of recent debates (filterable by status: `completed`, `running`) |
| `/api/debates/{id}` | `GET` | Complete debate record including full ordered transcript of turns |
| `/ws/debates` | `WebSocket` | Real-time event stream (`recent`, `active_debate`, `turn`, `thinking`, `completed`, `failed`) |
| `/` | `GET` | Root status endpoint / serves compiled React static assets in production |

---

## Frontend Experience

The frontend is a bespoke, brutalist-inspired single-page application built with React 18, TypeScript, and Vite.

- **Real-Time Arena View**: Displays the live debate as tokens stream, featuring dynamic speaker focus, turn counters, and countdown clocks.
- **Verdict Archive**: Searchable archive of past debates with judge scores, win/loss breakdowns, and commentary analysis.
- **Procedural Web Audio Engine**: A synthesized audio system built directly on the browser's native `AudioContext` (no heavy MP3 assets). Plays subtle mechanical typing clicks, low-frequency thinking hums, and victory fanfares.
- **Dynamic Particle Canvas**: Hardware-accelerated canvas background with ambient particle drifting that shifts visual intensity during debate turns.
- **Kinetic Typography & Motion**: Smooth page transitions and scrolling powered by Lenis, GSAP ticker synchronization, and Framer Motion.

---

## Repository Structure

```text
colosseum/
├── client/                     # React + TypeScript Frontend
│   ├── src/
│   │   ├── App.tsx             # Root layout & navigation tabs
│   │   ├── Arena.tsx           # Live debate arena & WebSocket handler
│   │   ├── History.tsx         # Historical debate archive & scoreboard
│   │   ├── Transcript.tsx      # Formatted debate dialogue renderer
│   │   ├── CanvasBackground.tsx# Procedural particle canvas
│   │   ├── sound.ts            # Web Audio procedural sound synthesizer
│   │   └── styles.css          # Monospace brutalist design system
│   ├── package.json
│   └── vite.config.ts
│
├── server/                     # Production Python Backend
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint, routes, WebSocket hub
│   │   ├── scheduler.py        # Asynchronous debate scheduler & recovery
│   │   ├── np_inference.py     # Zero-Torch pure NumPy inference engine
│   │   ├── debate_engine.py    # Turn-by-turn debate orchestration
│   │   ├── judge.py            # LLM evaluation & heuristic mock judge
│   │   ├── topics.py           # Hourly LLM topic batching & fallback pool
│   │   ├── storage.py          # Dual storage layer (Supabase PostgREST / Local JSON)
│   │   ├── tokenizer.py        # Portable BPE tokenizer runtime
│   │   └── config.py           # Environment settings loader
│   ├── scripts/
│   │   ├── bench_np_inference.py # CPU latency & throughput benchmark
│   │   └── bench_resource.py     # Memory (RSS) & CPU profiling harness
│   ├── tests/
│   │   └── test_integration.py # Full REST + WebSocket integration tests
│   └── requirements.txt        # Lightweight runtime dependencies (NumPy, FastAPI, Supabase)
│
├── training/                   # Model Pretraining & Research
│   ├── src/
│   │   ├── model.py            # PyTorch reference Transformer implementation
│   │   ├── tokenizer.py        # Custom BPE tokenizer trainer & encoder
│   │   ├── dataset.py          # Memory-mapped dataset loader & batcher
│   │   └── curation.py         # Text deduplication, normalization & cleaning
│   ├── datasets/
│   │   ├── synthetic/          # Hand-authored adversarial & persona banks
│   │   └── SOURCES.md          # Dataset licensing verification audit
│   ├── configs/                # YAML training & sweep configurations
│   ├── scripts/
│   │   ├── build_tokenizer.py  # Train custom 4096-vocab BPE tokenizer
│   │   ├── build_dataset.py    # Compile raw data into dataset-v002 format
│   │   ├── train.py            # PyTorch training loop (AdamW, bf16, Cosine)
│   │   ├── export_model.py     # Export PyTorch weights to NumPy .npz arrays
│   │   └── debate_arena.py     # 200-debate automated evaluation runner
│   ├── ARCHITECTURE.md         # Transformer math & architectural decisions
│   ├── DATA.md                 # Corpus strategy & curation rules
│   ├── EVALUATION.md           # Model evaluation protocol & loss tables
│   └── BENCHMARKS.md           # Measured training & inference telemetry
│
├── models/                     # Exported Production Weights
│   ├── optimist/               # model.npz, config.json, tokenizer-portable.json
│   └── pessimist/              # model.npz, config.json, tokenizer-portable.json
│
├── supabase/
│   └── migrations/
│       └── 001_init.sql        # Database schema for debates & turns (with RLS)
│
├── render.yaml                 # Render Blueprint for zero-touch deployment
├── requirements-train.txt      # PyTorch training dependencies (torch, transformers)
└── INITIAL_PLAN.md             # Comprehensive 12-phase system design blueprint
```

---

## Local Development Guide

You can run the entire Colosseum arena locally without external cloud dependencies using the local JSON storage mode and mock LLM providers.

### 1. Prerequisites
- Python 3.10+ (Python 3.11 recommended)
- Node.js 18+ and npm
- Exported model weights in `models/optimist/` and `models/pessimist/` (already included in repository)

### 2. Backend Setup (Local Mode)

```bash
# Navigate to server directory
cd server

# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install lightweight dependencies
pip install -r requirements.txt

# Run server with local storage and fast 10s debate cadence
set STORAGE_MODE=local
set DATA_DIR=../data
set DEBATE_INTERVAL_SECONDS=10
python -m uvicorn app.main:app --port 8011 --reload
```

The backend is now live at `http://localhost:8011`. Interactive API documentation is available at `http://localhost:8011/docs`.

### 3. Frontend Setup

```bash
# Navigate to client directory
cd client

# Install dependencies
npm install

# Start Vite development server (proxies API and WebSockets to :8011)
npm run dev
```

Open `http://localhost:5173` in your browser to watch live debates.

### 4. Running Integration Tests

The integration test suite spawns a live server in-process, connects over WebSockets, simulates a full debate lifecycle, and verifies database persistence:

```bash
cd server
pytest tests/test_integration.py -v
```

---

## Training & Model Reproduction

To retrain the models from scratch on your own GPU:

```bash
# 1. Install training dependencies (including PyTorch with CUDA support)
pip install -r requirements-train.txt

# 2. Train the custom BPE tokenizer (creates vocab_size=4096)
python training/scripts/build_tokenizer.py

# 3. Assemble and compile the dataset (dataset-v002)
python training/scripts/build_dataset.py

# 4. Train the Optimist model (2,000 steps, AdamW, bf16)
python training/scripts/train.py --config training/configs/train_final_optimist.yaml

# 5. Train the Pessimist model (2,000 steps, AdamW, bf16)
python training/scripts/train.py --config training/configs/train_final_pessimist.yaml

# 6. Export PyTorch checkpoints to portable NumPy .npz bundles
python training/scripts/export_model.py --personality optimist --checkpoint training/experiments/final_optimist/best.pt
python training/scripts/export_model.py --personality pessimist --checkpoint training/experiments/final_pessimist/best.pt

# 7. Run the 200-debate automated evaluation arena
python training/scripts/debate_arena.py --num-debates 200 --out training/experiments/arena
```

---

## Deployment (Render Free + Supabase + Upstash)

The application is architected to run permanently for free across three managed tiers:

### 1. Database Setup (Supabase)
1. Create a free project at [supabase.com](https://supabase.com).
2. Open the **SQL Editor** and run the migration script in [`supabase/migrations/001_init.sql`](file:///d:/colosseum/supabase/migrations/001_init.sql).
3. Copy your project URL, anon key, and service role key from **Project Settings > API**.

### 2. Cache Setup (Upstash Redis)
1. Create a free serverless Redis database at [upstash.com](https://upstash.com).
2. Copy the REST URL and Token.

### 3. Web Service Deployment (Render)
1. Connect your repository to [Render](https://render.com).
2. Use the provided [`render.yaml`](file:///d:/colosseum/render.yaml) blueprint or configure a Web Service with:
   - **Environment**: Python
   - **Plan**: Free
   - **Build Command**: `cd server && pip install -r requirements.txt`
   - **Start Command**: `cd server && python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`
3. Configure the following environment secrets in Render:

```ini
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-openrouter-or-openai-key
LLM_MODEL=openai/gpt-4o-mini
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
UPSTASH_REDIS_URL=https://your-redis.upstash.io
UPSTASH_REDIS_TOKEN=your-upstash-token
STORAGE_MODE=supabase
```

---

## Empirical Benchmarks

All metrics below were measured directly during testing and evaluation:

### Training Throughput (NVIDIA RTX 5050 Laptop GPU, 8 GB VRAM)
- **Batch Size 32, Sequence Length 512 (bf16)**: 46.1 ktok/s peak throughput (~3.9 GB VRAM peak).
- **Training Time**: ~2.5 minutes per 2,000-step run per model.
- **Final Validation Loss (dataset-v002)**:
  - Optimist: **3.4834**
  - Pessimist: **3.4566**

### Runtime & Memory (NumPy Inference Engine)
- **Startup Time**: ~0.05 seconds.
- **Steady-State Memory (RSS)**: ~96 MB RAM.
- **Active Debate Peak Memory**: ~152.8 MB RAM (comfortably below the 512 MB Render ceiling).
- **Per-Token Forward Latency**: ~4.0 ms/token (~250 tokens/second).

### 200-Debate Arena Results (Seed 7)

| Evaluation Metric | Optimist | Pessimist |
| :--- | :---: | :---: |
| **Average Turns Per Debate** | 11.12 | 11.12 |
| **Average Tokens Per Turn** | 42.9 | 40.5 |
| **50-Token Cap Hit Rate** | 53.2% | 38.4% |
| **Blank Turn / Derailment Rate** | 0.1% | 0.0% |
| **4-Gram Repetition Rate** | 0.8% | 0.7% |
| **Lexical Diversity** | 0.786 | 0.786 |

---

## Honest Limitations

1. **5M Parameters is Small**: These models are specialized conversational stylists, not knowledge engines. They will hallucinate if asked for factual trivia, historical dates, or technical coding solutions.
2. **Intentional Knowledge Insulation**: The models are deliberately trained on dialogue dynamics and subjective reasoning, avoiding reliance on current events or live internet retrieval.
3. **Turn Degradation on Long Horizons**: While the models maintain strong coherence across 6–10 turns, context drift can occur as debates approach the 20-turn limit.
4. **Imperfect Judge**: The debate judge is an external LLM and may exhibit slight stylistic preferences despite strict rubric constraints.

---

## License

This project is open-source under the terms of the **Apache License 2.0**. All upstream training datasets were audited to ensure full compliance with Apache-2.0, MIT, and CC-BY-4.0 redistribution rights. See [`training/datasets/SOURCES.md`](file:///d:/colosseum/training/datasets/SOURCES.md) and [`LICENSE`](file:///d:/colosseum/LICENSE) for details.