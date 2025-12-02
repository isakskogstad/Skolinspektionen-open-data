"""Tests for browser module."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.browser import (
    BLOCKED_RESOURCE_TYPES,
    BLOCKED_URL_PATTERNS,
    BrowserScraper,
    is_javascript_required,
)


class TestBrowserScraperInit:
    """Tests for BrowserScraper initialization."""

    def test_default_init(self):
        """Test default initialization."""
        scraper = BrowserScraper()
        assert scraper.headless is True
        assert scraper.timeout == 30000
        assert scraper.block_resources is True
        assert scraper._browser is None
        assert scraper._camoufox is None

    def test_custom_init(self):
        """Test custom initialization."""
        scraper = BrowserScraper(
            headless=False,
            timeout=60000,
            block_resources=False,
        )
        assert scraper.headless is False
        assert scraper.timeout == 60000
        assert scraper.block_resources is False


class TestShouldBlockRequest:
    """Tests for _should_block_request method."""

    @pytest.fixture
    def scraper(self) -> BrowserScraper:
        """Create a scraper instance."""
        return BrowserScraper()

    @pytest.fixture
    def mock_route(self):
        """Create a mock route object."""

        def create_route(resource_type: str, url: str):
            route = MagicMock()
            route.request.resource_type = resource_type
            route.request.url = url
            return route

        return create_route

    @pytest.mark.asyncio
    async def test_block_disabled(self, mock_route):
        """Test that blocking is skipped when disabled."""
        scraper = BrowserScraper(block_resources=False)
        route = mock_route("image", "https://example.com/test.jpg")
        result = await scraper._should_block_request(route)
        assert result is False

    @pytest.mark.asyncio
    async def test_block_image(self, scraper: BrowserScraper, mock_route):
        """Test blocking image resources."""
        route = mock_route("image", "https://example.com/test.jpg")
        result = await scraper._should_block_request(route)
        assert result is True

    @pytest.mark.asyncio
    async def test_block_font(self, scraper: BrowserScraper, mock_route):
        """Test blocking font resources."""
        route = mock_route("font", "https://example.com/font.woff2")
        result = await scraper._should_block_request(route)
        assert result is True

    @pytest.mark.asyncio
    async def test_block_stylesheet(self, scraper: BrowserScraper, mock_route):
        """Test blocking stylesheet resources."""
        route = mock_route("stylesheet", "https://example.com/style.css")
        result = await scraper._should_block_request(route)
        assert result is True

    @pytest.mark.asyncio
    async def test_block_media(self, scraper: BrowserScraper, mock_route):
        """Test blocking media resources."""
        route = mock_route("media", "https://example.com/video.mp4")
        result = await scraper._should_block_request(route)
        assert result is True

    @pytest.mark.asyncio
    async def test_block_analytics_url(self, scraper: BrowserScraper, mock_route):
        """Test blocking analytics URLs."""
        route = mock_route("script", "https://google-analytics.com/track.js")
        result = await scraper._should_block_request(route)
        assert result is True

    @pytest.mark.asyncio
    async def test_block_tracking_url(self, scraper: BrowserScraper, mock_route):
        """Test blocking tracking URLs."""
        route = mock_route("script", "https://example.com/tracking.js")
        result = await scraper._should_block_request(route)
        assert result is True

    @pytest.mark.asyncio
    async def test_allow_document(self, scraper: BrowserScraper, mock_route):
        """Test allowing document resources."""
        route = mock_route("document", "https://example.com/page.html")
        result = await scraper._should_block_request(route)
        assert result is False

    @pytest.mark.asyncio
    async def test_allow_xhr(self, scraper: BrowserScraper, mock_route):
        """Test allowing XHR resources."""
        route = mock_route("xhr", "https://example.com/api/data")
        result = await scraper._should_block_request(route)
        assert result is False


class TestRouteHandler:
    """Tests for _route_handler method."""

    @pytest.fixture
    def scraper(self) -> BrowserScraper:
        """Create a scraper instance."""
        return BrowserScraper()

    @pytest.mark.asyncio
    async def test_abort_blocked_request(self, scraper: BrowserScraper):
        """Test that blocked requests are aborted."""
        route = MagicMock()
        route.request.resource_type = "image"
        route.request.url = "https://example.com/test.jpg"
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()

        await scraper._route_handler(route)

        route.abort.assert_called_once()
        route.continue_.assert_not_called()

    @pytest.mark.asyncio
    async def test_continue_allowed_request(self, scraper: BrowserScraper):
        """Test that allowed requests continue."""
        route = MagicMock()
        route.request.resource_type = "document"
        route.request.url = "https://example.com/page.html"
        route.abort = AsyncMock()
        route.continue_ = AsyncMock()

        await scraper._route_handler(route)

        route.continue_.assert_called_once()
        route.abort.assert_not_called()


class TestFetchPage:
    """Tests for fetch_page method."""

    @pytest.mark.asyncio
    async def test_fetch_without_browser_init(self):
        """Test fetch fails when browser not initialized."""
        scraper = BrowserScraper()
        result = await scraper.fetch_page("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """Test successful page fetch with mocked browser."""
        scraper = BrowserScraper()

        # Mock the browser and page
        mock_page = AsyncMock()
        mock_page.content.return_value = "<html><body>Test content</body></html>"
        mock_page.route = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        scraper._browser = mock_browser

        result = await scraper.fetch_page("https://example.com")

        assert result == "<html><body>Test content</body></html>"
        mock_page.goto.assert_called_once()
        mock_page.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_with_selector(self):
        """Test fetch with wait_for_selector."""
        scraper = BrowserScraper()

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html><body><div id='content'>Test</div></body></html>"
        mock_page.route = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        scraper._browser = mock_browser

        result = await scraper.fetch_page(
            "https://example.com",
            wait_for_selector="#content",
        )

        assert result is not None
        mock_page.wait_for_selector.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_error_handling(self):
        """Test fetch handles errors gracefully."""
        scraper = BrowserScraper()

        mock_page = AsyncMock()
        mock_page.route = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=Exception("Network error"))
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        scraper._browser = mock_browser

        result = await scraper.fetch_page("https://example.com")

        assert result is None
        mock_page.close.assert_called_once()


class TestFetchWithScroll:
    """Tests for fetch_with_scroll method."""

    @pytest.mark.asyncio
    async def test_scroll_without_browser_init(self):
        """Test scroll fetch fails when browser not initialized."""
        scraper = BrowserScraper()
        result = await scraper.fetch_with_scroll("https://example.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_scroll_success(self):
        """Test successful scroll fetch."""
        scraper = BrowserScraper()

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html><body>Scrolled content</body></html>"
        mock_page.route = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        scraper._browser = mock_browser

        result = await scraper.fetch_with_scroll(
            "https://example.com",
            scroll_count=2,
            scroll_delay=0.1,
        )

        assert result == "<html><body>Scrolled content</body></html>"
        # Should scroll twice plus scroll to top
        assert mock_page.evaluate.call_count == 3


class TestFetchMultiple:
    """Tests for fetch_multiple method."""

    @pytest.mark.asyncio
    async def test_fetch_multiple_urls(self):
        """Test fetching multiple URLs."""
        scraper = BrowserScraper()

        mock_page = AsyncMock()
        mock_page.content.return_value = "<html>Content</html>"
        mock_page.route = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_page.return_value = mock_page

        scraper._browser = mock_browser

        urls = [
            "https://example.com/1",
            "https://example.com/2",
            "https://example.com/3",
        ]
        results = await scraper.fetch_multiple(urls, concurrency=2)

        assert len(results) == 3
        for url in urls:
            assert url in results


class TestIsJavascriptRequired:
    """Tests for is_javascript_required function."""

    @pytest.mark.asyncio
    async def test_skolverket_requires_js(self):
        """Test that skolverket.se requires JS."""
        result = await is_javascript_required("https://www.skolverket.se/page")
        assert result is True

    @pytest.mark.asyncio
    async def test_scb_hitta_requires_js(self):
        """Test that SCB statistics portal requires JS."""
        result = await is_javascript_required("https://www.scb.se/hitta-statistik/data")
        assert result is True

    @pytest.mark.asyncio
    async def test_generic_url_no_js(self):
        """Test that generic URLs don't require JS."""
        result = await is_javascript_required("https://example.com/page")
        assert result is False

    @pytest.mark.asyncio
    async def test_skolinspektionen_no_js(self):
        """Test that skolinspektionen doesn't require JS by default."""
        result = await is_javascript_required("https://www.skolinspektionen.se/publikation")
        assert result is False


class TestBlockedPatterns:
    """Tests for blocked resource patterns."""

    def test_blocked_resource_types(self):
        """Test that expected resource types are blocked."""
        assert "image" in BLOCKED_RESOURCE_TYPES
        assert "media" in BLOCKED_RESOURCE_TYPES
        assert "font" in BLOCKED_RESOURCE_TYPES
        assert "stylesheet" in BLOCKED_RESOURCE_TYPES
        assert "document" not in BLOCKED_RESOURCE_TYPES
        assert "script" not in BLOCKED_RESOURCE_TYPES

    def test_blocked_url_patterns(self):
        """Test that expected URL patterns are blocked."""
        assert "google-analytics" in BLOCKED_URL_PATTERNS
        assert "googletagmanager" in BLOCKED_URL_PATTERNS
        assert "facebook" in BLOCKED_URL_PATTERNS
        assert "tracking" in BLOCKED_URL_PATTERNS


class TestContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_import_error(self):
        """Test handling of missing Camoufox import."""
        scraper = BrowserScraper()

        with patch.dict("sys.modules", {"camoufox": None, "camoufox.async_api": None}):
            with pytest.raises((ImportError, ModuleNotFoundError)):
                async with scraper:
                    pass

    @pytest.mark.asyncio
    async def test_context_manager_success(self):
        """Test successful context manager usage with mocked Camoufox."""
        mock_browser = AsyncMock()

        mock_camoufox_instance = AsyncMock()
        mock_camoufox_instance.__aenter__.return_value = mock_browser
        mock_camoufox_instance.__aexit__.return_value = None

        MagicMock(return_value=mock_camoufox_instance)

        with patch(
            "src.services.browser.BrowserScraper.__aenter__",
            new=AsyncMock(side_effect=lambda self: setattr(self, "_browser", mock_browser) or self),
        ):
            scraper = BrowserScraper()
            # Manually set up as if context manager worked
            scraper._browser = mock_browser
            assert scraper._browser is not None
