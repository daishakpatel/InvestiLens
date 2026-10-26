"""Keep theses current when their company's data changes (FR-TH-007/008).

`refresh_company_theses` is the one hook the jobs call after metrics are rebuilt, after a red-flag
scan and after a brief is stored. It is idempotent and never polls:
- **Links.** It links each red flag (7e) and each quarter's first preview or brief (7j) that
  arrived after a thesis was written. These links are informational and never change a KPI's
  state.
- **Evaluation.** It re-evaluates the KPIs of every active thesis on the company.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.earnings.alerts import KIND_LABEL
from app.earnings.calendar import label
from app.models import Company, Thesis
from app.redflags import taxonomy
from app.repositories import theses as repo
from app.thesis.evaluator import evaluate_theses


def _links(session: Session, company: Company, thesis: Thesis) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for flag, filing in repo.flags_since(
        session, company.id, taxonomy.TAXONOMY_VERSION, thesis.created_at
    ):
        rule = taxonomy.RULES_BY_KEY.get(flag.rule_key)
        rows.append(
            {
                "thesis_id": thesis.id,
                "kind": "red_flag",
                "occurred_at": flag.detected_at,
                "ref_type": "red_flag",
                "ref_id": taxonomy.source_id(
                    company.ticker, flag.rule_key, filing.accession_number
                ),
                "payload": {"label": rule.label if rule else flag.rule_key},
            }
        )
    for brief in repo.first_briefs_since(session, company.id, thesis.created_at):
        period = label((brief.fiscal_year, brief.fiscal_period))
        rows.append(
            {
                "thesis_id": thesis.id,
                "kind": "brief_published",
                "occurred_at": brief.created_at,
                "ref_type": "earnings_brief",
                "ref_id": f"earnings_brief:{brief.id}",
                "payload": {"label": f"{KIND_LABEL[brief.kind]} for {period}"},
            }
        )
    return rows


def refresh_company_theses(session: Session, company: Company) -> int:
    """Link new evidence and re-evaluate KPIs for every active thesis on `company`. Returns the
    number of timeline events added."""
    theses = repo.active_for_company(session, company.id)
    if not theses:
        return 0
    linked = repo.link_events(session, [row for t in theses for row in _links(session, company, t)])
    return linked + len(evaluate_theses(session, company, theses))
