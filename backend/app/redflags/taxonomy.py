"""Red-flag taxonomy `red_flag_taxonomy_v1` (Phase 7e, FR-RF-001/002, ADR-0043).

A flag means "this event is reported in a filing", never "this company is in trouble". Every rule
is deterministic: an 8-K item code, a form type, a phrase rule on filing text, or a stored figure.
No model classifies anything. Severity says how closely an analyst would want to read it, not
whether it is bad.

Sources, checked on 2026-10-22:
- 8-K items and titles: SEC Form 8-K, General Instructions, "SEC 873 (02-25)",
  https://www.sec.gov/files/form8-k.pdf. Items 1.03, 1.05, 2.05, 2.06, 3.01, 4.01, 4.02, 5.01 and
  5.02 as quoted in `ITEM_TITLES`; 5.02(b) names the officer roles extracted for departures.
- Late-filing notices: SEC Form 12b-25, "Notification of Late Filing" (Exchange Act Rule
  12b-25), https://www.sec.gov/files/form12b-25.pdf; EDGAR files it as NT 10-K / NT 10-Q.
- Going concern: ASC 205-40 ("substantial doubt about an entity's ability to continue as a going
  concern"); material weakness: Regulation S-K Item 308 as reported in 10-K Item 9A.
- Beneish: Phase 7d (ADR-0042). Restatement: the as-reported rows Phase 1b keeps (DR-023).

Adding a rule is one `_rule(...)` entry plus its tests. Changing any rule or pattern bumps
`TAXONOMY_VERSION`; detection then writes new rows and the API serves the newest version only.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from app.redflags import going_concern
from app.redflags import patterns as p

TAXONOMY_VERSION = "red_flag_taxonomy_v1"
Severity = Literal["info", "warning", "critical"]
SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}


def severities_at_least(severity: str | None) -> list[str] | None:
    """The severities at or above `severity` (None = all): info < warning < critical."""
    if severity is None:
        return None
    floor = SEVERITY_RANK[severity]
    return [s for s, rank in SEVERITY_RANK.items() if rank >= floor]


EIGHT_K_FORMS = frozenset({"8-K", "8-K/A"})
LATE_NOTICE_FORMS = frozenset({"NT 10-K", "NT 10-Q", "NT 10-K/A", "NT 10-Q/A"})
PERIODIC_FORMS = frozenset({"10-K", "10-K/A", "10-Q", "10-Q/A"})
ANNUAL_FORMS = frozenset({"10-K", "10-K/A"})
MW_SECTION = "10k_item9a"
SNIPPET_CHARS = 500

# Official item titles, as printed in SEC Form 8-K (SEC 873, 02-25).
ITEM_TITLES: dict[str, str] = {
    "1.03": "Bankruptcy or Receivership",
    "1.05": "Material Cybersecurity Incidents",
    "2.05": "Costs Associated with Exit or Disposal Activities",
    "2.06": "Material Impairments",
    "3.01": "Notice of Delisting or Failure to Satisfy a Continued Listing Rule or Standard; "
    "Transfer of Listing",
    "4.01": "Changes in Registrant's Certifying Accountant",
    "4.02": "Non-Reliance on Previously Issued Financial Statements or a Related Audit Report or "
    "Completed Interim Review",
    "5.01": "Changes in Control of Registrant",
    "5.02": "Departure of Directors or Certain Officers; Election of Directors; Appointment of "
    "Certain Officers; Compensatory Arrangements of Certain Officers",
}


@dataclass(frozen=True)
class Paragraph:
    """One parsed chunk of the filing: its citation anchor, section and text."""

    paragraph_id: str | None
    section_key: str | None
    text: str


@dataclass(frozen=True)
class FilingEvidence:
    """Everything the rules may look at for one filing, gathered by the detector."""

    filing_type: str
    items: frozenset[str] = frozenset()  # 8-K item codes (index metadata, else parsed headings)
    paragraphs: tuple[Paragraph, ...] = ()
    notice_for: str | None = None  # NT forms: the late report (10-K / 10-Q)
    period_end: str | None = None
    beneish: dict[str, str] | None = None  # 10-K: {"score", "fiscal_year", "source_id"} if above
    restated: tuple[dict[str, str], ...] = ()  # amended filing: changed as-reported values


@dataclass(frozen=True)
class Match:
    paragraph_id: str | None  # the paragraph the snippet quotes (None: no chunk, e.g. NT form)
    snippet: str
    payload: dict[str, Any] = field(default_factory=dict)


Matcher = Callable[[FilingEvidence], Match | None]


@dataclass(frozen=True)
class RedFlagRule:
    key: str
    label: str  # neutral: what is reported, never a judgement
    severity: Severity  # how closely to read it, not how bad it is
    source: str  # the SEC form / standard the trigger comes from
    matcher: Matcher
    explanation: str  # one or two sentences shown in the tooltip


# --- helpers -----------------------------------------------------------------------------------


_MARKUP = re.compile(r"</?[a-z][^>]*>", re.I)  # parser residue such as a literal "</p>"


def _clip(text: str) -> str:
    text = " ".join(_MARKUP.sub(" ", text).split())
    if len(text) <= SNIPPET_CHARS:
        return text
    return text[:SNIPPET_CHARS].rsplit(" ", 1)[0] + "…"


_ITEM_PREFIX = re.compile(r"^item\s+\d{1,2}\.\d{2}\.?\s*", re.I)


def _strip_title(code: str, text: str) -> str:
    """Drop the item's own title from the start of its text: a heading is not an event. The
    heading ends at its first full stop (titles contain none)."""
    body = _ITEM_PREFIX.sub("", " ".join(text.replace("\u2019", "'").split()))
    title = ITEM_TITLES.get(code, "")
    if title and body.lower().startswith(title.split(";")[0].lower()):
        end = body.find(". ", 0, len(title) + 40)
        body = body[end + 2 :] if end >= 0 else body[len(title) :]
    return body.lstrip(" .;:")


def _section(e: FilingEvidence, code: str) -> Iterator[Paragraph]:
    key = f"8k_item{code}"
    return (para for para in e.paragraphs if para.section_key == key)


def _item(code: str) -> Matcher:
    """Fires when an 8-K reports item `code`; quotes the item's first paragraph."""

    def match(e: FilingEvidence) -> Match | None:
        if e.filing_type not in EIGHT_K_FORMS or code not in e.items:
            return None
        for para in _section(e, code):
            body = _strip_title(code, para.text)
            if body:
                return Match(para.paragraph_id, _clip(body), {"item": code})
        # No parsed text for the item: say what is reported rather than quote nothing.
        return Match(None, f"This 8-K reports Item {code} ({ITEM_TITLES[code]}).", {"item": code})

    return match


def _departure(e: FilingEvidence) -> tuple[str | None, str, list[str]] | None:
    """Item 5.02 sentences with a departure verb: (paragraph, first sentence, roles named)."""
    if e.filing_type not in EIGHT_K_FORMS or "5.02" not in e.items:
        return None
    first: tuple[str | None, str] | None = None
    roles: list[str] = []
    for para in _section(e, "5.02"):
        for sentence in p.sentences(_strip_title("5.02", para.text)):
            event = (
                p.DEPARTURE.search(sentence)
                and not p.DEPARTURE_NOT_EVENT.search(sentence)
                # A leftover heading ("Departure of Directors or …") is not an event.
                and not p.ITEM_502_HEADING.match(sentence)
            )
            if event:
                first = first or (para.paragraph_id, sentence)
                # Only roles in the departure sentence itself: a neighbouring sentence often
                # names someone else (the successor, the CEO they report to).
                roles += [r for r, rx in p.ROLES.items() if rx.search(sentence) and r not in roles]
    return (first[0], first[1], roles) if first else None


def _exec_departure(e: FilingEvidence) -> Match | None:
    found = _departure(e)
    if found is None or not found[2]:
        return None
    paragraph_id, sentence, roles = found
    return Match(paragraph_id, _clip(sentence), {"item": "5.02", "roles": roles})


def _exec_change_unspecified(e: FilingEvidence) -> Match | None:
    found = _departure(e)
    if found is None or found[2]:
        return None
    return Match(found[0], _clip(found[1]), {"item": "5.02", "roles": []})


def _late_notice(e: FilingEvidence) -> Match | None:
    if e.filing_type not in LATE_NOTICE_FORMS:
        return None
    late_for = e.notice_for or e.filing_type.removeprefix("NT ")
    period = f" for the period ended {e.period_end}" if e.period_end else ""
    return Match(
        e.paragraphs[0].paragraph_id if e.paragraphs else None,
        f"Notification of late filing (Form 12b-25): Form {late_for}{period}.",
        {"form": e.filing_type, "notice_for": late_for},
    )


def _going_concern(kind: str) -> Matcher:
    def match(e: FilingEvidence) -> Match | None:
        if e.filing_type not in PERIODIC_FORMS:
            return None
        found = going_concern.find((para.paragraph_id, para.text) for para in e.paragraphs)
        hit = found.get(kind)
        if hit is None:
            return None
        return Match(hit.paragraph_id, _clip(hit.sentence), {"classification": kind})

    return match


def _material_weakness(e: FilingEvidence) -> Match | None:
    if e.filing_type not in ANNUAL_FORMS:
        return None
    for para in e.paragraphs:
        if para.section_key != MW_SECTION:
            continue
        for sentence in p.sentences(para.text):
            if p.MATERIAL_WEAKNESS.search(sentence) and not p.MW_NOT_REPORTED.search(sentence):
                return Match(para.paragraph_id, _clip(sentence), {"section": "Item 9A"})
    return None


def _beneish(e: FilingEvidence) -> Match | None:
    if e.filing_type not in ANNUAL_FORMS or e.beneish is None:
        return None
    b = e.beneish
    return Match(
        None,
        f"Beneish M-score of {b['score']} for FY{b['fiscal_year']} is above the -1.78 "
        "screening threshold (a screening heuristic, not a finding).",
        dict(b),
    )


def _restatement(e: FilingEvidence) -> Match | None:
    if not e.filing_type.endswith("/A") or not e.restated:
        return None
    changes = "; ".join(
        f"{r['metric']} {r['period']}: {r['before']} → {r['after']}" for r in e.restated
    )
    return Match(
        None,
        _clip(f"This amended filing reports different values for: {changes}."),
        {"restated": list(e.restated)},
    )


def _rule(
    key: str, label: str, severity: Severity, source: str, matcher: Matcher, explanation: str
) -> RedFlagRule:
    return RedFlagRule(key, label, severity, source, matcher, explanation)


_8K = "SEC Form 8-K (SEC 873, 02-25), Item"

RULES: tuple[RedFlagRule, ...] = (
    _rule(
        "non_reliance",
        "Non-reliance on previously issued financial statements",
        "critical",
        f"{_8K} 4.02",
        _item("4.02"),
        "Item 4.02: the company says earlier financial statements should no longer be relied "
        "on, usually because of an error. They are typically restated later.",
    ),
    _rule(
        "auditor_change",
        "Change of auditor reported",
        "warning",
        f"{_8K} 4.01",
        _item("4.01"),
        "Item 4.01: the independent accountant resigned, declined to stand for re-appointment "
        "or was dismissed. The filing must say whether there were disagreements.",
    ),
    _rule(
        "late_filing_notice",
        "Late-filing notice",
        "warning",
        "SEC Form 12b-25 (Rule 12b-25), filed as NT 10-K / NT 10-Q",
        _late_notice,
        "Form 12b-25: the company told the SEC a 10-K or 10-Q will not be filed on time and "
        "why. A short extension follows automatically.",
    ),
    _rule(
        "exec_departure",
        "Officer or director departure reported",
        "info",
        f"{_8K} 5.02(b)",
        _exec_departure,
        "Item 5.02: a principal officer or director is leaving. Many departures are planned "
        "retirements or transitions.",
    ),
    _rule(
        "exec_change_unspecified",
        "Leadership change reported",
        "info",
        f"{_8K} 5.02",
        _exec_change_unspecified,
        "Item 5.02 describes a departure without naming one of the principal roles we track. "
        "Read the item for who is affected.",
    ),
    _rule(
        "impairment",
        "Material impairment reported",
        "warning",
        f"{_8K} 2.06",
        _item("2.06"),
        "Item 2.06: the company concluded an asset's value is materially impaired and will "
        "record a charge.",
    ),
    _rule(
        "restructuring",
        "Exit or restructuring costs reported",
        "info",
        f"{_8K} 2.05",
        _item("2.05"),
        "Item 2.05: the company committed to an exit or disposal plan, such as a restructuring, "
        "with material costs.",
    ),
    _rule(
        "delisting_notice",
        "Delisting or listing-standard notice reported",
        "critical",
        f"{_8K} 3.01",
        _item("3.01"),
        "Item 3.01: an exchange notified the company of delisting or of a failure to meet a "
        "listing standard, or the company is transferring its listing.",
    ),
    _rule(
        "bankruptcy",
        "Bankruptcy or receivership reported",
        "critical",
        f"{_8K} 1.03",
        _item("1.03"),
        "Item 1.03: a receiver or similar officer was appointed for the company or a significant "
        "subsidiary, for example in a Chapter 11 case.",
    ),
    _rule(
        "material_cyber_incident",
        "Material cybersecurity incident reported",
        "warning",
        f"{_8K} 1.05",
        _item("1.05"),
        "Item 1.05: the company determined a cybersecurity incident is material and describes "
        "its nature, scope and likely impact.",
    ),
    _rule(
        "change_in_control",
        "Change in control reported",
        "info",
        f"{_8K} 5.01",
        _item("5.01"),
        "Item 5.01: control of the company changed, for example after an acquisition of its "
        "shares.",
    ),
    _rule(
        "going_concern",
        "Going-concern doubt reported",
        "critical",
        "ASC 205-40 wording in a 10-K / 10-Q",
        _going_concern(going_concern.GOING_CONCERN),
        "The filing states substantial doubt about the company's ability to continue as a going "
        "concern for the next year.",
    ),
    _rule(
        "going_concern_alleviated",
        "Going-concern doubt alleviated by management's plans",
        "warning",
        "ASC 205-40 wording in a 10-K / 10-Q",
        _going_concern(going_concern.GOING_CONCERN_ALLEVIATED),
        "The filing describes conditions that raised substantial doubt and says management's "
        "plans alleviate it.",
    ),
    _rule(
        "going_concern_risk_language",
        "Going-concern risk language",
        "info",
        "ASC 205-40 wording in a 10-K / 10-Q (conditional)",
        _going_concern(going_concern.GOING_CONCERN_RISK_LANGUAGE),
        "A conditional statement, often a risk factor: substantial doubt could arise if "
        "something happens. It is not a conclusion that doubt exists.",
    ),
    _rule(
        "material_weakness",
        "Material weakness reported",
        "warning",
        "Regulation S-K Item 308, as reported in 10-K Item 9A",
        _material_weakness,
        "Item 9A reports a material weakness in internal control over financial reporting: a "
        "reasonable possibility that a material misstatement would not be caught in time.",
    ),
    _rule(
        "beneish_above_threshold",
        "Beneish M-score above screening threshold",
        "info",
        "Beneish (1999) M-score, Phase 7d (ADR-0042)",
        _beneish,
        "A screening heuristic computed from this 10-K's figures is above -1.78. It is a reason "
        "to read the accounting notes, not a conclusion about them.",
    ),
    _rule(
        "restatement_in_xbrl",
        "Values restated in an amended filing",
        "warning",
        "XBRL as-reported values (10-K/A, 10-Q/A)",
        _restatement,
        "An amended filing reports a different value for a period already reported. The "
        "earlier figure is kept as reported.",
    ),
)

RULES_BY_KEY: dict[str, RedFlagRule] = {rule.key: rule for rule in RULES}
SOURCE_PREFIX = "redflag:"


def source_id(ticker: str, rule_key: str, accession: str) -> str:
    """The backend-issued citation ID of a flag (FR-RF-008)."""
    return f"{SOURCE_PREFIX}{ticker.upper()}:{rule_key}:{accession}"


def parse_source_id(value: str) -> tuple[str, str, str] | None:
    """(ticker, rule_key, accession) of a `redflag:` ID, or None when it is not one."""
    parts = value.removeprefix(SOURCE_PREFIX).split(":")
    if not value.startswith(SOURCE_PREFIX) or len(parts) != 3 or not all(parts):
        return None
    return parts[0], parts[1], parts[2]


def evaluate(evidence: FilingEvidence) -> list[tuple[RedFlagRule, Match]]:
    """Every rule that fires on one filing, in taxonomy order."""
    out: list[tuple[RedFlagRule, Match]] = []
    for rule in RULES:
        found = rule.matcher(evidence)
        if found is not None:
            out.append((rule, found))
    return out
