"""CI regression gate (EVAL-002, spec §18.6). Compare a run's metrics to a stored baseline and
fail if quality regresses beyond the allowed drift. Points are percentage points (0.02 = 2 pts).

Defaults (from the task): Recall@5 may drop ≤ 2 pts, citation accuracy ≤ 1 pt, hallucination may
rise ≤ 0.5 pts. A metric missing from either side is skipped (not a failure), so the gate works
offline where retrieval/faithfulness are not meaningful.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_BASELINE_PATH = Path(__file__).resolve().parent / "baseline.json"

RECALL_MAX_DROP = 0.02
CITATION_MAX_DROP = 0.01
HALLUCINATION_MAX_RISE = 0.005


@dataclass
class GateResult:
    passed: bool
    failures: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


def _drop(baseline: dict[str, Any], current: dict[str, Any], key: str) -> float | None:
    b, c = baseline.get(key), current.get(key)
    if b is None or c is None:
        return None
    return float(b) - float(c)  # positive = regression (current lower)


def check_gate(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    recall_key: str = "recall_at_5",
) -> GateResult:
    failures: list[str] = []

    recall_drop = _drop(baseline, current, recall_key)
    if recall_drop is not None and recall_drop > RECALL_MAX_DROP:
        failures.append(f"{recall_key} dropped {recall_drop:.3f} > {RECALL_MAX_DROP}")

    cite_drop = _drop(baseline, current, "citation_accuracy")
    if cite_drop is not None and cite_drop > CITATION_MAX_DROP:
        failures.append(f"citation_accuracy dropped {cite_drop:.3f} > {CITATION_MAX_DROP}")

    # Hallucination rising is a regression → invert the drop sign.
    hall_rise = _drop(current, baseline, "hallucination_rate")
    if hall_rise is not None and hall_rise > HALLUCINATION_MAX_RISE:
        failures.append(f"hallucination_rate rose {hall_rise:.3f} > {HALLUCINATION_MAX_RISE}")

    return GateResult(passed=not failures, failures=failures)


def load_baseline(path: Path | None = None) -> dict[str, Any]:
    p = path or _BASELINE_PATH
    return json.loads(p.read_text()) if p.exists() else {}


def save_baseline(metrics: dict[str, Any], path: Path | None = None) -> None:
    (path or _BASELINE_PATH).write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
