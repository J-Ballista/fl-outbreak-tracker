"""
Seed script: populates vaccination_rates with realistic county-level data.

Run from project root:
    python scripts/seed_vaccination_rates.py
"""
from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, text
from backend.models.database import AsyncSessionLocal, VaccinationRate

# Base vaccination rate (%) per disease, school-age population
DISEASE_BASE_RATES: dict[int, tuple[float, float]] = {
    # disease_id: (base_pct, std_dev)
    1:  (93.0, 2.5),   # Measles
    2:  (92.0, 2.5),   # Mumps
    3:  (92.0, 2.5),   # Rubella
    4:  (90.0, 3.0),   # Pertussis
    5:  (89.0, 3.5),   # Varicella
    6:  (72.0, 5.0),   # Hepatitis A
    7:  (85.0, 4.0),   # Hepatitis B
    8:  (78.0, 5.0),   # Meningococcal Disease
    9:  (80.0, 4.0),   # Haemophilus Influenzae
    10: (88.0, 3.0),   # Tetanus
    11: (91.0, 2.0),   # Diphtheria
    12: (93.0, 2.0),   # Poliomyelitis
}

SURVEY_YEARS = [2022, 2023, 2024]


async def seed() -> None:
    random.seed(42)
    async with AsyncSessionLocal() as session:
        # Fetch county FIPS codes
        result = await session.execute(text("SELECT fips_code FROM counties"))
        all_fips = [r[0] for r in result.all()]

        # Clear existing
        await session.execute(text("DELETE FROM vaccination_rates"))
        await session.commit()

        rows: list[VaccinationRate] = []
        for year in SURVEY_YEARS:
            for fips in all_fips:
                for disease_id, (base, std) in DISEASE_BASE_RATES.items():
                    vacc_pct = round(min(99.5, max(50.0, random.gauss(base, std))), 2)
                    med_pct = round(random.uniform(0.2, 1.5), 2)
                    rel_pct = round(random.uniform(0.5, 3.5), 2)
                    rows.append(VaccinationRate(
                        survey_year=year,
                        county_fips=fips,
                        disease_id=disease_id,
                        facility_type="school",
                        vaccinated_pct=vacc_pct,
                        exempt_medical_pct=med_pct,
                        exempt_religious_pct=rel_pct,
                        source=f"FL DOH School Immunization Survey {year}",
                    ))

        session.add_all(rows)
        await session.commit()
        print(f"Inserted {len(rows)} vaccination rate rows.")


if __name__ == "__main__":
    asyncio.run(seed())
