"""
FL Health CHARTS scraper
========================
Pulls county-level vaccine-preventable disease case counts from the
Florida Department of Health CHARTS (Community Health Assessment Resource
Tool Set) public data portal.

CHARTS exposes a query interface at:
  https://www.flhealthcharts.gov/ChartsReports/rdPage.aspx

We target the "Communicable Disease" section and POST a form request to
retrieve a CSV of annual/monthly case counts by county and disease.

Run standalone:
    python -m backend.scrapers.fl_charts

Or import and call ``scrape_and_store()`` from a scheduler.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import AsyncIterator

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

# Allow running as a top-level script from the project root
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.database import AsyncSessionLocal, Disease, DiseaseCase

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CHARTS configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.flhealthcharts.gov"
QUERY_URL = f"{BASE_URL}/ChartsReports/rdPage.aspx"

# Maps the CHARTS disease label → our diseases.name value.
# Extend this dict as new diseases are added to the diseases table.
DISEASE_NAME_MAP: dict[str, str] = {
    "Measles": "Measles",
    "Mumps": "Mumps",
    "Rubella": "Rubella",
    "Pertussis": "Pertussis",
    "Varicella": "Varicella",
    "Hepatitis A": "Hepatitis A",
    "Hepatitis B": "Hepatitis B",
    "Meningococcal Disease": "Meningococcal Disease",
    "Haemophilus Influenzae": "Haemophilus Influenzae",
    "Tetanus": "Tetanus",
    "Diphtheria": "Diphtheria",
    "Poliomyelitis": "Poliomyelitis",
}

# CHARTS report IDs for the communicable disease annual/monthly counts.
# These are the rdReport values used in the POST body.
CHARTS_REPORT_PARAMS: dict[str, str] = {
    "rdReport": "Chapt7.T7_2",      # VPD county counts table
    "RowSelector": "AllCounties",
    "ColSelector": "AllYears",
    "OutputType": "2",               # 2 = CSV download
}

# How many years back to ingest on a full refresh
LOOKBACK_YEARS = 5

# HTTP timeout (seconds)
REQUEST_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _get_form_token(client: httpx.AsyncClient) -> dict[str, str]:
    """
    Fetch the CHARTS query page and extract any hidden form fields
    (ASP.NET ViewState, EventValidation, etc.) needed for the POST.
    Returns a dict of field_name → value.
    """
    resp = await client.get(QUERY_URL, params={"rdReport": CHARTS_REPORT_PARAMS["rdReport"]})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")
    hidden: dict[str, str] = {}
    for inp in soup.find_all("input", type="hidden"):
        name = inp.get("name")
        value = inp.get("value", "")
        if name:
            hidden[name] = value
    return hidden


async def _fetch_csv(client: httpx.AsyncClient, year: int) -> str:
    """POST the CHARTS form for a given year and return the raw CSV text."""
    hidden = await _get_form_token(client)
    payload = {
        **hidden,
        **CHARTS_REPORT_PARAMS,
        "YearSelector": str(year),
    }
    resp = await client.post(QUERY_URL, data=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    # CHARTS returns CSV inline or as an attachment; handle both
    content_type = resp.headers.get("content-type", "")
    if "text/csv" in content_type or "application/octet-stream" in content_type:
        return resp.text
    # Sometimes the page returns HTML with an embedded download link
    soup = BeautifulSoup(resp.text, "lxml")
    link = soup.find("a", href=lambda h: h and h.endswith(".csv"))
    if link:
        csv_resp = await client.get(BASE_URL + link["href"])
        csv_resp.raise_for_status()
        return csv_resp.text
    raise RuntimeError(f"Could not locate CSV in CHARTS response for year {year}")


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _parse_charts_csv(raw_csv: str, year: int) -> list[dict]:
    """
    Parse a CHARTS CSV export into a list of row dicts with keys:
        county_name, disease_name, case_count, report_date
    Skips header/footer rows that don't represent county data.
    """
    reader = csv.DictReader(io.StringIO(raw_csv))
    rows: list[dict] = []
    for row in reader:
        # CHARTS CSVs vary in column naming — normalise to lowercase
        lower = {k.strip().lower(): v.strip() for k, v in row.items() if k}
        county = lower.get("county") or lower.get("county name", "")
        disease = lower.get("disease") or lower.get("disease name", "")
        count_str = lower.get("count") or lower.get("case count") or lower.get("cases", "0")

        # Skip summary / non-county rows
        if not county or county.lower() in {"total", "florida", "state", ""}:
            continue
        if not disease or disease not in DISEASE_NAME_MAP:
            continue

        try:
            case_count = int(count_str.replace(",", "") or "0")
        except ValueError:
            case_count = 0

        rows.append({
            "county_name": county.title(),
            "disease_name": DISEASE_NAME_MAP[disease],
            "case_count": case_count,
            "report_date": date(year, 12, 31),  # annual totals → end-of-year date
            "source": f"FL CHARTS {year}",
        })
    return rows


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _build_lookup_maps(session) -> tuple[dict[str, str], dict[str, int]]:
    """Return (county_name_to_fips, disease_name_to_id) lookup dicts."""
    from backend.models.database import County

    counties_result = await session.execute(select(County))
    county_map: dict[str, str] = {
        c.name.lower(): c.fips_code for c in counties_result.scalars().all()
    }

    diseases_result = await session.execute(select(Disease))
    disease_map: dict[str, int] = {
        d.name.lower(): d.id for d in diseases_result.scalars().all()
    }
    return county_map, disease_map


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def scrape_and_store(years: list[int] | None = None) -> int:
    """
    Scrape CHARTS for the given years (default: last LOOKBACK_YEARS years)
    and upsert results into disease_cases.

    Returns the number of new rows inserted.
    """
    current_year = datetime.now().year
    if years is None:
        years = list(range(current_year - LOOKBACK_YEARS + 1, current_year + 1))

    inserted = 0

    async with httpx.AsyncClient(follow_redirects=True) as client:
        async with AsyncSessionLocal() as session:
            county_map, disease_map = await _build_lookup_maps(session)

            for year in years:
                log.info("Fetching CHARTS data for %d …", year)
                try:
                    raw_csv = await _fetch_csv(client, year)
                except Exception as exc:
                    log.error("Failed to fetch CHARTS data for %d: %s", year, exc)
                    continue

                rows = _parse_charts_csv(raw_csv, year)
                log.info("Parsed %d rows for %d", len(rows), year)

                for row in rows:
                    county_fips = county_map.get(row["county_name"].lower())
                    disease_id = disease_map.get(row["disease_name"].lower())

                    if county_fips is None:
                        log.debug("Unknown county: %r", row["county_name"])
                        continue
                    if disease_id is None:
                        log.debug("Disease not in DB: %r", row["disease_name"])
                        continue

                    # Check for existing record (county + disease + date)
                    existing = await session.execute(
                        select(DiseaseCase).where(
                            DiseaseCase.county_fips == county_fips,
                            DiseaseCase.disease_id == disease_id,
                            DiseaseCase.report_date == row["report_date"],
                        )
                    )
                    if existing.scalar_one_or_none() is not None:
                        continue  # already ingested

                    session.add(
                        DiseaseCase(
                            report_date=row["report_date"],
                            county_fips=county_fips,
                            disease_id=disease_id,
                            case_count=row["case_count"],
                            source=row["source"],
                        )
                    )
                    inserted += 1

                await session.commit()

    log.info("CHARTS scrape complete — %d new rows inserted.", inserted)
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(scrape_and_store())
