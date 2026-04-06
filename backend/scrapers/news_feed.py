"""
RSS news feed scraper
=====================
Ingests articles from Florida local news outlets, stores raw text in
news_articles, then calls the NLP classifier to extract disease/county signals
and writes them to article_signals.

Configured feeds (extend FEEDS to add more sources):
  - Orlando Sentinel  — Health section
  - Miami Herald      — Health section
  - Tampa Bay Times   — Health section

Run standalone:
    python -m backend.scrapers.news_feed

Or import and call ``ingest_all_feeds()`` from a scheduler.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.database import ArticleSignal, AsyncSessionLocal, NewsArticle
from backend.nlp.classifier import extract_signals

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feed registry
# ---------------------------------------------------------------------------

class FeedConfig(TypedDict):
    source: str
    url: str


FEEDS: list[FeedConfig] = [
    {
        "source": "Orlando Sentinel",
        "url": "https://www.orlandosentinel.com/health/feed/",
    },
    {
        "source": "Miami Herald",
        "url": "https://www.miamiherald.com/news/health-care/rss.xml",
    },
    {
        "source": "Tampa Bay Times",
        "url": "https://www.tampabay.com/health/feed/",
    },
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

def _parse_feed(raw_url: str) -> list[feedparser.FeedParserDict]:
    """Fetch and parse an RSS feed. Returns a list of entry dicts."""
    parsed = feedparser.parse(raw_url)
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
        entries = _parse_feed(feed["url"])
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


async def ingest_all_feeds(feeds: list[FeedConfig] | None = None) -> int:
    """Ingest all configured feeds sequentially. Returns total articles stored."""
    feeds = feeds or FEEDS
    total = 0
    for feed in feeds:
        total += await ingest_feed(feed)
    log.info("RSS ingestion complete — %d new articles stored.", total)
    return total


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ingest_all_feeds())
