"""Price & corporate-action ingestion pipeline (Phase 1d).

Fetches daily bars from the price source, upserts `price_history` (raw AND adjusted close,
DR-025), derives splits/dividends into `corporate_actions`, and records `data_freshness` for the
`price` source. Idempotent (ING-001); failures are isolated and dead-lettered (ING-004/005),
never crashing the run.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Company
from app.providers.prices import PriceBar, PriceSource, get_price_source
from app.repositories import prices as price_repo
from app.repositories.freshness import record_freshness
from app.repositories.ingestion import dead_letter, finish_run, start_run
from app.utils.dates import years_ago
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)
PRICE_SOURCE = "price"


@dataclass
class PriceCounts:
    bars: int = 0
    splits: int = 0
    dividends: int = 0


def _provider_label() -> str:
    return "tiingo" if get_settings().provider_mode == "live" else "mock"


def _corporate_actions(
    company_id: int, bars: list[PriceBar], provider: str
) -> list[dict[str, Any]]:
    """Derive split/dividend corporate actions from per-day bar signals (DR-025)."""
    actions: list[dict[str, Any]] = []
    for bar in bars:
        if bar.split_factor and bar.split_factor != 1:
            actions.append(
                {
                    "company_id": company_id,
                    "action_type": "split",
                    "ex_date": bar.date,
                    "ratio_or_amount": bar.split_factor,
                    "provider": provider,
                }
            )
        if bar.div_cash and bar.div_cash > 0:
            actions.append(
                {
                    "company_id": company_id,
                    "action_type": "dividend",
                    "ex_date": bar.date,
                    "ratio_or_amount": bar.div_cash,
                    "provider": provider,
                }
            )
    return actions


def ingest_prices(
    session: Session,
    company: Company,
    *,
    source: PriceSource | None = None,
    today: date | None = None,
) -> PriceCounts:
    """Ingest price history + corporate actions for one company. Records an ingestion run."""
    settings = get_settings()
    source = source or get_price_source()
    today = today or datetime.now(UTC).date()
    provider = _provider_label()
    counts = PriceCounts()
    run = start_run(session, source=PRICE_SOURCE, company_id=company.id)
    attempt_at = datetime.now(UTC)

    try:
        start = years_ago(today, settings.backfill_price_years)
        bars = list(source.get_prices(company.ticker, start=start, end=today))
        ingested_at = datetime.now(UTC)
        rows = [
            price_repo.price_bar_mapping(
                company.id,
                bar_date=b.date,
                open_=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                adj_close=b.adj_close,
                volume=b.volume,
                provider=provider,
                ingested_at=ingested_at,
            )
            for b in bars
        ]
        counts.bars = price_repo.upsert_price_bars(session, company.id, rows)
        actions = _corporate_actions(company.id, bars, provider)
        price_repo.replace_corporate_actions(session, company.id, actions, provider=provider)
        counts.splits = sum(1 for a in actions if a["action_type"] == "split")
        counts.dividends = sum(1 for a in actions if a["action_type"] == "dividend")
        record_freshness(
            session,
            company_id=company.id,
            source=PRICE_SOURCE,
            status="fresh",
            last_success_at=ingested_at,
            last_attempt_at=attempt_at,
        )
        finish_run(
            session,
            run,
            status="success",
            counts={"bars": counts.bars, "splits": counts.splits, "dividends": counts.dividends},
        )
    except Exception as exc:  # ING-005: never crash; record and surface
        dead_letter(
            session,
            source=PRICE_SOURCE,
            payload_ref=company.ticker,
            error=f"{type(exc).__name__}: {exc}",
        )
        record_freshness(
            session,
            company_id=company.id,
            source=PRICE_SOURCE,
            status="failed",
            last_success_at=None,
            last_attempt_at=attempt_at,
            message=str(exc),
        )
        finish_run(session, run, status="failed", counts={}, error=str(exc))
        log_event(
            logger, logging.ERROR, "price.ingest.failed", ticker=company.ticker, error=str(exc)
        )
    return counts


def ingest_prices_for_tickers(
    session_factory: Callable[[], Session],
    tickers: list[str],
    *,
    source: PriceSource | None = None,
) -> dict[str, PriceCounts]:
    """Ingest several companies; one company's failure never aborts the batch (ING-005)."""
    results: dict[str, PriceCounts] = {}
    for ticker in tickers:
        with session_factory() as session:
            company = session.scalar(select(Company).where(Company.ticker == ticker.upper()))
            if company is None:
                log_event(logger, logging.ERROR, "price.company.missing", ticker=ticker)
                continue
            results[ticker] = ingest_prices(session, company, source=source)
            session.commit()
    return results
