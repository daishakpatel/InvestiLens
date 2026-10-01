"""add embedding_dim and embedding_new staging column

Phase 2b (EMB-001, EMB-003, ADR-0013):
- `embedding_dim` records the vector dimension per row alongside `embedding_model`, so a corpus
  can hold rows embedded under different models and re-embedding stays safe.
- `embedding_new` is a staging column: a new model backfills here while `embedding` keeps serving
  reads, then an atomic swap promotes it — a zero-downtime model migration path.

Revision ID: 8c58e66dbdbc
Revises: 7ce7bee338f7
Create Date: 2026-10-01 18:40:46.322849
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "8c58e66dbdbc"
down_revision: str | None = "7ce7bee338f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("embedding_dim", sa.Integer(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("embedding_new", pgvector.sqlalchemy.Vector(dim=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "embedding_new")
    op.drop_column("document_chunks", "embedding_dim")
