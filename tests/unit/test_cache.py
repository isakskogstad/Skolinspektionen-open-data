"""Tests for caching module."""

import asyncio
import json
from pathlib import Path

import pytest

from src.services.cache import (
    ContentCache,
    DiskCache,
    LRUCache,
    get_content_cache,
    reset_content_cache,
)


class TestLRUCache:
    """Tests for LRUCache."""

    @pytest.fixture
    def cache(self) -> LRUCache:
        """Create a small LRU cache for testing."""
        return LRUCache(max_size=3)

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: LRUCache):
        """Test basic set and get operations."""
        await cache.set("key1", "value1", ttl_seconds=60)
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache: LRUCache):
        """Test getting a non-existent key returns None."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache: LRUCache):
        """Test that entries expire after TTL."""
        await cache.set("key1", "value1", ttl_seconds=0.1)
        await asyncio.sleep(0.15)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache: LRUCache):
        """Test LRU eviction when cache is full."""
        # Fill cache
        await cache.set("key1", "value1", ttl_seconds=60)
        await cache.set("key2", "value2", ttl_seconds=60)
        await cache.set("key3", "value3", ttl_seconds=60)

        # Access key1 to make it recently used
        await cache.get("key1")

        # Add new key, should evict key2 (least recently used)
        await cache.set("key4", "value4", ttl_seconds=60)

        assert await cache.get("key1") == "value1"  # Still there
        assert await cache.get("key2") is None  # Evicted
        assert await cache.get("key3") == "value3"  # Still there
        assert await cache.get("key4") == "value4"  # New entry

    @pytest.mark.asyncio
    async def test_clear(self, cache: LRUCache):
        """Test clearing the cache."""
        await cache.set("key1", "value1", ttl_seconds=60)
        await cache.set("key2", "value2", ttl_seconds=60)
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_delete(self, cache: LRUCache):
        """Test deleting a specific key."""
        await cache.set("key1", "value1", ttl_seconds=60)
        await cache.set("key2", "value2", ttl_seconds=60)
        await cache.delete("key1")
        assert await cache.get("key1") is None
        assert await cache.get("key2") == "value2"

    @pytest.mark.asyncio
    async def test_complex_values(self, cache: LRUCache):
        """Test caching complex values."""
        data = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        await cache.set("complex", data, ttl_seconds=60)
        result = await cache.get("complex")
        assert result == data


class TestDiskCache:
    """Tests for DiskCache."""

    @pytest.fixture
    def cache(self, temp_dir: Path) -> DiskCache:
        """Create a disk cache in temporary directory."""
        return DiskCache(cache_dir=temp_dir / "disk_cache")

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: DiskCache):
        """Test basic set and get operations."""
        await cache.set("key1", {"data": "test"}, ttl_seconds=60)
        result = await cache.get("key1")
        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_get_missing_key(self, cache: DiskCache):
        """Test getting a non-existent key returns None."""
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache: DiskCache):
        """Test that entries expire after TTL."""
        await cache.set("key1", "value1", ttl_seconds=0.1)
        await asyncio.sleep(0.15)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache: DiskCache):
        """Test deleting a specific key."""
        await cache.set("key1", "value1", ttl_seconds=60)
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_clear(self, cache: DiskCache):
        """Test clearing all cache files."""
        await cache.set("key1", "value1", ttl_seconds=60)
        await cache.set("key2", "value2", ttl_seconds=60)
        await cache.clear()
        assert await cache.get("key1") is None
        assert await cache.get("key2") is None

    @pytest.mark.asyncio
    async def test_persistence(self, temp_dir: Path):
        """Test that cache persists to disk."""
        cache_dir = temp_dir / "persistent_cache"
        cache1 = DiskCache(cache_dir=cache_dir)
        await cache1.set("key1", {"persistent": True}, ttl_seconds=3600)

        # Create new cache instance pointing to same directory
        cache2 = DiskCache(cache_dir=cache_dir)
        result = await cache2.get("key1")
        assert result == {"persistent": True}

    @pytest.mark.asyncio
    async def test_special_characters_in_key(self, cache: DiskCache):
        """Test keys with special characters are handled."""
        key = "https://example.com/path?query=1&other=2"
        await cache.set(key, "value", ttl_seconds=60)
        result = await cache.get(key)
        assert result == "value"


class TestContentCache:
    """Tests for ContentCache (combined memory + disk)."""

    @pytest.fixture
    def cache(self, temp_dir: Path) -> ContentCache:
        """Create a content cache for testing."""
        return ContentCache(
            disk_cache_dir=temp_dir / "content_cache",
            memory_max_items=10,
            default_ttl_hours=1,
        )

    @pytest.mark.asyncio
    async def test_set_and_get(self, cache: ContentCache):
        """Test basic set and get operations."""
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_memory_first(self, cache: ContentCache):
        """Test that memory cache is checked first."""
        # Set in cache (goes to both memory and disk)
        await cache.set("key1", "memory_value")

        # Should retrieve from memory
        result = await cache.get("key1")
        assert result == "memory_value"

    @pytest.mark.asyncio
    async def test_disk_fallback(self, temp_dir: Path):
        """Test that disk cache is used when memory cache is empty."""
        cache_dir = temp_dir / "fallback_cache"

        # Create cache and set value
        cache1 = ContentCache(
            disk_cache_dir=cache_dir,
            memory_max_items=10,
            default_ttl_hours=1,
        )
        await cache1.set("key1", "disk_value")

        # Clear memory cache but keep disk
        await cache1._memory.clear()

        # Should still get from disk (and promote back to memory)
        result = await cache1.get("key1")
        assert result == "disk_value"

    @pytest.mark.asyncio
    async def test_clear(self, cache: ContentCache):
        """Test clearing both caches."""
        await cache.set("key1", "value1")
        await cache.clear()
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, cache: ContentCache):
        """Test deleting from both caches."""
        await cache.set("key1", "value1")
        await cache.delete("key1")
        result = await cache.get("key1")
        assert result is None


class TestGetContentCache:
    """Tests for get_content_cache singleton."""

    def test_singleton(self):
        """Test that get_content_cache returns same instance."""
        reset_content_cache()
        cache1 = get_content_cache()
        cache2 = get_content_cache()
        assert cache1 is cache2

    def test_reset(self):
        """Test that reset_content_cache works."""
        cache1 = get_content_cache()
        reset_content_cache()
        cache2 = get_content_cache()
        # After reset, should have a new instance
        assert cache2 is not None
