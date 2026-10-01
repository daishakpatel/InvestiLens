"""Cross-cutting API contract types (spec §24.1).

These carry the conventions every endpoint shares: RFC 7807 errors, cursor pagination, and
freshness metadata on data endpoints. They are contracts consumed by the frontend, so field
names and shapes are stable.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FreshnessStatus = Literal["fresh", "stale", "failed"]


class Problem(BaseModel):
    """RFC 7807 `application/problem+json` error body (API-001)."""

    type: str = Field(default="about:blank", description="URI identifying the problem type")
    title: str = Field(description="Short, human-readable summary")
    status: int = Field(description="HTTP status code")
    detail: str | None = Field(default=None, description="Explanation specific to this occurrence")
    instance: str | None = Field(default=None, description="URI of the specific occurrence")
    request_id: str | None = Field(default=None, description="Correlates with X-Request-ID")
    errors: list[FieldError] | None = Field(default=None, description="Per-field validation errors")


class FieldError(BaseModel):
    """One field-level validation error inside a `Problem`."""

    field: str
    message: str


class Freshness(BaseModel):
    """Data-freshness metadata attached to data endpoints (API-008, FR-006)."""

    as_of: str = Field(description="ISO-8601 UTC timestamp of the underlying data")
    source: str = Field(description="Provider or system that produced the data")
    freshness_status: FreshnessStatus


Problem.model_rebuild()
