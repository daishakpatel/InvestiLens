"""Filing change detection: align, classify, word-diff (§37.4).

Pure functions over `Unit`s. Alignment is heading-first; whatever is left is paired by similarity,
so a renamed or moved risk factor is still recognised. Only pairs whose similarity falls between
the two thresholds are borderline, and only those may be handed to an adjudicator (an LLM on the
report path, ADR-0027) — everything else is deterministic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import pairwise
from typing import Literal

from app.filings.units import Unit, fingerprint

ChangeStatus = Literal["unchanged", "reworded", "new", "removed"]
DecidedBy = Literal["heading", "similarity", "llm", "threshold"]
DiffOpKind = Literal["equal", "insert", "delete"]

# Similarity of every old text against every new text: result[i][j] in [0, 1].
Similarity = Callable[[Sequence[str], Sequence[str]], list[list[float]]]
# True = same passage reworded, False = different passages, None = could not decide.
Adjudicator = Callable[[Unit, Unit], bool | None]


@dataclass(frozen=True)
class DiffItem:
    status: ChangeStatus
    decided_by: DecidedBy
    old: Unit | None
    new: Unit | None
    similarity: float | None = None  # None for new/removed: there is no counterpart


def lexical_similarity(old: Sequence[str], new: Sequence[str]) -> list[list[float]]:
    """Jaccard overlap of word bigrams. Deterministic and offline; the default (ADR-0027).

    Bigrams rather than single words: any two passages of filing prose share most of their
    vocabulary, but only a reworded passage shares its phrasing.
    """

    def shingles(text: str) -> set[tuple[str, str]]:
        words = fingerprint(text)
        return set(pairwise(words))

    new_sets = [shingles(text) for text in new]
    matrix: list[list[float]] = []
    for text in old:
        mine = shingles(text)
        matrix.append(
            [len(mine & other) / len(mine | other) if mine | other else 0.0 for other in new_sets]
        )
    return matrix


def word_diff(old: str, new: str) -> list[tuple[DiffOpKind, str]]:
    """Word-level edit script from `old` to `new`, as (op, text) runs."""
    a, b = old.split(), new.split()
    ops: list[tuple[DiffOpKind, str]] = []
    # autojunk off: it treats frequent words as junk on long texts and garbles the alignment.
    for tag, a0, a1, b0, b1 in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == "equal":
            ops.append(("equal", " ".join(a[a0:a1])))
            continue
        if tag in ("delete", "replace"):
            ops.append(("delete", " ".join(a[a0:a1])))
        if tag in ("insert", "replace"):
            ops.append(("insert", " ".join(b[b0:b1])))
    return ops


def _paired(old: Unit, new: Unit, decided_by: DecidedBy) -> DiffItem:
    a, b = fingerprint(old.text), fingerprint(new.text)
    if a == b:
        return DiffItem("unchanged", decided_by, old, new, 1.0)
    ratio = SequenceMatcher(None, a, b, autojunk=False).ratio()
    return DiffItem("reworded", decided_by, old, new, round(ratio, 4))


def _heading_key(unit: Unit) -> tuple[str, str]:
    return unit.section, " ".join(fingerprint(unit.heading))


def diff_units(
    old: Sequence[Unit],
    new: Sequence[Unit],
    *,
    similarity: Similarity = lexical_similarity,
    adjudicate: Adjudicator | None = None,
    match_threshold: float = 0.45,
    borderline_threshold: float = 0.20,
) -> list[DiffItem]:
    """Diff two filings' units. Results follow the new filing's order; removals come last."""
    by_new: dict[int, DiffItem] = {}
    removed: list[DiffItem] = []

    # 1. Heading match. Repeated headings in a section ("Income Taxes") pair off in order.
    waiting: dict[tuple[str, str], list[int]] = {}
    for j, unit in enumerate(new):
        waiting.setdefault(_heading_key(unit), []).append(j)
    left_old: list[int] = []
    for i, unit in enumerate(old):
        candidates = waiting.get(_heading_key(unit))
        if candidates:
            j = candidates.pop(0)
            by_new[j] = _paired(unit, new[j], "heading")
        else:
            left_old.append(i)
    left_new = [j for j in range(len(new)) if j not in by_new]

    # 2. Similarity match for whatever moved or was renamed, best pairs first, one-to-one.
    if left_old and left_new:
        matrix = similarity([old[i].text for i in left_old], [new[j].text for j in left_new])
        ranked = sorted(
            (
                (matrix[a][b], i, j)
                for a, i in enumerate(left_old)
                for b, j in enumerate(left_new)
                if matrix[a][b] >= borderline_threshold
            ),
            key=lambda pair: (-pair[0], pair[1], pair[2]),
        )
        used_old: set[int] = set()
        for score, i, j in ranked:
            if i in used_old or j in by_new:
                continue
            decided_by: DecidedBy = "similarity"
            same = True
            if score < match_threshold:
                verdict = adjudicate(old[i], new[j]) if adjudicate else None
                decided_by = "llm" if verdict is not None else "threshold"
                # Unadjudicated borderline pairs are kept together and labelled "threshold": on
                # NVDA's 10-Ks every such pair was a heavily rewritten risk factor, and a wrong
                # "reworded" is cheaper than a false "new risk factor" alert.
                same = verdict if verdict is not None else True
            if same:
                used_old.add(i)
                by_new[j] = _paired(old[i], new[j], decided_by)
        left_old = [i for i in left_old if i not in used_old]

    removed = [DiffItem("removed", "similarity", old[i], None) for i in left_old]
    items = [by_new.get(j) or DiffItem("new", "similarity", None, new[j]) for j in range(len(new))]
    return items + removed
