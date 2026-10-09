"""Ingestion-queue tasks (JOB-003): SEC, market, news, parse, embed, metrics, EDGAR poller.

Each task is a thin, idempotent (ING-001) wrapper over a Phase 1/2 pipeline function — no new
ingestion logic. The real per-item failure isolation and `ingestion_runs`/dead-letter bookkeeping
already live in those pipelines; these tasks add the Celery queue, retry policy, and job-row
tracking (JOB-001/002).
"""

from __future__ import annotations

from typing import Any

from celery import Task

from app.db import _session_factory, session_scope
from app.embeddings.pipeline import embed_pending
from app.finance.builder import build_company_metrics
from app.finance.ratio_builder import build_company_ratios
from app.ingestion.documents.pipeline import parse_and_chunk
from app.ingestion.news import ingest_news_for_tickers
from app.ingestion.prices import ingest_prices_for_tickers
from app.ingestion.sec import ingest_company
from app.ingestion.sec.poller import find_new_accessions
from app.repositories import companies as company_repo
from app.repositories import filings as filing_repo
from app.tasks.base import RETRY_KWARGS, job_task
from app.tasks.celery_app import celery_app
from app.utils.storage import get_object_storage

_SEED_TICKERS = ["NVDA", "AAPL", "JPM"]


@celery_app.task(bind=True, queue="ingestion", name="fetch_sec_filings", **RETRY_KWARGS)
def fetch_sec_filings(self: Task, tickers: list[str]) -> dict[str, int]:
    storage = get_object_storage()
    out: dict[str, int] = {}
    with job_task(self, job_type="fetch_sec_filings", params={"tickers": tickers}) as (
        session,
        progress,
    ):
        for i, ticker in enumerate(tickers):
            counts = ingest_company(session, ticker, storage=storage)
            out[ticker] = counts.filings_ingested
            progress.update(progress=int((i + 1) / len(tickers) * 100), stage=f"sec:{ticker}")
    return out


@celery_app.task(bind=True, queue="ingestion", name="fetch_market_data", **RETRY_KWARGS)
def fetch_market_data(self: Task, tickers: list[str]) -> dict[str, int]:
    with job_task(self, job_type="fetch_market_data", params={"tickers": tickers}):
        results = ingest_prices_for_tickers(_session_factory(), tickers)
    return {t: c.bars for t, c in results.items()}


@celery_app.task(bind=True, queue="ingestion", name="fetch_news", **RETRY_KWARGS)
def fetch_news(self: Task, tickers: list[str]) -> dict[str, int]:
    with job_task(self, job_type="fetch_news", params={"tickers": tickers}):
        results = ingest_news_for_tickers(_session_factory(), tickers)
    return {t: c.ingested for t, c in results.items()}


@celery_app.task(bind=True, queue="ingestion", name="fetch_insider_and_holdings", **RETRY_KWARGS)
def fetch_insider_and_holdings(self: Task, tickers: list[str]) -> dict[str, Any]:
    """Form 4 / 13F ingestion is P2 and not implemented (Appendix F #10). This task exists so the
    schedule and job list are complete; it records a no-op run rather than silently missing."""
    with job_task(self, job_type="fetch_insider_and_holdings", params={"tickers": tickers}):
        pass
    return {"status": "not_implemented", "reason": "Form 4 / 13F ingestion is P2"}


@celery_app.task(bind=True, queue="ingestion", name="parse_documents", **RETRY_KWARGS)
def parse_documents(self: Task, ticker: str) -> int:
    storage = get_object_storage()
    parsed = 0
    with job_task(self, job_type="parse_documents", params={"ticker": ticker}) as (
        session,
        progress,
    ):
        company = company_repo.get_by_ticker(session, ticker)
        if company is None:
            raise ValueError(f"unknown ticker: {ticker}")
        filings = filing_repo.list_filings(
            session, company_id=company.id, filing_type=None, limit=1000, after_id=None
        )
        for i, filing in enumerate(filings):
            if filing.raw_document_location:
                parse_and_chunk(session, filing, storage=storage)
                parsed += 1
            if filings:
                progress.update(progress=int((i + 1) / len(filings) * 100))
    return parsed


@celery_app.task(bind=True, queue="ingestion", name="generate_embeddings", **RETRY_KWARGS)
def generate_embeddings(self: Task) -> int:
    with job_task(self, job_type="generate_embeddings") as (session, _progress):
        counts = embed_pending(session)
    return counts.embedded


@celery_app.task(bind=True, queue="ingestion", name="update_financial_metrics", **RETRY_KWARGS)
def update_financial_metrics(self: Task, ticker: str) -> dict[str, int]:
    with job_task(self, job_type="update_financial_metrics", params={"ticker": ticker}) as (
        session,
        _progress,
    ):
        company = company_repo.get_by_ticker(session, ticker)
        if company is None:
            raise ValueError(f"unknown ticker: {ticker}")
        base = build_company_metrics(session, company)
        ratios = build_company_ratios(session, company)
    return {"metrics": base.annual_metrics, "ratios": ratios}


@celery_app.task(bind=True, queue="ingestion", name="poll_edgar_new_filings", **RETRY_KWARGS)
def poll_edgar_new_filings(self: Task, tickers: list[str] | None = None) -> dict[str, int]:
    """≤10-min EDGAR poll (§21.3): for each watched/seed company, if EDGAR has an accession we
    haven't ingested, enqueue a refresh for that company. Idempotent — the refresh re-checks."""
    tickers = tickers or _SEED_TICKERS
    new_counts: dict[str, int] = {}
    with (
        job_task(self, job_type="poll_edgar_new_filings", params={"tickers": tickers}),
        session_scope() as session,
    ):
        for ticker in tickers:
            company = company_repo.get_by_ticker(session, ticker)
            if company is None:
                continue
            new = find_new_accessions(session, company.cik)
            new_counts[ticker] = len(new)
    for ticker, n in new_counts.items():
        if n:
            refresh_company_data.delay(ticker)
    return new_counts


def _refresh_one(ticker: str) -> None:
    """Full single-company pipeline, run inline (used by the refresh task + chainable)."""
    storage = get_object_storage()
    with session_scope() as session:
        ingest_company(session, ticker, storage=storage)
    ingest_prices_for_tickers(_session_factory(), [ticker])
    ingest_news_for_tickers(_session_factory(), [ticker])
    with session_scope() as session:
        company = company_repo.get_by_ticker(session, ticker)
        if company is None:
            raise ValueError(f"unknown ticker: {ticker}")
        for filing in filing_repo.list_filings(
            session, company_id=company.id, filing_type=None, limit=1000, after_id=None
        ):
            if filing.raw_document_location:
                parse_and_chunk(session, filing, storage=storage)
        embed_pending(session)
        build_company_metrics(session, company)
        build_company_ratios(session, company)


@celery_app.task(bind=True, queue="interactive", name="refresh_company_data", **RETRY_KWARGS)
def refresh_company_data(self: Task, ticker: str) -> str:
    """Admin/user-triggered full refresh for one company (the Phase 4a `POST /admin/.../refresh`
    enqueues this). On the `interactive` queue so an operator refresh isn't stuck behind the
    nightly batch."""
    with job_task(self, job_type="refresh_company_data", params={"ticker": ticker}) as (
        _session,
        progress,
    ):
        progress.update(progress=10, stage="refresh:start")
        _refresh_one(ticker)
        progress.update(progress=100, stage="refresh:done")
    return ticker


__all__ = [
    "fetch_insider_and_holdings",
    "fetch_market_data",
    "fetch_news",
    "fetch_sec_filings",
    "generate_embeddings",
    "parse_documents",
    "poll_edgar_new_filings",
    "refresh_company_data",
    "update_financial_metrics",
]
