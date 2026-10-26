"""Earnings calendar rules, watch-item checks, narrative verification and wording guards
(Phase 7j). Offline: no DB, no network.

Requirement IDs: FR-EB-002/005/006/007/011, CIT-EB-001..003, AGT-EB-001/002.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.citation.advice import contains_advice, predicts
from app.config import get_settings
from app.earnings import calendar, narrative, service, watch
from app.earnings.alerts import KIND_LABEL, brief_event
from app.earnings.sections import change, shorten
from app.guidance.periods import CompanyCalendar
from app.models import DocumentChunk, EarningsBrief
from app.providers.base import LLMClient
from app.schemas.earnings import (
    BriefHeader,
    MetricRow,
    MetricTable,
    NarrativeSentence,
    Reaction,
    WatchItem,
)
from app.schemas.earnings import EarningsBrief as BriefContent
from app.schemas.guidance import GuidanceOutcomeView, GuidanceRelease, GuidanceRow

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "earnings"

# NVIDIA-like fiscal calendar: the year ends in late January, so fiscal 2027 is mostly 2026.
_NVDA = CompanyCalendar(
    calendar_aligned=False,
    anchor=(2026, date(2026, 1, 25)),
    known_ends={
        (2026, "Q3"): date(2025, 10, 26),
        (2026, "FY"): date(2026, 1, 25),
        (2027, "Q1"): date(2026, 4, 26),
        (2027, "Q2"): date(2026, 7, 26),
    },
)


class _Session:
    """Just enough of a Session for `llm_calls` logging."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    def add(self, row: Any) -> None:
        self.added.append(row)


class _Replay(LLMClient):
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.messages: list[Any] = []

    async def complete(self, messages: Any, *, model: str, max_tokens: int) -> str:
        raise NotImplementedError

    async def complete_json(
        self, messages: Any, *, model: str, schema: dict[str, Any], max_tokens: int
    ) -> dict[str, Any]:
        self.messages = list(messages)
        return self.response


def _recorded(name: str) -> dict[str, Any]:
    response: dict[str, Any] = json.loads((_FIXTURES / name).read_text())["response"]
    return response


# --- calendar (FR-EB-001/002) -------------------------------------------------------------------


def test_period_arithmetic_wraps_fiscal_years() -> None:
    assert calendar.next_period((2027, "Q4")) == (2028, "Q1")
    assert calendar.next_period((2027, "Q2")) == (2027, "Q3")
    assert calendar.previous_period((2027, "Q1")) == (2026, "Q4")
    assert calendar.year_ago((2027, "Q3")) == (2026, "Q3")
    assert calendar.label((2027, "Q3")) == "Q3 FY2027"


def test_quarter_ends_map_the_fiscal_year_end_to_q4_and_project_ahead() -> None:
    ends = calendar.quarter_ends(_NVDA)
    assert ends[(2026, "Q4")] == date(2026, 1, 25)
    assert ends[(2027, "Q3")] == date(2026, 10, 26)  # projected in 13-week steps (±1 day)
    assert (2028, "Q2") in ends and (2028, "Q3") not in ends  # four quarters ahead only
    assert calendar.quarter_ends(CompanyCalendar(calendar_aligned=True)) == {}


def test_a_release_reports_the_latest_quarter_ended_before_it() -> None:
    ends = calendar.quarter_ends(_NVDA)
    assert calendar.reported_period(date(2026, 8, 26), ends) == (2027, "Q2")
    assert calendar.reported_period(date(2026, 2, 25), ends) == (2026, "Q4")
    assert calendar.reported_period(date(2026, 7, 26), ends) == (2027, "Q1")  # not on the end day
    assert calendar.reported_period(date(2020, 1, 1), ends) is None  # nothing ended near it


def _chunk(text: str, filed: date) -> DocumentChunk:
    return DocumentChunk(text=text, filing_date=filed, paragraph_id="9_0_1")


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        (
            "NVIDIA will report its financial results for the third quarter of fiscal 2027 "
            "after the market closes on Wednesday, November 18, 2026.",
            (date(2026, 11, 18), "amc"),
        ),
        (
            "The company will host a conference call before the market opens on November 19, "
            "2026 to discuss results for the third quarter of fiscal 2027.",
            (date(2026, 11, 19), "bmo"),
        ),
        (
            "NVIDIA plans to announce results for the third quarter of fiscal 2027 on "
            "November 18, 2026.",
            (date(2026, 11, 18), "unknown"),
        ),
    ],
)
def test_an_announced_future_date_is_quoted(sentence: str, expected: tuple[date, str]) -> None:
    """FR-EB-002(b): a strict match keeps the company's own sentence as the quote."""
    found = calendar.announced(
        [_chunk(f"Intro. {sentence} Outro.", date(2026, 10, 1))], (2027, "Q3"), _NVDA
    )
    assert found is not None
    day, time, quote, chunk = found
    assert (day, time) == expected and quote == sentence and chunk.paragraph_id == "9_0_1"


@pytest.mark.parametrize(
    "sentence",
    [
        # "today": the same day as the release, not a future date
        "NVIDIA will conduct a conference call to discuss its third quarter fiscal 2027 results "
        "today, October 1, 2026.",
        # a past date
        "NVIDIA will report results for the third quarter of fiscal 2027 on September 1, 2026.",
        # two dates: which one?
        "NVIDIA will report results for the third quarter of fiscal 2027 on November 18, 2026, "
        "or November 19, 2026.",
        # another quarter
        "NVIDIA will report results for the fourth quarter of fiscal 2027 on February 24, 2027.",
        # no announcing verb
        "Results for the third quarter of fiscal 2027 were discussed on November 18, 2026.",
        # an ambiguous year for a non-calendar fiscal year
        "NVIDIA will report results for the third quarter of 2027 on November 18, 2026.",
        # an impossible date
        "NVIDIA will report results for the third quarter of fiscal 2027 on February 30, 2027.",
    ],
)
def test_anything_less_than_a_clear_statement_is_not_an_announcement(sentence: str) -> None:
    assert calendar.announced([_chunk(sentence, date(2026, 10, 1))], (2027, "Q3"), _NVDA) is None


def test_estimate_keeps_the_weekday() -> None:
    reported = date(2025, 11, 19)  # a Wednesday
    estimate = reported + calendar.ESTIMATE_SHIFT
    assert estimate == date(2026, 11, 18) and estimate.weekday() == reported.weekday()


# --- figures (FR-EB-004/006) --------------------------------------------------------------------


def test_change_is_growth_for_money_and_points_for_margins() -> None:
    assert change(Decimal("120"), Decimal("100"), "usd") == Decimal("0.2")
    assert change(Decimal("-50"), Decimal("-100"), "usd") == Decimal("0.5")  # off a loss: |prior|
    assert change(Decimal("0.75"), Decimal("0.72"), "ratio") == Decimal("0.03")
    assert change(Decimal("1"), Decimal("0"), "usd") is None  # growth off zero is undefined
    assert change(Decimal("1"), None, "usd_per_share") is None


def test_shorten_cuts_at_a_word_boundary() -> None:
    assert shorten("short", 10) == "short"
    assert shorten("Commitments expose us to financial risks", 25) == "Commitments expose us to…"
    assert shorten("abcdefghijklmnop", 8) == "abcdefg…"


# --- watch items (FR-EB-005, AGT-EB-001) --------------------------------------------------------

_ORIGINALS = [
    "Revenue growth slowed to 55.6% year over year in Q2 FY2027, from 69.2% in Q1 FY2027.",
    "Gross margin fell for two quarters in a row, to 70% in Q2 FY2027 from 72.5% in Q4 FY2026, "
    "after rising in Q4 FY2026.",
    "Mentions of supply chain in MD&A rose to 2.4 per 1,000 words in the 10-Q filed 2026-08-26, "
    "from 1.1 in the prior 10-Q.",
    "Mentions of export controls in MD&A rose to 3.2 per 1,000 words in the 10-Q filed "
    "2026-08-26, from 1.5 in the prior 10-Q.",
]


def _items() -> list[WatchItem]:
    kinds = ["growth_deceleration", "margin_reversal", "topic_rise", "topic_rise"]
    return [
        WatchItem(kind=kind, text=text, source_ids=[f"xbrl:T:m:{i}"])  # type: ignore[arg-type]
        for i, (kind, text) in enumerate(zip(kinds, _ORIGINALS, strict=True))
    ]


def test_a_recorded_bad_rewording_is_rejected_and_the_original_kept() -> None:
    """FR-EB-005 DoD: an LLM rewrite that changes a number is rejected (recorded response); so is
    a forecast, a second sentence and an id the model made up. Source IDs never change."""
    llm = _Replay(_recorded("watch_rewording_bad.json"))
    out = watch.reword(_Session(), _items(), llm=llm, settings=get_settings())  # type: ignore[arg-type]
    assert [i.text for i in out[:3]] == _ORIGINALS[:3]
    assert not any(i.reworded for i in out[:3])
    assert out[3].reworded and out[3].text.startswith("In the 10-Q filed 2026-08-26")
    assert [i.source_ids for i in out] == [i.source_ids for i in _items()]
    # The notes reach the model as numbered lines; the one from a filing heading is untrusted.
    prompt_text = llm.messages[1].content
    assert "[id=w1]" in prompt_text and "[id=w4]" in prompt_text


def test_rewording_checks() -> None:
    original = _ORIGINALS[0]
    same = "In Q2 FY2027, revenue growth slowed to 55.6% year over year, from 69.2% in Q1 FY2027."
    assert watch.acceptable_rewording(original, same)
    assert not watch.acceptable_rewording(original, same.replace("55.6%", "55.7%"))
    assert not watch.acceptable_rewording(original, same.replace(" from 69.2% in Q1 FY2027", ""))
    assert not watch.acceptable_rewording(original, same + " Expect a further slowdown.")
    assert not watch.acceptable_rewording(original, None)
    assert not watch.acceptable_rewording(original, "   ")
    assert not watch.acceptable_rewording(original, same * 5)  # too long


def test_no_candidates_means_no_call_and_no_items() -> None:
    llm = _Replay({"items": []})
    assert watch.reword(_Session(), [], llm=llm, settings=get_settings()) == []  # type: ignore[arg-type]
    assert llm.messages == []
    assert watch.reworded(None, _items()) == {}
    assert watch.reworded({"items": ["bad", {"id": "wx", "text": "x"}]}, _items()) == {}


# --- narrative (FR-EB-006, CIT-EB-001..003) -----------------------------------------------------


def _brief() -> BriefContent:
    header = BriefHeader(
        ticker="T",
        company_name="T Corp",
        fiscal_year=2027,
        fiscal_period="Q2",
        period_label="Q2 FY2027",
        report_date=date(2026, 8, 26),
        report_time="unknown",
        date_source="sec_8k",
        date_estimated=False,
        date_source_id="filing:22",
    )
    revenue = MetricRow(
        metric="revenue",
        label="Revenue",
        unit="usd",
        change_kind="growth",
        value=Decimal("96221000000"),
        source_ids=["xbrl:T:revenue:Q2-FY2027"],
        prior_quarter=Decimal("81620000000"),
        prior_quarter_source_ids=["xbrl:T:revenue:Q1-FY2027"],
        change_vs_prior_quarter=Decimal("0.178962"),
        prior_year=Decimal("46740000000"),
        prior_year_source_ids=["xbrl:T:revenue:Q2-FY2026"],
        change_vs_prior_year=Decimal("1.058511"),
    )
    margin = MetricRow(
        metric="gross_margin",
        label="Gross margin",
        unit="ratio",
        change_kind="points",
        value=Decimal("0.7498"),
        source_ids=["xbrl:T:gross_profit:Q2-FY2027", "xbrl:T:revenue:Q2-FY2027"],
        prior_year=Decimal("0.7242"),
        prior_year_source_ids=["xbrl:T:gross_profit:Q2-FY2026", "xbrl:T:revenue:Q2-FY2026"],
        change_vs_prior_year=Decimal("0.0256"),
    )
    eps = MetricRow(
        metric="eps_gaap",
        label="EPS (GAAP, diluted)",
        unit="usd_per_share",
        change_kind="growth",
        value=None,
        reason="Not reported for Q2 FY2027.",
    )
    guided = GuidanceRow(
        id=1,
        issued_at=None,
        low=Decimal("89180000000"),
        high=Decimal("92820000000"),
        point=None,
        midpoint=Decimal("91000000000"),
        derived_range=True,
        quote="Revenue is expected to be $91.0 billion, plus or minus 2%.",
        source_id="2719_0_5",
        release=GuidanceRelease(document_id=1, title=None, url=None),
        outcome=GuidanceOutcomeView(
            result="above_range",
            actual_value=Decimal("96221000000"),
            actual_source_ids=["xbrl:T:revenue:Q2-FY2027"],
            delta_vs_low=None,
            delta_vs_high=None,
            delta_vs_mid=None,
            delta_vs_mid_pct=None,
            reason_code=None,
            explanation=None,
            computed_at=datetime(2026, 8, 27, tzinfo=UTC),
        ),
        fiscal_year=2027,
        fiscal_period="Q2",
        period_label="Q2 FY2027",
        metric="revenue",
        metric_label="Revenue",
        basis="unspecified",
        unit="usd",
        revisions=[],
    )
    return BriefContent(
        header=header,
        headline_table=MetricTable(
            fiscal_year=2027,
            fiscal_period="Q2",
            period_label="Q2 FY2027",
            prior_quarter_label="Q1 FY2027",
            prior_year_label="Q2 FY2026",
            rows=[revenue, margin, eps],
        ),
        versus_guidance=[guided],
        reaction=Reaction(
            filing_id=22,
            filing_date=date(2026, 8, 26),
            move=Decimal("0.070077"),
            source_ids=["filing:22", "price:T:2026-08-25:2026-08-27"],
        ),
    )


def test_lines_carry_every_figure_with_its_sources() -> None:
    """FR-EB-010: the narrative's only input is the brief's own figures, each with its IDs."""
    lines = narrative.lines(_brief())
    texts = [text for _, text, _ in lines]
    assert texts[0] == (
        "Revenue for Q2 FY2027 was $96.22 billion; versus $81.62 billion in the prior quarter, "
        "Q1 FY2027 (+17.9%); versus $46.74 billion in the prior-year quarter, Q2 FY2026 "
        "(+105.85%)."
    )
    assert "+256 basis points" in texts[1]
    assert not any("EPS" in t for t in texts)  # a missing figure is not a line
    assert texts[2] == (
        "Revenue for Q2 FY2027 (guided $89.18 billion to $92.82 billion) came in above the "
        "guided range; the actual was $96.22 billion."
    )
    assert lines[3][0] == ["filing:22", "price:T:2026-08-25:2026-08-27"]


def test_narrative_keeps_only_verified_cited_sentences() -> None:
    """FR-EB-006 DoD: ≤4 sentences, each cited and verified; dropped sentences shorten it. A
    changed number (NUMERIC_MISMATCH), an uncited claim, a forecast and an unknown source ID are
    all dropped, never replaced."""
    llm = _Replay(_recorded("narrative_response.json"))
    session = _Session()
    out = narrative.narrative(session, _brief(), llm=llm, settings=get_settings())  # type: ignore[arg-type]
    assert out is not None
    texts = [s.text for s in out.sentences]
    assert len(texts) == 4
    assert texts[0].startswith("Revenue for Q2 FY2027 was $96.22 billion, versus $81.62")
    assert not any("99.5" in t or "rally" in t or "market wanted" in t for t in texts)
    assert all(s.source_ids for s in out.sentences)
    assert all("made-up-id" not in s.source_ids for s in out.sentences)
    # The marker-cited sentence keeps its marker's ID.
    assert ["2719_0_5"] in [s.source_ids for s in out.sentences]
    assert out.dropped == 4 and out.prompt_version == "earnings_narrative_v1"
    assert len(session.added) == 1  # one logged model call


def test_narrative_is_none_when_nothing_survives() -> None:
    settings = get_settings()
    nothing = _Replay(
        {"sentences": [{"text": "Shares should rally.", "source_ids": ["filing:22"]}]}
    )
    assert narrative.narrative(_Session(), _brief(), llm=nothing, settings=settings) is None  # type: ignore[arg-type]
    mock = _Replay({"_mock": True})
    assert narrative.narrative(_Session(), _brief(), llm=mock, settings=settings) is None  # type: ignore[arg-type]
    empty = BriefContent(header=_brief().header)
    assert narrative.narrative(_Session(), empty, llm=mock, settings=settings) is None  # type: ignore[arg-type]


def test_cap_drops_from_the_end_to_120_words() -> None:
    long = NarrativeSentence(text=" ".join(["word"] * 50) + ".", source_ids=["a"])
    short = NarrativeSentence(text="A short one.", source_ids=["a"])
    assert narrative.capped([long, long, long]) == [long, long]
    assert narrative.capped([short] * 6) == [short] * 4
    assert narrative.capped([NarrativeSentence(text="w " * 130, source_ids=["a"])]) == []


def test_proposed_ignores_malformed_items() -> None:
    claims = narrative.proposed(
        {"sentences": ["x", {"text": 3}, {"text": "Ok [SOURCE:a].", "source_ids": "b"}]}
    )
    assert [(c.text, c.source_ids) for c in claims] == [("Ok.", ["a"])]
    assert narrative.proposed(None) == []


# --- versioning (FR-EB-007) ---------------------------------------------------------------------


def test_inputs_hash_is_stable_and_sensitive() -> None:
    a, b = _brief(), _brief()
    assert service.inputs_hash(a) == service.inputs_hash(b)
    b.new_flags = []
    assert service.inputs_hash(a) == service.inputs_hash(b)
    assert b.reaction is not None
    b.reaction.move = Decimal("0.07")
    assert service.inputs_hash(a) != service.inputs_hash(b)


def _stored(content: dict[str, Any]) -> EarningsBrief:
    return EarningsBrief(version=1, content=content)


def test_inputs_labels_name_what_changed() -> None:
    v1 = _brief().model_dump(mode="json")
    assert service.inputs_label("brief", None, v1) == "after earnings release"
    assert service.inputs_label("preview", None, v1) == "first preview"
    with_10q = {**v1, "what_changed": {"filing_id": 1}}
    assert service.inputs_label("brief", None, with_10q) == "after 10-Q filed"
    assert service.inputs_label("brief", _stored(v1), with_10q) == "after 10-Q filed"
    q4 = {**with_10q, "header": {**v1["header"], "fiscal_period": "Q4"}}
    assert service.inputs_label("brief", _stored(v1), q4) == "after 10-K filed"
    moved = {**v1, "reaction": {**v1["reaction"], "move": "0.08"}}
    assert service.inputs_label("brief", _stored(v1), moved) == "updated: reaction"
    assert service.inputs_label("brief", _stored(v1), v1) == "updated"


# --- wording guards (FR-EB-011, AGT-EB-002) -----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "We expect revenue to beat.",
        "The company is likely to beat its guidance.",
        "Shares should rally after the print.",
        "The outlook for the stock is bright.",
        "Margins will rise next quarter.",
        "The stock is poised to climb.",
    ],
)
def test_predictions_are_caught(text: str) -> None:
    assert predicts(text)


def test_every_brief_template_is_free_of_prediction_and_advice() -> None:
    """FR-EB-011: banned-phrase check over every fixed sentence a brief can show."""
    event = brief_event(
        brief_id=1,
        ticker="NVDA",
        company_id=1,
        period=(2027, "Q3"),
        kind="preview",
        at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    templates = [
        *_ORIGINALS,
        "Revenue growth slowed to 55.6% year over year in Q2 FY2027, from 69.2% in Q1 FY2027.",
        "The 10-Q filed 2026-08-26 adds a risk factor not in the prior 10-Q: “X”.",
        event.title,
        event.body,
        *KIND_LABEL.values(),
        service.SCOPE,
        *[text for _, text, _ in narrative.lines(_brief())],
        "10-Q not yet filed.",
        "No price data around the earnings 8-K yet.",
        "No summary sentence passed verification.",
    ]
    for text in templates:
        assert not predicts(text), text
        assert not contains_advice(text), text
