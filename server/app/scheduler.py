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


class Scheduler:
    def __init__(self, storage: Storage, runner: DebateRunner, topics: TopicProvider, judge_client=None):
        self.storage = storage
        self.runner = runner
        self.topics = topics
        self.judge = judge_client or make_judge_llm()
        self._next_deadline: float = 0.0
        self._stopping = False

    async def run(self) -> None:
        """Main loop: sleep until the next slot, run one debate, repeat."""
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
        """On boot: fail any debates left in 'running' by a crashed process."""
        for d in await asyncio.to_thread(self.storage.list_debates, 100):
            if d.get("status") == "running":
                await asyncio.to_thread(self.storage.finish_debate, d["id"], None, "failed")
                log.warning("recovered stale debate %s", d["id"])

    async def _run_one(self) -> None:
        topic = await asyncio.to_thread(self.topics.next)
        if not topic:
            log.warning("no topics available; skipping slot")
            return
        debate_id = await asyncio.to_thread(self.storage.create_debate, topic, "running")

        async def on_event(ev: dict) -> None:
            if ev["type"] == EVENT_TURN:
                await asyncio.to_thread(
                    self.storage.append_turn, debate_id, ev["speaker"], ev["text"], ev["tokens"], ev["position"]
                )
            elif ev["type"] == EVENT_STARTED:
                pass
            await hub.publish({"debate_id": debate_id, **ev})

        log.info("debate %s: %r", debate_id, topic)
        try:
            turns, meta = await self.runner.run(topic, on_event)
            verdict = await asyncio.to_thread(judge_debate, self.judge, topic, turns)
            await asyncio.to_thread(self.storage.finish_debate, debate_id, verdict["winner"], "completed")
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
            await hub.publish({"debate_id": debate_id, "type": EVENT_FAILED, "error": str(e)[:200]})

    def stop(self) -> None:
        self._stopping = True