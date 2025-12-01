"""Hybrid search ranking with BM25 and fuzzy matching.

Provides intelligent search across Skolinspektionen publications
with support for exact matches, relevance ranking, and typo tolerance.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence, TypeVar

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz, process

T = TypeVar("T")


@dataclass
class SearchResult:
    """A search result with relevance scoring."""

    item: Any
    score: float
    match_type: str  # "exact", "bm25", "fuzzy"
    matched_field: str
    highlight: Optional[str] = None

    @property
    def relevance_label(self) -> str:
        """Human-readable relevance indicator."""
        if self.score >= 0.9:
            return "Mycket hög relevans"
        elif self.score >= 0.7:
            return "Hög relevans"
        elif self.score >= 0.5:
            return "Medelhög relevans"
        else:
            return "Låg relevans"


@dataclass
class SearchConfig:
    """Configuration for search behavior."""

    # Weight for different match types (higher = more important)
    exact_match_weight: float = 1.0
    bm25_weight: float = 0.8
    fuzzy_weight: float = 0.6

    # Fuzzy matching thresholds (0-100)
    fuzzy_score_cutoff: int = 70

    # BM25 parameters
    bm25_k1: float = 1.5
    bm25_b: float = 0.75

    # Result limits
    max_results: int = 50

    # Fields to search (in order of importance)
    title_weight: float = 2.0
    summary_weight: float = 1.0
    content_weight: float = 0.5


def tokenize_swedish(text: str) -> list[str]:
    """Tokenize Swedish text for search.

    Handles Swedish-specific patterns like compound words and
    common stop words.
    """
    if not text:
        return []

    # Convert to lowercase
    text = text.lower()

    # Remove punctuation but keep Swedish characters
    text = re.sub(r"[^\wåäöÅÄÖ\s-]", " ", text)

    # Split on whitespace and hyphens
    tokens = re.split(r"[\s-]+", text)

    # Remove empty tokens and very short tokens
    tokens = [t for t in tokens if len(t) > 1]

    # Swedish stop words (common words with low search value)
    stop_words = {
        "och", "i", "att", "en", "ett", "det", "som", "på", "är", "av",
        "för", "med", "den", "till", "har", "de", "inte", "om", "vi",
        "ska", "kan", "från", "eller", "hos", "vid", "så", "även",
        "efter", "utan", "mot", "under", "vara", "bli", "blev", "sina",
        "sin", "sitt", "denna", "detta", "dessa", "där", "här", "var",
    }

    tokens = [t for t in tokens if t not in stop_words]

    return tokens


class SearchRanker:
    """Hybrid search ranker using BM25 + fuzzy matching.

    Combines multiple search strategies:
    1. Exact match (highest priority)
    2. BM25 relevance ranking (good for multi-word queries)
    3. Fuzzy matching (handles typos and variations)

    Usage:
        ranker = SearchRanker(publications, get_text=lambda p: p.title)
        results = ranker.search("skolenkät grundskola")
    """

    def __init__(
        self,
        items: Sequence[T],
        get_text: Callable[[T], str],
        get_secondary_text: Optional[Callable[[T], str]] = None,
        config: Optional[SearchConfig] = None,
    ):
        """Initialize the search ranker.

        Args:
            items: Items to search
            get_text: Function to extract primary searchable text
            get_secondary_text: Optional function for secondary text (e.g., summary)
            config: Search configuration
        """
        self.items = list(items)
        self.get_text = get_text
        self.get_secondary_text = get_secondary_text
        self.config = config or SearchConfig()

        # Build search indices
        self._build_indices()

    def _build_indices(self) -> None:
        """Build BM25 and lookup indices."""
        # Extract and tokenize text
        self.texts = [self.get_text(item) or "" for item in self.items]
        self.texts_lower = [t.lower() for t in self.texts]

        # Tokenized corpus for BM25
        self.tokenized_corpus = [tokenize_swedish(text) for text in self.texts]

        # Build BM25 index
        if self.tokenized_corpus and any(self.tokenized_corpus):
            self.bm25 = BM25Okapi(
                self.tokenized_corpus,
                k1=self.config.bm25_k1,
                b=self.config.bm25_b,
            )
        else:
            self.bm25 = None

        # Secondary text if provided
        if self.get_secondary_text:
            self.secondary_texts = [
                self.get_secondary_text(item) or "" for item in self.items
            ]
            self.secondary_tokenized = [
                tokenize_swedish(text) for text in self.secondary_texts
            ]
        else:
            self.secondary_texts = None
            self.secondary_tokenized = None

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        min_score: float = 0.1,
    ) -> list[SearchResult]:
        """Search for items matching query.

        Args:
            query: Search query
            max_results: Maximum results to return
            min_score: Minimum relevance score (0-1)

        Returns:
            List of SearchResult sorted by relevance
        """
        if not query or not self.items:
            return []

        max_results = max_results or self.config.max_results
        query_lower = query.lower()
        query_tokens = tokenize_swedish(query)

        results: dict[int, SearchResult] = {}

        # 1. Exact matches (highest priority)
        exact_results = self._exact_search(query_lower)
        for idx, score in exact_results:
            if idx not in results or score > results[idx].score:
                results[idx] = SearchResult(
                    item=self.items[idx],
                    score=score * self.config.exact_match_weight,
                    match_type="exact",
                    matched_field="title",
                    highlight=self._highlight(self.texts[idx], query),
                )

        # 2. BM25 relevance ranking
        if self.bm25 and query_tokens:
            bm25_results = self._bm25_search(query_tokens)
            for idx, score in bm25_results:
                adjusted_score = score * self.config.bm25_weight
                if idx not in results or adjusted_score > results[idx].score:
                    results[idx] = SearchResult(
                        item=self.items[idx],
                        score=adjusted_score,
                        match_type="bm25",
                        matched_field="title",
                        highlight=self._highlight(self.texts[idx], query),
                    )

        # 3. Fuzzy matching (for typo tolerance)
        fuzzy_results = self._fuzzy_search(query_lower)
        for idx, score in fuzzy_results:
            adjusted_score = score * self.config.fuzzy_weight
            if idx not in results or adjusted_score > results[idx].score:
                results[idx] = SearchResult(
                    item=self.items[idx],
                    score=adjusted_score,
                    match_type="fuzzy",
                    matched_field="title",
                    highlight=self._highlight(self.texts[idx], query),
                )

        # Filter and sort
        final_results = [r for r in results.values() if r.score >= min_score]
        final_results.sort(key=lambda r: r.score, reverse=True)

        return final_results[:max_results]

    def _exact_search(self, query_lower: str) -> list[tuple[int, float]]:
        """Find exact substring matches."""
        results = []

        for idx, text in enumerate(self.texts_lower):
            if query_lower in text:
                # Higher score for title matches, position-based scoring
                position = text.find(query_lower)
                length_ratio = len(query_lower) / max(len(text), 1)

                # Score based on match quality
                if text == query_lower:
                    score = 1.0  # Perfect match
                elif text.startswith(query_lower):
                    score = 0.95  # Starts with query
                elif f" {query_lower}" in f" {text}":
                    score = 0.9  # Word boundary match
                else:
                    score = 0.7 + (length_ratio * 0.2)  # Partial match

                results.append((idx, score))

        return results

    def _bm25_search(
        self,
        query_tokens: list[str],
        top_n: int = 100,
    ) -> list[tuple[int, float]]:
        """Search using BM25 ranking."""
        if not self.bm25:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # Normalize scores to 0-1 range
        max_score = max(scores) if scores.any() else 1
        if max_score > 0:
            normalized = scores / max_score
        else:
            normalized = scores

        # Get top results with score > 0
        results = []
        for idx, score in enumerate(normalized):
            if score > 0:
                results.append((idx, float(score)))

        # Sort by score and return top N
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]

    def _fuzzy_search(
        self,
        query_lower: str,
        limit: int = 50,
    ) -> list[tuple[int, float]]:
        """Search using fuzzy string matching."""
        # Use rapidfuzz for fast fuzzy matching
        matches = process.extract(
            query_lower,
            self.texts_lower,
            scorer=fuzz.WRatio,
            limit=limit,
            score_cutoff=self.config.fuzzy_score_cutoff,
        )

        results = []
        for match_text, score, idx in matches:
            # Convert score from 0-100 to 0-1
            normalized_score = score / 100.0
            results.append((idx, normalized_score))

        return results

    def _highlight(self, text: str, query: str) -> str:
        """Create highlighted snippet showing match context."""
        if not text or not query:
            return text

        # Find query position (case-insensitive)
        text_lower = text.lower()
        query_lower = query.lower()
        pos = text_lower.find(query_lower)

        if pos == -1:
            # No exact match, return truncated text
            return text[:200] + "..." if len(text) > 200 else text

        # Extract context around match
        start = max(0, pos - 50)
        end = min(len(text), pos + len(query) + 100)

        snippet = text[start:end]

        # Add ellipsis if truncated
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet


def search_publications(
    publications: Sequence[Any],
    query: str,
    max_results: int = 20,
    publication_type: Optional[str] = None,
    year: Optional[int] = None,
) -> list[SearchResult]:
    """Search publications with optional filtering.

    Args:
        publications: List of Publication objects
        query: Search query
        max_results: Maximum results to return
        publication_type: Filter by publication type
        year: Filter by publication year

    Returns:
        List of SearchResult
    """
    # Apply filters first
    filtered = list(publications)

    if publication_type:
        filtered = [p for p in filtered if getattr(p, "type", None) == publication_type]

    if year:
        filtered = [
            p
            for p in filtered
            if getattr(p, "published", None)
            and getattr(p.published, "year", None) == year
        ]

    if not filtered:
        return []

    # Create ranker and search
    ranker = SearchRanker(
        items=filtered,
        get_text=lambda p: getattr(p, "title", ""),
        get_secondary_text=lambda p: getattr(p, "summary", ""),
    )

    return ranker.search(query, max_results=max_results)


def search_press_releases(
    releases: Sequence[Any],
    query: str,
    max_results: int = 20,
    year: Optional[int] = None,
) -> list[SearchResult]:
    """Search press releases.

    Args:
        releases: List of PressRelease objects
        query: Search query
        max_results: Maximum results to return
        year: Filter by year

    Returns:
        List of SearchResult
    """
    filtered = list(releases)

    if year:
        filtered = [
            r
            for r in filtered
            if getattr(r, "published", None)
            and getattr(r.published, "year", None) == year
        ]

    if not filtered:
        return []

    ranker = SearchRanker(
        items=filtered,
        get_text=lambda r: getattr(r, "title", ""),
    )

    return ranker.search(query, max_results=max_results)
