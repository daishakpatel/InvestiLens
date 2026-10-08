"""llm_calls persistence (NFR-015).

One row per external model invocation — chat completions, report-section generation, AND
embedding batches — so cost, tokens, and latency are tracked in one place project-wide (EMB-002
reuses this pattern). This is also the single choke point that feeds the Prometheus LLM
cost/latency metrics (OBS-002/005, ADR-0021) and the per-user AI budget check (ADR-0022): every
caller that logs a call here gets both for free.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LlmCall
from app.observability.metrics import record_llm_call


def record_call(
    session: Session,
    *,
    purpose: str,
    model: str,
    input_tokens: int,
    latency_ms: int,
    cost_usd: Decimal,
    status: str,
    output_tokens: int | None = None,
    request_id: str | None = None,
    user_id: int | None = None,
    prompt_version: str | None = None,
) -> None:
    session.add(
        LlmCall(
            request_id=request_id,
            user_id=user_id,
            purpose=purpose,
            model=model,
            prompt_version=prompt_version,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
        )
    )
    record_llm_call(purpose=purpose, model=model, cost_usd=cost_usd, latency_ms=latency_ms)


def monthly_spend(session: Session, *, user_id: int, as_of: datetime | None = None) -> Decimal:
    """Sum of `cost_usd` for this user's LLM calls in the current calendar month (ADR-0022)."""
    as_of = as_of or datetime.now(UTC)
    month_start = as_of.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = session.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_usd), Decimal("0"))).where(
            LlmCall.user_id == user_id, LlmCall.created_at >= month_start
        )
    )
    return total if total is not None else Decimal("0")


def daily_spend(session: Session, *, as_of: datetime | None = None) -> Decimal:
    """Sum of `cost_usd` across every user/purpose today — feeds the `llm_spend_over_budget`
    alert (OBS-003), a global circuit-breaker signal distinct from the per-user budget."""
    as_of = as_of or datetime.now(UTC)
    day_start = as_of.replace(hour=0, minute=0, second=0, microsecond=0)
    total = session.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_usd), Decimal("0"))).where(
            LlmCall.created_at >= day_start
        )
    )
    return total if total is not None else Decimal("0")
