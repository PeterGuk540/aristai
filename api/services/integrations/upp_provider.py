"""UPP provider implementation for the LMS integration hub.

This connector is endpoint-configurable so different UPP deployments can map
their API shapes without code changes.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import httpx

from api.services.integrations.base import ExternalCourse, ExternalEnrollment, ExternalMaterial, ExternalSession, LmsProvider

logger = logging.getLogger(__name__)


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

        # Browser automation settings for JavaScript-rendered content
        self.use_browser_fallback = os.getenv("UPP_USE_BROWSER_FALLBACK", "true").lower() == "true"
        self.browser_timeout = float(os.getenv("UPP_BROWSER_TIMEOUT", "30"))
        self.extract_videos = os.getenv("UPP_EXTRACT_VIDEOS", "true").lower() == "true"

        # Chrome MCP: Universal LLM-driven extraction (recommended)
        # When enabled, uses LLM to analyze page structure instead of regex patterns
        self.use_chrome_mcp = os.getenv("UPP_USE_CHROME_MCP", "true").lower() == "true"

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
        # Decode common HTML entities
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")
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
            looks_like_course = self._is_course_entry_link(href, label)
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
        out: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()

        href_links = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for href_raw, label_html in href_links:
            href = urljoin(base_url, href_raw.strip())
            label = self._clean_html_text(label_html)
            if not href:
                continue
            key = (href, label)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)

        onclick_links = re.findall(
            r'<a[^>]+onclick=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for onclick_js, label_html in onclick_links:
            label = self._clean_html_text(label_html)
            js = onclick_js.strip()
            match = re.search(
                r"""(?:location(?:\.href)?|window\.open)\s*\(?\s*['"]([^'"]+)['"]""",
                js,
                flags=re.IGNORECASE,
            )
            if not match:
                continue
            href = urljoin(base_url, match.group(1).strip())
            key = (href, label)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
        return out

    def _extract_course_urls_from_raw_html(self, html: str, base_url: str) -> list[tuple[str, str]]:
        """Extract course URLs and their titles from raw HTML.

        Returns list of (url, title) tuples.
        """
        import logging
        logger = logging.getLogger(__name__)

        results: list[tuple[str, str]] = []
        seen: set[str] = set()

        # Pattern 1: Standard <a href="...curso_cargar.asp...">content</a>
        # Supports both single and double quotes, and href with or without quotes
        link_patterns = [
            # Standard quoted href
            re.compile(
                r'<a\s[^>]*href\s*=\s*["\']([^"\']*curso_cargar\.asp\?[^"\']+)["\'][^>]*>(.*?)</a>',
                flags=re.IGNORECASE | re.DOTALL,
            ),
            # Unquoted href (rare but possible in old HTML)
            re.compile(
                r'<a\s[^>]*href\s*=\s*([^\s>]*curso_cargar\.asp\?[^\s>]+)[^>]*>(.*?)</a>',
                flags=re.IGNORECASE | re.DOTALL,
            ),
        ]

        for pattern in link_patterns:
            for match in pattern.finditer(html):
                href_raw = match.group(1).replace("&amp;", "&")
                href = urljoin(base_url, href_raw)
                if href in seen:
                    continue

                label_html = match.group(2)
                label = self._clean_html_text(label_html)
                title = self._normalize_course_title(label)

                logger.info(f"UPP course from <a> tag: '{title}'")
                seen.add(href)
                results.append((href, title))

        # Pattern 2: Extract title from course header on course detail page
        # Format: CURSO: P004103-CUR006620  CIENCIAS PARA LA INGENIERÍA I  (Sec: ...)
        header_pattern = re.compile(
            r'CURSO:\s*([A-Z]\d+-[A-Z]+\d+)\s*&nbsp;[&nbsp;\s]*([^<(]+)',
            flags=re.IGNORECASE,
        )
        for match in header_pattern.finditer(html):
            course_code = match.group(1).strip()
            course_name = self._clean_html_text(match.group(2)).strip()
            if course_name:
                logger.info(f"UPP course from header: code={course_code}, name='{course_name}'")

        # Fallback: find curso_cargar URLs and try to extract title from surrounding context
        fallback_pattern = re.compile(
            r'curso_cargar\.asp\?([^"\'<>\s]+)',
            flags=re.IGNORECASE,
        )
        for match in fallback_pattern.finditer(html):
            query = match.group(1).replace("&amp;", "&")
            href = urljoin(base_url, f"curso_cargar.asp?{query}")
            if href in seen:
                continue

            # Try to find the title near this URL by looking at surrounding text
            start_pos = max(0, match.start() - 50)
            end_pos = min(len(html), match.end() + 500)
            context = html[start_pos:end_pos]

            # Look for course title pattern in the context after the URL
            # Pattern: P004103-CUR006620&nbsp;&nbsp;COURSE NAME&nbsp; (sec:...
            title_match = re.search(
                r'>\s*([A-Z]\d+-[A-Z]+\d+)\s*(?:&nbsp;|\s)+([^<]+?)(?:\s*\(sec:|\s*<)',
                context,
                flags=re.IGNORECASE,
            )
            if title_match:
                raw_title = title_match.group(2)
                title = self._clean_html_text(raw_title).strip()
                title = self._normalize_course_title(title)
                if title and len(title) > 3:
                    logger.info(f"UPP course from context: '{title}'")
                    seen.add(href)
                    results.append((href, title))
                    continue

            # Final fallback: use query string
            fallback_title = f"UPP Course {query}"[:180]
            logger.info(f"UPP fallback (no title found): '{fallback_title}'")
            seen.add(href)
            results.append((href, fallback_title))

        logger.info(f"UPP _extract_course_urls: Returning {len(results)} courses")
        return results

    def _is_career_link(self, href: str) -> bool:
        h = href.lower()
        return "inicio.asp" in h and "carcodi=" in h

    def _is_semester_link(self, href: str, label: str) -> bool:
        txt = f"{href} {label}".lower()
        if "seme=" in txt or "sem=" in txt:
            return True
        if "cursos.asp" in txt and ("carcodi=" in txt or "sem=" in txt):
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
            return bool(re.search(r"curcodi=", h))
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
        """Normalize course title by extracting just the course name.

        Input examples:
        - "P004103-CUR006620  CIENCIAS PARA LA INGENIERÍA I (sec: 7120)  (Docente: JAIR KANASHIRO)"
        - "P004103-CUR006618  ORGANIZACIÓN Y ARQUITECTURA DE COMPUTADORES (sec: 7120)"

        Output: "CIENCIAS PARA LA INGENIERÍA I" or "ORGANIZACIÓN Y ARQUITECTURA DE COMPUTADORES"
        """
        text = label

        # Remove teacher info: (Docente: ...)
        text = re.sub(r"\(docente:.*?\)", "", text, flags=re.IGNORECASE)

        # Remove section info: (sec: ...) or (sec:...)
        text = re.sub(r"\(sec:\s*\d+\s*\)", "", text, flags=re.IGNORECASE)

        # Remove course code prefix: P004103-CUR006620 or similar patterns
        # Pattern: letter + digits + hyphen + letters + digits at the start
        text = re.sub(r"^[A-Z]\d{4,}-[A-Z]{2,}\d{4,}\s*", "", text, flags=re.IGNORECASE)

        # Clean up multiple spaces and trim
        text = re.sub(r"\s+", " ", text).strip(" _-")

        # If we stripped everything, return original
        return text if text else label

    def _discover_courses_via_mis_cursos(self, client: httpx.Client, seed_url: str) -> list[dict[str, Any]]:
        import logging
        logger = logging.getLogger(__name__)

        # Explicit starting point from your UPP tenant.
        mis_cursos_url = urljoin(seed_url, self.mis_cursos_path)
        logger.info(f"UPP _discover_courses: Fetching mis_cursos_url={mis_cursos_url}")
        mis_resp = client.get(mis_cursos_url)
        mis_resp.raise_for_status()
        logger.info(f"UPP _discover_courses: Got {len(mis_resp.text)} bytes from mis_cursos page")
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
            for href, extracted_title in self._extract_course_urls_from_raw_html(career_page.text, str(career_page.url)):
                if not self._is_course_entry_link(href, extracted_title or "curso"):
                    continue
                course_id = self._encode_url_ref("courseurl", href)
                title = extracted_title or f"UPP Course {urlparse(href).query}"[:180]
                key = f"{course_id}:{title.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                discovered.append(
                    {
                        "id": course_id,
                        "title": title,
                        "url": href,
                    }
                )

            for href, label in career_links_all:
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
                for href, extracted_title in self._extract_course_urls_from_raw_html(page.text, str(page.url)):
                    if not self._is_course_entry_link(href, extracted_title or "curso"):
                        continue
                    course_id = self._encode_url_ref("courseurl", href)
                    title = extracted_title or f"UPP Course {urlparse(href).query}"[:180]
                    key = f"{course_id}:{title.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    discovered.append(
                        {
                            "id": course_id,
                            "title": title,
                            "url": href,
                        }
                    )
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

        # Reject unresolved JS template literals (e.g. "${escapeHtml(file.fileUrl)}")
        from urllib.parse import unquote as _unquote
        decoded_href = _unquote(href)
        if any(pat in decoded_href for pat in ('${', '{%', '{{', 'escapeHtml', 'encodeURI')):
            return False

        # ========== UPP-SPECIFIC: Direct file paths ==========
        # PDFs served from /books/final/... are actual files
        if '/books/' in href_l and '.pdf' in href_l:
            return True

        # download.asp with id parameter is a file download
        if 'download.asp' in href_l and 'id=' in href_l:
            return True

        # Skip navigation/portal ASP pages - these are pages to crawl, not download
        # They contain links to actual materials but aren't materials themselves
        if re.search(r"\.(asp|aspx|php|html?)(\?|$)", href_l):
            # Exception: ASP pages with download parameters ARE materials
            if re.search(r"[?&](download|file|archivo|id)=", href_l):
                return True
            # Exception: direct file download endpoints
            if re.search(r"download\.asp|getfile\.asp|archivo\.asp", href_l):
                return True
            # Otherwise, ASP/PHP pages are navigation, not materials
            return False

        # Actual file extensions - these are definitely materials
        if re.search(r"\.(pdf|docx?|pptx?|xlsx?|csv|txt|zip|rar|mp4|mp3|m3u8|webm|avi|mov)(\?|$)", href_l):
            return True

        # URLs with download-related paths (but not ASP pages which are excluded above)
        if re.search(r"download|archivo|material|recurso|adjunto|file|files|document", href_l):
            return True

        # External video/streaming URLs
        if re.search(r"youtube\.com|vimeo\.com|drive\.google\.com|dropbox\.com|onedrive\.com|teams\.microsoft\.com", href_l):
            return True

        # Label-based detection for links that might be materials
        if re.search(
            r"archivo|material|recurso|adjunto|documento|descargar|download|sílabo|silabo|syllabus",
            label_l,
        ):
            return True

        return False

    def _filename_from_url(self, href: str) -> str:
        parsed = urlparse(href)
        name = (parsed.path.rsplit("/", 1)[-1] or "").strip()
        if name:
            return name
        return "material.bin"

    def _extract_session_from_url(self, url: str, course_external_id: str) -> str | None:
        """Extract session ID from URL with semana=X parameter."""
        match = re.search(r'[?&]semana=(\d+)', url, flags=re.IGNORECASE)
        if match:
            week_num = match.group(1)
            return f"{course_external_id}:semana:{week_num}"
        return None

    def _scrape_materials_from_html(
        self,
        html: str,
        base_url: str,
        course_external_id: str,
        session_external_id: str | None = None,
    ) -> list[ExternalMaterial]:
        # Extract links from <a href> tags
        links = re.findall(
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Also extract URLs from onclick handlers (common in UPP)
        onclick_urls = re.findall(
            r'onclick=["\'][^"\']*(?:window\.open|location\.href|window\.location)\s*[=\(]\s*["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        for url in onclick_urls:
            links.append((url, ""))

        # Extract video sources
        video_sources = re.findall(
            r'<(?:source|video)[^>]+src=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        for src in video_sources:
            links.append((src, "Video"))

        # ========== UPP-SPECIFIC: Extract PDFs from iframes ==========
        # UPP embeds PDFs like: <iframe src="/books/final/2026100/000/xxx.pdf">
        iframe_pdfs = re.findall(
            r'<iframe[^>]+src=["\']([^"\']+\.pdf)["\']',
            html,
            flags=re.IGNORECASE,
        )
        for src in iframe_pdfs:
            links.append((src, "Syllabus PDF"))
        logger.info(f"Found {len(iframe_pdfs)} PDF iframes in page")

        # Extract all iframe sources (for other embedded content)
        iframe_sources = re.findall(
            r'<iframe[^>]+src=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        for src in iframe_sources:
            if 'youtube' in src.lower() or 'vimeo' in src.lower() or 'video' in src.lower():
                links.append((src, "Embedded Video"))

        # ========== UPP-SPECIFIC: Extract file items with data-id ==========
        # UPP uses: <div class="file-item" data-id="1147"> with file-name inside
        # Pattern: find file-item divs and extract data-id + file-name
        file_items = re.findall(
            r'<div[^>]+class=["\'][^"\']*file-item[^"\']*["\'][^>]+data-id=["\'](\d+)["\'][^>]*>.*?'
            r'<div[^>]+class=["\'][^"\']*file-name[^"\']*["\'][^>]*(?:title=["\']([^"\']*)["\'])?[^>]*>([^<]*)</div>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        logger.info(f"Found {len(file_items)} file items with data-id in page")

        for data_id, title_attr, text_content in file_items:
            # Construct download URL from data-id
            # UPP likely uses: /coordinador/fileManager/download.asp?id=XXX
            filename = (title_attr or text_content).strip()
            if filename and filename != "0":  # "0" is used for links without files
                # Determine the file manager path based on page context
                download_url = urljoin(base_url, f"/coordinador/fileManager/download.asp?id={data_id}")
                links.append((download_url, filename))

        # ========== UPP-SPECIFIC: Extract material names for context ==========
        # <div class="file-material-name">SÍLABO - NEGOCIACIÓN...</div>
        material_names = re.findall(
            r'<div[^>]+class=["\'][^"\']*file-material-name[^"\']*["\'][^>]*>([^<]+)</div>',
            html,
            flags=re.IGNORECASE,
        )

        # Extract embed/object sources
        embed_sources = re.findall(
            r'<(?:embed|object)[^>]+(?:src|data)=["\']([^"\']+)["\']',
            html,
            flags=re.IGNORECASE,
        )
        for src in embed_sources:
            links.append((src, "Embedded Content"))

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

            # Determine session from URL parameter or passed value
            material_session_id = session_external_id
            if not material_session_id:
                material_session_id = self._extract_session_from_url(href, course_external_id)

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
                    session_external_id=material_session_id,
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

    def _extract_sessions_from_html(self, html: str, course_external_id: str) -> list[ExternalSession]:
        """Extract sessions/weeks (Semanas) from course page HTML.

        UPP structure: Accordion panels with titles like "Semana 1", "Semana 2", etc.
        Each session contains links with ?semana=X parameter.
        """
        sessions: list[ExternalSession] = []
        seen_weeks: set[int] = set()

        # Pattern 1: Look for accordion headers with "Semana X" pattern
        # e.g., <div class="accordion-header">Semana 1</div>
        accordion_pattern = re.findall(
            r'(?:accordion|panel|collapse)[^>]*>.*?[Ss]emana\s*(\d+)',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        for week_num_str in accordion_pattern:
            try:
                week_num = int(week_num_str)
                if week_num not in seen_weeks:
                    seen_weeks.add(week_num)
            except ValueError:
                continue

        # Pattern 2: Extract from links with semana=X parameter
        semana_links = re.findall(r'[?&]semana=(\d+)', html, flags=re.IGNORECASE)
        for week_num_str in semana_links:
            try:
                week_num = int(week_num_str)
                if week_num not in seen_weeks:
                    seen_weeks.add(week_num)
            except ValueError:
                continue

        # Pattern 3: Look for "Semana X" text in any context
        semana_text = re.findall(r'[Ss]emana\s*(\d+)', html)
        for week_num_str in semana_text:
            try:
                week_num = int(week_num_str)
                if week_num not in seen_weeks:
                    seen_weeks.add(week_num)
            except ValueError:
                continue

        # Create session objects for each discovered week
        for week_num in sorted(seen_weeks):
            session_id = f"{course_external_id}:semana:{week_num}"
            sessions.append(
                ExternalSession(
                    provider=self.provider_name,
                    external_id=session_id,
                    course_external_id=str(course_external_id),
                    title=f"Semana {week_num}",
                    week_number=week_num,
                )
            )

        return sessions

    def list_sessions(self, course_external_id: str) -> list[ExternalSession]:
        """List sessions/weeks for a UPP course by scraping the course page."""
        course_url = self._decode_url_ref(str(course_external_id), "courseurl")

        if course_url is None:
            # No URL-based course ID, return empty list
            return []

        sessions: list[ExternalSession] = []

        with httpx.Client(
            timeout=self.timeout,
            headers=self._headers(),
            cookies=self._login_cookies(),
            follow_redirects=True,
        ) as client:
            try:
                response = client.get(course_url)
                response.raise_for_status()
                sessions = self._extract_sessions_from_html(response.text, str(course_external_id))
            except Exception:
                pass

        return sessions

    # ============ Browser Fallback Methods ============

    def _needs_browser_fallback(self, html: str, materials: list) -> bool:
        """
        Detect if browser automation is needed.

        Returns True when:
        1. No materials found but page has JavaScript indicators
        2. Page has video content indicators but no video materials extracted
        """
        if not self.use_browser_fallback:
            return False

        # No materials found but page has dynamic content indicators
        if not materials:
            js_indicators = [
                'onclick=', 'javascript:', 'ng-', 'v-', 'react',
                'data-src=', 'lazy-load', 'ajax', 'fetch(', 'async',
                'semana', 'Semana', 'accordion', 'collapse',
            ]
            return any(ind in html for ind in js_indicators)

        # Check for video content indicators without extracted videos
        if self.extract_videos:
            video_indicators = [
                'video', 'player', 'stream', 'grabadas', 'clases en línea',
                'recordedclasses', 'onlineclasses', 'multimedia',
            ]
            has_video_indicators = any(ind in html.lower() for ind in video_indicators)
            has_video_materials = any(
                m.content_type.startswith('video/') or
                any(ext in (m.source_url or '').lower() for ext in ['.mp4', '.m3u8', '.mpd'])
                for m in materials
            )
            return has_video_indicators and not has_video_materials

        return False

    def _fetch_materials_with_browser(
        self,
        course_url: str,
        course_external_id: str,
        sub_page_urls: list[str] | None = None,
    ) -> list[ExternalMaterial]:
        """
        Extract materials using browser automation.

        When Chrome MCP is enabled (recommended), uses LLM-driven universal extraction.
        Otherwise, falls back to pattern-based BrowserMaterialFetcher.

        Args:
            course_url: Main course page URL
            course_external_id: External ID of the course
            sub_page_urls: Optional list of sub-page URLs discovered during crawl
        """
        if self.use_chrome_mcp:
            return self._fetch_materials_with_chrome_mcp(course_url, course_external_id, sub_page_urls)
        else:
            return self._fetch_materials_with_playwright(course_url, course_external_id)

    def _fetch_materials_with_chrome_mcp(
        self,
        course_url: str,
        course_external_id: str,
        sub_page_urls: list[str] | None = None,
    ) -> list[ExternalMaterial]:
        """
        Use Chrome MCP to extract materials universally via rule-based DOM analysis.

        When sub_page_urls are provided, visits all sub-pages (where JS-rendered
        file lists live) using a single browser context instead of only the main page.
        """
        from api.services.integrations.chrome_mcp_client import (
            extract_materials_from_pages,
            extract_materials_universal,
        )

        # Build the list of pages to visit
        all_urls: list[str] = []
        if sub_page_urls:
            # Use sub-pages (where actual files are JS-rendered)
            all_urls = list(sub_page_urls)
            # Include the main course page if not already in sub-pages
            if course_url not in all_urls:
                all_urls.insert(0, course_url)
        else:
            all_urls = [course_url]

        logger.info(f"Chrome MCP extracting materials from {len(all_urls)} pages")

        async def _fetch():
            cookies = self._login_cookies()
            if len(all_urls) > 1:
                extracted = await extract_materials_from_pages(
                    page_urls=all_urls,
                    cookies=cookies,
                    base_url=self.api_url,
                    timeout=self.browser_timeout,
                    use_llm=False,
                )
            else:
                extracted = await extract_materials_universal(
                    page_url=all_urls[0],
                    cookies=cookies,
                    base_url=self.api_url,
                    timeout=self.browser_timeout,
                    use_llm=False,
                )

            materials = []
            for m in extracted:
                external_id = self._encode_url_ref("maturl", m.url)
                filename = m.url.rsplit('/', 1)[-1].split('?')[0] or 'material.bin'
                content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

                # Map file_type to content_type
                if m.file_type == 'pdf':
                    content_type = 'application/pdf'
                elif m.file_type == 'video':
                    content_type = 'video/mp4'
                elif m.file_type == 'document':
                    content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

                materials.append(ExternalMaterial(
                    provider=self.provider_name,
                    external_id=external_id,
                    course_external_id=course_external_id,
                    title=m.title or filename,
                    filename=filename,
                    content_type=content_type,
                    size_bytes=0,
                    source_url=m.url,
                ))

            logger.info(f"Chrome MCP extracted {len(materials)} materials")
            return materials

        # Run async in sync context
        return self._run_async(_fetch())

    def _fetch_materials_with_playwright(
        self,
        course_url: str,
        course_external_id: str,
    ) -> list[ExternalMaterial]:
        """
        Use Playwright with pattern-based extraction (fallback).

        This is the legacy approach that uses regex patterns.
        Use Chrome MCP for better universal extraction.
        """
        from api.services.integrations.browser_helper import BrowserMaterialFetcher

        async def _fetch():
            cookies = self._login_cookies()
            fetcher = BrowserMaterialFetcher(cookies, self.browser_timeout)
            raw_materials = await fetcher.fetch_materials_from_page(
                course_url, self.api_url
            )

            materials = []
            for m in raw_materials:
                external_id = self._encode_url_ref("maturl", m['url'])
                filename = m['url'].rsplit('/', 1)[-1].split('?')[0] or 'material.bin'
                content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

                materials.append(ExternalMaterial(
                    provider=self.provider_name,
                    external_id=external_id,
                    course_external_id=course_external_id,
                    title=m.get('title', filename),
                    filename=filename,
                    content_type=content_type,
                    size_bytes=0,
                    source_url=m['url'],
                ))

            return materials

        return self._run_async(_fetch())

    def _run_async(self, coro):
        """Run async coroutine in sync context."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None:
            # If already in an async context, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return asyncio.run(coro)

    def _extract_video_url_with_browser(self, page_url: str) -> Optional[str]:
        """Extract video stream URL from a video page using browser."""
        from api.services.integrations.browser_helper import extract_video_stream_url

        async def _extract():
            cookies = self._login_cookies()
            return await extract_video_stream_url(page_url, cookies, self.browser_timeout)

        return self._run_async(_extract())

    def _download_with_browser(self, url: str) -> tuple[bytes, str]:
        """Download file using browser for protected downloads."""
        from api.services.integrations.browser_helper import download_with_browser

        async def _download():
            cookies = self._login_cookies()
            return await download_with_browser(url, cookies, self.browser_timeout)

        return self._run_async(_download())

    def _is_video_page(self, url: str) -> bool:
        """Check if URL is a video page (not a direct video file)."""
        url_lower = url.lower()
        # Direct video files - not pages
        if url_lower.endswith(('.mp4', '.m3u8', '.mpd', '.webm', '.avi', '.mov')):
            return False
        # Video page patterns
        video_page_patterns = [
            'recordedclasses', 'onlineclasses', 'video', 'player',
            'multimedia', 'stream', 'watch', 'reproductor',
        ]
        return any(pattern in url_lower for pattern in video_page_patterns)

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
                # Track URLs with their session context: (url, session_external_id)
                queue: list[tuple[str, str | None]] = [(course_url, None)]
                visited: set[str] = set()
                scraped: list[ExternalMaterial] = []

                while queue and len(visited) < 40:  # Increased limit for session pages
                    page_url, current_session_id = queue.pop(0)
                    if page_url in visited:
                        continue
                    visited.add(page_url)

                    # Determine session from URL if not already set
                    if not current_session_id:
                        current_session_id = self._extract_session_from_url(page_url, course_external_id)

                    try:
                        response = client.get(page_url)
                        response.raise_for_status()
                    except Exception:
                        continue

                    page_html = response.text
                    base = str(response.url)

                    # Scrape materials from this page with session context
                    scraped.extend(
                        self._scrape_materials_from_html(
                            page_html, base, str(course_external_id), current_session_id
                        )
                    )

                    # Find more content pages to crawl
                    for href, label in self._extract_links(page_html, base):
                        if self._is_course_content_nav_link(href, label):
                            if href not in visited:
                                # Extract session from the link URL
                                link_session_id = self._extract_session_from_url(href, course_external_id)
                                queue.append((href, link_session_id or current_session_id))

                # Collect all visited sub-page URLs (excluding the main course page)
                # These are the JS-rendered pages where files actually live
                sub_page_urls = [u for u in visited if u != course_url]
                logger.info(f"Static crawl visited {len(visited)} pages ({len(sub_page_urls)} sub-pages)")

            if scraped:
                # dedupe by external_id while preserving order
                unique: dict[str, ExternalMaterial] = {}
                for m in scraped:
                    if m.external_id not in unique:
                        unique[m.external_id] = m
                materials = list(unique.values())

                # Check if browser fallback is needed (JS content or missing videos)
                # Use the last page's HTML for detection
                if self._needs_browser_fallback(page_html, materials):
                    logger.info(f"Browser fallback triggered for course {course_external_id}")
                    try:
                        browser_materials = self._fetch_materials_with_browser(
                            course_url, str(course_external_id),
                            sub_page_urls=sub_page_urls,
                        )
                        # Merge browser results (avoid duplicates)
                        for bm in browser_materials:
                            if bm.external_id not in unique:
                                unique[bm.external_id] = bm
                        materials = list(unique.values())
                        logger.info(f"Browser fallback added {len(browser_materials)} materials")
                    except Exception as e:
                        logger.warning(f"Browser fallback failed: {e}")

                return materials

            # Static scraping found nothing - try browser fallback
            if self.use_browser_fallback:
                logger.info(f"No materials from static scraping, trying browser for {course_url}")
                try:
                    browser_materials = self._fetch_materials_with_browser(
                        course_url, str(course_external_id),
                        sub_page_urls=sub_page_urls,
                    )
                    if browser_materials:
                        return browser_materials
                except Exception as e:
                    logger.warning(f"Browser fallback failed: {e}")

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
            # Reject unresolved JS template literals before attempting download
            from urllib.parse import unquote as _unquote
            decoded_url = _unquote(material_url)
            if any(pat in decoded_url for pat in ('${', '{%', '{{', 'escapeHtml', 'encodeURI')):
                raise RuntimeError(
                    f"UPP material URL contains unresolved template literal: {material_url[:120]}"
                )

            # Check if this is a video page that needs browser extraction
            if self.extract_videos and self.use_browser_fallback and self._is_video_page(material_url):
                logger.info(f"Detected video page, extracting stream URL: {material_url}")
                try:
                    stream_url = self._extract_video_url_with_browser(material_url)
                    if stream_url:
                        logger.info(f"Extracted video stream URL: {stream_url[:100]}...")
                        material_url = stream_url
                except Exception as e:
                    logger.warning(f"Video extraction failed, falling back to original URL: {e}")

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
                try:
                    response = client.get(material_url)
                    response.raise_for_status()
                    if response.content:
                        meta.size_bytes = len(response.content)
                        return response.content, meta
                except Exception as e:
                    logger.warning(f"Direct download failed: {e}")

                # If direct download fails, try browser fallback
                if self.use_browser_fallback:
                    logger.info(f"Trying browser download for: {material_url}")
                    try:
                        content, ct = self._download_with_browser(material_url)
                        if content:
                            meta.size_bytes = len(content)
                            meta.content_type = ct
                            return content, meta
                    except Exception as browser_error:
                        logger.warning(f"Browser download also failed: {browser_error}")

                raise RuntimeError(
                    f"UPP material download failed for URL material {material_url}."
                )

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



