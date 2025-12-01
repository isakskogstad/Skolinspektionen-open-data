"""Kolada API client for municipal education statistics.

This module provides access to education-related KPIs from Kolada
(the Swedish municipality and county database) to complement
Skolinspektionen inspection data.
"""

import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

KOLADA_BASE_URL = "https://api.kolada.se/v2"

# Education-related KPIs that complement Skolinspektionen data
EDUCATION_KPIS = {
    # Grundskola (compulsory school)
    "N15005": "Kostnad grundskola, kr/elev",
    "N15030": "Elever/lärare (årsarbetare) i grundskolan, kommunal regi, antal",
    "N15406": "Elever i åk 9 med godkänt betyg i alla ämnen, hemkommun, andel (%)",
    "N15425": "Elever i åk 9 som uppnått kunskapskraven i alla ämnen, hemkommun, andel (%)",
    "N15451": "Elever i åk 9 med godkända betyg i engelska, matematik och svenska/svenska som andraspråk, hemkommun, andel (%)",
    "N15428": "Genomsnittligt meritvärde (17 ämnen), åk 9, hemkommun",
    "N15500": "Behöriga lärare i grundskolan, kommunal regi, andel (%)",
    "N15507": "Elever per lärare, lägeskommun, grundskola, antal",
    # Gymnasieskola (upper secondary)
    "N17005": "Kostnad gymnasieskola hemkommun, kr/elev",
    "N17445": "Gymnasieelever med examen inom 3 år, hemkommun, andel (%)",
    "N17473": "Gymnasieelever som uppnått grundläggande behörighet till universitet och högskola inom 3 år, hemkommun, andel (%)",
    "N17500": "Behöriga lärare i gymnasieskolan, kommunal regi, andel (%)",
    # Förskola (preschool)
    "N11008": "Kostnad förskola, kr/inskrivet barn",
    "N11041": "Heltidstjänster i förskolan med förskollärarexamen, lägeskommun, andel (%)",
    "N11701": "Barn per barngrupp i förskola, lägeskommun, antal",
}


async def search_municipalities(query: str, limit: int = 10) -> list[dict]:
    """Search for municipalities by name.

    Args:
        query: Search term
        limit: Maximum results to return

    Returns:
        List of municipality dicts with id and title
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{KOLADA_BASE_URL}/municipality",
            params={"title": query},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        results = []
        for m in data.get("values", [])[:limit]:
            results.append({
                "id": m["id"],
                "title": m["title"],
                "type": m.get("type", "K"),  # K=kommun, L=landsting
            })
        return results


async def get_municipality(municipality_id: str) -> Optional[dict]:
    """Get municipality details.

    Args:
        municipality_id: Municipality ID (e.g., "0180" for Stockholm)

    Returns:
        Municipality dict or None
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{KOLADA_BASE_URL}/municipality/{municipality_id}",
            timeout=30,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        values = data.get("values", [])
        return values[0] if values else None


async def get_kpi_data(
    kpi_id: str,
    municipality_id: str,
    year: Optional[int] = None,
) -> list[dict]:
    """Get KPI data for a municipality.

    Args:
        kpi_id: KPI identifier (e.g., "N15428")
        municipality_id: Municipality ID (e.g., "0180")
        year: Optional year filter

    Returns:
        List of data points with period and value
    """
    async with httpx.AsyncClient() as client:
        url = f"{KOLADA_BASE_URL}/data/kpi/{kpi_id}/municipality/{municipality_id}"
        if year:
            url += f"/year/{year}"

        response = await client.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("values", []):
            for val in item.get("values", []):
                if val.get("value") is not None:
                    results.append({
                        "period": item.get("period"),
                        "value": val.get("value"),
                        "gender": val.get("gender", "T"),  # T=total
                    })
        return results


async def get_education_stats(
    municipality_id: str,
    year: Optional[int] = None,
    kpi_ids: Optional[list[str]] = None,
) -> dict:
    """Get comprehensive education statistics for a municipality.

    Args:
        municipality_id: Municipality ID
        year: Optional year filter
        kpi_ids: Optional list of KPI IDs to fetch (defaults to EDUCATION_KPIS)

    Returns:
        Dict mapping KPI names to values
    """
    kpis_to_fetch = kpi_ids or list(EDUCATION_KPIS.keys())

    results = {
        "municipality_id": municipality_id,
        "year": year,
        "kpis": {},
    }

    async with httpx.AsyncClient() as client:
        for kpi_id in kpis_to_fetch:
            try:
                url = f"{KOLADA_BASE_URL}/data/kpi/{kpi_id}/municipality/{municipality_id}"
                if year:
                    url += f"/year/{year}"

                response = await client.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("values", []):
                        for val in item.get("values", []):
                            if val.get("value") is not None and val.get("gender") == "T":
                                results["kpis"][kpi_id] = {
                                    "title": EDUCATION_KPIS.get(kpi_id, kpi_id),
                                    "value": val["value"],
                                    "period": item.get("period"),
                                }
                                break
            except Exception as e:
                logger.debug(f"Failed to fetch KPI {kpi_id}: {e}")
                continue

    return results


async def compare_municipalities(
    municipality_ids: list[str],
    kpi_id: str,
    year: Optional[int] = None,
) -> list[dict]:
    """Compare a KPI across multiple municipalities.

    Args:
        municipality_ids: List of municipality IDs
        kpi_id: KPI to compare
        year: Optional year filter

    Returns:
        List of comparison results
    """
    results = []

    async with httpx.AsyncClient() as client:
        for muni_id in municipality_ids:
            try:
                # Get municipality name
                muni_resp = await client.get(
                    f"{KOLADA_BASE_URL}/municipality/{muni_id}",
                    timeout=30,
                )
                muni_data = muni_resp.json().get("values", [{}])[0]
                muni_name = muni_data.get("title", muni_id)

                # Get KPI data
                url = f"{KOLADA_BASE_URL}/data/kpi/{kpi_id}/municipality/{muni_id}"
                if year:
                    url += f"/year/{year}"

                response = await client.get(url, timeout=30)
                if response.status_code == 200:
                    data = response.json()
                    for item in data.get("values", []):
                        for val in item.get("values", []):
                            if val.get("value") is not None and val.get("gender") == "T":
                                results.append({
                                    "municipality_id": muni_id,
                                    "municipality_name": muni_name,
                                    "kpi_id": kpi_id,
                                    "kpi_title": EDUCATION_KPIS.get(kpi_id, kpi_id),
                                    "value": val["value"],
                                    "period": item.get("period"),
                                })
                                break
            except Exception as e:
                logger.debug(f"Failed to fetch data for {muni_id}: {e}")
                continue

    # Sort by value descending
    results.sort(key=lambda x: x.get("value", 0), reverse=True)
    return results


def list_education_kpis() -> dict:
    """List available education KPIs.

    Returns:
        Dict mapping KPI IDs to descriptions
    """
    return EDUCATION_KPIS.copy()
