"""Operational tables: ingestion, jobs, LLM/retrieval logging, quality, eval, freshness
(spec §23.3). These support observability (NFR-015), idempotency (NFR-014), and evaluation.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Money, TimestampMixin, intpk


class IngestionRun(Base):
    """One ingestion pass for a source/company, with counts and outcome."""

    __tablename__ = "ingestion_runs"

    id: Mapped[intpk]
    source: Mapped[str] = mapped_column(String(32))
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(16))
    counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


class IngestionDeadLetter(Base, TimestampMixin):
    """A record that failed validation (DR-003); parked for inspection/replay."""

    __tablename__ = "ingestion_dead_letters"

    id: Mapped[intpk]
    source: Mapped[str] = mapped_column(String(32))
    payload_ref: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Job(Base):
    """A background job (e.g. report generation) with progress tracking."""

    __tablename__ = "jobs"

    id: Mapped[intpk]
    job_type: Mapped[str] = mapped_column(String(64))
    params: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    progress: Mapped[int | None] = mapped_column(Integer)
    result_ref: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class LlmCall(Base, TimestampMixin):
    """One LLM invocation, logged with tokens, cost, and latency (NFR-015)."""

    __tablename__ = "llm_calls"

    id: Mapped[intpk]
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    # Attributes spend to a user for the per-user AI budget check (NFR-008, ADR-0022). Nullable:
    # embedding-batch calls (ingestion-time, no requesting user) never set it.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    purpose: Mapped[str | None] = mapped_column(String(64))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Money | None] = mapped_column()
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str | None] = mapped_column(String(16))


class RetrievalLog(Base, TimestampMixin):
    """One retrieval query, its intent, scores, and returned chunk IDs (RAG observability)."""

    __tablename__ = "retrieval_logs"

    id: Mapped[intpk]
    request_id: Mapped[str | None] = mapped_column(String(64), index=True)
    query: Mapped[str | None] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(32))
    top_k: Mapped[int | None] = mapped_column(Integer)
    scores: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    chunk_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))


class DataQualityIssue(Base, TimestampMixin):
    """A detected anomaly for a metric/period (DR-028)."""

    __tablename__ = "data_quality_issues"

    id: Mapped[intpk]
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    metric_name: Mapped[str | None] = mapped_column(String(64))
    period: Mapped[str | None] = mapped_column(String(32))
    issue_code: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(String(16))


class EvalRun(Base, TimestampMixin):
    """One evaluation run, pinned to a config hash and git sha (NFR gating, §18)."""

    __tablename__ = "eval_runs"

    id: Mapped[intpk]
    name: Mapped[str | None] = mapped_column(String(128))
    config_hash: Mapped[str | None] = mapped_column(String(64))
    git_sha: Mapped[str | None] = mapped_column(String(40))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str | None] = mapped_column(String(16))


class EvalResult(Base):
    """Per-question metrics within an eval run."""

    __tablename__ = "eval_results"

    id: Mapped[intpk]
    run_id: Mapped[int] = mapped_column(ForeignKey("eval_runs.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str | None] = mapped_column(String(64))
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class DataFreshness(Base):
    """Last success/attempt per company+source, driving fresh/stale/failed UI (FR-006)."""

    __tablename__ = "data_freshness"

    id: Mapped[intpk]
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(32))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str | None] = mapped_column(String(16))
    message: Mapped[str | None] = mapped_column(Text)
