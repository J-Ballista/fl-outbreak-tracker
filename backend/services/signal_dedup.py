"""
Article signal deduplication service
======================================
Groups ArticleSignal rows by (disease_id, county_fips, 14-day date bucket)
and marks lower-confidence signals in each group as is_duplicate=True.

The highest-confidence signal in each cluster is kept as primary; all others
are marked duplicate. Signals with no disease_id or no published_at are
compared within a fallback group and deduped together if they share the same
disease/county with no temporal anchor.

Call ``dedup_signals()`` after each news ingest run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from backend.models.database import ArticleSignal, NewsArticle

log = logging.getLogger(__name__)

# Window size in days — signals from articles published within this window
# and sharing the same disease + county are considered about the same event.
DEDUP_WINDOW_DAYS = 14


def _date_bucket(dt: datetime | None) -> int:
    """Map a datetime to a 14-day epoch bucket index (0, 1, 2, …)."""
    if dt is None:
        return -1  # unknown date — own bucket per disease/county combo
    epoch = datetime(2020, 1, 1, tzinfo=timezone.utc)
    delta_days = (dt.replace(tzinfo=timezone.utc) - epoch).days
    return delta_days // DEDUP_WINDOW_DAYS


async def dedup_signals(session: AsyncSession) -> int:
    """
    Mark duplicate article signals in-place.

    Returns the number of signals newly marked as duplicates.
    """
    # Load all non-duplicate signals with their article's published_at
    result = await session.execute(
        select(ArticleSignal)
        .options(selectinload(ArticleSignal.article))
        .where(ArticleSignal.is_duplicate.is_(False))
        .order_by(ArticleSignal.created_at)
    )
    signals: list[ArticleSignal] = list(result.scalars().all())

    # Group by (disease_id, county_fips, date_bucket)
    groups: dict[tuple, list[ArticleSignal]] = {}
    for sig in signals:
        pub = sig.article.published_at if sig.article else None
        bucket = _date_bucket(pub)
        key = (sig.disease_id, sig.county_fips, bucket)
        groups.setdefault(key, []).append(sig)

    newly_marked = 0
    ids_to_mark: list[int] = []

    for key, group in groups.items():
        if len(group) <= 1:
            continue  # nothing to dedup

        # Sort descending by confidence; None confidence → 0.0
        group.sort(key=lambda s: s.confidence or 0.0, reverse=True)

        # Keep group[0] as primary; mark the rest
        for dup in group[1:]:
            ids_to_mark.append(dup.id)
            newly_marked += 1

    if ids_to_mark:
        await session.execute(
            update(ArticleSignal)
            .where(ArticleSignal.id.in_(ids_to_mark))
            .values(is_duplicate=True)
        )
        await session.commit()
        log.info("Dedup complete — %d signals marked as duplicate.", newly_marked)
    else:
        log.info("Dedup complete — no new duplicates found.")

    return newly_marked
