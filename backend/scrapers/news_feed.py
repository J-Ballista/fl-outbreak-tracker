"""
RSS news feed scraper + GDELT ingestion
========================================
Ingests articles from Florida local news outlets, stores raw text in
news_articles, then calls the NLP classifier to extract disease/county signals
and writes them to article_signals.

Sources:
  - RSS: Florida Health News (verified working 2026-04)
  - GDELT Doc 2.0 API: free, no auth, searches English articles by keyword

Run standalone:
    python -m backend.scrapers.news_feed

Or import and call ``ingest_all_feeds()`` from a scheduler.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.database import ArticleSignal, AsyncSessionLocal, Disease, NewsArticle
from backend.nlp.classifier import extract_signals, set_disease_id_cache

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feed registry
# ---------------------------------------------------------------------------

class FeedConfig(TypedDict):
    source: str
    url: str


FEEDS: list[FeedConfig] = [
    # Verified working feeds (checked 2026-04)
    {
        "source": "Florida Health News",
        "url": "https://www.floridahealthnews.com/feed/",
    },
    # Dead / broken feeds as of 2026-04:
    #   Orlando Sentinel (403), Miami Herald (timeout), Tampa Bay Times (404),
    #   Sun Sentinel (403), FL DOH News RSS (empty), Jacksonville.com (returns HTML),
    #   Gainesville Sun (returns HTML)
]

# Keywords used to pre-filter articles before running expensive NLP.
# Any article whose title or summary contains at least one keyword is kept.
RELEVANCE_KEYWORDS: tuple[str, ...] = (
    "measles", "mumps", "rubella", "pertussis", "whooping cough",
    "varicella", "chickenpox", "hepatitis", "meningococcal", "meningitis",
    "outbreak", "disease", "vaccine", "vaccination", "immunization",
    "case", "cases", "infection", "virus", "epidemic",
)

# Max body length to store (characters) — avoids storing paywalled pages
MAX_BODY_CHARS = 20_000

# HTTP timeout (seconds)
REQUEST_TIMEOUT = 20.0


# ---------------------------------------------------------------------------
# Feed parsing helpers
# ---------------------------------------------------------------------------

async def _parse_feed(raw_url: str) -> list[feedparser.FeedParserDict]:
    """Fetch and parse an RSS feed. Returns a list of entry dicts."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (FL-Outbreak-Tracker/2.0; public health research)"},
        follow_redirects=True,
    ) as client:
        resp = await client.get(raw_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        content = resp.text
    parsed = feedparser.parse(content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Failed to parse feed {raw_url!r}: {parsed.bozo_exception}")
    return parsed.entries


def _is_relevant(entry: feedparser.FeedParserDict) -> bool:
    """Return True if the article looks disease-related based on title/summary."""
    text = " ".join([
        entry.get("title", ""),
        entry.get("summary", ""),
    ]).lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def _entry_url(entry: feedparser.FeedParserDict) -> str | None:
    return entry.get("link") or entry.get("id") or None


def _entry_published(entry: feedparser.FeedParserDict) -> datetime | None:
    ts = entry.get("published_parsed") or entry.get("updated_parsed")
    if ts is None:
        return None
    return datetime(*ts[:6], tzinfo=timezone.utc)


async def _fetch_body(client: httpx.AsyncClient, url: str) -> str:
    """
    Fetch the article page and extract readable body text.
    Falls back to an empty string on any error.
    """
    try:
        resp = await client.get(url, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove navigation, ads, scripts
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # Prefer <article> content, fall back to <main>, then <body>
        container = soup.find("article") or soup.find("main") or soup.body
        if container is None:
            return ""
        text = container.get_text(separator=" ", strip=True)
        return text[:MAX_BODY_CHARS]
    except Exception as exc:
        log.debug("Could not fetch body for %s: %s", url, exc)
        return ""


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def _article_exists(session, url: str) -> bool:
    result = await session.execute(
        select(NewsArticle.id).where(NewsArticle.url == url)
    )
    return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Main ingestion logic
# ---------------------------------------------------------------------------

async def ingest_feed(feed: FeedConfig) -> int:
    """
    Ingest one RSS feed.
    Returns the number of new articles stored.
    """
    log.info("Fetching feed: %s (%s)", feed["source"], feed["url"])
    try:
        entries = await _parse_feed(feed["url"])
    except Exception as exc:
        log.error("Feed error [%s]: %s", feed["source"], exc)
        return 0

    relevant = [e for e in entries if _is_relevant(e)]
    log.info("%s: %d/%d entries relevant", feed["source"], len(relevant), len(entries))

    stored = 0
    async with httpx.AsyncClient() as client:
        async with AsyncSessionLocal() as session:
            for entry in relevant:
                url = _entry_url(entry)
                if not url:
                    continue

                if await _article_exists(session, url):
                    log.debug("Already stored: %s", url)
                    continue

                body = await _fetch_body(client, url)

                article = NewsArticle(
                    url=url,
                    title=entry.get("title"),
                    source=feed["source"],
                    published_at=_entry_published(entry),
                    body_text=body,
                )
                session.add(article)
                await session.flush()  # get article.id before NLP

                # Run NLP extraction on title + body
                text_for_nlp = f"{entry.get('title', '')} {body}"
                signals = extract_signals(text_for_nlp)

                for sig in signals:
                    session.add(
                        ArticleSignal(
                            article_id=article.id,
                            county_fips=sig.get("county_fips"),
                            disease_id=sig.get("disease_id"),
                            extracted_case_count=sig.get("case_count"),
                            confidence=sig.get("confidence"),
                            extraction_notes=sig.get("notes"),
                        )
                    )

                await session.commit()
                stored += 1
                log.info("Stored: [%s] %s", feed["source"], url)

    return stored


# ---------------------------------------------------------------------------
# GDELT Doc 2.0 ingestion
# ---------------------------------------------------------------------------

GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"

# Search terms: any disease keyword near Florida context
GDELT_QUERY = (
    "(measles OR mumps OR rubella OR pertussis OR \"whooping cough\" "
    "OR varicella OR chickenpox OR hepatitis OR meningococcal OR meningitis "
    "OR \"vaccine-preventable\") Florida"
)

# How far back to look on each run (days)
GDELT_LOOKBACK_DAYS = 7


async def ingest_gdelt(lookback_days: int = GDELT_LOOKBACK_DAYS) -> int:
    """
    Query the GDELT Doc 2.0 API for recent FL disease news, store new articles.
    Returns count of new articles stored.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=lookback_days)

    params = {
        "query": GDELT_QUERY,
        "mode": "artlist",
        "maxrecords": "250",
        "sourcelang": "english",
        "startdatetime": start.strftime("%Y%m%d%H%M%S"),
        "enddatetime": now.strftime("%Y%m%d%H%M%S"),
        "format": "json",
    }

    log.info("Querying GDELT: lookback=%dd, from %s", lookback_days, start.date())
    data: dict = {}
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": "Mozilla/5.0 (FL-Outbreak-Tracker/2.0; public health research)"},
                follow_redirects=True,
            ) as client:
                resp = await client.get(GDELT_API, params=params, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 429:
                    wait = 30 * (attempt + 1)
                    log.warning("GDELT rate limited — waiting %ds (attempt %d/3)", wait, attempt + 1)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                break
        except Exception as exc:
            log.error("GDELT API error (attempt %d/3): %s", attempt + 1, exc)
            if attempt < 2:
                await asyncio.sleep(15)
    if not data:
        return 0

    articles = data.get("articles", [])
    log.info("GDELT returned %d articles", len(articles))

    stored = 0
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (FL-Outbreak-Tracker/2.0; public health research)"},
        follow_redirects=True,
    ) as client:
        async with AsyncSessionLocal() as session:
            for art in articles:
                url = art.get("url")
                if not url:
                    continue

                if await _article_exists(session, url):
                    log.debug("Already stored: %s", url)
                    continue

                # Parse GDELT date: "20260408T123456Z"
                published_at: datetime | None = None
                seen = art.get("seendate", "")
                try:
                    published_at = datetime.strptime(seen, "%Y%m%dT%H%M%SZ").replace(
                        tzinfo=timezone.utc
                    )
                except ValueError:
                    pass

                body = await _fetch_body(client, url)

                title = art.get("title", "")
                source_name = art.get("domain", "GDELT")

                # Pre-filter: skip if body + title have no relevance keywords
                combined = f"{title} {body}".lower()
                if not any(kw in combined for kw in RELEVANCE_KEYWORDS):
                    log.debug("Skipping irrelevant GDELT article: %s", url)
                    continue

                article = NewsArticle(
                    url=url,
                    title=title,
                    source=source_name,
                    published_at=published_at,
                    body_text=body,
                )
                session.add(article)
                await session.flush()

                text_for_nlp = f"{title} {body}"
                signals = extract_signals(text_for_nlp)

                for sig in signals:
                    session.add(
                        ArticleSignal(
                            article_id=article.id,
                            county_fips=sig.get("county_fips"),
                            disease_id=sig.get("disease_id"),
                            extracted_case_count=sig.get("case_count"),
                            confidence=sig.get("confidence"),
                            extraction_notes=sig.get("notes"),
                        )
                    )

                await session.commit()
                stored += 1
                log.info("Stored GDELT: [%s] %s", source_name, url)

    log.info("GDELT ingestion complete — %d new articles stored.", stored)
    return stored


async def _load_disease_cache() -> None:
    """Pre-populate the NLP disease-id cache from the DB."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Disease))
        diseases = result.scalars().all()
    set_disease_id_cache({d.name: d.id for d in diseases})
    log.info("Disease ID cache loaded: %d entries", len(diseases))


async def ingest_all_feeds(feeds: list[FeedConfig] | None = None) -> int:
    """Ingest all configured feeds + GDELT. Returns total articles stored."""
    await _load_disease_cache()
    feeds = feeds or FEEDS
    total = 0
    for feed in feeds:
        total += await ingest_feed(feed)
    total += await ingest_gdelt()
    log.info("Full ingestion complete — %d new articles stored.", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ingest_all_feeds())
