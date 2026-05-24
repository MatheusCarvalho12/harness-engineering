"""LLM access with force-provider support for comparison mode.

Primary provider is Ollama; OpenAI is the fallback or can be forced via
the `force_provider` parameter for side-by-side comparison.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from config import settings
from logging_config import get_logger, log_error

logger = get_logger("llm")

_COMPLETION_MODEL: str = "gpt-5-nano"


@dataclass
class Completion:
    text: str
    tokens_consumed: int
    provider: str


def _approximate_tokens(*texts: str) -> int:
    total_chars = sum(len(text) for text in texts)
    return max(1, total_chars // 4)


def _extract_tokens(response, system_prompt: str, user_prompt: str) -> int:
    usage = getattr(response, "usage_metadata", None)
    if usage:
        return usage.get("total_tokens") or _approximate_tokens(
            system_prompt, user_prompt, response.content
        )
    return _approximate_tokens(system_prompt, user_prompt, response.content)


def _build_ollama() -> ChatOllama:
    return ChatOllama(
        model=settings.model_name,
        base_url=settings.ollama_base_url,
        temperature=settings.llm_temperature,
        client_kwargs={"timeout": settings.llm_timeout_seconds},
    )


def _build_openai(model_name: str | None = None) -> ChatOpenAI | None:
    if not settings.openai_api_key:
        return None
    return ChatOpenAI(
        model=model_name or settings.openai_model_name or _COMPLETION_MODEL,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_completion_tokens=4096,
    )


async def complete(
    system_prompt: str,
    user_prompt: str,
    force_provider: str | None = None,
) -> Completion:
    """Call an LLM.

    Args:
        system_prompt: System prompt for the model.
        user_prompt: User message.
        force_provider: ``"ollama"`` to force local only,
            ``"openai"`` to force OpenAI only,
            ``None`` / ``"auto"`` for try-Ollama-then-fallback.
    """
    messages = [SystemMessage(system_prompt), HumanMessage(user_prompt)]

    if force_provider == "openai":
        client = _build_openai()
        if client is None:
            raise RuntimeError("OPENAI_API_KEY not configured for forced OpenAI mode")
        response = await client.ainvoke(messages)
        return Completion(
            text=response.content,
            tokens_consumed=_extract_tokens(response, system_prompt, user_prompt),
            provider="openai",
        )

    # Default path: try Ollama first
    try:
        response = await _build_ollama().ainvoke(messages)
        return Completion(
            text=response.content,
            tokens_consumed=_extract_tokens(response, system_prompt, user_prompt),
            provider="ollama",
        )
    except Exception as ollama_error:
        if force_provider == "ollama":
            raise  # No fallback when forced
        log_error(logger, "ollama_unavailable_falling_back", exc=ollama_error)
        openai_client = _build_openai()
        if openai_client is None:
            raise RuntimeError(
                "Ollama unreachable and no OPENAI_API_KEY configured for fallback"
            ) from ollama_error
        response = await openai_client.ainvoke(messages)
        return Completion(
            text=response.content,
            tokens_consumed=_extract_tokens(response, system_prompt, user_prompt),
            provider="openai",
        )
