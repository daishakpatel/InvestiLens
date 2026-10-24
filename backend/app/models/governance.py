"""Executive compensation facts from proxy statements (Phase 7g, FR-GV-004, ADR-0045)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, Quantity, intpk


class ExecCompFact(Base):
    """One validated figure from one proxy: a Pay-Versus-Performance XBRL fact (`tier` pvp), a
    Summary Compensation Table cell (`sct`, with the officer), or the CEO pay ratio (`pay_ratio`).

    Not a `financial_metrics` row: these describe a proxy year's pay, not the company's periods.
    Only figures that passed validation are stored; a missing one is absent, never zero.
    `person` is NULL for company-level facts, so the unique key treats NULLs as equal.
    """

    __tablename__ = "exec_comp_facts"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "fiscal_year",
            "fact_key",
            "person",
            name="uq_exec_comp_facts_fact",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_exec_comp_facts_company_id_fiscal_year", "company_id", "fiscal_year"),
    )

    id: Mapped[intpk]
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    fiscal_year: Mapped[int] = mapped_column()  # the year the figure covers, not the filing year
    tier: Mapped[str] = mapped_column(String(16))  # pvp | sct | pay_ratio
    fact_key: Mapped[str] = mapped_column(String(64))  # peo_total_comp, salary, total, ratio, …
    person: Mapped[str | None] = mapped_column(String(256))  # SCT name and position, as printed
    role: Mapped[str | None] = mapped_column(String(16))  # peo | pfo | neo (SCT rows)
    value: Mapped[Quantity] = mapped_column()
    unit: Mapped[str] = mapped_column(String(16))  # USD | pure | ratio_to_1
    source_id: Mapped[str] = mapped_column(String(128))  # xbrl:<fact_id> or a paragraph_id
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
