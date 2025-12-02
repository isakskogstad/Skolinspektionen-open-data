"""Tests for rate limiting module."""

import asyncio
import time

import pytest

from src.services.rate_limiter import (
    RateLimiter,
    TokenBucket,
    extract_domain,
    get_rate_limiter,
    reset_rate_limiter,
)


class TestTokenBucket:
    """Tests for TokenBucket algorithm."""

    @pytest.fixture
    def bucket(self) -> TokenBucket:
        """Create a token bucket for testing."""
        return TokenBucket(rate=10.0, capacity=5)

    @pytest.mark.asyncio
    async def test_initial_tokens(self, bucket: TokenBucket):
        """Test that bucket starts with full capacity."""
        # Should be able to immediately acquire capacity tokens
        for _ in range(5):
            wait_time = await bucket.acquire(1)
            assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_token_refill(self):
        """Test that tokens refill over time."""
        bucket = TokenBucket(rate=100.0, capacity=1)  # Fast rate for testing

        # Consume the token
        await bucket.acquire(1)

        # Wait for refill
        await asyncio.sleep(0.02)  # 20ms should give us ~2 tokens at 100/s

        # Should be able to acquire again
        wait_time = await bucket.acquire(1)
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_wait_when_empty(self):
        """Test that acquire waits when bucket is empty."""
        bucket = TokenBucket(rate=10.0, capacity=1)

        # Consume the token
        await bucket.acquire(1)

        # Next acquire should require waiting
        start = time.time()
        await bucket.acquire(1)
        elapsed = time.time() - start

        # Should have waited approximately 0.1s (1 token at 10/s)
        assert elapsed >= 0.05  # Allow some margin

    @pytest.mark.asyncio
    async def test_throttle_context_manager(self, bucket: TokenBucket):
        """Test the throttle context manager."""
        async with bucket.throttle(1):
            pass  # Should complete without error

    @pytest.mark.asyncio
    async def test_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        bucket = TokenBucket(rate=100.0, capacity=10)

        # Acquire 5 tokens
        wait_time = await bucket.acquire(5)
        assert wait_time == 0.0

        # Acquire 5 more
        wait_time = await bucket.acquire(5)
        assert wait_time == 0.0

        # Next should require waiting
        start = time.time()
        await bucket.acquire(1)
        elapsed = time.time() - start
        assert elapsed >= 0.005  # At least 5ms at 100/s

    @pytest.mark.asyncio
    async def test_available_tokens_property(self, bucket: TokenBucket):
        """Test available_tokens property."""
        # Should start at capacity
        assert bucket.available_tokens <= bucket.capacity


class TestRateLimiter:
    """Tests for RateLimiter (per-domain)."""

    @pytest.fixture
    def limiter(self) -> RateLimiter:
        """Create a rate limiter for testing."""
        return RateLimiter(default_rate=100.0, default_capacity=10)

    @pytest.mark.asyncio
    async def test_per_domain_limiting(self, limiter: RateLimiter):
        """Test that each domain has its own bucket."""
        async with limiter.limit("domain1.com"):
            pass
        async with limiter.limit("domain2.com"):
            pass
        # Both should complete immediately (separate buckets)

    @pytest.mark.asyncio
    async def test_same_domain_shares_bucket(self, limiter: RateLimiter):
        """Test that same domain uses same bucket."""
        # Exhaust bucket for domain1
        for _ in range(10):
            async with limiter.limit("domain1.com"):
                pass

        # Next request should be throttled
        start = time.time()
        async with limiter.limit("domain1.com"):
            pass
        elapsed = time.time() - start
        assert elapsed >= 0.005  # Should have waited

    @pytest.mark.asyncio
    async def test_acquire_method(self, limiter: RateLimiter):
        """Test direct acquire method."""
        wait_time = await limiter.acquire("test.com", tokens=1)
        assert wait_time >= 0.0

    def test_get_status(self, limiter: RateLimiter):
        """Test get_status method."""
        status = limiter.get_status()
        assert isinstance(status, dict)


class TestGetRateLimiter:
    """Tests for get_rate_limiter singleton."""

    def test_singleton(self):
        """Test that get_rate_limiter returns same instance."""
        reset_rate_limiter()
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter1 is limiter2

    def test_reset(self):
        """Test that reset_rate_limiter works."""
        get_rate_limiter()
        reset_rate_limiter()
        limiter2 = get_rate_limiter()
        assert limiter2 is not None


class TestExtractDomain:
    """Tests for extract_domain function."""

    def test_full_url(self):
        """Test extracting domain from full URL."""
        assert extract_domain("https://www.example.com/path") == "www.example.com"

    def test_http_url(self):
        """Test extracting domain from HTTP URL."""
        assert extract_domain("http://example.com/path") == "example.com"

    def test_relative_path(self):
        """Test relative path returns default."""
        assert extract_domain("/path/to/resource") == "default"


class TestConcurrentAccess:
    """Tests for concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test that concurrent requests are properly rate limited."""
        bucket = TokenBucket(rate=10.0, capacity=5)

        async def make_request():
            await bucket.acquire(1)
            return time.time()

        # Make 10 concurrent requests
        start = time.time()
        await asyncio.gather(*[make_request() for _ in range(10)])
        end = time.time()

        # First 5 should complete immediately (capacity)
        # Next 5 should be spread over ~0.5s (5 tokens at 10/s)
        # Total time should be at least 0.4s
        assert end - start >= 0.4
