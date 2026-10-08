#!/usr/bin/env python3
"""Run the evaluation harness (spec §18.5/§18.6).

    uv run python ../scripts/run_eval.py                 # full golden set, persist, print summary
    uv run python ../scripts/run_eval.py --smoke --gate  # smoke subset, fail on regression (CI)
    uv run python ../scripts/run_eval.py --update-baseline

Offline/mock mode gives meaningful numbers only for the deterministic metrics (numeric answer
accuracy, abstention, citation presence, hallucination). Retrieval Recall@K and judge faithfulness
need live Voyage + an LLM key (PROVIDER_MODE=live, ADR-0009/0010); otherwise they compute but are
not a quality signal (ADR-0020). A real judge is used when an LLM key is present; else FakeJudge.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.db import session_scope
from app.eval.dataset import load_golden
from app.eval.gate import check_gate, load_baseline, save_baseline
from app.eval.judge import JUDGE_PROMPT_VERSION, FakeJudge, Judge, LLMJudge
from app.eval.runner import config_hash, persist_run, run_eval
from app.providers import get_llm_client

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
_SMOKE = _BACKEND / "tests" / "eval" / "smoke.jsonl"


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()  # noqa: S607
    except Exception:
        return None


def _judge() -> Judge:
    # A real judge only when a model key is configured; otherwise deterministic FakeJudge.
    if os.environ.get("PROVIDER_MODE") == "live":
        return LLMJudge(get_llm_client(), model=get_settings().llm_model_strong)
    return FakeJudge()


def main() -> int:
    parser = argparse.ArgumentParser(description="InvestiLens evaluation runner")
    parser.add_argument("--smoke", action="store_true", help="run the small smoke subset")
    parser.add_argument("--gate", action="store_true", help="fail if metrics regress vs baseline")
    parser.add_argument("--update-baseline", action="store_true", help="write the new baseline")
    parser.add_argument("--user-id", type=int, default=1)
    args = parser.parse_args()

    settings = get_settings()
    questions = load_golden(_SMOKE if args.smoke else None)
    judge = _judge()

    with session_scope() as session:
        summary = run_eval(
            session, questions, user_id=args.user_id, llm=get_llm_client(), judge=judge
        )
        run_id = persist_run(
            session,
            summary,
            name="smoke" if args.smoke else "full",
            config_hash=config_hash(settings, judge_version=JUDGE_PROMPT_VERSION),
            git_sha=_git_sha(),
        )

    print(f"eval run {run_id} ({summary.n} questions):")
    print(json.dumps(summary.metrics, indent=2, sort_keys=True, default=str))

    if args.update_baseline:
        save_baseline(summary.metrics)
        print("baseline updated")

    if args.gate:
        result = check_gate(summary.metrics, load_baseline())
        if not result:
            print("GATE FAILED:", "; ".join(result.failures), file=sys.stderr)
            return 1
        print("gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
