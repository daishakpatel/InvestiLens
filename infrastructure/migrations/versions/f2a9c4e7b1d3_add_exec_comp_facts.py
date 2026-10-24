"""add exec_comp_facts

Phase 7g (FR-GV-005, ADR-0045): validated executive-compensation figures from proxy statements:
Pay-Versus-Performance XBRL facts, Summary Compensation Table cells and the CEO pay ratio. Unique
`(document_id, fiscal_year, fact_key, person)` NULLS NOT DISTINCT (`person` is NULL for
company-level facts), so a rebuild is a no-op.

Revision ID: f2a9c4e7b1d3
Revises: c3f8a1d2e9b7
Create Date: 2026-10-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a9c4e7b1d3"
down_revision: str | None = "c3f8a1d2e9b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exec_comp_facts",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("fact_key", sa.String(length=64), nullable=False),
        sa.Column("person", sa.String(length=256), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=True),
        sa.Column("value", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_exec_comp_facts_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_exec_comp_facts_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exec_comp_facts")),
        sa.UniqueConstraint(
            "document_id",
            "fiscal_year",
            "fact_key",
            "person",
            name="uq_exec_comp_facts_fact",
            postgresql_nulls_not_distinct=True,
        ),
    )
    op.create_index(
        "ix_exec_comp_facts_company_id_fiscal_year",
        "exec_comp_facts",
        ["company_id", "fiscal_year"],
    )


def downgrade() -> None:
    op.drop_index("ix_exec_comp_facts_company_id_fiscal_year", table_name="exec_comp_facts")
    op.drop_table("exec_comp_facts")
