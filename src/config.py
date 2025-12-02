"""Configuration management for Skolinspektionen DATA."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables with SI_ prefix.
    Example: SI_BASE_URL=https://example.com
    """

    model_config = SettingsConfigDict(
        env_prefix="SI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base URLs
    base_url: str = "https://www.skolinspektionen.se"
    publication_search_path: str = "/beslut-rapporter/publikationssok/"
    press_releases_path: str = "/om-oss/press/pressmeddelanden/"

    # HTTP settings
    http_timeout: float = 30.0
    user_agent: str = (
        "SkolinspektionenData/0.1 (https://github.com/civictechsweden/skolinspektionen-data)"
    )

    # Rate limiting
    rate_limit_per_second: float = 2.0
    rate_limit_burst: int = 5

    # Retry settings
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    retry_initial_delay: float = 1.0

    # Cache settings
    cache_ttl_hours: int = 24
    cache_max_memory_items: int = 50
    cache_dir: Optional[Path] = None

    # Scraping settings
    max_pages_per_scrape: int = 50
    scrape_delay_seconds: float = 0.5

    # Data paths
    data_dir: Path = Path("data/api")
    index_filename: str = "index.json"
    latest_updated_filename: str = "latest_updated.json"

    @property
    def publication_search_url(self) -> str:
        """Full URL for publication search."""
        return f"{self.base_url}{self.publication_search_path}"

    @property
    def press_releases_url(self) -> str:
        """Full URL for press releases."""
        return f"{self.base_url}{self.press_releases_path}"

    @property
    def index_path(self) -> Path:
        """Full path to index file."""
        return self.data_dir / self.index_filename

    @property
    def latest_updated_path(self) -> Path:
        """Full path to latest_updated file."""
        return self.data_dir / self.latest_updated_filename

    @property
    def effective_cache_dir(self) -> Path:
        """Cache directory, defaulting to data_dir/.cache if not set."""
        if self.cache_dir:
            return self.cache_dir
        return self.data_dir / ".cache"


# Global settings instance (lazy-loaded)
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None
