"""
FL Health CHARTS scraper (v2)
=============================
Pulls county-level vaccine-preventable disease case counts from the
Florida Department of Health CHARTS portal.

The old single-report endpoint (Chapt7.T7_2) is gone. CHARTS now exposes
per-disease DataViewer pages keyed by a content ID (cid). Data is embedded
directly in the page HTML (not AJAX), in a table with id=dtChartDataGrid_CountsOnly.

Strategy
--------
For each of the 12 tracked diseases:
  1. GET the DataViewer page to extract the CSRF token (rdCSRFKey).
  2. POST with each FL county name + "All" years selection to get that county's
     full time-series.
  3. Parse the HTML table: rows are (year, county_count, fl_count).
  4. Upsert new rows into disease_cases.

Requests are batched (CONCURRENCY tasks at a time) to avoid hammering the portal.

Run standalone:
    python -m backend.scrapers.fl_charts

Or import and call ``scrape_and_store()`` from a scheduler.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.database import AsyncSessionLocal, Disease, DiseaseCase
from backend.models.database import County as CountyModel

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CHARTS configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.flhealthcharts.gov"
DATAVIEWER_URL = f"{BASE_URL}/ChartsReports/rdPage.aspx"

# Disease name (matches diseases.name in DB) → CHARTS content ID (cid)
DISEASE_CID_MAP: dict[str, int] = {
    "Measles":                129,
    "Mumps":                  155,
    "Rubella":                157,
    "Pertussis":              156,
    "Varicella":              8633,
    "Hepatitis A":            154,
    "Hepatitis B":            8659,
    "Meningococcal Disease":  8662,
    "Haemophilus Influenzae": 167,
    "Tetanus":                168,
    "Diphtheria":             161,
    "Poliomyelitis":          162,
}

# CHARTS DataViewer report name for individual disease counts by county
REPORT_NAME = "NonVitalIndNoGrpCounts.DataViewer"

# Concurrent HTTP requests (stay polite to the public portal)
CONCURRENCY = 8

# Years to ingest on a full refresh (set to None to get all available years)
LOOKBACK_YEARS = 5

REQUEST_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# County name helpers
# ---------------------------------------------------------------------------

# CHARTS uses county names without "County" suffix.
# Most match exactly (e.g. "Alachua"), but a few need mapping.
_FIPS_TO_CHARTS_NAME: dict[str, str] = {
    "12086": "Miami-Dade",   # DB stores as "Miami-Dade", CHARTS may use same
    "12109": "St. Johns",    # might be "St Johns" in CHARTS
    "12111": "St. Lucie",    # might be "St Lucie"
}


def _charts_county_name(db_name: str, fips_code: str) -> str:
    """
    Convert the DB county name to the name used in the CHARTS county dropdown.
    Most are identical; a handful need normalisation.
    """
    if fips_code in _FIPS_TO_CHARTS_NAME:
        return _FIPS_TO_CHARTS_NAME[fips_code]
    # Strip " County" suffix if present (shouldn't be, but defensive)
    return db_name.replace(" County", "").strip()


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

async def _get_csrf_token(client: httpx.AsyncClient, cid: int) -> str:
    """
    GET the DataViewer page for a disease and extract the rdCSRFKey token.
    Returns an empty string if the token is not found (page still works without
    it on some CHARTS versions, but include it for safety).
    """
    params = {"rdReport": REPORT_NAME, "cid": cid}
    resp = await client.get(DATAVIEWER_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Try hidden input named rdCSRFKey
    csrf_input = soup.find("input", {"name": "rdCSRFKey"})
    if csrf_input:
        return csrf_input.get("value", "")

    # Fallback: scan all hidden inputs
    for inp in soup.find_all("input", type="hidden"):
        name = inp.get("name", "")
        if "csrf" in name.lower() or "csrfkey" in name.lower():
            return inp.get("value", "")

    return ""


async def _fetch_county_html(
    client: httpx.AsyncClient,
    cid: int,
    csrf_token: str,
    county_name: str,
) -> str:
    """
    POST the DataViewer form for a specific disease + county (all available years).
    Returns the raw HTML response text, or "" on failure.
    """
    payload = {
        "rdReport": REPORT_NAME,
        "cid": str(cid),
        "rdCSRFKey": csrf_token,
        "county": county_name,
        # Omitting county_year (or leaving empty) returns all available years
        "county_year": "",
    }
    try:
        resp = await client.post(
            DATAVIEWER_URL,
            data=payload,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        log.warning("HTTP error for cid=%d county=%r: %s", cid, county_name, exc)
        return ""


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _parse_county_table(html: str, county_fips: str) -> list[dict]:
    """
    Parse the HTML table (id=dtChartDataGrid_CountsOnly) from a CHARTS
    DataViewer response.

    Expected columns: Data Year | <County> Count | Florida Count

    Returns a list of dicts:
        { county_fips, year, case_count, report_date, source }
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")

    # Primary: find by table ID
    table = soup.find("table", {"id": "dtChartDataGrid_CountsOnly"})
    if table is None:
        # Fallback: find any table with "Year" in the first header cell
        for t in soup.find_all("table"):
            headers = [th.get_text(strip=True) for th in t.find_all("th")]
            if headers and "Year" in headers[0]:
                table = t
                break

    if table is None:
        return []

    rows: list[dict] = []
    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue

        # Skip header rows
        try:
            year = int(cells[0])
        except ValueError:
            continue
        if year < 1990 or year > datetime.now().year:
            continue

        # Column 1 is county count, column 2 is FL statewide count
        try:
            count_str = cells[1].replace(",", "").strip()
            case_count = int(count_str) if count_str not in ("", "--", "N/A", "*") else 0
        except ValueError:
            case_count = 0

        rows.append({
            "county_fips": county_fips,
            "year": year,
            "case_count": case_count,
            "report_date": date(year, 12, 31),  # annual total → end-of-year
            "source": f"FL CHARTS (cid={county_fips}:{year})",
        })

    return rows


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _build_lookup_maps(session) -> tuple[dict[str, str], dict[str, int]]:
    """Return (fips → county_db_name, disease_name_lower → disease_id) dicts."""
    counties_result = await session.execute(select(CountyModel))
    counties = counties_result.scalars().all()
    fips_to_name: dict[str, str] = {c.fips_code: c.name for c in counties}

    diseases_result = await session.execute(select(Disease))
    disease_map: dict[str, int] = {
        d.name: d.id for d in diseases_result.scalars().all()
    }
    return fips_to_name, disease_map


# ---------------------------------------------------------------------------
# Core scrape worker
# ---------------------------------------------------------------------------

async def _scrape_disease_county(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    cid: int,
    csrf_token: str,
    disease_id: int,
    disease_name: str,
    county_fips: str,
    county_charts_name: str,
    lookback_years: int | None,
) -> list[dict]:
    """
    Fetch and parse case data for one disease × one county combination.
    Returns a list of upsert-ready row dicts.
    """
    async with semaphore:
        html = await _fetch_county_html(client, cid, csrf_token, county_charts_name)

    rows = _parse_county_table(html, county_fips)

    if lookback_years is not None:
        cutoff = datetime.now().year - lookback_years + 1
        rows = [r for r in rows if r["year"] >= cutoff]

    # Attach disease_id to each row
    for r in rows:
        r["disease_id"] = disease_id
        r["source"] = f"FL CHARTS {disease_name} {r['year']}"

    log.debug(
        "cid=%d %s / %s → %d rows",
        cid, disease_name, county_charts_name, len(rows)
    )
    return rows


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def scrape_and_store(lookback_years: int | None = LOOKBACK_YEARS) -> int:
    """
    Scrape CHARTS for all tracked diseases × all FL counties and upsert results
    into disease_cases.

    Args:
        lookback_years: How many years back to ingest. None = all available years.

    Returns:
        Number of new rows inserted.
    """
    inserted = 0
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with httpx.AsyncClient(
        headers={"User-Agent": "FL-Outbreak-Tracker/1.0 (public health research)"},
        follow_redirects=True,
    ) as client:
        async with AsyncSessionLocal() as session:
            fips_to_name, disease_map = await _build_lookup_maps(session)

        # Build the list of (disease_name, disease_id, cid) to process
        tasks_meta: list[tuple[str, int, int]] = []
        for disease_name, cid in DISEASE_CID_MAP.items():
            disease_id = disease_map.get(disease_name)
            if disease_id is None:
                log.warning("Disease %r not found in DB — skipping", disease_name)
                continue
            tasks_meta.append((disease_name, disease_id, cid))

        log.info(
            "Scraping %d diseases × %d counties …",
            len(tasks_meta), len(fips_to_name)
        )

        for disease_name, disease_id, cid in tasks_meta:
            log.info("Fetching CHARTS DataViewer for %s (cid=%d) …", disease_name, cid)

            try:
                csrf_token = await _get_csrf_token(client, cid)
            except Exception as exc:
                log.error("Could not load DataViewer for %s: %s", disease_name, exc)
                continue

            # Fan out: one async task per county
            county_tasks = [
                _scrape_disease_county(
                    client=client,
                    semaphore=semaphore,
                    cid=cid,
                    csrf_token=csrf_token,
                    disease_id=disease_id,
                    disease_name=disease_name,
                    county_fips=fips,
                    county_charts_name=_charts_county_name(name, fips),
                    lookback_years=lookback_years,
                )
                for fips, name in fips_to_name.items()
            ]
            county_results = await asyncio.gather(*county_tasks, return_exceptions=True)

            # Flatten results and upsert
            disease_inserted = 0
            async with AsyncSessionLocal() as session:
                for result in county_results:
                    if isinstance(result, Exception):
                        log.error("County task failed: %s", result)
                        continue
                    for row in result:
                        existing = await session.execute(
                            select(DiseaseCase).where(
                                DiseaseCase.county_fips == row["county_fips"],
                                DiseaseCase.disease_id == row["disease_id"],
                                DiseaseCase.report_date == row["report_date"],
                            )
                        )
                        if existing.scalar_one_or_none() is not None:
                            continue

                        session.add(DiseaseCase(
                            report_date=row["report_date"],
                            county_fips=row["county_fips"],
                            disease_id=row["disease_id"],
                            case_count=row["case_count"],
                            source=row["source"],
                        ))
                        disease_inserted += 1
                        inserted += 1

                await session.commit()
                log.info("%s: %d new rows inserted", disease_name, disease_inserted)

    log.info("CHARTS scrape complete — %d new rows inserted.", inserted)
    return inserted


async def _dry_run_single(disease_name: str = "Measles", county_name: str = "Alachua") -> None:
    """
    Fetch and print parsed rows for ONE disease × county without writing to DB.
    Useful for verifying the scraper works before a full run.

    Usage:
        python -m backend.scrapers.fl_charts --dry-run
        python -m backend.scrapers.fl_charts --dry-run Pertussis Broward
    """
    cid = DISEASE_CID_MAP.get(disease_name)
    if cid is None:
        print(f"Unknown disease: {disease_name!r}. Options: {list(DISEASE_CID_MAP)}")
        return

    print(f"Dry run: {disease_name} (cid={cid}) / {county_name} county …")

    async with httpx.AsyncClient(
        headers={"User-Agent": "FL-Outbreak-Tracker/1.0 (public health research)"},
        follow_redirects=True,
    ) as client:
        csrf = await _get_csrf_token(client, cid)
        print(f"  CSRF token: {csrf!r}")

        html = await _fetch_county_html(client, cid, csrf, county_name)
        print(f"  HTML length: {len(html)} chars")

        rows = _parse_county_table(html, county_fips="TEST")
        print(f"  Parsed {len(rows)} rows:")
        for r in rows[-10:]:  # show last 10 years
            print(f"    {r['year']}: {r['case_count']} cases")

        if not rows:
            print("  ⚠ No data parsed — check HTML structure or county_name spelling")


if __name__ == "__main__":
    import sys as _sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args = _sys.argv[1:]
    if args and args[0] == "--dry-run":
        disease_arg = args[1] if len(args) > 1 else "Measles"
        county_arg  = args[2] if len(args) > 2 else "Alachua"
        asyncio.run(_dry_run_single(disease_arg, county_arg))
    else:
        asyncio.run(scrape_and_store())
