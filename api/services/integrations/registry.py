"""Provider registry for LMS integrations."""

from __future__ import annotations

from api.services.integrations.base import LmsProvider
from api.services.integrations.canvas_provider import CanvasProvider


def get_provider(provider_name: str) -> LmsProvider:
    name = provider_name.strip().lower()
    if name == "canvas":
        return CanvasProvider()
    raise ValueError(f"Unsupported provider: {provider_name}")


def list_supported_providers() -> list[str]:
    return ["canvas", "blackboard", "upp"]
