"""add peer_sets, peer_set_members, valuation_history

Phase 7h (FR-PS-001/009, ADR-0046): explicit peer sets (the deterministic system default per
company, and users' private sets) with a rationale per member, and each valuation multiple at
each fiscal year end and the latest close, computed only from facts filed by that date.

Revision ID: a6d2f8c3e5b1
Revises: f2a9c4e7b1d3
Create Date: 2026-10-24 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6d2f8c3e5b1"
down_revision: str | None = "f2a9c4e7b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _fk(table: str, column: str, target: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        [f"{target}.id"],
        name=op.f(f"fk_{table}_{column}_{target}"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "peer_sets",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _fk("peer_sets", "owner_user_id", "users"),
        _fk("peer_sets", "company_id", "companies"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_peer_sets")),
    )
    op.create_index(
        "ix_peer_sets_company_id_owner_user_id", "peer_sets", ["company_id", "owner_user_id"]
    )
    op.create_table(
        "peer_set_members",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("peer_set_id", sa.BigInteger(), nullable=False),
        sa.Column("peer_company_id", sa.BigInteger(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        _fk("peer_set_members", "peer_set_id", "peer_sets"),
        _fk("peer_set_members", "peer_company_id", "companies"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_peer_set_members")),
        sa.UniqueConstraint(
            "peer_set_id", "peer_company_id", name=op.f("uq_peer_set_members_peer_set_id_peer_company_id")
        ),
    )
    op.create_table(
        "valuation_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("multiple", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _fk("valuation_history", "company_id", "companies"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_valuation_history")),
        sa.UniqueConstraint(
            "company_id",
            "as_of_date",
            "multiple",
            name=op.f("uq_valuation_history_company_id_as_of_date_multiple"),
        ),
    )


def downgrade() -> None:
    op.drop_table("valuation_history")
    op.drop_table("peer_set_members")
    op.drop_index("ix_peer_sets_company_id_owner_user_id", table_name="peer_sets")
    op.drop_table("peer_sets")
