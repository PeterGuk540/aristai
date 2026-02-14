"""Provider registry for LMS integrations."""

from __future__ import annotations

from api.services.integrations.base import LmsProvider
from api.services.integrations.blackboard_provider import BlackboardProvider
from api.services.integrations.canvas_provider import CanvasProvider
from api.services.integrations.upp_provider import UppProvider


def get_provider(provider_name: str, config: dict | None = None) -> LmsProvider:
    name = provider_name.strip().lower()
    cfg = config or {}
    if name == "canvas":
        return CanvasProvider(
            api_url=cfg.get("api_base_url"),
            api_token=cfg.get("api_token"),
        )
    if name == "blackboard":
        return BlackboardProvider(
            api_url=cfg.get("api_base_url"),
            api_token=cfg.get("api_token"),
        )
    if name == "upp":
        return UppProvider(
            api_url=cfg.get("api_base_url"),
            api_token=cfg.get("api_token"),
        )
    raise ValueError(f"Unsupported provider: {provider_name}")


def list_supported_providers() -> list[str]:
    return ["canvas", "blackboard", "upp"]
