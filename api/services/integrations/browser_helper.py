"""
Browser automation helper using Playwright.

Provides fallback for JavaScript-rendered content and video extraction
for LMS integrations that require browser automation.
"""

import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Lazy-loaded browser instances (avoid startup overhead)
_playwright = None
_browser = None


async def get_browser():
    """
    Get or create a shared browser instance.

    Uses lazy initialization to avoid startup overhead when browser
    automation is not needed.
    """
    global _playwright, _browser
    if _browser is None:
        from playwright.async_api import async_playwright
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']  # For EC2/Docker
        )
        logger.info("Playwright browser instance created")
    return _browser


async def close_browser():
    """
    Close browser instance.

    Call this on application shutdown to clean up resources.
    """
    global _playwright, _browser
    if _browser:
        await _browser.close()
        _browser = None
        logger.info("Playwright browser closed")
    if _playwright:
        await _playwright.stop()
        _playwright = None


class BrowserMaterialFetcher:
    """
    Fetch materials from UPP using browser automation.

    Handles JavaScript-rendered content and video extraction that
    cannot be handled by static HTML scraping.
    """

    def __init__(self, cookies: dict[str, str], timeout: float = 30.0):
        """
        Initialize the material fetcher.

        Args:
            cookies: Login cookies for authentication
            timeout: Page load timeout in seconds
        """
        self.cookies = cookies
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self.intercepted_urls: list[dict] = []

    async def fetch_materials_from_page(
        self,
        course_url: str,
        base_url: str,
    ) -> list[dict[str, Any]]:
        """
        Navigate to course page and extract all material links.

        Handles JavaScript-rendered content by:
        1. Waiting for network idle
        2. Expanding accordions/collapsed sections
        3. Intercepting video stream requests
        4. Extracting links from rendered DOM

        Args:
            course_url: URL of the course materials page
            base_url: Base URL for resolving relative links

        Returns:
            List of material dictionaries with url, title, type
        """
        browser = await get_browser()
        context = await browser.new_context()

        # Set cookies from login
        parsed_url = urlparse(base_url)
        cookie_list = [
            {"name": k, "value": v, "domain": parsed_url.netloc, "path": "/"}
            for k, v in self.cookies.items()
        ]
        await context.add_cookies(cookie_list)

        page = await context.new_page()
        materials = []

        try:
            # Intercept network requests to catch video streams
            page.on("request", lambda req: self._on_request(req))
            page.on("response", lambda res: self._on_response(res))

            # Navigate and wait for content
            logger.info(f"Browser navigating to: {course_url}")
            await page.goto(course_url, timeout=self.timeout)
            await page.wait_for_load_state("networkidle", timeout=self.timeout)

            # Wait for dynamic content (Semanas, accordions, etc.)
            await self._expand_accordions(page)
            await self._wait_for_materials(page)

            # Extract material links from DOM
            materials = await self._extract_material_links(page, base_url)
            logger.info(f"Browser extracted {len(materials)} materials from DOM")

            # Add intercepted video URLs
            video_materials = self._get_intercepted_videos()
            logger.info(f"Browser intercepted {len(video_materials)} video streams")
            materials.extend(video_materials)

        except Exception as e:
            logger.warning(f"Browser material fetch failed: {e}")
        finally:
            await page.close()
            await context.close()

        return materials

    async def _expand_accordions(self, page):
        """Click on collapsed sections to reveal content."""
        try:
            # Common accordion patterns in UPP and other LMS
            accordions = await page.query_selector_all(
                '[class*="accordion"], [class*="collapse"], [class*="semana"], '
                '[class*="Semana"], [data-toggle="collapse"], [onclick*="toggle"], '
                '[class*="expandable"], [class*="collapsible"]'
            )
            for accordion in accordions[:20]:  # Limit to prevent infinite loops
                try:
                    # Check if it's not already expanded
                    is_collapsed = await accordion.evaluate(
                        '(el) => el.classList.contains("collapsed") || '
                        'el.getAttribute("aria-expanded") === "false"'
                    )
                    if is_collapsed:
                        await accordion.click()
                        await page.wait_for_timeout(300)  # Brief pause for animation
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Accordion expansion failed: {e}")

    async def _wait_for_materials(self, page):
        """Wait for material links to appear in the DOM."""
        try:
            # Wait for common material link patterns
            await page.wait_for_selector(
                'a[href*=".pdf"], a[href*=".docx"], a[href*=".mp4"], '
                'a[href*="download"], a[href*="material"], a[href*="archivo"], '
                'a[href*="recurso"], a[href*="file"]',
                timeout=5000
            )
        except Exception:
            pass  # Continue even if selector times out

    async def _extract_material_links(self, page, base_url: str) -> list[dict]:
        """Extract all material links from the page DOM."""
        materials = []

        # Get all links via JavaScript evaluation
        links = await page.evaluate('''() => {
            const links = [];
            document.querySelectorAll('a[href]').forEach(a => {
                links.push({
                    href: a.href,
                    text: a.textContent.trim(),
                    onclick: a.getAttribute('onclick') || ''
                });
            });
            // Also check iframes for embedded content
            document.querySelectorAll('iframe[src]').forEach(iframe => {
                links.push({
                    href: iframe.src,
                    text: 'Embedded Content',
                    type: 'iframe'
                });
            });
            // Check video elements
            document.querySelectorAll('video source[src], video[src]').forEach(vid => {
                const src = vid.getAttribute('src');
                if (src) {
                    links.push({
                        href: src,
                        text: 'Video',
                        type: 'video'
                    });
                }
            });
            return links;
        }''')

        for link in links:
            href = link.get('href', '')
            if self._is_material_url(href):
                materials.append({
                    'url': href,
                    'title': link.get('text', '') or self._title_from_url(href),
                    'type': self._detect_material_type(href),
                })

        return materials

    def _on_request(self, request):
        """Intercept requests to detect video streams."""
        url = request.url.lower()
        if any(ext in url for ext in ['.m3u8', '.mpd', '.ts', '.mp4', '.webm']):
            self.intercepted_urls.append({
                'url': request.url,
                'type': 'video_stream',
                'resource_type': request.resource_type,
            })

    def _on_response(self, response):
        """Intercept responses to detect video content."""
        content_type = response.headers.get('content-type', '')
        if any(ct in content_type for ct in [
            'video/', 'application/vnd.apple.mpegurl',
            'application/x-mpegurl', 'application/dash+xml'
        ]):
            self.intercepted_urls.append({
                'url': response.url,
                'type': 'video',
                'content_type': content_type,
            })

    def _get_intercepted_videos(self) -> list[dict]:
        """Return unique intercepted video URLs."""
        seen = set()
        videos = []
        for item in self.intercepted_urls:
            url = item['url']
            if url not in seen:
                seen.add(url)
                videos.append({
                    'url': url,
                    'title': f"Video: {self._title_from_url(url)}",
                    'type': 'video',
                })
        return videos

    @staticmethod
    def _is_material_url(url: str) -> bool:
        """Check if URL looks like a downloadable material."""
        if not url:
            return False
        url_lower = url.lower()

        # Skip non-material URLs
        skip_patterns = [
            'javascript:', 'mailto:', '#', 'void(0)',
            'login', 'logout', 'session', 'auth'
        ]
        if any(p in url_lower for p in skip_patterns):
            return False

        # File extensions that indicate downloadable content
        if re.search(r'\.(pdf|docx?|pptx?|xlsx?|csv|txt|zip|rar|'
                     r'mp4|mp3|m3u8|mpd|webm|ogg|wav|avi|mov)(\?|$)',
                     url_lower):
            return True

        # URL patterns that suggest downloadable content
        if re.search(r'download|archivo|material|recurso|file|document|'
                     r'video|stream|media|attachment|content',
                     url_lower):
            return True

        return False

    @staticmethod
    def _detect_material_type(url: str) -> str:
        """Detect material type from URL."""
        url_lower = url.lower()
        if '.pdf' in url_lower:
            return 'pdf'
        if any(ext in url_lower for ext in ['.docx', '.doc']):
            return 'document'
        if any(ext in url_lower for ext in ['.pptx', '.ppt']):
            return 'presentation'
        if any(ext in url_lower for ext in ['.xlsx', '.xls', '.csv']):
            return 'spreadsheet'
        if any(ext in url_lower for ext in ['.mp4', '.m3u8', '.mpd', '.webm', '.avi', '.mov']):
            return 'video'
        if any(ext in url_lower for ext in ['.mp3', '.wav', '.ogg']):
            return 'audio'
        if any(ext in url_lower for ext in ['.zip', '.rar', '.7z']):
            return 'archive'
        return 'unknown'

    @staticmethod
    def _title_from_url(url: str) -> str:
        """Extract a readable title from URL."""
        # Get filename from URL
        filename = url.rsplit('/', 1)[-1].split('?')[0]
        # Remove extension and clean up
        name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        # Replace underscores/hyphens with spaces
        name = re.sub(r'[_-]+', ' ', name)
        return name[:50] if name else 'Material'


async def download_with_browser(
    url: str,
    cookies: dict[str, str],
    timeout: float = 30.0
) -> tuple[bytes, str]:
    """
    Download a file using browser (for protected downloads).

    Some LMS systems require browser-based downloads for protected
    content that can't be fetched via direct HTTP requests.

    Args:
        url: URL to download
        cookies: Login cookies for authentication
        timeout: Download timeout in seconds

    Returns:
        Tuple of (content_bytes, content_type)
    """
    browser = await get_browser()
    context = await browser.new_context()

    # Set cookies
    parsed_url = urlparse(url)
    cookie_list = [
        {"name": k, "value": v, "domain": parsed_url.netloc, "path": "/"}
        for k, v in cookies.items()
    ]
    await context.add_cookies(cookie_list)

    page = await context.new_page()
    content = b''
    content_type = 'application/octet-stream'

    try:
        # Set up download handler
        async with page.expect_download(timeout=timeout * 1000) as download_info:
            await page.goto(url)

        download = await download_info.value
        path = await download.path()

        if path:
            with open(path, 'rb') as f:
                content = f.read()

        if download.suggested_filename:
            # Infer content type from filename
            ext = download.suggested_filename.rsplit('.', 1)[-1].lower()
            type_map = {
                'pdf': 'application/pdf',
                'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'doc': 'application/msword',
                'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'mp4': 'video/mp4',
                'mp3': 'audio/mpeg',
            }
            content_type = type_map.get(ext, 'application/octet-stream')

    except Exception as e:
        logger.warning(f"Browser download failed, trying direct page fetch: {e}")
        # Fallback: try to get page content directly
        try:
            response = await page.goto(url)
            if response:
                content = await response.body()
                content_type = response.headers.get('content-type', 'application/octet-stream')
        except Exception as inner_e:
            logger.error(f"Direct page fetch also failed: {inner_e}")

    finally:
        await page.close()
        await context.close()

    return content, content_type


async def extract_video_stream_url(
    page_url: str,
    cookies: dict[str, str],
    timeout: float = 30.0
) -> Optional[str]:
    """
    Extract HLS/DASH video stream URL from a video page.

    Navigates to a video page, waits for the video player to load,
    and intercepts network requests to capture the stream manifest URL.

    Args:
        page_url: URL of the video page
        cookies: Login cookies for authentication
        timeout: Page load timeout in seconds

    Returns:
        The manifest URL (.m3u8 or .mpd), or None if not found
    """
    browser = await get_browser()
    context = await browser.new_context()

    # Set cookies
    parsed_url = urlparse(page_url)
    cookie_list = [
        {"name": k, "value": v, "domain": parsed_url.netloc, "path": "/"}
        for k, v in cookies.items()
    ]
    await context.add_cookies(cookie_list)

    page = await context.new_page()
    stream_url = None

    def capture_stream(request):
        nonlocal stream_url
        url = request.url.lower()
        # Prefer manifest files over segment files
        if '.m3u8' in url or '.mpd' in url:
            stream_url = request.url

    try:
        page.on("request", capture_stream)
        logger.info(f"Browser extracting video from: {page_url}")
        await page.goto(page_url, timeout=timeout * 1000)
        await page.wait_for_load_state("networkidle", timeout=timeout * 1000)

        # Try to trigger video playback
        try:
            # Look for play buttons or video elements
            play_selectors = [
                '[class*="play"]', '[aria-label*="play"]', '[aria-label*="Play"]',
                'video', '[class*="player"]', 'button[class*="play"]'
            ]
            for selector in play_selectors:
                play_btn = await page.query_selector(selector)
                if play_btn:
                    await play_btn.click()
                    await page.wait_for_timeout(2000)  # Wait for video to start
                    if stream_url:
                        break
        except Exception:
            pass

        # If no stream URL captured, check for video source in DOM
        if not stream_url:
            stream_url = await page.evaluate('''() => {
                // Check video source elements
                const sources = document.querySelectorAll('video source[src], video[src]');
                for (const src of sources) {
                    const url = src.getAttribute('src') || src.src;
                    if (url && (url.includes('.m3u8') || url.includes('.mpd') || url.includes('.mp4'))) {
                        return url;
                    }
                }
                // Check for data attributes
                const players = document.querySelectorAll('[data-video-src], [data-src]');
                for (const p of players) {
                    const url = p.getAttribute('data-video-src') || p.getAttribute('data-src');
                    if (url && (url.includes('.m3u8') || url.includes('.mpd') || url.includes('.mp4'))) {
                        return url;
                    }
                }
                return null;
            }''')

    except Exception as e:
        logger.warning(f"Video extraction failed: {e}")
    finally:
        await page.close()
        await context.close()

    if stream_url:
        logger.info(f"Extracted video stream URL: {stream_url[:100]}...")
    return stream_url
