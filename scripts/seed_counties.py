"""
Seed script: populates the counties table with all 67 Florida counties.

Run from the project root:
    python scripts/seed_counties.py

Requires a running Postgres instance (see docker-compose.yml).
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.models.database import AsyncSessionLocal, County

# ---------------------------------------------------------------------------
# All 67 Florida counties with FIPS codes, 2020 Census populations,
# and geographic centroids (lat/lng, WGS-84).
# ---------------------------------------------------------------------------
FLORIDA_COUNTIES: list[dict] = [
    {"fips_code": "12001", "name": "Alachua",      "population": 278468,  "centroid_lat": 29.6747, "centroid_lng": -82.3564},
    {"fips_code": "12003", "name": "Baker",         "population": 29219,   "centroid_lat": 30.3294, "centroid_lng": -82.2985},
    {"fips_code": "12005", "name": "Bay",            "population": 174705,  "centroid_lat": 30.2380, "centroid_lng": -85.6529},
    {"fips_code": "12007", "name": "Bradford",       "population": 28201,   "centroid_lat": 29.9449, "centroid_lng": -82.1707},
    {"fips_code": "12009", "name": "Brevard",        "population": 606612,  "centroid_lat": 28.2638, "centroid_lng": -80.7214},
    {"fips_code": "12011", "name": "Broward",        "population": 1944375, "centroid_lat": 26.1522, "centroid_lng": -80.3455},
    {"fips_code": "12013", "name": "Calhoun",        "population": 13909,   "centroid_lat": 30.4079, "centroid_lng": -85.1920},
    {"fips_code": "12015", "name": "Charlotte",      "population": 188910,  "centroid_lat": 26.9706, "centroid_lng": -81.9561},
    {"fips_code": "12017", "name": "Citrus",         "population": 153843,  "centroid_lat": 28.8414, "centroid_lng": -82.5212},
    {"fips_code": "12019", "name": "Clay",           "population": 219252,  "centroid_lat": 29.9831, "centroid_lng": -81.8682},
    {"fips_code": "12021", "name": "Collier",        "population": 375752,  "centroid_lat": 26.1126, "centroid_lng": -81.3959},
    {"fips_code": "12023", "name": "Columbia",       "population": 71686,   "centroid_lat": 30.2236, "centroid_lng": -82.6181},
    {"fips_code": "12027", "name": "DeSoto",         "population": 37352,   "centroid_lat": 27.1879, "centroid_lng": -81.8253},
    {"fips_code": "12029", "name": "Dixie",          "population": 16422,   "centroid_lat": 29.5827, "centroid_lng": -83.1765},
    {"fips_code": "12031", "name": "Duval",          "population": 995567,  "centroid_lat": 30.3322, "centroid_lng": -81.6557},
    {"fips_code": "12033", "name": "Escambia",       "population": 319684,  "centroid_lat": 30.6228, "centroid_lng": -87.3413},
    {"fips_code": "12035", "name": "Flagler",        "population": 115081,  "centroid_lat": 29.4727, "centroid_lng": -81.3053},
    {"fips_code": "12037", "name": "Franklin",       "population": 11913,   "centroid_lat": 29.8218, "centroid_lng": -84.8012},
    {"fips_code": "12039", "name": "Gadsden",        "population": 44272,   "centroid_lat": 30.5755, "centroid_lng": -84.6059},
    {"fips_code": "12041", "name": "Gilchrist",      "population": 17615,   "centroid_lat": 29.7251, "centroid_lng": -82.8003},
    {"fips_code": "12043", "name": "Glades",         "population": 12595,   "centroid_lat": 26.9924, "centroid_lng": -81.2058},
    {"fips_code": "12045", "name": "Gulf",           "population": 13089,   "centroid_lat": 29.9253, "centroid_lng": -85.2102},
    {"fips_code": "12047", "name": "Hamilton",       "population": 14428,   "centroid_lat": 30.4962, "centroid_lng": -82.9490},
    {"fips_code": "12049", "name": "Hardee",         "population": 26714,   "centroid_lat": 27.4942, "centroid_lng": -81.8140},
    {"fips_code": "12051", "name": "Hendry",         "population": 42444,   "centroid_lat": 26.4970, "centroid_lng": -81.2720},
    {"fips_code": "12053", "name": "Hernando",       "population": 193920,  "centroid_lat": 28.5630, "centroid_lng": -82.4657},
    {"fips_code": "12055", "name": "Highlands",      "population": 102101,  "centroid_lat": 27.3425, "centroid_lng": -81.3403},
    {"fips_code": "12057", "name": "Hillsborough",   "population": 1459762, "centroid_lat": 27.9058, "centroid_lng": -82.3495},
    {"fips_code": "12059", "name": "Holmes",         "population": 19819,   "centroid_lat": 30.8685, "centroid_lng": -85.8134},
    {"fips_code": "12061", "name": "Indian River",   "population": 159923,  "centroid_lat": 27.6963, "centroid_lng": -80.5992},
    {"fips_code": "12063", "name": "Jackson",        "population": 47833,   "centroid_lat": 30.7869, "centroid_lng": -85.2179},
    {"fips_code": "12065", "name": "Jefferson",      "population": 14246,   "centroid_lat": 30.4233, "centroid_lng": -83.8874},
    {"fips_code": "12067", "name": "Lafayette",      "population": 8422,    "centroid_lat": 29.9940, "centroid_lng": -83.2006},
    {"fips_code": "12069", "name": "Lake",           "population": 367118,  "centroid_lat": 28.7570, "centroid_lng": -81.7126},
    {"fips_code": "12071", "name": "Lee",            "population": 760822,  "centroid_lat": 26.5620, "centroid_lng": -81.7513},
    {"fips_code": "12073", "name": "Leon",           "population": 293447,  "centroid_lat": 30.4601, "centroid_lng": -84.2808},
    {"fips_code": "12075", "name": "Levy",           "population": 41503,   "centroid_lat": 29.3169, "centroid_lng": -82.7837},
    {"fips_code": "12077", "name": "Liberty",        "population": 8354,    "centroid_lat": 30.2344, "centroid_lng": -84.8882},
    {"fips_code": "12079", "name": "Madison",        "population": 18493,   "centroid_lat": 30.4430, "centroid_lng": -83.4614},
    {"fips_code": "12081", "name": "Manatee",        "population": 403253,  "centroid_lat": 27.4798, "centroid_lng": -82.3452},
    {"fips_code": "12083", "name": "Marion",         "population": 365579,  "centroid_lat": 29.2109, "centroid_lng": -82.0636},
    {"fips_code": "12085", "name": "Martin",         "population": 161000,  "centroid_lat": 27.0846, "centroid_lng": -80.4015},
    {"fips_code": "12086", "name": "Miami-Dade",     "population": 2701767, "centroid_lat": 25.5516, "centroid_lng": -80.6327},
    {"fips_code": "12087", "name": "Monroe",         "population": 74228,   "centroid_lat": 24.6634, "centroid_lng": -81.3803},
    {"fips_code": "12089", "name": "Nassau",         "population": 88625,   "centroid_lat": 30.6128, "centroid_lng": -81.7693},
    {"fips_code": "12091", "name": "Okaloosa",       "population": 217959,  "centroid_lat": 30.5994, "centroid_lng": -86.6601},
    {"fips_code": "12093", "name": "Okeechobee",     "population": 42276,   "centroid_lat": 27.3937, "centroid_lng": -80.8985},
    {"fips_code": "12095", "name": "Orange",         "population": 1429908, "centroid_lat": 28.5383, "centroid_lng": -81.3792},
    {"fips_code": "12097", "name": "Osceola",        "population": 375751,  "centroid_lat": 28.0628, "centroid_lng": -81.1503},
    {"fips_code": "12099", "name": "Palm Beach",     "population": 1496770, "centroid_lat": 26.6467, "centroid_lng": -80.3998},
    {"fips_code": "12101", "name": "Pasco",          "population": 553947,  "centroid_lat": 28.3072, "centroid_lng": -82.4374},
    {"fips_code": "12103", "name": "Pinellas",       "population": 959107,  "centroid_lat": 27.8758, "centroid_lng": -82.7761},
    {"fips_code": "12105", "name": "Polk",           "population": 724777,  "centroid_lat": 27.9351, "centroid_lng": -81.6884},
    {"fips_code": "12107", "name": "Putnam",         "population": 74521,   "centroid_lat": 29.6239, "centroid_lng": -81.7381},
    {"fips_code": "12109", "name": "St. Johns",      "population": 273425,  "centroid_lat": 29.9741, "centroid_lng": -81.4560},
    {"fips_code": "12111", "name": "St. Lucie",      "population": 328297,  "centroid_lat": 27.3793, "centroid_lng": -80.4455},
    {"fips_code": "12113", "name": "Santa Rosa",     "population": 184313,  "centroid_lat": 30.6929, "centroid_lng": -86.9627},
    {"fips_code": "12115", "name": "Sarasota",       "population": 433742,  "centroid_lat": 27.1842, "centroid_lng": -82.3647},
    {"fips_code": "12117", "name": "Seminole",       "population": 471826,  "centroid_lat": 28.7162, "centroid_lng": -81.2095},
    {"fips_code": "12119", "name": "Sumter",         "population": 132420,  "centroid_lat": 28.7069, "centroid_lng": -82.0757},
    {"fips_code": "12121", "name": "Suwannee",       "population": 44417,   "centroid_lat": 30.1944, "centroid_lng": -83.0191},
    {"fips_code": "12123", "name": "Taylor",         "population": 21569,   "centroid_lat": 30.0568, "centroid_lng": -83.6130},
    {"fips_code": "12125", "name": "Union",          "population": 15237,   "centroid_lat": 30.0466, "centroid_lng": -82.3730},
    {"fips_code": "12127", "name": "Volusia",        "population": 553284,  "centroid_lat": 29.0283, "centroid_lng": -81.1680},
    {"fips_code": "12129", "name": "Wakulla",        "population": 33739,   "centroid_lat": 30.1554, "centroid_lng": -84.3680},
    {"fips_code": "12131", "name": "Walton",         "population": 74071,   "centroid_lat": 30.6426, "centroid_lng": -86.1762},
    {"fips_code": "12133", "name": "Washington",     "population": 25473,   "centroid_lat": 30.6091, "centroid_lng": -85.6635},
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        # Upsert: skip rows that already exist
        existing = {
            row[0]
            for row in (
                await session.execute(text("SELECT fips_code FROM counties"))
            ).all()
        }
        new_counties = [
            County(**c) for c in FLORIDA_COUNTIES if c["fips_code"] not in existing
        ]
        if not new_counties:
            print("counties table already seeded — nothing to do.")
            return

        session.add_all(new_counties)
        await session.commit()
        print(f"Inserted {len(new_counties)} counties.")


if __name__ == "__main__":
    asyncio.run(seed())
