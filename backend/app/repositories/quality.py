"""data_quality_issues persistence (DR-024, DR-028)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import DataQualityIssue


def record_issue(
    session: Session,
    *,
    company_id: int | None,
    metric_name: str | None,
    period: str | None,
    issue_code: str,
    details: dict[str, Any],
) -> None:
    session.add(
        DataQualityIssue(
            company_id=company_id,
            metric_name=metric_name,
            period=period,
            issue_code=issue_code,
            details=details,
            status="open",
        )
    )
