"""OpenAI-compatible LLM client for offline synthetic-data generation.

Real mode: talks to any OpenAI-compatible endpoint (OpenAI, OpenRouter, Groq, LocalAI...)
configured via env vars. Mock mode: deterministic, seedable, schema-shaped output so the
whole pipeline is testable and runnable with zero API keys or cost.

The production server ships its own async client (server/app) — this module is for the
training/data pipeline only.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests

MAX_RETRIES = 3
BACKOFF_BASE_S = 2.0

JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _load_env() -> None:
    """Load .env from the project root (repo root or cwd)."""
    try:
        from dotenv import load_dotenv

        for candidate in (
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".env"),
            os.path.join(os.getcwd(), ".env"),
        ):
            if os.path.exists(candidate):
                load_dotenv(candidate, override=False)
                return
    except ImportError:
        pass


_load_env()


class LLMClient:
    def __init__(self):
        self.base_url = os.environ.get("LLM_BASE_URL", "").rstrip("/") or "https://api.openai.com/v1"
        self.api_key = os.environ.get("LLM_API_KEY", "").strip()
        self.model = os.environ.get("LLM_MODEL", "").strip() or "gpt-4o-mini"
        self.timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
        self.mock = not bool(self.api_key)
        self._mock_rng = random.Random(int(os.environ.get("LLM_MOCK_SEED", "1337")))

    # ---- mock machinery ----
    def _mock_reply(self, system: str, user: str, json_schema: Optional[dict] = None) -> str:
        h = hashlib.sha256((system + user).encode("utf-8")).hexdigest()
        seed = int(h[:8], 16)
        rng = random.Random(seed)
        self._mock_topic_mode = "topics" in (system + user).lower()
        if json_schema is None:
            return self._mock_text(rng, user)
        return json.loads(self._mock_json(rng, user, json_schema))

    _MOCK_TOPICS = [
        "Is it better to be spontaneous or highly organized?",
        "Would life be better if everyone could read minds?",
        "Should people always pursue their passion?",
        "Is competition more motivating than cooperation?",
        "Does technology bring people closer or push them apart?",
        "Would you rather travel the world alone or with friends?",
        "Is change something to embrace or to resist?",
        "Should we trust our first impressions of people?",
        "Is failure a teacher or a warning sign?",
        "Does money actually buy happiness?",
        "Is it better to have many friends or a few close ones?",
        "Can routine and structure coexist with creativity?",
        "Should everyone follow their dreams, or plan for reality?",
        "Is honesty always the best policy?",
        "Do we learn more from success or from failure?",
        "Is it better to be lucky or to be skilled?",
        "Should people share their feelings openly or keep them private?",
        "Is simplicity underrated?",
        "Are rules there to protect us or to limit us?",
        "Would you rather be remembered or forgettable?",
    ]
    _MOCK_CLAUSES = [
        "I think the real question here is what we actually value most.",
        "It honestly depends on the situation and the people involved.",
        "There is always a trade-off, and pretending otherwise does not help.",
        "Small consistent steps tend to add up to big changes over time.",
        "We should weigh both the upside and the downside carefully.",
        "What works for one person may not work for another at all.",
        "The evidence from everyday life seems to support a balanced view.",
        "I have seen both sides of this and neither is as simple as it looks.",
        "It comes down to whether we want comfort now or growth later.",
        "People often forget that context changes almost everything here.",
        "A little humility about our own certainty would serve us well.",
        "The best answer usually lies somewhere in the middle, honestly.",
        "You could look at it as a risk, or as an opportunity in disguise.",
        "It is easy to be idealistic until reality gets in the way.",
        "Once you start noticing the small details, the picture changes.",
        "I would say intention matters just as much as the outcome does.",
    ]

    def _mock_text(self, rng: random.Random, user: str) -> str:
        if self._mock_topic_mode:
            return rng.choice(self._MOCK_TOPICS)
        return " ".join(rng.sample(self._MOCK_CLAUSES, 4)) + " " + rng.choice(self._MOCK_TOPICS)

    def _mock_json(self, rng: random.Random, user: str, schema: dict) -> str:
        if schema.get("type") == "object":
            props = schema.get("properties", {})
            out: Dict[str, Any] = {}
            for name, pspec in props.items():
                field_rng = random.Random(rng.randrange(1 << 32) ^ hash(name))
                out[name] = self._mock_value(field_rng, pspec, name)
            return json.dumps(out)
        if schema.get("type") == "array":
            items = schema.get("items", {})
            return json.dumps([self._mock_json(rng, user, items) for _ in range(12)])
        return json.dumps(self._mock_value(rng, schema, ""))

    def _mock_value(self, rng: random.Random, spec: dict, field: str = ""):
        t = spec.get("type", "string")
        if t == "array":
            items = spec.get("items", {"type": "string"})
            n = spec.get("minItems", 12)
            return [self._mock_value(rng, items, field) for _ in range(n)]
        if t == "string":
            if self._mock_topic_mode:
                return rng.choice(self._MOCK_TOPICS)
            return " ".join(rng.sample(self._MOCK_CLAUSES, 4)) + " " + rng.choice(self._MOCK_TOPICS) + f" ({field})"
        if t == "number":
            return round(rng.uniform(spec.get("minimum", 0), spec.get("maximum", 10)), 1)
        if t == "boolean":
            return rng.random() < 0.5
        return None

    # ---- real API ----
    def chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.8,
        max_tokens: int = 1024,
        json_schema: Optional[dict] = None,
    ) -> Any:
        if self.mock:
            return self._mock_reply(system, user, json_schema)
        messages = [{"role": "system", "content": system}]
        if user:
            messages.append({"role": "user", "content": user})
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        url = self.base_url + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                text = resp.json()["choices"][0]["message"]["content"]
                if json_schema is not None:
                    return self._parse_json(text)
                return text
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(BACKOFF_BASE_S * (2**attempt))
        raise RuntimeError(f"LLM call failed after {MAX_RETRIES} attempts: {last_err}")

    def _parse_json(self, text: str) -> Any:
        text = text.strip()
        if text.startswith("```"):
            m = JSON_FENCE.search(text)
            if m:
                text = m.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # try to extract the first {...} or [...] block
            start = text.find("{")
            if start == -1:
                start = text.find("[")
            end = text.rfind("}")
            if end == -1:
                end = text.rfind("]")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not parse JSON from LLM output: {text[:200]!r}")