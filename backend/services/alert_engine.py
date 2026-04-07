"""
Alert engine
============
Scans disease_cases and vaccination_rates to generate OutbreakAlert rows.

Two alert types:
  - case_spike   : county/disease case count in recent window is ≥ 2× the
                   trailing 12-month monthly average  (warning) or ≥ 4× (emergency)
  - below_herd   : county vaccination rate is below the disease herd threshold (watch)

Call generate_alerts() from the /alerts/generate endpoint or the cron runner.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import (
    Disease,
    DiseaseCase,
    OutbreakAlert,
    VaccinationRate,
)

# Thresholds for case-spike severity
SPIKE_WARNING_RATIO = 2.0
SPIKE_EMERGENCY_RATIO = 4.0

# How many days back to treat as "recent" for spike detection
SPIKE_WINDOW_DAYS = 30


async def generate_alerts(session: AsyncSession) -> int:
    """
    Scan current data and upsert OutbreakAlert rows.
    Returns the number of new alerts created.
    """
    created = 0
    today = date.today()

    # ── Load reference data ──────────────────────────────────────────────
    diseases_result = await session.execute(select(Disease))
    diseases = {d.id: d for d in diseases_result.scalars().all()}

    # ── 1. Case-spike alerts ─────────────────────────────────────────────
    window_start = today - timedelta(days=SPIKE_WINDOW_DAYS)
    year_start = today - timedelta(days=365)

    # Recent totals per county/disease
    recent_q = (
        select(
            DiseaseCase.county_fips,
            DiseaseCase.disease_id,
            func.sum(DiseaseCase.case_count).label("recent_total"),
        )
        .where(DiseaseCase.report_date >= window_start)
        .group_by(DiseaseCase.county_fips, DiseaseCase.disease_id)
    )
    recent_result = await session.execute(recent_q)
    recent_map: dict[tuple, int] = {
        (r.county_fips, r.disease_id): int(r.recent_total)
        for r in recent_result.all()
    }

    # Trailing 12-month totals (excluding the recent window)
    baseline_q = (
        select(
            DiseaseCase.county_fips,
            DiseaseCase.disease_id,
            func.sum(DiseaseCase.case_count).label("year_total"),
        )
        .where(
            DiseaseCase.report_date >= year_start,
            DiseaseCase.report_date < window_start,
        )
        .group_by(DiseaseCase.county_fips, DiseaseCase.disease_id)
    )
    baseline_result = await session.execute(baseline_q)
    # Monthly average = year_total / 11 months (365 - 30 days ≈ 11 months)
    baseline_map: dict[tuple, float] = {
        (r.county_fips, r.disease_id): float(r.year_total) / 11.0
        for r in baseline_result.all()
        if float(r.year_total) > 0
    }

    for (fips, disease_id), recent_count in recent_map.items():
        monthly_avg = baseline_map.get((fips, disease_id), 0.0)
        if monthly_avg == 0:
            continue
        ratio = recent_count / monthly_avg
        if ratio < SPIKE_WARNING_RATIO:
            continue

        severity = "emergency" if ratio >= SPIKE_EMERGENCY_RATIO else "warning"

        # Skip if an unresolved alert already exists for this combo
        existing = await session.execute(
            select(OutbreakAlert).where(
                OutbreakAlert.county_fips == fips,
                OutbreakAlert.disease_id == disease_id,
                OutbreakAlert.metric == "case_spike",
                OutbreakAlert.resolved_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            continue

        session.add(
            OutbreakAlert(
                county_fips=fips,
                disease_id=disease_id,
                alert_date=today,
                severity=severity,
                metric="case_spike",
                threshold_value=round(monthly_avg * SPIKE_WARNING_RATIO, 4),
                observed_value=float(recent_count),
            )
        )
        created += 1

    # ── 2. Below-herd-threshold alerts ───────────────────────────────────
    # Use most recent survey year per county/disease
    vacc_q = (
        select(VaccinationRate)
        .where(
            VaccinationRate.survey_year == (
                select(func.max(VaccinationRate.survey_year))
                .where(
                    VaccinationRate.county_fips == VaccinationRate.county_fips
                )
                .correlate(VaccinationRate)
                .scalar_subquery()
            )
        )
    )
    # Simpler: just grab max year globally and filter
    max_year_result = await session.execute(
        select(func.max(VaccinationRate.survey_year))
    )
    max_year = max_year_result.scalar_one_or_none()

    if max_year:
        vacc_result = await session.execute(
            select(
                VaccinationRate.county_fips,
                VaccinationRate.disease_id,
                func.avg(VaccinationRate.vaccinated_pct).label("avg_pct"),
            )
            .where(VaccinationRate.survey_year == max_year)
            .group_by(VaccinationRate.county_fips, VaccinationRate.disease_id)
        )
        for row in vacc_result.all():
            disease = diseases.get(row.disease_id)
            if not disease or disease.herd_threshold_pct is None:
                continue
            threshold = float(disease.herd_threshold_pct)
            avg_pct = float(row.avg_pct)
            if avg_pct >= threshold:
                continue

            existing = await session.execute(
                select(OutbreakAlert).where(
                    OutbreakAlert.county_fips == row.county_fips,
                    OutbreakAlert.disease_id == row.disease_id,
                    OutbreakAlert.metric == "below_herd_threshold",
                    OutbreakAlert.resolved_at.is_(None),
                )
            )
            if existing.scalar_one_or_none():
                continue

            session.add(
                OutbreakAlert(
                    county_fips=row.county_fips,
                    disease_id=row.disease_id,
                    alert_date=today,
                    severity="watch",
                    metric="below_herd_threshold",
                    threshold_value=threshold,
                    observed_value=round(avg_pct, 4),
                )
            )
            created += 1

    await session.commit()
    return created
