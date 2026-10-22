"""alert framework v2: per-alert watermark, typed rules, idempotent notifications

Phase 7a (FR-AL-005..009, ADR-0039). `alerts` moves to the registry shape (`event_type`,
`params`, `channels`, `enabled`, nullable `company_id` = watchlist-wide) and gains `created_at` +
`watermark_at`. Existing rows get `watermark_at = now()` (not their creation time) so deploying
does not replay history. The three per-form filing types fold into `new_filing` with a
`form_types` param. `notifications` gains `event_key` + `payload` and a unique
`(alert_id, event_key)`, the idempotency guard for overlapping or retried dispatch runs.

Downgrade is lossy where v2 is richer: watchlist-wide alerts are deleted (v1 needs a company), a
multi-form `new_filing` keeps only its first form, and only the first channel survives.

Revision ID: e4a7c2d91b30
Revises: 8b0a53766648
Create Date: 2026-10-21 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e4a7c2d91b30"
down_revision: str | None = "8b0a53766648"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("alerts", "alert_type", new_column_name="event_type", type_=sa.String(64))
    op.alter_column("alerts", "is_active", new_column_name="enabled", server_default=sa.true())
    op.alter_column("alerts", "company_id", nullable=True)
    op.execute("UPDATE alerts SET config = '{}'::jsonb WHERE config IS NULL")
    op.alter_column(
        "alerts",
        "config",
        new_column_name="params",
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        existing_type=postgresql.JSONB(),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "channels",
            postgresql.ARRAY(sa.String(16)),
            server_default=sa.text("'{in_app}'"),
            nullable=False,
        ),
    )
    op.execute("UPDATE alerts SET channels = ARRAY[channel]::varchar(16)[]")
    op.drop_column("alerts", "channel")
    op.drop_column("alerts", "last_triggered_at")
    for column in ("created_at", "watermark_at"):
        op.add_column(
            "alerts",
            sa.Column(
                column,
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
    op.execute(
        "UPDATE alerts SET event_type = 'new_filing', params = jsonb_build_object("
        "'form_types', jsonb_build_array(CASE event_type WHEN 'new_10k' THEN '10-K' "
        "WHEN 'new_10q' THEN '10-Q' ELSE '8-K' END)) "
        "WHERE event_type IN ('new_10k', 'new_10q', 'new_8k')"
    )

    op.add_column("notifications", sa.Column("event_key", sa.String(256), nullable=True))
    op.add_column("notifications", sa.Column("payload", postgresql.JSONB(), nullable=True))
    op.create_unique_constraint(
        op.f("uq_notifications_alert_id_event_key"), "notifications", ["alert_id", "event_key"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_notifications_alert_id_event_key"), "notifications", type_="unique")
    op.drop_column("notifications", "payload")
    op.drop_column("notifications", "event_key")

    op.execute("DELETE FROM alerts WHERE company_id IS NULL")
    op.execute(
        "UPDATE alerts SET event_type = CASE params->'form_types'->>0 WHEN '10-K' THEN 'new_10k' "
        "WHEN '10-Q' THEN 'new_10q' ELSE 'new_8k' END, params = '{}'::jsonb "
        "WHERE event_type = 'new_filing'"
    )
    op.drop_column("alerts", "watermark_at")
    op.drop_column("alerts", "created_at")
    op.add_column(
        "alerts", sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "alerts",
        sa.Column("channel", sa.String(16), server_default="in_app", nullable=False),
    )
    op.execute("UPDATE alerts SET channel = channels[1]")
    op.alter_column("alerts", "channel", server_default=None)
    op.drop_column("alerts", "channels")
    # Events no longer fit the old 32-char column; v1 never stored anything longer.
    op.execute("DELETE FROM alerts WHERE length(event_type) > 32")
    op.alter_column(
        "alerts",
        "params",
        new_column_name="config",
        nullable=True,
        server_default=None,
        existing_type=postgresql.JSONB(),
    )
    op.alter_column("alerts", "company_id", nullable=False)
    op.alter_column("alerts", "enabled", new_column_name="is_active", server_default=None)
    op.alter_column("alerts", "event_type", new_column_name="alert_type", type_=sa.String(32))
