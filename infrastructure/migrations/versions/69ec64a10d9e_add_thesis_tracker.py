"""add theses, thesis_kpis, thesis_events, thesis_revisions

Phase 7k (FR-TH-001/004, SEC-TH-001, ADR-0049): a user's written thesis on a company, its
measurable KPIs (current state on the row), an append-only timeline (KPI transitions, linked red
flags and briefs, notes, status changes) and every saved revision. All rows hang off
`theses.user_id` with ON DELETE CASCADE, so deleting a thesis or the user removes them.

Revision ID: 69ec64a10d9e
Revises: f186174c8045
Create Date: 2026-10-25 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "69ec64a10d9e"
down_revision: str | None = "f186174c8045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def _id() -> sa.Column[int]:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False)


def upgrade() -> None:
    op.create_table(
        "theses",
        _id(),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("stance", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_theses_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_theses_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "stance IN ('long', 'short', 'watch', 'avoid')", name=op.f("ck_theses_stance_known")
        ),
        sa.CheckConstraint("status IN ('active', 'closed')", name=op.f("ck_theses_status_known")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_theses")),
    )
    op.create_index("ix_theses_user_id_status", "theses", ["user_id", "status"])
    op.create_index("ix_theses_company_id", "theses", ["company_id"])

    op.create_table(
        "thesis_kpis",
        _id(),
        sa.Column("thesis_id", sa.BigInteger(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("period_type", sa.String(length=8), nullable=False),
        sa.Column("comparator", sa.String(length=4), nullable=False),
        sa.Column("threshold", sa.Numeric(precision=28, scale=8), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=8), nullable=False),
        sa.Column("last_value", sa.Numeric(precision=28, scale=8), nullable=True),
        sa.Column(
            "last_source_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("last_period", sa.String(length=32), nullable=True),
        sa.Column("last_period_end", sa.Date(), nullable=True),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["thesis_id"],
            ["theses.id"],
            name=op.f("fk_thesis_kpis_thesis_id_theses"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "comparator IN ('gte', 'lte', 'gt', 'lt')",
            name=op.f("ck_thesis_kpis_comparator_known"),
        ),
        sa.CheckConstraint(
            "state IN ('met', 'broken', 'no_data')", name=op.f("ck_thesis_kpis_state_known")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_thesis_kpis")),
    )
    op.create_index("ix_thesis_kpis_thesis_id", "thesis_kpis", ["thesis_id"])

    op.create_table(
        "thesis_events",
        _id(),
        sa.Column("thesis_id", sa.BigInteger(), nullable=False),
        sa.Column("kpi_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("ref_type", sa.String(length=24), nullable=True),
        sa.Column("ref_id", sa.String(length=160), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thesis_id"],
            ["theses.id"],
            name=op.f("fk_thesis_events_thesis_id_theses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["kpi_id"],
            ["thesis_kpis.id"],
            name=op.f("fk_thesis_events_kpi_id_thesis_kpis"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            "kind IN ('kpi_met', 'kpi_broken', 'red_flag', 'brief_published', 'user_note', "
            "'status_changed')",
            name=op.f("ck_thesis_events_kind_known"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_thesis_events")),
    )
    op.create_index(
        "ix_thesis_events_thesis_id_occurred_at", "thesis_events", ["thesis_id", "occurred_at"]
    )
    op.create_index(
        "uq_thesis_events_link",
        "thesis_events",
        ["thesis_id", "kind", "ref_id"],
        unique=True,
        postgresql_where=sa.text("kind IN ('red_flag', 'brief_published')"),
    )

    op.create_table(
        "thesis_revisions",
        sa.Column("thesis_id", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.ForeignKeyConstraint(
            ["thesis_id"],
            ["theses.id"],
            name=op.f("fk_thesis_revisions_thesis_id_theses"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("thesis_id", "revision", name=op.f("pk_thesis_revisions")),
    )


def downgrade() -> None:
    op.drop_table("thesis_revisions")
    op.drop_index("uq_thesis_events_link", table_name="thesis_events")
    op.drop_index("ix_thesis_events_thesis_id_occurred_at", table_name="thesis_events")
    op.drop_table("thesis_events")
    op.drop_index("ix_thesis_kpis_thesis_id", table_name="thesis_kpis")
    op.drop_table("thesis_kpis")
    op.drop_index("ix_theses_company_id", table_name="theses")
    op.drop_index("ix_theses_user_id_status", table_name="theses")
    op.drop_table("theses")
