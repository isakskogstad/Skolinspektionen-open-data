"""Services for scraping and parsing Skolinspektionen data."""

from .cache import ContentCache, get_content_cache, reset_content_cache
from .delta import DeltaTracker, calculate_items_to_fetch
from .models import (
    DECISION_TYPES,
    PUBLICATION_TYPES,
    THEMES,
    Attachment,
    Decision,
    Index,
    PressRelease,
    Publication,
    SearchResult,
    StatisticsFile,
)
from .parser import ContentParser
from .rate_limiter import RateLimiter, extract_domain, get_rate_limiter
from .retry import CircuitBreaker, RetryConfig, with_retry
from .scraper import PublicationScraper

__all__ = [
    # Models
    "Publication",
    "PressRelease",
    "Decision",
    "SearchResult",
    "Index",
    "StatisticsFile",
    "Attachment",
    "PUBLICATION_TYPES",
    "THEMES",
    "DECISION_TYPES",
    # Core services
    "PublicationScraper",
    "ContentParser",
    # Infrastructure
    "ContentCache",
    "get_content_cache",
    "reset_content_cache",
    "RateLimiter",
    "get_rate_limiter",
    "extract_domain",
    "with_retry",
    "RetryConfig",
    "CircuitBreaker",
    "DeltaTracker",
    "calculate_items_to_fetch",
]
