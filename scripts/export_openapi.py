"""Write the OpenAPI spec to docs/openapi.json (the published contract).

The spec is generated from the FastAPI app so the routers stay the single source of truth.
A contract test asserts the checked-in file matches the app, so this must be re-run whenever
routes or schemas change.

Usage:  cd backend && uv run python ../scripts/export_openapi.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.main import app

OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def export() -> None:
    spec = app.openapi()
    OUTPUT.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {OUTPUT.relative_to(Path.cwd().parent)} ({len(spec['paths'])} paths)")


if __name__ == "__main__":
    export()
