"""Blackboard provider scaffold for the LMS integration hub."""

from __future__ import annotations

import os

from api.services.integrations.base import ExternalCourse, ExternalMaterial, LmsProvider


class BlackboardProvider(LmsProvider):
    provider_name = "blackboard"

    def __init__(self, api_url: str | None = None, api_token: str | None = None) -> None:
        self.api_url = (api_url if api_url is not None else os.getenv("BLACKBOARD_API_URL", "")).strip().rstrip("/")
        self.api_token = (api_token if api_token is not None else os.getenv("BLACKBOARD_API_TOKEN", "")).strip()

    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_token)

    def list_courses(self) -> list[ExternalCourse]:
        raise RuntimeError("Blackboard connector is not implemented yet.")

    def list_materials(self, course_external_id: str) -> list[ExternalMaterial]:
        raise RuntimeError("Blackboard connector is not implemented yet.")

    def download_material(self, material_external_id: str) -> tuple[bytes, ExternalMaterial]:
        raise RuntimeError("Blackboard connector is not implemented yet.")
