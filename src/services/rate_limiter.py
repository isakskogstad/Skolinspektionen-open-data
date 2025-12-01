"""Rate limiting using token bucket algorithm.

Provides async-compatible rate limiting to respect server resources
and avoid IP blocking when scraping.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Optional

from rich.console import Console

from ..config import get_settings

console = Console()


class TokenBucket:
    """Token bucket rate limiter for controlling request rates.

    The token bucket algorithm allows for burst capacity while maintaining
    an average rate limit. Tokens are added at a constant rate up to a
    maximum (burst) capacity.

    Example:
        # Allow 2 requests/second with burst of 5
        bucket = TokenBucket(rate=2.0, capacity=5)

        async with bucket.acquire():
            await fetch_page(url)
    """

    def __init__(
        self,
        rate: float = 2.0,
        capacity: int = 5,
        name: str = "default",
    ):
        """Initialize the token bucket.

        Args:
            rate: Tokens added per second (requests/second)
            capacity: Maximum bucket capacity (burst size)
            name: Name for logging purposes
        """
        self.rate = rate
        self.capacity = capacity
        self.name = name
        self.tokens = float(capacity)  # Start with full bucket
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    def _add_tokens(self) -> None:
        """Add tokens based on elapsed time since last update."""
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        async with self._lock:
            self._add_tokens()

            wait_time = 0.0
            if self.tokens < tokens:
                # Calculate wait time needed
                deficit = tokens - self.tokens
                wait_time = deficit / self.rate
                console.print(
                    f"[dim]Rate limiter '{self.name}': waiting {wait_time:.2f}s[/dim]"
                )
                await asyncio.sleep(wait_time)
                self._add_tokens()

            self.tokens -= tokens
            return wait_time

    @asynccontextmanager
    async def throttle(self, tokens: int = 1):
        """Context manager for rate-limited operations.

        Usage:
            async with bucket.throttle():
                await do_something()
        """
        await self.acquire(tokens)
        yield

    @property
    def available_tokens(self) -> float:
        """Get current available tokens (without modifying state)."""
        elapsed = time.monotonic() - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


class RateLimiter:
    """Rate limiter manager with support for multiple domains.

    Maintains separate rate limits per domain to avoid overwhelming
    any single server while maximizing overall throughput.

    Example:
        limiter = RateLimiter()

        async with limiter.limit("skolinspektionen.se"):
            await fetch_from_skolinspektionen()

        async with limiter.limit("skolverket.se"):
            await fetch_from_skolverket()
    """

    def __init__(
        self,
        default_rate: Optional[float] = None,
        default_capacity: Optional[int] = None,
    ):
        """Initialize the rate limiter manager.

        Args:
            default_rate: Default rate limit per second
            default_capacity: Default burst capacity
        """
        settings = get_settings()
        self.default_rate = default_rate or settings.rate_limit_per_second
        self.default_capacity = default_capacity or settings.rate_limit_burst
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def _get_bucket(self, domain: str) -> TokenBucket:
        """Get or create a bucket for a domain."""
        async with self._lock:
            if domain not in self._buckets:
                self._buckets[domain] = TokenBucket(
                    rate=self.default_rate,
                    capacity=self.default_capacity,
                    name=domain,
                )
            return self._buckets[domain]

    @asynccontextmanager
    async def limit(self, domain: str, tokens: int = 1):
        """Context manager for rate-limited operations on a domain.

        Args:
            domain: The domain being accessed
            tokens: Number of tokens to consume

        Usage:
            async with limiter.limit("example.com"):
                await fetch_page("https://example.com/page")
        """
        bucket = await self._get_bucket(domain)
        async with bucket.throttle(tokens):
            yield

    async def acquire(self, domain: str, tokens: int = 1) -> float:
        """Acquire tokens for a domain.

        Args:
            domain: The domain being accessed
            tokens: Number of tokens to acquire

        Returns:
            Time waited in seconds
        """
        bucket = await self._get_bucket(domain)
        return await bucket.acquire(tokens)

    def get_status(self) -> dict[str, dict]:
        """Get status of all rate limit buckets.

        Returns:
            Dictionary mapping domain to bucket status
        """
        return {
            domain: {
                "available_tokens": bucket.available_tokens,
                "rate": bucket.rate,
                "capacity": bucket.capacity,
            }
            for domain, bucket in self._buckets.items()
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the global rate limiter (useful for testing)."""
    global _rate_limiter
    _rate_limiter = None


def extract_domain(url: str) -> str:
    """Extract domain from a URL for rate limiting.

    Args:
        url: Full URL or path

    Returns:
        Domain name or 'default' for relative paths
    """
    from urllib.parse import urlparse

    if url.startswith(("http://", "https://")):
        parsed = urlparse(url)
        return parsed.netloc or "default"
    return "default"
