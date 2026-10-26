"""add earnings_events, earnings_briefs

Phase 7j (FR-EB-001/007, ADR-0048): each fiscal quarter's earnings report date with where it came
from (an Item 2.02 8-K, the company's own announcement, or an estimate shown as one), and stored
pre-earnings previews / post-earnings briefs, versioned by a hash of their inputs so the same
inputs return the stored row and changed inputs add a version while the old one is kept.

Revision ID: f186174c8045
Revises: b9e4d7a2c6f1
Create Date: 2026-10-24 22:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f186174c8045"
down_revision: str | None = "b9e4d7a2c6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "earnings_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(length=4), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=True),
        sa.Column("report_time", sa.String(length=8), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("quote", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_earnings_events_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "status IN ('scheduled', 'reported', 'unknown')",
            name=op.f("ck_earnings_events_status_known"),
        ),
        sa.CheckConstraint(
            "source IN ('sec_8k', 'announcement', 'estimated')",
            name=op.f("ck_earnings_events_source_known"),
        ),
        sa.CheckConstraint(
            "report_time IN ('bmo', 'amc', 'unknown')",
            name=op.f("ck_earnings_events_report_time_known"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_earnings_events")),
        sa.UniqueConstraint(
            "company_id", "fiscal_year", "fiscal_period", name="uq_earnings_events_period"
        ),
    )
    op.create_table(
        "earnings_briefs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sa.String(length=4), nullable=False),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.Column("inputs_label", sa.Text(), nullable=False),
        sa.Column("report_date_estimated", sa.Boolean(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_earnings_briefs_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "kind IN ('preview', 'brief')", name=op.f("ck_earnings_briefs_kind_known")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_earnings_briefs")),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "kind",
            "inputs_hash",
            name="uq_earnings_briefs_inputs",
        ),
        sa.UniqueConstraint(
            "company_id",
            "fiscal_year",
            "fiscal_period",
            "kind",
            "version",
            name="uq_earnings_briefs_version",
        ),
    )


def downgrade() -> None:
    op.drop_table("earnings_briefs")
    op.drop_table("earnings_events")
