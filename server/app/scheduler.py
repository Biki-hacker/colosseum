"""Scheduler: runs debates on a fixed cadence (default 5 min), recovers stale
in-flight debates on boot, and cleans up old records. Single asyncio task."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from .config import settings
from .debate_engine import DebateRunner, EVENT_COMPLETED, EVENT_FAILED, EVENT_STARTED, EVENT_TURN
from .judge import judge_debate
from .llm import make_judge_llm
from .pubsub import hub
from .storage import Storage
from .topics import TopicProvider

log = logging.getLogger("colosseum.scheduler")

CLEANUP_INTERVAL_S = 6 * 3600


import json


class Scheduler:
    def __init__(self, storage: Storage, runner: DebateRunner, topics: TopicProvider, judge_client=None, redis=None):
        self.storage = storage
        self.runner = runner
        self.topics = topics
        self.judge = judge_client or make_judge_llm()
        self.redis = redis
        self._next_deadline: float = 0.0
        self._stopping = False
        self._active_key = "colosseum:active_debate"
        self._live_turn_key = "colosseum:live_turn"

    async def run(self) -> None:
        """Main loop: recover stale sessions, ensure topics, sleep until the next slot, run one debate, repeat."""
        await self.recover()
        self._next_deadline = time.time()
        last_cleanup = 0.0
        while not self._stopping:
            now = time.time()
            if now >= self._next_deadline:

                self._next_deadline = now + settings.debate_interval_seconds
                await self._run_one()
            if now - last_cleanup > CLEANUP_INTERVAL_S:
                last_cleanup = now
                await asyncio.to_thread(self.storage.delete_older_than, settings.retention_hours)
            await asyncio.sleep(1.0)

    async def recover(self) -> None:
        """On boot: inspect Supabase DB and Redis cache for any ongoing/stale sessions."""
        log.info("running startup recovery check on Supabase DB and Redis cache...")
        try:
            debates = await asyncio.to_thread(self.storage.list_debates, 100)
            stale_count = 0
            for d in debates:
                if d.get("status") == "running":
                    await asyncio.to_thread(self.storage.finish_debate, d["id"], None, "failed")
                    stale_count += 1
                    log.warning("recovered and cleared stale Supabase debate %s", d["id"])
            if stale_count == 0:
                log.info("no ongoing/stale debate sessions in Supabase DB")
        except Exception as e:  # noqa: BLE001
            log.warning("recover storage check failed: %s", e)

        if self.redis is not None:
            try:
                active = self.redis.get(self._active_key)
                if active:
                    log.warning("cleared stale active session in Redis: %s", active)
                    self.redis.delete(self._active_key)
                    self.redis.delete(self._live_turn_key)
                else:
                    log.info("no ongoing session in Redis cache")
            except Exception as e:  # noqa: BLE001
                log.warning("recover redis check failed: %s", e)

        # Ensure 12 hourly topics are ready in Redis cache / generated from LLM
        await asyncio.to_thread(self.topics.ensure_hourly_batch)

    async def _run_one(self) -> None:
        topic = await asyncio.to_thread(self.topics.next)
        if not topic:
            log.warning("no topics available; skipping slot")
            return
        debate_id = await asyncio.to_thread(self.storage.create_debate, topic, "running")

        if self.redis is not None:
            try:
                self.redis.set(
                    self._active_key,
                    json.dumps({"debate_id": debate_id, "topic": topic, "status": "running", "started_at": time.time()}),
                    ex=600,
                )
            except Exception:
                pass

        async def on_event(ev: dict) -> None:
            if ev["type"] == EVENT_TURN:
                await asyncio.to_thread(
                    self.storage.append_turn, debate_id, ev["speaker"], ev["text"], ev["tokens"], ev["position"]
                )
                if self.redis is not None:
                    try:
                        self.redis.set(
                            self._live_turn_key,
                            json.dumps({"debate_id": debate_id, "turn": ev["position"], "speaker": ev["speaker"], "text": ev["text"]}),
                            ex=300,
                        )
                    except Exception:
                        pass
            elif ev["type"] == EVENT_STARTED:
                pass
            await hub.publish({"debate_id": debate_id, **ev})

        log.info("debate %s: %r", debate_id, topic)
        try:
            turns, meta = await self.runner.run(topic, on_event)
            verdict = await asyncio.to_thread(judge_debate, self.judge, topic, turns)
            await asyncio.to_thread(self.storage.finish_debate, debate_id, verdict["winner"], "completed")
            if self.redis is not None:
                try:
                    self.redis.delete(self._active_key)
                    self.redis.delete(self._live_turn_key)
                    self.redis.set(
                        "colosseum:last_debate",
                        json.dumps({"debate_id": debate_id, "winner": verdict["winner"], "scores": verdict}),
                        ex=86400,
                    )
                except Exception:
                    pass
            await hub.publish(
                {
                    "debate_id": debate_id,
                    "type": EVENT_COMPLETED,
                    "winner": verdict["winner"],
                    "optimist_score": verdict["optimist_score"],
                    "pessimist_score": verdict["pessimist_score"],
                    "commentary": verdict["commentary"],
                }
            )
        except Exception as e:  # noqa: BLE001
            log.exception("debate %s failed", debate_id)
            await asyncio.to_thread(self.storage.finish_debate, debate_id, None, "failed")
            if self.redis is not None:
                try:
                    self.redis.delete(self._active_key)
                    self.redis.delete(self._live_turn_key)
                except Exception:
                    pass
            await hub.publish({"debate_id": debate_id, "type": EVENT_FAILED, "error": str(e)[:200]})

    def stop(self) -> None:
        self._stopping = True