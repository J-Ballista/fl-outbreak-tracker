"""
Cron runner for FL Outbreak Tracker scrapers.

Runs as a long-lived process inside the `scraper` Docker service.
Uses the `schedule` library for simple cron-like scheduling.

Schedule:
  - News RSS scraper  : nightly at 02:00
  - Alert engine      : nightly at 02:30 (after news ingest)
  - CHARTS scraper    : weekly, Sunday at 03:00
  - Vacc scraper      : monthly, 1st at 04:00

Run standalone:
    python -m backend.scrapers.cron_runner
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date

import schedule

from backend.models.database import AsyncSessionLocal
from backend.scrapers.fl_doh_exemptions import ingest_exemptions
from backend.scrapers.news_feed import ingest_all_feeds
from backend.services.alert_engine import generate_alerts

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job wrappers
# ---------------------------------------------------------------------------

def _run_async(coro) -> None:
    """Execute an async coroutine in a new event loop (schedule is sync)."""
    asyncio.run(coro)


def job_news_scraper() -> None:
    log.info("[cron] Starting news RSS ingest")
    try:
        count = asyncio.run(ingest_all_feeds())
        log.info("[cron] News ingest complete — %d new articles", count)
    except Exception:
        log.exception("[cron] News ingest failed")


def job_alert_engine() -> None:
    log.info("[cron] Running alert engine")
    try:
        async def _run():
            async with AsyncSessionLocal() as session:
                return await generate_alerts(session)
        count = asyncio.run(_run())
        log.info("[cron] Alert engine complete — %d new alerts", count)
    except Exception:
        log.exception("[cron] Alert engine failed")


def job_charts_scraper() -> None:
    log.info("[cron] CHARTS scraper not yet implemented — skipping")


def job_vacc_scraper() -> None:
    log.info("[cron] Running FL DOH exemption scraper")
    try:
        count = asyncio.run(ingest_exemptions())
        log.info("[cron] Exemption scraper complete — %d rows inserted", count)
    except Exception:
        log.exception("[cron] Exemption scraper failed")


# ---------------------------------------------------------------------------
# Schedule setup
# ---------------------------------------------------------------------------

def setup_schedule() -> None:
    schedule.every().day.at("02:00").do(job_news_scraper)
    schedule.every().day.at("02:30").do(job_alert_engine)
    schedule.every().sunday.at("03:00").do(job_charts_scraper)

    # Monthly: run on the 1st of each month
    schedule.every().day.at("04:00").do(
        lambda: job_vacc_scraper() if date.today().day == 1 else None
    )

    log.info(
        "[cron] Schedule registered:\n"
        "  02:00 daily   → news RSS + GDELT ingest\n"
        "  02:30 daily   → alert engine\n"
        "  03:00 Sunday  → CHARTS scraper (stub)\n"
        "  04:00 monthly → FL DOH exemption scraper"
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log.info("[cron] FL Outbreak Tracker cron runner starting")
    setup_schedule()

    while True:
        schedule.run_pending()
        time.sleep(30)  # check every 30 s


if __name__ == "__main__":
    main()
