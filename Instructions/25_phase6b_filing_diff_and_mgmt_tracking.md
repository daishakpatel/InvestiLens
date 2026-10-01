# Phase 6b — Filing Diff, Earnings Analysis & Management Language Tracking

**Prerequisites:** MVP Definition of Done (main spec §36) met. Requires Phase 2a (chunking,
including the boilerplate-clustering it already builds), Phase 1e (news, for earnings-day price
reaction context), Phase 1d (prices).
**Blocks:** nothing — optional enhancement phase, can run in parallel with Phase 6a.
**Full spec sections:** §37.3 (earnings analysis), §37.4 (filing change detection — the
strongest AI feature in the whole project, per the main spec), §37.5 (management language
tracking).

## Objective

Build the two features the main spec calls out as the best interview material: detecting what
actually changed between two filings, and tracking how management's language evolves over
time — both fully cited, neither one guessing.

## Scope

### Filing diff (the priority item in this file)

1. **Section/risk-factor alignment:** for two filings of the same type from the same company
   (e.g. this year's 10-K vs last year's), align sections and individual risk factors by
   heading first, then by embedding similarity for anything that moved or was renamed.
2. **Classification:** for each aligned pair, classify as `unchanged | reworded | new |
   removed` using similarity thresholds, with an LLM adjudicating only the borderline cases
   (not every pair — keep this cheap and mostly deterministic).
3. **Word-level diff:** for `reworded` sections, generate an actual word-level diff (not just
   "this changed"), so the UI can show what specifically was added/removed.
4. **Citations both ways:** every diff result cites both the old and new passages — this reuses
   Phase 3a's source-record machinery, applied to two documents instead of one.
5. **Wire into risk display:** populate the `change_status` field on `Risk` objects (spec
   §17.2 already has this field, left null until now) so the Risks section of the report shows
   "New / Unchanged / Reworded / Removed" per risk, as originally specified in §10.10.
6. **API & UI:** implement `GET /filings/{filing_id}/diff?against={other_filing_id}` (already
   contracted in Phase 0c, unimplemented until now) and the filing-diff view in the Filings
   page (placeholder left in Phase 4d).
7. **Alerting:** wire a "new risk factor detected" alert type into Phase 5d's alert dispatch.

### Earnings analysis

8. **Guidance tracking:** capture stated guidance from earnings releases/8-Ks and compare
   against subsequent actual results — a deterministic comparison (expected vs actual revenue/
   EPS), only where the licensed data source actually supports expectations data (check
   ADR-0009 from Phase 0a before building this — don't source estimates from an unlicensed
   place).
9. **Earnings-day price reaction:** deterministic price move around the earnings date, using
   Phase 1d's price history.
10. **"What changed vs last quarter":** reuse the filing-diff and management-tracking
    machinery from this file applied to consecutive 10-Qs/earnings releases.

### Management language tracking

11. **Topic taxonomy:** version a fixed set of topics (AI Demand, Supply Chain, Margins,
    Regulation, China Exposure, etc. — extend as needed) as `topic_taxonomy_v1`.
12. **Per-period intensity:** count topic mentions per period, normalized per 1,000 words, so
    frequency is comparable across filings of different lengths.
13. **Hedging-language index:** deterministic lexicon count of hedging terms ("may," "could,"
    "expect," "uncertain") per period — labeled clearly as a lexicon-based signal, not an AI
    judgment.
14. **First-appearance/disappearance flags:** flag when a topic first appears or drops out of
    management's commentary.
15. **Click-through to source:** every topic-intensity data point links back to the actual
    statements that were counted, using the same source-record pattern as everything else.

## Out of scope for this file

Don't rebuild chunking or citation verification — reuse Phase 2a's boilerplate-clustering
groundwork and Phase 3a's verification pipeline as-is. No sentiment scoring beyond the
hedging-language lexicon (spec explicitly avoids exposing a bare "bullish/bearish" sentiment
score).

## Definition of Done

- [ ] Diffing NVDA's two most recent 10-Ks correctly identifies at least one unchanged, one
      reworded (if present), and correctly flags any genuinely new or removed risk factor
- [ ] Risk objects in the research report correctly populate `change_status` from real diff
      results
- [ ] Word-level diff output is readable and accurate for a reworded section
- [ ] `GET /filings/{id}/diff` returns correct, cited results
- [ ] A "new risk factor" alert fires correctly in a simulated new-filing scenario
- [ ] Management topic intensity chart shows plausible trends across at least 4 periods for a
      seed company, with every data point traceable to source statements
- [ ] Guidance-vs-actual comparison only appears if the underlying data source is properly
      licensed for it — otherwise this feature is left out rather than approximated
