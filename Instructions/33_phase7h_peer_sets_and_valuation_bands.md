# Phase 7h — Peer Sets v2 & Valuation Bands (5-Year History, Peer Percentiles)

**Prerequisites:** 7b (TTM metrics) done; Phase 6a (comparison) done.
**Blocks:** 7j (briefs cite relative valuation). 7k may reference bands.
**Full spec sections:** §37.1–§37.2 (comparison), §10.x (metrics), `TODO.md` ("5Y averages",
"EV/EBITDA N/A for AMD/INTC", "watchlist stand-in"). Requirement IDs: `FR-PS-001` …
`FR-PS-014`, `DR-PS-001` … `DR-PS-004`.

## Objective

Phase 6a built the machinery (`comparison/peers.py`, `engine.py`, calendarization,
`percentile_rank`). It currently relies on a fixed notion of peers and compares only current
values. Analysts judge valuation **relative to the company's own history and to a defensible
peer set**. This file makes peer sets explicit, editable and explained, and adds valuation
bands: where today's multiple sits within its own 5-year range and within the peer range.

This is "v2" of the existing work, not new infrastructure. Read the current `peers.py` and
`engine.py` first and extend them; do not build a parallel module.

## Scope

### 1. Peer-set model

1. New tables: `peer_sets(id, owner_user_id NULL, company_id, name, kind, created_at)` and
   `peer_set_members(peer_set_id, peer_company_id, rationale)`. `kind` is `system_default` or
   `user`. `owner_user_id` is null for system defaults.
2. **System default peers** are produced by a deterministic rule, not by AI: same SIC code
   (from `companies`), market cap within a configured band (default 0.25×–4×), and the same
   reporting currency, excluding the company itself, capped at 8 and ordered by market-cap
   proximity. Record the *reason* per member (`"same SIC 3674; market cap 1.8× target"`). If
   fewer than 3 candidates exist, the default peer set is "insufficient peers" and downstream
   percentiles are hidden (`DR-PS-001`).
3. A user can create a custom peer set per company (add/remove tickers, max 12). Tickers must
   exist in the app's universe; the API rejects unknown tickers with a clear message that
   points to "add this company to your watchlist first". Do not silently drop them.
4. Peers differ in fiscal year end. All peer comparisons go through the existing
   calendarization path, never raw FY-vs-FY (`DR-PS-002`). If a peer lacks the four quarters
   needed to calendarize (use 7b), exclude it from that metric and list it as excluded with
   a reason.

### 2. Valuation multiples (completing the set)

5. Ensure these are computed from TTM figures and period-end market data:
   P/E (TTM), P/S, EV/Revenue, EV/EBITDA, EV/FCF, P/B (not for banks; P/TBV for banks if
   tangible book is mapped, else not applicable), FCF yield, earnings yield.
   Enterprise value = market cap + total debt + minority interest + preferred − cash &
   equivalents (and short-term investments, stated explicitly). Record the formula and inputs.
6. `TODO.md` notes EV/EBITDA is N/A for AMD and INTC. Diagnose why before coding (likely
   missing D&A or operating-income tags, or a different tag in those filers). Fix it in the
   concept map with a fixture-backed golden value, or document the specific reason in the
   `metric_gaps` row. "N/A because the tag is missing" must become either a value or a clear
   reason (`FR-PS-006`).
7. Negative or near-zero denominators (negative earnings, negative EBITDA) produce `not_meaningful`
   rather than a negative multiple, and are excluded from percentile and band calculations.

### 3. Five-year history

8. Compute each multiple at each fiscal year-end for the last 5 years using the year-end price
   from `price_history` (Phase 1d) and the TTM fundamentals as of that date. Look-ahead is the
   classic error: for a date D use only fundamentals **filed on or before D** (`DR-PS-003`).
   Add a test where a restated figure filed after D must not influence D's multiple.
9. Persist `valuation_history(company_id, as_of_date, multiple, value, status, inputs)`.
   `inputs` must reference the source IDs of the price and fundamentals used.
10. Where fewer than 3 years of history exist (recent IPOs), the band is `insufficient_history`
    and the UI says so.

### 4. Bands and percentiles

11. For each multiple compute: `own_history_percentile` (where today's value falls among
    year-end values, using `percentile_rank`), `own_min/median/max`, `peer_median`,
    `peer_percentile`, and `premium_to_peer_median` (ratio as decimal, e.g. 0.18 = 18% premium).
12. Percentiles need ≥5 points for own history (use 5 fiscal years + current) and ≥3 peers;
    otherwise return `null` with a reason. State the sample size next to every percentile in the
    API (`n`) so the UI can show "n=5".
13. Do not describe any value as "cheap" or "expensive". Labels are positional: "in the top
    quartile of its 5-year range", "18% above peer median". Add the phrase list to
    `citation.advice` tests.

### 5. API

14. `GET /companies/{ticker}/peer-sets` (list system default + user sets, with member rationales),
    `POST/PATCH/DELETE /companies/{ticker}/peer-sets` for user sets,
    `GET /companies/{ticker}/valuation-bands?peer_set_id=` returning the band object per
    multiple, history series, excluded peers with reasons, and `n` values. The existing
    comparison endpoint accepts `peer_set_id`. Additive; update docs and openapi.
15. A user's custom peer set is private to that user (404 for others).

### 6. UI

16. Peer-set selector on the Compare view showing the default set with its rationale list
    ("why these peers?") and an Edit button. Excluded peers appear greyed out with the reason.
17. "Valuation" section: for each multiple a horizontal range bar (5-year min–max) with a marker
    for today's value and a tick for peer median, with labels, never colour alone. Under it, the
    sample sizes. Hide a bar when status is `not_meaningful`/`insufficient_*` and show the
    reason in text.
18. Chart axes and units follow the conventions: ratios formatted as `x.x×`, yields as `%`.

## Out of scope

Analyst consensus estimates and forward multiples (no licensed estimates source),
DCF or target-price models, sector-relative adjustments by growth (PEG), automatically
suggesting peers with an LLM, and intraday multiples.

## Docs to update in the same PR

`docs/database.md` (peer tables, `valuation_history`), `docs/api.md`/`openapi.json`, `docs/ui.md`,
comparison docs, spec Appendix H, ADR-0046 (peer-set rule, look-ahead rule, minimum sample sizes).

## Definition of Done

- [ ] Default peer set for NVDA is deterministic across runs and each member has a stored
      rationale; a company with <3 candidates returns "insufficient peers"
- [ ] User peer sets are private, validated, capped at 12; unknown ticker rejected with a
      useful message
- [ ] Calendarization is applied to peers with different fiscal year ends; a peer missing
      quarters is excluded with a reason (test)
- [ ] EV/EBITDA for AMD and INTC either computes (with golden value) or has a specific,
      documented reason in `metric_gaps`; `TODO.md` item is updated accordingly
- [ ] Negative-earnings fixture yields `not_meaningful` and is excluded from percentiles
- [ ] Look-ahead test: a figure filed after date D does not affect D's multiple
- [ ] Percentiles are `null` with a reason when n is below thresholds; `n` is returned
- [ ] No "cheap/expensive/undervalued" wording anywhere (advice test over all label templates)
- [ ] Valuation range bars render in light and dark themes with text labels and are tested for
      all states
- [ ] Docs and ADR-0046 written; `make coverage` still 100% on `app/finance/*`;
      `make check` and `make openapi` clean
