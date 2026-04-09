"""
FL DOH Religious Exemption Scraper
====================================
Pulls census-tract-level religious exemption counts from the FL DOH ArcGIS
service (UpdateThisMapNew, sourced from Florida SHOTS registry, updated monthly).

Aggregates census tracts to county level, then writes to vaccination_rates:
  - vaccinated_pct  = 100 - religious_exempt_pct  (approximation)
  - exempt_religious_pct = religious_exempt_pct
  - facility_type = "school_religious_exemption"
  - survey_year = current calendar year

One VaccinationRate row is written per disease per county so the existing
vaccination-rate API and map layer work unchanged.  Running this again for
the same year upserts (delete-then-insert) to avoid duplicates.

Run standalone:
    python -m backend.scrapers.fl_doh_exemptions

Or import and call ``ingest_exemptions()`` from a scheduler.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import delete, select

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.database import AsyncSessionLocal, County, Disease, VaccinationRate

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ArcGIS service config
# ---------------------------------------------------------------------------

FEATURE_SERVER = (
    "https://services1.arcgis.com/CY1LXxl9zlJeBuRZ/arcgis/rest/services"
    "/UpdateThisMapNew/FeatureServer"
)

# Layer IDs 0-66 correspond to Florida counties (67-74 are regions / state).
COUNTY_LAYER_IDS = list(range(67))

FACILITY_TYPE = "school_religious_exemption"
SOURCE = "FL DOH ArcGIS – Religious Exemptions (Florida SHOTS registry)"

REQUEST_TIMEOUT = 30.0
CONCURRENCY = 8  # parallel layer fetches


# ---------------------------------------------------------------------------
# Layer-name → County name normalisation
# ---------------------------------------------------------------------------

def _layer_name_to_county(layer_name: str) -> str:
    """Convert ArcGIS layer name to the county name stored in the DB."""
    # Handle known special cases first
    _OVERRIDES: dict[str, str] = {
        "Indian_River": "Indian River",
        "Miami_Dade":   "Miami-Dade",
        "Palm_Beach":   "Palm Beach",
        "Santa_Rosa":   "Santa Rosa",
        "St_Johns":     "St. Johns",
        "St_Lucie":     "St. Lucie",
    }
    if layer_name in _OVERRIDES:
        return _OVERRIDES[layer_name]
    # Generic: replace underscores with spaces
    return layer_name.replace("_", " ")


# ---------------------------------------------------------------------------
# ArcGIS REST helpers
# ---------------------------------------------------------------------------

async def _fetch_layer_features(
    client: httpx.AsyncClient,
    layer_id: int,
    semaphore: asyncio.Semaphore,
) -> tuple[int, list[dict]]:
    """
    Fetch all census-tract features for one county layer.
    Returns (layer_id, list of attribute dicts).
    """
    url = f"{FEATURE_SERVER}/{layer_id}/query"
    params = {
        "where": "1=1",
        "outFields": "TotalPop4_18,Exempt",
        "returnGeometry": "false",
        "f": "json",
    }
    async with semaphore:
        try:
            resp = await client.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            return layer_id, [f["attributes"] for f in features]
        except Exception as exc:
            log.warning("Layer %d fetch failed: %s", layer_id, exc)
            return layer_id, []


def _aggregate_to_county(features: list[dict]) -> tuple[float, float] | None:
    """
    Aggregate census tract features to a single county-level exemption rate.
    Returns (vaccinated_pct, exempt_religious_pct) or None if no usable data.
    """
    total_pop = 0
    total_exempt = 0
    for feat in features:
        pop = feat.get("TotalPop4_18")
        exempt_raw = feat.get("Exempt")
        # Skip suppressed/invalid population cells
        if not isinstance(pop, (int, float)) or pop <= 0:
            continue
        # Exempt comes as a string from ArcGIS (e.g. "53", "<5", None)
        if exempt_raw is None:
            exempt = 0
        else:
            try:
                exempt = float(str(exempt_raw).replace(",", ""))
            except ValueError:
                # Suppressed value like "<5" — treat as 0 (conservative)
                exempt = 0
        total_pop += pop
        total_exempt += exempt

    if total_pop == 0:
        return None

    exempt_pct = round((total_exempt / total_pop) * 100, 2)
    vaccinated_pct = round(max(0.0, 100.0 - exempt_pct), 2)
    return vaccinated_pct, exempt_pct


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------

async def ingest_exemptions() -> int:
    """
    Fetch religious exemption data for all 67 FL counties and write to
    vaccination_rates.  Returns count of rows inserted.
    """
    survey_year = datetime.now(timezone.utc).year

    # Load county name → FIPS mapping from DB
    async with AsyncSessionLocal() as session:
        county_result = await session.execute(select(County.name, County.fips_code))
        name_to_fips: dict[str, str] = {row.name: row.fips_code for row in county_result.all()}

        disease_result = await session.execute(select(Disease.id))
        disease_ids: list[int] = [row.id for row in disease_result.all()]

    log.info(
        "Starting exemption ingest: %d counties, %d diseases, year=%d",
        len(name_to_fips), len(disease_ids), survey_year,
    )

    # Fetch all county layers concurrently
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async with httpx.AsyncClient(
        headers={"User-Agent": "FL-Outbreak-Tracker/2.0 (public health research)"},
        follow_redirects=True,
    ) as client:
        tasks = [
            _fetch_layer_features(client, layer_id, semaphore)
            for layer_id in COUNTY_LAYER_IDS
        ]
        results = await asyncio.gather(*tasks)

    # Build (layer_id, features) mapping and fetch layer names
    # We need the layer names — fetch service metadata
    async with httpx.AsyncClient(follow_redirects=True) as client:
        meta_resp = await client.get(
            FEATURE_SERVER,
            params={"f": "json"},
            timeout=REQUEST_TIMEOUT,
        )
        meta = meta_resp.json()

    layer_id_to_name: dict[int, str] = {
        lyr["id"]: lyr["name"]
        for lyr in meta.get("layers", [])
        if lyr["id"] < 67
    }

    # Aggregate and prepare rows
    rows_to_insert: list[VaccinationRate] = []
    skipped = 0

    for layer_id, features in results:
        layer_name = layer_id_to_name.get(layer_id, "")
        county_name = _layer_name_to_county(layer_name)
        fips = name_to_fips.get(county_name)

        if not fips:
            log.warning("No FIPS match for layer %d (%r → %r)", layer_id, layer_name, county_name)
            skipped += 1
            continue

        agg = _aggregate_to_county(features)
        if agg is None:
            log.warning("No usable data for %s (layer %d)", county_name, layer_id)
            skipped += 1
            continue

        vaccinated_pct, exempt_pct = agg
        log.debug("%s: vacc=%.1f%%, exempt=%.2f%%", county_name, vaccinated_pct, exempt_pct)

        for disease_id in disease_ids:
            rows_to_insert.append(
                VaccinationRate(
                    survey_year=survey_year,
                    county_fips=fips,
                    disease_id=disease_id,
                    facility_type=FACILITY_TYPE,
                    vaccinated_pct=vaccinated_pct,
                    exempt_medical_pct=None,
                    exempt_religious_pct=exempt_pct,
                    source=SOURCE,
                )
            )

    log.info(
        "Aggregation complete: %d county records, %d rows to insert (%d skipped)",
        len(rows_to_insert) // max(len(disease_ids), 1),
        len(rows_to_insert),
        skipped,
    )

    # Upsert: delete existing rows for this year + facility_type, then insert
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(VaccinationRate).where(
                VaccinationRate.survey_year == survey_year,
                VaccinationRate.facility_type == FACILITY_TYPE,
            )
        )
        session.add_all(rows_to_insert)
        await session.commit()

    log.info("Inserted %d vaccination_rate rows (year=%d).", len(rows_to_insert), survey_year)
    return len(rows_to_insert)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ingest_exemptions())
