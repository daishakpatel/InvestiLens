"""add llm_calls.user_id

Phase 5c (NFR-008, ADR-0022): attributes each LLM call to the requesting user so
`app.repositories.llm_calls.monthly_spend` can enforce the per-user AI budget. Nullable —
embedding-batch calls (ingestion-time, no requesting user) never set it.

Revision ID: 331b479d2be6
Revises: 723724f0d34e
Create Date: 2026-10-07 21:52:22.444772
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "331b479d2be6"
down_revision: str | None = "723724f0d34e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("llm_calls", sa.Column("user_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_llm_calls_user_id"), "llm_calls", ["user_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_llm_calls_user_id_users"),
        "llm_calls",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_llm_calls_user_id_users"), "llm_calls", type_="foreignkey")
    op.drop_index(op.f("ix_llm_calls_user_id"), table_name="llm_calls")
    op.drop_column("llm_calls", "user_id")
