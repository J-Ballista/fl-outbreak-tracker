from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models.database import ArticleSignal, NewsArticle, get_db
from backend.services.signal_dedup import dedup_signals

router = APIRouter(prefix="/news", tags=["news"])


class NewsSignalOut(BaseModel):
    id: int
    county_fips: str | None
    disease_id: int | None
    extracted_case_count: int | None
    confidence: float | None
    article_id: int
    article_title: str | None
    article_url: str
    article_source: str | None
    article_published_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/signals", response_model=list[NewsSignalOut])
async def list_signals(
    county_fips: str | None = Query(None, description="Filter by county FIPS code"),
    disease_id: int | None = Query(None, description="Filter by disease ID"),
    include_duplicates: bool = Query(False, description="Include duplicate signals"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> list[NewsSignalOut]:
    """
    Return NLP-extracted disease signals from news articles, joined with
    article metadata (URL, title, source, published date).

    Duplicate signals (same disease/county/~2-week window, lower confidence)
    are hidden by default. Pass include_duplicates=true to see all.
    """
    q = (
        select(ArticleSignal)
        .options(selectinload(ArticleSignal.article))
        .order_by(ArticleSignal.created_at.desc())
        .limit(limit)
    )

    if county_fips:
        q = q.where(ArticleSignal.county_fips == county_fips)
    if disease_id is not None:
        q = q.where(ArticleSignal.disease_id == disease_id)
    if not include_duplicates:
        q = q.where(ArticleSignal.is_duplicate.is_(False))

    result = await db.execute(q)
    signals = result.scalars().all()

    return [
        NewsSignalOut(
            id=s.id,
            county_fips=s.county_fips,
            disease_id=s.disease_id,
            extracted_case_count=s.extracted_case_count,
            confidence=s.confidence,
            article_id=s.article_id,
            article_title=s.article.title,
            article_url=s.article.url,
            article_source=s.article.source,
            article_published_at=s.article.published_at,
        )
        for s in signals
    ]
