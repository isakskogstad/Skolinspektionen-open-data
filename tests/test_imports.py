"""Test that all modules can be imported."""

import pytest


def test_import_models():
    """Test that models can be imported."""
    from src.services.models import (
        Publication,
        PressRelease,
        Decision,
        Index,
        StatisticsFile,
        Attachment,
        PUBLICATION_TYPES,
        THEMES,
    )

    assert Publication is not None
    assert len(PUBLICATION_TYPES) > 0
    assert len(THEMES) > 0


def test_import_scraper():
    """Test that scraper can be imported."""
    from src.services.scraper import PublicationScraper

    assert PublicationScraper is not None


def test_import_parser():
    """Test that parser can be imported."""
    from src.services.parser import ContentParser

    assert ContentParser is not None


def test_import_mcp_server():
    """Test that MCP server can be imported."""
    from src.mcp.server import create_server, server

    assert server is not None
    assert create_server is not None


def test_create_publication():
    """Test creating a Publication model."""
    from src.services.models import Publication

    pub = Publication(
        title="Test Report",
        url="/beslut-rapporter/publikationer/kvalitetsgranskning/2024/test/",
        type="kvalitetsgranskning",
    )

    assert pub.title == "Test Report"
    assert pub.slug == "test"
    assert pub.type == "kvalitetsgranskning"


def test_create_index():
    """Test creating an Index model."""
    from src.services.models import Index, Publication

    pub = Publication(
        title="Test",
        url="/test/",
        type="kvalitetsgranskning",
    )

    index = Index(publications=[pub])
    assert index.total_items == 1
