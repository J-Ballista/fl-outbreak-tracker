from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.database import County, get_db

router = APIRouter(prefix="/counties", tags=["counties"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class CountyOut(BaseModel):
    fips_code: str
    name: str
    population: int | None
    centroid_lat: float | None
    centroid_lng: float | None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[CountyOut])
async def list_counties(db: AsyncSession = Depends(get_db)) -> list[CountyOut]:
    """Return all 67 Florida counties."""
    result = await db.execute(select(County).order_by(County.name))
    return result.scalars().all()


@router.get("/{fips_code}", response_model=CountyOut)
async def get_county(fips_code: str, db: AsyncSession = Depends(get_db)) -> CountyOut:
    """Return a single county by FIPS code."""
    county = await db.get(County, fips_code)
    if county is None:
        raise HTTPException(status_code=404, detail=f"County {fips_code!r} not found")
    return county
