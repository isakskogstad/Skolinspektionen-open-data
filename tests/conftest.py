"""Pytest configuration and fixtures for Skolinspektionen DATA tests."""

import asyncio
import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
import respx
from httpx import Response

from src.config import Settings, reset_settings
from src.services.cache import reset_content_cache
from src.services.models import (
    Attachment,
    Index,
    PressRelease,
    Publication,
    StatisticsFile,
)
from src.services.rate_limiter import reset_rate_limiter


@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset all global state between tests."""
    reset_settings()
    reset_content_cache()
    reset_rate_limiter()
    yield
    reset_settings()
    reset_content_cache()
    reset_rate_limiter()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary directory."""
    return Settings(
        data_dir=temp_dir / "data",
        cache_dir=temp_dir / "cache",
        http_timeout=5.0,
        rate_limit_per_second=100.0,  # Fast for tests
        rate_limit_burst=100,
        max_pages_per_scrape=20,
    )


@pytest.fixture
def sample_publication() -> Publication:
    """Create a sample publication for testing."""
    return Publication(
        title="Kvalitetsgranskning av matematik i grundskolan",
        url="/beslut-rapporter/publikationer/kvalitetsgranskning/2024/matematik-grundskolan",
        published=date(2024, 3, 15),
        type="kvalitetsgranskning",
        summary="En granskning av matematikundervisningen i årskurs 7-9.",
        themes=["undervisningskvalitet", "grundskola"],
        attachments=[
            Attachment(
                name="Rapport.pdf",
                url="/globalassets/rapport-matematik-2024.pdf",
                file_type="pdf",
            )
        ],
    )


@pytest.fixture
def sample_publications() -> list[Publication]:
    """Create a list of sample publications for testing search."""
    return [
        Publication(
            title="Kvalitetsgranskning av matematik i grundskolan",
            url="/pub/1",
            published=date(2024, 3, 15),
            type="kvalitetsgranskning",
            summary="En granskning av matematikundervisningen.",
        ),
        Publication(
            title="Tillsyn av Stockholms kommun",
            url="/pub/2",
            published=date(2024, 2, 10),
            type="regelbunden-tillsyn",
            summary="Tillsyn genomförd i Stockholms kommun.",
        ),
        Publication(
            title="Skolenkäten resultat 2024",
            url="/pub/3",
            published=date(2024, 1, 20),
            type="ovriga-publikationer",
            summary="Resultat från skolenkäten vårterminen 2024.",
        ),
        Publication(
            title="Regeringsuppdrag om skolans digitalisering",
            url="/pub/4",
            published=date(2023, 12, 5),
            type="regeringsuppdrag",
            summary="Rapport till regeringen om digitaliseringens påverkan.",
        ),
        Publication(
            title="Granskning av trygghet och studiero",
            url="/pub/5",
            published=date(2023, 11, 18),
            type="kvalitetsgranskning",
            summary="Granskning av hur skolor arbetar med trygghet.",
        ),
    ]


@pytest.fixture
def sample_press_release() -> PressRelease:
    """Create a sample press release for testing."""
    return PressRelease(
        title="Nya resultat från skolenkäten",
        url="/om-oss/press/pressmeddelanden/2024/nya-resultat",
        published=date(2024, 3, 1),
    )


@pytest.fixture
def sample_statistics_file() -> StatisticsFile:
    """Create a sample statistics file for testing."""
    return StatisticsFile(
        name="Tillståndsbeslut 2023",
        url="/globalassets/statistik/tillstandsbeslut-2023.xlsx",
        file_type="xlsx",
        category="tillstand",
        year=2023,
        description="Statistik över tillståndsbeslut 2023",
    )


@pytest.fixture
def sample_index(
    sample_publications: list[Publication],
    sample_press_release: PressRelease,
    sample_statistics_file: StatisticsFile,
) -> Index:
    """Create a sample index for testing."""
    return Index(
        publications=sample_publications,
        press_releases=[sample_press_release],
        statistics_files=[sample_statistics_file],
        last_updated=datetime.now().isoformat(),
    )


@pytest.fixture
def mock_html_publication_list() -> str:
    """Sample HTML for publication list page."""
    return """
    <html>
    <body>
        <div class="search-result-item">
            <h2><a href="/publikationer/kvalitetsgranskning/2024/test">Test Rapport 2024</a></h2>
            <time datetime="2024-03-15">15 mars 2024</time>
            <p>Sammanfattning av rapporten.</p>
            <a href="/globalassets/rapport.pdf">Ladda ner PDF</a>
        </div>
        <div class="search-result-item">
            <h2><a href="/publikationer/tillsyn/2024/tillsyn-test">Tillsyn av testskola</a></h2>
            <time datetime="2024-02-10">10 februari 2024</time>
            <p>Tillsynsrapport.</p>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_html_publication_detail() -> str:
    """Sample HTML for publication detail page."""
    return """
    <html>
    <head><title>Test Rapport 2024</title></head>
    <body>
        <article>
            <h1>Test Rapport 2024</h1>
            <div class="metadata">
                <span class="date">2024-03-15</span>
                <span class="diarienummer">SI 2024:1234</span>
            </div>
            <div class="content">
                <h2>Sammanfattning</h2>
                <p>Detta är en testrapport om kvalitet i skolan.</p>
                <h2>Bakgrund</h2>
                <p>Skolinspektionen har genomfört en granskning.</p>
            </div>
        </article>
    </body>
    </html>
    """


@pytest.fixture
def respx_mock():
    """Set up respx mock for HTTP requests."""
    with respx.mock(assert_all_called=False) as mock:
        yield mock


@pytest.fixture
def index_json_content(sample_index: Index) -> str:
    """Generate JSON content for index file."""
    return json.dumps(sample_index.model_dump(mode="json"), ensure_ascii=False)
