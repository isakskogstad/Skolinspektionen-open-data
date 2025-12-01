"""Ombedömning nationella prov (national test re-evaluation) data service.

This module provides access to Skolinspektionen's reports on re-evaluation
of national tests. Note: The data is only available as PDF reports, not
structured Excel data.

Ombedömning is when Skolinspektionen re-grades a sample of national tests
to assess consistency in grading across Sweden.
"""

import logging
from pathlib import Path
from typing import Optional

from .models import OmbedomningRapport, OmbedomningSummary

logger = logging.getLogger(__name__)

# Base URL for Skolinspektionen's website
BASE_URL = "https://www.skolinspektionen.se"

# Catalog of known ombedömning reports (manually curated from PDF files found)
OMBEDOMNING_REPORTS: list[OmbedomningRapport] = [
    OmbedomningRapport(
        title="Ombedömning av nationella prov 2019 (Omgång 10)",
        year=2019,
        test_year=2019,
        omgang=10,
        filename="onp-omg10.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/redovisning-av-regeringsuppdrag/2019/onp-omg10.pdf",
        description="Slutrapport för omgång 10 av ombedömning av nationella prov. "
                    "Fortsatt stora skillnader i bedömning mellan lärare och externa bedömare.",
        subjects=["Svenska", "Engelska", "Matematik", "NO", "SO"],
        grades=["åk 3", "åk 6", "åk 9", "gymnasiet"],
    ),
    OmbedomningRapport(
        title="Ombedömning av nationella prov 2017 - Fortsatt stora skillnader",
        year=2018,
        test_year=2017,
        omgang=9,
        filename="ombedomning-av-nationella-prov-2017-fortsatt-stora-skillnader.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/redovisning-av-regeringsuppdrag/2018/ombedomning-av-nationella-prov-2017-fortsatt-stora-skillnader.pdf",
        description="Rapport som visar att betydande skillnader kvarstår i hur lärare "
                    "bedömer nationella prov jämfört med externa bedömare.",
        subjects=["Svenska", "Engelska", "Matematik"],
        grades=["åk 3", "åk 6", "åk 9", "gymnasiet"],
    ),
    OmbedomningRapport(
        title="Ombedömning av nationella prov 2016 (Omgång 8)",
        year=2017,
        test_year=2016,
        omgang=8,
        filename="ombedomning_nationellaprov_omg8_slutgiltig.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/redovisning-av-regeringsuppdrag/2017/ombedomning_nationellaprov_omg8_slutgiltig.pdf",
        description="Slutrapport för omgång 8. Visar fortsatta brister i likvärdighet "
                    "vid bedömning av nationella prov.",
        subjects=["Svenska", "Engelska", "Matematik"],
        grades=["åk 3", "åk 6", "åk 9", "gymnasiet"],
    ),
    OmbedomningRapport(
        title="Ombedömning av nationella prov 2015",
        year=2016,
        test_year=2015,
        omgang=7,
        filename="ombedomning-av-nationella-prov-2015.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/redovisning-av-regeringsuppdrag/2016/ombedomning-av-nationella-prov-2015.pdf",
        description="Rapport om ombedömning av nationella prov genomförda 2015.",
        subjects=["Svenska", "Engelska", "Matematik"],
        grades=["åk 3", "åk 6", "åk 9", "gymnasiet"],
    ),
    OmbedomningRapport(
        title="Slutrapport Ombedömning nationella prov 2014",
        year=2015,
        test_year=2014,
        omgang=6,
        filename="slutrapport_ombedomning_nationella_prov_2014_151116.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/redovisning-av-regeringsuppdrag/2015/slutrapport_ombedomning_nationella_prov_2014_151116.pdf",
        description="Slutrapport för ombedömning av nationella prov 2014. "
                    "Sammanfattar resultat från omgång 6.",
        subjects=["Svenska", "Engelska", "Matematik"],
        grades=["åk 3", "åk 6", "åk 9", "gymnasiet"],
    ),
    OmbedomningRapport(
        title="Omrättning av nationella prov 2013",
        year=2013,
        test_year=2013,
        omgang=4,
        filename="omrattning-nationella-prov-2013.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/regeringsrapporter/redovisning-av-regeringsuppdrag/2013/omrattning-nationella-prov-2013.pdf",
        description="Rapport om omrättning av nationella prov 2013. "
                    "Visar systematiska skillnader i bedömning.",
        subjects=["Svenska", "Engelska", "Matematik"],
        grades=["åk 3", "åk 6", "åk 9"],
    ),
    OmbedomningRapport(
        title="Omrättning 2011 - Slutrapport",
        year=2011,
        test_year=2011,
        omgang=1,
        filename="omratt2011-slutrapport.pdf",
        url=f"{BASE_URL}/globalassets/02-beslut-rapporter-stat/granskningsrapporter/ovriga-publikationer/2011/omrattning/omratt2011-slutrapport.pdf",
        description="Första omgången av systematisk omrättning av nationella prov. "
                    "Grundlade metodiken för framtida ombedömningar.",
        subjects=["Svenska", "Matematik"],
        grades=["åk 3", "åk 9"],
    ),
]


def get_all_reports() -> list[OmbedomningRapport]:
    """Get all available ombedömning reports.

    Returns:
        List of OmbedomningRapport objects sorted by year (newest first)
    """
    return sorted(OMBEDOMNING_REPORTS, key=lambda r: r.year, reverse=True)


def get_report_by_year(year: int) -> Optional[OmbedomningRapport]:
    """Get ombedömning report for a specific year.

    Args:
        year: Publication year of the report

    Returns:
        OmbedomningRapport or None if not found
    """
    for report in OMBEDOMNING_REPORTS:
        if report.year == year:
            return report
    return None


def get_reports_by_test_year(test_year: int) -> list[OmbedomningRapport]:
    """Get reports covering tests from a specific year.

    Args:
        test_year: Year when the tests were administered

    Returns:
        List of matching reports
    """
    return [r for r in OMBEDOMNING_REPORTS if r.test_year == test_year]


def get_latest_report() -> Optional[OmbedomningRapport]:
    """Get the most recent ombedömning report.

    Returns:
        The latest OmbedomningRapport or None
    """
    reports = get_all_reports()
    return reports[0] if reports else None


def get_summary() -> OmbedomningSummary:
    """Get summary of all available ombedömning reports.

    Returns:
        OmbedomningSummary with aggregated statistics
    """
    reports = get_all_reports()

    # Collect all unique subjects
    all_subjects = set()
    for report in reports:
        all_subjects.update(report.subjects)

    return OmbedomningSummary(
        total_reports=len(reports),
        years_available=sorted([r.year for r in reports], reverse=True),
        latest_report=get_latest_report(),
        subjects_covered=sorted(all_subjects),
    )


def discover_local_pdfs(base_path: Path) -> list[Path]:
    """Discover locally available ombedömning PDF files.

    Args:
        base_path: Base directory to search (e.g., downloaded website mirror)

    Returns:
        List of paths to PDF files
    """
    patterns = [
        "**/ombedomning*.pdf",
        "**/omratt*.pdf",
        "**/onp*.pdf",
        "**/*nationella*prov*.pdf",
    ]

    found = []
    seen = set()
    for pattern in patterns:
        for f in base_path.glob(pattern):
            if f.name not in seen and not f.name.startswith("~"):
                seen.add(f.name)
                found.append(f)

    return sorted(found, key=lambda p: p.name, reverse=True)


def update_local_paths(base_path: Path) -> int:
    """Update local_path for reports that exist locally.

    Args:
        base_path: Base directory where PDF files are stored

    Returns:
        Number of reports with local paths updated
    """
    count = 0
    local_files = discover_local_pdfs(base_path)
    local_by_name = {f.name: f for f in local_files}

    for report in OMBEDOMNING_REPORTS:
        if report.filename in local_by_name:
            report.local_path = str(local_by_name[report.filename])
            count += 1

    return count
