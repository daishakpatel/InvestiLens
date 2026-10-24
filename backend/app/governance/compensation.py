"""Summary Compensation Table and CEO pay ratio, parsed and validated (Tier B, FR-GV-005/006).

Pure functions over the proxy's HTML and text. Nothing is ever "fixed": a Summary Compensation
Table row whose components do not add up to its Total (within $1 of rounding) is rejected and
reported, and a pay ratio is kept only if median pay x ratio is within 2% of the CEO's total.

The table is read as a grid with `rowspan` and `colspan` expanded, so a value belongs to the
header whose columns it falls under, whatever spacer and "$" cells the filer used. A footnote
marker in its own cell ("6", "(3)(4)") is ignored; a dash is a reported zero.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from selectolax.parser import Node

from app.ingestion.documents.clean import clean_tree

# Header text -> component, first match wins (pension before "compensation", etc.).
_COLUMNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("non_equity_incentive", re.compile(r"non-?equity|incentive plan", re.I)),
    ("pension_nqdc", re.compile(r"pension|deferred compensation", re.I)),
    ("all_other", re.compile(r"all other", re.I)),
    ("option_awards", re.compile(r"option", re.I)),
    ("stock_awards", re.compile(r"stock awards?|restricted stock|performance share", re.I)),
    ("bonus", re.compile(r"\bbonus", re.I)),
    ("salary", re.compile(r"\bsalary", re.I)),
    ("total", re.compile(r"^total", re.I)),
    ("year", re.compile(r"\byear\b|fiscalyear", re.I)),
    ("name", re.compile(r"\bname\b", re.I)),
)
COMPONENTS = (
    "salary",
    "bonus",
    "stock_awards",
    "option_awards",
    "non_equity_incentive",
    "pension_nqdc",
    "all_other",
)
_MONEY = re.compile(r"^\(?\$?\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?\)?$")
_DASH = {"\u2014", "\u2013", "-"}  # em dash, en dash, hyphen: a reported zero
# "6", "(3)(4)": a footnote marker, not a value. A bare number is a marker only up to two digits.
_FOOTNOTE = re.compile(r"^(\d{1,2}|(\(\d{1,2}\))+)$")
_YEAR = re.compile(r"^(19|20)\d{2}$")
_LABEL_FOOTNOTE = re.compile(r"\s+\(?\d{1,2}\)?(?=\s|,|$)")
_CFO = re.compile(r"chief financial officer|\bcfo\b", re.I)
SUM_TOLERANCE = Decimal(1)  # dollars: the table rounds each cell, not the total
RATIO_TOLERANCE = Decimal("0.02")  # median x ratio vs CEO total: disclosure rounding


@dataclass(frozen=True)
class CompRow:
    person: str  # name and position as printed, footnote markers removed
    year: int
    components: dict[str, Decimal]  # reported components; a dash is 0, an absent column absent
    total: Decimal
    role: str = "neo"  # peo | pfo | neo


@dataclass
class SctParse:
    rows: list[CompRow] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)  # "<person> <year>: <why>"
    table_index: int | None = None  # position among the document's tables (chunk table_id)


def _children(node: Node, tags: tuple[str, ...]) -> list[Node]:
    return [child for child in node.iter(include_text=False) if child.tag in tags]


def _rows(table: Node) -> list[Node]:
    rows: list[Node] = []
    for child in table.iter(include_text=False):
        if child.tag == "tr":
            rows.append(child)
        elif child.tag in ("thead", "tbody", "tfoot"):
            rows.extend(_children(child, ("tr",)))
    return rows


def grid(table: Node) -> list[list[str | None]]:
    """The table as a grid: a colspan's extra columns are None, a rowspan's later rows ""."""
    out: list[list[str | None]] = []
    carried: dict[int, int] = {}  # column -> rows a rowspan still covers
    for tr in _rows(table):
        row: list[str | None] = []
        for cell in _children(tr, ("td", "th")):
            while carried.get(len(row), 0) > 0:
                carried[len(row)] -= 1
                row.append("")
            text = " ".join(cell.text(separator=" ").split())
            span = max(1, int(cell.attributes.get("colspan") or 1))
            down = max(1, int(cell.attributes.get("rowspan") or 1))
            for offset in range(span):
                if down > 1:
                    carried[len(row)] = down - 1
                row.append(text if offset == 0 else None)
        while carried.get(len(row), 0) > 0:
            carried[len(row)] -= 1
            row.append("")
        out.append(row)
    return out


def _column(text: str) -> str | None:
    for key, pattern in _COLUMNS:
        if pattern.search(text):
            return key
    return None


def _header(rows: list[list[str | None]]) -> tuple[int, list[tuple[int, int, str]]] | None:
    """(header row index, [(first col, end col, column key)]) of the Summary Compensation Table."""
    for index, row in enumerate(rows):
        texts = [c for c in row if c]
        keys = [_column(c) for c in texts]
        if {"salary", "total", "year"} <= set(keys):
            spans: list[tuple[int, int, str]] = []
            starts = [col for col, cell in enumerate(row) if cell is not None and cell != ""]
            for position, col in enumerate(starts):
                key = _column(str(row[col]))
                end = starts[position + 1] if position + 1 < len(starts) else len(row) + 8
                if key:
                    spans.append((col, end, key))
            return index, spans
    return None


def find_sct(html: str, *, peo_names: Sequence[str] = ()) -> SctParse:
    """The Summary Compensation Table: the first table with Year, Salary and Total headers whose
    rows validate. A proxy can have several such tables (JPMorgan's "pay decisions" table comes
    first), so a table where no row adds up is passed over; if none validates, the first
    candidate's rejections are returned. `table_index` counts the cleaned document's tables, as
    the chunker numbers them (`table_id`), so the source is the table chunk (FR-GV-005)."""
    first: SctParse | None = None
    for index, table in enumerate(clean_tree(html).css("table")):
        rows = grid(table)
        if _header(rows) is None:
            continue
        parsed = parse_sct(rows, peo_names=peo_names)
        parsed.table_index = index
        if parsed.rows:
            return parsed
        first = first or parsed
    return first or SctParse()


def _amount(text: str) -> Decimal | None:
    if text in _DASH:
        return Decimal(0)
    match = _MONEY.match(text)
    if match is None:
        return None
    try:
        value = Decimal(match.group(1).replace(",", "") + (match.group(2) or ""))
    except InvalidOperation:  # pragma: no cover - the pattern only admits digits
        return None
    return -value if text.startswith("(") else value


def parse_sct(rows: list[list[str | None]], *, peo_names: Sequence[str] = ()) -> SctParse:
    """Rows of the Summary Compensation Table that add up (FR-GV-005, DR-GV-001)."""
    result = SctParse()
    found = _header(rows)
    if found is None:
        return result
    header_index, spans = found

    def key_at(col: int) -> str | None:
        return next((key for start, end, key in spans if start <= col < end), None)

    # Pass 1: each data row's label, year and values, grouped by officer. Years run newest
    # first within an officer, so a year that does not fall starts the next officer.
    parsed: list[tuple[int, int, dict[str, list[Decimal]]]] = []  # (group, year, values)
    group_labels: list[list[str]] = []
    previous_year: int | None = None
    pending: list[str] = []  # a name printed on its own row, above the officer's first year (AMD)
    for row in rows[header_index + 1 :]:
        values: dict[str, list[Decimal]] = {}
        label_parts: list[str] = []
        year: int | None = None
        for col, cell in enumerate(row):
            if not cell or cell == "$" or (_FOOTNOTE.match(cell) and not _YEAR.match(cell)):
                continue
            key = key_at(col)
            if key == "year" and _YEAR.match(cell):
                year = int(cell)
            elif key == "name":
                label_parts.append(cell)
            elif key is not None and (amount := _amount(cell)) is not None:
                values.setdefault(key, []).append(amount)
        label = _LABEL_FOOTNOTE.sub("", " ".join(label_parts)).strip()
        if year is None:
            if label and not values:
                pending.append(label)
            continue  # otherwise a spacer, sub-header or footnote row
        starts = (label or pending) and (previous_year is None or year >= previous_year)
        if not group_labels or starts:
            group_labels.append(pending)
            pending = []
        if label:
            group_labels[-1].append(label)  # the name, then position lines under it
        parsed.append((len(group_labels) - 1, year, values))
        previous_year = year

    # Pass 2: validate each row against its total; never repair one.
    for group, year, values in parsed:
        person = " ".join(group_labels[group])
        name = f"{person} {year}"
        if any(len(found) > 1 for found in values.values()):
            result.rejected.append(f"{name}: two values under one column")
            continue
        total = values.get("total", [None])[0]
        if total is None:
            result.rejected.append(f"{name}: no total")
            continue
        components = {k: v[0] for k, v in values.items() if k in COMPONENTS}
        reported = sum(components.values(), Decimal(0))
        if abs(reported - total) > SUM_TOLERANCE:
            result.rejected.append(f"{name}: components {reported} != total {total}")
            continue
        result.rows.append(CompRow(person, year, components, total))
    result.rows = _with_roles(result.rows, peo_names)
    return result


_HONORIFICS = {"mr", "mrs", "ms", "dr", "jr", "sr", "ii", "iii"}


def _name_tokens(text: str) -> set[str]:
    """Name words, case-folded, without titles or initials: "Dr. Lisa T. Su" -> {lisa, su}."""
    return {
        t for t in re.findall(r"[a-z]+", text.casefold()) if len(t) > 1 and t not in _HONORIFICS
    }


def _with_roles(rows: list[CompRow], peo_names: Sequence[str]) -> list[CompRow]:
    """The PEO is the officer the proxy's XBRL names most often as `ecd:PeoName` (some filers tag
    other officers' names with it too), matched on name words; else the first officer listed,
    the SEC's order. The PFO is the first current officer titled chief financial officer."""
    people = list(dict.fromkeys(r.person for r in rows))
    named = Counter(n for n in peo_names if _name_tokens(n)).most_common(1)
    wanted = _name_tokens(named[0][0]) if named else set()
    peo = next((p for p in people if wanted and wanted <= _name_tokens(p)), None)
    peo = peo or (people[0] if people else None)
    pfo = next((p for p in people if _CFO.search(p) and "former" not in p.casefold()), None)

    def role(person: str) -> str:
        return "peo" if person == peo else "pfo" if person == pfo else "neo"

    return [CompRow(r.person, r.year, r.components, r.total, role(r.person)) for r in rows]


# --- CEO pay ratio (FR-GV-006) ----------------------------------------------------------------
_RATIO = re.compile(r"\b(\d{1,3}(?:,\d{3})*)\s*(?::|to)\s*1\b")
# "median employee was $111,905": the amount closest after "median" in the same sentence.
_MEDIAN_PAY = re.compile(
    r"\bmedian\b[^.$]{0,160}?\$\s*(\d[\d,]*(?:\.\d+)?)(?!\s*(?:million|billion))", re.I
)


@dataclass(frozen=True)
class PayRatio:
    ratio: Decimal
    median_pay: Decimal
    ceo_total: Decimal
    paragraph_id: str


def find_pay_ratio(paragraphs: Sequence[tuple[str, str]], ceo_total: Decimal) -> PayRatio | None:
    """The disclosed ratio and median pay, kept only if median x ratio within 2% of the CEO total.

    Each paragraph is read with the one before it, because filers often state the median pay
    and the ratio in consecutive bullets.
    """
    previous = ""
    for paragraph_id, text in paragraphs:
        window = " ".join(f"{previous} {text}".split())
        previous = text
        for match in _RATIO.finditer(window):
            medians = list(_MEDIAN_PAY.finditer(window[: match.start()]))
            if not medians:
                continue
            ratio = Decimal(match.group(1).replace(",", ""))
            median = Decimal(medians[-1].group(1).replace(",", ""))
            if ratio > 0 and abs(median * ratio - ceo_total) <= ceo_total * RATIO_TOLERANCE:
                return PayRatio(ratio, median, ceo_total, paragraph_id)
    return None
