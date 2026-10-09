"""Celery Beat schedule (JOB-006): in code, documented, timezone-explicit (America/New_York).

The daily 02:00 ET pipeline runs as a chain so each stage only starts after the previous
succeeds (§21.3): SEC → market → news → parse → embed → metrics. Pollers and housekeeping run on
their own cadences. All market-related times are ET (set on the Celery app).
"""

from __future__ import annotations

from celery import chain
from celery.schedules import crontab

from app.config import get_settings
from app.tasks.celery_app import celery_app

settings = get_settings()
_SEED = ["NVDA", "AAPL", "JPM"]


@celery_app.task(name="daily_pipeline", queue="ingestion")
def daily_pipeline(tickers: list[str] | None = None) -> str:
    """Kick off the ordered daily refresh chain for the seed/watched universe (§21.3)."""
    from app.tasks.ingestion import (
        fetch_market_data,
        fetch_news,
        fetch_sec_filings,
        generate_embeddings,
        parse_documents,
        update_financial_metrics,
    )

    tickers = tickers or _SEED
    # Per-ticker parse/metrics, fanned into the chain after the batch fetches.
    steps = [
        fetch_sec_filings.si(tickers),
        fetch_market_data.si(tickers),
        fetch_news.si(tickers),
    ]
    for ticker in tickers:
        steps.append(parse_documents.si(ticker))
    steps.append(generate_embeddings.si())
    for ticker in tickers:
        steps.append(update_financial_metrics.si(ticker))
    chain(*steps).apply_async()
    return "scheduled"


celery_app.conf.beat_schedule = {
    # Daily full refresh at 02:00 ET (§21.3).
    "daily-pipeline": {
        "task": "daily_pipeline",
        "schedule": crontab(hour=2, minute=0),
    },
    # EDGAR new-filing poller for watched/seed companies, ≤10 min (§21.3).
    "edgar-poller": {
        "task": "poll_edgar_new_filings",
        "schedule": crontab(minute=f"*/{settings.edgar_poll_interval_minutes}"),
    },
    # News refresh ~15 min.
    "news-poller": {
        "task": "fetch_news",
        "schedule": crontab(minute=f"*/{settings.news_poll_interval_minutes}"),
        "args": (_SEED,),
    },
    # Price refresh after the US close (EOD): 16:30 ET on weekdays.
    "price-eod": {
        "task": "fetch_market_data",
        "schedule": crontab(hour=16, minute=30, day_of_week="mon-fri"),
        "args": (_SEED,),
    },
    # Alert dispatch every 5 min (keeps the 30-min DoD SLA comfortably).
    "send-alerts": {
        "task": "send_alerts",
        "schedule": crontab(minute="*/5"),
    },
    # Nightly evaluation smoke run (§18.4).
    "nightly-eval": {
        "task": "run_eval_suite",
        "schedule": crontab(hour=3, minute=0),
    },
    # Chat-log retention purge, daily (SEC-014).
    "retention-purge": {
        "task": "purge_chat_history",
        "schedule": crontab(hour=4, minute=0),
    },
}
