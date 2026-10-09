"""add notifications table

Phase 5d (§26.2, ADR-0025): durable in-app notification records produced by the alert-dispatch
job. `alert_id`/`company_id` are `ON DELETE SET NULL` so a notification outlives the rule or
company that produced it; `user_id` cascades with the account (SEC-014).

Revision ID: 8b0a53766648
Revises: 331b479d2be6
Create Date: 2026-10-08 21:06:05.529718
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8b0a53766648"
down_revision: str | None = "331b479d2be6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("alert_id", sa.BigInteger(), nullable=True),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("channel", sa.String(length=16), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"], ["alerts.id"],
            name=op.f("fk_notifications_alert_id_alerts"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name=op.f("fk_notifications_company_id_companies"), ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_notifications_user_id_users"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
