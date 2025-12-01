"""Tests for delta calculation module."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.services.delta import (
    DeltaResult,
    DeltaTracker,
    UpdateMetadata,
    calculate_items_to_fetch,
    days_since,
    load_update_metadata,
    merge_items,
    save_update_metadata,
)


class TestCalculateItemsToFetch:
    """Tests for calculate_items_to_fetch function."""

    def test_first_run_fetches_all(self):
        """Test that first run (no saved data) fetches all items."""
        result = calculate_items_to_fetch(
            online_count=100,
            saved_count=0,
            days_since_update=0,
        )
        assert result.items_to_fetch == 100
        assert result.is_full_scrape == True

    def test_new_items_detected(self):
        """Test fetching when new items detected."""
        result = calculate_items_to_fetch(
            online_count=105,
            saved_count=100,
            days_since_update=1,
        )
        # Should fetch diff + buffer + daily_factor
        assert result.items_to_fetch > 5
        assert result.new_items_estimate == 5

    def test_items_removed_triggers_full_scrape(self):
        """Test that item removal triggers full scrape."""
        result = calculate_items_to_fetch(
            online_count=90,
            saved_count=100,
            days_since_update=1,
        )
        assert result.is_full_scrape == True
        assert "removed" in result.reason

    def test_stale_data_triggers_full_scrape(self):
        """Test that very old data triggers full scrape."""
        result = calculate_items_to_fetch(
            online_count=100,
            saved_count=100,
            days_since_update=35,  # > 30 days
        )
        assert result.is_full_scrape == True
        assert "stale" in result.reason

    def test_incremental_update(self):
        """Test incremental update calculation."""
        result = calculate_items_to_fetch(
            online_count=105,
            saved_count=100,
            days_since_update=2,
        )
        # Should be incremental if not too many items
        assert result.new_items_estimate == 5


class TestDeltaResult:
    """Tests for DeltaResult dataclass."""

    def test_creation(self):
        """Test creating a DeltaResult."""
        result = DeltaResult(
            items_to_fetch=10,
            reason="test reason",
            is_full_scrape=False,
            new_items_estimate=5,
        )
        assert result.items_to_fetch == 10
        assert result.reason == "test reason"
        assert result.is_full_scrape == False
        assert result.new_items_estimate == 5

    def test_description_property(self):
        """Test description property."""
        result = DeltaResult(
            items_to_fetch=10,
            reason="test",
            is_full_scrape=False,
        )
        assert "Incremental" in result.description

        full_result = DeltaResult(
            items_to_fetch=100,
            reason="test",
            is_full_scrape=True,
        )
        assert "Full" in full_result.description


class TestUpdateMetadata:
    """Tests for UpdateMetadata dataclass."""

    def test_creation(self):
        """Test creating UpdateMetadata."""
        meta = UpdateMetadata(
            latest_updated=datetime.now(),
            items={"publications": 100},
        )
        assert meta.items["publications"] == 100

    def test_to_dict(self):
        """Test conversion to dictionary."""
        meta = UpdateMetadata(
            latest_updated=datetime.now(),
            items={"publications": 100},
        )
        data = meta.to_dict()
        assert "latest_updated" in data
        assert data["items"]["publications"] == 100

    def test_from_dict(self):
        """Test creation from dictionary."""
        now = datetime.now()
        data = {
            "latest_updated": now.isoformat(),
            "items": {"publications": 100},
        }
        meta = UpdateMetadata.from_dict(data)
        assert meta.items["publications"] == 100


class TestDeltaTracker:
    """Tests for DeltaTracker."""

    @pytest.fixture
    def tracker(self, temp_dir: Path) -> DeltaTracker:
        """Create a delta tracker for testing."""
        return DeltaTracker(metadata_path=temp_dir / "delta_state.json")

    @pytest.mark.asyncio
    async def test_load_no_file(self, tracker: DeltaTracker):
        """Test loading when no file exists."""
        await tracker.load()
        assert tracker.metadata is None

    @pytest.mark.asyncio
    async def test_calculate_delta_no_metadata(self, tracker: DeltaTracker):
        """Test delta calculation with no previous metadata."""
        await tracker.load()
        result = tracker.calculate_delta("publications", online_count=50)
        assert result.is_full_scrape == True
        assert result.items_to_fetch == 50

    @pytest.mark.asyncio
    async def test_record_and_save(self, tracker: DeltaTracker):
        """Test recording update and saving."""
        await tracker.load()

        # Record update
        tracker.record_update("publications", count=100)
        assert tracker.metadata is not None
        assert tracker.metadata.items["publications"] == 100

        # Save and reload
        await tracker.save()

        tracker2 = DeltaTracker(metadata_path=tracker.metadata_path)
        await tracker2.load()
        assert tracker2.metadata is not None
        assert tracker2.metadata.items["publications"] == 100

    @pytest.mark.asyncio
    async def test_get_item_count(self, tracker: DeltaTracker):
        """Test getting item count."""
        await tracker.load()
        assert tracker.get_item_count("publications") == 0

        tracker.record_update("publications", count=100)
        assert tracker.get_item_count("publications") == 100

    @pytest.mark.asyncio
    async def test_get_last_update(self, tracker: DeltaTracker):
        """Test getting last update time."""
        await tracker.load()
        assert tracker.get_last_update() is None

        tracker.record_update("publications", count=100)
        assert tracker.get_last_update() is not None


class TestDaysSince:
    """Tests for days_since function."""

    def test_recent_date(self):
        """Test with recent date."""
        recent = datetime.now() - timedelta(hours=1)
        assert days_since(recent) == 0

    def test_old_date(self):
        """Test with old date."""
        old = datetime.now() - timedelta(days=10)
        result = days_since(old)
        assert 9 <= result <= 11


class TestMergeItems:
    """Tests for merge_items function."""

    def test_add_new_items(self):
        """Test adding new items."""

        class Item:
            def __init__(self, url):
                self.url = url

        existing = [Item("/a"), Item("/b")]
        new = [Item("/c"), Item("/d")]

        merged, added, updated = merge_items(existing, new, key_field="url")
        assert len(merged) == 4
        assert added == 2
        assert updated == 0

    def test_update_existing_items(self):
        """Test updating existing items."""

        class Item:
            def __init__(self, url, value=0):
                self.url = url
                self.value = value

        existing = [Item("/a", 1), Item("/b", 2)]
        new = [Item("/a", 10)]  # Update /a

        merged, added, updated = merge_items(existing, new, key_field="url")
        assert len(merged) == 2
        assert added == 0
        assert updated == 1
