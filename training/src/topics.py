"""Topic validation and safe topic-pool handling.

Shared concepts used by the offline generator and the production server.
"""

from __future__ import annotations

import json
import re
import os
from typing import List, Optional

MAX_TOPIC_CHARS = 140
MIN_TOPIC_CHARS = 8

CURRENT_EVENT_HINTS = re.compile(
    r"\b(202[0-9]|20[0-9]{2}|election|president|government|senate|congress|covid|"
    r"war in|invasion|stock market|inflation|GDP|bill|law passed|news report|"
    r"tweet|twitter|instagram|tiktok|musk|trump|biden|zelensky|putin|netanyahu|"
    r"china|russia|ukraine|israel|gaza|iran)\b",
    re.IGNORECASE,
)
FACTUAL_HINTS = re.compile(
    r"\b(when did|what is the capital|who invented|what year|how many people|"
    r"what is the tallest|first president|largest country|speed of light|"
    r"population of|founding date|invented in|discovered by)\b",
    re.IGNORECASE,
)
UNSAFE_HINTS = re.compile(
    r"\b(kill|suicide|self-harm|bomb|weapon|poison|illegal|hack|weaponize|"
    r"attack instructions|violent)\b",
    re.IGNORECASE,
)
INJECTION_HINTS = re.compile(
    r"\b(ignore (all )?(previous|prior) (instructions|prompts)|system prompt|"
    r"you are now|disregard|jailbreak|api key|secret key|environment variable|"
    r"sudo |shell command|sql injection)\b",
    re.IGNORECASE,
)
TRIVIA_HINTS = re.compile(
    r"\b(what is the capital of|who won|who scored|highest score ever|"
    r"current champion|latest version|release date)\b",
    re.IGNORECASE,
)

TOPIC_PROMPT = """You generate debate topics for two AI personalities with opposing worldviews (one optimistic, one pessimistic) to argue about.

Requirements for each topic:
- a conversational question that invites argument
- both sides must be defensible (not a factual question with one right answer)
- no current events, no breaking news, no politics, no news-dependent facts
- no obscure factual trivia, nothing requiring external databases or web lookup
- no unsafe, illegal, violent, hateful or sexual content
- concise (one sentence, under 140 characters), varied, creative, genuinely debatable
- about everyday life, values, habits, relationships, work, imagination, hypotheticals, preferences, philosophy, absurd-but-harmless scenarios

Return exactly the requested number of topics as a JSON object with the key "topics" (a list of strings)."""

TOPIC_SCHEMA = {"type": "object", "properties": {"topics": {"type": "array", "items": {"type": "string"}}}}


def validate_topic(text: str) -> Optional[str]:
    """Return a reason string if the topic is rejected, else None."""
    text = text.strip()
    if not text:
        return "empty"
    if len(text) < MIN_TOPIC_CHARS:
        return "too_short"
    if len(text) > MAX_TOPIC_CHARS:
        return "too_long"
    if CURRENT_EVENT_HINTS.search(text):
        return "current_events"
    if FACTUAL_HINTS.search(text) or TRIVIA_HINTS.search(text):
        return "factual_or_trivia"
    if UNSAFE_HINTS.search(text):
        return "unsafe"
    if INJECTION_HINTS.search(text):
        return "injection"
    if len(set(text.split())) < 4:
        return "too_simple"
    return None


def dedupe_topics(topics: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in topics:
        key = re.sub(r"[^a-z0-9 ]", "", t.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(t)
    return out


def validate_topic_batch(topics: List[str]) -> List[str]:
    valid = []
    for t in topics:
        if validate_topic(t) is None:
            valid.append(t)
    return valid


FALLBACK_POOL_PATH = "server/app/topics/fallback_pool.json"


def load_fallback_pool(path: str = FALLBACK_POOL_PATH) -> List[str]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [t for t in json.load(f) if validate_topic(t) is None]