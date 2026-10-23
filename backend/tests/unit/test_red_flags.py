"""Red-flag taxonomy (Phase 7e): every rule's positives and negatives, the going-concern guards,
departure parsing, and the copy review. Offline and pure.

Text marked SYNTHETIC is written for these tests; the rest is quoted from real filings in the dev
store or the fixtures (NVIDIA, Intel, JPMorgan, AMD 8-Ks). Requirement IDs: FR-RF-001 … FR-RF-005,
FR-RF-011, FR-RF-014, DR-RF-001.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import get_args

import pytest

from app.citation.advice import contains_advice
from app.redflags import going_concern as gc
from app.redflags import taxonomy as tx
from app.redflags.alerts import RedFlagParams, RuleKey, red_flag_event
from app.redflags.patterns import sentences

E = tx.FilingEvidence


def _p(section: str | None, text: str, pid: str = "1_p_0") -> tx.Paragraph:
    return tx.Paragraph(pid, section, text)


def _8k(items: set[str], *paras: tx.Paragraph, form: str = "8-K") -> tx.FilingEvidence:
    return E(form, frozenset(items), tuple(paras))


def _periodic(text: str, form: str = "10-Q", section: str = "10q_P1-2") -> tx.FilingEvidence:
    return E(form, paragraphs=(_p(section, text),))


# --- Item-code rules ---------------------------------------------------------------------------

ITEM_RULES = {
    "non_reliance": "4.02",
    "auditor_change": "4.01",
    "impairment": "2.06",
    "restructuring": "2.05",
    "delisting_notice": "3.01",
    "bankruptcy": "1.03",
    "material_cyber_incident": "1.05",
    "change_in_control": "5.01",
}
# A neighbour code that shared the collapsed major number before Phase 7c ("5" for 5.01 and
# 5.07): it must never trigger the rule (FR-RF-001, the old item-code collision).
NEIGHBOUR = {
    "4.02": "4.01",
    "4.01": "4.02",
    "2.06": "2.05",
    "2.05": "2.02",
    "3.01": "3.02",
    "1.03": "1.01",
    "1.05": "1.01",
    "5.01": "5.07",
}


def _item_cases(code: str) -> tuple[list[tx.FilingEvidence], list[tx.FilingEvidence]]:
    section = f"8k_item{code}"
    body = f"{tx.ITEM_TITLES[code]}. On March 2, 2026, the Company reported the event."
    positives = [
        _8k({code, "9.01"}, _p(section, body)),
        _8k({code}, _p(section, body), form="8-K/A"),
        _8k({code}),  # classified by the filing index, no parsed text: still reported
    ]
    negatives = [
        _8k({NEIGHBOUR[code], "9.01"}, _p(f"8k_item{NEIGHBOUR[code]}", body)),
        E("10-K", frozenset({code}), (_p(section, body),)),  # not an 8-K
        _8k(set(), _p(section, body)),  # no item in the index or headings
    ]
    return positives, negatives


@pytest.mark.parametrize(("key", "code"), sorted(ITEM_RULES.items()))
def test_item_rules_fire_on_their_item_only(key: str, code: str) -> None:
    """FR-RF-001: ≥3 positives and ≥3 negatives per item rule."""
    rule = tx.RULES_BY_KEY[key]
    positives, negatives = _item_cases(code)
    for evidence in positives:
        found = rule.matcher(evidence)
        assert found is not None and found.payload == {"item": code}, (key, evidence)
    for evidence in negatives:
        assert rule.matcher(evidence) is None, (key, evidence)


def test_item_snippet_drops_the_heading_and_falls_back_to_a_sentence() -> None:
    """FR-RF-003: the quote is the item's text, not its title; no text says what is reported."""
    rule = tx.RULES_BY_KEY["non_reliance"]
    para = _p(
        "8k_item4.02",
        "Item 4.02. Non-Reliance on Previously Issued Financial Statements or a Related Audit "
        "Report or Completed Interim Review. On March 2, 2026, the Audit Committee concluded "
        "that the financial statements should no longer be relied upon.",
        pid="7_4.02_0",
    )
    found = rule.matcher(_8k({"4.02"}, para))
    assert found is not None and found.paragraph_id == "7_4.02_0"
    assert found.snippet.startswith("On March 2, 2026, the Audit Committee")
    bare = rule.matcher(_8k({"4.02"}))
    assert bare is not None and bare.snippet.startswith("This 8-K reports Item 4.02 (")
    heading_only = rule.matcher(_8k({"4.02"}, _p("8k_item4.02", tx.ITEM_TITLES["4.02"] + ".")))
    assert heading_only is not None and heading_only.paragraph_id is None


# --- Executive departure (Item 5.02) -----------------------------------------------------------

_502 = "8k_item5.02"
DEPARTURE_POSITIVE = [
    # Real: NVIDIA 8-K, 2026-04-27.
    (
        "(b) On April 24, 2026, Donald Robertson, Vice President, or VP, and Chief Accounting "
        "Officer, or CAO, of NVIDIA Corporation, or the Company, notified the Company of his "
        "intention to resign.",
        ["CAO"],
    ),
    # Real: Intel 8-K, 2024-12-03.
    (
        "Resignation of Chief Executive Officer On December 1, 2024, Patrick Gelsinger, Chief "
        "Executive Officer and director of Intel Corporation, retired from his roles.",
        ["CEO", "Director"],
    ),
    # Real: JPMorgan 8-K, 2025-12-08.
    (
        'On December 7, 2025, Todd A. Combs notified JPMorgan Chase & Co. (the "Company") of his '
        "intention to resign as a member of the Board of Directors, effective December 7, 2025.",
        ["Director"],
    ),
    # SYNTHETIC: "will step down".
    ("Jane Roe will step down as Chief Financial Officer on June 30, 2026.", ["CFO"]),
]
DEPARTURE_NEGATIVE = [
    # The item title alone.
    "Departure of Directors or Certain Officers; Election of Directors; Appointment of Certain "
    "Officers; Compensatory Arrangements of Certain Officers.",
    # SYNTHETIC: an appointment only.
    "On May 1, 2026, the Board appointed John Smith as Chief Operating Officer, effective "
    "immediately.",
    # Real shape (Apple 8-K, award terms): a condition, not an event.
    "The award vests in full upon Mr. Cook's termination due to retirement on or after the first "
    "anniversary of the grant date.",
    # Real shape (Intel 8-K, director biography).
    "Mr. Meurice, 68, has over three decades of leadership experience, including most recently "
    "as President and Chief Executive Officer of ASML until his retirement.",
    # Real shape (Intel 8-K, agreement terms).
    "Ms. Johnston Holthaus will also be eligible for such benefits if she resigns for good reason.",
]


@pytest.mark.parametrize(("text", "roles"), DEPARTURE_POSITIVE)
def test_exec_departure_reports_roles_not_names(text: str, roles: list[str]) -> None:
    """FR-RF-004: a departure verb with a principal role fires; roles are reported, names never."""
    found = tx.RULES_BY_KEY["exec_departure"].matcher(_8k({"5.02"}, _p(_502, text)))
    assert found is not None and found.payload["roles"] == roles
    assert tx.RULES_BY_KEY["exec_change_unspecified"].matcher(_8k({"5.02"}, _p(_502, text))) is None


@pytest.mark.parametrize("text", DEPARTURE_NEGATIVE)
def test_exec_departure_ignores_headings_appointments_terms_and_bios(text: str) -> None:
    for key in ("exec_departure", "exec_change_unspecified"):
        assert tx.RULES_BY_KEY[key].matcher(_8k({"5.02"}, _p(_502, text))) is None, (key, text)


def test_departure_needs_item_502_in_an_8k() -> None:
    """FR-RF-004: a 5.07 vote 8-K, a 10-K, or text outside Item 5.02 never fires."""
    text = DEPARTURE_POSITIVE[0][0]
    rule = tx.RULES_BY_KEY["exec_departure"]
    assert rule.matcher(_8k({"5.07"}, _p("8k_item5.07", text))) is None
    assert rule.matcher(E("10-K", frozenset({"5.02"}), (_p(_502, text),))) is None
    assert rule.matcher(_8k({"5.02"}, _p("8k_item9.01", text))) is None


UNSPECIFIED_POSITIVE = [
    # Real: NVIDIA 8-K, 2026-07-02 (an executive VP, not a 5.02(b) principal role).
    "(b) On June 28, 2026, Ajay K. Puri, Executive Vice President, Worldwide Field Operations of "
    "NVIDIA Corporation, notified the Company of his intention to retire.",
    # Real: Apple 8-K, 2025-07-09.
    "Apple's design team will then transition to reporting directly to Mr. Cook after Mr. "
    "Williams retires late in the year.",
    # SYNTHETIC.
    "On May 4, 2026, the General Counsel resigned from the Company.",
]


@pytest.mark.parametrize("text", UNSPECIFIED_POSITIVE)
def test_departure_without_a_tracked_role_is_unspecified(text: str) -> None:
    """FR-RF-004: no role keyword → `exec_change_unspecified`, still reported."""
    found = tx.RULES_BY_KEY["exec_change_unspecified"].matcher(_8k({"5.02"}, _p(_502, text)))
    assert found is not None and found.payload["roles"] == []
    assert tx.RULES_BY_KEY["exec_departure"].matcher(_8k({"5.02"}, _p(_502, text))) is None


# --- Late-filing notice -------------------------------------------------------------------------


@pytest.mark.parametrize("form", ["NT 10-K", "NT 10-Q", "NT 10-K/A"])
def test_late_filing_notice_fires_on_nt_forms(form: str) -> None:
    found = tx.RULES_BY_KEY["late_filing_notice"].matcher(
        E(form, notice_for=form.removeprefix("NT ").removesuffix("/A"), period_end="2026-01-25")
    )
    assert found is not None
    assert found.snippet.startswith("Notification of late filing (Form 12b-25): Form 10-")
    assert "period ended 2026-01-25" in found.snippet


@pytest.mark.parametrize("form", ["10-K", "10-Q", "8-K"])
def test_late_filing_notice_ignores_other_forms(form: str) -> None:
    assert tx.RULES_BY_KEY["late_filing_notice"].matcher(E(form)) is None


# --- Going concern (FR-RF-003) ----------------------------------------------------------------

GC = (
    "These conditions raise substantial doubt about the Company's ability to continue as a "
    "going concern."
)
GOING_CONCERN_CASES = [
    # SYNTHETIC, each one class.
    (GC, gc.GOING_CONCERN),
    (
        "Our recurring losses and negative cash flows raise substantial doubt about our ability "
        "to continue as a going concern within one year after the date the financial statements "
        "are issued.",
        gc.GOING_CONCERN,
    ),
    (
        "The report of our auditor includes an explanatory paragraph stating that there is "
        "substantial doubt about our ability to continue as a going concern.",
        gc.GOING_CONCERN,
    ),
    # Negation: no flag.
    ("There is no substantial doubt about our ability to continue as a going concern.", None),
    (
        "These events did not raise substantial doubt about the Company's ability to continue as "
        "a going concern.",
        None,
    ),
    (
        "The financing completed in March alleviated substantial doubt about our ability to "
        "continue as a going concern.",
        None,
    ),
    # Policy description: no flag.
    (
        "Management evaluates whether there are conditions that raise substantial doubt about "
        "the Company's ability to continue as a going concern within one year.",
        None,
    ),
    # Hypothetical / risk-factor language: a lower tier, its own label.
    (
        "If we are unable to obtain additional financing, there could be substantial doubt about "
        "our ability to continue as a going concern.",
        gc.GOING_CONCERN_RISK_LANGUAGE,
    ),
    (
        "Failure to refinance the notes could raise substantial doubt about our ability to "
        "continue as a going concern.",
        gc.GOING_CONCERN_RISK_LANGUAGE,
    ),
    (
        "Should revenue decline further, substantial doubt may arise about our ability to "
        "continue as a going concern.",
        gc.GOING_CONCERN_RISK_LANGUAGE,
    ),
    # Alleviated by management's plans.
    (
        "Substantial doubt about the Company's ability to continue as a going concern has been "
        "alleviated by management's plans.",
        gc.GOING_CONCERN_ALLEVIATED,
    ),
    (
        "Conditions raised substantial doubt about our ability to continue as a going concern, "
        "which was alleviated by management's plans to reduce costs.",
        gc.GOING_CONCERN_ALLEVIATED,
    ),
    (
        "Substantial doubt regarding the going concern assumption was mitigated by management's "
        "plans, including the new credit facility.",
        gc.GOING_CONCERN_ALLEVIATED,
    ),
    # No core match.
    ("We continue to operate as a going concern and have ample liquidity.", None),
    ("There is substantial doubt that the merger will close this year.", None),
]


@pytest.mark.parametrize(("sentence", "expected"), GOING_CONCERN_CASES)
def test_going_concern_classification_with_guards(sentence: str, expected: str | None) -> None:
    """FR-RF-003: negated, policy, hypothetical and alleviated sentences each get the right
    class (or none)."""
    assert gc.classify(sentence) == expected


@pytest.mark.parametrize(
    "key", [gc.GOING_CONCERN, gc.GOING_CONCERN_ALLEVIATED, gc.GOING_CONCERN_RISK_LANGUAGE]
)
def test_going_concern_rules_quote_the_sentence_and_paragraph(key: str) -> None:
    """FR-RF-003: ≥3 positives and ≥3 negatives per going-concern rule, with the quoted sentence
    and its paragraph id."""
    rule = tx.RULES_BY_KEY[key]
    positives = [s for s, k in GOING_CONCERN_CASES if k == key]
    negatives = [s for s, k in GOING_CONCERN_CASES if k != key]
    assert len(positives) >= 3 and len(negatives) >= 3
    for sentence in positives:
        found = rule.matcher(_periodic(f"Liquidity. {sentence} We continue to evaluate options."))
        assert found is not None and found.snippet == sentence and found.paragraph_id == "1_p_0"
    for sentence in negatives:
        assert rule.matcher(_periodic(sentence)) is None, sentence
    assert rule.matcher(_8k({"8.01"}, _p("8k_item8.01", positives[0]))) is None  # not a 10-K/Q


# --- Material weakness (10-K Item 9A) ----------------------------------------------------------

MW_POSITIVE = [
    # SYNTHETIC.
    "Management identified a material weakness in our internal control over financial reporting "
    "related to revenue recognition.",
    "A material weakness existed in the design of controls over inventory valuation.",
    "Our principal executive and financial officers concluded that our internal control over "
    "financial reporting was not effective because of the material weakness described below.",
]
MW_NEGATIVE = [
    # Real shape: the definition every 10-K quotes.
    "A material weakness is a deficiency, or a combination of deficiencies, in internal control "
    "over financial reporting, such that there is a reasonable possibility that a material "
    "misstatement will not be prevented or detected on a timely basis.",
    "We did not identify any material weaknesses in our internal control over financial reporting.",
    "If we fail to maintain effective controls, it could result in a material weakness.",
    "The material weakness previously reported has been remediated as of January 25, 2026.",
]


@pytest.mark.parametrize("text", MW_POSITIVE)
def test_material_weakness_reported_in_item_9a(text: str) -> None:
    found = tx.RULES_BY_KEY["material_weakness"].matcher(_periodic(text, "10-K", tx.MW_SECTION))
    assert found is not None and found.payload == {"section": "Item 9A"}


@pytest.mark.parametrize("text", MW_NEGATIVE)
def test_material_weakness_ignores_definitions_denials_and_hypotheticals(text: str) -> None:
    assert (
        tx.RULES_BY_KEY["material_weakness"].matcher(_periodic(text, "10-K", tx.MW_SECTION)) is None
    )


def test_material_weakness_only_in_10k_item_9a() -> None:
    rule = tx.RULES_BY_KEY["material_weakness"]
    assert rule.matcher(_periodic(MW_POSITIVE[0], "10-K", "10k_item8")) is None
    assert rule.matcher(_periodic(MW_POSITIVE[0], "10-Q", tx.MW_SECTION)) is None


# --- Beneish and restatement (stored data) ----------------------------------------------------

_B = {"score": "-1.17", "fiscal_year": "2026", "source_id": "derived:NVDA:beneish_m:FY2026"}
_R = ({"metric": "revenue", "period": "FY2024", "before": "100", "after": "95"},)


@pytest.mark.parametrize(
    ("evidence", "fires"),
    [
        (E("10-K", beneish=_B), True),
        (E("10-K/A", beneish=_B), True),
        (E("10-K", beneish={**_B, "score": "-0.50", "fiscal_year": "2025"}), True),
        (E("10-K"), False),
        (E("10-Q", beneish=_B), False),
        (E("8-K", beneish=_B), False),
    ],
)
def test_beneish_above_threshold(evidence: tx.FilingEvidence, fires: bool) -> None:
    found = tx.RULES_BY_KEY["beneish_above_threshold"].matcher(evidence)
    assert (found is not None) is fires
    if found is not None:
        assert "screening heuristic, not a finding" in found.snippet


@pytest.mark.parametrize(
    ("evidence", "fires"),
    [
        (E("10-K/A", restated=_R), True),
        (E("10-Q/A", restated=_R), True),
        (E("10-K/A", restated=_R * 2), True),
        (E("10-K", restated=_R), False),
        (E("10-K/A"), False),
        (E("8-K/A", restated=()), False),
    ],
)
def test_restatement_in_xbrl(evidence: tx.FilingEvidence, fires: bool) -> None:
    found = tx.RULES_BY_KEY["restatement_in_xbrl"].matcher(evidence)
    assert (found is not None) is fires
    if found is not None:
        assert "revenue FY2024: 100 → 95" in found.snippet


# --- Taxonomy-wide checks ----------------------------------------------------------------------


def test_every_rule_has_a_source_and_a_test() -> None:
    """FR-RF-001/002: every rule names its SEC/standard source and is covered above."""
    covered = (
        set(ITEM_RULES)
        | {"exec_departure", "exec_change_unspecified", "late_filing_notice", "material_weakness"}
        | {gc.GOING_CONCERN, gc.GOING_CONCERN_ALLEVIATED, gc.GOING_CONCERN_RISK_LANGUAGE}
        | {"beneish_above_threshold", "restatement_in_xbrl"}
    )
    assert covered == set(tx.RULES_BY_KEY)
    for rule in tx.RULES:
        assert rule.source and rule.explanation and rule.severity in tx.SEVERITY_RANK
    for key, code in ITEM_RULES.items():
        assert tx.RULES_BY_KEY[key].source.endswith(code)


_ACCUSATION = re.compile(r"fraud|manipulat|wrongdo|misconduct|illegal|guilty|cheat|scandal", re.I)


def test_copy_review_neutral_text_everywhere() -> None:
    """FR-RF-014: no label, explanation, snippet template or alert text implies wrongdoing or
    gives advice."""
    texts: list[str] = []
    for rule in tx.RULES:
        texts += [rule.label, rule.explanation]
        event = red_flag_event(
            ticker="TST",
            rule_key=rule.key,
            accession="0000000000-26-000001",
            company_id=1,
            filed=None,
            at=datetime(2026, 1, 1),
        )
        texts += [event.title, event.body]
        assert event.body.startswith(f"Reported: {rule.label} (filed ")
    texts += [
        tx.RULES_BY_KEY["beneish_above_threshold"].matcher(E("10-K", beneish=_B)).snippet,  # type: ignore[union-attr]
        tx.RULES_BY_KEY["late_filing_notice"].matcher(E("NT 10-K")).snippet,  # type: ignore[union-attr]
        tx.RULES_BY_KEY["non_reliance"].matcher(_8k({"4.02"})).snippet,  # type: ignore[union-attr]
    ]
    for text in texts:
        assert not contains_advice(text), text
        assert not _ACCUSATION.search(text), text


def test_alert_params_validate_rule_keys_and_severity() -> None:
    """FR-RF-011: `min_severity` defaults to warning; unknown flag types are rejected."""
    assert RedFlagParams().min_severity == "warning"
    assert RedFlagParams(rule_keys=["non_reliance"]).rule_keys == ["non_reliance"]
    with pytest.raises(ValueError, match="rule_keys"):
        RedFlagParams.model_validate({"rule_keys": ["nope"]})
    assert set(get_args(RuleKey)) == set(tx.RULES_BY_KEY)  # the form's choices = the taxonomy
    schema = RedFlagParams.model_json_schema()["properties"]["rule_keys"]
    assert any("enum" in b.get("items", {}) for b in schema["anyOf"])
    assert tx.severities_at_least("warning") == ["warning", "critical"]
    assert tx.severities_at_least(None) is None


def test_source_ids_round_trip() -> None:
    """FR-RF-008: `redflag:{TICKER}:{rule_key}:{accession}`."""
    sid = tx.source_id("nvda", "non_reliance", "0001045810-26-000099")
    assert sid == "redflag:NVDA:non_reliance:0001045810-26-000099"
    assert tx.parse_source_id(sid) == ("NVDA", "non_reliance", "0001045810-26-000099")
    for bad in ("redflag:NVDA:only", "news:1", "redflag:::"):
        assert tx.parse_source_id(bad) is None


def test_sentences_keep_abbreviations_and_initials_together() -> None:
    assert sentences("On May 1, 2026, Mr. A. B. Smith resigned. The U.S. office closed.") == [
        "On May 1, 2026, Mr. A. B. Smith resigned.",
        "The U.S. office closed.",
    ]
    assert sentences("First.\n\nSecond line") == ["First.", "Second line"]


def test_evaluate_runs_every_rule_in_order() -> None:
    evidence = _8k({"4.01", "4.02"}, _p("8k_item4.02", "x"), _p("8k_item4.01", "y"))
    keys: list[str] = [rule.key for rule, _ in tx.evaluate(evidence)]
    assert keys == ["non_reliance", "auditor_change"]


def test_taxonomy_reference_doc_lists_every_rule() -> None:
    """FR-RF-001: the docs table (docs/red-flag-taxonomy.md) names every rule and its source."""
    from pathlib import Path

    doc = (Path(__file__).resolve().parents[3] / "docs" / "red-flag-taxonomy.md").read_text()
    assert tx.TAXONOMY_VERSION in doc
    for rule in tx.RULES:
        assert f"| `{rule.key}` |" in doc and rule.source in doc, rule.key
