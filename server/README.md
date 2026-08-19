# server/ — Production Backend

Python backend for the live debate arena. FastAPI + WebSockets, designed for Render Free
(≈512 MB RAM, ≈0.1 CPU, restartable at any time).

Populated in Phase 7–8. High-level design:

- single uvicorn worker (memory constraint)
- asyncio scheduler aligned to 5-minute wall-clock slots, restart-safe
- Redis (Upstash REST) `SET NX` locks prevent duplicate debate sessions
- debate engine runs exactly 20 turns (Optimist/Pessimist alternating), one authoritative
  generation pipeline shared by all WebSocket viewers
- external LLM (OpenAI-compatible) generates 12 topics/hour and judges completed debates
  via strict JSON schemas, with retry + fallback paths
- Supabase PostgreSQL is the source of truth; Redis holds transient live state
- 48-hour retention cleanup runs at startup + hourly, in batches
- endpoints: `/health`, `/ready`, `/metrics`, WS `/ws/live`, REST snapshot/state

See `README.md` inside this directory for full details after implementation.