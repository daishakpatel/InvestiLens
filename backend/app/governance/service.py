"""Read side of the Governance view (Phase 7g, FR-GV-011). No model is called here."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.api.filings import to_summary
from app.config import get_settings
from app.footnotes.summary import model_label
from app.governance import facts as tier_c
from app.ingestion.documents.chunker import PARSER_VERSION
from app.ingestion.documents.proxy_sections import SECTION_KEYS
from app.models import Company, Document, ExecCompFact, Filing
from app.repositories import governance as repo
from app.schemas.governance import (
    BoardFacts,
    Compensation,
    CompensationRow,
    GovernanceField,
    GovernanceHistoryPoint,
    GovernanceHistoryResponse,
    GovernanceResponse,
    PayRatio,
    PayVersusPerformance,
    PayVersusPerformancePoint,
)

_LABELS = {
    "board_size": "Board size",
    "independent_directors": "Independent directors",
    "ceo_chair_combined": "CEO is also board chair",
    "lead_independent_director": "Lead independent director",
    "classified_board": "Classified (staggered) board",
    "dual_class": "Dual-class shares",
    "say_on_pay_support_pct": "Say-on-pay support (%)",
    "committees": "Board committees",
}
_PAY_RATIO_REASONS = {
    "no_ceo_total": "No validated CEO total in this proxy to check a pay ratio against.",
    "not_validated": "No disclosed pay ratio matched median pay x ratio within 2% of the CEO's "
    "total, so none is shown.",
}
NO_PROXY = "No DEF 14A proxy statement has been processed for this company yet."


def _proxies(session: Session, company: Company) -> list[tuple[Filing, Document, dict[str, Any]]]:
    """Processed DEF 14A proxies tied to a fiscal year, newest year first, one per year."""
    out: dict[int, tuple[Filing, Document, dict[str, Any]]] = {}
    for filing, document in repo.proxy_filings(session, company.id, parser_version=PARSER_VERSION):
        info = (document.doc_metadata or {}).get("proxy") or {}
        year = info.get("fiscal_year")
        if filing.filing_type == "DEF 14A" and isinstance(year, int):
            out.setdefault(year, (filing, document, info))  # newest filing wins (amended reissue)
    return [out[y] for y in sorted(out, reverse=True)]


def _board(document: Document) -> BoardFacts:
    cached = tier_c.cached_facts(document, model_label(get_settings()))
    if cached is None:
        return BoardFacts(status="pending", reason="Not extracted yet.")
    if cached.get("no_evidence"):
        return BoardFacts(
            status="no_sections", reason="No paragraph about the board was found in this proxy."
        )
    fields = cached.get("fields", {})
    return BoardFacts(
        status="extracted",
        model=cached.get("model"),
        fields=[
            GovernanceField(name=name, label=_LABELS[name], **(fields.get(name) or {}))
            for name in tier_c.FIELDS
        ],
        independence_ratio=tier_c.independence_ratio(fields),
    )


def _compensation(rows: list[ExecCompFact], info: dict[str, Any]) -> Compensation:
    grouped: dict[tuple[str, int], dict[str, ExecCompFact]] = defaultdict(dict)
    for row in rows:
        if row.tier == "sct" and row.person is not None:
            grouped[(row.person, row.fiscal_year)][row.fact_key] = row
    rejected = len(info.get("sct_rejected", []))
    out = [
        CompensationRow(
            person=person,
            role=cells["total"].role or "neo",  # type: ignore[arg-type]
            fiscal_year=year,
            components={k: c.value for k, c in cells.items() if k != "total"},
            total=cells["total"].value,
            source_id=cells["total"].source_id,
        )
        for (person, year), cells in grouped.items()
        if "total" in cells
    ]
    out.sort(key=lambda r: (["peo", "pfo", "neo"].index(r.role), r.person, -r.fiscal_year))
    reason = None
    if not out:
        reason = (
            "The Summary Compensation Table was found, but no row added up to its total, so "
            "none is shown."
            if rejected
            else "No Summary Compensation Table was found in this proxy."
        )
    return Compensation(rows=out, rejected_rows=rejected, reason=reason)


def _pvp(rows: list[ExecCompFact], info: dict[str, Any]) -> PayVersusPerformance:
    by_year: dict[int, PayVersusPerformancePoint] = {}
    for row in rows:
        if row.tier == "pvp":
            point = by_year.setdefault(
                row.fiscal_year,
                PayVersusPerformancePoint(fiscal_year=row.fiscal_year, values={}, source_ids={}),
            )
            point.values[row.fact_key] = row.value
            point.source_ids[row.fact_key] = row.source_id
    return PayVersusPerformance(
        points=[by_year[y] for y in sorted(by_year)],
        company_selected_measure=info.get("company_selected_measure"),
        reason=None if by_year else "This proxy has no Pay Versus Performance XBRL facts.",
    )


def _pay_ratio(rows: list[ExecCompFact], info: dict[str, Any], fiscal_year: int) -> PayRatio:
    found = {r.fact_key: r for r in rows if r.tier == "pay_ratio" and r.fiscal_year == fiscal_year}
    if "ratio" not in found:
        status = info.get("pay_ratio_status", "no_ceo_total")
        return PayRatio(reason=_PAY_RATIO_REASONS.get(status, _PAY_RATIO_REASONS["no_ceo_total"]))
    ceo = next(
        (
            r.value
            for r in rows
            if r.tier == "sct" and r.role == "peo" and r.fact_key == "total"
            and r.fiscal_year == fiscal_year
        ),
        None,
    )  # fmt: skip
    return PayRatio(
        ratio=found["ratio"].value,
        median_pay=found["median_pay"].value,
        ceo_total=ceo,
        source_id=found["ratio"].source_id,
    )


def governance(
    session: Session, company: Company, fiscal_year: int | None = None
) -> GovernanceResponse | None:
    """The proxy for `fiscal_year` (default the latest); None if that year has no proxy."""
    proxies = _proxies(session, company)
    ingested = sum(
        1
        for filing, _ in repo.proxy_filings(session, company.id, parser_version=PARSER_VERSION)
        if filing.filing_type == "DEF 14A"
    )
    years = [info["fiscal_year"] for _, _, info in proxies]
    if not proxies:
        return GovernanceResponse(
            company_ticker=company.ticker,
            fiscal_year=None,
            fiscal_year_source=None,
            filing=None,
            available_years=[],
            proxies_ingested=ingested,
            reason=NO_PROXY,
        )
    chosen = next((p for p in proxies if p[2]["fiscal_year"] == fiscal_year), None)
    if fiscal_year is None:
        chosen = proxies[0]
    if chosen is None:
        return None
    filing, document, info = chosen
    year = int(info["fiscal_year"])
    rows = [r for r in repo.facts_for_company(session, company.id) if r.document_id == document.id]
    sections = set((document.doc_metadata or {}).get("proxy_sections", []))
    return GovernanceResponse(
        company_ticker=company.ticker,
        fiscal_year=year,
        fiscal_year_source=info.get("fiscal_year_source"),
        filing=to_summary(filing),
        available_years=years,
        proxies_ingested=ingested,
        coverage={key: key in sections for key in SECTION_KEYS},
        facts=_board(document),
        compensation=_compensation(rows, info),
        pay_vs_performance=_pvp(rows, info),
        pay_ratio=_pay_ratio(rows, info, year),
    )


def history(session: Session, company: Company) -> GovernanceHistoryResponse:
    """CEO total pay per fiscal year (each year from the newest proxy that reports it: the
    Summary Compensation Table, else Pay Versus Performance) and each proxy's independence ratio."""
    proxies = _proxies(session, company)
    rank = {document.id: i for i, (_, document, _) in enumerate(proxies)}  # 0 = newest
    pay: dict[int, tuple[tuple[int, int], ExecCompFact]] = {}
    for row in repo.facts_for_company(session, company.id):
        is_sct = row.tier == "sct" and row.role == "peo" and row.fact_key == "total"
        is_pvp = row.tier == "pvp" and row.fact_key == "peo_total_comp"
        if row.document_id not in rank or not (is_sct or is_pvp):
            continue
        priority = (0 if is_sct else 1, rank[row.document_id])
        if row.fiscal_year not in pay or priority < pay[row.fiscal_year][0]:
            pay[row.fiscal_year] = (priority, row)
    model = model_label(get_settings())
    ratios: dict[int, Decimal | None] = {}
    for _, document, info in proxies:
        cached = tier_c.cached_facts(document, model)
        ratios[info["fiscal_year"]] = (
            tier_c.independence_ratio(cached["fields"]) if cached else None
        )
    points = []
    for year in sorted(set(pay) | set(ratios)):
        chosen = pay.get(year)
        best = chosen[1] if chosen else None
        points.append(
            GovernanceHistoryPoint(
                fiscal_year=year,
                ceo_total_pay=best.value if best else None,
                ceo_total_pay_source=(
                    None
                    if best is None
                    else "summary_compensation_table"
                    if best.tier == "sct"
                    else "pay_versus_performance"
                ),
                ceo_total_pay_source_id=best.source_id if best else None,
                independence_ratio=ratios.get(year),
            )
        )
    return GovernanceHistoryResponse(company_ticker=company.ticker, points=points)
