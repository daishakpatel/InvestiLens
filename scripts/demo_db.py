#!/usr/bin/env python3
"""Build the demo database locally, exactly as the demo's pre-deploy step does (ADR-0050).

    cd backend && uv run python ../scripts/demo_db.py

Recreates `assay_desk_demo` on the configured Postgres server, migrates it, and seeds NVDA, AAPL
and JPM from the offline fixtures (scripts/seed_demo.py). Then run the API against it with
`DEMO_MODE=true` and `DATABASE_URL` pointing at that database; scripts/vertical_slice.sh does
this.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))

_DEMO_DB = "assay_desk_demo"


def main() -> int:
    parser = argparse.ArgumentParser(description="Recreate and seed the local demo database")
    parser.add_argument("--name", default=_DEMO_DB, help=f"database name (default {_DEMO_DB})")
    args = parser.parse_args()

    from _dbtools import recreate_database

    from app.config import get_settings

    url = recreate_database(get_settings().database_url, args.name)
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "DEMO_MODE": "true",
        "PROVIDER_MODE": "mock",
        "BACKGROUND_JOBS_ENABLED": "false",
    }
    seed = [sys.executable, str(_ROOT / "scripts" / "seed_demo.py"), "--with-reports"]
    subprocess.run(seed, env=env, check=True, cwd=_ROOT / "backend")  # noqa: S603
    shown = urlparse(url)._replace(netloc=urlparse(url).hostname or "").geturl()  # no password
    print(f"[demo-db] ready: {shown} (database {args.name})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
