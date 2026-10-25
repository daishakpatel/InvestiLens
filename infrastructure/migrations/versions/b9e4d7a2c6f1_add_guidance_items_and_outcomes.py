"""add guidance_items, guidance_outcomes

Phase 7i (FR-GD-001/002, ADR-0047): numbers a company guided to, each quoted from its own
earnings release (verified rows are shown; rejected rows keep the reason, for audit), and each
verified item's outcome against the reported actual. A verified row holds a single value or a
full range (CHECK `one_value_form`); revisions chain through `superseded_by`.

Revision ID: b9e4d7a2c6f1
Revises: a6d2f8c3e5b1
Create Date: 2026-10-24 16:44:40.468533
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9e4d7a2c6f1"
down_revision: str | None = "a6d2f8c3e5b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guidance_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("source_document_id", sa.BigInteger(), nullable=False),
        sa.Column("paragraph_id", sa.String(length=64), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=4), nullable=True),
        sa.Column("metric", sa.String(length=32), nullable=False),
        sa.Column("low", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("high", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("point", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("unit", sa.String(length=24), nullable=True),
        sa.Column("basis", sa.String(length=16), nullable=True),
        sa.Column("derived_range", sa.Boolean(), nullable=False),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("period_text", sa.Text(), nullable=True),
        sa.Column("confidence_state", sa.String(length=16), nullable=False),
        sa.Column("rejection_reason", sa.String(length=64), nullable=True),
        sa.Column("superseded_by", sa.BigInteger(), nullable=True),
        sa.Column("taxonomy_version", sa.String(length=32), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_guidance_items_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_document_id"],
            ["documents.id"],
            name=op.f("fk_guidance_items_source_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["superseded_by"],
            ["guidance_items.id"],
            name=op.f("fk_guidance_items_superseded_by_guidance_items"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "confidence_state <> 'verified' OR "
            "((point IS NOT NULL) <> (low IS NOT NULL AND high IS NOT NULL))",
            name=op.f("ck_guidance_items_one_value_form"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_guidance_items")),
    )
    op.create_index(
        "ix_guidance_items_company_id_fiscal_year",
        "guidance_items",
        ["company_id", "fiscal_year"],
        unique=False,
    )
    op.create_index(
        "ix_guidance_items_source_document_id",
        "guidance_items",
        ["source_document_id"],
        unique=False,
    )
    op.create_table(
        "guidance_outcomes",
        sa.Column("guidance_id", sa.BigInteger(), nullable=False),
        sa.Column("actual_value", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column(
            "actual_source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("delta_vs_low", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("delta_vs_high", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("delta_vs_mid", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("delta_vs_mid_pct", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column("result", sa.String(length=24), nullable=False),
        sa.Column("reason_code", sa.String(length=32), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["guidance_id"],
            ["guidance_items.id"],
            name=op.f("fk_guidance_outcomes_guidance_id_guidance_items"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "result IN ('above_range', 'within_range', 'below_range', 'not_comparable', "
            "'actual_unavailable')",
            name=op.f("ck_guidance_outcomes_result_known"),
        ),
        sa.PrimaryKeyConstraint("guidance_id", name=op.f("pk_guidance_outcomes")),
    )


def downgrade() -> None:
    op.drop_table("guidance_outcomes")
    op.drop_index("ix_guidance_items_source_document_id", table_name="guidance_items")
    op.drop_index("ix_guidance_items_company_id_fiscal_year", table_name="guidance_items")
    op.drop_table("guidance_items")
