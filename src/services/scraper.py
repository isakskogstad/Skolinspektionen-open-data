"""Scraper for fetching publication index from Skolinspektionen.

Enhanced with rate limiting, retry logic, caching, and delta updates.
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress

from ..config import get_settings
from .cache import get_content_cache
from .delta import DeltaTracker
from .models import (
    PUBLICATION_TYPES,
    SKOLFORMER,
    SUBJECTS,
    THEMES,
    Attachment,
    Index,
    PressRelease,
    Publication,
    StatisticsFile,
)
from .rate_limiter import extract_domain, get_rate_limiter
from .retry import CircuitBreaker, with_retry

console = Console()


class PublicationScraper:
    """Scraper for Skolinspektionen publications.

    Features:
    - Rate limiting to respect server resources
    - Automatic retry with exponential backoff
    - Two-tier caching (memory + disk)
    - Delta updates for efficient incremental scraping
    """

    def __init__(
        self,
        timeout: Optional[float] = None,
        use_cache: bool = True,
        use_delta: bool = True,
    ):
        """Initialize scraper.

        Args:
            timeout: HTTP timeout in seconds (uses config default if not provided)
            use_cache: Enable content caching
            use_delta: Enable incremental updates via delta tracking
        """
        self.settings = get_settings()
        self.timeout = timeout or self.settings.http_timeout
        self.use_cache = use_cache
        self.use_delta = use_delta

        self.client: Optional[httpx.AsyncClient] = None
        self.rate_limiter = get_rate_limiter()
        self.cache = get_content_cache() if use_cache else None
        self.delta_tracker = DeltaTracker() if use_delta else None
        self.circuit_breaker = CircuitBreaker()

    async def __aenter__(self):
        """Start the HTTP client."""
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": self.settings.user_agent},
        )

        if self.delta_tracker:
            await self.delta_tracker.load()

        return self

    async def __aexit__(self, *args):
        """Close the HTTP client and save delta state."""
        if self.client:
            await self.client.aclose()

        if self.delta_tracker:
            await self.delta_tracker.save()

    @with_retry()
    async def _fetch_page_internal(self, url: str) -> Optional[str]:
        """Internal fetch method with retry decorator."""
        if not self.client:
            raise RuntimeError("Scraper not initialized. Use async with.")

        response = await self.client.get(url)
        response.raise_for_status()
        return response.text

    async def fetch_page(self, url: str, use_cache: bool = True) -> Optional[str]:
        """Fetch a page with rate limiting and caching.

        Args:
            url: URL to fetch
            use_cache: Whether to use cache for this request

        Returns:
            HTML content or None if fetch failed
        """
        # Check cache first
        if use_cache and self.cache:
            cached = await self.cache.get(url)
            if cached:
                console.print(f"[dim]Cache hit: {url}[/dim]")
                return cached

        # Apply rate limiting
        domain = extract_domain(url)
        async with self.rate_limiter.limit(domain):
            try:
                html = await self._fetch_page_internal(url)

                # Cache the result
                if html and use_cache and self.cache:
                    await self.cache.set(url, html)

                return html

            except Exception as e:
                console.print(f"[red]Error fetching {url}: {e}[/red]")
                return None

    async def scrape_publications(
        self,
        max_pages: Optional[int] = None,
    ) -> list[Publication]:
        """Scrape publications from the publication search page.

        Uses delta tracking to minimize unnecessary scraping.

        Args:
            max_pages: Maximum pages to scrape (uses config default if not provided)

        Returns:
            List of scraped publications
        """
        max_pages = max_pages or self.settings.max_pages_per_scrape
        publications = []
        page = 1

        # Calculate delta if enabled
        if self.delta_tracker:
            # First, get the total count from the first page
            first_page_url = f"{self.settings.publication_search_url}?p=1"
            first_html = await self.fetch_page(first_page_url, use_cache=False)

            if first_html:
                total_online = self._extract_total_count(first_html)
                if total_online:
                    delta = self.delta_tracker.calculate_delta("publications", total_online)
                    console.print(f"[cyan]{delta.description}[/cyan]")

                    # Adjust max_pages based on delta
                    if not delta.is_full_scrape:
                        # Estimate pages needed (assuming ~20 items per page)
                        estimated_pages = (delta.items_to_fetch // 20) + 1
                        max_pages = min(max_pages, estimated_pages)

        with Progress() as progress:
            task = progress.add_task("[cyan]Scraping publications...", total=max_pages)

            while page <= max_pages:
                url = f"{self.settings.publication_search_url}?p={page}"
                html = await self.fetch_page(url)

                if not html:
                    break

                soup = BeautifulSoup(html, "html.parser")
                items = self._parse_publication_list(soup)

                if not items:
                    break

                publications.extend(items)
                progress.update(
                    task, advance=1, description=f"[cyan]Page {page}: {len(items)} items"
                )
                page += 1

                # Respectful delay between pages
                await asyncio.sleep(self.settings.scrape_delay_seconds)

        # Update delta tracker
        if self.delta_tracker:
            self.delta_tracker.record_update("publications", len(publications))

        console.print(f"[green]Scraped {len(publications)} publications[/green]")
        return publications

    def _extract_total_count(self, html: str) -> Optional[int]:
        """Extract total item count from search results page."""
        soup = BeautifulSoup(html, "html.parser")

        # Look for common patterns like "Visar 1-20 av 334 resultat"
        count_patterns = [
            r"av\s+(\d+)\s+resultat",
            r"(\d+)\s+träffar",
            r"totalt\s+(\d+)",
        ]

        text = soup.get_text()
        for pattern in count_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))

        return None

    def _parse_publication_list(self, soup: BeautifulSoup) -> list[Publication]:
        """Parse the publication list from a search results page."""
        publications = []

        # Find all publication items - adjust selector based on actual HTML structure
        items = soup.select("article, .search-result-item, .publication-item")

        if not items:
            # Try alternative selectors
            items = soup.select("[class*='result'], [class*='item']")

        for item in items:
            try:
                pub = self._parse_publication_item(item)
                if pub:
                    publications.append(pub)
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to parse item: {e}[/yellow]")

        return publications

    def _clean_url(self, url: str) -> str:
        """Remove tracking parameters from URL."""
        parsed = urlparse(url)
        # Remove query string (tracking params)
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        return clean

    def _parse_publication_item(self, item) -> Optional[Publication]:
        """Parse a single publication item from the search results."""
        base_url = self.settings.base_url

        # Find title and URL
        link = item.select_one("a[href*='/publikationer/'], h2 a, h3 a, .title a")
        if not link:
            return None

        title = link.get_text(strip=True)
        url = link.get("href", "")

        if not url.startswith("http"):
            url = urljoin(base_url, url)

        # Clean tracking parameters from URL
        url = self._clean_url(url)

        # Determine publication type from URL
        pub_type = "ovriga-publikationer"
        for type_key in PUBLICATION_TYPES:
            if type_key in url:
                pub_type = type_key
                break

        # Find publication date
        date_elem = item.select_one("time, .date, [class*='date'], [class*='published']")
        published = None
        if date_elem:
            date_text = date_elem.get("datetime") or date_elem.get_text(strip=True)
            published = self._parse_date(date_text)

        # Find summary
        summary_elem = item.select_one("p, .summary, .description, [class*='excerpt']")
        summary = summary_elem.get_text(strip=True) if summary_elem else None

        # Extract themes from tags, links, or categories
        themes = self._extract_taxonomy(item, THEMES)

        # Extract school forms (skolformer)
        skolformer = self._extract_taxonomy(item, SKOLFORMER)

        # Extract subjects (ämnen)
        subjects = self._extract_taxonomy(item, SUBJECTS)

        # Find PDF attachment if visible
        attachments = []
        pdf_link = item.select_one("a[href$='.pdf']")
        if pdf_link:
            attachments.append(
                Attachment(
                    name=pdf_link.get_text(strip=True) or "Rapport",
                    url=urljoin(base_url, pdf_link.get("href", "")),
                    file_type="pdf",
                )
            )

        return Publication(
            title=title,
            url=url.replace(base_url, ""),  # Store relative URL
            published=published,
            type=pub_type,
            summary=summary,
            themes=themes,
            skolformer=skolformer,
            subjects=subjects,
            attachments=attachments,
        )

    def _extract_taxonomy(self, item, taxonomy: dict) -> list[str]:
        """Extract taxonomy values from an item based on text content and links.

        Searches for taxonomy keys in:
        - Link hrefs (e.g., /teman/matematik/)
        - Tag/category elements
        - Text content of the item
        """
        found = []
        item.get_text().lower()

        # Check links for taxonomy slugs
        for link in item.select("a"):
            href = link.get("href", "").lower()
            link_text = link.get_text().lower()

            for key, display_name in taxonomy.items():
                # Check if key is in URL path
                if f"/{key}/" in href or f"/{key}" in href:
                    if key not in found:
                        found.append(key)
                # Check if display name matches link text
                elif display_name.lower() in link_text:
                    if key not in found:
                        found.append(key)

        # Also check for taxonomy terms in tag/category elements
        for tag_elem in item.select(".tag, .category, [class*='tag'], [class*='category']"):
            tag_text = tag_elem.get_text().lower()
            for key, display_name in taxonomy.items():
                if display_name.lower() in tag_text or key in tag_text:
                    if key not in found:
                        found.append(key)

        # Fallback: check title for common terms
        title_elem = item.select_one("h2, h3, .title")
        if title_elem:
            title_text = title_elem.get_text().lower()
            for key, display_name in taxonomy.items():
                if display_name.lower() in title_text:
                    if key not in found:
                        found.append(key)

        return found

    async def scrape_press_releases(self) -> list[PressRelease]:
        """Scrape press releases from Skolinspektionen."""
        html = await self.fetch_page(self.settings.press_releases_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        releases = []

        # Find all press release items
        items = soup.select("article, .press-item, [class*='news-item']")

        for item in items:
            link = item.select_one("a")
            if not link:
                continue

            title = link.get_text(strip=True)
            url = link.get("href", "")

            if not url.startswith("http"):
                url = urljoin(self.settings.base_url, url)

            # Find date
            date_elem = item.select_one("time, .date, [class*='date']")
            published = None
            if date_elem:
                date_text = date_elem.get("datetime") or date_elem.get_text(strip=True)
                published = self._parse_date(date_text)

            releases.append(
                PressRelease(
                    title=title,
                    url=url.replace(self.settings.base_url, ""),
                    published=published,
                )
            )

        # Update delta tracker
        if self.delta_tracker:
            self.delta_tracker.record_update("press_releases", len(releases))

        console.print(f"[green]Scraped {len(releases)} press releases[/green]")
        return releases

    async def scrape_statistics_files(self) -> list[StatisticsFile]:
        """Scrape known statistics file URLs."""
        # These are known file patterns from our research
        known_files = [
            StatisticsFile(
                name="Tillståndsbeslut 2023",
                url="/globalassets/02-beslut-rapporter-stat/statistik/statistik-tillstand/2023-skolstart-2024-25/tillstandsbeslut-2023.xlsx",
                file_type="xlsx",
                category="tillstand",
                year=2023,
            ),
            StatisticsFile(
                name="Tillståndsbeslut 2022",
                url="/globalassets/02-beslut-rapporter-stat/statistik/statistik-tillstand/2022-skolstart-2023-24/tillstandsbeslut-2022-publicering.xlsx",
                file_type="xlsx",
                category="tillstand",
                year=2022,
            ),
            StatisticsFile(
                name="Ansökningar 2022",
                url="/globalassets/02-beslut-rapporter-stat/statistik/statistik-tillstand/2022-skolstart-2023-24/ansokningar-2022.xlsx",
                file_type="xlsx",
                category="tillstand",
                year=2022,
            ),
            StatisticsFile(
                name="Årsstatistik tillsyn brister 2020",
                url="/globalassets/02-beslut-rapporter-stat/statistik/statistik-regelbunden-tillsyn/rt-2020/arsstatistik-2020_rt_brister_detalj.xlsx",
                file_type="xlsx",
                category="tillsyn",
                year=2020,
            ),
            StatisticsFile(
                name="Årsrapport 2024",
                url="/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/arsrapport/arsrapport-2024/arsrapport-2024.pdf",
                file_type="pdf",
                category="arsrapport",
                year=2024,
            ),
            StatisticsFile(
                name="Skolenkäten fakta 2025",
                url="/globalassets/02-beslut-rapporter-stat/statistik/statistik-skolenkaten/2025/fakta-om-skolenkaten-2025.pdf",
                file_type="pdf",
                category="skolenkaten",
                year=2025,
            ),
        ]

        # Verify which files exist
        valid_files = []
        for file in known_files:
            full_url = self.settings.base_url + file.url

            # Apply rate limiting
            domain = extract_domain(full_url)
            async with self.rate_limiter.limit(domain):
                try:
                    response = await self.client.head(full_url)
                    if response.status_code == 200:
                        valid_files.append(file)
                        console.print(f"[green]✓ {file.name}[/green]")
                    else:
                        console.print(
                            f"[yellow]✗ {file.name} (status {response.status_code})[/yellow]"
                        )
                except Exception as e:
                    console.print(f"[yellow]✗ {file.name} ({e})[/yellow]")

        # Update delta tracker
        if self.delta_tracker:
            self.delta_tracker.record_update("statistics_files", len(valid_files))

        return valid_files

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse a date string in various formats."""
        if not date_str:
            return None

        # Clean up the string
        date_str = date_str.strip()

        # Try various formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%d %B %Y",
            "%d %b %Y",
            "%B %d, %Y",
        ]

        # Swedish month names
        swedish_months = {
            "januari": "01",
            "februari": "02",
            "mars": "03",
            "april": "04",
            "maj": "05",
            "juni": "06",
            "juli": "07",
            "augusti": "08",
            "september": "09",
            "oktober": "10",
            "november": "11",
            "december": "12",
        }

        # Try to extract date pattern
        date_match = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", date_str)
        if date_match:
            day, month, year = date_match.groups()
            month_lower = month.lower()
            if month_lower in swedish_months:
                try:
                    return datetime.strptime(
                        f"{year}-{swedish_months[month_lower]}-{day.zfill(2)}", "%Y-%m-%d"
                    ).date()
                except ValueError:
                    pass

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    async def build_index(self) -> Index:
        """Build a complete index of all available data."""
        console.print("[bold]Building Skolinspektionen index...[/bold]")

        publications = await self.scrape_publications()
        press_releases = await self.scrape_press_releases()
        statistics_files = await self.scrape_statistics_files()

        index = Index(
            publications=publications,
            press_releases=press_releases,
            statistics_files=statistics_files,
            last_updated=datetime.now().isoformat(),
        )

        console.print(f"[bold green]Index complete: {index.total_items} total items[/bold green]")
        return index

    async def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        if self.cache:
            return await self.cache.get_stats()
        return {"enabled": False}

    async def clear_cache(self) -> dict:
        """Clear all caches."""
        if self.cache:
            return await self.cache.clear()
        return {"enabled": False}


async def _async_main():
    """Async main entry point for the scraper."""
    settings = get_settings()

    async with PublicationScraper() as scraper:
        index = await scraper.build_index()

        # Save index to file
        data_dir = settings.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)

        index_path = settings.index_path
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index.model_dump(mode="json"), f, ensure_ascii=False, indent=2)

        console.print(f"[green]Index saved to {index_path}[/green]")

        # Print cache stats
        cache_stats = await scraper.get_cache_stats()
        console.print(
            f"[dim]Cache stats: {cache_stats.get('memory', {}).get('size', 0)} items in memory[/dim]"
        )


def main():
    """Synchronous entry point for CLI."""
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
