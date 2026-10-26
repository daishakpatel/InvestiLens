#!/usr/bin/env python3
"""Record the live-model answers the public demo replays (Phase 7l, NFR-ME-009, ADR-0050).

    cd backend && uv run python ../scripts/demo_db.py          # 1. a fresh demo database
    uv run python ../scripts/record_demo_llm.py                # 2. record (live calls, ~4)
    uv run python ../scripts/demo_db.py                        # 3. rebuild: now replays them

Runs the demo's model-backed steps against the local demo database with the live LLM wrapped in
a recorder: NVIDIA's guidance extraction from its latest earnings release, the post-earnings
brief narrative, and the guided path's cited question. Each response is written to
`backend/tests/fixtures/llm_recordings/<key>.json`, keyed by model + exact prompt, which is what
`MockLLMClient` (forced on in demo mode) looks up. Needs an LLM key; spends a few cents. The
answers still pass the citation verifier at replay time; recording only saves the model call.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))

_DEMO_DB = "assay_desk_demo"
_RISK_QUESTION = "What changed in risk factors vs last year?"  # frontend/src/lib/demo.ts


def main() -> int:
    parser = argparse.ArgumentParser(description="Record live-model answers for the demo")
    parser.add_argument("--ticker", default="NVDA")
    args = parser.parse_args()

    from _dbtools import with_database

    from app.config import get_settings

    os.environ["DATABASE_URL"] = with_database(get_settings().database_url, _DEMO_DB)
    os.environ["PROVIDER_MODE"] = "mock"  # fixture data; only the LLM is live
    os.environ["EMBEDDING_PROVIDER"] = "mock"  # the demo's chunks carry offline embeddings
    os.environ["DEMO_MODE"] = "false"  # demo mode would force the replaying mock
    get_settings.cache_clear()

    from sqlalchemy import delete, select

    import app.earnings.service as earnings_service
    import app.guidance.extract as guidance_extract
    from app.auth.demo import demo_user
    from app.chat.service import answer_question
    from app.db import session_scope
    from app.guidance.builder import build_company_guidance
    from app.models import Document, EarningsBrief
    from app.providers import get_llm_client
    from app.providers.base import LLMClient, LLMMessage
    from app.providers.mocks.llm import _RECORDINGS, _key
    from app.repositories import companies as company_repo

    live = get_llm_client()
    written: list[str] = []

    class Recorder(LLMClient):
        def _save(self, messages: Sequence[LLMMessage], model: str, kind: str, out: Any) -> None:
            key = _key(messages, model)
            record = {
                "kind": kind,
                "model": model,
                "prompt_summary": f"demo recording ({args.ticker}): {messages[0].content[:80]}",
                "response": out,
            }
            (_RECORDINGS / f"{key}.json").write_text(json.dumps(record, indent=2) + "\n")
            written.append(key)

        async def complete(
            self, messages: Sequence[LLMMessage], *, model: str, max_tokens: int
        ) -> str:
            out = await live.complete(messages, model=model, max_tokens=max_tokens)
            self._save(messages, model, "text", out)
            return out

        async def complete_json(
            self,
            messages: Sequence[LLMMessage],
            *,
            model: str,
            schema: dict[str, Any],
            max_tokens: int,
        ) -> dict[str, Any]:
            out = await live.complete_json(
                messages, model=model, schema=schema, max_tokens=max_tokens
            )
            self._save(messages, model, "json", out)
            return out

    recorder = Recorder()
    guidance_extract.get_llm_client = lambda: recorder  # type: ignore[attr-defined]
    earnings_service.get_llm_client = lambda: recorder  # type: ignore[attr-defined]

    with session_scope() as session:
        company = company_repo.get_by_ticker(session, args.ticker)
        if company is None:
            print(
                f"{args.ticker} is not in {_DEMO_DB}; run scripts/demo_db.py first", file=sys.stderr
            )
            return 1
        # The seed already ran extraction with the stub and cached its empty result; drop that
        # cache so the live model is asked (FR-GD-006 caches per release and model).
        for document in session.scalars(select(Document).where(Document.company_id == company.id)):
            if guidance_extract.CACHE_KEY in (document.doc_metadata or {}):
                document.doc_metadata = {
                    k: v
                    for k, v in document.doc_metadata.items()
                    if k != guidance_extract.CACHE_KEY
                }
        session.flush()
        guidance_extract.extract_company_guidance(session, company)
        build_company_guidance(session, company)
        # Drop the seeded brief so its narrative prompt is built (and recorded) from the same
        # inputs the fresh pre-deploy seed will have: guidance present, no earlier version.
        session.execute(delete(EarningsBrief).where(EarningsBrief.company_id == company.id))
        earnings_service.after_filings(session, company)
        turn = answer_question(
            session,
            company=args.ticker,
            question=_RISK_QUESTION,
            user_id=demo_user(session).id,
            llm=recorder,
        )
        print(f"[record] chat answered={not (turn.abstained or turn.refused)}: {turn.answer[:160]}")
        session.rollback()  # the recordings are the product; leave the database as seeded

    print(f"[record] wrote {len(written)} recording(s): {', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
