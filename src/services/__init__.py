"""Services for scraping and parsing Skolinspektionen data."""

from .models import (
    Publication,
    PressRelease,
    Decision,
    SearchResult,
    Index,
    StatisticsFile,
    Attachment,
    PUBLICATION_TYPES,
    THEMES,
    DECISION_TYPES,
)
from .scraper import PublicationScraper
from .parser import ContentParser
from .cache import ContentCache, get_content_cache, reset_content_cache
from .rate_limiter import RateLimiter, get_rate_limiter, extract_domain
from .retry import with_retry, RetryConfig, CircuitBreaker
from .delta import DeltaTracker, calculate_items_to_fetch

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
