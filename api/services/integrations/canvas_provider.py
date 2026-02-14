"""Canvas provider implementation for the LMS integration hub."""

from __future__ import annotations

import mimetypes
import os
from typing import Any

import httpx

from api.services.integrations.base import ExternalCourse, ExternalMaterial, LmsProvider


class CanvasProvider(LmsProvider):
    provider_name = "canvas"

    def __init__(self, api_url: str | None = None, api_token: str | None = None) -> None:
        self.api_url = (api_url if api_url is not None else os.getenv("CANVAS_API_URL", "")).strip().rstrip("/")
        self.api_token = (api_token if api_token is not None else os.getenv("CANVAS_API_TOKEN", "")).strip()
        self.timeout = float(os.getenv("CANVAS_API_TIMEOUT", "30"))

    def is_configured(self) -> bool:
        return bool(self.api_url and self.api_token)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def _request(self, method: str, path: str, params: dict[str, Any] | None = None) -> tuple[Any, httpx.Headers]:
        if not self.is_configured():
            raise RuntimeError("Canvas provider is not configured. Set CANVAS_API_URL and CANVAS_API_TOKEN.")

        url = f"{self.api_url}{path}"
        with httpx.Client(timeout=self.timeout, headers=self._headers(), follow_redirects=True) as client:
            response = client.request(method, url, params=params)
            response.raise_for_status()
            return response.json(), response.headers

    def _get_paginated(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        page_params = dict(params or {})
        page_params.setdefault("per_page", 100)

        items: list[dict[str, Any]] = []
        next_url: str | None = f"{self.api_url}{path}"

        with httpx.Client(timeout=self.timeout, headers=self._headers(), follow_redirects=True) as client:
            while next_url:
                response = client.get(next_url, params=page_params if next_url.endswith(path) else None)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    items.extend(payload)
                elif isinstance(payload, dict):
                    items.append(payload)

                next_url = None
                links = response.links
                if "next" in links and links["next"].get("url"):
                    next_url = links["next"]["url"]

        return items

    def list_courses(self) -> list[ExternalCourse]:
        raw_courses = self._get_paginated("/courses", params={"enrollment_state": "active"})
        courses: list[ExternalCourse] = []
        for c in raw_courses:
            course_id = c.get("id")
            if course_id is None:
                continue
            courses.append(
                ExternalCourse(
                    provider=self.provider_name,
                    external_id=str(course_id),
                    title=c.get("name") or c.get("course_code") or f"Canvas Course {course_id}",
                    code=c.get("course_code"),
                    term=(c.get("term") or {}).get("name") if isinstance(c.get("term"), dict) else None,
                )
            )
        return courses

    def list_materials(self, course_external_id: str) -> list[ExternalMaterial]:
        raw_files = self._get_paginated(f"/courses/{course_external_id}/files")
        materials: list[ExternalMaterial] = []
        for f in raw_files:
            file_id = f.get("id")
            if file_id is None:
                continue
            filename = f.get("filename") or f.get("display_name") or f"file-{file_id}"
            mime = f.get("content-type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
            materials.append(
                ExternalMaterial(
                    provider=self.provider_name,
                    external_id=str(file_id),
                    course_external_id=str(course_external_id),
                    title=f.get("display_name") or filename,
                    filename=filename,
                    content_type=mime,
                    size_bytes=int(f.get("size") or 0),
                    updated_at=f.get("updated_at"),
                    source_url=f.get("url"),
                )
            )
        return materials

    def _get_file_metadata(self, material_external_id: str) -> ExternalMaterial:
        payload, _ = self._request("get", f"/files/{material_external_id}")
        filename = payload.get("filename") or payload.get("display_name") or f"file-{material_external_id}"
        mime = payload.get("content-type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return ExternalMaterial(
            provider=self.provider_name,
            external_id=str(payload.get("id") or material_external_id),
            course_external_id=str(payload.get("context_id") or ""),
            title=payload.get("display_name") or filename,
            filename=filename,
            content_type=mime,
            size_bytes=int(payload.get("size") or 0),
            updated_at=payload.get("updated_at"),
            source_url=payload.get("url"),
        )

    def download_material(self, material_external_id: str) -> tuple[bytes, ExternalMaterial]:
        material = self._get_file_metadata(material_external_id)
        if not material.source_url:
            raise RuntimeError(f"Canvas file {material_external_id} has no downloadable URL.")

        with httpx.Client(timeout=self.timeout, headers=self._headers(), follow_redirects=True) as client:
            response = client.get(material.source_url)
            response.raise_for_status()
            return response.content, material
