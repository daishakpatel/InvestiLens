"""Table extraction: filing HTML tables -> structured rows + Markdown + caption (CH-003)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from selectolax.parser import Node

_UNIT_HINT = re.compile(r"(?i)in (thousands|millions|billions)")
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


@dataclass
class ExtractedTable:
    table_id: str
    rows: list[list[str]]  # all rows including header, cells as cleaned strings
    header: list[str] = field(default_factory=list)
    row_labels: list[str] = field(default_factory=list)
    caption: str = ""
    markdown: str = ""

    @property
    def cell_refs(self) -> list[str]:
        return [f"r{r}c{c}" for r, row in enumerate(self.rows) for c, v in enumerate(row) if v]


def _cell_text(cell: Node) -> str:
    return " ".join((cell.text(deep=True) or "").split())


def extract_table(node: Node, table_id: str, *, context: str = "") -> ExtractedTable:
    """Extract a <table> into structured rows, a Markdown rendering, and a caption."""
    rows: list[list[str]] = []
    for tr in node.css("tr"):
        cells = [_cell_text(c) for c in tr.css("td,th")]
        if any(cells):  # skip spacer rows
            rows.append(cells)
    header = rows[0] if rows else []
    row_labels = [r[0] for r in rows[1:] if r]
    table = ExtractedTable(table_id=table_id, rows=rows, header=header, row_labels=row_labels)
    table.caption = _caption(rows, context)
    table.markdown = _to_markdown(rows)
    return table


def _caption(rows: list[list[str]], context: str) -> str:
    years = sorted({m.group(0) for row in rows[:2] for cell in row for m in _YEAR.finditer(cell)})
    unit = ""
    for row in rows[:3]:
        for cell in row:
            hit = _UNIT_HINT.search(cell)
            if hit:
                unit = f", in {hit.group(1)}"
                break
    span = f", {years[0]}-{years[-1]}" if len(years) > 1 else (f", {years[0]}" if years else "")
    base = context.strip() or "Financial table"
    return f"{base}{span}{unit}".strip()


def _to_markdown(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    padded = [r + [""] * (width - len(r)) for r in rows]
    lines = [
        "| " + " | ".join(c.replace("|", r"\|") for c in padded[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines += ["| " + " | ".join(c.replace("|", r"\|") for c in row) + " |" for row in padded[1:]]
    return "\n".join(lines)
