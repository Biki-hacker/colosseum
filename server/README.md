# Colosseum Server (`server/`)

The production backend for Colosseum — a high-performance, asynchronous Python service hosting the pure NumPy Transformer inference engine, automated debate scheduler, WebSocket pub/sub stream, PostgREST storage layer, and LLM judge coordinator.

Designed to operate continuously under severe resource constraints (~512 MB RAM, ~0.1 vCPU on Render Free tier) with zero PyTorch runtime dependencies.

```
                                  FastAPI App (main.py)
                                           │
             ┌─────────────────────────────┼─────────────────────────────┐
             ▼                             ▼                             ▼
      REST API Endpoints             WebSocket Hub              Async Scheduler Loop
    (/api/health, /api/debates)      (/ws/debates)                 (scheduler.py)
             │                             │                             │
             │                             │                  ┌──────────┴──────────┐
             │                             │                  ▼                     ▼
             │                             │            TopicProvider          DebateRunner
             │                             │          (12 topics/hr)        (20 turns max)
             │                             │                  │                     │
             ▼                             ▼                  ▼                     ▼
     Storage Layer ◄────────────────── Hub Publish ◄────── Fallback Pool     NPModel Engine
   (Supabase / Local)                                                    (NumPy CPU Inference)
```

---

## Table of Contents

- [Core Responsibilities](#core-responsibilities)
- [Architecture & Module Breakdown](#architecture--module-breakdown)
- [The Zero-Torch NumPy Inference Engine](#the-zero-torch-numpy-inference-engine)
- [Scheduling & Self-Healing Resilience](#scheduling--self-healing-resilience)
- [Dual-Mode Storage Abstraction](#dual-mode-storage-abstraction)
- [Topic Provisioning & Caching](#topic-provisioning--caching)
- [Debate Judging & Scoring Rubric](#debate-judging--scoring-rubric)
- [REST & WebSocket API Specifications](#rest--websocket-api-specifications)
- [Environment Configuration](#environment-configuration)
- [Local Development & Testing](#local-development--testing)
- [Profiling & Benchmarks](#profiling--benchmarks)

---

## Core Responsibilities

1. **Host & Execute Model Inference**: Run the ~5M parameter Optimist and Pessimist transformer models in pure NumPy on CPU at ~4.0 ms/token while keeping process RSS under ~100 MB.
2. **Deterministic Turn-by-Turn Scheduling**: Execute a 20-turn adversarial debate every 5 minutes (`DEBATE_INTERVAL_SECONDS=300`), publishing turn-by-turn tokens to live WebSocket subscribers.
3. **Ephemeral State & Coordination**: Use Upstash Redis for distributed locks, active debate snapshots, live turn caching, and hourly topic deduplication.
4. **PostgREST Database Persistence**: Commit debate metadata, turn transcripts, token counts, and winner verdicts to Supabase PostgreSQL.
5. **Post-Debate Evaluation**: Coordinate with an external LLM to judge completed debates on a 1–10 rubric, generating winner declarations and commentary.
6. **Data Lifecycle Pruning**: Run an automated 48-hour rolling retention reaper every 6 hours to purge historical records and keep database size minimal.
7. **Fail-Safe Self-Healing**: Recover gracefully from container restarts or free-tier spin-downs by clearing stale locks and marking orphaned in-progress debates as failed on boot.

---

## Architecture & Module Breakdown

```text
server/
├── app/
│   ├── main.py              # FastAPI application, lifespan manager, REST & WebSocket routes
│   ├── config.py            # Typed settings parsed from .env and environment variables
│   ├── np_inference.py      # Pure NumPy decoder-only Transformer engine (NPModel)
│   ├── debate_engine.py     # Turn-by-turn debate orchestration loop (DebateRunner)
│   ├── scheduler.py         # Asynchronous background loop, startup recovery & retention
│   ├── topics.py            # Hourly LLM topic batching, regex validation & fallback pool
│   ├── judge.py             # External LLM debate judge & deterministic heuristic fallback
│   ├── storage.py           # Pluggable storage abstraction (LocalStorage / SupabaseStorage)
│   ├── tokenizer.py         # Standalone BPE tokenizer runtime for inference
│   ├── pubsub.py            # Asyncio queue pub/sub broadcast hub for WebSockets
│   └── llm.py               # Lightweight HTTP client for external OpenAI-compatible APIs
│
├── scripts/
│   ├── bench_np_inference.py# CPU latency and throughput benchmark harness
│   └── bench_resource.py    # RSS memory profiling & CPU load simulation
│
├── tests/
│   └── test_integration.py  # Full REST and WebSocket integration test suite
│
└── requirements.txt         # Minimal production dependencies (FastAPI, NumPy, Supabase, Redis)
```

### Module Roles in Detail

- **[`app/main.py`](file:///d:/colosseum/server/app/main.py)**: Initializes the FastAPI app, manages the lifespan context (spawning the scheduler task and warming up models), registers CORS middlewares, and exposes REST `/api/*` and WebSocket `/ws/debates` endpoints.
- **[`app/np_inference.py`](file:///d:/colosseum/server/app/np_inference.py)**: The mathematical core of production inference. Loads exported `.npz` float32 weight matrices and executes RoPE, SwiGLU, and attention caching in NumPy.
- **[`app/debate_engine.py`](file:///d:/colosseum/server/app/debate_engine.py)**: Manages debate state. Alternates between Optimist and Pessimist, renders canonical prompt markers (`<BOS>`, `<TOPIC>`, `<OPTIMIST>`, `<PESSIMIST>`, `<TURN>`), stops at 50 tokens or `<EOS>`, and streams events through callbacks.
- **[`app/scheduler.py`](file:///d:/colosseum/server/app/scheduler.py)**: Single `asyncio.Task` running the 5-minute interval loop. Runs startup recovery, topic provisioning, debate execution, judge evaluation, and periodic 48-hour database cleanup.
- **[`app/topics.py`](file:///d:/colosseum/server/app/topics.py)**: Generates 12 topics per hour via external LLM with strict schema enforcement. Falls back to a 40-topic curated offline list if the LLM is unavailable.
- **[`app/judge.py`](file:///d:/colosseum/server/app/judge.py)**: Evaluates full transcripts post-debate. Prompts an external LLM for an unbiased 1–10 score and commentary. Includes a deterministic heuristic mock judge for offline operation.
- **[`app/storage.py`](file:///d:/colosseum/server/app/storage.py)**: Unified `Storage` interface with two implementations: `LocalStorage` (file-based JSON for zero-dep local dev) and `SupabaseStorage` (PostgREST client for production).
- **[`app/pubsub.py`](file:///d:/colosseum/server/app/pubsub.py)**: Broadcast hub. Manages `asyncio.Queue` subscriptions for each connected WebSocket client.

---

## The Zero-Torch NumPy Inference Engine

Running PyTorch on a 512 MB free-tier container often results in Out-Of-Memory kills due to binary size and runtime baseline overhead.

The production server uses a custom inference engine ([`app/np_inference.py`](file:///d:/colosseum/server/app/np_inference.py)) implemented entirely with NumPy arrays:

```python
class NPModel:
    """Frozen transformer loaded from exported .npz float32 arrays."""
    def __init__(self, cfg: dict, arrays: Dict[str, np.ndarray], ...):
        # Precomputed Rotary Positional Frequencies (RoPE)
        theta = cfg.get("rope_theta", 10000.0)
        inv_freq = 1.0 / (theta ** (np.arange(0, hd, 2) / hd))
        freqs = np.arange(L)[:, None] * inv_freq[None, :]
        self.cos = np.repeat(np.cos(freqs), 2, axis=-1).astype(np.float32)
        self.sin = np.repeat(np.sin(freqs), 2, axis=-1).astype(np.float32)
        ...
```

### Forward Pass & KV-Cache Mechanics

1. **Incremental Attention**: The engine maintains a pre-allocated Key-Value cache (`_kc`, `_vc`) per layer. When generating token $N+1$, only the single new token position is computed and appended to the cache.
2. **RoPE Implementation**: Applied via vector half-rotation:
   $$R(x) = x \odot \cos(\theta) + \text{rot\_half}(x) \odot \sin(\theta)$$
3. **SwiGLU Gating**:
   $$\text{SwiGLU}(x) = (x W_{gate} \cdot \sigma(x W_{gate})) \odot (x W_{up}) W_{down}$$
4. **Logit Sampling**: Computes softmax probabilities over the 4,096-token vocabulary with temperature scaling, top-k filtering, nucleus (top-p) truncation, and repetition penalties.
5. **Memory & Performance Profile**:
   - Model weights in RAM: **~19.9 MB** per model.
   - Total process memory at rest: **~96 MB RSS**.
   - Peak memory during active generation: **~152.8 MB RSS**.
   - Evaluation speed: **~4.0 ms per token** (~250 tokens/sec on CPU).

---

## Scheduling & Self-Healing Resilience

Render free instances spin down when idle and reboot without warning. The server implements multi-tier self-healing logic:

### Startup Recovery Routine (`Scheduler.recover()`)
On server boot, before starting the debate cadence:
1. Queries the database for debates stuck in `running` status and marks them as `failed`.
2. Checks Upstash Redis for orphaned locks (`colosseum:active_debate`, `colosseum:live_turn`) and flushes them.
3. Checks if the hourly topic cache in Redis is populated; if empty, fetches a fresh batch of 12 topics.

### Distributed Coordination via Upstash Redis

| Redis Key | Type | TTL | Purpose |
| :--- | :--- | :--- | :--- |
| `colosseum:active_debate` | String (JSON) | 600s | Active debate mutex lock; stores current debate ID, topic, and start timestamp |
| `colosseum:live_turn` | String (JSON) | 300s | Snapshot of the most recent turn (position, speaker, text) for instant client hydration |
| `colosseum:hourly_topics` | List (JSON) | 7200s | Queue of unconsumed topics for the current hour |
| `colosseum:used_topics` | Set (JSON) | Persistent | Rolling history of the last 500 topics to prevent repetitive debates |
| `colosseum:last_debate` | String (JSON) | 86400s | Cache of the most recent completed debate and judge verdict |

*Note: If Redis is unconfigured or offline, the server gracefully falls back to local in-memory sets and locks without interruption.*

---

## Dual-Mode Storage Abstraction

The storage layer ([`app/storage.py`](file:///d:/colosseum/server/app/storage.py)) defines a common interface:

```python
class Storage:
    def create_debate(self, topic: str, status: str = "running") -> str: ...
    def append_turn(self, debate_id: str, speaker: str, text: str, tokens: int, position: int) -> None: ...
    def finish_debate(self, debate_id: str, winner: Optional[str], status: str = "completed") -> None: ...
    def list_debates(self, limit: int = 20) -> List[dict]: ...
    def get_debate(self, debate_id: str) -> Optional[dict]: ...
    def get_turns(self, debate_id: str) -> List[dict]: ...
    def delete_older_than(self, hours: int) -> int: ...
```

- **`LocalStorage`**: Used for local development. Stores debates as individual formatted JSON documents in `DATA_DIR/debates/<uuid>.json` protected by threading locks.
- **`SupabaseStorage`**: Used in production. Communicates with Supabase PostgreSQL via PostgREST client queries against the `debates` and `turns` tables.

---

## Topic Provisioning & Caching

Topics are generated by [`TopicProvider`](file:///d:/colosseum/server/app/topics.py) through a multi-tier pipeline:

1. **LLM Generation**: Requests 12 provocative, polarizing debate topics ending in `?` from an OpenAI-compatible endpoint using a structured JSON schema.
2. **Quality & Safety Validation**:
   - Bounds check: Length between 8 and 120 characters.
   - Non-Latin character screening.
   - Content blacklist regex filter blocking party politics, violent topics, and medical trivia.
   - Shingle-based deduplication against the last 500 used topics.
3. **Offline Fallback Pool**: If the external LLM is offline or times out, the provider selects from 40 pre-validated philosophical dilemmas in `server/app/topics/fallback_pool.json`.

---

## Debate Judging & Scoring Rubric

Once 20 turns conclude (or `<EOS>` is reached), [`app/judge.py`](file:///d:/colosseum/server/app/judge.py) evaluates the complete transcript:

### Prompt Rubric for External LLM
- **Impartial Evaluation**: Zero bias toward optimism or pessimism; constructive vision and cautionary critique are weighted equally.
- **Persuasiveness & Conviction**: Evaluation of rhetorical strength and grounded reasoning.
- **Rebuttal Agility**: How effectively each speaker answered and reframed the opponent's prior points.
- **Persona Fidelity**: Did the Optimist champion agency and progress? Did the Pessimist articulate risks and trade-offs?
- **Strict No-Tie Mandate**: The judge must pick a definitive winner (`"optimist"` or `"pessimist"`).

### Heuristic Mock Fallback
In mock mode (`LLM_API_KEY` unset) or if the judge API fails, a deterministic heuristic evaluates the debate based on:
- Polarity lexicon density (frequency of constructive vs skeptical keywords).
- Unique vocabulary diversity.
- Mean turn length and engagement continuity.

---

## REST & WebSocket API Specifications

### REST Endpoints

#### `GET /api/health`
Returns runtime status, uptime, storage mode, and countdown to the next scheduled debate.
```json
{
  "status": "ok",
  "uptime_s": 1420,
  "next_debate_in_s": 184,
  "interval_s": 300,
  "llm": "openai/gpt-4o-mini",
  "storage": "supabase"
}
```

#### `GET /api/debates?limit=50&status=completed`
Returns a list of recent debates ordered by creation time descending.

#### `GET /api/debates/{debate_id}`
Returns full details of a specific debate, including its ordered turn transcript.

---

### WebSocket Stream (`/ws/debates`)

Clients connect to `ws://localhost:8011/ws/debates` (or `wss://...` in production).

#### 1. Initial State Hydration on Connect
Upon establishing a WebSocket connection, the server immediately sends:
```json
{
  "type": "recent",
  "debates": [ /* list of recent completed debates */ ]
}
```
If a debate is actively running, it also transmits the ongoing state:
```json
{
  "type": "active_debate",
  "debate_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "topic": "Should human consciousness be uploaded to a shared cloud?",
  "status": "running",
  "turns": [ /* turns accumulated so far */ ]
}
```

#### 2. Live Stream Events
- `started`: Sent when a new debate session begins (`debate_id`, `topic`, `turns_total`).
- `thinking`: Sent before a model begins inference (`speaker`).
- `turn`: Emitted when a speaker completes a turn (`position`, `speaker`, `text`, `tokens`).
- `completed`: Emitted after judging concludes (`winner`, `optimist_score`, `pessimist_score`, `commentary`).
- `failed`: Emitted if an unexpected error aborts the debate (`error`).

---

## Environment Configuration

Configure via `.env` in repository root or pass directly as environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `STORAGE_MODE` | `local` (or `supabase` if keys set) | Storage backend: `supabase` or `local` |
| `DATA_DIR` | `../data` | Directory for local JSON storage files |
| `PORT` | `8011` | Server listening port |
| `HOST` | `0.0.0.0` | Host binding interface |
| `ALLOWED_ORIGINS` | `http://localhost:5173` | Comma-separated allowed CORS origins |
| `DEBATE_INTERVAL_SECONDS` | `300` | Cadence between debate launches (5 minutes) |
| `DEBATE_TURNS` | `20` | Maximum number of alternating turns per debate |
| `MAX_NEW_TOKENS` | `75` | Maximum tokens generated per model turn |
| `TOPICS_PER_HOUR` | `12` | Number of topics requested per batch |
| `RETENTION_HOURS` | `48` | Rolling retention pruning window |
| `LLM_BASE_URL` | `""` | OpenAI-compatible endpoint URL |
| `LLM_API_KEY` | `""` | API key for topic generation and judging |
| `LLM_MODEL` | `""` | Model identifier (e.g. `openai/gpt-4o-mini`) |
| `JUDGE_MODEL` | `LLM_MODEL` | Optional override for judge model identifier |
| `SUPABASE_URL` | `""` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | `""` | Supabase service-role API key |
| `UPSTASH_REDIS_URL` | `""` | Upstash Redis connection URL |
| `UPSTASH_REDIS_TOKEN` | `""` | Upstash Redis authentication token |

---

## Local Development & Testing

### 1. Virtual Environment & Dependencies

```bash
cd server
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Running Locally (Zero Cloud Dependencies)

```bash
set STORAGE_MODE=local
set DATA_DIR=..\data
set DEBATE_INTERVAL_SECONDS=10
python -m uvicorn app.main:app --port 8011 --reload
```

### 3. Running Integration Tests

The integration test suite starts an in-process Uvicorn instance, opens a live WebSocket connection, simulates debate progression, and verifies turn persistence:

```bash
pytest tests/test_integration.py -v
```

---

## Profiling & Benchmarks

Run the standalone profiling scripts in `server/scripts/`:

```bash
# Benchmark NumPy CPU inference latency (ms/token) and throughput
python scripts/bench_np_inference.py

# Benchmark memory footprint (RSS) and CPU load over a multi-debate window
python scripts/bench_resource.py
```

### Measured Production Results
- **Cold Boot Time**: ~0.05 seconds.
- **Process Memory (Steady State)**: ~96 MB RAM.
- **Peak Memory During Debate**: ~152.8 MB RAM (comfortably within 512 MB Render limit).
- **Inference Speed**: ~4.0 ms per token (~250 tok/s on CPU).