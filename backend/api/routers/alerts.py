from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import OutbreakAlert, get_db
from backend.services.alert_engine import generate_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: int
    county_fips: str
    disease_id: int
    alert_date: date
    severity: str
    metric: str
    threshold_value: float | None
    observed_value: float | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateResult(BaseModel):
    new_alerts: int


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    county_fips: str | None = Query(None),
    disease_id: int | None = Query(None),
    severity: str | None = Query(None, description="watch | warning | emergency"),
    active_only: bool = Query(True, description="Only return unresolved alerts"),
    db: AsyncSession = Depends(get_db),
) -> list[AlertOut]:
    """Return outbreak alerts, newest first."""
    q = select(OutbreakAlert).order_by(OutbreakAlert.created_at.desc())

    if county_fips:
        q = q.where(OutbreakAlert.county_fips == county_fips)
    if disease_id is not None:
        q = q.where(OutbreakAlert.disease_id == disease_id)
    if severity:
        q = q.where(OutbreakAlert.severity == severity)
    if active_only:
        q = q.where(OutbreakAlert.resolved_at.is_(None))

    result = await db.execute(q)
    return result.scalars().all()


@router.post("/generate", response_model=GenerateResult)
async def run_generate_alerts(db: AsyncSession = Depends(get_db)) -> GenerateResult:
    """
    Scan current case and vaccination data and create new OutbreakAlert rows
    where thresholds are breached. Idempotent — skips combos that already
    have an unresolved alert.
    """
    new_count = await generate_alerts(db)
    return GenerateResult(new_alerts=new_count)
