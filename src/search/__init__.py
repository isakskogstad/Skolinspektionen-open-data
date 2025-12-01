"""Search and ranking functionality for Skolinspektionen data."""

from .ranker import (
    SearchRanker,
    SearchResult,
    search_publications,
    search_press_releases,
)

__all__ = [
    "SearchRanker",
    "SearchResult",
    "search_publications",
    "search_press_releases",
]
