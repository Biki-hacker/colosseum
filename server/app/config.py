"""Environment configuration for the Colosseum server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

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


@dataclass
class Settings:
    # LLM
    llm_base_url: str = os.environ.get("LLM_BASE_URL", "")
    llm_api_key: str = os.environ.get("LLM_API_KEY", "")
    llm_model: str = os.environ.get("LLM_MODEL", "")
    judge_model: str = os.environ.get("JUDGE_MODEL", "") or os.environ.get("LLM_MODEL", "")
    llm_timeout: int = _int("LLM_TIMEOUT_SECONDS", 60)

    # storage / infra
    supabase_url: str = os.environ.get("SUPABASE_URL", "")
    supabase_key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    upstash_redis_url: str = os.environ.get("UPSTASH_REDIS_URL", "")
    upstash_redis_token: str = os.environ.get("UPSTASH_REDIS_TOKEN", "")
    storage_mode: str = os.environ.get("STORAGE_MODE", "supabase")
    data_dir: str = os.environ.get("DATA_DIR", "./data")

    # server
    port: int = _int("PORT", 8000)
    host: str = os.environ.get("HOST", "0.0.0.0")
    allowed_origins: List[str] = field(default_factory=lambda: _list("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"))
    fallback_pool_file: str = field(default_factory=lambda: os.environ.get(
        "FALLBACK_TOPIC_POOL_FILE",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics", "fallback_pool.json"),
    ))

    # debate / scheduling
    debate_interval_seconds: int = _int("DEBATE_INTERVAL_SECONDS", 300)
    debate_turns: int = _int("DEBATE_TURNS", 20)
    max_new_tokens: int = _int("MAX_NEW_TOKENS", 50)
    topics_per_hour: int = _int("TOPICS_PER_HOUR", 12)
    turn_delay_seconds: float = _float("TURN_DELAY_SECONDS", 6.5)
    retention_hours: int = _int("RETENTION_HOURS", 48)


    # inference
    generation_temperature: float = _float("GENERATION_TEMPERATURE", 0.55)
    generation_top_k: int = _int("GENERATION_TOP_K", 15)
    generation_top_p: float = _float("GENERATION_TOP_P", 0.85)
    generation_repetition_penalty: float = _float("GENERATION_REPETITION_PENALTY", 1.20)


    @property
    def llm_mock(self) -> bool:
        return not (self.llm_base_url and self.llm_api_key)

    @property
    def models_root(self) -> str:
        return os.environ.get("MODELS_ROOT", os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "models")))


settings = Settings()