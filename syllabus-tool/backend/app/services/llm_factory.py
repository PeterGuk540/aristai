from __future__ import annotations

import time
from typing import Any, Sequence

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage

from app.core.config import settings

def get_llm():
    """
    Returns a configured LLM instance.
    """
    if settings.ANTHROPIC_API_KEY:
        return ChatAnthropic(
            model=settings.ANTHROPIC_MODEL,
            api_key=settings.ANTHROPIC_API_KEY,
            temperature=settings.LLM_TEMPERATURE,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    
    # Fallback to DeepSeek/OpenAI
    if not settings.DEEPSEEK_API_KEY:
        raise ValueError(
            "No LLM API key configured. Set ANTHROPIC_API_KEY or DEEPSEEK_API_KEY. "
            "For systemd deployments, set them in /etc/syllabus_tool/backend.env"
        )
    return ChatOpenAI(
        model=settings.DEEPSEEK_MODEL,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=settings.LLM_TEMPERATURE,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def invoke_llm(messages: Sequence[BaseMessage], *, max_retries: int | None = None) -> Any:
    """Invoke the configured LLM with basic retry/backoff.

    Keeps dependencies minimal (no tenacity). Retries transient provider/network errors.
    """
    llm = get_llm()
    attempts = max(0, int(max_retries if max_retries is not None else settings.LLM_MAX_RETRIES)) + 1
    last_exc: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return llm.invoke(list(messages))
        except Exception as e:  # provider-specific exception types vary
            last_exc = e
            if attempt >= attempts:
                raise
            # Exponential backoff with cap
            sleep_s = min(2 ** (attempt - 1), 8)
            time.sleep(sleep_s)

    if last_exc:
        raise last_exc
    raise RuntimeError("LLM invocation failed")
