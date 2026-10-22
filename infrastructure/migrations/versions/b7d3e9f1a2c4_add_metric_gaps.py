"""add metric_gaps

Phase 7b (FR-QT-010, ADR-0040): one row per (company, metric, period) that a quarterly or TTM
metric is missing, with a reason code (`missing_ytd_2q`, `missing_fy`, `incomplete_window`, ...).
Rebuilt on every metrics run (delete-per-company + insert), so the table only ever describes the
latest build. `financial_metrics` itself needs no change: `period_type` already allows Q/TTM.

Revision ID: b7d3e9f1a2c4
Revises: e4a7c2d91b30
Create Date: 2026-10-21 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3e9f1a2c4"
down_revision: str | None = "e4a7c2d91b30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "metric_gaps",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column("period_label", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column(
            "detected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
            name=op.f("fk_metric_gaps_company_id_companies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metric_gaps")),
        sa.UniqueConstraint(
            "company_id",
            "metric",
            "period_label",
            name=op.f("uq_metric_gaps_company_id_metric_period_label"),
        ),
    )


def downgrade() -> None:
    op.drop_table("metric_gaps")
