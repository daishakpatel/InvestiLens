#!/usr/bin/env python3
"""CI gate for the committed evaluation report (Phase 7l, NFR-ME-004).

Fails when a metric in docs/eval/latest.json breaches docs/eval/thresholds.json, or when the
report is stale: the chat, citation, retrieval, prompt or golden-set code it measured has
changed since it was generated. Fix by running `make eval-report` (needs Postgres).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))

from app.eval.published import gate_failures  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Check docs/eval/latest.json against thresholds")
    parser.add_argument("--report", type=Path, default=_ROOT / "docs" / "eval" / "latest.json")
    parser.add_argument(
        "--thresholds", type=Path, default=_ROOT / "docs" / "eval" / "thresholds.json"
    )
    args = parser.parse_args()
    if not args.report.exists():
        print(f"eval gate: {args.report} is missing; run `make eval-report`", file=sys.stderr)
        return 1
    failures = gate_failures(
        json.loads(args.report.read_text()), json.loads(args.thresholds.read_text()), _ROOT
    )
    for failure in failures:
        print(f"eval gate: {failure}", file=sys.stderr)
    if not failures:
        print("eval gate: passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
