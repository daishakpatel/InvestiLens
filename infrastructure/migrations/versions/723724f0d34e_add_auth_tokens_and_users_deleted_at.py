"""add auth_tokens and users.deleted_at

Phase 4b (AUTH-003, LGL-007):
- `auth_tokens` holds single-use, hashed email-verification / password-reset tokens (only the
  SHA-256 hash is stored; the raw token is delivered to the user and never persisted).
- `users.deleted_at` is the soft-delete marker set by `DELETE /auth/me`; a hard-delete job later
  purges the row (retention, LGL-007).

Revision ID: 723724f0d34e
Revises: 8c58e66dbdbc
Create Date: 2026-10-02 23:21:08.226157
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "723724f0d34e"
down_revision: str | None = "8c58e66dbdbc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_tokens_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_tokens_token_hash")),
    )
    op.create_index(op.f("ix_auth_tokens_user_id"), "auth_tokens", ["user_id"], unique=False)
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "deleted_at")
    op.drop_index(op.f("ix_auth_tokens_user_id"), table_name="auth_tokens")
    op.drop_table("auth_tokens")
