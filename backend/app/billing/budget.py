"""Per-user AI budget enforcement (NFR-008, SEC-008, ADR-0022).

`users.ai_budget_month_usd` existed since Phase 4b but was never enforced. `check_budget` is
called once, right before the LLM-cost-incurring path in chat (qualitative synthesis only —
deterministic metric answers are free) and research report generation, so a user who has spent
through their monthly cap gets a clear `402` instead of silently running up more spend.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import User
from app.repositories import llm_calls as llm_repo


class BudgetExceededError(Exception):
    """Raised when a user's monthly AI spend has reached their budget cap (→ RFC 7807 402)."""

    status_code = 402

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def check_budget(session: Session, user: User, *, settings: Settings | None = None) -> None:
    """Raise `BudgetExceededError` if `user`'s spend this calendar month is at/over their cap.

    A `NULL` `ai_budget_month_usd` means unlimited (an explicit operator override, never set by
    `register` — see `default_ai_budget_month_usd`); such users are never blocked.
    """
    settings = settings or get_settings()
    cap = user.ai_budget_month_usd
    if cap is None:
        return
    spent = llm_repo.monthly_spend(session, user_id=user.id)
    if spent >= cap:
        raise BudgetExceededError(
            f"Monthly AI budget of ${cap} reached (${spent} spent). "
            "It resets at the start of next month."
        )
