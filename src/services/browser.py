"""Headless browser support using Camoufox for JavaScript-heavy pages."""

import asyncio
from typing import Optional, Set
from urllib.parse import urlparse

from rich.console import Console

from ..config import get_settings

console = Console()

# Resource types to block for faster page loads
BLOCKED_RESOURCE_TYPES: Set[str] = {
    "image",
    "media",
    "font",
    "stylesheet",
}

# URL patterns to block (tracking, analytics, ads)
BLOCKED_URL_PATTERNS: Set[str] = {
    "google-analytics",
    "googletagmanager",
    "facebook",
    "doubleclick",
    "analytics",
    "tracking",
    "advertisement",
}


class BrowserScraper:
    """Stealthy browser scraper using Camoufox for JavaScript-rendered pages.

    Camoufox is a Firefox-based browser with anti-fingerprinting measures
    that helps avoid bot detection while scraping JavaScript-heavy sites.

    Usage:
        async with BrowserScraper() as browser:
            html = await browser.fetch_page("https://example.com")
    """

    def __init__(
        self,
        headless: bool = True,
        timeout: float = 30000,
        block_resources: bool = True,
    ):
        """Initialize browser scraper.

        Args:
            headless: Run browser in headless mode (no visible window)
            timeout: Page load timeout in milliseconds
            block_resources: Block unnecessary resources for faster loads
        """
        self.headless = headless
        self.timeout = timeout
        self.block_resources = block_resources
        self._browser = None
        self._camoufox = None

    async def __aenter__(self):
        """Start the browser context."""
        try:
            from camoufox.async_api import AsyncCamoufox

            self._camoufox = AsyncCamoufox(headless=self.headless, geoip=True)
            self._browser = await self._camoufox.__aenter__()
            console.print("[dim]Camoufox browser started[/dim]")
            return self
        except ImportError:
            console.print(
                "[yellow]Camoufox not installed. "
                "Install with: pip install 'skolinspektionen-data[scraper]'[/yellow]"
            )
            raise
        except Exception as e:
            console.print(f"[red]Failed to start browser: {e}[/red]")
            raise

    async def __aexit__(self, *args):
        """Close the browser context."""
        if self._camoufox:
            await self._camoufox.__aexit__(*args)
            console.print("[dim]Camoufox browser closed[/dim]")

    async def _should_block_request(self, route) -> bool:
        """Determine if a request should be blocked."""
        if not self.block_resources:
            return False

        request = route.request

        # Block by resource type
        if request.resource_type in BLOCKED_RESOURCE_TYPES:
            return True

        # Block by URL pattern
        url_lower = request.url.lower()
        for pattern in BLOCKED_URL_PATTERNS:
            if pattern in url_lower:
                return True

        return False

    async def _route_handler(self, route):
        """Handle route requests, blocking unnecessary resources."""
        if await self._should_block_request(route):
            await route.abort()
        else:
            await route.continue_()

    async def fetch_page(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        wait_for_load_state: str = "networkidle",
    ) -> Optional[str]:
        """Fetch a page and return its rendered HTML content.

        Args:
            url: The URL to fetch
            wait_for_selector: Optional CSS selector to wait for before returning
            wait_for_load_state: Page load state to wait for
                ('load', 'domcontentloaded', 'networkidle')

        Returns:
            The rendered HTML content, or None if fetch failed
        """
        if not self._browser:
            console.print("[red]Browser not initialized. Use async with.[/red]")
            return None

        page = None
        try:
            page = await self._browser.new_page()

            # Set up request blocking if enabled
            if self.block_resources:
                await page.route("**/*", self._route_handler)

            # Navigate to the page
            console.print(f"[dim]Fetching: {url}[/dim]")
            await page.goto(url, timeout=self.timeout, wait_until=wait_for_load_state)

            # Wait for specific selector if provided
            if wait_for_selector:
                await page.wait_for_selector(
                    wait_for_selector,
                    timeout=self.timeout,
                    state="visible",
                )

            # Get the rendered HTML
            content = await page.content()
            console.print(f"[green]✓ Fetched {len(content)} bytes[/green]")
            return content

        except Exception as e:
            console.print(f"[red]Browser fetch error for {url}: {e}[/red]")
            return None

        finally:
            if page:
                await page.close()

    async def fetch_with_scroll(
        self,
        url: str,
        scroll_count: int = 3,
        scroll_delay: float = 1.0,
    ) -> Optional[str]:
        """Fetch a page with infinite scroll support.

        Useful for pages that load content dynamically as you scroll.

        Args:
            url: The URL to fetch
            scroll_count: Number of times to scroll down
            scroll_delay: Delay in seconds between scrolls

        Returns:
            The rendered HTML content after scrolling
        """
        if not self._browser:
            console.print("[red]Browser not initialized. Use async with.[/red]")
            return None

        page = None
        try:
            page = await self._browser.new_page()

            if self.block_resources:
                await page.route("**/*", self._route_handler)

            await page.goto(url, timeout=self.timeout, wait_until="networkidle")

            # Scroll down multiple times to trigger lazy loading
            for i in range(scroll_count):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(scroll_delay)
                console.print(f"[dim]Scroll {i + 1}/{scroll_count}[/dim]")

            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(0.5)

            content = await page.content()
            return content

        except Exception as e:
            console.print(f"[red]Browser scroll fetch error: {e}[/red]")
            return None

        finally:
            if page:
                await page.close()

    async def fetch_multiple(
        self,
        urls: list[str],
        concurrency: int = 3,
    ) -> dict[str, Optional[str]]:
        """Fetch multiple pages concurrently.

        Args:
            urls: List of URLs to fetch
            concurrency: Maximum concurrent page fetches

        Returns:
            Dictionary mapping URLs to their HTML content
        """
        semaphore = asyncio.Semaphore(concurrency)
        results: dict[str, Optional[str]] = {}

        async def fetch_with_semaphore(url: str):
            async with semaphore:
                results[url] = await self.fetch_page(url)

        await asyncio.gather(*[fetch_with_semaphore(url) for url in urls])
        return results


async def is_javascript_required(url: str) -> bool:
    """Check if a URL likely requires JavaScript rendering.

    This is a heuristic check based on known patterns.

    Args:
        url: The URL to check

    Returns:
        True if JavaScript rendering is likely needed
    """
    settings = get_settings()

    # Known JavaScript-heavy domains/patterns
    js_patterns = [
        "skolverket.se",  # Known to use JavaScript-heavy portals
        "scb.se/hitta-statistik",  # Statistics portal
    ]

    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    for pattern in js_patterns:
        if pattern in hostname or pattern in url:
            return True

    return False
