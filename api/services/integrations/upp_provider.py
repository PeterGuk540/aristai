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
from urllib.parse import parse_qs, urljoin, urlparse

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
        self.portal_courses_paths = [
            p.strip()
            for p in os.getenv(
                "UPP_PORTAL_COURSES_PATHS",
                "/coordinador/index.asp,/coordinador/cursos.asp,/aula-virtual.asp",
            ).split(",")
            if p.strip()
        ]
        self.portal_nav_exclude = {
            "mis cursos",
            "descargar material",
            "descargar materiales",
            "material",
            "materiales",
            "inicio",
            "home",
            "salir",
            "logout",
            "perfil",
            "mi perfil",
            "ayuda",
            "contacto",
        }
        self.mis_cursos_path = os.getenv("UPP_MIS_CURSOS_PATH", "/coordinador/carreras.asp").strip() or "/coordinador/carreras.asp"

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

    def _extract_form_html(self, html: str) -> tuple[str | None, str]:
        # Prefer a form containing a password input.
        forms = re.findall(r"(<form\b[^>]*>.*?</form>)", html, flags=re.IGNORECASE | re.DOTALL)
        if not forms:
            return None, html
        for form in forms:
            if re.search(r'<input[^>]+type=["\']password["\']', form, flags=re.IGNORECASE):
                return form, form
        return forms[0], forms[0]

    def _extract_form_action(self, form_html: str) -> str | None:
        match = re.search(r'<form\b[^>]*\baction=["\']([^"\']+)["\']', form_html, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip() or None

    def _extract_inputs(self, html: str) -> list[dict[str, str]]:
        inputs: list[dict[str, str]] = []
        for attrs in re.findall(r"<input\b([^>]*)>", html, flags=re.IGNORECASE | re.DOTALL):
            name_match = re.search(r'\bname=["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
            if not name_match:
                continue
            value_match = re.search(r'\bvalue=["\']([^"\']*)["\']', attrs, flags=re.IGNORECASE)
            type_match = re.search(r'\btype=["\']([^"\']+)["\']', attrs, flags=re.IGNORECASE)
            inputs.append(
                {
                    "name": name_match.group(1).strip(),
                    "value": (value_match.group(1) if value_match else "").strip(),
                    "type": (type_match.group(1).strip().lower() if type_match else "text"),
                }
            )
        return inputs

    @staticmethod
    def _clean_html_text(raw: str) -> str:
        text = re.sub(r"<[^>]+>", " ", raw or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _guess_login_fields(self, inputs: list[dict[str, str]]) -> tuple[str | None, str | None]:
        password_name: str | None = None
        username_name: str | None = None

        for inp in inputs:
            n = inp["name"].lower()
            t = inp["type"]
            if t == "password":
                password_name = inp["name"]
                break
            if not password_name and re.search(r"pass|clave|contras", n):
                password_name = inp["name"]

        username_candidates = []
        for inp in inputs:
            n = inp["name"].lower()
            t = inp["type"]
            if t in {"hidden", "password", "submit", "button", "checkbox", "radio"}:
                continue
            score = 0
            if re.search(r"user|usuario|login|email|correo|identifier|id", n):
                score += 2
            if t in {"text", "email"}:
                score += 1
            username_candidates.append((score, inp["name"]))

        if username_candidates:
            username_candidates.sort(key=lambda x: x[0], reverse=True)
            username_name = username_candidates[0][1]

        return username_name, password_name

    def _extract_course_id_from_url(self, href: str) -> str | None:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        for key in ("id", "course_id", "curso", "idcurso", "aula", "seccion"):
            val = qs.get(key)
            if val and val[0]:
                return str(val[0]).strip()
        match = re.search(r"(?:course|curso|aula|seccion)[=/\-](\d+)", href, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _encode_url_ref(prefix: str, url: str) -> str:
        raw = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").rstrip("=")
        return f"{prefix}:{raw}"

    @staticmethod
    def _decode_url_ref(value: str, prefix: str) -> str | None:
        if not value.startswith(f"{prefix}:"):
            return None
        payload = value.split(":", 1)[1]
        if not payload:
            return None
        pad = "=" * (-len(payload) % 4)
        try:
            return base64.urlsafe_b64decode((payload + pad).encode("utf-8")).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None

    def _scrape_courses_from_html(self, html: str, base_url: str) -> list[dict[str, Any]]:
        links = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href_raw, label_html in links:
            href = urljoin(base_url, href_raw.strip())
            label = self._clean_html_text(label_html)
            href_l = href.lower()
            label_l = label.lower()
            if label_l in self.portal_nav_exclude:
                continue
            looks_like_course = bool(
                ("inicio.asp" in href_l and "carcodi=" in href_l)
                or ("curso_cargar.asp" in href_l)
                or re.search(r"curcodi=|ciccodi=|seccodi=|crrcodi=", href_l)
                or re.search(r"p\d{6}-cur\d{5,}", label_l)
            )
            if not looks_like_course:
                continue
            extracted_id = self._extract_course_id_from_url(href)
            external_id = extracted_id if extracted_id else self._encode_url_ref("courseurl", href)
            key = f"{external_id}:{label}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "id": external_id,
                    "title": label or f"UPP Course {external_id}",
                    "url": href,
                }
            )
        return out

    def _extract_links(self, html: str, base_url: str) -> list[tuple[str, str]]:
        links = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        out: list[tuple[str, str]] = []
        for href_raw, label_html in links:
            href = urljoin(base_url, href_raw.strip())
            label = self._clean_html_text(label_html)
            if not href:
                continue
            out.append((href, label))
        return out

    def _is_career_link(self, href: str) -> bool:
        h = href.lower()
        return "inicio.asp" in h and "carcodi=" in h

    def _is_semester_link(self, href: str, label: str) -> bool:
        txt = f"{href} {label}".lower()
        if "seme=" in txt:
            return True
        return bool(
            re.search(r"semestre|periodo|ciclo|campa[nñ]a|t[eé]rmino|term", txt)
            or re.search(r"20\d{2}", txt)
            or re.search(r"\b(i|ii|iii|iv|v|vi|vii|viii)\b", txt)
        )

    def _is_course_entry_link(self, href: str, label: str) -> bool:
        h = href.lower()
        l = (label or "").lower()
        if l.strip() in self.portal_nav_exclude:
            return False
        if re.search(r"calendario|notificaciones|favoritos|blog|manual", h) or re.search(
            r"calendario|notificaciones|favoritos|blog|manual", l
        ):
            return False
        # Strict course row signature for this UPP tenant.
        if "curso_cargar.asp" in h:
            return bool(
                re.search(r"curcodi=", h)
                and re.search(r"ciccodi=", h)
                and re.search(r"seccodi=", h)
            )
        # Fallback: label has code and query includes curcodi.
        if re.search(r"p\d{6}-cur\d{5,}", l) and re.search(r"curcodi=", h):
            return True
        return False

    def _is_course_link(self, href: str, label: str) -> bool:
        label_l = (label or "").strip().lower()
        if not label_l or label_l in self.portal_nav_exclude:
            return False
        href_l = href.lower()
        if re.search(r"mis[_\s-]?cursos?|descargar[_\s-]?material|logout|salir", href_l):
            return False
        if re.search(r"silabo|s[ií]labo|contenido del curso|semana", label_l):
            return False
        # Strong UPP course signatures first.
        if ("inicio.asp" in href_l and "carcodi=" in href_l) or ("curso_cargar.asp" in href_l):
            return True
        if re.search(r"curcodi=|ciccodi=|seccodi=|crrcodi=", href_l):
            return True
        if re.search(r"p\d{6}-cur\d{5,}", label_l):
            return True
        if re.search(r"curso|course|asignatura|materia|secci[oó]n|aula", label_l):
            return True
        if re.search(r"[A-Z]{2,}\s*[-:]?\s*\d{2,}", label):
            return True
        if re.search(r"idcurso=|curso=|course_id=|id=", href_l):
            return True
        return False

    @staticmethod
    def _normalize_course_title(label: str) -> str:
        text = re.sub(r"\(docente:.*?\)", "", label, flags=re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip(" _-")
        return text or label

    def _discover_courses_via_mis_cursos(self, client: httpx.Client, seed_url: str) -> list[dict[str, Any]]:
        # Explicit starting point from your UPP tenant.
        mis_cursos_url = urljoin(seed_url, self.mis_cursos_path)
        mis_resp = client.get(mis_cursos_url)
        mis_resp.raise_for_status()
        mis_links = self._extract_links(mis_resp.text, str(mis_resp.url))

        # Step 1: careers list
        career_links = [href for href, _ in mis_links if self._is_career_link(href)]
        if not career_links:
            career_links = [mis_cursos_url]

        discovered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for career_url in career_links[:60]:
            try:
                career_page = client.get(career_url)
                career_page.raise_for_status()
            except Exception:
                continue

            career_links_all = self._extract_links(career_page.text, str(career_page.url))
            semester_links = [href for href, label in career_links_all if self._is_semester_link(href, label)]
            candidate_pages = semester_links if semester_links else [str(career_page.url)]

            # Step 2: semester pages -> course entries
            for page_url in candidate_pages[:40]:
                try:
                    page = client.get(page_url)
                    page.raise_for_status()
                except Exception:
                    continue
                page_links = self._extract_links(page.text, str(page.url))
                for href, label in page_links:
                    if not self._is_course_entry_link(href, label):
                        continue
                    course_id = self._encode_url_ref("courseurl", href)
                    title = self._normalize_course_title(label.strip())
                    key = f"{course_id}:{title.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    discovered.append(
                        {
                            "id": course_id,
                            "title": title or f"UPP Course {course_id}",
                            "url": href,
                        }
                    )
        return discovered

    def _looks_like_material_link(self, href: str, label: str) -> bool:
        href_l = href.lower()
        label_l = label.lower()
        if re.search(r"\.(pdf|docx?|pptx?|xlsx?|csv|txt|zip|rar|mp4|mp3)(\?|$)", href_l):
            return True
        if re.search(r"download|archivo|material|recurso|adjunto|file|files|document", href_l):
            return True
        if re.search(r"archivo|material|recurso|adjunto|documento", label_l):
            return True
        return False

    def _filename_from_url(self, href: str) -> str:
        parsed = urlparse(href)
        name = (parsed.path.rsplit("/", 1)[-1] or "").strip()
        if name:
            return name
        return "material.bin"

    def _scrape_materials_from_html(self, html: str, base_url: str, course_external_id: str) -> list[ExternalMaterial]:
        links = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        out: list[ExternalMaterial] = []
        seen: set[str] = set()
        for href_raw, label_html in links:
            href = urljoin(base_url, href_raw.strip())
            label = self._clean_html_text(label_html)
            if not self._looks_like_material_link(href, label):
                continue
            external_id = self._encode_url_ref("maturl", href)
            if external_id in seen:
                continue
            seen.add(external_id)
            filename = self._filename_from_url(href)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            out.append(
                ExternalMaterial(
                    provider=self.provider_name,
                    external_id=external_id,
                    course_external_id=str(course_external_id),
                    title=label or filename,
                    filename=filename,
                    content_type=content_type,
                    size_bytes=0,
                    source_url=href,
                )
            )
        return out

    def _is_course_content_nav_link(self, href: str, label: str) -> bool:
        txt = f"{href} {label}".lower()
        return bool(
            re.search(
                r"semana=|s[ií]labo|syllabus|contenido|did[aá]ctico|clases|grabadas|trabajo|ayudas|lecturas|evaluaciones|filemanager|linkmanager|onlineclasses|recordedclasses|educationalcontent|academicwork|selectedreadings|academicsupport|webgrafia",
                txt,
            )
        )

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
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 AristAI/UPP-Integration"},
        ) as client:
            page = client.get(login_url)
            page.raise_for_status()
            form_html, _ = self._extract_form_html(page.text)
            candidate_html = form_html or page.text
            inputs = self._extract_inputs(candidate_html)
            payload = {inp["name"]: inp["value"] for inp in inputs if inp["type"] == "hidden"}
            username_field, password_field = self._guess_login_fields(inputs)
            if not username_field:
                username_field = "username"
            if not password_field:
                password_field = "password"
            payload[username_field] = self.username or ""
            payload[password_field] = self.password or ""
            action = self._extract_form_action(candidate_html)
            post_url = urljoin(str(page.url), action) if action else login_url
            post = client.post(post_url, data=payload)
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
            with httpx.Client(
                timeout=self.timeout,
                headers=self._headers(),
                cookies=self._login_cookies(),
                follow_redirects=True,
            ) as client:
                # Guided flow fallback: seed page -> "Mis Cursos" -> semester -> course links
                for path in self.portal_courses_paths:
                    try:
                        seed_url = f"{self.api_url}{path}"
                        guided = self._discover_courses_via_mis_cursos(client, seed_url)
                        if guided:
                            raw_courses.extend(guided)
                            break
                    except Exception:
                        continue

                # Moodle-like fallback
                if not raw_courses:
                    try:
                        courses_url = f"{self.api_url}{self.my_courses_path}"
                        response = client.get(courses_url)
                        response.raise_for_status()
                        raw_courses.extend(self._scrape_courses_from_html(response.text, str(response.url)))
                    except Exception:
                        pass

                # Portal fallback (UPP-specific coordinator pages)
                if not raw_courses:
                    for path in self.portal_courses_paths:
                        try:
                            portal_url = f"{self.api_url}{path}"
                            response = client.get(portal_url)
                            response.raise_for_status()
                            scraped = self._scrape_courses_from_html(response.text, str(response.url))
                            if scraped:
                                raw_courses.extend(scraped)
                                break
                        except Exception:
                            continue

            if not raw_courses:
                raise RuntimeError(
                    "UPP course discovery failed: no supported JSON course endpoint and no course links found in portal pages. "
                    "Configure UPP_COURSES_PATH for this tenant or provide portal-specific scraping paths."
                )
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
        course_url = self._decode_url_ref(str(course_external_id), "courseurl")
        raw_materials: list[dict[str, Any]] = []
        if course_url is None:
            path = self.materials_path_tpl.format(course_id=course_external_id)
            try:
                payload = self._request_json("get", path)
                raw_materials = self._extract_list(payload)
            except Exception:
                raw_materials = []

        if course_url is not None or not raw_materials:
            if course_url is None:
                raise RuntimeError(
                    f"UPP materials endpoint not found for course '{course_external_id}'. "
                    "This tenant likely needs portal scraping with URL-based course identifiers."
                )
            with httpx.Client(
                timeout=self.timeout,
                headers=self._headers(),
                cookies=self._login_cookies(),
                follow_redirects=True,
            ) as client:
                # Crawl course page + content/week tab pages.
                queue = [course_url]
                visited: set[str] = set()
                scraped: list[ExternalMaterial] = []
                while queue and len(visited) < 20:
                    page_url = queue.pop(0)
                    if page_url in visited:
                        continue
                    visited.add(page_url)
                    try:
                        response = client.get(page_url)
                        response.raise_for_status()
                    except Exception:
                        continue
                    page_html = response.text
                    base = str(response.url)
                    scraped.extend(self._scrape_materials_from_html(page_html, base, str(course_external_id)))
                    for href, label in self._extract_links(page_html, base):
                        if self._is_course_content_nav_link(href, label):
                            if href not in visited and href not in queue:
                                queue.append(href)
            if scraped:
                # dedupe by external_id while preserving order
                unique: dict[str, ExternalMaterial] = {}
                for m in scraped:
                    if m.external_id not in unique:
                        unique[m.external_id] = m
                return list(unique.values())
                return scraped
            raise RuntimeError(
                f"UPP materials could not be discovered from course page: {course_url}. "
                "No downloadable material links were detected."
            )

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
        material_url = self._decode_url_ref(str(material_external_id), "maturl")
        if material_url is not None:
            filename = self._filename_from_url(material_url)
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            meta = ExternalMaterial(
                provider=self.provider_name,
                external_id=str(material_external_id),
                course_external_id="",
                title=filename,
                filename=filename,
                content_type=content_type,
                size_bytes=0,
                source_url=material_url,
            )
            with httpx.Client(
                timeout=self.timeout,
                headers=self._headers(),
                cookies=self._login_cookies(),
                follow_redirects=True,
            ) as client:
                response = client.get(material_url)
                response.raise_for_status()
                if not response.content:
                    raise RuntimeError(
                        f"UPP material download returned empty content for URL material {material_url}."
                    )
                meta.size_bytes = len(response.content)
                return response.content, meta

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
