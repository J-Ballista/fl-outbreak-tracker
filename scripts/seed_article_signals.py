"""
Seed script: inserts sample news articles and NLP-extracted signals.

Run from project root:
    python scripts/seed_article_signals.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from backend.models.database import AsyncSessionLocal, NewsArticle, ArticleSignal

# (title, url, source, published_at, county_fips, disease_id, case_count, confidence)
ARTICLES = [
    ("Measles exposure reported at Miami-Dade school",
     "https://www.miamiherald.com/news/health/article-measles-miami-dade-2024",
     "Miami Herald", "2024-03-12", "12086", 1, 3, 0.90),

    ("Pertussis outbreak spreads across Broward County",
     "https://www.sun-sentinel.com/news/pertussis-broward-outbreak-2024",
     "Sun Sentinel", "2024-05-22", "12011", 4, 14, 0.88),

    ("Varicella cases rise in Orange County schools",
     "https://www.orlandosentinel.com/health/varicella-orange-county-schools",
     "Orlando Sentinel", "2024-09-08", "12095", 5, 22, 0.85),

    ("Hepatitis A cluster in Hillsborough restaurant workers",
     "https://www.tampabay.com/health/hepatitis-a-hillsborough-2024",
     "Tampa Bay Times", "2024-11-03", "12057", 6, 6, 0.82),

    ("Mumps confirmed at University of Florida campus",
     "https://www.gainesville.com/story/news/health/mumps-uf-campus-2025",
     "Gainesville Sun", "2025-01-18", "12001", 2, 4, 0.87),

    ("Meningococcal disease reported in Palm Beach County",
     "https://www.palmbeachpost.com/health/meningococcal-palm-beach-2025",
     "Palm Beach Post", "2025-02-05", "12099", 8, 2, 0.80),

    ("Pertussis cases surge in Duval County this winter",
     "https://www.jacksonville.com/news/health/pertussis-duval-2025",
     "Jacksonville.com", "2025-01-30", "12031", 4, 9, 0.86),

    ("Chickenpox outbreak at Pinellas County daycare",
     "https://www.tampabay.com/health/chickenpox-pinellas-daycare-2025",
     "Tampa Bay Times", "2025-03-01", "12103", 5, 18, 0.83),

    ("Hepatitis B screening drive in Miami after uptick",
     "https://www.miamiherald.com/health/hepatitis-b-miami-screening-2025",
     "Miami Herald", "2025-02-20", "12086", 7, None, 0.65),

    ("Measles scare at Orlando theme park prompts investigation",
     "https://www.orlandosentinel.com/news/measles-orlando-theme-park-2025",
     "Orlando Sentinel", "2025-03-14", "12095", 1, 1, 0.78),

    ("Whooping cough cases reported in Alachua County",
     "https://www.gainesville.com/story/news/health/pertussis-alachua-2024",
     "Gainesville Sun", "2024-10-17", "12001", 4, 5, 0.84),

    ("Two Haemophilus influenzae cases in Collier County",
     "https://www.naplesnews.com/health/hib-collier-2024",
     "Naples Daily News", "2024-07-29", "12021", 9, 2, 0.81),

    ("Tetanus case treated at Tampa General, officials urge vaccination",
     "https://www.tampabay.com/health/tetanus-tampa-general-2024",
     "Tampa Bay Times", "2024-08-14", "12057", 10, 1, 0.92),

    ("Rubella vaccination rates drop in Leon County schools",
     "https://www.tallahassee.com/health/rubella-vaccine-leon-2025",
     "Tallahassee Democrat", "2025-01-07", "12073", 3, None, 0.60),

    ("Polio awareness campaign launched in Broward after national alert",
     "https://www.sun-sentinel.com/health/polio-awareness-broward-2024",
     "Sun Sentinel", "2024-06-03", "12011", 12, None, 0.55),

    ("Varicella outbreak at Sarasota elementary",
     "https://www.heraldtribune.com/health/varicella-sarasota-elementary-2025",
     "Sarasota Herald-Tribune", "2025-02-11", "12115", 5, 11, 0.88),

    ("Hepatitis A confirmed in three Miami restaurant workers",
     "https://www.miamiherald.com/health/hepatitis-a-miami-workers-2025",
     "Miami Herald", "2025-03-18", "12086", 6, 3, 0.90),

    ("Mumps outbreak at Jacksonville high school",
     "https://www.jacksonville.com/health/mumps-jacksonville-high-2024",
     "Jacksonville.com", "2024-04-25", "12031", 2, 7, 0.86),

    ("Measles exposure at Fort Lauderdale airport",
     "https://www.sun-sentinel.com/health/measles-fort-lauderdale-airport-2025",
     "Sun Sentinel", "2025-01-22", "12011", 1, 1, 0.89),

    ("Pertussis reported across Polk County elementary schools",
     "https://www.theledger.com/health/pertussis-polk-schools-2025",
     "The Ledger", "2025-02-28", "12105", 4, 8, 0.85),
]


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(text("DELETE FROM article_signals"))
        await session.execute(text("DELETE FROM news_articles"))
        await session.commit()

        inserted_articles = 0
        inserted_signals = 0

        for (title, url, source, pub_date, county_fips,
             disease_id, case_count, confidence) in ARTICLES:
            article = NewsArticle(
                url=url,
                title=title,
                source=source,
                published_at=datetime.strptime(pub_date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                body_text=f"{title}. Reported by {source}.",
            )
            session.add(article)
            await session.flush()  # get article.id

            signal = ArticleSignal(
                article_id=article.id,
                county_fips=county_fips,
                disease_id=disease_id,
                extracted_case_count=case_count,
                confidence=confidence,
                extraction_notes=f"disease_id={disease_id}, county_fips={county_fips}"
                                 + (f", case_count={case_count}" if case_count else ""),
            )
            session.add(signal)
            inserted_articles += 1
            inserted_signals += 1

        await session.commit()
        print(f"Inserted {inserted_articles} articles and {inserted_signals} signals.")


if __name__ == "__main__":
    asyncio.run(seed())
