#!/usr/bin/env python3
"""Fail when the README, docs and code disagree (Phase 7l Part D, NFR-ME-011). Run by make check.

Rules, each a pure function with a failing-case test (backend/tests/unit/test_docs_consistency.py):
1. every requirement ID cited in tests or docs exists in the spec;
2. every API route the README names exists in docs/openapi.json;
3. every numeric claim in the README is a value in docs/eval/latest.json or
   docs/generated/stats.json (dates, code, links and IDs are not claims);
4. ADR numbers are unique and contiguous from 0001;
5. every task file named in Instructions/00_START_HERE.md exists;
6. docs/generated/stats.json and the README's generated blocks are current (scripts/stats.py).
Standard library only.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

_REQ_ID = re.compile(r"\b(?:FR|NFR|DR|SEC|CIT|RAG|AGT)(?:-[A-Z]{2,4})?-\d{3}\b")
_ROUTE = re.compile(r"`(GET|POST|PUT|PATCH|DELETE) (/[^`\s]*)`")
_FENCE = re.compile(r"```.*?```", re.S)
_CODE = re.compile(r"`[^`]*`")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LINK_TARGET = re.compile(r"\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_LIST_MARKER = re.compile(r"^\s*\d+\.\s", re.M)
_NUMBER = re.compile(r"(?<![\w./#@-])(\d+(?:\.\d+)?%?)(?![\w/-])")  # hit@5 is a name
_ADR = re.compile(r"^(\d{4})-.+\.md$")
_TASK = re.compile(r"\b(\d{2}_[a-z0-9_]+\.md)\b")


# --- rule 1 --------------------------------------------------------------------------------
def unknown_requirement_ids(spec: str, documents: Mapping[str, str]) -> list[str]:
    known = set(_REQ_ID.findall(spec))
    problems = []
    for name, text in sorted(documents.items()):
        for rid in sorted(set(_REQ_ID.findall(text)) - known):
            problems.append(f"{name}: requirement {rid} is not in docs/AssayDesk_Spec_v2.md")
    return problems


# --- rule 2 --------------------------------------------------------------------------------
def missing_routes(readme: str, openapi: Mapping[str, Any], prefix: str = "/api/v1") -> list[str]:
    paths = openapi.get("paths", {})
    problems = []
    for method, path in _ROUTE.findall(readme):
        ops = paths.get(prefix + path, {})
        if method.lower() not in ops:
            problems.append(f"README names `{method} {path}`, which is not in docs/openapi.json")
    return problems


# --- rule 3 --------------------------------------------------------------------------------
def _flatten(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        for v in value.values():
            yield from _flatten(v)
    elif isinstance(value, list):
        for v in value:
            yield from _flatten(v)
    else:
        yield value


def allowed_numbers(*sources: Mapping[str, Any]) -> set[str]:
    """Every way a generated value may be written: integers as-is, ratios as one-decimal
    percentages, latencies rounded to whole milliseconds."""
    allowed: set[str] = set()
    for source in sources:
        for value in _flatten(source):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if isinstance(value, int):
                allowed.add(str(value))
            else:
                allowed.add(f"{value * 100:.1f}%")
                allowed.add(f"{value:.0f}")
                allowed.add(str(value))
    return allowed


def prose_of(markdown: str) -> str:
    """The README with code, comments, link targets, URLs, dates and list markers removed."""
    text = _FENCE.sub(" ", markdown)
    for pattern in (_COMMENT, _CODE, _LINK_TARGET, _URL, _DATE, _LIST_MARKER):
        text = pattern.sub(" ", text)
    return text


def unbacked_numbers(readme: str, allowed: set[str]) -> list[str]:
    return [
        f"README states {num!r}, which is not in docs/eval/latest.json or docs/generated/stats.json"
        for num in sorted(set(_NUMBER.findall(prose_of(readme))))
        if num not in allowed
    ]


# --- rule 4 --------------------------------------------------------------------------------
def adr_numbering_problems(filenames: Iterable[str]) -> list[str]:
    numbers = [int(m.group(1)) for name in filenames if (m := _ADR.match(name))]
    numbers = [n for n in numbers if n != 0]  # 0000 is the template
    problems = [
        f"ADR-{n:04d} is used more than once" for n in sorted(set(numbers)) if numbers.count(n) > 1
    ]
    present = set(numbers)
    problems += [
        f"ADR-{n:04d} is missing (numbers must not skip)"
        for n in range(1, max(present, default=0) + 1)
        if n not in present
    ]
    return problems


# --- rule 5 --------------------------------------------------------------------------------
def missing_task_files(start_here: str, existing: set[str]) -> list[str]:
    return [
        f"Instructions/00_START_HERE.md names {name}, which does not exist"
        for name in sorted(set(_TASK.findall(start_here)))
        if name not in existing
    ]


# --- wiring --------------------------------------------------------------------------------
def _read_documents() -> dict[str, str]:
    globs = ("backend/tests/**/*.py", "frontend/src/**/*.test.ts", "e2e/tests/*.ts", "docs/**/*.md")
    docs: dict[str, str] = {}
    for pattern in globs:
        for path in ROOT.glob(pattern):
            if path.name == "AssayDesk_Spec_v2.md" or "node_modules" in path.parts:
                continue
            docs[str(path.relative_to(ROOT))] = path.read_text(errors="ignore")
    return docs


def main() -> int:
    readme = (ROOT / "README.md").read_text()
    spec = (ROOT / "docs" / "AssayDesk_Spec_v2.md").read_text()
    openapi = json.loads((ROOT / "docs" / "openapi.json").read_text())
    report = json.loads((ROOT / "docs" / "eval" / "latest.json").read_text())
    stats = json.loads((ROOT / "docs" / "generated" / "stats.json").read_text())
    instructions = ROOT / "Instructions"

    problems = [
        *unknown_requirement_ids(spec, _read_documents()),
        *missing_routes(readme, openapi),
        *unbacked_numbers(readme, allowed_numbers(report, stats)),
        *adr_numbering_problems(p.name for p in (ROOT / "docs" / "decisions").glob("*.md")),
        *missing_task_files(
            (instructions / "00_START_HERE.md").read_text(),
            {p.name for p in instructions.rglob("*.md")},
        ),
    ]
    stale = subprocess.run(  # noqa: S603  # rule 6: our own script, fixed arguments
        [sys.executable, str(ROOT / "scripts" / "stats.py"), "--check"], check=False
    )
    for problem in problems:
        print(f"docs: {problem}", file=sys.stderr)
    if problems or stale.returncode:
        return 1
    print("docs: consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
