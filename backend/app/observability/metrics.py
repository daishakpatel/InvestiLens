"""Prometheus metrics (OBS-002, ADR-0021): API latency, LLM cost, ingestion lag, job failures,
cache hit rate, retrieval score distribution, and citation rejection rate.

Two kinds of metric here, by how they're updated:
- **Push** (counters/histograms): updated at the moment an event happens — one call per API
  request, LLM call, retrieval, or citation verification. Hooked into the single existing choke
  point for each (middleware, `llm_calls` repo, `rag.pipeline`, `citation.pipeline`) rather than
  scattered across every call site.
- **Pull** (gauges): computed fresh from the DB when `/metrics` is scraped (ingestion lag, queue
  depth, job/ingestion failure rate) — cheaper than keeping them live-updated and always correct
  for the current DB state, matching how `app/observability/alerts.py` evaluates the same data.

`cache_hit_ratio` is deliberately a no-op gauge: no cache layer exists yet (the RAG-050 semantic
cache was deferred past Phase 2c/3c). The metric name and a Grafana panel exist so the dashboard
is ready the day a cache lands; until then it reports `NaN` (Prometheus's "no data" value) rather
than a fabricated number.
"""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import freshness as freshness_repo
from app.repositories import ingestion as ingestion_repo
from app.repositories import jobs as job_repo

REGISTRY = CollectorRegistry()

API_REQUEST_LATENCY = Histogram(
    "api_request_duration_seconds",
    "API request latency (OBS-002: p50/p95/p99 via histogram_quantile).",
    ["method", "route", "status"],
    registry=REGISTRY,
)
LLM_CALL_LATENCY = Histogram(
    "llm_call_duration_seconds",
    "LLM call latency by purpose/model.",
    ["purpose", "model"],
    registry=REGISTRY,
)
LLM_COST_USD = Counter(
    "llm_cost_usd_total",
    "Cumulative estimated LLM spend (OBS-002 'LLM cost/day' via rate()).",
    ["purpose", "model"],
    registry=REGISTRY,
)
RETRIEVAL_TOP_SCORE = Histogram(
    "retrieval_top_score",
    "Top reranked/fused score per retrieval (RAG retrieval score distribution).",
    ["intent"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)
CITATION_VERIFICATIONS = Counter(
    "citation_verifications_total",
    "Claim verification outcomes (citation rejection rate = rejected / total).",
    ["status"],
    registry=REGISTRY,
)
INGESTION_LAG_MINUTES = Gauge(
    "ingestion_lag_minutes",
    "Minutes since the last successful ingestion per source (max across companies).",
    ["source"],
    registry=REGISTRY,
)
JOB_FAILURE_RATE = Gauge(
    "job_failure_rate",
    "Fraction of the most recent background jobs that failed.",
    registry=REGISTRY,
)
INGESTION_FAILURE_RATE = Gauge(
    "ingestion_failure_rate",
    "Fraction of the most recent ingestion runs that failed.",
    registry=REGISTRY,
)
QUEUE_DEPTH = Gauge(
    "job_queue_depth",
    "Number of jobs currently queued.",
    registry=REGISTRY,
)
CACHE_HIT_RATIO = Gauge(
    "cache_hit_ratio",
    "Placeholder: no cache layer exists yet (RAG-050 semantic cache deferred); always NaN.",
    registry=REGISTRY,
)
CACHE_HIT_RATIO.set(float("nan"))


def record_llm_call(*, purpose: str, model: str, cost_usd: Decimal, latency_ms: int) -> None:
    """Hooked from `app.repositories.llm_calls.record_call` — the one place every LLM call logs."""
    LLM_CALL_LATENCY.labels(purpose=purpose, model=model).observe(latency_ms / 1000)
    LLM_COST_USD.labels(purpose=purpose, model=model).inc(float(cost_usd))


def record_retrieval_score(*, intent: str, top_score: float) -> None:
    RETRIEVAL_TOP_SCORE.labels(intent=intent).observe(max(0.0, min(1.0, top_score)))


def record_citation_verification(status: str) -> None:
    CITATION_VERIFICATIONS.labels(status=status).inc()


def refresh_gauges(session: Session) -> None:
    """Recompute every pull-based gauge from current DB state (called on each `/metrics` scrape)."""
    now = datetime.now(UTC)
    lag_by_source: dict[str, float] = {}
    for row in freshness_repo.list_all(session):
        if row.last_success_at is None:
            continue
        lag_minutes = (now - row.last_success_at).total_seconds() / 60
        lag_by_source[row.source] = max(lag_by_source.get(row.source, 0.0), lag_minutes)
    for source, lag in lag_by_source.items():
        INGESTION_LAG_MINUTES.labels(source=source).set(lag)

    recent_jobs = job_repo.recent(session, limit=20)
    terminal_jobs = [j for j in recent_jobs if j.status in ("done", "failed")]
    if terminal_jobs:
        JOB_FAILURE_RATE.set(sum(j.status == "failed" for j in terminal_jobs) / len(terminal_jobs))
    QUEUE_DEPTH.set(job_repo.queued_count(session))

    recent_runs = ingestion_repo.recent(session, limit=20)
    terminal_runs = [r for r in recent_runs if r.status in ("success", "failed", "partial")]
    if terminal_runs:
        INGESTION_FAILURE_RATE.set(
            sum(r.status == "failed" for r in terminal_runs) / len(terminal_runs)
        )


router = APIRouter(tags=["Observability"])
_DB = Depends(get_db)


@router.get("/metrics", include_in_schema=False)
async def metrics(db: Session = _DB) -> Response:
    """Prometheus scrape endpoint. No auth (standard scrape convention; not linked from the UI)."""
    refresh_gauges(db)
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


async def api_latency_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Records every request's latency/status into `api_request_duration_seconds` (OBS-002)."""
    started = time.monotonic()
    response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    API_REQUEST_LATENCY.labels(
        method=request.method, route=route_path, status=str(response.status_code)
    ).observe(time.monotonic() - started)
    return response
