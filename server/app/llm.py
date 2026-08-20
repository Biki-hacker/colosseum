"""Minimal OpenAI-compatible chat client for the server, with a deterministic
mock mode used when no API key is configured (and in tests)."""

from __future__ import annotations

import json
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from .config import settings

MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0

JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)

_MOCK_TOPICS = [
    "Should people always pursue their passion?",
    "Is technology making us less social?",
    "Would life be better if everyone could read minds?",
    "Is failure a necessary part of success?",
    "Should we fear artificial intelligence?",
    "Is remote work better than working in an office?",
]


class LLMError(Exception):
    pass


def _extract_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = JSON_FENCE.search(text)
    if m:
        return json.loads(m.group(1))
    raise LLMError(f"no JSON in response: {text[:200]!r}")


class LLMClient:
    def __init__(self, base_url: str = "", api_key: str = "", model: str = "", timeout: int = 60, mock: bool = False):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.llm_model
        self.timeout = timeout
        self.mock = mock or not (self.base_url and self.api_key)

    def chat(
        self,
        system: str,
        user: str,
        json_schema: Optional[dict] = None,
        temperature: float = 0.9,
    ) -> Any:
        if self.mock:
            return self._mock(system, user, json_schema)
        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                payload = {
                    "model": self.model,
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                    "temperature": temperature,
                }
                if json_schema:
                    payload["response_format"] = {"type": "json_object"}
                with httpx.Client(timeout=self.timeout) as client:
                    r = client.post(f"{self.base_url}/chat/completions", headers={"Authorization": f"Bearer {self.api_key}"}, json=payload)
                    r.raise_for_status()
                    content = r.json()["choices"][0]["message"]["content"]
                if json_schema:
                    return _extract_json(content)
                return content
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(BACKOFF_BASE_S ** attempt)
        raise LLMError(f"LLM request failed after {MAX_RETRIES} retries: {last_err}")

    # ------------------------------------------------------------------ mock

    def _mock(self, system: str, user: str, json_schema: Optional[dict]) -> Any:
        rng = random.Random(hash((system, user)) & 0xFFFFFFFF)
        if json_schema:
            props = json_schema.get("properties", {})
            return {k: self._mock_value(rng, v, k) for k, v in props.items()}
        if "topic" in system.lower() or "generate" in user.lower() and "topic" in user.lower():
            return rng.choice(_MOCK_TOPICS)
        return self._mock_text(rng, user)

    def _mock_value(self, rng: random.Random, spec: dict, field: str) -> Any:
        if spec.get("type") == "array":
            items = spec.get("items", {})
            if field == "topics":
                return [rng.choice(_MOCK_TOPICS) for _ in range(rng.randint(3, 6))]
            return [self._mock_value(rng, items, field) for _ in range(rng.randint(1, 4))]
        if spec.get("type") == "integer":
            return rng.randint(1, 100)
        if spec.get("type") == "number":
            return round(rng.uniform(0, 10), 1)
        return self._mock_text(rng, field)

    def _mock_text(self, rng: random.Random, user: str) -> str:
        if "winner" in user or "judge" in user.lower():
            return rng.choice(["optimist", "pessimist", "tie"])
        words = ["the", "most", "people", "world", "way", "good", "think", "really", "better", "time", "one", "day", "life"]
        return " ".join(rng.choice(words) for _ in range(rng.randint(25, 45)))


def make_llm(mock: bool = False) -> LLMClient:
    return LLMClient(mock=mock or settings.llm_mock)


def make_judge_llm(mock: bool = False) -> LLMClient:
    return LLMClient(model=settings.judge_model or settings.llm_model, mock=mock or settings.llm_mock)