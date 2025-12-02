"""Delta calculation for incremental updates.

Inspired by the g0vse project pattern - only fetch what's changed
to minimize server load and scraping time.
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import aiofiles
from rich.console import Console

from ..config import get_settings

console = Console()


@dataclass
class UpdateMetadata:
    """Metadata about the last successful update."""

    latest_updated: datetime
    items: dict[str, int] = field(default_factory=dict)
    last_scraped_urls: list[str] = field(default_factory=list)
    version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "latest_updated": self.latest_updated.isoformat(),
            "items": self.items,
            "last_scraped_urls": self.last_scraped_urls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UpdateMetadata":
        """Create from dictionary."""
        return cls(
            version=data.get("version", "1.0"),
            latest_updated=datetime.fromisoformat(data["latest_updated"]),
            items=data.get("items", {}),
            last_scraped_urls=data.get("last_scraped_urls", []),
        )


@dataclass
class DeltaResult:
    """Result of delta calculation."""

    items_to_fetch: int
    reason: str
    is_full_scrape: bool = False
    new_items_estimate: int = 0
    days_since_update: int = 0

    @property
    def description(self) -> str:
        """Human-readable description."""
        if self.is_full_scrape:
            return f"Full scrape needed: {self.reason}"
        return (
            f"Incremental update: {self.items_to_fetch} items "
            f"({self.new_items_estimate} new, {self.reason})"
        )


def calculate_items_to_fetch(
    online_count: int,
    saved_count: int,
    days_since_update: int,
    buffer: int = 10,
    daily_factor: int = 2,
) -> DeltaResult:
    """Calculate how many items to fetch based on changes.

    Uses a smart algorithm inspired by g0vse to minimize redundant scraping
    while ensuring no items are missed.

    Args:
        online_count: Current total count from website
        saved_count: Count in our saved index
        days_since_update: Days since last successful update
        buffer: Safety margin for edge cases
        daily_factor: Expected new items per day

    Returns:
        DeltaResult with recommended fetch count and reasoning
    """
    # New items (positive) or deleted items (negative)
    count_diff = online_count - saved_count

    if count_diff < 0:
        # Items were removed - need full rescrape to sync
        return DeltaResult(
            items_to_fetch=online_count,
            reason="items removed from source",
            is_full_scrape=True,
            new_items_estimate=0,
            days_since_update=days_since_update,
        )

    if days_since_update > 30:
        # Too long since update - do a full rescrape
        return DeltaResult(
            items_to_fetch=online_count,
            reason=f"stale data ({days_since_update} days)",
            is_full_scrape=True,
            new_items_estimate=count_diff,
            days_since_update=days_since_update,
        )

    if saved_count == 0:
        # First run - fetch everything
        return DeltaResult(
            items_to_fetch=online_count,
            reason="initial scrape",
            is_full_scrape=True,
            new_items_estimate=online_count,
            days_since_update=days_since_update,
        )

    # Calculate incremental fetch count
    # abs(diff) handles both additions and modifications
    # daily_factor * days accounts for potential updates to existing items
    # buffer provides safety margin
    items_to_fetch = abs(count_diff) + buffer + (daily_factor * days_since_update)

    # Don't fetch more than total available
    items_to_fetch = min(items_to_fetch, online_count)

    # If we'd fetch most items anyway, just do a full scrape
    if items_to_fetch > online_count * 0.7:
        return DeltaResult(
            items_to_fetch=online_count,
            reason="incremental would fetch >70%",
            is_full_scrape=True,
            new_items_estimate=count_diff,
            days_since_update=days_since_update,
        )

    return DeltaResult(
        items_to_fetch=items_to_fetch,
        reason=f"+{count_diff} new, {days_since_update}d stale",
        is_full_scrape=False,
        new_items_estimate=count_diff,
        days_since_update=days_since_update,
    )


async def load_update_metadata(path: Optional[Path] = None) -> Optional[UpdateMetadata]:
    """Load update metadata from file.

    Args:
        path: Path to metadata file (uses settings default if not provided)

    Returns:
        UpdateMetadata if file exists and is valid, None otherwise
    """
    settings = get_settings()
    metadata_path = path or settings.latest_updated_path

    if not metadata_path.exists():
        console.print("[dim]No previous update metadata found[/dim]")
        return None

    try:
        async with aiofiles.open(metadata_path, "r", encoding="utf-8") as f:
            content = await f.read()

        data = json.loads(content)
        metadata = UpdateMetadata.from_dict(data)
        console.print(f"[dim]Loaded metadata from {metadata.latest_updated}[/dim]")
        return metadata

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        console.print(f"[yellow]Failed to load metadata: {e}[/yellow]")
        return None


async def save_update_metadata(
    metadata: UpdateMetadata,
    path: Optional[Path] = None,
) -> None:
    """Save update metadata to file.

    Args:
        metadata: Metadata to save
        path: Path to save to (uses settings default if not provided)
    """
    settings = get_settings()
    metadata_path = path or settings.latest_updated_path

    # Ensure directory exists
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(metadata_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2))

    console.print(f"[green]Saved update metadata to {metadata_path}[/green]")


def days_since(dt: datetime) -> int:
    """Calculate days since a datetime."""
    if dt.tzinfo is None:
        now = datetime.now()
    else:
        from datetime import timezone

        now = datetime.now(timezone.utc)

    delta = now - dt
    return max(0, delta.days)


def filter_items_since(
    items: list[Any],
    since_date: Optional[date],
    date_field: str = "published",
) -> list[Any]:
    """Filter items to only those published since a date.

    Args:
        items: List of items with date field
        since_date: Only include items after this date
        date_field: Name of the date attribute

    Returns:
        Filtered list of items
    """
    if since_date is None:
        return items

    filtered = []
    for item in items:
        item_date = getattr(item, date_field, None)
        if item_date is None:
            # Include items without dates (can't determine age)
            filtered.append(item)
        elif isinstance(item_date, datetime):
            if item_date.date() >= since_date:
                filtered.append(item)
        elif isinstance(item_date, date):
            if item_date >= since_date:
                filtered.append(item)

    return filtered


def merge_items(
    existing: list[Any],
    new: list[Any],
    key_field: str = "url",
) -> tuple[list[Any], int, int]:
    """Merge new items into existing list, updating duplicates.

    Args:
        existing: Current list of items
        new: New items to merge in
        key_field: Field to use as unique key

    Returns:
        Tuple of (merged list, items added, items updated)
    """
    # Build lookup of existing items
    existing_by_key = {getattr(item, key_field): item for item in existing}

    added = 0
    updated = 0

    for item in new:
        key = getattr(item, key_field)
        if key in existing_by_key:
            # Update existing item
            existing_by_key[key] = item
            updated += 1
        else:
            # Add new item
            existing_by_key[key] = item
            added += 1

    merged = list(existing_by_key.values())

    console.print(f"[green]Merged: {added} added, {updated} updated[/green]")
    return merged, added, updated


class DeltaTracker:
    """Track and manage incremental updates.

    Provides a higher-level interface for managing delta updates
    across multiple item types.

    Usage:
        tracker = DeltaTracker()
        await tracker.load()

        delta = tracker.calculate_delta("publications", online_count=350)
        if delta.items_to_fetch > 0:
            # Fetch items...
            await tracker.record_update("publications", new_count=350)

        await tracker.save()
    """

    def __init__(self, metadata_path: Optional[Path] = None):
        """Initialize delta tracker.

        Args:
            metadata_path: Path to metadata file
        """
        settings = get_settings()
        self.metadata_path = metadata_path or settings.latest_updated_path
        self.metadata: Optional[UpdateMetadata] = None

    async def load(self) -> None:
        """Load metadata from disk."""
        self.metadata = await load_update_metadata(self.metadata_path)

    async def save(self) -> None:
        """Save metadata to disk."""
        if self.metadata:
            await save_update_metadata(self.metadata, self.metadata_path)

    def calculate_delta(
        self,
        item_type: str,
        online_count: int,
        buffer: int = 10,
        daily_factor: int = 2,
    ) -> DeltaResult:
        """Calculate delta for a specific item type.

        Args:
            item_type: Type of items (e.g., "publications", "press_releases")
            online_count: Current count from website
            buffer: Safety margin
            daily_factor: Expected items per day

        Returns:
            DeltaResult with fetch recommendation
        """
        if self.metadata is None:
            # No previous data - full scrape
            return DeltaResult(
                items_to_fetch=online_count,
                reason="no previous metadata",
                is_full_scrape=True,
                new_items_estimate=online_count,
                days_since_update=0,
            )

        saved_count = self.metadata.items.get(item_type, 0)
        days_stale = days_since(self.metadata.latest_updated)

        return calculate_items_to_fetch(
            online_count=online_count,
            saved_count=saved_count,
            days_since_update=days_stale,
            buffer=buffer,
            daily_factor=daily_factor,
        )

    def record_update(self, item_type: str, count: int) -> None:
        """Record successful update of item type.

        Args:
            item_type: Type of items updated
            count: New total count
        """
        if self.metadata is None:
            self.metadata = UpdateMetadata(
                latest_updated=datetime.now(),
                items={},
            )

        self.metadata.items[item_type] = count
        self.metadata.latest_updated = datetime.now()

    def get_last_update(self) -> Optional[datetime]:
        """Get datetime of last update."""
        return self.metadata.latest_updated if self.metadata else None

    def get_item_count(self, item_type: str) -> int:
        """Get saved count for item type."""
        if self.metadata is None:
            return 0
        return self.metadata.items.get(item_type, 0)
