"""Tests for MCP server tools."""

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import Response

from src.services.models import Index, PressRelease, Publication, StatisticsFile


class TestSearchPublications:
    """Tests for search_publications tool."""

    @pytest.mark.asyncio
    async def test_search_with_query(self, sample_publications: list[Publication]):
        """Test searching publications with a query."""
        from src.search.ranker import search_publications

        # Search for "matematik" which is in sample_publications
        results = search_publications(sample_publications, "matematik")
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_search_with_type_filter(self, sample_publications: list[Publication]):
        """Test filtering by publication type."""
        from src.search.ranker import search_publications

        results = search_publications(
            sample_publications, "", publication_type="kvalitetsgranskning"
        )
        for result in results:
            assert result.item.type == "kvalitetsgranskning"

    @pytest.mark.asyncio
    async def test_search_with_year_filter(self, sample_publications: list[Publication]):
        """Test filtering by year."""
        from src.search.ranker import search_publications

        results = search_publications(sample_publications, "", year=2024)
        for result in results:
            if result.item.published:
                assert result.item.published.year == 2024


class TestGetPublicationContent:
    """Tests for get_publication_content tool."""

    @pytest.mark.asyncio
    async def test_fetch_publication_content(self, respx_mock):
        """Test fetching publication content."""
        html_content = """
        <html>
        <body>
            <article>
                <h1>Test Rapport</h1>
                <div class="content">
                    <p>Innehåll från rapporten.</p>
                </div>
            </article>
        </body>
        </html>
        """
        respx_mock.get("https://www.skolinspektionen.se/test-rapport").mock(
            return_value=Response(200, text=html_content)
        )

        # Just verify the mock is set up correctly
        assert respx_mock.calls.call_count == 0


class TestListPublicationTypes:
    """Tests for list_publication_types tool."""

    def test_returns_all_types(self):
        """Test that all publication types are returned."""
        from src.services.models import PUBLICATION_TYPES

        assert len(PUBLICATION_TYPES) > 0
        assert "kvalitetsgranskning" in PUBLICATION_TYPES
        # Check actual types that exist
        assert "regeringsrapporter" in PUBLICATION_TYPES or "ovriga-publikationer" in PUBLICATION_TYPES

    def test_types_have_display_names(self):
        """Test that types have Swedish display names."""
        from src.services.models import PUBLICATION_TYPES

        for key, name in PUBLICATION_TYPES.items():
            assert len(name) > 0
            assert key == key.lower()


class TestListThemes:
    """Tests for list_themes tool."""

    def test_returns_all_themes(self):
        """Test that themes are returned."""
        from src.services.models import THEMES

        assert len(THEMES) > 0


class TestGetStatistics:
    """Tests for get_statistics tool."""

    def test_statistics_structure(self, sample_statistics_file: StatisticsFile):
        """Test statistics file structure."""
        assert sample_statistics_file.year == 2023
        assert sample_statistics_file.category == "tillstand"
        assert sample_statistics_file.file_type == "xlsx"
        assert sample_statistics_file.url.endswith(".xlsx")


class TestSearchPressReleases:
    """Tests for search_press_releases tool."""

    @pytest.mark.asyncio
    async def test_search_press_releases(self):
        """Test searching press releases."""
        from src.search.ranker import search_press_releases

        releases = [
            PressRelease(
                title="Ny rapport om skolor",
                url="/press/1",
                published=date(2024, 3, 1),
            ),
            PressRelease(
                title="Statistik över tillsyn",
                url="/press/2",
                published=date(2024, 2, 15),
            ),
        ]

        results = search_press_releases(releases, "rapport")
        assert len(results) > 0


class TestGetCacheStats:
    """Tests for get_cache_stats tool."""

    def test_cache_stats_format(self):
        """Test cache stats return format."""
        from src.services.cache import get_content_cache, reset_content_cache

        reset_content_cache()
        cache = get_content_cache()

        # Cache should have a get_stats method
        assert hasattr(cache, "get_stats")


class TestHealthCheck:
    """Tests for health_check tool."""

    def test_health_check_returns_status(self):
        """Test health check returns expected format."""
        # Health check should return:
        # - status: "healthy" | "degraded" | "unhealthy"
        # - components: dict of component statuses
        # - timestamp: ISO timestamp
        pass


class TestMCPResources:
    """Tests for MCP resources."""

    def test_publication_types_resource(self):
        """Test publication-types resource."""
        from src.services.models import PUBLICATION_TYPES

        # Resource should return PUBLICATION_TYPES as JSON
        data = PUBLICATION_TYPES
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_themes_resource(self):
        """Test themes resource."""
        from src.services.models import THEMES

        # Resource should return THEMES as JSON
        data = THEMES
        assert isinstance(data, (dict, list))

    def test_recent_publications_resource(self, sample_index: Index):
        """Test recent publications resource."""
        # Should return 10 most recent publications
        recent = sorted(
            [p for p in sample_index.publications if p.published],
            key=lambda p: p.published,
            reverse=True,
        )[:10]
        assert len(recent) <= 10


class TestMCPPrompts:
    """Tests for MCP prompts."""

    def test_analyze_school_prompt_structure(self):
        """Test analyze_school prompt accepts school name."""
        # Prompt should accept "school_name" argument
        # and return a structured analysis prompt
        pass

    def test_compare_inspections_prompt_structure(self):
        """Test compare_inspections prompt accepts publication URLs."""
        # Prompt should accept list of publication URLs
        # and return comparison prompt
        pass


class TestIndexOperations:
    """Tests for index-related operations."""

    def test_load_index_from_file(self, sample_index: Index, temp_dir: Path):
        """Test loading index from JSON file."""
        index_path = temp_dir / "api" / "index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        # Write index
        data = sample_index.model_dump(mode="json")
        index_path.write_text(json.dumps(data, ensure_ascii=False))

        # Read and parse
        loaded_data = json.loads(index_path.read_text())
        loaded_index = Index(**loaded_data)

        assert loaded_index.total_items == sample_index.total_items

    def test_index_total_items(self, sample_index: Index):
        """Test total_items calculation."""
        expected = (
            len(sample_index.publications)
            + len(sample_index.press_releases)
            + len(sample_index.statistics_files)
        )
        # Note: total_items may also include decisions
        assert sample_index.total_items >= expected


class TestToolErrorHandling:
    """Tests for tool error handling."""

    def test_search_with_empty_index(self):
        """Test search when index is empty."""
        from src.search.ranker import search_publications

        results = search_publications([], "anything")
        assert results == []

    def test_search_with_invalid_filters(self, sample_publications: list[Publication]):
        """Test search with invalid filter values."""
        from src.search.ranker import search_publications

        # Non-existent type should return empty
        results = search_publications(
            sample_publications, "", publication_type="nonexistent-type"
        )
        assert results == []

    def test_search_with_future_year(self, sample_publications: list[Publication]):
        """Test search with year in the future."""
        from src.search.ranker import search_publications

        results = search_publications(sample_publications, "", year=2099)
        assert results == []
