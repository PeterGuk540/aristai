"""UPP provider implementation for the LMS integration hub.

This connector is endpoint-configurable so different UPP deployments can map
their API shapes without code changes.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from typing import Any

import httpx

from api.services.integrations.base import ExternalCourse, ExternalEnrollment, ExternalMaterial, LmsProvider


class UppProvider(LmsProvider):
    provider_name = "upp"

    def __init__(self, api_url: str | None = None, api_token: str | None = None) -> None:
        self.api_url = (api_url if api_url is not None else os.getenv("UPP_API_URL", "")).strip().rstrip("/")
        raw_token = (api_token if api_token is not None else os.getenv("UPP_API_TOKEN", "")).strip()
        self.api_token = raw_token
        self.username: str | None = None
        self.password: str | None = None
        if raw_token.startswith("UPP_CRED_B64:"):
            try:
                payload = raw_token.split(":", 1)[1]
                decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
                token_json = json.loads(decoded)
                self.username = str(token_json.get("username", "")).strip() or None
                self.password = str(token_json.get("password", "")).strip() or None
                self.api_token = ""
            except Exception:  # noqa: BLE001
                self.username = None
                self.password = None
        self.timeout = float(os.getenv("UPP_API_TIMEOUT", "30"))
        self.auth_header = os.getenv("UPP_AUTH_HEADER", "Authorization").strip() or "Authorization"
        self.auth_scheme = os.getenv("UPP_AUTH_SCHEME", "Bearer").strip()
        self.login_path = os.getenv("UPP_LOGIN_PATH", "/login/index.php").strip() or "/login/index.php"
        self.my_courses_path = os.getenv("UPP_MY_COURSES_PATH", "/my/courses.php").strip() or "/my/courses.php"

        self.courses_path = os.getenv("UPP_COURSES_PATH", "/courses").strip() or "/courses"
        self.materials_path_tpl = os.getenv("UPP_MATERIALS_PATH", "/courses/{course_id}/materials").strip()
        self.enrollments_path_tpl = os.getenv("UPP_ENROLLMENTS_PATH", "/courses/{course_id}/enrollments").strip()
        self.download_path_tpl = os.getenv("UPP_DOWNLOAD_PATH", "/materials/{material_id}/download").strip()

    def is_configured(self) -> bool:
        # Token may be optional for some deployments if SSO/session auth is used.
        return bool(self.api_url)

    def _credentials_configured(self) -> bool:
        return bool(self.username and self.password)

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.api_token:
            token_value = self.api_token
            if self.auth_scheme:
                token_value = f"{self.auth_scheme} {self.api_token}"
            headers[self.auth_header] = token_value
        return headers

    def _extract_hidden_inputs(self, html: str) -> dict[str, str]:
        hidden: dict[str, str] = {}
        for name, value in re.findall(
            r'<input[^>]+type=["\']hidden["\'][^>]+name=["\']([^"\']+)["\'][^>]+value=["\']([^"\']*)["\']',
            html,
            flags=re.IGNORECASE,
        ):
            hidden[name] = value
        return hidden

    @staticmethod
    def _contains_any(text: str, needles: list[str]) -> bool:
        low = text.lower()
        return any(n in low for n in needles)

    def _diagnose_login_failure(self, html: str, status_code: int | None = None) -> str:
        if status_code in (401, 403):
            return "UPP login failed: credentials rejected (401/403). Check username/password."
        if self._contains_any(html, ["invalid login", "incorrect", "authentication failed", "credenciales", "usuario o contraseña"]):
            return "UPP login failed: invalid username or password."
        if self._contains_any(html, ["captcha", "recaptcha"]):
            return "UPP login failed: CAPTCHA/interactive challenge is required and cannot be completed by backend sync."
        if self._contains_any(html, ["microsoft", "saml", "single sign-on", "sso"]):
            return "UPP login failed: SSO login flow detected. Use token/OAuth integration for this tenant."
        if "login" in (html or "").lower():
            return "UPP login failed: still on login page after submit. Check credentials or login path."
        return "UPP login failed: unexpected login response. Verify UPP login path and credential validity."

    def _login_cookies(self) -> dict[str, str]:
        if not self._credentials_configured():
            return {}
        login_url = f"{self.api_url}{self.login_path}"
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            page = client.get(login_url)
            page.raise_for_status()
            payload = self._extract_hidden_inputs(page.text)
            payload["username"] = self.username or ""
            payload["password"] = self.password or ""
            post = client.post(login_url, data=payload)
            post.raise_for_status()
            post_text = post.text or ""
            if self._contains_any(post.url.path.lower(), ["/login"]) and not client.cookies:
                raise RuntimeError(self._diagnose_login_failure(post_text, post.status_code))
            if self._contains_any(post_text, ["invalid login", "incorrect", "authentication failed", "credenciales", "usuario o contraseña"]):
                raise RuntimeError(self._diagnose_login_failure(post_text, post.status_code))
            cookies = dict(client.cookies.items())
            if not cookies:
                raise RuntimeError(
                    "UPP login failed: no session cookie returned. Check login path, credentials, and whether SSO/CAPTCHA is enabled."
                )
            return cookies

    def _request_json(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        if not self.is_configured():
            raise RuntimeError("UPP provider is not configured. Set UPP_API_URL.")
        url = f"{self.api_url}{path}"
        with httpx.Client(
            timeout=self.timeout,
            headers=self._headers(),
            cookies=self._login_cookies(),
            follow_redirects=True,
        ) as client:
            response = client.request(method, url, params=params)
            response.raise_for_status()
            if not response.content:
                return {}
            try:
                return response.json()
            except Exception as exc:  # noqa: BLE001
                content_type = response.headers.get("content-type", "")
                body_preview = (response.text or "")[:180].replace("\n", " ").strip()
                raise RuntimeError(
                    f"UPP API returned non-JSON response for {path}. "
                    f"Status={response.status_code}, content-type={content_type or 'unknown'}, preview='{body_preview}'. "
                    "Check endpoint paths/env mapping for this UPP tenant."
                ) from exc

    @staticmethod
    def _extract_list(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [x for x in payload if isinstance(x, dict)]
        if isinstance(payload, dict):
            for key in ("courses", "materials", "enrollments", "items", "data", "results"):
                if isinstance(payload.get(key), list):
                    return [x for x in payload[key] if isinstance(x, dict)]
            return [payload]
        return []

    @staticmethod
    def _pick(*values: Any) -> Any:
        for value in values:
            if value is not None and value != "":
                return value
        return None

    def list_courses(self) -> list[ExternalCourse]:
        raw_courses: list[dict[str, Any]] = []
        try:
            payload = self._request_json("get", self.courses_path)
            raw_courses = self._extract_list(payload)
        except Exception:
            if not self._credentials_configured():
                raise
            courses_url = f"{self.api_url}{self.my_courses_path}"
            with httpx.Client(
                timeout=self.timeout,
                headers=self._headers(),
                cookies=self._login_cookies(),
                follow_redirects=True,
            ) as client:
                response = client.get(courses_url)
                response.raise_for_status()
                html = response.text
            links = re.findall(r'href=["\']([^"\']*course/view\.php\?id=(\d+)[^"\']*)["\'][^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL)
            seen: set[str] = set()
            for href, course_id, label in links:
                if course_id in seen:
                    continue
                seen.add(course_id)
                title = re.sub(r"<[^>]+>", "", label).strip() or f"UPP Course {course_id}"
                raw_courses.append({"id": course_id, "title": title, "url": href})
        courses: list[ExternalCourse] = []
        for c in raw_courses:
            course_id = self._pick(c.get("id"), c.get("course_id"), c.get("external_id"), c.get("uuid"))
            if course_id is None:
                continue
            title = self._pick(c.get("title"), c.get("name"), c.get("course_name"), f"UPP Course {course_id}")
            code = self._pick(c.get("code"), c.get("course_code"))
            term = self._pick(c.get("term"), c.get("semester"), c.get("period"))
            courses.append(
                ExternalCourse(
                    provider=self.provider_name,
                    external_id=str(course_id),
                    title=str(title),
                    code=str(code) if code is not None else None,
                    term=str(term) if term is not None else None,
                )
            )
        return courses

    def list_materials(self, course_external_id: str) -> list[ExternalMaterial]:
        path = self.materials_path_tpl.format(course_id=course_external_id)
        payload = self._request_json("get", path)
        raw_materials = self._extract_list(payload)
        materials: list[ExternalMaterial] = []
        for m in raw_materials:
            material_id = self._pick(m.get("id"), m.get("material_id"), m.get("external_id"), m.get("uuid"))
            if material_id is None:
                continue
            filename = self._pick(
                m.get("filename"),
                m.get("file_name"),
                m.get("name"),
                m.get("title"),
                f"material-{material_id}",
            )
            content_type = self._pick(
                m.get("content_type"),
                m.get("mime_type"),
                mimetypes.guess_type(str(filename))[0],
                "application/octet-stream",
            )
            source_url = self._pick(m.get("download_url"), m.get("url"), m.get("source_url"))
            materials.append(
                ExternalMaterial(
                    provider=self.provider_name,
                    external_id=str(material_id),
                    course_external_id=str(course_external_id),
                    title=str(self._pick(m.get("title"), m.get("name"), filename)),
                    filename=str(filename),
                    content_type=str(content_type),
                    size_bytes=int(self._pick(m.get("size"), m.get("size_bytes"), 0) or 0),
                    updated_at=str(self._pick(m.get("updated_at"), m.get("modified_at"), m.get("created_at")))
                    if self._pick(m.get("updated_at"), m.get("modified_at"), m.get("created_at")) is not None
                    else None,
                    source_url=str(source_url) if source_url is not None else None,
                )
            )
        return materials

    def _material_meta_by_id(self, material_external_id: str) -> ExternalMaterial | None:
        # Best-effort lookup across known courses. This is used only when direct
        # download metadata is unavailable.
        for course in self.list_courses():
            for mat in self.list_materials(course.external_id):
                if mat.external_id == str(material_external_id):
                    return mat
        return None

    def download_material(self, material_external_id: str) -> tuple[bytes, ExternalMaterial]:
        path = self.download_path_tpl.format(material_id=material_external_id)
        if not self.is_configured():
            raise RuntimeError("UPP provider is not configured. Set UPP_API_URL.")

        meta = self._material_meta_by_id(material_external_id) or ExternalMaterial(
            provider=self.provider_name,
            external_id=str(material_external_id),
            course_external_id="",
            title=f"UPP Material {material_external_id}",
            filename=f"material-{material_external_id}",
            content_type="application/octet-stream",
            size_bytes=0,
        )

        url = f"{self.api_url}{path}"
        with httpx.Client(
            timeout=self.timeout,
            headers=self._headers(),
            cookies=self._login_cookies(),
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            if not response.content:
                raise RuntimeError(
                    f"UPP material download returned empty content for material {material_external_id}. "
                    "Check the provider download endpoint mapping and access permissions."
                )
            return response.content, meta

    def list_enrollments(self, course_external_id: str) -> list[ExternalEnrollment]:
        path = self.enrollments_path_tpl.format(course_id=course_external_id)
        payload = self._request_json("get", path)
        raw = self._extract_list(payload)
        enrollments: list[ExternalEnrollment] = []
        for e in raw:
            user_id = self._pick(e.get("id"), e.get("user_id"), e.get("external_user_id"), e.get("uuid"))
            if user_id is None:
                continue
            role = str(self._pick(e.get("role"), "student"))
            enrollments.append(
                ExternalEnrollment(
                    provider=self.provider_name,
                    external_user_id=str(user_id),
                    role=role.lower(),
                    name=str(self._pick(e.get("name"), e.get("full_name"), e.get("display_name")))
                    if self._pick(e.get("name"), e.get("full_name"), e.get("display_name")) is not None
                    else None,
                    email=str(self._pick(e.get("email"), e.get("mail"), e.get("login")))
                    if self._pick(e.get("email"), e.get("mail"), e.get("login")) is not None
                    else None,
                )
            )
        return enrollments
