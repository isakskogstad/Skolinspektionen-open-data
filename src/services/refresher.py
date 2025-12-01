"""Data refresher that orchestrates updates from all data sources.

Coordinates fetching, parsing, and storage of:
- Publications index (scraped from website)
- Skolenkäten survey data (Excel files)
- Tillståndsbeslut decisions (Excel files)
- Tillsyn statistics (Viten, TUI, Planerad Tillsyn)
- Kolada municipal statistics (API)
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from enum import Enum

from pydantic import BaseModel, Field

from ..config import get_settings
from .fetcher import DataFetcher
from .scraper import PublicationScraper
from .skolenkaten import parse_skolenkaten_excel, discover_skolenkaten_files
from .tillstand import parse_tillstand_excel, discover_tillstand_files
from .tillsyn_statistik import load_all_tillsyn_statistik
from .kolada import get_education_stats, EDUCATION_KPIS

logger = logging.getLogger(__name__)


class RefreshStatus(str, Enum):
    """Status of a refresh operation."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceRefreshResult(BaseModel):
    """Result of refreshing a single data source."""
    source: str
    status: RefreshStatus
    items_fetched: int = 0
    items_parsed: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None


class RefreshResult(BaseModel):
    """Result of a complete data refresh operation."""
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    sources: dict[str, SourceRefreshResult] = Field(default_factory=dict)
    total_items: int = 0
    total_errors: int = 0
    success: bool = False


class RefreshState(BaseModel):
    """Persistent state for tracking refresh operations."""
    last_full_refresh: Optional[str] = None
    last_incremental_refresh: Optional[str] = None
    source_states: dict[str, dict] = Field(default_factory=dict)
    refresh_history: list[dict] = Field(default_factory=list)


class DataRefresher:
    """Orchestrates data refresh from all sources."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
    ):
        self.settings = get_settings()
        self.data_dir = data_dir or self.settings.data_dir
        self.state_file = state_file or (self.data_dir / "refresh_state.json")
        self.state = self._load_state()

    def _load_state(self) -> RefreshState:
        """Load refresh state from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return RefreshState(**data)
            except Exception as e:
                logger.warning(f"Failed to load refresh state: {e}")
        return RefreshState()

    def _save_state(self):
        """Save refresh state to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self.state.model_dump(), f, ensure_ascii=False, indent=2)

    async def refresh_publications(self, max_pages: int = 50) -> SourceRefreshResult:
        """Refresh publications index from website."""
        result = SourceRefreshResult(
            source="publications",
            status=RefreshStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            async with PublicationScraper() as scraper:
                index = await scraper.build_index()

                # Save index
                index_path = self.settings.index_path
                index_path.parent.mkdir(parents=True, exist_ok=True)
                with open(index_path, "w", encoding="utf-8") as f:
                    json.dump(index.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

                result.items_fetched = index.total_items
                result.items_parsed = index.total_items
                result.status = RefreshStatus.SUCCESS

        except Exception as e:
            logger.error(f"Failed to refresh publications: {e}")
            result.status = RefreshStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = datetime.now().isoformat()
        if result.started_at:
            start = datetime.fromisoformat(result.started_at)
            end = datetime.fromisoformat(result.completed_at)
            result.duration_seconds = (end - start).total_seconds()

        return result

    async def refresh_skolenkaten(self, force: bool = False) -> SourceRefreshResult:
        """Refresh Skolenkäten data by downloading and parsing Excel files."""
        result = SourceRefreshResult(
            source="skolenkaten",
            status=RefreshStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            async with DataFetcher() as fetcher:
                # Download files
                downloaded = await fetcher.fetch_all_skolenkaten(force=force)
                result.items_fetched = len(downloaded)

                # Parse downloaded files
                parsed_count = 0
                for path in downloaded:
                    try:
                        records = parse_skolenkaten_excel(path)
                        parsed_count += len(records)
                    except Exception as e:
                        result.errors.append(f"Parse error {path.name}: {e}")

                result.items_parsed = parsed_count
                result.status = RefreshStatus.SUCCESS

        except Exception as e:
            logger.error(f"Failed to refresh Skolenkäten: {e}")
            result.status = RefreshStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = datetime.now().isoformat()
        if result.started_at:
            start = datetime.fromisoformat(result.started_at)
            end = datetime.fromisoformat(result.completed_at)
            result.duration_seconds = (end - start).total_seconds()

        return result

    async def refresh_tillstand(self, force: bool = False) -> SourceRefreshResult:
        """Refresh Tillståndsbeslut data."""
        result = SourceRefreshResult(
            source="tillstand",
            status=RefreshStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            async with DataFetcher() as fetcher:
                downloaded = await fetcher.fetch_all_tillstand(force=force)
                result.items_fetched = len(downloaded)

                parsed_count = 0
                for path in downloaded:
                    try:
                        records = parse_tillstand_excel(path)
                        parsed_count += len(records)
                    except Exception as e:
                        result.errors.append(f"Parse error {path.name}: {e}")

                result.items_parsed = parsed_count
                result.status = RefreshStatus.SUCCESS

        except Exception as e:
            logger.error(f"Failed to refresh Tillstånd: {e}")
            result.status = RefreshStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = datetime.now().isoformat()
        if result.started_at:
            start = datetime.fromisoformat(result.started_at)
            end = datetime.fromisoformat(result.completed_at)
            result.duration_seconds = (end - start).total_seconds()

        return result

    async def refresh_tillsyn(self, force: bool = False) -> SourceRefreshResult:
        """Refresh Tillsyn statistics (Viten, TUI, Planerad Tillsyn)."""
        result = SourceRefreshResult(
            source="tillsyn",
            status=RefreshStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        try:
            async with DataFetcher() as fetcher:
                downloaded = await fetcher.fetch_all_tillsyn(force=force)

                total_files = sum(len(files) for files in downloaded.values())
                result.items_fetched = total_files

                # Parse using existing loader
                download_dir = fetcher.download_dir / "tillsyn"
                if download_dir.exists():
                    summary = load_all_tillsyn_statistik(download_dir)
                    result.items_parsed = (
                        len(summary.viten) +
                        len(summary.tui) +
                        len(summary.planerad_tillsyn)
                    )

                result.status = RefreshStatus.SUCCESS

        except Exception as e:
            logger.error(f"Failed to refresh Tillsyn: {e}")
            result.status = RefreshStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = datetime.now().isoformat()
        if result.started_at:
            start = datetime.fromisoformat(result.started_at)
            end = datetime.fromisoformat(result.completed_at)
            result.duration_seconds = (end - start).total_seconds()

        return result

    async def refresh_kolada(
        self,
        municipality_ids: Optional[list[str]] = None,
        year: Optional[int] = None,
    ) -> SourceRefreshResult:
        """Refresh Kolada municipal education statistics.

        Args:
            municipality_ids: List of municipality IDs to fetch (default: major cities)
            year: Year to fetch data for (default: latest)
        """
        result = SourceRefreshResult(
            source="kolada",
            status=RefreshStatus.RUNNING,
            started_at=datetime.now().isoformat(),
        )

        # Default to major Swedish municipalities
        if not municipality_ids:
            municipality_ids = [
                "0180",  # Stockholm
                "1480",  # Göteborg
                "1280",  # Malmö
                "0380",  # Uppsala
                "1281",  # Lund
                "0580",  # Linköping
                "1880",  # Örebro
                "0680",  # Jönköping
                "1980",  # Västerås
                "2580",  # Umeå
            ]

        try:
            kolada_data = {}
            for muni_id in municipality_ids:
                try:
                    stats = await get_education_stats(muni_id, year)
                    if stats and stats.get("kpis"):
                        kolada_data[muni_id] = stats
                        result.items_fetched += 1
                except Exception as e:
                    result.errors.append(f"Kolada error {muni_id}: {e}")

            # Save Kolada data
            kolada_path = self.data_dir / "kolada" / f"education_stats_{year or 'latest'}.json"
            kolada_path.parent.mkdir(parents=True, exist_ok=True)
            with open(kolada_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "fetched_at": datetime.now().isoformat(),
                        "year": year,
                        "municipalities": kolada_data,
                        "kpi_definitions": EDUCATION_KPIS,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )

            result.items_parsed = len(kolada_data)
            result.status = RefreshStatus.SUCCESS

        except Exception as e:
            logger.error(f"Failed to refresh Kolada: {e}")
            result.status = RefreshStatus.FAILED
            result.errors.append(str(e))

        result.completed_at = datetime.now().isoformat()
        if result.started_at:
            start = datetime.fromisoformat(result.started_at)
            end = datetime.fromisoformat(result.completed_at)
            result.duration_seconds = (end - start).total_seconds()

        return result

    async def refresh_all(
        self,
        force: bool = False,
        sources: Optional[list[str]] = None,
    ) -> RefreshResult:
        """Refresh all data sources.

        Args:
            force: Force re-download of all files
            sources: List of sources to refresh (default: all)
                     Options: publications, skolenkaten, tillstand, tillsyn, kolada

        Returns:
            RefreshResult with status of all operations
        """
        all_sources = ["publications", "skolenkaten", "tillstand", "tillsyn", "kolada"]
        sources_to_refresh = sources or all_sources

        result = RefreshResult(started_at=datetime.now().isoformat())

        logger.info(f"Starting data refresh for: {sources_to_refresh}")

        # Run refreshes
        refresh_methods = {
            "publications": lambda: self.refresh_publications(),
            "skolenkaten": lambda: self.refresh_skolenkaten(force),
            "tillstand": lambda: self.refresh_tillstand(force),
            "tillsyn": lambda: self.refresh_tillsyn(force),
            "kolada": lambda: self.refresh_kolada(),
        }

        for source in sources_to_refresh:
            if source in refresh_methods:
                logger.info(f"Refreshing {source}...")
                source_result = await refresh_methods[source]()
                result.sources[source] = source_result
                result.total_items += source_result.items_parsed
                result.total_errors += len(source_result.errors)

        # Finalize result
        result.completed_at = datetime.now().isoformat()
        start = datetime.fromisoformat(result.started_at)
        end = datetime.fromisoformat(result.completed_at)
        result.duration_seconds = (end - start).total_seconds()

        # Determine overall success
        failed_sources = [
            s for s, r in result.sources.items()
            if r.status == RefreshStatus.FAILED
        ]
        result.success = len(failed_sources) == 0

        # Update state
        now = datetime.now().isoformat()
        if sources is None:
            self.state.last_full_refresh = now
        else:
            self.state.last_incremental_refresh = now

        for source, source_result in result.sources.items():
            self.state.source_states[source] = {
                "last_refresh": source_result.completed_at,
                "status": source_result.status.value,
                "items": source_result.items_parsed,
            }

        # Add to history (keep last 100)
        self.state.refresh_history.append({
            "timestamp": result.completed_at,
            "sources": list(result.sources.keys()),
            "success": result.success,
            "duration": result.duration_seconds,
        })
        self.state.refresh_history = self.state.refresh_history[-100:]

        self._save_state()

        logger.info(
            f"Refresh complete: {result.total_items} items, "
            f"{result.total_errors} errors, "
            f"{result.duration_seconds:.1f}s"
        )

        return result

    def get_status(self) -> dict:
        """Get current refresh status and statistics."""
        return {
            "last_full_refresh": self.state.last_full_refresh,
            "last_incremental_refresh": self.state.last_incremental_refresh,
            "sources": self.state.source_states,
            "recent_history": self.state.refresh_history[-10:],
        }


async def run_refresh(
    sources: Optional[list[str]] = None,
    force: bool = False,
) -> RefreshResult:
    """Run data refresh (for CLI/scheduled use).

    Args:
        sources: List of sources to refresh (None = all)
        force: Force re-download of files

    Returns:
        RefreshResult with operation status
    """
    refresher = DataRefresher()
    return await refresher.refresh_all(force=force, sources=sources)
