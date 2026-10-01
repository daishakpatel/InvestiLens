"""Admin (internal) response schemas (spec §24.2)."""

from __future__ import annotations

from pydantic import BaseModel


class IngestionRunSummary(BaseModel):
    id: str
    source: str
    status: str | None = None
    started_at: str | None = None
    ended_at: str | None = None


class EvalRunSummary(BaseModel):
    id: str
    name: str | None = None
    status: str | None = None
    git_sha: str | None = None


class RefreshAccepted(BaseModel):
    ticker: str
    job_id: str
    status: str = "queued"
