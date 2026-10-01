"""llm_calls persistence (NFR-015).

One row per external model invocation — chat completions AND embedding batches — so cost,
tokens, and latency are tracked in one place project-wide (EMB-002 reuses this pattern).
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import LlmCall


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
) -> None:
    session.add(
        LlmCall(
            request_id=request_id,
            purpose=purpose,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            status=status,
        )
    )
