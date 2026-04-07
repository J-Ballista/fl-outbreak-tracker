"""
Seed script: inserts sample OutbreakAlerts covering all three severities.

Run from project root:
    python scripts/seed_alerts.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.models.database import AsyncSessionLocal, OutbreakAlert

ALERTS = [
    # (county_fips, disease_id, alert_date, severity, metric, threshold, observed)
    # Emergencies
    ("12086", 1,  "2025-03-01", "emergency", "case_spike",          1.5,   8.0),   # Miami-Dade Measles
    ("12011", 4,  "2025-02-15", "emergency", "case_spike",          4.2,  18.0),   # Broward Pertussis
    # Warnings
    ("12095", 5,  "2025-03-10", "warning",   "case_spike",          5.0,  12.0),   # Orange Varicella
    ("12057", 6,  "2025-02-20", "warning",   "case_spike",          2.1,   6.0),   # Hillsborough Hep A
    ("12031", 2,  "2025-01-28", "warning",   "case_spike",          1.8,   5.0),   # Duval Mumps
    ("12099", 8,  "2025-03-05", "warning",   "case_spike",          0.9,   2.0),   # Palm Beach Meningococcal
    # Watches (below herd threshold)
    ("12133", 1,  "2025-03-14", "watch",     "below_herd_threshold", 95.0, 88.4),  # Washington Measles
    ("12077", 4,  "2025-03-14", "watch",     "below_herd_threshold", 92.0, 85.1),  # Liberty Pertussis
    ("12013", 12, "2025-03-14", "watch",     "below_herd_threshold", 80.0, 74.3),  # Calhoun Polio
    ("12047", 1,  "2025-03-14", "watch",     "below_herd_threshold", 95.0, 91.2),  # Hamilton Measles
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM outbreak_alerts"))
        await session.commit()

        rows = [
            OutbreakAlert(
                county_fips=fips,
                disease_id=disease_id,
                alert_date=date.fromisoformat(alert_date),
                severity=severity,
                metric=metric,
                threshold_value=threshold,
                observed_value=observed,
            )
            for fips, disease_id, alert_date, severity, metric, threshold, observed
            in ALERTS
        ]
        session.add_all(rows)
        await session.commit()
        print(f"Inserted {len(rows)} alerts ({sum(1 for a in ALERTS if a[3]=='emergency')} emergency, "
              f"{sum(1 for a in ALERTS if a[3]=='warning')} warning, "
              f"{sum(1 for a in ALERTS if a[3]=='watch')} watch).")


if __name__ == "__main__":
    asyncio.run(seed())
