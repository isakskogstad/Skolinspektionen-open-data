#!/usr/bin/env python3
"""CLI script for refreshing Skolinspektionen data.

Usage:
    # Refresh all sources
    python scripts/refresh_data.py

    # Refresh specific sources
    python scripts/refresh_data.py --sources skolenkaten tillstand

    # Force re-download
    python scripts/refresh_data.py --force

    # Show status only
    python scripts/refresh_data.py --status

For scheduled runs (cron), use:
    # Daily at 06:00
    0 6 * * * cd /path/to/skolinspektionen-data && /path/to/venv/bin/python scripts/refresh_data.py >> logs/refresh.log 2>&1

    # Weekly full refresh on Sundays at 03:00
    0 3 * * 0 cd /path/to/skolinspektionen-data && /path/to/venv/bin/python scripts/refresh_data.py --force >> logs/refresh.log 2>&1
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.refresher import DataRefresher, run_refresh


def setup_logging(verbose: bool = False, log_file: Path = None):
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO

    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def print_status(refresher: DataRefresher):
    """Print current refresh status."""
    status = refresher.get_status()

    print("\n=== Skolinspektionen DATA - Refresh Status ===\n")

    print(f"Last full refresh:        {status['last_full_refresh'] or 'Never'}")
    print(f"Last incremental refresh: {status['last_incremental_refresh'] or 'Never'}")

    print("\n--- Source Status ---")
    for source, info in status["sources"].items():
        last = info.get("last_refresh", "Never")
        status_str = info.get("status", "unknown")
        items = info.get("items", 0)
        print(f"  {source:15} | {status_str:8} | {items:6} items | Last: {last}")

    if status["recent_history"]:
        print("\n--- Recent Operations ---")
        for op in status["recent_history"][-5:]:
            success = "✓" if op.get("success") else "✗"
            duration = op.get("duration", 0)
            sources = ", ".join(op.get("sources", []))
            print(f"  {success} {op['timestamp'][:19]} | {duration:6.1f}s | {sources}")

    print()


def print_result(result):
    """Print refresh result summary."""
    success = "✓ SUCCESS" if result.success else "✗ FAILED"

    print(f"\n=== Refresh Complete: {success} ===\n")
    print(f"Duration: {result.duration_seconds:.1f} seconds")
    print(f"Total items: {result.total_items}")
    print(f"Total errors: {result.total_errors}")

    print("\n--- Source Results ---")
    for source, sr in result.sources.items():
        status = "✓" if sr.status.value == "success" else "✗"
        print(f"  {status} {source:15} | {sr.items_parsed:6} items | {sr.duration_seconds or 0:.1f}s")
        if sr.errors:
            for error in sr.errors[:3]:
                print(f"      Error: {error[:80]}")

    print()


async def main():
    parser = argparse.ArgumentParser(
        description="Refresh Skolinspektionen data from all sources",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--sources",
        nargs="+",
        choices=["publications", "skolenkaten", "tillstand", "tillsyn", "kolada"],
        help="Specific sources to refresh (default: all)",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download of all files even if unchanged",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current status only, don't refresh",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log to file instead of stdout",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON (for scripting)",
    )

    args = parser.parse_args()

    setup_logging(verbose=args.verbose, log_file=args.log_file)
    logger = logging.getLogger(__name__)

    refresher = DataRefresher()

    if args.status:
        if args.json:
            print(json.dumps(refresher.get_status(), ensure_ascii=False, indent=2))
        else:
            print_status(refresher)
        return 0

    # Run refresh
    logger.info(f"Starting data refresh at {datetime.now().isoformat()}")
    logger.info(f"Sources: {args.sources or 'all'}")
    logger.info(f"Force: {args.force}")

    try:
        result = await run_refresh(sources=args.sources, force=args.force)

        if args.json:
            # Output JSON for scripting
            output = {
                "success": result.success,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "duration_seconds": result.duration_seconds,
                "total_items": result.total_items,
                "total_errors": result.total_errors,
                "sources": {
                    name: {
                        "status": sr.status.value,
                        "items_fetched": sr.items_fetched,
                        "items_parsed": sr.items_parsed,
                        "errors": sr.errors,
                    }
                    for name, sr in result.sources.items()
                },
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        else:
            print_result(result)

        return 0 if result.success else 1

    except Exception as e:
        logger.exception(f"Refresh failed with error: {e}")
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}))
        else:
            print(f"\n✗ ERROR: {e}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
