# Phase 7j — Pre-Earnings Preview & Post-Earnings Brief

**Prerequisites:** 7a, 7b, 7c, 7d, 7e, 7i done. 7h recommended (relative valuation line) but the
brief must degrade gracefully without it. Phase 3b (report generation) and Phase 6b (filing diff,
earnings price reaction) done.
**Blocks:** 7k (thesis tracker links to briefs), 7l (demo flow).
**Full spec sections:** §37.3 (earnings analysis), §17 (report schema). Requirement IDs:
`FR-EB-001` … `FR-EB-014`, `CIT-EB-001` … `CIT-EB-003`, `AGT-EB-001` … `AGT-EB-002`.

## Objective

Assemble the earnings-season workflow into two one-page documents:

- **Pre-earnings preview** (generated ahead of the report date): what to watch.
- **Post-earnings brief** (generated after the 8-K + 10-Q land): what happened and what changed.

The brief is mostly *assembly of verified parts that already exist* (quarterly metrics, guidance
outcome, price reaction, filing diff, red flags, management-topic shifts) plus a **short**,
fully-cited narrative. The point of this file is orchestration and honesty, not new analytics.

**Rule of the file.** Every number is fetched from the backend; every sentence of narrative is
verified by the existing citation pipeline; any section whose inputs are missing says so instead
of being filled with prose.

## Scope

### 1. Calendar

1. `earnings_events(id, company_id, fiscal_year, fiscal_period, report_date, report_time
   (bmo|amc|unknown), source, status, created_at)`. `status`: `scheduled | reported | unknown`.
2. Source of the date, in order: (a) an Item 2.02 8-K already filed (status `reported`, date from
   the filing); (b) the company's announcement 8-K or press release stating a future date
   (parse with a strict regex and quote); (c) an estimate = previous year's date for the same
   fiscal period ± weekday alignment, labelled `source='estimated'`. **Estimated dates are shown
   as estimates** (`~`) and never trigger a "preview ready" notification on their own.
3. Reuse the existing earnings-reaction code in `filings/earnings.py` for dates after the fact;
   do not duplicate the 8-K-date logic.

### 2. Preview (pre-earnings) content, deterministic where possible

4. `EarningsPreview` schema in `schemas/earnings.py`:
   - header: company, fiscal period, report date (with estimated flag)
   - `last_quarter_snapshot`: revenue, gross margin, operating margin, EPS (GAAP), OCF, with YoY
     change from 7b rows
   - `guidance_for_period`: the initial guidance items for this period from 7i (or "no guidance
     found")
   - `track_record`: from 7i (if n≥4)
   - `valuation_snapshot`: current P/E, EV/EBITDA with own-history and peer positions from 7h
     (omitted if unavailable)
   - `open_flags`: red flags from the last 90 days (7e)
   - `last_reaction`: the price move after the previous earnings (`filings/earnings.py`)
   - `watch_items`: up to 5 items, each `{text, source_ids}`, produced under the rules below
5. **Watch items generation.** First build candidates **deterministically**: (a) metric where
   the latest quarter's YoY growth decelerated by more than 5 percentage points; (b) risk
   factors flagged `new` in the most recent filing diff; (c) management topics whose intensity
   rose most (topic_taxonomy_v1); (d) a margin whose trend reversed for two quarters. Each
   candidate carries its evidence IDs. The LLM may only *rephrase* a candidate in one sentence
   and must keep every number and source ID; the verifier rejects any sentence whose numbers
   differ. If no candidate exists, `watch_items` is empty and the page says so.

### 3. Post-earnings brief content

6. `EarningsBrief` schema: 
   - `headline_table`: reported revenue, EPS, margins vs prior quarter and prior-year quarter,
     each with source IDs (7b)
   - `versus_guidance`: outcomes from 7i
   - `reaction`: price move (open/close, 1-day, 5-day) from the existing reaction code,
     displayed next to the volume ratio if available; wording purely descriptive
   - `what_changed`: from the filing diff of this 10-Q vs the previous 10-Q (new/removed/reworded
     risks counts, plus the top 3 changes with old/new quotes) and management-topic shifts
   - `new_flags`: red flags dated since the previous earnings
   - `narrative`: ≤120 words, ≤4 sentences, all cited; produced by the report generator under
     the standard verifier. If verification drops sentences, shorten rather than invent.
7. Brief generation is idempotent and keyed by `(company_id, fiscal_year, fiscal_period,
   kind, inputs_hash)` where `inputs_hash` hashes the IDs and values of all inputs. Re-running
   with the same inputs returns the stored brief; changed inputs (e.g. late 10-Q) create a new
   version, retaining the old for audit.
8. Trigger: Celery task `generate_earnings_brief(company_id, kind)`:
   - preview: 3 days before a non-estimated `scheduled` date;
   - brief: when both the Item 2.02 8-K **and** its EX-99.1 are ingested (from 7c), and again
     (new version) when the 10-Q lands, since the diff needs it. The first version states
     "10-Q not yet filed" in the `what_changed` section instead of leaving it blank.
9. Registered alert type `brief_ready` (7a): one notification per `(company, period, kind)`,
   with a link to the brief.

### 4. LLM use and safety

10. A single prompt version `earnings_narrative_v1`. Inputs are the structured brief JSON only,
    never raw filing text beyond quoted evidence snippets. Output schema forbids numbers not
    present in the input.
11. Advice and prediction guard: add "expect", "likely to beat", "should rally", "outlook for
    the stock" to the banned-phrase tests for brief text. Preview says "what to watch",
    never "what will happen".
12. Cost guard: briefs are generated only for tickers on at least one user's watchlist or in
    the seed set. Cap daily brief generations via a config value and log when the cap is hit.

### 5. API & UI

13. `GET /companies/{ticker}/earnings/calendar`, `GET /companies/{ticker}/earnings/briefs
    ?kind=&fiscal_year=&fiscal_period=` (versions listed), `POST /companies/{ticker}/earnings/
    briefs` (user-triggered regeneration, rate-limited per user). Additive; update docs and
    openapi.
14. Earnings view: an "Upcoming" card (date, estimated flag), a "Latest brief" page, and a
    print-friendly layout (CSS `@media print`) so an analyst can PDF it. Every figure opens
    the citation drawer; AI narrative sits under the AI marker; sections with missing inputs show
    a plain "Not available: {reason}" row.
15. A version switcher if multiple versions exist, labelled by input change ("after 10-Q filed").

## Out of scope

Intraday or live earnings-call coverage, transcripts, consensus comparisons, email/PDF export
beyond browser print, forecasting, and scheduling around holidays beyond weekday alignment.

## Docs to update in the same PR

`docs/database.md` (`earnings_events`, `earnings_briefs`), `docs/api.md`/`openapi.json`,
`docs/ui.md`, prompt registry, scheduled-task docs (`tasks/schedule.py` entries), spec Appendix H,
ADR-0048 (inputs-hash versioning; estimated dates never trigger notifications).

## Definition of Done

- [x] Calendar returns reported dates from Item 2.02 8-Ks and flags estimated dates; an
      estimated date never produces a "preview ready" notification (test)
- [x] Preview for an NVDA fixture quarter contains snapshot, guidance, flags and valuation; with
      7h data removed it still renders and states the omission
- [x] Watch items come only from deterministic candidates; a candidate-free fixture yields an
      empty list; an LLM rewrite changing a number is rejected (recorded bad response)
- [x] Post-earnings brief assembles headline table, guidance outcomes, reaction, diff changes and
      new flags from stored data; no number is generated by the LLM
- [x] Narrative ≤4 sentences, every sentence cited and verified; dropped sentences shorten the
      narrative rather than being replaced
- [x] Same inputs → same stored brief (idempotent); changed inputs → new version, old retained
- [x] The 8-K+EX-99.1 trigger produces version 1 stating "10-Q not yet filed"; the 10-Q
      triggers version 2 with real diff content
- [x] `brief_ready` alert fires exactly once per `(company, period, kind)`
- [x] Banned-phrase tests pass for all templates and the narrative prompt output
- [x] Per-user regeneration is rate-limited and daily cap logs when reached
- [x] Print stylesheet check (Playwright PDF snapshot has no clipped tables)
- [x] Docs and ADR-0048 written; `make check` and `make openapi` clean
