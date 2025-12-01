"""Tests for Pydantic models."""

from datetime import date

import pytest

from src.services.models import (
    Attachment,
    Index,
    PressRelease,
    Publication,
    StatisticsFile,
    PUBLICATION_TYPES,
    THEMES,
)


class TestPublication:
    """Tests for Publication model."""

    def test_create_minimal(self):
        """Test creating a publication with minimal data."""
        pub = Publication(
            title="Test Publication",
            url="/test/url",
            type="ovriga-publikationer",
        )
        assert pub.title == "Test Publication"
        assert pub.url == "/test/url"
        assert pub.published is None
        assert pub.type == "ovriga-publikationer"
        assert pub.attachments == []
        assert pub.themes == []

    def test_create_full(self, sample_publication: Publication):
        """Test creating a publication with full data."""
        assert sample_publication.title.startswith("Kvalitetsgranskning")
        assert sample_publication.type == "kvalitetsgranskning"
        assert len(sample_publication.attachments) == 1
        assert sample_publication.published == date(2024, 3, 15)

    def test_publication_types_valid(self, sample_publication: Publication):
        """Test that publication type is valid."""
        assert sample_publication.type in PUBLICATION_TYPES

    def test_themes_are_strings(self, sample_publication: Publication):
        """Test that themes are strings."""
        for theme in sample_publication.themes:
            assert isinstance(theme, str)

    def test_slug_auto_extracted(self):
        """Test that slug is extracted from URL."""
        pub = Publication(
            title="Test",
            url="/beslut-rapporter/publikationer/2024/test-slug/",
            type="ovriga-publikationer",
        )
        assert pub.slug == "test-slug"


class TestAttachment:
    """Tests for Attachment model."""

    def test_create_attachment(self):
        """Test creating an attachment."""
        att = Attachment(
            name="Report.pdf",
            url="/files/report.pdf",
            file_type="pdf",
        )
        assert att.name == "Report.pdf"
        assert att.file_type == "pdf"

    def test_attachment_without_file_type(self):
        """Test attachment without file type."""
        att = Attachment(
            name="Data.xlsx",
            url="/files/data.xlsx",
        )
        assert att.file_type is None


class TestPressRelease:
    """Tests for PressRelease model."""

    def test_create_press_release(self, sample_press_release: PressRelease):
        """Test creating a press release."""
        assert sample_press_release.title.startswith("Nya resultat")
        assert sample_press_release.published == date(2024, 3, 1)

    def test_slug_auto_extracted(self):
        """Test that slug is extracted from URL."""
        pr = PressRelease(
            title="Test",
            url="/press/2024/test-press-slug/",
        )
        assert pr.slug == "test-press-slug"


class TestStatisticsFile:
    """Tests for StatisticsFile model."""

    def test_create_statistics_file(self, sample_statistics_file: StatisticsFile):
        """Test creating a statistics file."""
        assert sample_statistics_file.year == 2023
        assert sample_statistics_file.category == "tillstand"
        assert sample_statistics_file.file_type == "xlsx"


class TestIndex:
    """Tests for Index model."""

    def test_create_empty_index(self):
        """Test creating an empty index."""
        index = Index(last_updated="2024-01-01T00:00:00")
        assert index.total_items == 0
        assert len(index.publications) == 0
        assert len(index.press_releases) == 0
        assert len(index.statistics_files) == 0

    def test_total_items(self, sample_index: Index):
        """Test total_items property."""
        expected = (
            len(sample_index.publications)
            + len(sample_index.press_releases)
            + len(sample_index.decisions)
            + len(sample_index.statistics_files)
        )
        assert sample_index.total_items == expected

    def test_index_serialization(self, sample_index: Index):
        """Test that index can be serialized to JSON."""
        data = sample_index.model_dump(mode="json")
        assert "publications" in data
        assert "press_releases" in data
        assert "statistics_files" in data
        assert "last_updated" in data

    def test_index_deserialization(self, sample_index: Index):
        """Test that index can be deserialized from JSON."""
        data = sample_index.model_dump(mode="json")
        restored = Index(**data)
        assert restored.total_items == sample_index.total_items


class TestConstants:
    """Tests for constant definitions."""

    def test_publication_types_not_empty(self):
        """Test that publication types are defined."""
        assert len(PUBLICATION_TYPES) > 0

    def test_themes_not_empty(self):
        """Test that themes are defined."""
        assert len(THEMES) > 0

    def test_publication_types_have_swedish_names(self):
        """Test that publication types have Swedish display names."""
        for key, name in PUBLICATION_TYPES.items():
            assert len(name) > 0
            # Keys should be URL-friendly (lowercase, hyphens)
            assert key == key.lower()
