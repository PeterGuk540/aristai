"""
Chrome MCP-style Universal Browser Client.

This module provides LLM-driven browser automation for universal file extraction.
Instead of hardcoded regex patterns, it uses an LLM to analyze page structure
and identify downloadable materials - working for any website structure.

Architecture:
    1. Playwright provides browser control (navigation, DOM access, screenshots)
    2. LLM analyzes the page structure and identifies materials
    3. Universal extraction works without site-specific patterns

This follows Chrome MCP principles where an AI model interprets the page
rather than relying on brittle CSS selectors or regex patterns.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger(__name__)

# Lazy imports to avoid startup overhead
_playwright = None
_browser = None


async def _get_browser():
    """Get or create a shared browser instance."""
    global _playwright, _browser
    if _browser is None:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        )
        logger.info("Chrome MCP browser instance created")
    return _browser


async def _close_browser():
    """Close browser instance (call on shutdown)."""
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None


@dataclass
class ExtractedMaterial:
    """A material identified by the LLM analyzer."""
    url: str
    title: str
    file_type: str  # pdf, video, document, etc.
    confidence: float  # 0.0 to 1.0
    source: str  # How it was found: 'link', 'iframe', 'onclick', 'network'


@dataclass
class PageSnapshot:
    """A structured snapshot of the page for LLM analysis."""
    url: str
    title: str
    simplified_dom: str
    links: list[dict]
    iframes: list[dict]
    file_items: list[dict]
    network_requests: list[dict]


class ChromeMCPClient:
    """
    Chrome MCP-style browser client for universal material extraction.

    Uses Playwright for browser control and LLM for intelligent page analysis.
    This approach is UNIVERSAL - it doesn't rely on site-specific patterns.
    """

    def __init__(
        self,
        cookies: dict[str, str],
        base_url: str,
        timeout: float = 30.0,
        use_llm: bool = True,
    ):
        """
        Initialize the Chrome MCP client.

        Args:
            cookies: Authentication cookies
            base_url: Base URL for the target site
            timeout: Page load timeout in seconds
            use_llm: Whether to use LLM for analysis (True) or fallback rules (False)
        """
        self.cookies = cookies
        self.base_url = base_url
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self.use_llm = use_llm
        self.network_requests: list[dict] = []
        self._openai_client = None

    def _get_openai_client(self):
        """Lazy-load OpenAI client."""
        if self._openai_client is None:
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is required for LLM-based material extraction")
            self._openai_client = openai.OpenAI(api_key=api_key)
        return self._openai_client

    async def extract_materials(self, page_url: str) -> list[ExtractedMaterial]:
        """
        Universal material extraction using LLM analysis.

        This is the main entry point. It:
        1. Navigates to the page
        2. Takes a structured DOM snapshot
        3. Uses LLM to analyze and identify materials
        4. Returns extracted materials

        Args:
            page_url: URL of the page to extract materials from

        Returns:
            List of ExtractedMaterial objects
        """
        import time
        start_time = time.time()
        logger.info(f"Chrome MCP extracting materials from: {page_url}")

        # Step 1: Get page snapshot
        logger.info("Chrome MCP: Taking page snapshot...")
        snapshot = await self._take_snapshot(page_url)
        snapshot_time = time.time() - start_time
        logger.info(f"Chrome MCP: Snapshot complete in {snapshot_time:.1f}s - found {len(snapshot.links)} links, {len(snapshot.iframes)} iframes, {len(snapshot.file_items)} file items")

        # Step 2: Analyze with LLM (with timeout protection)
        materials = []
        if self.use_llm:
            try:
                logger.info("Chrome MCP: Analyzing with LLM...")
                import asyncio
                # Timeout LLM analysis to 20 seconds max
                materials = await asyncio.wait_for(
                    self._analyze_with_llm(snapshot),
                    timeout=20.0
                )
                llm_time = time.time() - start_time - snapshot_time
                logger.info(f"Chrome MCP: LLM analysis complete in {llm_time:.1f}s - found {len(materials)} materials")
            except asyncio.TimeoutError:
                logger.warning("Chrome MCP: LLM analysis timed out, using rule-based fallback")
                materials = self._analyze_with_rules(snapshot)
            except Exception as e:
                logger.warning(f"Chrome MCP: LLM analysis failed ({e}), using rule-based fallback")
                materials = self._analyze_with_rules(snapshot)
        else:
            materials = self._analyze_with_rules(snapshot)

        # Step 3: Add network-intercepted materials
        for req in self.network_requests:
            if self._is_downloadable_url(req['url']):
                materials.append(ExtractedMaterial(
                    url=req['url'],
                    title=self._title_from_url(req['url']),
                    file_type=self._detect_file_type(req['url']),
                    confidence=0.9,
                    source='network',
                ))

        # Deduplicate by URL
        seen_urls = set()
        unique_materials = []
        for m in materials:
            if m.url not in seen_urls:
                seen_urls.add(m.url)
                unique_materials.append(m)

        total_time = time.time() - start_time
        logger.info(f"Chrome MCP: Extraction complete in {total_time:.1f}s - {len(unique_materials)} unique materials")
        return unique_materials

    async def _take_snapshot(self, page_url: str) -> PageSnapshot:
        """
        Navigate to page and take a structured snapshot for LLM analysis.

        Collects:
        - Simplified DOM structure
        - All links with context
        - Iframes (often contain embedded PDFs)
        - File item patterns (divs with data-id, download buttons)
        - Network requests (video streams, file downloads)
        """
        browser = await _get_browser()
        context = await browser.new_context()

        # Set authentication cookies
        parsed_url = urlparse(self.base_url)
        cookie_list = [
            {"name": k, "value": v, "domain": parsed_url.netloc, "path": "/"}
            for k, v in self.cookies.items()
        ]
        logger.info(f"Chrome MCP: Setting {len(cookie_list)} cookies for {parsed_url.netloc}")
        await context.add_cookies(cookie_list)

        page = await context.new_page()
        self.network_requests = []

        # Intercept network requests for video/file detection
        def on_request(request):
            url = request.url
            resource_type = request.resource_type
            if resource_type in ('media', 'fetch', 'xhr') or \
               any(ext in url.lower() for ext in ['.m3u8', '.mpd', '.mp4', '.pdf']):
                self.network_requests.append({
                    'url': url,
                    'type': resource_type,
                })

        page.on("request", on_request)

        try:
            # Use shorter timeout for initial load (15 seconds)
            load_timeout = min(self.timeout, 15000)
            logger.info(f"Chrome MCP: Navigating to {page_url[:80]}...")
            await page.goto(page_url, timeout=load_timeout)
            current_url = page.url
            logger.info(f"Chrome MCP: Page loaded, current URL: {current_url[:80]}...")

            # Check if redirected to login page
            if 'login' in current_url.lower() or 'usuariodued' in current_url.lower():
                logger.warning(f"Chrome MCP: Redirected to login page! Cookies may not be working.")

            logger.info("Chrome MCP: Waiting for network idle...")

            # Wait for network idle with shorter timeout (5 seconds - reduced)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
                logger.info("Chrome MCP: Network idle reached")
            except Exception:
                logger.info("Chrome MCP: Network idle timeout (5s), continuing with available content")

            # Expand accordions and collapsed sections
            logger.info("Chrome MCP: Expanding collapsed sections...")
            await self._expand_all_sections(page)
            logger.info("Chrome MCP: Extracting page data...")

            # Extract page data via JavaScript
            page_data = await page.evaluate('''() => {
                // Simplified DOM: keep structure but remove noise
                function simplifyDOM(element, depth = 0) {
                    if (depth > 5) return '';
                    const tag = element.tagName?.toLowerCase() || '';
                    if (['script', 'style', 'noscript', 'meta', 'link'].includes(tag)) return '';

                    let result = '';
                    const classes = element.className?.toString?.() || '';
                    const id = element.id || '';
                    const text = element.childNodes.length === 1 && element.childNodes[0].nodeType === 3
                        ? element.textContent?.trim().substring(0, 100) : '';

                    // Only include elements with interesting attributes
                    if (tag === 'a' || tag === 'button' || tag === 'iframe' ||
                        classes.includes('file') || classes.includes('download') ||
                        classes.includes('material') || element.dataset?.id) {
                        result += `<${tag}`;
                        if (id) result += ` id="${id}"`;
                        if (classes) result += ` class="${classes.substring(0, 50)}"`;
                        if (element.href) result += ` href="${element.href}"`;
                        if (element.src) result += ` src="${element.src}"`;
                        if (element.dataset?.id) result += ` data-id="${element.dataset.id}"`;
                        if (element.onclick) result += ` onclick="..."`;
                        result += '>';
                        if (text) result += text;
                    }

                    for (const child of element.children || []) {
                        result += simplifyDOM(child, depth + 1);
                    }

                    if (tag === 'a' || tag === 'button' || tag === 'iframe') {
                        result += `</${tag}>`;
                    }
                    return result;
                }

                // Extract all links with context
                const links = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href || a.getAttribute('href') || '';
                    const text = a.textContent?.trim() || '';
                    const parentText = a.parentElement?.textContent?.trim()?.substring(0, 200) || '';
                    const onclick = a.getAttribute('onclick') || '';
                    const classes = a.className?.toString?.() || '';
                    const dataId = a.dataset?.id || a.closest('[data-id]')?.dataset?.id || '';

                    links.push({
                        href: href,
                        text: text.substring(0, 100),
                        context: parentText.substring(0, 200),
                        onclick: onclick.substring(0, 200),
                        classes: classes,
                        dataId: dataId,
                    });
                });

                // Extract iframes (often contain embedded PDFs)
                const iframes = [];
                document.querySelectorAll('iframe[src]').forEach(iframe => {
                    iframes.push({
                        src: iframe.src,
                        title: iframe.title || '',
                    });
                });

                // Extract file-like items (common LMS pattern)
                const fileItems = [];
                document.querySelectorAll('[class*="file"], [class*="material"], [class*="download"], [data-id]').forEach(el => {
                    const dataId = el.dataset?.id || '';
                    const text = el.textContent?.trim()?.substring(0, 200) || '';
                    const links = Array.from(el.querySelectorAll('a[href]')).map(a => a.href);
                    const buttons = Array.from(el.querySelectorAll('button[data-action], button[onclick]')).map(b => ({
                        action: b.dataset?.action || '',
                        id: b.dataset?.id || '',
                        onclick: b.getAttribute('onclick')?.substring(0, 100) || '',
                    }));

                    if (dataId || links.length > 0 || buttons.length > 0) {
                        fileItems.push({
                            dataId: dataId,
                            text: text,
                            links: links,
                            buttons: buttons,
                        });
                    }
                });

                return {
                    title: document.title,
                    simplifiedDOM: simplifyDOM(document.body).substring(0, 10000),
                    links: links.slice(0, 100),
                    iframes: iframes,
                    fileItems: fileItems.slice(0, 50),
                };
            }''')

            snapshot = PageSnapshot(
                url=page_url,
                title=page_data.get('title', ''),
                simplified_dom=page_data.get('simplifiedDOM', ''),
                links=page_data.get('links', []),
                iframes=page_data.get('iframes', []),
                file_items=page_data.get('fileItems', []),
                network_requests=list(self.network_requests),
            )

        finally:
            await page.close()
            await context.close()

        return snapshot

    async def _expand_all_sections(self, page):
        """Expand accordions, tabs, and collapsed sections to reveal content."""
        try:
            # Click on collapsed elements
            collapsed = await page.query_selector_all(
                '[class*="collapse"]:not(.show), [class*="accordion"]:not(.active), '
                '[aria-expanded="false"], [class*="closed"], [class*="hidden-content"]'
            )
            for el in collapsed[:20]:  # Limit to prevent infinite loops
                try:
                    await el.click()
                    await page.wait_for_timeout(200)
                except Exception:
                    pass

            # Click "show more" buttons
            show_more = await page.query_selector_all(
                'button:has-text("more"), a:has-text("more"), [class*="show-more"]'
            )
            for btn in show_more[:10]:
                try:
                    await btn.click()
                    await page.wait_for_timeout(200)
                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Section expansion failed: {e}")

    async def _analyze_with_llm(self, snapshot: PageSnapshot) -> list[ExtractedMaterial]:
        """
        Use LLM to analyze page snapshot and identify downloadable materials.

        This is the UNIVERSAL approach - the LLM understands page structure
        without relying on hardcoded patterns.
        """
        client = self._get_openai_client()

        # Prepare context for LLM
        context = {
            "page_url": snapshot.url,
            "page_title": snapshot.title,
            "links_sample": snapshot.links[:50],  # Top 50 links
            "iframes": snapshot.iframes,
            "file_items": snapshot.file_items[:30],
            "network_requests": snapshot.network_requests[:20],
        }

        prompt = f"""Analyze this web page snapshot and identify ALL downloadable educational materials.

PAGE DATA:
```json
{json.dumps(context, indent=2, ensure_ascii=False)}
```

TASK:
Identify all downloadable files (PDFs, videos, documents, presentations, etc.) on this page.
Look for:
1. Direct file links (.pdf, .docx, .pptx, .mp4, etc.)
2. Embedded content in iframes (especially PDFs)
3. Download buttons with data-id attributes
4. Links with "download", "archivo", "material" in URL
5. Video streams (.m3u8, .mpd URLs)
6. onclick handlers that trigger downloads

DO NOT include:
- Navigation links (home, menu, profile, logout)
- ASP/PHP pages that are just portals (unless they have download parameters)
- JavaScript void links
- Authentication/login links

Return a JSON array of materials found:
```json
[
  {{
    "url": "https://example.com/file.pdf",
    "title": "Lecture Notes Week 1",
    "file_type": "pdf",
    "confidence": 0.95,
    "source": "link"
  }}
]
```

IMPORTANT:
- For file items with data-id, construct download URL as: /api/materials/{{data-id}}/download
- For iframes with PDF src, use the iframe src directly
- Include ONLY actual downloadable content, not portal pages

Return ONLY the JSON array, no other text."""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a web scraping expert that identifies downloadable educational materials from web pages. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', result_text)
            if json_match:
                materials_data = json.loads(json_match.group())
            else:
                materials_data = json.loads(result_text)

            materials = []
            for m in materials_data:
                url = m.get('url', '')
                if url and self._is_valid_material_url(url):
                    # Resolve relative URLs
                    if not url.startswith('http'):
                        url = urljoin(snapshot.url, url)

                    materials.append(ExtractedMaterial(
                        url=url,
                        title=m.get('title', self._title_from_url(url)),
                        file_type=m.get('file_type', self._detect_file_type(url)),
                        confidence=float(m.get('confidence', 0.8)),
                        source=m.get('source', 'llm'),
                    ))

            logger.info(f"LLM identified {len(materials)} materials")
            return materials

        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"LLM analysis error: {e}")
            raise

    def _analyze_with_rules(self, snapshot: PageSnapshot) -> list[ExtractedMaterial]:
        """
        Rule-based fallback when LLM is unavailable.

        Uses intelligent heuristics but less accurate than LLM.
        """
        materials = []

        # Extract from iframes (often contain embedded PDFs)
        for iframe in snapshot.iframes:
            src = iframe.get('src', '')
            if self._is_downloadable_url(src):
                materials.append(ExtractedMaterial(
                    url=src,
                    title=iframe.get('title', '') or self._title_from_url(src),
                    file_type=self._detect_file_type(src),
                    confidence=0.9,
                    source='iframe',
                ))

        # Extract from file items with data-id
        for item in snapshot.file_items:
            data_id = item.get('dataId', '')
            if data_id:
                # Construct download URL pattern
                url = f"{self.base_url}/api/materials/{data_id}/download"
                materials.append(ExtractedMaterial(
                    url=url,
                    title=item.get('text', '')[:100] or f"Material {data_id}",
                    file_type='unknown',
                    confidence=0.7,
                    source='data-id',
                ))

        # Extract from links
        for link in snapshot.links:
            href = link.get('href', '')
            if self._is_downloadable_url(href):
                # Skip if it's a navigation/portal page
                if self._is_portal_page(href):
                    continue

                materials.append(ExtractedMaterial(
                    url=href,
                    title=link.get('text', '') or self._title_from_url(href),
                    file_type=self._detect_file_type(href),
                    confidence=0.8,
                    source='link',
                ))

        return materials

    @staticmethod
    def _is_valid_material_url(url: str) -> bool:
        """Check if URL is a valid material URL."""
        if not url:
            return False
        url_lower = url.lower()

        # Skip invalid URLs
        skip_patterns = ['javascript:', 'mailto:', 'tel:', '#', 'void(0)']
        return not any(p in url_lower for p in skip_patterns)

    @staticmethod
    def _is_downloadable_url(url: str) -> bool:
        """Check if URL looks like downloadable content."""
        if not url:
            return False
        url_lower = url.lower()

        # Direct file extensions
        if re.search(r'\.(pdf|docx?|pptx?|xlsx?|csv|txt|zip|rar|'
                     r'mp4|mp3|m3u8|mpd|webm|avi|mov|wav|ogg)(\?|$)', url_lower):
            return True

        # Download-related URL patterns
        download_patterns = [
            r'/download', r'/file', r'/material', r'/archivo',
            r'/recurso', r'/attachment', r'/content', r'/books/',
            r'[?&](download|file|id)=',
        ]
        return any(re.search(p, url_lower) for p in download_patterns)

    @staticmethod
    def _is_portal_page(url: str) -> bool:
        """Check if URL is a portal/navigation page, not actual content."""
        url_lower = url.lower()

        # ASP/PHP pages without download parameters are usually portals
        if re.search(r'\.(asp|aspx|php|html?)(\?|$)', url_lower):
            # Unless they have download-related parameters
            if re.search(r'[?&](download|file|archivo|content|id)=', url_lower):
                return False
            # Common portal page names
            portal_names = [
                'index', 'home', 'login', 'logout', 'menu', 'nav',
                'recordedclasses', 'onlineclasses', 'educationalcontent',
                'courses', 'syllabus', 'materials',
            ]
            return any(p in url_lower for p in portal_names)

        return False

    @staticmethod
    def _detect_file_type(url: str) -> str:
        """Detect file type from URL."""
        url_lower = url.lower()
        type_map = {
            '.pdf': 'pdf',
            '.doc': 'document', '.docx': 'document',
            '.ppt': 'presentation', '.pptx': 'presentation',
            '.xls': 'spreadsheet', '.xlsx': 'spreadsheet',
            '.mp4': 'video', '.m3u8': 'video', '.mpd': 'video',
            '.mp3': 'audio', '.wav': 'audio',
            '.zip': 'archive', '.rar': 'archive',
        }
        for ext, file_type in type_map.items():
            if ext in url_lower:
                return file_type
        return 'unknown'

    @staticmethod
    def _title_from_url(url: str) -> str:
        """Extract a readable title from URL."""
        # Get filename from URL
        filename = url.rsplit('/', 1)[-1].split('?')[0]
        # Remove extension
        name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        # Clean up
        name = re.sub(r'[_-]+', ' ', name)
        name = re.sub(r'%20', ' ', name)
        return name[:100] if name else 'Material'


# Module-level functions for easy access

async def extract_materials_universal(
    page_url: str,
    cookies: dict[str, str],
    base_url: str,
    timeout: float = 30.0,
    use_llm: bool = True,
) -> list[ExtractedMaterial]:
    """
    Universal material extraction using Chrome MCP approach.

    This is the main API for extracting materials from any web page.
    It uses LLM analysis for universal compatibility.

    Args:
        page_url: URL of the page to extract from
        cookies: Authentication cookies
        base_url: Base URL of the site
        timeout: Page load timeout
        use_llm: Whether to use LLM (True) or rule-based extraction (False)

    Returns:
        List of ExtractedMaterial objects
    """
    client = ChromeMCPClient(
        cookies=cookies,
        base_url=base_url,
        timeout=timeout,
        use_llm=use_llm,
    )
    return await client.extract_materials(page_url)


async def close_chrome_mcp():
    """Close the browser instance (call on shutdown)."""
    await _close_browser()
