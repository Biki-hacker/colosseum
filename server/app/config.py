"""Environment configuration for the Colosseum server."""

from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

env_file = os.environ.get("ENV_FILE")
if env_file:
    load_dotenv(env_file, override=True)
else:
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"))
    load_dotenv(os.path.join(os.getcwd(), ".env"))


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def _list(name: str, default: str) -> List[str]:
    return [s.strip() for s in os.environ.get(name, default).split(",") if s.strip()]


class Settings:
    @property
    def llm_base_url(self) -> str:
        return os.environ.get("LLM_BASE_URL", "")

    @property
    def llm_api_key(self) -> str:
        return os.environ.get("LLM_API_KEY", "")

    @property
    def llm_model(self) -> str:
        return os.environ.get("LLM_MODEL", "")

    @property
    def judge_model(self) -> str:
        return os.environ.get("JUDGE_MODEL", "") or self.llm_model

    @property
    def llm_timeout(self) -> int:
        return _int("LLM_TIMEOUT_SECONDS", 150)

    @property
    def supabase_url(self) -> str:
        return os.environ.get("SUPABASE_URL", "")

    @property
    def supabase_key(self) -> str:
        return os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")

    @property
    def upstash_redis_url(self) -> str:
        return os.environ.get("UPSTASH_REDIS_URL", "")

    @property
    def upstash_redis_token(self) -> str:
        return os.environ.get("UPSTASH_REDIS_TOKEN", "")

    @property
    def data_dir(self) -> str:
        return os.environ.get("DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")))

    @property
    def storage_mode(self) -> str:
        explicit = os.environ.get("STORAGE_MODE")
        if explicit:
            return explicit
        return "supabase" if (self.supabase_url and self.supabase_key) else "local"

    @property
    def port(self) -> int:
        return _int("PORT", 8011)

    @property
    def host(self) -> str:
        return os.environ.get("HOST", "0.0.0.0")

    @property
    def allowed_origins(self) -> List[str]:
        return _list("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")

    @property
    def fallback_pool_file(self) -> str:
        return os.environ.get(
            "FALLBACK_TOPIC_POOL_FILE",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics", "fallback_pool.json"),
        )

    @property
    def debate_interval_seconds(self) -> int:
        return _int("DEBATE_INTERVAL_SECONDS", 300)

    @property
    def debate_turns(self) -> int:
        return _int("DEBATE_TURNS", 20)

    @property
    def max_new_tokens(self) -> int:
        return _int("MAX_NEW_TOKENS", 75)

    @property
    def topics_per_hour(self) -> int:
        return _int("TOPICS_PER_HOUR", 12)

    @property
    def turn_delay_seconds(self) -> float:
        return _float("TURN_DELAY_SECONDS", 6.5)

    @property
    def retention_hours(self) -> int:
        return _int("RETENTION_HOURS", 48)

    @property
    def generation_temperature(self) -> float:
        return _float("GENERATION_TEMPERATURE", 0.65)

    @property
    def generation_top_k(self) -> int:
        return _int("GENERATION_TOP_K", 25)

    @property
    def generation_top_p(self) -> float:
        return _float("GENERATION_TOP_P", 0.90)

    @property
    def generation_repetition_penalty(self) -> float:
        return _float("GENERATION_REPETITION_PENALTY", 1.20)

    @property
    def llm_mock(self) -> bool:
        return not (self.llm_base_url and self.llm_api_key)

    @property
    def models_root(self) -> str:
        return os.environ.get("MODELS_ROOT", os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models")))


settings = Settings()