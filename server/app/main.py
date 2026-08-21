"""Colosseum server: FastAPI app with REST + WebSocket."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .debate_engine import DebateRunner, make_engine
from .judge import judge_debate
from .llm import make_judge_llm, make_llm
from .pubsub import hub
from .scheduler import Scheduler
from .storage import make_storage
from .topics import TopicProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("colosseum")

app = FastAPI(title="Colosseum", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

scheduler: Optional[Scheduler] = None
_scheduler_task: Optional[asyncio.Task] = None
_started_at = time.time()


def _make_redis():
    if not settings.upstash_redis_url:
        return None
    try:
        import redis

        url = settings.upstash_redis_url.strip()
        if url.startswith("https://") or url.startswith("http://"):
            host = url.split("://", 1)[1].strip("/")
            token = (settings.upstash_redis_token or "").strip()
            if token:
                url = f"rediss://default:{token}@{host}:6379"
            else:
                url = f"rediss://{host}:6379"
        client = redis.Redis.from_url(url, socket_timeout=3)
        client.ping()
        log.info("connected to Upstash Redis")
        return client
    except Exception as e:  # noqa: BLE001
        log.warning("redis unavailable: %s", e)
        return None



@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler, _scheduler_task
    storage = make_storage()
    engine = make_engine()
    runner = DebateRunner(engine)
    redis_client = await asyncio.to_thread(_make_redis)
    topics = TopicProvider(make_llm(), redis=redis_client)
    scheduler = Scheduler(storage, runner, topics, judge_client=make_judge_llm(), redis=redis_client)
    _scheduler_task = asyncio.create_task(scheduler.run())
    log.info("server ready (models loaded, scheduler task spawned)")
    yield
    scheduler.stop()
    if _scheduler_task:
        _scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _scheduler_task


app.router.lifespan_context = lifespan



@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "uptime_s": int(time.time() - _started_at),
        "next_debate_in_s": max(0, int(scheduler._next_deadline - time.time())) if scheduler else None,
        "interval_s": settings.debate_interval_seconds,
        "llm": "mock" if settings.llm_mock else settings.llm_model,
        "storage": settings.storage_mode,
    }


@app.get("/api/debates")
async def list_debates(limit: int = 50, status: Optional[str] = "completed"):
    debates = await asyncio.to_thread(scheduler.storage.list_debates, max(1, min(limit, 100)))
    if status:
        return [d for d in debates if d.get("status") == status]
    return debates


@app.get("/api/debates/{debate_id}")
async def get_debate(debate_id: str):
    debate = await asyncio.to_thread(scheduler.storage.get_debate, debate_id)
    if debate is None:
        raise HTTPException(status_code=404, detail="debate not found")
    turns = await asyncio.to_thread(scheduler.storage.get_turns, debate_id)
    debate["turns"] = turns
    return debate


@app.websocket("/ws/debates")
async def ws_debates(ws: WebSocket):
    await ws.accept()
    q = hub.subscribe()
    try:
        if scheduler is not None:
            debates = await asyncio.to_thread(scheduler.storage.list_debates, 20)
            completed_debates = [d for d in debates if d.get("status") == "completed"]
            await ws.send_json({"type": "recent", "debates": completed_debates})

            # Check if there is an ongoing live debate
            running = next((d for d in debates if d.get("status") == "running"), None)
            if running:
                turns = await asyncio.to_thread(scheduler.storage.get_turns, running["id"])
                await ws.send_json({
                    "type": "active_debate",
                    "debate_id": running["id"],
                    "topic": running["topic"],
                    "status": "running",
                    "turns": turns,
                })
        while True:
            ev = await q.get()
            await ws.send_json(ev)
    except WebSocketDisconnect:
        pass
    finally:
        hub.unsubscribe(q)



_DIST = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "client", "dist"))
if os.path.isdir(_DIST):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=_DIST, html=True), name="client")
    log.info("serving client from %s", _DIST)
else:
    @app.get("/")
    def root():
        return {"service": "colosseum", "status": "ok", "uptime_s": int(time.time() - _started_at)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
