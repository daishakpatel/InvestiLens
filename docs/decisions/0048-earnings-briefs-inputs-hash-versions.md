# ADR-0048: Earnings briefs are assembled from stored data, versioned by an inputs hash; estimated dates never notify

- **Status:** Accepted
- **Date:** 2026-10-24
- **Spec refs:** §37.3, §17, Appendix H (FR-EB-001 … FR-EB-015, CIT-EB-001 … CIT-EB-003,
  AGT-EB-001 … AGT-EB-002)

## Problem

Earnings season needs two one-page documents: a pre-earnings preview (what to watch) and a
post-earnings brief (what was reported and what changed). Most of their content already exists
as verified parts: quarterly rows (7b), guidance outcomes (7i), valuation bands (7h), red flags
(7e), the filing diff and earnings reaction (6b). Five things still had to be decided:
- **Dates.** No licensed earnings calendar exists. A guessed date must not look confirmed.
- **Versions.** The inputs arrive in steps: the 8-K and press release first, the 10-Q later
  (often the same day for NVIDIA, weeks later for others). A brief must change when its inputs
  change, but not on every run, and old versions must stay for audit.
- **The model.** Its role must be small enough that no number or uncited claim can come from it.
- **Cost.** Every new version costs a model call.
- **Notifications.** "Brief ready" must not fire once per version.

## Decision

**Calendar** (`app/earnings/calendar.py`, table `earnings_events`, one row per fiscal quarter):
- **Reported dates** are the Item 2.02 8-K filing dates from the reaction code's list. The
  quarter is the latest fiscal quarter that ended before the filing (within 100 days).
- **Announced dates** come from one sentence in a later 8-K or press release. The sentence must
  name exactly that quarter, use a "will report/host/…" verb, and give exactly one date after the
  document's own date. The sentence is kept as a quote.
- **Estimates** are the same quarter's date a year earlier plus 52 weeks (same weekday),
  `source='estimated'`, shown with "~".
- **An estimated date never triggers a preview or a notification.** The beat task skips it, and
  the `brief_ready` detector skips previews stored with `report_date_estimated`, even when a user
  made one by hand.

**Assembly first, model last** (`app/earnings/service.py`):
- Every section is built from stored rows, and a section without its input is listed in
  `missing` with a plain reason ("10-Q not yet filed.").
- **`inputs_hash`** is the sha-256 of that assembled JSON, which carries every input's IDs and
  values. Briefs are unique on `(company, fiscal_year, fiscal_period, kind, inputs_hash)`:
  - The same hash returns the stored row with no model call.
  - A new hash stores version n+1 and keeps the old ones.
  - `inputs_label` names what changed ("after 10-Q filed", "updated: reaction").

**One prompt version, `earnings_narrative_v1`, with two tasks:**
- **Watch items.** These are built in code first: a growth slowdown over 5 points, a margin that
  moved the same way for two quarters after moving the other way, new risk factors, and the topic
  whose MD&A intensity rose most. The model may reword each one in one sentence. A rewording is
  used only if it has exactly the original's numbers and passes the advice, prediction and
  characterisation guards; otherwise the code's sentence stays.
- **The brief narrative.** The model sees only the brief's own lines with their source IDs. Every
  sentence goes through the standard claim verifier and the same guards. The result is capped at
  4 sentences and 120 words by dropping sentences, never by rewriting them.

**Cost and notification limits:**
- Briefs are made only for watched or seed tickers, with at most `earnings_brief_daily_cap` new
  versions a day; reaching the cap is logged.
- Users may regenerate `earnings_brief_regen_per_hour` times an hour.
- The `brief_ready` event key leaves out the version, so a (company, quarter, kind) notifies once.

## Consequences

**What this gives us:** briefs whose every figure is a stored, cited value; deterministic
idempotence (re-running the post-ingest hook is free); and an audit trail of versions. With
`gemini-3.8-flash` on NVIDIA's Q2 FY2027, all four proposed narrative sentences verified (about
90 words), and the preview's four watch items were reworded without changing a number.

**What it costs:**
- A version also changes when a price-driven input moves. For example, the 5-session move fills
  in, or the valuation date rolls forward. The automatic hooks run only after filings and
  metrics, not prices, so this happens only on a user's regeneration or the daily preview run.
- The regeneration limit is per API process (in-memory); it needs the Redis limiter once the API
  runs on more than one process.
- Announced dates are found only in text this app ingests (8-Ks and their exhibits). Companies
  that announce only on their investor-relations site get an estimate.
- Before its 10-Q, a quarter's headline figures come only from XBRL already in companyfacts, so
  version 1 usually reads "10-Q not yet filed" there too.

**What would make us revisit it:** a licensed earnings calendar, transcripts (Q&A themes), or
more API processes (shared rate limiting).
