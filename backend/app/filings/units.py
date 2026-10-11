"""Rebuild comparable units (risk factors, sub-sections) from Phase 2a chunks (§37.4).

Chunks are retrieval-sized, not risk-factor-sized, so diffing chunk-to-chunk would report a change
whenever a page break moved. This walks a filing's text chunks paragraph by paragraph and regroups
them under their headings — no re-parsing, no re-chunking. Each unit keeps the `paragraph_id`s of
the chunks it came from, which are the backend-issued source IDs (CIT-001) the diff cites.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal

from app.ingestion.documents.clean import clean_tree
from app.models import DocumentChunk

RISK_SECTION = "Item 1A"
_SUBHEADING_MAX_CHARS = 140  # same bound the chunker uses for sub-headings (CH-002)
_RISK_HEADING_MAX_CHARS = 400
_SENTENCE_BREAK = re.compile(r"[.!?]\s+[A-Z]")
# Openers of one-sentence *body* paragraphs ("In July 2023, …", "Any of these could …"), which a
# risk-factor caption never starts with.
_BODY_OPENER = re.compile(
    r"^(in|over|for|during|as|on|at|additionally|further|furthermore|moreover|however|these|this|"
    r"such|any|while|although|since|recently|also|there|see|refer)\b",
    re.I,
)
_NOISE = re.compile(r"^(table of conten\w*|risk factors?( summary)?)$", re.I)  # page furniture

_WORD = re.compile(r"\w+")
_DIGIT = re.compile(r"\d")
_EMPHASIS_CSS = ", ".join(
    ["b", "strong", "i", "em"]
    + [
        f"[style*='{prop}:{gap}{value}']"
        for prop, value in (
            ("font-weight", "700"),
            ("font-weight", "bold"),
            ("font-style", "italic"),
        )
        for gap in ("", " ")
    ]
)

UnitKind = Literal["risk_factor", "section"]


def fingerprint(text: str) -> list[str]:
    """Lower-cased words with digits masked, like the chunker's dedup_hash (CH-006): a rolled
    forward year or share count in otherwise identical text is not a wording change."""
    return _WORD.findall(_DIGIT.sub("0", text.lower()))


def emphasized_text(html: str) -> str:
    """Every bold or italic run of a filing, fingerprinted and space-joined, in document order.

    Risk-factor captions are set in bold or italics; the chunks no longer carry styling, so this
    is read from the raw filing to tell a caption from a one-sentence body paragraph.
    """
    runs = (" ".join(fingerprint(node.text())) for node in clean_tree(html).css(_EMPHASIS_CSS))
    return f" {' '.join(run for run in runs if run)} "


@dataclass(frozen=True)
class Paragraph:
    section: str
    text: str
    source_id: str
    is_bullet: bool = False


@dataclass(frozen=True)
class Unit:
    section: str
    heading: str
    text: str  # heading + body
    source_ids: tuple[str, ...]
    kind: UnitKind


def section_key(chunk: DocumentChunk) -> str:
    path = chunk.section_path or []
    return path[0] if path else (chunk.section or "")


def paragraphs(chunks: Iterable[DocumentChunk]) -> Iterator[Paragraph]:
    """Text paragraphs in document order, with chunk-overlap repeats and page furniture removed."""
    previous: tuple[str, str] | None = None  # (section, text) of the last paragraph yielded
    bullet = False
    for chunk in chunks:
        if chunk.chunk_type != "text":
            continue  # tables restate numbers every period: all noise for a wording diff
        section = section_key(chunk)
        source_id = chunk.paragraph_id or f"{chunk.document_id}_{chunk.chunk_index}"
        for index, raw in enumerate(chunk.text.split("\n\n")):
            text = raw.strip()
            if not text or _NOISE.match(text):
                continue
            if text == "•":
                bullet = True
                continue
            # The chunker carries one small tail paragraph into the next chunk (overlap).
            if index == 0 and previous == (section, text):
                continue
            yield Paragraph(section, text, source_id, is_bullet=bullet or text.startswith("•"))
            previous = (section, text)
            bullet = False


def _is_subheading(text: str) -> bool:
    return (
        len(text) <= _SUBHEADING_MAX_CHARS
        and text[0].isupper()
        and not text.endswith((".", ";", ":", ","))
    )


def _is_risk_heading(text: str, emphasized: str | None) -> bool:
    if len(text) > _RISK_HEADING_MAX_CHARS or not text[0].isupper():
        return False
    if emphasized is not None:
        return f" {' '.join(fingerprint(text))} " in emphasized
    # shortcut: with no styling to go on, a caption is taken to be a one-sentence paragraph, which
    # also catches some one-sentence body text; upgrade by keeping emphasis in the chunk metadata.
    return (
        text.endswith(".")
        and not _SENTENCE_BREAK.search(text)
        and not _BODY_OPENER.match(text)
        and not any(ch.isdigit() for ch in text)
    )


def build_units(chunks: Iterable[DocumentChunk], emphasized: str | None = None) -> list[Unit]:
    """Group a filing's paragraphs into heading-led units, in document order.

    `emphasized` is the filing's `emphasized_text`; without it risk captions are guessed.
    """
    units: list[Unit] = []
    section: str | None = None
    heading = ""
    body: list[str] = []
    sources: list[str] = []
    heading_only = True
    is_label = False  # current heading is a short sub-heading rather than a risk caption
    all_bullets = True

    def flush() -> None:
        # A heading with nothing under it is a group label ("Risks Related to …"), not a unit; a
        # risk-section label followed only by bullets is the Risk Factors Summary restating the
        # captions, which would otherwise double-report every change.
        if section is None or heading_only:
            return
        if section == RISK_SECTION and is_label and all_bullets:
            return
        units.append(
            Unit(
                section=section,
                heading=heading,
                text="\n\n".join(body),
                source_ids=tuple(dict.fromkeys(sources)),
                kind="risk_factor" if section == RISK_SECTION else "section",
            )
        )

    for para in paragraphs(chunks):
        new_section = para.section != section
        subheading = not para.is_bullet and _is_subheading(para.text)
        starts_unit = subheading or (
            not para.is_bullet
            and para.section == RISK_SECTION
            and _is_risk_heading(para.text, emphasized)
            # A one-sentence paragraph directly under a risk caption is its body, not a new one.
            and not (heading_only and section is not None and not is_label)
        )
        if new_section or starts_unit:
            flush()
            section = para.section
            heading = para.text if starts_unit else para.section
            body, sources = [para.text], [para.source_id]
            heading_only, is_label, all_bullets = starts_unit, subheading, True
            continue
        body.append(para.text)
        sources.append(para.source_id)
        heading_only = False
        all_bullets = all_bullets and para.is_bullet
    flush()
    return units
