from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import DiseaseCase, get_db

router = APIRouter(prefix="/cases", tags=["cases"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CaseOut(BaseModel):
    id: int
    report_date: date
    county_fips: str
    disease_id: int
    case_count: int
    confirmed_count: int | None
    probable_count: int | None
    age_group: str | None
    acquisition: str | None
    source: str | None

    model_config = {"from_attributes": True}


class CaseSummary(BaseModel):
    """Aggregated case totals per county for choropleth rendering."""
    county_fips: str
    total_cases: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CaseOut])
async def list_cases(
    county_fips: str | None = Query(None, description="Filter by county FIPS code"),
    disease_id: int | None = Query(None, description="Filter by disease ID"),
    date_from: date | None = Query(None, description="Earliest report_date (inclusive)"),
    date_to: date | None = Query(None, description="Latest report_date (inclusive)"),
    limit: int = Query(1000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[CaseOut]:
    """
    Return individual case records with optional filters.
    Supports county, disease, and date-range filtering.
    """
    q = select(DiseaseCase)

    if county_fips:
        q = q.where(DiseaseCase.county_fips == county_fips)
    if disease_id is not None:
        q = q.where(DiseaseCase.disease_id == disease_id)
    if date_from:
        q = q.where(DiseaseCase.report_date >= date_from)
    if date_to:
        q = q.where(DiseaseCase.report_date <= date_to)

    q = q.order_by(DiseaseCase.report_date.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/summary", response_model=list[CaseSummary])
async def cases_summary(
    disease_id: int | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[CaseSummary]:
    """
    Return total case counts grouped by county — used to drive the choropleth
    colour scale on the frontend map.
    """
    q = (
        select(
            DiseaseCase.county_fips,
            func.sum(DiseaseCase.case_count).label("total_cases"),
        )
        .group_by(DiseaseCase.county_fips)
    )

    if disease_id is not None:
        q = q.where(DiseaseCase.disease_id == disease_id)
    if date_from:
        q = q.where(DiseaseCase.report_date >= date_from)
    if date_to:
        q = q.where(DiseaseCase.report_date <= date_to)

    result = await db.execute(q)
    return [
        CaseSummary(county_fips=row.county_fips, total_cases=int(row.total_cases))
        for row in result.all()
    ]
