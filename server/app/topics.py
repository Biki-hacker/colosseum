"""Topic provisioning: external LLM batches with fallback pool + dedupe."""

from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from .config import settings
from .llm import LLMClient

TOPIC_PROMPT = """You are the topic curator for a live debate arena between two AI personalities (an OPTIMIST and a PESSIMIST) with opposing worldviews.
Rules:
- Topics must be debatable: both sides have a fair, non-caricature case.
- Conversational, everyday language; one sentence each.
- No politics, religion, hate speech, health advice, or copyrighted material.
- Never repeat a topic already provided.
Return a JSON object with a "topics" array of strings."""

TOPIC_SCHEMA = {"type": "object", "properties": {"topics": {"type": "array", "items": {"type": "string"}}}}

TOPIC_BLOCKED = re.compile(
    r"\b(covid|vaccine|abortion|trump|biden|gaza|israel|palestine|ukraine|russia|china|kim|putin|"
    r"trump|election|gun control|racism|religion|jesus|allah|muslim|christian|suicide|drugs|"
    r"depression|anxiety|die|death|kill|murder|weight|fat|diabetes|diet)\b",
    re.IGNORECASE,
)


def validate_topic(text: str) -> Optional[str]:
    s = text.strip()
    if len(s) < 8 or len(s) > 120:
        return "bad length"
    if not s[-1] in "?.":
        return "not a question/statement"
    if TOPIC_BLOCKED.search(s):
        return "blocked content"
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", s):
        return "non-latin"
    return None


def dedupe_topics(topics: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in topics:
        key = re.sub(r"[^a-z0-9]", "", t.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return out


def load_fallback_pool(path: str = "") -> List[str]:
    path = path or settings.fallback_pool_file
    try:
        with open(path, encoding="utf-8") as f:
            pool = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return [t for t in pool if validate_topic(t) is None]


def generate_topic_batch(client: LLMClient, count: int = 12, used: Optional[set] = None) -> List[str]:
    used = used or set()
    data = client.chat(TOPIC_PROMPT, f"Generate {count} new topics.", json_schema=TOPIC_SCHEMA)
    topics = data.get("topics", []) if isinstance(data, dict) else []
    topics = [t for t in topics if isinstance(t, str)]
    topics = [t for t in topics if validate_topic(t) is None]
    topics = [t for t in topics if t.lower() not in used]
    return dedupe_topics(topics)[:count]


import logging

log = logging.getLogger("colosseum.topics")


class TopicProvider:
    """Round-robins: fresh LLM batch (12 topics/hour target) cached in Redis, then fallback pool.

    Dedupe against recently used topics (Redis set when available, else a
    per-process set seeded from storage)."""

    def __init__(self, client: LLMClient, redis=None):
        self.client = client
        self.redis = redis
        self.pool: List[str] = []
        self.pool_pos = 0
        self.used: set = set()
        self._batch: List[str] = []
        self._batch_pos = 0
        self._pool = load_fallback_pool()
        self._used_key = "colosseum:used_topics"
        self._hourly_key = "colosseum:hourly_topics"

    def _load_used(self) -> set:
        if self.redis is not None:
            try:
                raw = self.redis.get(self._used_key)
                return set(json.loads(raw)) if raw else set()
            except Exception:
                pass
        return self.used

    def _save_used(self, used: set) -> None:
        if self.redis is not None:
            try:
                self.redis.set(self._used_key, json.dumps(list(used)[-500:]))
            except Exception:
                pass

    def _remember(self, topic: str) -> None:
        self.used.add(topic)
        if len(self.used) > 500:
            self.used = set(list(self.used)[-500:])
        self._save_used(self.used)

    def _load_hourly_from_redis(self) -> List[str]:
        if self.redis is not None:
            try:
                raw = self.redis.get(self._hourly_key)
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, list) and data:
                        return data
            except Exception as e:
                log.warning("redis load hourly topics error: %s", e)
        return []

    def _save_hourly_to_redis(self, topics: List[str]) -> None:
        if self.redis is not None:
            try:
                self.redis.set(self._hourly_key, json.dumps(topics), ex=7200)
            except Exception as e:
                log.warning("redis save hourly topics error: %s", e)

    def ensure_hourly_batch(self) -> None:
        """Called on startup / when batch is empty: ensure 12 topics are ready in Redis cache."""
        # 1. Check Redis for existing unconsumed hourly batch
        redis_topics = self._load_hourly_from_redis()
        if redis_topics:
            self._batch = redis_topics
            self._batch_pos = 0
            log.info("Loaded %d remaining hourly topics from Redis cache", len(self._batch))
            return

        # 2. If Redis has no topics, ask OpenRouter for 12 topics for the upcoming hour
        used = self._load_used()
        log.info("Requesting external LLM (OpenRouter) to generate 12 topics for the upcoming hour...")
        try:
            new_topics = generate_topic_batch(self.client, count=settings.topics_per_hour, used=used)
            if new_topics:
                self._batch = new_topics
                self._batch_pos = 0
                self._save_hourly_to_redis(self._batch)
                log.info("Generated %d hourly topics from LLM and cached to Redis", len(new_topics))
                return
        except Exception as e:
            log.warning("Failed generating hourly topics from LLM, falling back to curated pool: %s", e)

        # 3. Fallback pool
        self._batch = [t for t in self._pool if t not in used][:12] or self._pool[:12]
        self._batch_pos = 0
        self._save_hourly_to_redis(self._batch)

    def next(self) -> Optional[str]:
        used = self._load_used()
        if self._batch_pos >= len(self._batch):
            self.ensure_hourly_batch()

        if self._batch_pos < len(self._batch):
            topic = self._batch[self._batch_pos]
            self._batch_pos += 1
            remaining = self._batch[self._batch_pos:]
            self._save_hourly_to_redis(remaining)
            self._remember(topic)
            return topic

        attempts = 0
        while self._pool and attempts < len(self._pool) * 2:
            if self._pool_pos >= len(self._pool):
                self._pool_pos = 0
            topic = self._pool[self._pool_pos]
            self._pool_pos += 1
            attempts += 1
            if topic not in used or attempts >= len(self._pool):
                self._remember(topic)
                return topic
        return "Is it better to be optimistic or skeptical in life?"
