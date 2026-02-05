"""Speech output filter to enforce brand compliance."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from api.core.config import get_settings


DEFAULT_FALLBACK = "I can help with that inside this app. What would you like to do next?"


def _split_terms(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _compile_terms(terms: Iterable[str]) -> List[re.Pattern]:
    patterns = []
    for term in terms:
        escaped = re.escape(term)
        patterns.append(re.compile(rf"\b{escaped}\b", re.IGNORECASE))
    return patterns


def _contains_banned(text: str, patterns: Iterable[re.Pattern], allowlist: Iterable[str]) -> bool:
    if not text:
        return False
    for term in allowlist:
        if term and term.lower() in text.lower():
            return False
    return any(pattern.search(text) for pattern in patterns)


def sanitize_speech(text: str) -> str:
    settings = get_settings()
    denylist = _split_terms(settings.voice_brand_denylist)
    allowlist = _split_terms(settings.voice_brand_allowlist)
    return sanitize_speech_text(text, denylist, allowlist)


def sanitize_speech_text(
    text: str,
    denylist: Iterable[str],
    allowlist: Optional[Iterable[str]] = None,
) -> str:
    if not text:
        return text
    allowlist = allowlist or []
    patterns = _compile_terms(denylist)
    sanitized = text

    for term in denylist:
        if not term:
            continue
        term_pattern = re.compile(re.escape(term), re.IGNORECASE)
        sanitized = term_pattern.sub("voice service", sanitized)

    sanitized = re.sub(
        r"\b(open|go to|visit|navigate to)\s+(the\s+)?voice\s+service\s+(dashboard|console)\b",
        "open the settings page",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(open|go to|visit|navigate to)\s+(the\s+)?voice\s+service\s+(website|docs|documentation)\b",
        "open the documentation",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(open|go to|visit|navigate to)\s+(the\s+)?voice\s+service\b",
        "open the settings page",
        sanitized,
        flags=re.IGNORECASE,
    )
    sanitized = re.sub(
        r"\b(open|go to|visit|navigate to)\s+(the\s+)?[^.]*\b(website|docs|documentation)\b",
        "open the documentation",
        sanitized,
        flags=re.IGNORECASE,
    )

    if _contains_banned(sanitized, patterns, allowlist):
        return DEFAULT_FALLBACK
    return sanitized
