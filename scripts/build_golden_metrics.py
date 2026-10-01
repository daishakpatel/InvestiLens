"""Derive hand-verifiable golden metrics from the frozen XBRL companyfacts (Phase 0d).

Extracts revenue, net income, diluted EPS, and gross margin for each seed company's latest
fiscal year (10-K), straight from the authoritative XBRL facts. Values are exact-match targets
used by tests through Phase 1c. Money is kept as strings to preserve Decimal precision.

Gross margin is N/A for banks (JPM): no GrossProfit / CostOfRevenue XBRL concepts exist, which
is exactly the DR-001 sector-applicability edge case JPM is included to exercise.

Usage:  uv run python scripts/build_golden_metrics.py
"""

from __future__ import annotations

import gzip
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"
TICKERS = ("nvda", "aapl", "jpm")

REVENUE_CONCEPTS = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues")
GROSS_PROFIT_CONCEPTS = ("GrossProfit",)
COST_CONCEPTS = ("CostOfRevenue", "CostOfGoodsAndServicesSold")


def _load_facts(ticker: str) -> dict:
    with gzip.open(FIXTURES / ticker / "companyfacts.json.gz") as fh:
        raw = fh.read()
    return json.loads(raw)["facts"]["us-gaap"]


def _annual_fact(facts: dict, concepts: tuple[str, ...], accession: str, unit: str) -> dict | None:
    """Return the full-year fact for the given 10-K accession, trying each concept in order."""
    for concept in concepts:
        node = facts.get(concept)
        if not node or unit not in node["units"]:
            continue
        candidates = [
            f
            for f in node["units"][unit]
            if f.get("form") == "10-K"
            and f.get("accn") == accession
            and f.get("start")
            and 330 <= (date.fromisoformat(f["end"]) - date.fromisoformat(f["start"])).days <= 400
        ]
        if candidates:
            return max(candidates, key=lambda f: f["end"])  # latest full year in that filing
    return None


def _build_company(ticker: str) -> dict:
    manifest = json.loads((FIXTURES / ticker / "filings_manifest.json").read_text())
    tenk = next(f for f in manifest["filings"] if f["form"] == "10-K")
    accession = tenk["accession_number"]
    facts = _load_facts(ticker)

    revenue = _annual_fact(facts, REVENUE_CONCEPTS, accession, "USD")
    net_income = _annual_fact(facts, ("NetIncomeLoss",), accession, "USD")
    eps = _annual_fact(facts, ("EarningsPerShareDiluted",), accession, "USD/shares")
    gross_profit = _annual_fact(facts, GROSS_PROFIT_CONCEPTS, accession, "USD")
    cost = _annual_fact(facts, COST_CONCEPTS, accession, "USD")

    if revenue is None or net_income is None:
        raise RuntimeError(f"{ticker}: missing revenue/net income in {accession}")

    # Gross margin: prefer reported GrossProfit; else revenue - cost; else N/A (banks, DR-001).
    gross_margin: str | None
    gross_margin_note: str
    rev = Decimal(str(revenue["val"]))
    if gross_profit is not None:
        gross_margin = str((Decimal(str(gross_profit["val"])) / rev).quantize(Decimal("0.0001")))
        gross_margin_note = "GrossProfit / Revenue"
    elif cost is not None:
        gm = (rev - Decimal(str(cost["val"]))) / rev
        gross_margin = str(gm.quantize(Decimal("0.0001")))
        gross_margin_note = "(Revenue - CostOfRevenue) / Revenue"
    else:
        gross_margin = None
        gross_margin_note = "NOT_APPLICABLE_SECTOR (no gross profit/cost concept — financials)"

    return {
        "ticker": ticker.upper(),
        "fiscal_year_end": revenue["end"],
        "accession_number": accession,
        "source": f"XBRL companyfacts, 10-K {tenk['filing_date']}",
        "metrics": {
            "revenue": {
                "value": str(revenue["val"]),
                "unit": "USD",
                "concept": _concept_of(facts, REVENUE_CONCEPTS, accession, "USD"),
            },
            "net_income": {
                "value": str(net_income["val"]),
                "unit": "USD",
                "concept": "NetIncomeLoss",
            },
            "eps_diluted": {
                "value": str(eps["val"]) if eps else None,
                "unit": "USD/shares",
                "concept": "EarningsPerShareDiluted",
            },
            "gross_margin": {"value": gross_margin, "unit": "ratio", "note": gross_margin_note},
        },
    }


def _concept_of(facts: dict, concepts: tuple[str, ...], accession: str, unit: str) -> str:
    for concept in concepts:
        if _annual_fact(facts, (concept,), accession, unit) is not None:
            return concept
    return concepts[0]


def main() -> None:
    output = {
        "_comment": "Hand-verifiable golden metrics from frozen XBRL (Phase 0d, DR-029).",
        "companies": [_build_company(t) for t in TICKERS],
    }
    path = FIXTURES / "golden_metrics.json"
    path.write_text(json.dumps(output, indent=2) + "\n")
    for company in output["companies"]:
        m = company["metrics"]
        print(
            f"{company['ticker']:5} FY{company['fiscal_year_end']} "
            f"rev={m['revenue']['value']} ni={m['net_income']['value']} "
            f"eps={m['eps_diluted']['value']} gm={m['gross_margin']['value']}"
        )
    print("Wrote", path)


if __name__ == "__main__":
    main()
