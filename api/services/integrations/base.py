"""Common provider contracts for LMS integrations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ExternalCourse:
    provider: str
    external_id: str
    title: str
    code: str | None = None
    term: str | None = None


@dataclass
class ExternalMaterial:
    provider: str
    external_id: str
    course_external_id: str
    title: str
    filename: str
    content_type: str
    size_bytes: int
    updated_at: str | None = None
    source_url: str | None = None


@dataclass
class ExternalEnrollment:
    provider: str
    external_user_id: str
    role: str
    name: str | None = None
    email: str | None = None


class LmsProvider(Protocol):
    """Provider contract for LMS platforms (Canvas, Blackboard, etc.)."""

    provider_name: str

    def is_configured(self) -> bool:
        """Return whether provider credentials/config are available."""

    def list_courses(self) -> list[ExternalCourse]:
        """List courses visible to the configured account."""

    def list_materials(self, course_external_id: str) -> list[ExternalMaterial]:
        """List importable materials for an external course."""

    def download_material(self, material_external_id: str) -> tuple[bytes, ExternalMaterial]:
        """Download one material and return payload plus normalized metadata."""

    def list_enrollments(self, course_external_id: str) -> list[ExternalEnrollment]:
        """List enrollments for an external course."""
