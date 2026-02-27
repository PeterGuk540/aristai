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
from urllib.parse import urljoin, urlparse, unquote

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
    download_url_patterns: list[str] = None  # URL patterns found in page scripts
    file_url_map: dict[str, str] | None = None  # data-id → actual file URL (from API intercept or preview click)
    file_title_map: dict[str, str] | None = None  # data-id → title (from API intercept)
    material_names: list[str] | None = None  # Clean titles from .file-material-name elements


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
        use_llm: bool = False,  # Disabled by default - use rule-based extraction
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
            logger.info(f"Chrome MCP: Using OpenAI API key: {api_key[:8]}...{api_key[-4:]}")
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
                materials = await self._analyze_with_llm(snapshot)
                llm_time = time.time() - start_time - snapshot_time
                logger.info(f"Chrome MCP: LLM analysis complete in {llm_time:.1f}s - found {len(materials)} materials")
            except Exception as e:
                logger.warning(f"Chrome MCP: LLM analysis failed ({e}), using rule-based fallback")
                materials = self._analyze_with_rules(snapshot)
                logger.info(f"Chrome MCP: Rule-based fallback found {len(materials)} materials")
        else:
            materials = self._analyze_with_rules(snapshot)
            logger.info(f"Chrome MCP: Rule-based extraction found {len(materials)} materials")

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

        Creates a new browser context, takes a snapshot, and closes the context.
        For multi-page extraction, use _take_snapshot_with_context instead.
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

        try:
            return await self._take_snapshot_with_context(context, page_url)
        finally:
            await context.close()

    async def _take_snapshot_with_context(self, context, page_url: str) -> PageSnapshot:
        """
        Navigate to page and take a structured snapshot, reusing an existing browser context.

        Collects:
        - Simplified DOM structure
        - All links with context
        - Iframes (often contain embedded PDFs)
        - File item patterns (divs with data-id, download buttons)
        - Network requests (video streams, file downloads)
        """
        page = await context.new_page()
        self.network_requests = []
        # Capture XHR/fetch response bodies for file URL extraction
        intercepted_responses: list[dict] = []

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

        async def on_response(response):
            """Capture XHR/fetch responses that may contain file URL data."""
            try:
                url_lower = response.url.lower()
                rtype = response.request.resource_type
                if rtype in ('fetch', 'xhr', 'document'):
                    # Capture responses from file management APIs
                    if any(kw in url_lower for kw in [
                        'listfile', 'getfile', 'filemanager', 'drive',
                        'material', 'archivo', 'preview',
                    ]):
                        try:
                            body = await response.text()
                            if body and len(body) < 50000:
                                intercepted_responses.append({
                                    'url': response.url, 'body': body,
                                })
                        except Exception:
                            pass
            except Exception:
                pass

        page.on("request", on_request)
        page.on("response", on_response)

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
            logger.info("Chrome MCP: Extracting page data via JavaScript...")

            # Extract page data via JavaScript (with timeout)
            import asyncio
            try:
                page_data = await asyncio.wait_for(
                    page.evaluate('''() => {
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

                // Extract ALL material name elements separately (UPP pattern)
                // These are independent divs like <div class="file-material-name">Title</div>
                const materialNames = [];
                document.querySelectorAll('.file-material-name, [class*="material-name"]').forEach(el => {
                    const name = el.textContent?.trim()?.substring(0, 150) || '';
                    if (name) materialNames.push(name);
                });

                return {
                    title: document.title,
                    simplifiedDOM: simplifyDOM(document.body).substring(0, 10000),
                    links: links.slice(0, 100),
                    iframes: iframes,
                    fileItems: fileItems.slice(0, 50),
                    materialNames: materialNames.slice(0, 50),
                };
            }'''),
                    timeout=10.0  # 10 second timeout for JS extraction
                )
                mat_names = page_data.get('materialNames', [])
                logger.info(f"Chrome MCP: Page data extracted - {len(page_data.get('links', []))} links, {len(page_data.get('iframes', []))} iframes, {len(mat_names)} materialNames")
            except asyncio.TimeoutError:
                logger.warning("Chrome MCP: JavaScript extraction timed out (10s), using empty data")
                page_data = {'title': '', 'links': [], 'iframes': [], 'fileItems': [], 'simplifiedDOM': '', 'materialNames': []}

            # Extract download URL patterns from page scripts
            # (e.g., the JS handler for data-action="preview" buttons)
            download_patterns = []
            try:
                download_patterns = await asyncio.wait_for(
                    page.evaluate('''() => {
                        const patterns = [];
                        const scripts = document.querySelectorAll('script');
                        for (const s of scripts) {
                            const t = s.textContent || '';
                            if (!t) continue;
                            // Look for URL strings containing download/file/preview endpoints
                            const matches = [...t.matchAll(
                                /['"`]((?:\\/|https?:\\/\\/)[^'"`\\n]{3,120}?(?:download|getFile|getfile|descargar|preview|archivo|fileManager\\/)[^'"`\\n]{0,80}?)['"`]/gi
                            )];
                            for (const m of matches) {
                                const url = m[1];
                                // Skip template literals and JS expressions
                                if (url.includes('${') || url.includes('function')) continue;
                                patterns.push(url);
                            }
                        }
                        return [...new Set(patterns)].slice(0, 20);
                    }'''),
                    timeout=3.0,
                )
                if download_patterns:
                    logger.info(f"Chrome MCP: Download URL patterns from scripts: {download_patterns}")
            except Exception:
                pass

            # --- Build file_url_map and file_title_map from intercepted API responses ---
            file_url_map: dict[str, str] = {}
            file_title_map: dict[str, str] = {}
            if intercepted_responses:
                logger.info(f"Chrome MCP: Processing {len(intercepted_responses)} intercepted API responses")
                for resp_data in intercepted_responses:
                    body = resp_data['body']
                    try:
                        json_data = json.loads(body)
                        items = json_data if isinstance(json_data, list) else [json_data]
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            # Try common field names for file ID and URL
                            fid = str(
                                item.get('id', '') or item.get('fileId', '')
                                or item.get('materialId', '') or item.get('material_id', '')
                            )
                            furl = (
                                item.get('fileUrl', '') or item.get('file_url', '')
                                or item.get('filePath', '') or item.get('path', '')
                                or item.get('url', '') or item.get('src', '')
                            )
                            if fid and furl and (
                                '/books/' in furl or '.pdf' in furl.lower()
                                or '.mp4' in furl.lower() or '/download' in furl.lower()
                            ):
                                file_url_map[fid] = furl
                            # Also capture title/name from the API response
                            if fid:
                                ftitle = str(
                                    item.get('title', '') or item.get('name', '')
                                    or item.get('label', '') or item.get('description', '')
                                    or item.get('materialName', '') or item.get('material_name', '')
                                ).strip()
                                if ftitle:
                                    file_title_map[fid] = ftitle[:150]
                    except (json.JSONDecodeError, TypeError):
                        # Try regex to find /books/...pdf URLs in non-JSON responses
                        pdf_urls = re.findall(r'/books/[^\s"\'<>]+\.(?:pdf|mp4|docx?)', body)
                        for pdf_url in pdf_urls:
                            key = f'__intercepted_{len(file_url_map)}'
                            file_url_map[key] = pdf_url

                if file_url_map:
                    logger.info(f"Chrome MCP: File URL map from API: {file_url_map}")
                if file_title_map:
                    logger.info(f"Chrome MCP: File title map from API: {file_title_map}")

            # --- Resolve file URLs for data-id items ---
            # Strategy: use download URL patterns from JS scripts first (instant),
            # only click preview buttons for the first 2 items as validation.
            file_items = page_data.get('fileItems', [])
            items_needing_urls = []
            for item in file_items:
                data_id = item.get('dataId', '')
                if not data_id or data_id in file_url_map:
                    continue
                item_text = (item.get('text', '') or '').strip()
                if item_text == '0' or 'enlace' in item_text.lower():
                    continue
                buttons = item.get('buttons') or []
                has_preview = any(
                    b.get('action') in ('preview', 'download') and b.get('id')
                    for b in buttons
                )
                if has_preview:
                    items_needing_urls.append(data_id)

            # First, try to construct download URLs from discovered JS patterns
            # This avoids expensive preview button clicks entirely
            pattern_resolved = 0
            if download_patterns and items_needing_urls:
                for data_id in items_needing_urls:
                    built_url = self._build_download_url(data_id, download_patterns, page_url)
                    if built_url:
                        file_url_map[data_id] = built_url
                        pattern_resolved += 1
                if pattern_resolved:
                    logger.info(f"Chrome MCP: Resolved {pattern_resolved}/{len(items_needing_urls)} URLs from JS patterns (no clicking needed)")
                # Remove resolved items
                items_needing_urls = [d for d in items_needing_urls if d not in file_url_map]

            # Only click preview for up to 2 remaining items (validation + fallback)
            if items_needing_urls:
                click_limit = 2
                logger.info(f"Chrome MCP: Clicking preview for {min(len(items_needing_urls), click_limit)}/{len(items_needing_urls)} remaining items")
                clicked_ok = 0
                for data_id in items_needing_urls[:click_limit]:
                    try:
                        btn = await page.query_selector(
                            f'button[data-action="preview"][data-id="{data_id}"]'
                        )
                        if not btn:
                            btn = await page.query_selector(
                                f'[data-id="{data_id}"] .file-material-name[data-action="preview"]'
                            )
                        if not btn:
                            continue

                        await btn.click()

                        try:
                            await page.wait_for_selector(
                                '#previewContent iframe[src], #filePreviewModal iframe[src]',
                                timeout=1500,
                            )
                        except Exception:
                            pass

                        iframe_src = await page.evaluate('''() => {
                            const iframe = document.querySelector(
                                '#previewContent iframe[src], #filePreviewModal iframe[src]'
                            );
                            return iframe ? iframe.src : null;
                        }''')

                        if iframe_src and (
                            '/books/' in iframe_src or iframe_src.lower().endswith('.pdf')
                            or iframe_src.lower().endswith('.mp4')
                            or '/download' in iframe_src.lower()
                        ):
                            file_url_map[data_id] = iframe_src
                            clicked_ok += 1
                            logger.info(
                                f"Chrome MCP: Preview click → data-id={data_id} → {iframe_src[:100]}"
                            )

                        # Close modal
                        close_btn = await page.query_selector(
                            '#filePreviewModal .btn-close, '
                            '#filePreviewModal [data-bs-dismiss="modal"]'
                        )
                        if close_btn:
                            await close_btn.click()
                            await page.wait_for_timeout(200)
                        else:
                            await page.keyboard.press('Escape')
                            await page.wait_for_timeout(200)

                    except Exception as e:
                        logger.debug(f"Chrome MCP: Preview click failed for data-id={data_id}: {e}")

                # If clicks succeeded but we still have unresolved items,
                # construct download URLs for remaining items using the page URL pattern
                remaining = [d for d in items_needing_urls if d not in file_url_map]
                if remaining and clicked_ok > 0:
                    # Construct download URL from the page's base URL
                    parsed = urlparse(page_url)
                    base_download = f"{parsed.scheme}://{parsed.netloc}/coordinador/fileManager/download.asp?id="
                    for data_id in remaining:
                        file_url_map[data_id] = base_download + data_id
                    logger.info(f"Chrome MCP: Constructed download URLs for {len(remaining)} remaining items")

            if file_url_map:
                logger.info(f"Chrome MCP: Final file_url_map has {len(file_url_map)} entries: {list(file_url_map.keys())}")

            js_material_names = page_data.get('materialNames', [])
            snapshot = PageSnapshot(
                url=page_url,
                title=page_data.get('title', ''),
                simplified_dom=page_data.get('simplifiedDOM', ''),
                links=page_data.get('links', []),
                iframes=page_data.get('iframes', []),
                file_items=page_data.get('fileItems', []),
                network_requests=list(self.network_requests),
                download_url_patterns=download_patterns,
                file_url_map=file_url_map if file_url_map else None,
                file_title_map=file_title_map if file_title_map else None,
                material_names=js_material_names if js_material_names else None,
            )

        finally:
            await page.close()

        return snapshot

    async def _discover_download_url_by_click(
        self, context, page_url: str, data_id: str
    ) -> str | None:
        """
        Click a preview/download button on the page and capture the resulting URL.

        This discovers the actual download URL pattern used by the site's JavaScript.
        """
        import asyncio
        page = await context.new_page()
        captured_urls: list[str] = []

        def on_request(request):
            url = request.url
            # Capture requests that contain the file ID
            if data_id in url and request.resource_type in ('document', 'fetch', 'xhr', 'other'):
                captured_urls.append(url)

        page.on("request", on_request)

        try:
            await page.goto(page_url, timeout=15000)
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # Find the preview/download button for this data-id
            selectors = [
                f'button[data-action="preview"][data-id="{data_id}"]',
                f'[data-action="preview"][data-id="{data_id}"]',
                f'[data-action="download"][data-id="{data_id}"]',
                f'button[data-id="{data_id}"]',
            ]
            btn = None
            for sel in selectors:
                btn = await page.query_selector(sel)
                if btn:
                    break

            if not btn:
                logger.info(f"Chrome MCP: No clickable button found for data-id={data_id}")
                return None

            # Click and capture: try popup first, then check network requests
            try:
                async with page.expect_popup(timeout=5000) as popup_info:
                    await btn.click()
                popup = await popup_info.value
                popup_url = popup.url
                logger.info(f"Chrome MCP: Preview button opened popup: {popup_url[:120]}")
                await popup.close()
                if data_id in popup_url:
                    return popup_url
            except Exception:
                # Not a popup — maybe a same-page action or download
                await btn.click()
                await page.wait_for_timeout(2000)

            # Check captured network requests
            if captured_urls:
                logger.info(f"Chrome MCP: Preview button triggered requests: {captured_urls[:3]}")
                return captured_urls[0]

            # Check if the page URL changed (navigation)
            current = page.url
            if data_id in current and current != page_url:
                logger.info(f"Chrome MCP: Preview button navigated to: {current[:120]}")
                return current

        except Exception as e:
            logger.warning(f"Chrome MCP: Download URL discovery failed: {e}")
        finally:
            await page.close()

        return None

    async def extract_materials_multi(self, page_urls: list[str]) -> list[ExtractedMaterial]:
        """
        Extract materials from multiple pages using a single browser context.

        This is more efficient than calling extract_materials() for each URL
        because it reuses the same authenticated browser context.

        Args:
            page_urls: List of URLs to extract materials from

        Returns:
            Deduplicated list of ExtractedMaterial objects from all pages
        """
        import time
        if not page_urls:
            return []

        start_time = time.time()
        logger.info(f"Chrome MCP extracting materials from {len(page_urls)} pages")

        browser = await _get_browser()
        context = await browser.new_context()

        # Set authentication cookies
        parsed_url = urlparse(self.base_url)
        cookie_list = [
            {"name": k, "value": v, "domain": parsed_url.netloc, "path": "/"}
            for k, v in self.cookies.items()
        ]
        await context.add_cookies(cookie_list)

        all_materials: list[ExtractedMaterial] = []
        # Download URL pattern discovered by clicking a preview button
        self._discovered_download_pattern: str | None = None

        try:
            for i, page_url in enumerate(page_urls):
                logger.info(f"Chrome MCP: Page {i+1}/{len(page_urls)}: {page_url[:80]}...")
                try:
                    snapshot = await self._take_snapshot_with_context(context, page_url)
                    logger.info(
                        f"Chrome MCP: Page {i+1} snapshot: {len(snapshot.links)} links, "
                        f"{len(snapshot.file_items)} file_items, {len(snapshot.iframes)} iframes"
                    )

                    # Log file_url_map if present (populated by _take_snapshot_with_context)
                    if snapshot.file_url_map:
                        logger.info(
                            f"Chrome MCP: Page {i+1} has file_url_map with {len(snapshot.file_url_map)} entries"
                        )

                    if self.use_llm:
                        try:
                            materials = await self._analyze_with_llm(snapshot)
                        except Exception as e:
                            logger.warning(f"Chrome MCP: LLM failed for {page_url} ({e}), using rules")
                            materials = self._analyze_with_rules(snapshot)
                    else:
                        materials = self._analyze_with_rules(snapshot)

                    # Add network-intercepted materials
                    for req in self.network_requests:
                        if self._is_downloadable_url(req['url']):
                            materials.append(ExtractedMaterial(
                                url=req['url'],
                                title=self._title_from_url(req['url']),
                                file_type=self._detect_file_type(req['url']),
                                confidence=0.9,
                                source='network',
                            ))

                    logger.info(f"Chrome MCP: Page {i+1} yielded {len(materials)} materials")
                    all_materials.extend(materials)
                except Exception as e:
                    logger.warning(f"Chrome MCP: Failed to extract from {page_url}: {e}")
                    continue
        finally:
            await context.close()

        # Deduplicate by URL, preferring entries with better titles
        seen: dict[str, ExtractedMaterial] = {}
        for m in all_materials:
            norm_url = m.url.rstrip('/')
            existing = seen.get(norm_url)
            if existing is None:
                seen[norm_url] = m
            else:
                new_looks_like_filename = bool(re.search(r'^[\w_-]+\.\w{2,5}$', m.title.strip()))
                old_looks_like_filename = bool(re.search(r'^[\w_-]+\.\w{2,5}$', existing.title.strip()))
                new_is_better = (
                    (not new_looks_like_filename and old_looks_like_filename)
                    or (new_looks_like_filename == old_looks_like_filename and len(m.title) > len(existing.title))
                )
                if new_is_better:
                    seen[norm_url] = m
        unique_materials = list(seen.values())

        total_time = time.time() - start_time
        logger.info(f"Chrome MCP: Multi-page extraction complete in {total_time:.1f}s - {len(unique_materials)} unique materials from {len(page_urls)} pages")
        return unique_materials

    async def _expand_all_sections(self, page):
        """Expand accordions, tabs, and collapsed sections to reveal content."""
        import asyncio
        try:
            # Quick expansion with timeout - max 1 second total
            async def expand_with_timeout():
                # Click on collapsed elements (limit to 3 to be fast)
                collapsed = await page.query_selector_all(
                    '[class*="collapse"]:not(.show), [class*="accordion"]:not(.active), '
                    '[aria-expanded="false"]'
                )
                clicked = 0
                for el in collapsed[:3]:
                    try:
                        await el.click()
                        await page.wait_for_timeout(50)
                        clicked += 1
                    except Exception:
                        pass
                if clicked:
                    logger.info(f"Chrome MCP: Expanded {clicked} sections")

            await asyncio.wait_for(expand_with_timeout(), timeout=1.0)
        except asyncio.TimeoutError:
            logger.info("Chrome MCP: Section expansion timed out (1s), continuing")
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
- For file items with data-id, use the download links found within the item element (not a generic API path)
- If no links are found in the item, look for download.asp or fileManager patterns in the page URL
- For iframes with PDF src, use the iframe src directly
- Include ONLY actual downloadable content, not portal pages
- NEVER include URLs containing template literals like ${{...}}, escapeHtml, or encodeURI

Return ONLY the JSON array, no other text."""

        try:
            import asyncio
            import concurrent.futures

            # Run blocking OpenAI call in thread pool to allow timeout
            def call_openai():
                logger.info("Chrome MCP: Starting OpenAI API call...")
                try:
                    result = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a web scraping expert that identifies downloadable educational materials from web pages. Return only valid JSON."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                        max_tokens=2000,
                        timeout=15.0,  # OpenAI SDK timeout
                    )
                    logger.info("Chrome MCP: OpenAI API call completed")
                    return result
                except Exception as e:
                    logger.error(f"Chrome MCP: OpenAI API error in thread: {type(e).__name__}: {e}")
                    raise

            logger.info("Chrome MCP: Submitting OpenAI call to thread pool...")
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                response = await asyncio.wait_for(
                    loop.run_in_executor(executor, call_openai),
                    timeout=20.0  # Overall timeout
                )
            logger.info("Chrome MCP: Thread pool execution completed")

            result_text = response.choices[0].message.content.strip()
            logger.info(f"Chrome MCP: OpenAI response received ({len(result_text)} chars)")

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
            logger.warning(f"Chrome MCP: LLM returned invalid JSON: {e}")
            return []
        except asyncio.TimeoutError:
            logger.warning("Chrome MCP: OpenAI API call timed out (20s)")
            raise
        except Exception as e:
            import traceback
            logger.error(f"Chrome MCP: LLM analysis error: {type(e).__name__}: {e}")
            logger.debug(f"Chrome MCP: Full traceback: {traceback.format_exc()}")
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

        # Build a mapping from data-id items to material names.
        # material_names are extracted separately from .file-material-name divs
        # and correspond 1:1 (in page order) with file items that have
        # data-id AND preview/download buttons (the actual file entries).
        real_file_items = [
            item for item in snapshot.file_items
            if item.get('dataId') and any(
                b.get('action') in ('preview', 'download') and b.get('id')
                for b in (item.get('buttons') or [])
            )
        ]
        page_material_names = snapshot.material_names or []
        dataid_to_name: dict[str, str] = {}
        if page_material_names:
            for idx, item in enumerate(real_file_items):
                if idx < len(page_material_names):
                    dataid_to_name[item['dataId']] = page_material_names[idx]
            logger.info(
                f"Chrome MCP: Mapped {len(dataid_to_name)} material names to "
                f"{len(real_file_items)} real file items (from {len(page_material_names)} names)"
            )

        # Extract from file items with data-id
        for item in snapshot.file_items:
            data_id = item.get('dataId', '')
            if not data_id:
                continue

            item_text = (item.get('text', '') or '').strip()
            # Title priority: page material name > API-intercepted title > concatenated textContent
            page_name = dataid_to_name.get(data_id, '')
            api_title = (snapshot.file_title_map or {}).get(data_id, '')
            item_title = page_name or api_title or item_text[:100]

            # Skip non-file entries: "0" placeholder text or "Enlace" (link-type entries)
            if item_text == '0' or 'enlace' in item_text.lower():
                continue

            # Prefer actual file links found within the file item element
            # Filter out portal/navigation ASP pages — only keep real file URLs
            item_links = [
                l for l in (item.get('links') or [])
                if self._is_downloadable_url(l) and not self._is_portal_page(l)
            ]
            if item_links:
                for link_url in item_links:
                    materials.append(ExtractedMaterial(
                        url=link_url,
                        title=item_title or self._title_from_url(link_url),
                        file_type=self._detect_file_type(link_url),
                        confidence=0.85,
                        source='data-id',
                    ))
            else:
                # No <a href> links — check for preview/download buttons
                buttons = item.get('buttons') or []
                has_preview = any(
                    b.get('action') in ('preview', 'download') and b.get('id')
                    for b in buttons
                )
                if has_preview and item_text:
                    # 1) Check file_url_map first (from API intercept or preview click)
                    if snapshot.file_url_map and data_id in snapshot.file_url_map:
                        file_url = snapshot.file_url_map[data_id]
                        if not file_url.startswith('http'):
                            file_url = urljoin(snapshot.url, file_url)
                        materials.append(ExtractedMaterial(
                            url=file_url,
                            title=item_title,
                            file_type=self._detect_file_type(file_url),
                            confidence=0.95,
                            source='preview-extract',
                        ))
                    else:
                        # 2) Fallback: try download URL pattern from page scripts
                        download_url = self._build_download_url(
                            data_id, snapshot.download_url_patterns, snapshot.url
                        )
                        if download_url:
                            materials.append(ExtractedMaterial(
                                url=download_url,
                                title=item_title,
                                file_type=self._detect_file_type(item_text),
                                confidence=0.75,
                                source='data-id',
                            ))
                        else:
                            logger.debug(f"Chrome MCP: Skipping data-id={data_id}, no URL found in file_url_map or patterns")

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

        # Post-filter: remove any materials with invalid/template URLs
        materials = [m for m in materials if self._is_downloadable_url(m.url)]

        # Deduplicate by URL, preferring entries with better (non-URL-derived) titles
        seen: dict[str, ExtractedMaterial] = {}
        for m in materials:
            norm_url = m.url.rstrip('/')
            existing = seen.get(norm_url)
            if existing is None:
                seen[norm_url] = m
            else:
                # Keep the entry with the better title:
                # A "good" title is longer and doesn't look like a filename
                new_looks_like_filename = bool(re.search(r'^[\w_-]+\.\w{2,5}$', m.title.strip()))
                old_looks_like_filename = bool(re.search(r'^[\w_-]+\.\w{2,5}$', existing.title.strip()))
                new_is_better = (
                    (not new_looks_like_filename and old_looks_like_filename)
                    or (new_looks_like_filename == old_looks_like_filename and len(m.title) > len(existing.title))
                )
                if new_is_better:
                    seen[norm_url] = m
        materials = list(seen.values())

        return materials

    def _build_download_url(
        self, data_id: str, patterns: list[str] | None, page_url: str
    ) -> str | None:
        """
        Build a download URL for a data-id item using patterns discovered from
        the page's JavaScript.

        Args:
            data_id: The file ID from the data-id attribute
            patterns: URL patterns found in page scripts
            page_url: The page URL for context

        Returns:
            A download URL, or None if no suitable pattern found
        """
        if patterns:
            for pattern in patterns:
                pattern_lower = pattern.lower()
                # Look for patterns that take an id parameter
                if 'id=' in pattern_lower or '{id}' in pattern_lower:
                    # Replace placeholder or append id
                    if '{id}' in pattern:
                        url = pattern.replace('{id}', data_id)
                    elif pattern.endswith('id='):
                        url = pattern + data_id
                    elif 'id=' in pattern:
                        # Pattern already has an id value — replace it
                        url = re.sub(r'id=[^&]*', f'id={data_id}', pattern)
                    else:
                        continue

                    # Resolve relative URLs
                    if not url.startswith('http'):
                        url = urljoin(self.base_url + '/', url)
                    return url

                # Patterns like /path/to/download/ followed by id
                if pattern.endswith('/'):
                    url = pattern + data_id
                    if not url.startswith('http'):
                        url = urljoin(self.base_url + '/', url)
                    return url

        # No pattern found — don't guess, return None
        return None

    @staticmethod
    def _is_valid_material_url(url: str) -> bool:
        """Check if URL is a valid material URL."""
        if not url:
            return False

        # Reject unresolved JS template literals and template engine patterns
        decoded_url = unquote(url)
        if any(pat in decoded_url for pat in ('${', '{%', '{{', 'escapeHtml', 'encodeURI')):
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

        # Skip URLs containing unresolved JavaScript template strings
        # e.g., "${escapeHtml(file.fileUrl)}" or "${variable}"
        # Also check URL-decoded version in case special chars are encoded
        decoded_url = unquote(url)
        if '${' in decoded_url or '{%' in decoded_url or '{{' in decoded_url:
            return False
        # Also skip URLs containing literal JS function names (common template patterns)
        if 'escapeHtml' in decoded_url or 'encodeURI' in decoded_url:
            return False

        url_lower = url.lower()

        # Direct file extensions
        if re.search(r'\.(pdf|docx?|pptx?|xlsx?|csv|txt|zip|rar|'
                     r'mp4|mp3|m3u8|mpd|webm|avi|mov|wav|ogg)(\?|$)', url_lower):
            return True

        # Download-related URL patterns
        download_patterns = [
            r'/download', r'/files?/', r'/material', r'/archivo',
            r'/recurso', r'/attachment', r'/content/', r'/books/',
            r'[?&](download|file)=',
        ]
        return any(re.search(p, url_lower) for p in download_patterns)

    @staticmethod
    def _is_portal_page(url: str) -> bool:
        """Check if URL is a portal/navigation page, not actual content."""
        url_lower = url.lower()

        # ASP/PHP/HTML pages are portal pages by default
        if re.search(r'\.(asp|aspx|php|html?)(\?|$)', url_lower):
            # Exception: known download endpoints ARE content
            if re.search(r'download\.asp|getfile\.asp|archivo\.asp', url_lower):
                return False
            # Exception: pages with explicit download/file params
            if re.search(r'[?&](download|file|archivo)=', url_lower):
                return False
            # All other ASP/PHP pages are portal/navigation pages
            return True

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
    use_llm: bool = False,  # Disabled by default - use rule-based extraction
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


async def extract_materials_from_pages(
    page_urls: list[str],
    cookies: dict[str, str],
    base_url: str,
    timeout: float = 30.0,
    use_llm: bool = False,
) -> list[ExtractedMaterial]:
    """
    Extract materials from multiple pages using a single browser context.

    More efficient than calling extract_materials_universal for each URL.

    Args:
        page_urls: List of URLs to extract from
        cookies: Authentication cookies
        base_url: Base URL of the site
        timeout: Page load timeout
        use_llm: Whether to use LLM (True) or rule-based extraction (False)

    Returns:
        Deduplicated list of ExtractedMaterial objects from all pages
    """
    client = ChromeMCPClient(
        cookies=cookies,
        base_url=base_url,
        timeout=timeout,
        use_llm=use_llm,
    )
    return await client.extract_materials_multi(page_urls)


async def close_chrome_mcp():
    """Close the browser instance (call on shutdown)."""
    await _close_browser()
