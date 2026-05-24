"""Single source of truth for runtime configuration.

Every tunable value (broker URLs, model selection, timeouts, retry policy)
is read from the environment here and nowhere else. Business logic imports
from this module instead of touching os.environ directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


@dataclass(frozen=True)
class Settings:
    redis_url: str = _env_str("REDIS_URL", "redis://localhost:6379/0")

    ollama_base_url: str = _env_str("OLLAMA_BASE_URL", "http://localhost:11434")
    openai_api_key: str = _env_str("OPENAI_API_KEY", "")
    openai_base_url: str = _env_str("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model_name: str = _env_str("MODEL_NAME", "llama3.2:3b")
    openai_model_name: str = _env_str("OPENAI_MODEL_NAME", "gpt-4o-mini")

    llm_timeout_seconds: float = _env_float("LLM_TIMEOUT_SECONDS", 120.0)
    llm_temperature: float = _env_float("LLM_TEMPERATURE", 0.2)

    retry_max_attempts: int = _env_int("RETRY_MAX_ATTEMPTS", 3)
    retry_base_delay_seconds: float = _env_float("RETRY_BASE_DELAY_SECONDS", 1.0)
    retry_backoff_multiplier: float = _env_float("RETRY_BACKOFF_MULTIPLIER", 2.0)

    result_wait_timeout_seconds: int = _env_int("RESULT_WAIT_TIMEOUT_SECONDS", 180)
    max_revision_rounds: int = _env_int("MAX_REVISION_ROUNDS", 1)

    api_host: str = _env_str("API_HOST", "0.0.0.0")
    api_port: int = _env_int("API_PORT", 8000)


settings = Settings()

PLANNER = "planner"
EXECUTOR = "executor"
CRITIC = "critic"
AGGREGATOR = "aggregator"

AGENT_ROLES = (PLANNER, EXECUTOR, CRITIC, AGGREGATOR)


def queue_name(stage: str) -> str:
    return f"harness:queue:{stage}"


def reply_channel(reply_token: str) -> str:
    return f"harness:reply:{reply_token}"


DEAD_LETTER_QUEUE = "harness:dlq"
