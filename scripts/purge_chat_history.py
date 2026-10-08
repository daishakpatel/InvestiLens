"""Purge chat messages older than the retention window (SEC-014, Phase 5c).

A real cron/Celery-Beat wiring is Phase 5d (same pattern as the ingestion poller); this is the
callable the job will wrap, runnable standalone until then.

Usage:
    cd backend && uv run python ../scripts/purge_chat_history.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings
from app.db import session_scope
from app.repositories.chat import purge_messages_before


def main() -> None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(days=settings.chat_message_retention_days)
    with session_scope() as session:
        deleted = purge_messages_before(session, cutoff=cutoff)
    print(f"Purged {deleted} chat message(s) older than {cutoff.date().isoformat()}")


if __name__ == "__main__":
    main()
