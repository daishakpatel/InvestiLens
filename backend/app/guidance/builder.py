"""Chain revisions and compute every verified guidance item's outcome (FR-GD-007..010).

Deterministic and idempotent: run after the metrics build (actuals may have arrived or been
restated) and after extraction (new guidance). Outcomes cite the same `financial_metrics` source
IDs the rest of the app does, so the actual opens its own evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.guidance import outcomes
from app.guidance.taxonomy import actual_inputs
from app.models import Company, GuidanceItem
from app.repositories import guidance as repo


def guided(item: GuidanceItem) -> outcomes.Guided:
    return outcomes.Guided(
        metric=item.metric,
        basis=item.basis or "unspecified",
        unit=item.unit or "usd",
        low=item.low,
        high=item.high,
        point=item.point,
    )


def outcome_row(guidance_id: int, outcome: outcomes.Outcome, at: datetime) -> dict[str, Any]:
    return {
        "guidance_id": guidance_id,
        "actual_value": outcome.actual.value if outcome.actual else None,
        "actual_source_ids": list(outcome.actual.source_ids) if outcome.actual else [],
        "delta_vs_low": outcome.delta_vs_low,
        "delta_vs_high": outcome.delta_vs_high,
        "delta_vs_mid": outcome.delta_vs_mid,
        "delta_vs_mid_pct": outcome.delta_vs_mid_pct,
        "result": outcome.result,
        "reason_code": outcome.reason_code,
        "computed_at": at,
    }


def build_company_guidance(session: Session, company: Company) -> int:
    """Revision chain and outcomes for every verified item. Returns the number of items."""
    items = repo.verified_items(session, company.id)
    with_period = [i for i in items if i.fiscal_year is not None and i.fiscal_period]
    repo.set_superseded(
        session,
        outcomes.revision_chain(
            [
                outcomes.Issued(
                    i.id,
                    (i.fiscal_year or 0, i.fiscal_period or "", i.metric, i.basis or ""),
                    i.issued_at,
                )
                for i in with_period
            ]
        ),
    )
    actuals = repo.actual_rows(
        session,
        company.id,
        {(i.fiscal_year or 0, i.fiscal_period or "") for i in with_period},
        actual_inputs(),
    )
    now = datetime.now(UTC)
    rows = []
    for item in with_period:
        period_rows = actuals.get((item.fiscal_year or 0, item.fiscal_period or ""), {})
        actual = outcomes.actual_for(item.metric, item.unit or "usd", period_rows)
        rows.append(outcome_row(item.id, outcomes.compute_outcome(guided(item), actual), now))
    repo.upsert_outcomes(session, rows)
    return len(with_period)
