from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import Disease, get_db

router = APIRouter(prefix="/diseases", tags=["diseases"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DiseaseOut(BaseModel):
    id: int
    name: str
    category: str | None
    icd10_code: str | None
    herd_threshold_pct: float | None
    r0_estimate: float | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[DiseaseOut])
async def list_diseases(db: AsyncSession = Depends(get_db)) -> list[DiseaseOut]:
    """Return all tracked diseases."""
    result = await db.execute(select(Disease).order_by(Disease.name))
    return result.scalars().all()


@router.get("/{disease_id}", response_model=DiseaseOut)
async def get_disease(disease_id: int, db: AsyncSession = Depends(get_db)) -> DiseaseOut:
    """Return a single disease by ID."""
    disease = await db.get(Disease, disease_id)
    if disease is None:
        raise HTTPException(status_code=404, detail=f"Disease {disease_id} not found")
    return disease
