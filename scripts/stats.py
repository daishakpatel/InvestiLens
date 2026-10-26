#!/usr/bin/env python3
"""Generate docs/generated/stats.json and the README's generated blocks (Phase 7l, NFR-ME-011).

    python3 scripts/stats.py           # write stats.json and refresh the README blocks
    python3 scripts/stats.py --check   # exit 1 if either is out of date (run by make check)

Counts come from the files themselves, so the README never carries a hand-typed number: test
functions (backend `def test_`, frontend/e2e `it(`/`test(`), API operations in openapi.json,
ADRs, seed companies, and non-blank lines of code by area. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "docs" / "generated" / "stats.json"
README = ROOT / "README.md"
EVAL = ROOT / "docs" / "eval" / "latest.json"

_METHODS = {"get", "post", "put", "patch", "delete"}
_PY_TEST = re.compile(r"^\s*(?:async\s+)?def test_", re.M)
_TS_TEST = re.compile(r"^\s*(?:it|test)\(", re.M)
_LOC_AREAS = {
    "backend_app": ("backend/app", (".py",)),
    "backend_tests": ("backend/tests", (".py",)),
    "frontend_src": ("frontend/src", (".ts", ".tsx")),
    "e2e": ("e2e/tests", (".ts",)),
    "scripts": ("scripts", (".py", ".sh")),
}


def _files(rel: str, suffixes: tuple[str, ...]) -> list[Path]:
    base = ROOT / rel
    return sorted(
        p
        for p in base.rglob("*")
        if p.is_file() and p.suffix in suffixes and "node_modules" not in p.parts
    )


def _count(pattern: re.Pattern[str], paths: list[Path]) -> int:
    return sum(len(pattern.findall(p.read_text(errors="ignore"))) for p in paths)


def compute() -> dict[str, Any]:
    backend = _count(_PY_TEST, _files("backend/tests", (".py",)))
    frontend = _count(
        _TS_TEST, [p for p in _files("frontend/src", (".ts", ".tsx")) if ".test." in p.name]
    )
    e2e = _count(
        _TS_TEST, [p for p in _files("e2e/tests", (".ts",)) if p.name.endswith(".spec.ts")]
    )
    openapi = json.loads((ROOT / "docs" / "openapi.json").read_text())
    endpoints = sum(1 for ops in openapi["paths"].values() for m in ops if m in _METHODS)
    adrs = len(
        [
            p
            for p in (ROOT / "docs" / "decisions").glob("[0-9][0-9][0-9][0-9]-*.md")
            if not p.name.startswith("0000")
        ]
    )
    seed = re.search(r"_SEED\s*=\s*\[([^\]]*)\]", (ROOT / "scripts" / "seed_demo.py").read_text())
    seed_companies = len(re.findall(r'"[A-Z.]+"', seed.group(1))) if seed else 0
    loc = {
        area: sum(
            1
            for p in _files(rel, suffixes)
            for line in p.read_text(errors="ignore").splitlines()
            if line.strip()
        )
        for area, (rel, suffixes) in _LOC_AREAS.items()
    }
    return {
        "generated_by": "make stats",
        "tests": {
            "backend": backend,
            "frontend": frontend,
            "e2e": e2e,
            "total": backend + frontend + e2e,
        },
        "endpoints": endpoints,
        "adrs": adrs,
        "seed_companies": seed_companies,
        "loc": loc,
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def results_block(report: dict[str, Any]) -> str:
    """The README's measured-results table, from docs/eval/latest.json."""
    m = report["metrics"]
    rows = [
        ("Citation validity", "citation_validity"),
        ("Number match", "number_match"),
        ("Correct abstention", "correct_abstention"),
        ("False abstention (lower is better)", "false_abstention"),
        ("Retrieval hit@5", "retrieval_hit_at_5"),
        ("Injection resistance", "injection_resistance"),
    ]
    lines = [
        f"Mock-LLM run of {report['n_cases']} golden questions on "
        f"{report['generated_at'][:10]} ([full report](docs/eval/latest.md), with what it does "
        "not cover).",
        "",
        "| Metric | Measured | Wilson interval | n |",
        "|---|---|---|---|",
    ]
    for label, key in rows:
        b = m[key]
        lo, hi = b["ci95"] or (None, None)
        lines.append(f"| {label} | {_pct(b['value'])} | {_pct(lo)} to {_pct(hi)} | {b['n']} |")
    return "\n".join(lines)


def stats_block(stats: dict[str, Any]) -> str:
    t = stats["tests"]
    return (
        f"{t['backend']} backend and {t['frontend']} frontend test functions, {t['e2e']} "
        f"Playwright tests, {stats['endpoints']} API operations and {stats['adrs']} ADRs "
        "([generated](docs/generated/stats.json))."
    )


def _replace_block(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- generated:{name} -->\n).*?(<!-- /generated:{name} -->)", re.S)
    return pattern.sub(lambda mt: mt.group(1) + body + "\n" + mt.group(2), text)


def render_readme(readme: str, stats: dict[str, Any], report: dict[str, Any]) -> str:
    readme = _replace_block(readme, "results", results_block(report))
    return _replace_block(readme, "stats", stats_block(stats))


def comparable(stats: dict[str, Any]) -> dict[str, Any]:
    """Everything but lines of code, which move with every edit and back no README claim."""
    return {k: v for k, v in stats.items() if k != "loc"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate docs/generated/stats.json")
    parser.add_argument("--check", action="store_true", help="fail if stats or README are stale")
    args = parser.parse_args()

    stats = compute()
    report = json.loads(EVAL.read_text())
    readme = README.read_text()
    fresh_readme = render_readme(readme, stats, report)

    if args.check:
        recorded = json.loads(STATS.read_text()) if STATS.exists() else {}
        problems = []
        if comparable(recorded) != comparable(stats):
            problems.append("docs/generated/stats.json is out of date")
        if fresh_readme != readme:
            problems.append("README generated blocks are out of date")
        for p in problems:
            print(f"stats: {p}; run `make stats`", file=sys.stderr)
        return 1 if problems else 0

    STATS.parent.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(stats, indent=2) + "\n")
    README.write_text(fresh_readme)
    print(json.dumps(comparable(stats), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
