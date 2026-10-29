# ADR-0051: Per-share series are served split-adjusted; stored rows stay as filed

- **Status:** Accepted
- **Date:** 2026-10-28
- **Spec refs:** §11.7, DR-025, DR-026, CIT-003, FR-QT-012

## Problem

DR-026 requires per-share history to be adjusted for splits retroactively when periods are
compared, but `GET /companies/{ticker}/financials` served each year's diluted EPS and diluted
share count exactly as filed. A filing reports them on the share basis of the day it was filed,
so NVIDIA's EPS fell from $11.93 (FY2024, before the June 2024 10:1 split) to $2.94 (FY2025)
and its share count jumped tenfold, in the charts, the growth view and the statement table.
Valuation and earnings quality already moved share counts across splits themselves, but only
with the splits in `corporate_actions`, which the price feed fills from its five-year backfill:
NVIDIA's 2021 4:1 and Apple's 2014 7:1 were missing.

## Decision

`app/finance/splits.py` builds each company's split list from the price feed's exact ex-dates
plus the company's own `us-gaap:StockholdersEquityNoteStockSplitConversionRatio1` facts, which
cover every split since XBRL began (one entry per split, a tagged split dated by its latest
context when the feed lacks it). The financials endpoint divides every `USD/shares` value, and
multiplies every `shares` value, by the product of the splits effective after its filing date
(the filed date of `as_reported_accession`), and appends a note to the point's `formula`:
"Split-adjusted: as filed 11.93, divided by 10 for later stock splits (10-for-1 on 2024-06-10)".
Stored `financial_metrics` rows are not changed, so `source_id` still resolves to the figure the
filing shows, and consumers that already adjust (valuation, earnings quality) do not do it twice.

## Consequences

Per-share and share-count series read on one basis across splits for every company, without a
data migration or re-ingest, and the hover says what was adjusted and why. A figure whose filing
date is unknown passes through unadjusted. A tagged split's date can be off by days from its
ex-date, which matters only for a filing made between a split's approval and its ex-date.
Revisit if other endpoints (compare, research tools) start showing per-share history, or if a
filer reports splits under a different concept.
