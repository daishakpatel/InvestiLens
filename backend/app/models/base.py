"""Declarative base, naming conventions, and shared column types for all models.

Every model in `app/models/` inherits from `Base`. Import the model modules through
`app.models` (see `app/models/__init__.py`) so `Base.metadata` is fully populated before
Alembic autogenerates or a test creates the schema.

Conventions (docs/conventions.md, spec §0, §23.4):
- Money is `NUMERIC(24,4)` (`Money`), never float (DB-003).
- Ratios / large derived values use a wider `NUMERIC` (`Quantity`) to keep precision.
- Timestamps are timezone-aware and stored in UTC.
- Fiscal-period fields are separate columns, never derived from calendar dates.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import BigInteger, DateTime, Identity, MetaData, Numeric, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint/index names → deterministic, reviewable Alembic migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Shared declarative base carrying the metadata + naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# --- Shared column type aliases -------------------------------------------------------

# BigInteger identity PK: room to grow (NFR-007) without a later type migration.
intpk = Annotated[int, mapped_column(BigInteger, Identity(), primary_key=True)]

# Monetary amounts in raw USD (DB-003). Display scaling ($M/$B) happens in the UI.
Money = Annotated[Decimal, mapped_column(Numeric(24, 4))]

# Ratios (0.1234 = 12.34%), share counts, and derived metrics needing wider precision.
Quantity = Annotated[Decimal, mapped_column(Numeric(28, 8))]


class TimestampMixin:
    """`created_at` set by the database on insert (UTC)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UpdatedAtMixin:
    """`updated_at` maintained by the ORM on insert and update (UTC)."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
