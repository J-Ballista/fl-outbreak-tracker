from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import VaccinationRate, get_db

router = APIRouter(prefix="/vaccination-rates", tags=["vaccination-rates"])


class VaccinationSummary(BaseModel):
    county_fips: str
    vaccinated_pct: float
    exempt_medical_pct: float | None
    exempt_religious_pct: float | None
    survey_year: int

    model_config = {"from_attributes": True}


class CountyDiseaseVaccRate(BaseModel):
    disease_id: int
    vaccinated_pct: float
    survey_year: int

    model_config = {"from_attributes": True}


class VaccTrendPoint(BaseModel):
    survey_year: int
    vaccinated_pct: float


@router.get("/summary", response_model=list[VaccinationSummary])
async def vaccination_summary(
    disease_id: int | None = Query(None, description="Filter by disease ID"),
    survey_year: int | None = Query(None, description="Survey year (defaults to most recent)"),
    db: AsyncSession = Depends(get_db),
) -> list[VaccinationSummary]:
    """
    Return average vaccination rate per county.
    When disease_id is omitted, averages across all diseases.
    When survey_year is omitted, uses the most recent year available.
    """
    if survey_year is None:
        year_q = select(func.max(VaccinationRate.survey_year))
        if disease_id is not None:
            year_q = year_q.where(VaccinationRate.disease_id == disease_id)
        year_result = await db.execute(year_q)
        survey_year = year_result.scalar_one_or_none()
        if survey_year is None:
            return []

    q = (
        select(
            VaccinationRate.county_fips,
            func.avg(VaccinationRate.vaccinated_pct).label("vaccinated_pct"),
            func.avg(VaccinationRate.exempt_medical_pct).label("exempt_medical_pct"),
            func.avg(VaccinationRate.exempt_religious_pct).label("exempt_religious_pct"),
        )
        .where(VaccinationRate.survey_year == survey_year)
        .group_by(VaccinationRate.county_fips)
    )

    if disease_id is not None:
        q = q.where(VaccinationRate.disease_id == disease_id)

    result = await db.execute(q)
    return [
        VaccinationSummary(
            county_fips=row.county_fips,
            vaccinated_pct=round(float(row.vaccinated_pct), 2),
            exempt_medical_pct=round(float(row.exempt_medical_pct), 2) if row.exempt_medical_pct else None,
            exempt_religious_pct=round(float(row.exempt_religious_pct), 2) if row.exempt_religious_pct else None,
            survey_year=survey_year,
        )
        for row in result.all()
    ]


@router.get("/county/{fips_code}/trend", response_model=list[VaccTrendPoint])
async def county_vacc_trend(
    fips_code: str,
    disease_id: int | None = Query(None, description="Filter by disease ID"),
    db: AsyncSession = Depends(get_db),
) -> list[VaccTrendPoint]:
    """
    Return year-over-year religious exemption rate for a county (real FL SHOTS
    data only — facility_type='school_religious_exemption').  Averaged across
    all diseases unless disease_id is specified.

    Synthetic seed rows (facility_type='school') are intentionally excluded
    because they represent vaccination rates rather than exemption rates and
    would create a spurious drop on the exemption trend line.
    """
    q = (
        select(
            VaccinationRate.survey_year,
            func.avg(VaccinationRate.vaccinated_pct).label("vaccinated_pct"),
        )
        .where(
            VaccinationRate.county_fips == fips_code,
            VaccinationRate.facility_type == "school_religious_exemption",
        )
        .group_by(VaccinationRate.survey_year)
        .order_by(VaccinationRate.survey_year)
    )
    if disease_id is not None:
        q = q.where(VaccinationRate.disease_id == disease_id)

    result = await db.execute(q)
    return [
        VaccTrendPoint(
            survey_year=row.survey_year,
            vaccinated_pct=round(float(row.vaccinated_pct), 2),
        )
        for row in result.all()
    ]


@router.get("/county/{fips_code}", response_model=list[CountyDiseaseVaccRate])
async def county_vaccination_by_disease(
    fips_code: str,
    survey_year: int | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[CountyDiseaseVaccRate]:
    """Return per-disease vaccination rates for a single county."""
    if survey_year is None:
        year_result = await db.execute(
            select(func.max(VaccinationRate.survey_year)).where(
                VaccinationRate.county_fips == fips_code
            )
        )
        survey_year = year_result.scalar_one_or_none()
        if survey_year is None:
            return []

    q = (
        select(
            VaccinationRate.disease_id,
            func.avg(VaccinationRate.vaccinated_pct).label("vaccinated_pct"),
        )
        .where(
            VaccinationRate.county_fips == fips_code,
            VaccinationRate.survey_year == survey_year,
        )
        .group_by(VaccinationRate.disease_id)
        .order_by(VaccinationRate.disease_id)
    )

    result = await db.execute(q)
    return [
        CountyDiseaseVaccRate(
            disease_id=row.disease_id,
            vaccinated_pct=round(float(row.vaccinated_pct), 2),
            survey_year=survey_year,
        )
        for row in result.all()
    ]
