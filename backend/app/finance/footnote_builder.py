"""Persist footnote facts per fiscal year (Phase 7f, FR-FN-004..006, ADR-0044).

XBRL first, text last: every figure here is a tagged fact, never read from note text. For each
fiscal year, each footnote metric in the concept map is selected from companyfacts like any other
base value and stored as `xbrl:{TICKER}:{metric}:FY{yr}`. For the latest year only, a metric that
companyfacts lacks is then looked up in that year's 10-K inline XBRL, which keeps what
companyfacts drops: numeric durations (the lease term) and dimensioned facts. NVIDIA tags no
maturity ladder, only each note's principal and remaining term on `LongtermDebtTypeAxis`; its
ladder is the sum of the notes falling in each window, stored as derived rows whose lineage lists
every note. Whatever is still missing for the latest year is a `metric_gaps` row, never a zero.

Runs after the ratio builder: lease-adjusted debt adds the stored FY `total_debt`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance import metrics
from app.finance.concept_map import ConceptMap, load_concept_map
from app.finance.facts import fact_view_from_orm
from app.finance.ratio_builder import persist_derived
from app.finance.selection import FactView, select_metric
from app.ingestion.documents.ixbrl import IxValue, tagged_values
from app.models import Company, FinancialMetric
from app.repositories import facts as facts_repo
from app.repositories import filings as filing_repo
from app.repositories import gaps as gaps_repo
from app.repositories import metrics as metrics_repo
from app.schemas.sources import MetricInput, MetricResult
from app.utils.logging import get_logger, log_event
from app.utils.storage import get_object_storage

logger = get_logger(__name__)

FOOTNOTE_DERIVED = ("debt_due_within_2y_share", "lease_adjusted_debt")
NOT_TAGGED = "not_tagged"  # neither companyfacts nor the 10-K's inline XBRL has it
FILING_UNAVAILABLE = "filing_unavailable"  # the 10-K could not be read for inline XBRL
_DEBT_AXES = frozenset({"us-gaap:LongtermDebtTypeAxis", "us-gaap:DebtInstrumentAxis"})
_PRINCIPAL_TAGS = ("us-gaap:DebtInstrumentCarryingAmount", "us-gaap:DebtInstrumentFaceAmount")
# NVIDIA tags each note's "Expected Remaining Term (years)" column with this concept.
_TERM_TAG = "us-gaap:DebtInstrumentTerm"
_LADDER_FORMULA = (
    "sum of each note's principal (inline XBRL DebtInstrumentCarryingAmount per debt instrument) "
    "whose remaining term (DebtInstrumentTerm) falls in this window"
)
_FORMULAS = {
    "debt_due_within_2y_share": "(maturities in year 1 + year 2) / all scheduled maturities",
    "lease_adjusted_debt": "total debt + operating lease liabilities",
}

RawReader = Callable[[str], bytes]


@dataclass
class FootnoteCounts:
    rows: int = 0
    gaps: int = 0


@dataclass(frozen=True)
class Instrument:
    member: str  # the XBRL member naming the note ("nvda:A2026NotesMember")
    principal: Decimal
    years: Decimal  # remaining term


def ladder_bucket(years: Decimal) -> str:
    """The maturity window of a remaining term: up to 1 year is year 1, …, over 5 is after."""
    for index, name in enumerate(metrics.DEBT_MATURITY_BUCKETS[:-1], start=1):
        if years <= index:
            return name
    return metrics.DEBT_MATURITY_BUCKETS[-1]


def _debt_member(value: IxValue) -> str | None:
    members = value.context.members
    if len(members) != 1:
        return None
    axis, member = next(iter(members.items()))
    return member if axis in _DEBT_AXES else None


def instruments(values: Sequence[IxValue], period_end: date) -> list[Instrument]:
    """Each debt instrument with both a principal and a remaining term at `period_end`."""
    at_end = [v for v in values if v.context.period_end == period_end and _debt_member(v)]
    terms = {_debt_member(v): v.value for v in at_end if v.concept == _TERM_TAG}
    principal: dict[str, Decimal] = {}
    for tag in _PRINCIPAL_TAGS:
        for value in at_end:
            member = _debt_member(value)
            if value.concept == tag and member in terms and member is not None:
                principal.setdefault(member, value.value)
    return [
        Instrument(member, amount, terms[member]) for member, amount in sorted(principal.items())
    ]


def inline_value(
    values: Sequence[IxValue], tags: Sequence[str], period_end: date
) -> tuple[str, Decimal] | None:
    """First tag with an undimensioned fact at `period_end` (an instant or a period's end)."""
    for tag in tags:
        for value in values:
            if (
                value.concept == tag
                and not value.context.members
                and value.context.period_end == period_end
            ):
                return tag, value.value
    return None


class _Writer:
    def __init__(self, session: Session, company: Company, cmap: ConceptMap) -> None:
        self.session = session
        self.company = company
        self.cmap = cmap
        self.counts = FootnoteCounts()

    def fact(
        self,
        metric: str,
        fy: int,
        fye: date,
        value: Decimal,
        *,
        tag: str,
        accession: str,
        inline: bool = False,
    ) -> str:
        source_id = f"xbrl:{self.company.ticker}:{metric}:FY{fy}"
        flags: dict[str, str] = {"note_category": self.cmap.footnote_metrics[metric]}
        if inline:
            flags["source"] = "inline_xbrl"
        metrics_repo.upsert_metric(
            self.session,
            company_id=self.company.id,
            period=f"FY{fy}",
            fiscal_year=fy,
            fiscal_quarter=None,
            period_start=None,
            period_end=fye,
            period_type="FY",
            metric_name=metric,
            metric_value=value,
            unit=self.cmap.footnote_unit(metric),
            source_tag=tag,
            source_id=source_id,
            as_reported_accession=accession,
            is_latest=True,
            quality_flags=flags,
        )
        self.counts.rows += 1
        return source_id

    def derived(self, fy: int, result: MetricResult, *, formula: str, category: str) -> str:
        persist_derived(
            self.session,
            self.company.id,
            self.company.ticker,
            fy,
            result,
            extra={"derived": formula, "note_category": category},
        )
        self.counts.rows += 1
        return f"derived:{self.company.ticker}:{result.formula_id}:FY{fy}"


def _fiscal_year_ends(session: Session, company_id: int) -> dict[int, date]:
    """Fiscal year -> year-end date, from the FY base rows the annual builder wrote."""
    rows = session.execute(
        select(FinancialMetric.fiscal_year, FinancialMetric.period_end).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.period_type == "FY",
            FinancialMetric.is_derived.is_(False),
            FinancialMetric.period_end.is_not(None),
        )
    )
    ends: dict[int, date] = {}
    for fy, end in rows:
        if fy is not None and end is not None and end > ends.get(fy, date.min):
            ends[fy] = end
    return ends


def _total_debt(session: Session, company_id: int) -> dict[int, FinancialMetric]:
    rows = session.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.metric_name == "total_debt",
            FinancialMetric.period_type == "FY",
            FinancialMetric.is_latest.is_(True),
            FinancialMetric.metric_value.is_not(None),
        )
    )
    return {row.fiscal_year: row for row in rows if row.fiscal_year is not None}


def _inline_values(
    session: Session, company: Company, fye: date, read_raw: RawReader
) -> tuple[list[IxValue], str] | None:
    """The fiscal year's 10-K inline XBRL and its accession, or None if it cannot be read."""
    filing = filing_repo.get_annual_report(session, company_id=company.id, period_end=fye)
    if filing is None or not filing.raw_document_location:
        return None
    try:
        raw = read_raw(filing.raw_document_location)
    except Exception as exc:  # degrade to gaps, surfaced in the API (never fail the build)
        log_event(
            logger,
            logging.WARNING,
            "footnotes.inline_unavailable",
            ticker=company.ticker,
            accession=filing.accession_number,
            error=str(exc),
        )
        return None
    return tagged_values(raw.decode("utf-8", errors="ignore")), filing.accession_number


def _latest_year_fallbacks(
    writer: _Writer,
    found: dict[str, tuple[Decimal, str]],
    *,
    fy: int,
    fye: date,
    read_raw: RawReader,
) -> str:
    """Fill the latest year's missing metrics from inline XBRL. Returns the gap reason left."""
    cmap = writer.cmap
    missing = [m for m in cmap.footnote_metrics if m not in found]
    inline = _inline_values(writer.session, writer.company, fye, read_raw)
    if inline is None:
        return FILING_UNAVAILABLE
    values, accession = inline
    for metric in missing:
        hit = inline_value(values, cmap.tags(metric), fye)
        if hit is not None:
            tag, value = hit
            sid = writer.fact(metric, fy, fye, value, tag=tag, accession=accession, inline=True)
            found[metric] = (value, sid)
    if any(bucket in found for bucket in metrics.DEBT_MATURITY_BUCKETS):
        return NOT_TAGGED
    notes = instruments(values, fye)
    for bucket in metrics.DEBT_MATURITY_BUCKETS if notes else ():
        window = [n for n in notes if ladder_bucket(n.years) == bucket]
        result = MetricResult(
            value=sum((n.principal for n in window), Decimal(0)),  # 0 = no note matures then
            unit=metrics.USD,
            inputs=[
                MetricInput(name=f"{n.member} ({n.years} years remaining)", value=n.principal)
                for n in window
            ],
            formula_id=bucket,
            formula_version=metrics.FORMULA_VERSION,
        )
        sid = writer.derived(fy, result, formula=_LADDER_FORMULA, category="debt")
        found[bucket] = (result.value or Decimal(0), sid)
    return NOT_TAGGED


def build_company_footnotes(
    session: Session, company: Company, *, read_raw: RawReader | None = None
) -> FootnoteCounts:
    """Persist footnote facts, the two derived footnote metrics, and the latest year's gaps."""
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    facts: list[FactView] = [
        fact_view_from_orm(f) for f in facts_repo.facts_for_company(session, company.id)
    ]
    reader = read_raw or get_object_storage().get
    own = [*cmap.footnote_metrics, *FOOTNOTE_DERIVED]
    metrics_repo.clear_company_metric_names(
        session, company.id, own
    )  # a re-run leaves no stale row
    writer = _Writer(session, company, cmap)
    debt = _total_debt(session, company.id)
    years = _fiscal_year_ends(session, company.id)
    latest = max(years, default=None)
    gaps: list[tuple[str, str, str]] = []

    for fy, fye in sorted(years.items()):
        found: dict[str, tuple[Decimal, str]] = {}
        for metric in cmap.footnote_metrics:
            selection = select_metric(facts, cmap, metric, period_end=fye)
            if selection is not None:
                sid = writer.fact(
                    metric,
                    fy,
                    fye,
                    selection.value,
                    tag=selection.source_tag,
                    accession=selection.accession_number,
                )
                found[metric] = (selection.value, sid)
        reason = NOT_TAGGED
        if fy == latest:
            reason = _latest_year_fallbacks(writer, found, fy=fy, fye=fye, read_raw=reader)

        total = debt.get(fy)
        lease = found.get("operating_lease_liability")
        lease_sources = {"total_debt": total.source_id} if total and total.source_id else {}
        if lease is not None:
            lease_sources["operating_lease_liability"] = lease[1]
        ladder = {m: found[m] for m in metrics.DEBT_MATURITY_BUCKETS if m in found}
        results = {
            "debt_due_within_2y_share": metrics.debt_due_within_2y_share(
                {m: v for m, (v, _) in ladder.items()},
                sources={m: sid for m, (_, sid) in ladder.items()},
            ),
            "lease_adjusted_debt": metrics.lease_adjusted_debt(
                total.metric_value if total else None,
                lease[0] if lease else None,
                sources=lease_sources,
            ),
        }
        for name, result in results.items():
            if result.value is not None:
                category = "debt" if name == "debt_due_within_2y_share" else "leases"
                writer.derived(fy, result, formula=_FORMULAS[name], category=category)
            elif fy == latest:
                gaps.append((name, f"FY{fy}", metrics.MISSING_INPUT))
        if fy == latest:
            gaps.extend((m, f"FY{fy}", reason) for m in cmap.footnote_metrics if m not in found)

    writer.counts.gaps = gaps_repo.replace_metric_gaps(session, company.id, own, gaps)
    return writer.counts
