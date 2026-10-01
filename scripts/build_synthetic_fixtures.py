"""Generate deterministic SYNTHETIC price and news fixtures (Phase 0d).

Unlike the SEC fixtures, prices and news have no free keyless source, so these are synthetic —
deterministic (seeded) and clearly labelled. They are shape-correct for `PriceProvider` /
`NewsProvider`, which is all the offline mocks and tests need. Real recorded fixtures can
replace them once Tiingo/Finnhub keys exist (ADR-0007/0008).

Usage:  uv run python scripts/build_synthetic_fixtures.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "fixtures"

# (ticker, approximate 2026 base price)
COMPANIES = [("nvda", 180.0), ("aapl", 230.0), ("jpm", 250.0)]
TRADING_DAYS = 10  # ~2 weeks of weekdays
START = date(2026, 9, 14)

_HEADLINE_TEMPLATES = [
    ("{T} beats quarterly revenue estimates", "earnings"),
    ("{T} announces new product line", "product"),
    ("Analysts raise price target on {T}", "analyst"),
    ("{T} expands data center partnerships", "business"),
    ("Regulators review {T} market practices", "regulatory"),
    ("{T} increases share buyback program", "capital_allocation"),
    ("Supply chain update from {T}", "supply_chain"),
    ("{T} reports strong demand outlook", "guidance"),
    ("Insider activity noted at {T}", "ownership"),
    ("{T} to present at industry conference", "event"),
    ("{T} margins in focus ahead of earnings", "earnings"),
    ("Market reacts to {T} guidance", "guidance"),
]


def _weekdays(start: date, count: int) -> list[date]:
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current)
        current += timedelta(days=1)
    return days


def _write_prices(ticker: str, base: float) -> None:
    rng = random.Random(f"prices-{ticker}")  # noqa: S311  (synthetic fixtures, not crypto)
    rows = [["date", "open", "high", "low", "close", "adj_close", "volume"]]
    price = base
    for day in _weekdays(START, TRADING_DAYS):
        open_ = price
        close = round(open_ * (1 + rng.uniform(-0.02, 0.02)), 2)
        high = round(max(open_, close) * (1 + rng.uniform(0, 0.01)), 2)
        low = round(min(open_, close) * (1 - rng.uniform(0, 0.01)), 2)
        volume = rng.randint(20_000_000, 80_000_000)
        rows.append(
            [
                day.isoformat(),
                f"{open_:.2f}",
                f"{high:.2f}",
                f"{low:.2f}",
                f"{close:.2f}",
                f"{close:.2f}",
                str(volume),
            ]
        )
        price = close
    with (FIXTURES / ticker / "prices.csv").open("w", newline="") as fh:
        csv.writer(fh).writerows(rows)


def _write_news(ticker: str) -> None:
    rng = random.Random(f"news-{ticker}")  # noqa: S311  (synthetic fixtures, not crypto)
    upper = ticker.upper()
    items = []
    for i, (template, category) in enumerate(_HEADLINE_TEMPLATES):
        published = datetime(2026, 9, 25, 12, 0, tzinfo=UTC) - timedelta(hours=i * 8)
        items.append(
            {
                "news_id": f"news_{ticker}_{i:02d}",
                "title": template.format(T=upper),
                "description": f"Synthetic fixture summary for {upper}. Not real news.",
                "url": f"https://news.example/{ticker}/{i:02d}",
                "publisher": rng.choice(["Example Wire", "Market Times", "Finance Daily"]),
                "published_at": published.isoformat().replace("+00:00", "Z"),
                "category": category,
                "relevance_score": round(rng.uniform(0.4, 1.0), 2),
            }
        )
    payload = {
        "_comment": f"SYNTHETIC news fixtures for {upper} (Phase 0d). Not real articles.",
        "items": items,
    }
    (FIXTURES / ticker / "news.json").write_text(json.dumps(payload, indent=2) + "\n")


def main() -> None:
    for ticker, base in COMPANIES:
        (FIXTURES / ticker).mkdir(parents=True, exist_ok=True)
        _write_prices(ticker, base)
        _write_news(ticker)
        print(f"[{ticker}] wrote prices.csv ({TRADING_DAYS} days) + news.json (12 items)")


if __name__ == "__main__":
    main()
