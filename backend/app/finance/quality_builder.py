"""Persist earnings-quality measures per fiscal year (Phase 7d, FR-EQ-008, ADR-0042).

Runs after the ratio and valuation builders, because Altman's original Z needs the fiscal-year-end
market cap and FCF conversion needs the stored free cash flow. Every measure is a derived FY row
(`derived:{TICKER}:{metric}:FY{yr}`) in the ratio record format: `formula_id`, and
`quality_flags.inputs` with the source ID of every figure used, so the citation drawer can open
each one. Score-specific details (band, Beneish indices, Altman model variant, Piotroski
criteria) sit beside the lineage in `quality_flags`.

Uncomputable is NULL plus a reason code, never zero (DR-041); not applicable for the sector is
NULL plus NOT_APPLICABLE_SECTOR (DR-042, DR-EQ-001). A year without its predecessor gets
MISSING_INPUT rows for the two-year measures, so the gap is visible rather than absent.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.finance import beneish, metrics
from app.finance.concept_map import ConceptMap, load_concept_map
from app.finance.ratio_builder import Canonical, persist_derived
from app.finance.sic import is_manufacturer
from app.finance.valuation_builder import load_splits, split_factor
from app.models import Company, FinancialFact, FinancialMetric
from app.schemas.sources import MetricInput, MetricResult

# Stored metric names, in dashboard order (the API and UI read this list).
QUALITY_METRICS = (
    "accruals_ratio",
    "accruals_ratio_bs",
    "fcf_conversion",
    "dso",
    "dio",
    "dpo",
    "cash_conversion_cycle",
    "dilution",
    "beneish_m",
    "altman_z",
    "piotroski_f",
)


def _not_applicable(formula_id: str, unit: str) -> MetricResult:
    return MetricResult(
        value=None,
        unit=unit,
        formula_id=formula_id,
        formula_version=metrics.FORMULA_VERSION,
        warnings=[metrics.NOT_APPLICABLE_SECTOR],
    )


def _average(a: Decimal | None, b: Decimal | None) -> Decimal | None:
    return None if a is None or b is None else (a + b) / 2


def _with_inputs(result: MetricResult, extra: list[MetricInput]) -> MetricResult:
    """Add the raw figures behind a computed input (an average) to the lineage (CIT-003)."""
    return result.model_copy(update={"inputs": [*result.inputs, *extra]})


def altman_variant(sic_code: str | None) -> tuple[metrics.AltmanVariant, str]:
    """The Altman model for this company and why: original Z for SIC 20-39 manufacturers, Z''
    otherwise (FR-EQ-006). Recorded on every row; never picked silently."""
    manufacturer = is_manufacturer(sic_code)
    if manufacturer:
        return "original", f"SIC {sic_code}: manufacturer, original Z (market equity)"
    if manufacturer is None:
        return "z_double_prime", "no SIC code: non-manufacturer Z'' (book equity)"
    return "z_double_prime", f"SIC {sic_code}: non-manufacturer, Z'' (book equity)"


class _Year:
    """Readers over the canonical values for fiscal year `fy` and its predecessor."""

    def __init__(self, canonical: Canonical, fy: int) -> None:
        self.c = canonical
        self.fy = fy

    def v(self, metric: str, prior: bool = False) -> Decimal | None:
        return self.c.value(self.fy - 1 if prior else self.fy, metric)

    def s(self, metric: str, prior: bool = False) -> str | None:
        return self.c.source(self.fy - 1 if prior else self.fy, metric)

    def current(self, **names: str) -> dict[str, str]:
        """Year-t source IDs keyed by input name: `current(ebit="operating_income")`."""
        return {key: sid for key, metric in names.items() if (sid := self.s(metric))}

    def sources(self, *names: str) -> dict[str, str]:
        """Source IDs keyed `name` (year t) and `prior_name` (t-1), as year-pair inputs use."""
        out: dict[str, str] = {}
        for name in names:
            for prior, key in ((False, name), (True, f"prior_{name}")):
                found = self.s(name, prior)
                if found:
                    out[key] = found
        return out

    def raw(self, metric: str) -> list[MetricInput]:
        """Both years' figures of a balance that was averaged."""
        return [
            MetricInput(name=metric, value=self.v(metric), source_id=self.s(metric)),
            MetricInput(
                name=f"prior_{metric}", value=self.v(metric, True), source_id=self.s(metric, True)
            ),
        ]


def _days(
    y: _Year, cmap: ConceptMap, name: str, balance: str, flow: str, fn: Callable[..., MetricResult]
) -> MetricResult:
    if not cmap.applies(name):
        return _not_applicable(name, metrics.DAYS)
    avg = _average(y.v(balance), y.v(balance, True))
    result = fn(avg, y.v(flow), sources=y.current(**{flow: flow}))
    return _with_inputs(result, y.raw(balance))


_SHARES = "shares_diluted_weighted"


@dataclass(frozen=True)
class _PriorShares:
    """Year t-1's diluted shares on year t's share basis, with where that basis comes from."""

    value: Decimal | None
    source_id: str | None
    basis: dict[str, str]


def _prior_shares(
    y: _Year,
    comparatives: dict[int, tuple[Decimal | None, str | None]],
    splits: list[tuple[date, Decimal]],
    year_end: dict[int, date],
) -> _PriorShares:
    """The prior year's count as year t's own 10-K restates it (the filer has applied any split),
    else the as-reported count moved across the splits we hold. Without either, a split year
    would read as dilution (NVIDIA's 4:1 in 2021 and 10:1 in 2024)."""
    if y.fy in comparatives:
        value, source = comparatives[y.fy]
        return _PriorShares(value, source, {"prior_shares_basis": f"restated in the FY{y.fy} 10-K"})
    prior = y.v(_SHARES, True)
    start, end = year_end.get(y.fy - 1), year_end.get(y.fy)
    factor = split_factor(splits, start, end) if start and end else Decimal(1)
    return _PriorShares(
        prior * factor if prior is not None else None,
        y.s(_SHARES, True),
        {"prior_shares_basis": "as reported, split-adjusted", "split_factor": str(factor)},
    )


def _comparative_shares(
    session: Session, company_id: int
) -> dict[int, tuple[Decimal | None, str | None]]:
    """Year t-1's diluted shares as reported in year t's 10-K, keyed by t, citing the raw fact."""
    rows = session.scalars(
        select(FinancialMetric).where(
            FinancialMetric.company_id == company_id,
            FinancialMetric.metric_name == _SHARES,
            FinancialMetric.period_type == "FY",
        )
    ).all()
    filed_in = {r.fiscal_year: r.as_reported_accession for r in rows if r.is_latest}
    restated = [
        r
        for r in rows
        if r.fiscal_year is not None
        and r.metric_value is not None
        and r.as_reported_accession is not None
        and filed_in.get(r.fiscal_year + 1) == r.as_reported_accession
    ]
    facts = session.execute(
        select(
            FinancialFact.id,
            FinancialFact.accession_number,
            FinancialFact.concept_tag,
            FinancialFact.period_start,
            FinancialFact.period_end,
        ).where(
            FinancialFact.company_id == company_id,
            FinancialFact.accession_number.in_({r.as_reported_accession for r in restated}),
            FinancialFact.concept_tag.in_({r.source_tag for r in restated}),
        )
    ).all()
    fact_ids: dict[tuple[str | None, str | None, date | None, date | None], int] = {
        (acc, tag, start, end): fid for fid, acc, tag, start, end in facts
    }
    out: dict[int, tuple[Decimal | None, str | None]] = {}
    for r in restated:
        fid = fact_ids.get((r.as_reported_accession, r.source_tag, r.period_start, r.period_end))
        out[(r.fiscal_year or 0) + 1] = (
            r.metric_value,
            f"xbrl:{fid}" if fid is not None else None,
        )
    return out


def _dilution(y: _Year, prior: _PriorShares) -> MetricResult:
    """Diluted weighted shares, t vs t-1, both on year t's share basis."""
    sources = y.current(current_shares=_SHARES)
    if prior.source_id is not None:
        sources["prior_shares"] = prior.source_id
    return metrics.dilution(y.v(_SHARES), prior.value, sources=sources)


def _beneish_year(y: _Year, prior: bool) -> beneish.BeneishYear:
    return beneish.BeneishYear(
        **{name: y.v(name, prior) for name in beneish.BeneishYear.__dataclass_fields__}
    )


def _piotroski_year(y: _Year, prior: _PriorShares | None) -> metrics.YearFinancials:
    """Year t (`prior` None) or t-1, whose shares are restated onto year t's basis."""
    values = {
        name: y.v(name, prior is not None)
        for name in metrics.YearFinancials.__dataclass_fields__
        if name != "shares_diluted"
    }
    shares = prior.value if prior is not None else y.v(_SHARES)
    return metrics.YearFinancials(**values, shares_diluted=shares)


def _operating_balances(y: _Year, prior: bool) -> metrics.OperatingBalances:
    return metrics.OperatingBalances(
        **{name: y.v(name, prior) for name in metrics.OperatingBalances.__dataclass_fields__}
    )


def _compute_year(
    y: _Year,
    cmap: ConceptMap,
    company: Company,
    splits: list[tuple[date, Decimal]],
    year_end: dict[int, date],
    comparatives: dict[int, tuple[Decimal | None, str | None]],
) -> list[tuple[str, MetricResult, dict[str, Any]]]:
    """Every quality measure for one fiscal year: (stored name, result, extra quality flags)."""
    out: list[tuple[str, MetricResult, dict[str, Any]]] = []

    accruals = metrics.accruals_ratio(
        y.v("net_income"),
        y.v("operating_cash_flow"),
        _average(y.v("total_assets"), y.v("total_assets", True)),
        sources=y.current(net_income="net_income", operating_cash_flow="operating_cash_flow"),
    )
    out.append(("accruals_ratio", _with_inputs(accruals, y.raw("total_assets")), {}))
    balances = tuple(metrics.OperatingBalances.__dataclass_fields__)
    out.append(
        (
            "accruals_ratio_bs",
            metrics.accruals_ratio_balance_sheet(
                _operating_balances(y, False),
                _operating_balances(y, True),
                applicable=cmap.applies("accruals_ratio_bs"),
                sources=y.sources(*balances),
            ),
            {},
        )
    )
    out.append(
        (
            "fcf_conversion",
            metrics.fcf_conversion(
                y.v("free_cash_flow"),
                y.v("net_income"),
                sources=y.current(free_cash_flow="free_cash_flow", net_income="net_income"),
            ),
            {},
        )
    )

    days = {
        "dso": _days(y, cmap, "dso", "receivables", "revenue", metrics.dso),
        "dio": _days(y, cmap, "dio", "inventory", "cost_of_revenue", metrics.dio),
        "dpo": _days(y, cmap, "dpo", "payables", "cost_of_revenue", metrics.dpo),
    }
    out.extend((name, result, {}) for name, result in days.items())
    if cmap.applies("cash_conversion_cycle"):
        ccc = metrics.cash_conversion_cycle(
            days["dso"].value,
            days["dio"].value,
            days["dpo"].value,
            sources={n: f"derived:{company.ticker}:{n}:FY{y.fy}" for n in days},
        )
    else:
        ccc = _not_applicable("cash_conversion_cycle", metrics.DAYS)
    out.append(("cash_conversion_cycle", ccc, {}))

    prior_shares = _prior_shares(y, comparatives, splits, year_end)
    out.append(("dilution", _dilution(y, prior_shares), prior_shares.basis))

    score = beneish.beneish_m_score(
        _beneish_year(y, False),
        _beneish_year(y, True),
        applicable=cmap.applies("beneish"),
        sources=y.sources(*beneish.BeneishYear.__dataclass_fields__),
    )
    out.append(
        (
            "beneish_m",
            score.metric,
            {
                "band": score.band,
                "threshold": str(beneish.THRESHOLD),
                "indices": {k: None if v is None else str(v) for k, v in score.indices.items()},
                "missing": score.missing,
            },
        )
    )

    out.append(_altman(y, cmap, company))

    current, prior = _piotroski_year(y, None), _piotroski_year(y, prior_shares)
    piotroski_sources = y.sources(*metrics.YearFinancials.__dataclass_fields__)
    piotroski_sources |= y.current(shares_diluted=_SHARES)
    if prior_shares.source_id is not None:
        piotroski_sources["prior_shares_diluted"] = prior_shares.source_id
    applies = cmap.applies("piotroski")
    criteria = metrics.piotroski_criteria(current, prior) if applies else {}
    out.append(
        (
            "piotroski_f",
            metrics.piotroski_f_score(
                current, prior, applicable=applies, sources=piotroski_sources
            ),
            {
                "criteria": criteria,
                "computable": sum(1 for passed in criteria.values() if passed is not None),
            },
        )
    )
    return out


def _altman(
    y: _Year, cmap: ConceptMap, company: Company
) -> tuple[str, MetricResult, dict[str, Any]]:
    variant, basis = altman_variant(company.sic_code)
    original = variant == "original"
    ca, cl = y.v("current_assets"), y.v("current_liabilities")
    working_capital = None if ca is None or cl is None else ca - cl
    equity = "market_cap" if original else "shareholders_equity"
    named = {
        "retained_earnings": "retained_earnings",
        "ebit": "operating_income",
        "total_assets": "total_assets",
        ("market_value_equity" if original else "book_value_equity"): equity,
        "total_liabilities": "total_liabilities",
        "sales": "revenue",
    }
    sources = y.current(**named)
    result = metrics.altman_z_score(
        working_capital,
        y.v("retained_earnings"),
        y.v("operating_income"),
        y.v("total_assets"),
        y.v(equity),
        y.v("total_liabilities"),
        y.v("revenue") if original else None,
        variant=variant,
        applicable=cmap.applies("altman"),
        sources=sources,
    )
    result = _with_inputs(
        result,
        [
            MetricInput(name="current_assets", value=ca, source_id=y.s("current_assets")),
            MetricInput(name="current_liabilities", value=cl, source_id=y.s("current_liabilities")),
        ],
    )
    zone = metrics.altman_zone(result.value, variant) if result.value is not None else None
    return "altman_z", result, {"band": zone, "model_variant": variant, "variant_basis": basis}


def build_company_earnings_quality(session: Session, company: Company) -> int:
    """Compute and persist every earnings-quality measure per fiscal year. Returns rows written."""
    cmap = load_concept_map(ticker=company.ticker, cik=company.cik, sector=company.sector)
    rows = list(
        session.scalars(
            select(FinancialMetric).where(
                FinancialMetric.company_id == company.id,
                FinancialMetric.period_type == "FY",
                FinancialMetric.is_latest.is_(True),
            )
        )
    )
    canonical = Canonical(rows)
    year_end: dict[int, date] = {}
    for row in rows:
        if not row.is_derived and row.fiscal_year is not None and row.period_end is not None:
            year_end[row.fiscal_year] = max(
                row.period_end, year_end.get(row.fiscal_year, row.period_end)
            )
    splits = load_splits(session, company.id)
    comparatives = _comparative_shares(session, company.id)
    written = 0
    for fy in sorted(year_end):
        for name, result, extra in _compute_year(
            _Year(canonical, fy), cmap, company, splits, year_end, comparatives
        ):
            persist_derived(session, company.id, company.ticker, fy, result, name=name, extra=extra)
            written += 1
    return written
