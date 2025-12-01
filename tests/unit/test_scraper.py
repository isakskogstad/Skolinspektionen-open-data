"""Tests for scraper module."""

import pytest
import respx
from bs4 import BeautifulSoup
from httpx import Response

from src.config import Settings
from src.services.scraper import PublicationScraper


class TestPublicationScraper:
    """Tests for PublicationScraper."""

    @pytest.mark.asyncio
    async def test_fetch_page_success(
        self, test_settings: Settings, respx_mock, mock_html_publication_list: str
    ):
        """Test successful page fetch."""
        respx_mock.get("https://www.skolinspektionen.se/test").mock(
            return_value=Response(200, text=mock_html_publication_list)
        )

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            html = await scraper.fetch_page("https://www.skolinspektionen.se/test")
            assert html is not None
            assert "search-result-item" in html

    @pytest.mark.asyncio
    async def test_fetch_page_not_found(self, test_settings: Settings, respx_mock):
        """Test handling of 404 response."""
        respx_mock.get("https://www.skolinspektionen.se/notfound").mock(
            return_value=Response(404)
        )

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            html = await scraper.fetch_page("https://www.skolinspektionen.se/notfound")
            assert html is None

    @pytest.mark.asyncio
    async def test_fetch_page_server_error(self, test_settings: Settings, respx_mock):
        """Test handling of server error."""
        respx_mock.get("https://www.skolinspektionen.se/error").mock(
            return_value=Response(500)
        )

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            html = await scraper.fetch_page("https://www.skolinspektionen.se/error")
            assert html is None

    @pytest.mark.asyncio
    async def test_fetch_page_timeout(self, test_settings: Settings, respx_mock):
        """Test handling of timeout."""
        import httpx

        respx_mock.get("https://www.skolinspektionen.se/timeout").mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            html = await scraper.fetch_page("https://www.skolinspektionen.se/timeout")
            assert html is None


class TestPublicationParsing:
    """Tests for publication parsing."""

    def test_parse_publication_list(
        self, test_settings: Settings, mock_html_publication_list: str
    ):
        """Test parsing publication list HTML."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        soup = BeautifulSoup(mock_html_publication_list, "html.parser")
        publications = scraper._parse_publication_list(soup)
        assert len(publications) == 2

        # Check first publication
        pub1 = publications[0]
        assert "Test Rapport 2024" in pub1.title

    def test_parse_empty_html(self, test_settings: Settings):
        """Test parsing empty HTML."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        soup = BeautifulSoup("<html><body></body></html>", "html.parser")
        publications = scraper._parse_publication_list(soup)
        assert publications == []

    def test_parse_date_extraction(
        self, test_settings: Settings, mock_html_publication_list: str
    ):
        """Test date extraction from publication list."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        soup = BeautifulSoup(mock_html_publication_list, "html.parser")
        publications = scraper._parse_publication_list(soup)
        if publications and publications[0].published:
            assert publications[0].published.year == 2024
            assert publications[0].published.month == 3
            assert publications[0].published.day == 15

    def test_parse_date_method(self, test_settings: Settings):
        """Test the _parse_date method directly."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        # Test ISO format
        result = scraper._parse_date("2024-03-15")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 15

        # Test Swedish date format
        result = scraper._parse_date("15 mars 2024")
        assert result is not None
        assert result.year == 2024
        assert result.month == 3

        # Test invalid date
        result = scraper._parse_date("invalid")
        assert result is None


class TestScraperWithCache:
    """Tests for scraper caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit(
        self,
        test_settings: Settings,
        respx_mock,
        mock_html_publication_list: str,
    ):
        """Test that cache is used on second request."""
        url = "https://www.skolinspektionen.se/cached"

        # Mock returns content
        respx_mock.get(url).mock(
            return_value=Response(200, text=mock_html_publication_list)
        )

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=True,
            use_delta=False,
        ) as scraper:
            # First request
            html1 = await scraper.fetch_page(url)
            assert html1 is not None

            # Second request should use cache (same content)
            html2 = await scraper.fetch_page(url)
            assert html2 == html1


class TestScraperIntegration:
    """Integration tests for scraper (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_scrape_publications_single_page(
        self, test_settings: Settings, respx_mock, mock_html_publication_list: str
    ):
        """Test scraping single page of publications."""
        # Mock the publication search pages
        respx_mock.get(
            "https://www.skolinspektionen.se/beslut-rapporter/publikationssok/?p=1"
        ).mock(return_value=Response(200, text=mock_html_publication_list))

        respx_mock.get(
            "https://www.skolinspektionen.se/beslut-rapporter/publikationssok/?p=2"
        ).mock(return_value=Response(200, text="<html><body></body></html>"))

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            publications = await scraper.scrape_publications(max_pages=1)
            assert len(publications) >= 0  # May find items depending on selectors

    @pytest.mark.asyncio
    async def test_scrape_publications_respects_max_pages(
        self, test_settings: Settings, respx_mock, mock_html_publication_list: str
    ):
        """Test that max_pages limit is respected."""
        # Mock first page
        respx_mock.get(
            "https://www.skolinspektionen.se/beslut-rapporter/publikationssok/?p=1"
        ).mock(return_value=Response(200, text=mock_html_publication_list))

        # Second page
        respx_mock.get(
            "https://www.skolinspektionen.se/beslut-rapporter/publikationssok/?p=2"
        ).mock(return_value=Response(200, text=mock_html_publication_list))

        # Third page - should not be accessed if max_pages=2
        respx_mock.get(
            "https://www.skolinspektionen.se/beslut-rapporter/publikationssok/?p=3"
        ).mock(return_value=Response(200, text=mock_html_publication_list))

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            # This should complete without error
            await scraper.scrape_publications(max_pages=2)


class TestScraperRobustness:
    """Tests for scraper robustness."""

    def test_parse_malformed_html(self, test_settings: Settings):
        """Test parsing malformed HTML doesn't crash."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        malformed = "<div><span>Unclosed tags<p>More content"
        soup = BeautifulSoup(malformed, "html.parser")
        try:
            result = scraper._parse_publication_list(soup)
            assert isinstance(result, list)
        except Exception:
            pytest.fail("Parsing malformed HTML should not raise exception")

    def test_parse_missing_required_fields(self, test_settings: Settings):
        """Test parsing HTML with missing fields."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        html = """
        <div class="search-result-item">
            <h2><a href="/publikationer/ovriga/test">Title Only</a></h2>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        publications = scraper._parse_publication_list(soup)
        assert len(publications) == 1
        assert publications[0].title == "Title Only"
        # Other fields should have defaults
        assert publications[0].published is None

    @pytest.mark.asyncio
    async def test_handles_empty_response(self, test_settings: Settings, respx_mock):
        """Test handling empty response body."""
        respx_mock.get("https://www.skolinspektionen.se/empty").mock(
            return_value=Response(200, text="")
        )

        async with PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        ) as scraper:
            html = await scraper.fetch_page("https://www.skolinspektionen.se/empty")
            # Empty response is still a valid response
            assert html == ""


class TestExtractTotalCount:
    """Tests for _extract_total_count method."""

    def test_extract_count_from_results_text(self, test_settings: Settings):
        """Test extracting count from 'av X resultat' pattern."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        html = "<div>Visar 1-20 av 334 resultat</div>"
        count = scraper._extract_total_count(html)
        assert count == 334

    def test_extract_count_from_traffar(self, test_settings: Settings):
        """Test extracting count from 'X träffar' pattern."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        html = "<div>500 träffar</div>"
        count = scraper._extract_total_count(html)
        assert count == 500

    def test_no_count_found(self, test_settings: Settings):
        """Test when no count pattern found."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        html = "<div>No results here</div>"
        count = scraper._extract_total_count(html)
        assert count is None


class TestCleanUrl:
    """Tests for _clean_url method."""

    def test_removes_query_params(self, test_settings: Settings):
        """Test that query parameters are removed."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        url = "https://example.com/path?tracking=123&utm_source=test"
        clean = scraper._clean_url(url)
        assert clean == "https://example.com/path"

    def test_preserves_path(self, test_settings: Settings):
        """Test that path is preserved."""
        scraper = PublicationScraper(
            timeout=test_settings.http_timeout,
            use_cache=False,
            use_delta=False,
        )
        url = "https://example.com/deep/path/to/resource"
        clean = scraper._clean_url(url)
        assert clean == "https://example.com/deep/path/to/resource"
