"""README / docs / code consistency rules (Phase 7l Part D, NFR-ME-005, NFR-ME-011).

Each rule of scripts/check_docs_consistency.py gets a failing case; the last test runs the real
check on the repository, so `make check` and CI both enforce it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT / "scripts"))

import check_docs_consistency as docs  # type: ignore[import-not-found]  # noqa: E402
import stats  # type: ignore[import-not-found]  # noqa: E402

_OPENAPI: dict[str, Any] = {"paths": {"/api/v1/companies/{ticker}": {"get": {}}}}


def test_rule1_unknown_requirement_ids_fail() -> None:
    spec = "| FR-AL-001 | ... |\n| NFR-013 | ... |"
    ok = {"tests/a.py": "covers FR-AL-001 and NFR-013"}
    assert docs.unknown_requirement_ids(spec, ok) == []
    fake = "FR-ZZ-" + "999"  # split so this file does not itself cite an unknown ID
    bad = docs.unknown_requirement_ids(spec, {"tests/b.py": f"covers {fake}"})
    assert bad == [f"tests/b.py: requirement {fake} is not in docs/AssayDesk_Spec_v2.md"]


def test_rule2_readme_route_missing_from_openapi_fails() -> None:
    assert docs.missing_routes("Open `GET /companies/{ticker}`.", _OPENAPI) == []
    bad = docs.missing_routes("Try `POST /companies/{ticker}` or `GET /nope`.", _OPENAPI)
    assert len(bad) == 2 and "`GET /nope`" in bad[1]


def test_rule3_hand_typed_numbers_fail_and_generated_ones_pass() -> None:
    allowed = docs.allowed_numbers({"metrics": {"x": {"value": 0.583, "n": 24}}}, {"adrs": 50})
    readme = (
        "Correct abstention 58.3% over 24 cases, 50 ADRs. Generated 2026-10-25. "
        "See [ADR-0050](docs/decisions/0050-x.md), `make check`, https://example.com/1.\n"
        "1. first step\n"
    )
    assert docs.unbacked_numbers(readme, allowed) == []
    bad = docs.unbacked_numbers("Over 1000 tests and 99.9% uptime.", allowed)
    assert [b.split("'")[1] for b in bad] == ["1000", "99.9%"]


def test_rule4_duplicate_or_skipped_adr_numbers_fail() -> None:
    names = ["0000-adr-template.md", "0001-a.md", "0002-b.md"]
    assert docs.adr_numbering_problems(names) == []
    assert docs.adr_numbering_problems([*names, "0002-c.md"]) == ["ADR-0002 is used more than once"]
    assert docs.adr_numbering_problems([*names, "0004-d.md"]) == [
        "ADR-0003 is missing (numbers must not skip)"
    ]


def test_rule5_task_file_named_in_start_here_must_exist() -> None:
    start = "Do `01_phase0a_contracts.md`, then `02_phase0b_db.md`."
    assert docs.missing_task_files(start, {"01_phase0a_contracts.md", "02_phase0b_db.md"}) == []
    assert docs.missing_task_files(start, {"01_phase0a_contracts.md"}) == [
        "Instructions/00_START_HERE.md names 02_phase0b_db.md, which does not exist"
    ]


def test_rule6_generated_blocks_are_replaced_and_lines_of_code_ignored() -> None:
    readme = "a\n<!-- generated:stats -->\nold\n<!-- /generated:stats -->\nb"
    counts = {
        "tests": {"backend": 1, "frontend": 2, "e2e": 3, "total": 6},
        "endpoints": 4,
        "adrs": 5,
    }
    fresh = stats._replace_block(readme, "stats", stats.stats_block(counts))
    assert "old" not in fresh and "1 backend and 2 frontend test functions" in fresh
    # Lines of code move with every edit and back no claim, so they never make stats stale.
    assert stats.comparable({**counts, "loc": {"a": 1}}) == stats.comparable(
        {**counts, "loc": {"a": 9}}
    )
    assert stats.comparable(counts) != stats.comparable({**counts, "adrs": 6})


def test_secrets_are_excluded_from_images_in_every_directory() -> None:
    # NFR-ME-009: a root-only `.env` pattern would let backend/.env into the image.
    patterns = (_ROOT / ".dockerignore").read_text().split()
    assert "**/.env" in patterns and "**/.env.*" in patterns
    frontend = (_ROOT / "frontend" / ".dockerignore").read_text().split()  # its own context
    assert ".env" in frontend and ".env.*" in frontend


def test_the_repository_is_consistent() -> None:
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(_ROOT / "scripts" / "check_docs_consistency.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
