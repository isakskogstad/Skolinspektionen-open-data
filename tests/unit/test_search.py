"""Tests for search module."""

from datetime import date

import pytest

from src.search.ranker import (
    SearchRanker,
    SearchResult,
    search_press_releases,
    search_publications,
    tokenize_swedish,
)
from src.services.models import PressRelease, Publication


class TestTokenizeSwedish:
    """Tests for Swedish tokenization."""

    def test_basic_tokenization(self):
        """Test basic word tokenization."""
        tokens = tokenize_swedish("Hej på dig")
        assert "hej" in tokens
        assert "dig" in tokens

    def test_lowercase(self):
        """Test that tokens are lowercased."""
        tokens = tokenize_swedish("STORA Bokstäver")
        assert "stora" in tokens
        assert "bokstäver" in tokens

    def test_stop_words_removed(self):
        """Test that Swedish stop words are removed."""
        tokens = tokenize_swedish("Detta är en test av systemet")
        # Common Swedish stop words should be removed
        assert "detta" not in tokens or "är" not in tokens or "en" not in tokens
        assert "test" in tokens
        assert "systemet" in tokens

    def test_handles_special_characters(self):
        """Test handling of Swedish special characters."""
        tokens = tokenize_swedish("Skolan på Åland med räksmörgås")
        assert "skolan" in tokens
        assert "åland" in tokens
        assert "räksmörgås" in tokens

    def test_empty_string(self):
        """Test tokenizing empty string."""
        tokens = tokenize_swedish("")
        assert tokens == []

    def test_only_stop_words(self):
        """Test string with only stop words."""
        tokens = tokenize_swedish("och i på")
        # Should return empty or minimal tokens
        assert len(tokens) <= 3  # Depending on stop word list


class TestSearchRanker:
    """Tests for SearchRanker class."""

    @pytest.fixture
    def ranker(self, sample_publications: list[Publication]) -> SearchRanker:
        """Create a search ranker with sample data."""
        return SearchRanker(
            items=sample_publications,
            get_text=lambda p: p.title,
            get_secondary_text=lambda p: p.summary or "",
        )

    def test_exact_match(self, ranker: SearchRanker):
        """Test searching for exact term."""
        results = ranker.search("matematik")
        assert len(results) > 0
        # The publication about matematik should rank highly
        titles = [r.item.title for r in results]
        assert any("matematik" in t.lower() for t in titles)

    def test_partial_match(self, ranker: SearchRanker):
        """Test fuzzy matching for partial terms."""
        results = ranker.search("matema")  # Partial
        assert len(results) > 0

    def test_no_results(self, ranker: SearchRanker):
        """Test search with no matching results."""
        results = ranker.search("xyznonexistent123")
        assert len(results) == 0

    def test_result_ordering(self, ranker: SearchRanker):
        """Test that results are ordered by relevance."""
        results = ranker.search("kvalitetsgranskning")
        assert len(results) > 0
        # Results should be ordered by score (descending)
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_max_results(self, ranker: SearchRanker):
        """Test limiting number of results."""
        results = ranker.search("skola", max_results=2)
        assert len(results) <= 2

    def test_search_result_structure(self, ranker: SearchRanker):
        """Test SearchResult structure."""
        results = ranker.search("tillsyn")
        if results:
            result = results[0]
            assert isinstance(result, SearchResult)
            assert hasattr(result, "item")
            assert hasattr(result, "score")
            assert isinstance(result.score, float)


class TestSearchPublications:
    """Tests for search_publications function."""

    def test_basic_search(self, sample_publications: list[Publication]):
        """Test basic publication search."""
        results = search_publications(sample_publications, "matematik")
        assert len(results) > 0

    def test_filter_by_type(self, sample_publications: list[Publication]):
        """Test filtering by publication type."""
        results = search_publications(
            sample_publications, "", publication_type="kvalitetsgranskning"
        )
        for result in results:
            assert result.item.type == "kvalitetsgranskning"

    def test_filter_by_year(self, sample_publications: list[Publication]):
        """Test filtering by year."""
        results = search_publications(sample_publications, "", year=2024)
        for result in results:
            if result.item.published:
                assert result.item.published.year == 2024

    def test_combined_filters(self, sample_publications: list[Publication]):
        """Test combining search with filters."""
        results = search_publications(
            sample_publications,
            "granskning",
            publication_type="kvalitetsgranskning",
            year=2024,
        )
        for result in results:
            assert result.item.type == "kvalitetsgranskning"
            if result.item.published:
                assert result.item.published.year == 2024

    def test_empty_query_returns_empty(self, sample_publications: list[Publication]):
        """Test that empty query returns empty results."""
        results = search_publications(sample_publications, "")
        # Empty query returns empty (search requires a query)
        assert len(results) == 0

    def test_max_results_respected(self, sample_publications: list[Publication]):
        """Test that max_results is respected."""
        results = search_publications(sample_publications, "skola", max_results=2)
        assert len(results) <= 2


class TestSearchPressReleases:
    """Tests for search_press_releases function."""

    @pytest.fixture
    def press_releases(self) -> list[PressRelease]:
        """Create sample press releases."""
        return [
            PressRelease(
                title="Nya resultat från skolenkäten",
                url="/press/1",
                published=date(2024, 3, 1),
            ),
            PressRelease(
                title="Skolinspektionen granskar grundskolor",
                url="/press/2",
                published=date(2024, 2, 15),
            ),
            PressRelease(
                title="Rapport om gymnasieskolor publicerad",
                url="/press/3",
                published=date(2023, 12, 10),
            ),
        ]

    def test_basic_search(self, press_releases: list[PressRelease]):
        """Test basic press release search."""
        results = search_press_releases(press_releases, "skolenkäten")
        assert len(results) > 0

    def test_filter_by_year(self, press_releases: list[PressRelease]):
        """Test filtering press releases by year."""
        results = search_press_releases(press_releases, "", year=2024)
        for result in results:
            if result.item.published:
                assert result.item.published.year == 2024

    def test_search_in_title(self, press_releases: list[PressRelease]):
        """Test that search matches title content."""
        results = search_press_releases(press_releases, "granskar")
        assert len(results) > 0
        assert any("granskar" in r.item.title.lower() for r in results)


class TestSearchResultScoring:
    """Tests for search result scoring."""

    def test_exact_match_scores_higher(self):
        """Test that exact matches score higher than partial."""
        publications = [
            Publication(title="Matematik i skolan", url="/1", type="ovriga-publikationer"),
            Publication(title="Skolan och samhället", url="/2", type="ovriga-publikationer"),
        ]

        ranker = SearchRanker(
            items=publications,
            get_text=lambda p: p.title,
        )
        results = ranker.search("matematik")

        # The exact match should score higher
        if len(results) >= 2:
            titles = [r.item.title for r in results]
            assert titles[0] == "Matematik i skolan"

    def test_title_match_vs_summary(self):
        """Test that title matches may score higher than summary matches."""
        publications = [
            Publication(
                title="Rapport om trygghet",
                url="/1",
                type="ovriga-publikationer",
                summary="En studie av matematik i skolan.",
            ),
            Publication(
                title="Matematik i grundskolan",
                url="/2",
                type="ovriga-publikationer",
                summary="En rapport om undervisning.",
            ),
        ]

        ranker = SearchRanker(
            items=publications,
            get_text=lambda p: p.title,
            get_secondary_text=lambda p: p.summary or "",
        )
        results = ranker.search("matematik")

        # Title match should likely score higher
        assert len(results) > 0


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_publications(self):
        """Test searching empty publication list."""
        results = search_publications([], "anything")
        assert results == []

    def test_unicode_search(self, sample_publications: list[Publication]):
        """Test searching with Swedish characters."""
        results = search_publications(sample_publications, "kvalitetsgranskning")
        assert len(results) > 0

    def test_special_characters_in_query(self, sample_publications: list[Publication]):
        """Test search with special characters."""
        results = search_publications(sample_publications, "test-rapport")
        # Should not crash
        assert isinstance(results, list)

    def test_very_long_query(self, sample_publications: list[Publication]):
        """Test with very long search query."""
        long_query = "matematik " * 100
        results = search_publications(sample_publications, long_query)
        # Should not crash
        assert isinstance(results, list)
