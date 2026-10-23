"""add red_flags

Phase 7e (FR-RF-006, ADR-0043): one row per red-flag rule that fired on a filing under one
taxonomy version. Unique `(company_id, rule_key, taxonomy_version, filing_id, paragraph_id)` with
NULLS NOT DISTINCT (Postgres 15+), because `paragraph_id` is NULL for flags that quote no chunk:
re-running detection is a no-op, a new taxonomy version adds rows.

Revision ID: c3f8a1d2e9b7
Revises: b7d3e9f1a2c4
Create Date: 2026-10-22 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3f8a1d2e9b7"
down_revision: str | None = "b7d3e9f1a2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "red_flags",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_key", sa.String(length=64), nullable=False),
        sa.Column("taxonomy_version", sa.String(length=32), nullable=False),
        sa.Column("filing_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("paragraph_id", sa.String(length=64), nullable=True),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_red_flags_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["filing_id"],
            ["filings.id"],
            name=op.f("fk_red_flags_filing_id_filings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_red_flags_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_red_flags")),
        sa.UniqueConstraint(
            "company_id",
            "rule_key",
            "taxonomy_version",
            "filing_id",
            "paragraph_id",
            # Explicit: the generated name would exceed Postgres's 63-character limit.
            name="uq_red_flags_event",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_red_flags_company_id_event_date", "red_flags", ["company_id", "event_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_red_flags_company_id_event_date", table_name="red_flags")
    op.drop_table("red_flags")
