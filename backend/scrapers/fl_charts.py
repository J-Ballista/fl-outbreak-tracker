"""
FL Health CHARTS scraper (v2)
=============================
Pulls county-level vaccine-preventable disease case counts from the
Florida Department of Health CHARTS portal.

The old single-report endpoint (Chapt7.T7_2) is gone. CHARTS now exposes
per-disease DataViewer pages keyed by a content ID (cid). Data is embedded
directly in the page HTML (not AJAX), in a table with id=dtChartDataGrid_CountsOnly.

Verified mechanics (2026-04)
----------------------------
1. GET  rdPage.aspx?rdReport=NonVitalIndNoGrpCounts.DataViewer&cid=<CID>
   → 200 HTML (54 KB); extracts CSRF token + all hidden fields + county dropdown
     (numeric values 1-67, not names).
2. POST rdPage.aspx with all hidden fields + county=<NUM> + county_year=<YEAR> + FL_Year=<YEAR>
   → 200 HTML; table dtChartDataGrid_CountsOnly contains ALL available years for that county.
   (county_year only controls the bar chart; the HTML table always shows the full time-series.)

One POST per county per disease → 67 × 12 = 804 total requests, async-batched.

Run standalone:
    python -m backend.scrapers.fl_charts                      # full ingest
    python -m backend.scrapers.fl_charts --dry-run            # test Measles / Alachua
    python -m backend.scrapers.fl_charts --dry-run Pertussis Broward
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import NamedTuple

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
REPORT_NAME = "NonVitalIndNoGrpCounts.DataViewer"

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

# Concurrent HTTP requests
CONCURRENCY = 8

# Years to retain on ingest (None = all available, typically back to 2011)
LOOKBACK_YEARS = 10

REQUEST_TIMEOUT = 30.0

CURRENT_YEAR = datetime.now().year


# ---------------------------------------------------------------------------
# Page context (extracted once per disease from the GET response)
# ---------------------------------------------------------------------------

class PageContext(NamedTuple):
    hidden_fields: dict[str, str]          # all hidden form inputs
    county_options: dict[str, str]         # normalised county name → numeric value
    latest_year: str                       # most recent year in the year dropdown


def _normalise(name: str) -> str:
    """Lowercase, strip punctuation/spaces for fuzzy county name matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


async def _get_page_context(client: httpx.AsyncClient, cid: int) -> PageContext:
    """
    GET the DataViewer page and extract:
      - all hidden form fields (CSRF token, cid, etc.)
      - county dropdown options  {normalised_name → numeric_value}
      - the most recent year available
    """
    params = {"rdReport": REPORT_NAME, "cid": cid}
    resp = await client.get(DATAVIEWER_URL, params=params, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Collect hidden fields (first occurrence wins for duplicates)
    hidden: dict[str, str] = {}
    for inp in soup.find_all("input"):
        if inp.get("type", "").upper() == "HIDDEN":
            name = inp.get("name", "")
            if name and name not in hidden:
                hidden[name] = inp.get("value", "")

    # County dropdown: text = county name, value = numeric string (1-67)
    county_opts: dict[str, str] = {}
    county_sel = soup.find("select", {"name": "county"})
    if county_sel:
        for opt in county_sel.find_all("option"):
            text = opt.get_text(strip=True)
            val = opt.get("value", "")
            if text and val:
                county_opts[_normalise(text)] = val

    # Year dropdown — first option is the most recent
    latest_year = str(CURRENT_YEAR - 1)
    year_sel = soup.find("select", {"name": "county_year"})
    if year_sel:
        first_opt = year_sel.find("option")
        if first_opt:
            latest_year = first_opt.get("value", latest_year)

    return PageContext(
        hidden_fields=hidden,
        county_options=county_opts,
        latest_year=latest_year,
    )


# ---------------------------------------------------------------------------
# HTTP fetch
# ---------------------------------------------------------------------------

async def _fetch_county_html(
    client: httpx.AsyncClient,
    cid: int,
    ctx: PageContext,
    county_value: str,
) -> str:
    """
    POST the DataViewer form for one disease × county.
    Returns the response HTML (contains the full time-series table).
    """
    payload = {
        **ctx.hidden_fields,
        "rdReport": REPORT_NAME,
        "county": county_value,
        "county_year": ctx.latest_year,
        "FL_Year": ctx.latest_year,
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
        log.warning("HTTP error cid=%d county_val=%r: %s", cid, county_value, exc)
        return ""


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _parse_county_table(
    html: str,
    county_fips: str,
    disease_id: int,
    disease_name: str,
    lookback_years: int | None,
) -> list[dict]:
    """
    Parse the dtChartDataGrid_CountsOnly HTML table.

    Table structure (verified):
        Row 0: ['', 'Alachua', 'Florida']          ← county/state header
        Row 1: ['Data Year', 'Count', 'Count']      ← column header
        Row 2+: ['2024', '0', '12']                 ← data rows

    Returns upsert-ready dicts with keys:
        report_date, county_fips, disease_id, case_count, source
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", {"id": "dtChartDataGrid_CountsOnly"})
    if table is None:
        return []

    cutoff = (CURRENT_YEAR - lookback_years + 1) if lookback_years else 0
    rows: list[dict] = []

    for tr in table.find_all("tr"):
        cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
        if len(cells) < 2:
            continue
        try:
            year = int(cells[0])
        except ValueError:
            continue
        if year < max(1990, cutoff) or year > CURRENT_YEAR:
            continue

        raw = cells[1].replace(",", "").strip()
        try:
            case_count = int(raw) if raw not in ("", "--", "N/A", "*") else 0
        except ValueError:
            case_count = 0

        rows.append({
            "report_date": date(year, 12, 31),
            "county_fips": county_fips,
            "disease_id": disease_id,
            "case_count": case_count,
            "source": f"FL CHARTS {disease_name} {year}",
        })

    return rows


# ---------------------------------------------------------------------------
# Async worker
# ---------------------------------------------------------------------------

async def _scrape_one_county(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    cid: int,
    ctx: PageContext,
    county_fips: str,
    county_value: str,
    disease_id: int,
    disease_name: str,
    lookback_years: int | None,
) -> list[dict]:
    async with semaphore:
        html = await _fetch_county_html(client, cid, ctx, county_value)
    return _parse_county_table(html, county_fips, disease_id, disease_name, lookback_years)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _build_db_maps(session) -> tuple[dict[str, str], dict[str, int]]:
    """Return (fips → county_name, disease_name → disease_id)."""
    result = await session.execute(select(CountyModel))
    fips_to_name = {c.fips_code: c.name for c in result.scalars().all()}

    result2 = await session.execute(select(Disease))
    disease_map = {d.name: d.id for d in result2.scalars().all()}

    return fips_to_name, disease_map


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def scrape_and_store(lookback_years: int | None = LOOKBACK_YEARS) -> int:
    """
    Scrape CHARTS for all 12 tracked diseases × 67 FL counties and upsert
    results into disease_cases.

    Returns the number of new rows inserted.
    """
    inserted = 0
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async with AsyncSessionLocal() as session:
        fips_to_name, disease_map = await _build_db_maps(session)

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (FL-Outbreak-Tracker/2.0; public health research)"},
        follow_redirects=True,
    ) as client:
        for disease_name, cid in DISEASE_CID_MAP.items():
            disease_id = disease_map.get(disease_name)
            if disease_id is None:
                log.warning("Disease %r not in DB — skipping", disease_name)
                continue

            log.info("Loading DataViewer for %s (cid=%d) …", disease_name, cid)
            try:
                ctx = await _get_page_context(client, cid)
            except Exception as exc:
                log.error("Failed to load DataViewer for %s: %s", disease_name, exc)
                continue

            if not ctx.county_options:
                log.error("No county options found for %s — page may have changed", disease_name)
                continue

            log.info(
                "  %d county options; latest year=%s; %d hidden fields",
                len(ctx.county_options), ctx.latest_year, len(ctx.hidden_fields)
            )

            # Match DB counties to CHARTS county values
            county_tasks = []
            for fips, db_name in fips_to_name.items():
                key = _normalise(db_name)
                charts_val = ctx.county_options.get(key)
                if charts_val is None:
                    # Try stripping common suffixes ("County", "St." → "Saint")
                    alt = _normalise(db_name.replace("St.", "Saint").replace(" County", ""))
                    charts_val = ctx.county_options.get(alt)
                if charts_val is None:
                    log.debug("No CHARTS match for county %r (fips=%s)", db_name, fips)
                    continue
                county_tasks.append((fips, charts_val))

            log.info("  Matched %d/%d counties — fetching …", len(county_tasks), len(fips_to_name))

            results = await asyncio.gather(
                *[
                    _scrape_one_county(
                        client, semaphore, cid, ctx,
                        fips, val, disease_id, disease_name, lookback_years
                    )
                    for fips, val in county_tasks
                ],
                return_exceptions=True,
            )

            disease_inserted = 0
            async with AsyncSessionLocal() as session:
                for result in results:
                    if isinstance(result, Exception):
                        log.error("County task error: %s", result)
                        continue
                    for row in result:
                        exists = await session.execute(
                            select(DiseaseCase).where(
                                DiseaseCase.county_fips == row["county_fips"],
                                DiseaseCase.disease_id == row["disease_id"],
                                DiseaseCase.report_date == row["report_date"],
                            )
                        )
                        if exists.scalar_one_or_none() is not None:
                            continue
                        session.add(DiseaseCase(**row))
                        disease_inserted += 1
                        inserted += 1
                await session.commit()

            log.info("%s: %d new rows inserted", disease_name, disease_inserted)

    log.info("CHARTS scrape complete — %d total new rows inserted.", inserted)
    return inserted


# ---------------------------------------------------------------------------
# Dry-run (no DB writes)
# ---------------------------------------------------------------------------

async def _dry_run(disease_name: str = "Measles", county_name: str = "Alachua") -> None:
    """Fetch and print rows for ONE disease × county without touching the DB."""
    cid = DISEASE_CID_MAP.get(disease_name)
    if cid is None:
        print(f"Unknown disease: {disease_name!r}. Options:\n  {list(DISEASE_CID_MAP)}")
        return

    print(f"Dry run: {disease_name} (cid={cid}) / {county_name} …")

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (FL-Outbreak-Tracker/2.0)"},
        follow_redirects=True,
    ) as client:
        ctx = await _get_page_context(client, cid)
        print(f"  Hidden fields: {list(ctx.hidden_fields.keys())}")
        print(f"  County options in CHARTS: {len(ctx.county_options)}")
        print(f"  Latest year: {ctx.latest_year}")

        key = _normalise(county_name)
        val = ctx.county_options.get(key)
        if val is None:
            print(f"  ⚠ County {county_name!r} not matched. Available keys (sample):")
            for k, v in list(ctx.county_options.items())[:10]:
                print(f"    {k!r} → {v!r}")
            return
        print(f"  Matched {county_name!r} → CHARTS value={val!r}")

        html = await _fetch_county_html(client, cid, ctx, val)
        print(f"  Response HTML: {len(html)} chars")

        rows = _parse_county_table(html, "TEST_FIPS", disease_id=0, disease_name=disease_name, lookback_years=None)
        print(f"  Parsed {len(rows)} rows:")
        for r in rows:
            print(f"    {r['report_date'].year}: {r['case_count']} cases")
        if not rows:
            print("  ⚠ No rows parsed — inspect HTML table structure")


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
        asyncio.run(_dry_run(disease_arg, county_arg))
    else:
        asyncio.run(scrape_and_store())
