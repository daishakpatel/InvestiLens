"""Aggregated risk themes across a portfolio's holdings (§37.2).

Each holding's cited risk factors come from its latest completed research report (Phase 3b,
`report_json.risks`). We group them by the report's fixed risk taxonomy and surface categories
shared across holdings — every contribution keeps its own `source_ids`, so a theme stays fully
cited back to each company's filing. No report means no fabricated risk: the holding simply does
not contribute, and that gap is noted by the caller.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.portfolio.weights import NormalizedWeight
from app.repositories import companies as company_repo
from app.repositories import reports as report_repo
from app.schemas.portfolio import HoldingContribution, RiskTheme


def aggregate_themes(
    session: Session, weights: list[NormalizedWeight]
) -> tuple[list[RiskTheme], list[str]]:
    """Group holdings' cited risks by category. Returns (themes, holdings-without-a-report)."""
    by_category: dict[str, list[tuple[str, HoldingContribution]]] = {}
    category_weight: dict[str, Decimal] = {}
    missing: list[str] = []

    for w in weights:
        company = company_repo.get_by_ticker(session, w.ticker)
        if company is None:
            missing.append(w.ticker)
            continue
        report = report_repo.get_latest_complete(session, company_id=company.id)
        risks = (report.report_json or {}).get("risks", []) if report else []
        if not report or not risks:
            missing.append(w.ticker)
            continue
        seen_categories: set[str] = set()
        for risk in risks:
            category = str(risk.get("category") or "uncategorized")
            contribution = HoldingContribution(
                ticker=w.ticker,
                description=str(risk.get("description") or ""),
                source_ids=[str(s) for s in risk.get("source_ids", [])],
            )
            by_category.setdefault(category, []).append((w.ticker, contribution))
            if category not in seen_categories:  # count each holding's weight once per category
                category_weight[category] = category_weight.get(category, Decimal(0)) + w.weight
                seen_categories.add(category)

    themes: list[RiskTheme] = []
    for category, contributions in by_category.items():
        holders = {ticker for ticker, _ in contributions}
        themes.append(
            RiskTheme(
                category=category,
                holding_count=len(holders),
                portfolio_weight=category_weight.get(category, Decimal(0)),
                contributions=[c for _, c in contributions],
            )
        )
    # Most-shared, highest-weight themes first.
    themes.sort(key=lambda t: (-t.holding_count, -t.portfolio_weight, t.category))
    return themes, missing
