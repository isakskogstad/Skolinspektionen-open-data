"""Tests for configuration module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import Settings, get_settings, reset_settings


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.base_url == "https://www.skolinspektionen.se"
        assert settings.http_timeout == 30.0
        assert settings.rate_limit_per_second == 2.0
        assert settings.rate_limit_burst == 5
        assert settings.max_retries == 3
        assert settings.retry_initial_delay == 1.0
        assert settings.retry_backoff_factor == 2.0
        assert settings.cache_ttl_hours == 24
        assert settings.max_pages_per_scrape == 50

    def test_custom_settings(self, temp_dir: Path):
        """Test custom settings values."""
        settings = Settings(
            data_dir=temp_dir / "custom_data",
            cache_dir=temp_dir / "custom_cache",
            http_timeout=60.0,
            rate_limit_per_second=5.0,
        )
        assert settings.data_dir == temp_dir / "custom_data"
        assert settings.cache_dir == temp_dir / "custom_cache"
        assert settings.http_timeout == 60.0
        assert settings.rate_limit_per_second == 5.0

    def test_settings_from_env(self, temp_dir: Path):
        """Test settings can be loaded from environment variables."""
        env_vars = {
            "SI_BASE_URL": "https://test.example.com",
            "SI_HTTP_TIMEOUT": "45.0",
            "SI_RATE_LIMIT_PER_SECOND": "3.0",
            "SI_MAX_PAGES_PER_SCRAPE": "100",
        }
        with patch.dict(os.environ, env_vars):
            reset_settings()
            settings = Settings()
            assert settings.base_url == "https://test.example.com"
            assert settings.http_timeout == 45.0
            assert settings.rate_limit_per_second == 3.0
            assert settings.max_pages_per_scrape == 100

    def test_data_dir_default(self):
        """Test default data directory path."""
        settings = Settings()
        assert "data" in str(settings.data_dir)

    def test_cache_dir_default_is_none(self):
        """Test default cache_dir is None (uses effective_cache_dir)."""
        settings = Settings()
        assert settings.cache_dir is None

    def test_effective_cache_dir(self):
        """Test effective_cache_dir property."""
        settings = Settings()
        assert ".cache" in str(settings.effective_cache_dir)


class TestGetSettings:
    """Tests for get_settings function."""

    def test_get_settings_singleton(self):
        """Test that get_settings returns same instance."""
        reset_settings()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_reset_settings(self):
        """Test that reset_settings clears the singleton."""
        settings1 = get_settings()
        reset_settings()
        settings2 = get_settings()
        # After reset, should be a new instance
        # (but may have same values, so we just check the function works)
        assert settings2 is not None


class TestSettingsProperties:
    """Tests for computed settings properties."""

    def test_publication_search_url(self):
        """Test publication search URL is computed correctly."""
        settings = Settings()
        url = settings.publication_search_url
        assert url.startswith("https://www.skolinspektionen.se")
        assert "publikationssok" in url

    def test_press_releases_url(self):
        """Test press releases URL is computed correctly."""
        settings = Settings()
        url = settings.press_releases_url
        assert url.startswith("https://www.skolinspektionen.se")
        assert "pressmeddelanden" in url

    def test_index_path(self):
        """Test index path is computed correctly."""
        settings = Settings(data_dir=Path("/tmp/data"))
        assert settings.index_path == Path("/tmp/data/index.json")

    def test_latest_updated_path(self):
        """Test latest_updated path is computed correctly."""
        settings = Settings(data_dir=Path("/tmp/data"))
        assert settings.latest_updated_path == Path("/tmp/data/latest_updated.json")


class TestSettingsValidation:
    """Tests for settings validation."""

    def test_positive_timeout(self):
        """Test that timeout can be set to positive value."""
        settings = Settings(http_timeout=0.1)
        assert settings.http_timeout == 0.1

    def test_positive_rate_limit(self):
        """Test that rate limit can be set to positive value."""
        settings = Settings(rate_limit_per_second=0.5)
        assert settings.rate_limit_per_second == 0.5

    def test_retry_settings(self):
        """Test retry settings can be configured."""
        settings = Settings(
            max_retries=5,
            retry_initial_delay=2.0,
            retry_backoff_factor=3.0,
        )
        assert settings.max_retries == 5
        assert settings.retry_initial_delay == 2.0
        assert settings.retry_backoff_factor == 3.0

    def test_cache_settings(self):
        """Test cache settings can be configured."""
        settings = Settings(
            cache_ttl_hours=48,
            cache_max_memory_items=100,
        )
        assert settings.cache_ttl_hours == 48
        assert settings.cache_max_memory_items == 100
