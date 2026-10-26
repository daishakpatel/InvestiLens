"""Thesis use cases behind the API (FR-TH-001..014). The caller has already proved ownership:
every function here takes a thesis that `repo.owned` returned for the signed-in user.

Thesis text is never logged (SEC-TH-002): log lines carry ids and counts only.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.filings.diff import word_diff
from app.models import Company, Thesis, ThesisEvent, ThesisKpi
from app.repositories import companies as company_repo
from app.repositories import theses as repo
from app.schemas.filings import DiffOp
from app.schemas.thesis import (
    Kpi,
    KpiCreate,
    KpiPoint,
    KpiUpdate,
    MetricRegistryEntry,
    MetricRegistryResponse,
    StateCounts,
    ThesisCreate,
    ThesisDetail,
    ThesisRevision,
    ThesisSummary,
    ThesisUpdate,
)
from app.schemas.thesis import ThesisEvent as EventOut
from app.thesis import registry
from app.thesis.evaluator import evaluate_kpi
from app.utils.logging import get_logger, log_event

logger = get_logger(__name__)

MAX_ACTIVE_THESES = 20
MAX_KPIS = 10
HISTORY_POINTS = 12


@dataclass
class ThesisError(Exception):
    """A request the rules refuse; `field` set for a 422 on one input."""

    status: int
    title: str
    detail: str
    field: str | None = None


def company_for(session: Session, ticker: str) -> Company:
    company = company_repo.get_by_ticker(session, ticker.upper())
    if company is None:
        raise ThesisError(404, "Not Found", f"Unknown ticker {ticker!r}.", "body.ticker")
    return company


def validate_kpi(
    company: Company, metric_key: str, period_type: str, threshold: Decimal
) -> registry.TrackedMetric:
    """The registry entry, or a 422 naming the input at fault (FR-TH-002/005/006)."""
    metric = registry.BY_KEY.get(metric_key)
    if metric is None:
        raise ThesisError(
            422, "Unknown metric", f"{metric_key!r} is not a trackable metric.", "body.metric"
        )
    if period_type not in metric.period_types:
        allowed = ", ".join(metric.period_types)
        raise ThesisError(
            422,
            "Unsupported period",
            f"{metric.label} is tracked for {allowed}, not {period_type}.",
            "body.period_type",
        )
    if not registry.applicable(metric, company):
        raise ThesisError(
            422,
            "Metric not applicable",
            f"{metric.label} is not applicable to {company.ticker}'s sector.",
            "body.metric",
        )
    mistake = metric.plausible(threshold)
    if mistake:
        raise ThesisError(422, "Threshold looks like a unit mistake", mistake, "body.threshold")
    return metric


def _company(session: Session, thesis: Thesis) -> Company:
    company = session.get(Company, thesis.company_id)
    if company is None:  # cannot happen: the FK cascades a company's theses away
        raise LookupError(f"thesis {thesis.id} has no company")
    return company


def create(session: Session, user_id: int, body: ThesisCreate) -> Thesis:
    company = company_for(session, body.ticker)
    if repo.count_active(session, user_id) >= MAX_ACTIVE_THESES:
        raise ThesisError(
            409, "Too many theses", f"Close a thesis first: at most {MAX_ACTIVE_THESES} active."
        )
    thesis = Thesis(
        user_id=user_id,
        company_id=company.id,
        title=body.title,
        body_md=body.body_md,
        stance=body.stance,
        status="active",
    )
    session.add(thesis)
    session.flush()
    repo.add_revision(session, thesis)
    log_event(logger, logging.INFO, "thesis.created", thesis_id=thesis.id)
    return thesis


def update(session: Session, thesis: Thesis, body: ThesisUpdate) -> Thesis:
    """Apply an edit. A new title or body adds a revision (edits never overwrite); a status
    change is logged on the timeline."""
    reopening = body.status == "active" and thesis.status != "active"
    if reopening and repo.count_active(session, thesis.user_id) >= MAX_ACTIVE_THESES:
        raise ThesisError(409, "Too many theses", "At most 20 theses can be active.")
    text_changed = (body.title is not None and body.title != thesis.title) or (
        body.body_md is not None and body.body_md != thesis.body_md
    )
    if body.title is not None:
        thesis.title = body.title
    if body.body_md is not None:
        thesis.body_md = body.body_md
    if body.stance is not None:
        thesis.stance = body.stance
    if body.status is not None and body.status != thesis.status:
        session.add(
            ThesisEvent(
                thesis_id=thesis.id,
                kind="status_changed",
                payload={"from": thesis.status, "to": body.status},
            )
        )
        thesis.status = body.status
    session.flush()
    if text_changed:
        repo.add_revision(session, thesis)
    return thesis


def add_kpi(session: Session, thesis: Thesis, body: KpiCreate) -> ThesisKpi:
    company = _company(session, thesis)
    if len(repo.kpis(session, [thesis.id])) >= MAX_KPIS:
        raise ThesisError(409, "Too many KPIs", f"A thesis has at most {MAX_KPIS} KPIs.")
    metric = validate_kpi(company, body.metric, body.period_type, body.threshold)
    kpi = ThesisKpi(
        thesis_id=thesis.id,
        metric=metric.key,
        period_type=body.period_type,
        comparator=body.comparator,
        threshold=body.threshold,
        unit=metric.unit,
        label=body.label,
        rationale=body.rationale,
        state="no_data",
    )
    session.add(kpi)
    session.flush()
    evaluate_kpi(session, company, kpi)  # the baseline: no event (ADR-0049)
    return kpi


def update_kpi(session: Session, thesis: Thesis, kpi: ThesisKpi, body: KpiUpdate) -> ThesisKpi:
    company = _company(session, thesis)
    metric_key = body.metric or kpi.metric
    period_type = body.period_type or kpi.period_type
    threshold = body.threshold if body.threshold is not None else kpi.threshold
    comparator = body.comparator or kpi.comparator
    redefined = (metric_key, period_type, threshold, comparator) != (
        kpi.metric,
        kpi.period_type,
        kpi.threshold,
        kpi.comparator,
    )
    if redefined:
        metric = validate_kpi(company, metric_key, period_type, threshold)
        kpi.metric, kpi.unit = metric.key, metric.unit
        kpi.period_type, kpi.threshold, kpi.comparator = period_type, threshold, comparator
        kpi.evaluated_at = None  # the user moved the goalposts: a new baseline, not news
    if body.label is not None:
        kpi.label = body.label
    if "rationale" in body.model_fields_set:
        kpi.rationale = body.rationale
    session.flush()
    if redefined:
        evaluate_kpi(session, company, kpi)
    return kpi


def add_note(session: Session, thesis: Thesis, note: str) -> ThesisEvent:
    event = ThesisEvent(thesis_id=thesis.id, kind="user_note", note=note)
    session.add(event)
    session.flush()
    return event


def _states(kpis: Sequence[ThesisKpi]) -> StateCounts:
    counts = Counter(k.state for k in kpis)
    return StateCounts(met=counts["met"], broken=counts["broken"], no_data=counts["no_data"])


def summary(thesis: Thesis, ticker: str, kpis: Sequence[ThesisKpi]) -> ThesisSummary:
    return ThesisSummary(
        id=thesis.id,
        ticker=ticker,
        title=thesis.title,
        stance=thesis.stance,  # type: ignore[arg-type]  # CHECK stance_known
        status=thesis.status,  # type: ignore[arg-type]
        created_at=thesis.created_at,
        updated_at=thesis.updated_at,
        kpi_states=_states(kpis),
    )


def kpi_out(kpi: ThesisKpi, history: Sequence[registry.Point]) -> Kpi:
    metric = registry.BY_KEY.get(kpi.metric)
    return Kpi(
        id=kpi.id,
        metric=kpi.metric,
        metric_label=metric.label if metric else kpi.metric,
        unit=kpi.unit,  # type: ignore[arg-type]
        period_type=kpi.period_type,  # type: ignore[arg-type]
        comparator=kpi.comparator,  # type: ignore[arg-type]
        threshold=kpi.threshold,
        label=kpi.label,
        rationale=kpi.rationale,
        state=kpi.state,  # type: ignore[arg-type]
        last_value=kpi.last_value,
        last_source_ids=[str(s) for s in kpi.last_source_ids],
        last_period=kpi.last_period,
        last_period_end=kpi.last_period_end,
        evaluated_at=kpi.evaluated_at,
        history=[
            KpiPoint(
                period=p.period,
                period_end=p.period_end,
                value=p.value,
                source_ids=list(p.source_ids),
            )
            for p in history[-HISTORY_POINTS:]
        ],
    )


def detail(session: Session, thesis: Thesis) -> ThesisDetail:
    company = _company(session, thesis)
    kpis = repo.kpis(session, [thesis.id])
    series: dict[tuple[str, str], list[registry.Point]] = {}
    out = []
    for kpi in kpis:
        metric = registry.BY_KEY.get(kpi.metric)
        key = (kpi.metric, kpi.period_type)
        if metric is not None and key not in series:
            series[key] = registry.series(session, company, metric, kpi.period_type)
        out.append(kpi_out(kpi, series.get(key, [])))
    return ThesisDetail(
        **summary(thesis, company.ticker, kpis).model_dump(), body_md=thesis.body_md, kpis=out
    )


def summaries(session: Session, user_id: int, *, company_id: int | None) -> list[ThesisSummary]:
    rows = repo.list_for_user(session, user_id, company_id=company_id)
    by_thesis: dict[int, list[ThesisKpi]] = {}
    for kpi in repo.kpis(session, [t.id for t, _ in rows]):
        by_thesis.setdefault(kpi.thesis_id, []).append(kpi)
    return [summary(t, ticker, by_thesis.get(t.id, [])) for t, ticker in rows]


def event_out(event: ThesisEvent) -> EventOut:
    return EventOut(
        id=event.id,
        kind=event.kind,  # type: ignore[arg-type]  # CHECK kind_known
        occurred_at=event.occurred_at,
        kpi_id=event.kpi_id,
        ref_type=event.ref_type,
        ref_id=event.ref_id,
        note=event.note,
        payload=event.payload or {},
    )


def revisions(session: Session, thesis: Thesis) -> list[ThesisRevision]:
    """Every revision, newest first, each with a word diff against the one before it."""
    rows = repo.revisions(session, thesis.id)
    out = []
    for previous, current in zip([None, *rows[:-1]], rows, strict=True):
        diff = (
            [
                DiffOp(op=op, text=text)
                for op, text in word_diff(
                    f"{previous.title}\n\n{previous.body_md}",
                    f"{current.title}\n\n{current.body_md}",
                )
            ]
            if previous is not None
            else None
        )
        out.append(
            ThesisRevision(
                revision=current.revision,
                title=current.title,
                body_md=current.body_md,
                created_at=current.created_at,
                word_diff=diff,
            )
        )
    return out[::-1]


def metric_registry(company: Company | None) -> MetricRegistryResponse:
    return MetricRegistryResponse(
        version=registry.REGISTRY_VERSION,
        ticker=company.ticker if company else None,
        metrics=[
            MetricRegistryEntry(
                key=m.key,
                label=m.label,
                group=m.group,
                unit=m.unit,
                period_types=list(m.period_types),  # type: ignore[arg-type]
                description=m.description,
                applicable=registry.applicable(m, company) if company else None,
            )
            for m in registry.METRICS
        ],
    )
