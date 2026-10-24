# Phase 7g — Governance & Executive Compensation (DEF 14A Proxy Statements)

**Prerequisites:** 7c (DEF 14A ingested and chunked) and Phase 2c (RAG) done.
**Blocks:** 7j (briefs may note a governance change). Feeds 7e only through `exec_departure`
context (no hard dependency).
**Full spec sections:** §13 (parsing), §17 (report schema), `TODO.md` ("governance", "insiders").
Requirement IDs: `FR-GV-001` … `FR-GV-012`, `DR-GV-001` … `DR-GV-003`, `AGT-GV-001`.

## Objective

Add a Governance view built from the annual proxy statement (DEF 14A): board composition,
independence, committee structure, CEO pay and pay ratio, say-on-pay result, and share
structure (dual-class). Analysts read these to judge who controls the company and how
management is paid.

**Reality check, stated up front.** Proxy statements have no standard XBRL for most of this
(only Pay-Versus-Performance data has been tagged, since fiscal 2022 proxy filings, via Inline
XBRL). Everything else is HTML prose and tables that differ company to company. So this file
splits the work by reliability:

- **Tier A (structured, exact):** Pay-Versus-Performance XBRL facts, if present.
- **Tier B (table parsing, validated):** the Summary Compensation Table and CEO pay ratio.
- **Tier C (text, cited, abstain-friendly):** board independence, tenure, committees, say-on-pay
  percentage, anti-takeover provisions. Extracted with a bounded LLM step that must quote.

Anything that fails verification is shown as "not found in this proxy", never guessed.

## Scope

### 1. Proxy document handling

1. Using 7c's `DEF 14A` documents, add `ingestion/documents/proxy_sections.py` to identify
   proxy sections by heading keywords: "Board of Directors", "Director Independence",
   "Committees", "Compensation Discussion and Analysis", "Summary Compensation Table", "CEO Pay
   Ratio", "Pay Versus Performance", "Advisory Vote" (say-on-pay), "Security Ownership of
   Certain Beneficial Owners". Store section keys on chunks like the 10-K splitter does.
2. Each proxy is tied to a fiscal year (`fiscal_year` = the year the proxy covers, taken from
   the cover page / filing metadata, not from the filing date). Annual meetings fall in
   different months, so a calendar-year guess is wrong.
3. Handle `DEFA14A` supplemental materials: store but exclude from extraction unless they
   contain the same sections.

### 2. Tier A — Pay Versus Performance XBRL

4. Extend the concept map with the PvP tags that exist in the SEC taxonomy (Executive
   compensation disclosure: `PeoTotalCompAmt`, `PeoActuallyPaidCompAmt`,
   `NonPeoNeoAvgTotalCompAmt`, `TotalShareholderRtnAmt`, `PeerGroupTotalShareholderRtnAmt`,
   `NetIncomeLoss`, and the company-selected measure). Verify exact element names against the
   current SEC `ecd` taxonomy before coding and list them in the ADR.
5. Persist per proxy year as `financial_metrics`-style rows in a new table `exec_comp_facts
   (company_id, fiscal_year, fact_key, value, unit, source_id)` with `xbrl:` provenance. This
   is a separate table because these facts are not period-of-company-financials metrics.

### 3. Tier B — Summary Compensation Table & pay ratio

6. Parse the Summary Compensation Table from the HTML: columns Name & Position, Year, Salary,
   Bonus, Stock Awards, Option Awards, Non-Equity Incentive, Pension/NQDC, All Other, Total.
   Use a table parser keyed on header text; **validate** every row: components must sum to the
   Total within $1 (rounding). A row that fails validation is discarded and logged, never
   "fixed". Only the Principal Executive Officer (CEO) and Principal Financial Officer rows
   are required in v1; store all named officers when validation passes.
7. CEO pay ratio: find the sentence "ratio ... to the median ... employee" and extract the
   ratio and median pay with regex, validating that median pay × ratio is within 2% of CEO total
   pay (disclosure rounding). Fail → not stored.
8. Money stays Decimal in raw USD. Names are text; do not try to canonicalise them across
   years beyond case-folding.

### 4. Tier C — text-derived governance facts (bounded LLM, quote-or-abstain)

9. Fixed schema `GovernanceFacts { board_size, independent_directors, ceo_chair_combined
   (bool), lead_independent_director (bool), classified_board (bool), dual_class (bool),
   say_on_pay_support_pct, committees: [str] }`, each field `{value, quote, paragraph_id}` or
   `null`. The LLM fills a field **only** if it can return a verbatim quote supporting it;
   numeric fields must satisfy the existing number-match verification against the quote. Fields
   that fail are set to null and displayed as "not stated".
10. Compute derived values deterministically from the validated fields:
    `independence_ratio = independent_directors / board_size` (ratio as decimal). Never let the
    LLM compute it.
11. Proxy text is untrusted data. Add the standard injection test (a paragraph telling the model
    to set `dual_class=true`).
12. Cache by `(document_id, prompt_version, model)`. Version the prompt (`governance_v1`).

### 5. API

13. `GET /companies/{ticker}/governance?fiscal_year=` returns: `facts` (Tier C with quotes),
    `compensation` (Tier B rows), `pay_vs_performance` (Tier A series), `pay_ratio`, and a
    `coverage` object listing which sections were found. Missing parts are explicit nulls with
    a `reason`. Additive; update docs and openapi.
14. `GET /companies/{ticker}/governance/history` returns the multi-year CEO total pay series and
    the independence ratio, for a trend chart.

### 6. UI

15. A "Governance" tab: left column — board snapshot (size, independence ratio, chair/CEO split,
    classified board, dual class) with "not stated" for missing; right column — CEO pay table
    and a pay-vs-total-shareholder-return chart if Tier A exists. Each fact has a quote on
    hover and opens the citation drawer.
16. AI-derived facts sit under the AI marker; Tier A/B numbers are marked "Extracted from
    filing tables" (deterministic). The page states the proxy fiscal year and filing date.
17. If no proxy has been ingested for the ticker, show an explicit empty state with the
    ingest status (e.g. JPM fixture present, other missing), not a blank page.

## Out of scope

Insider trading (Form 4), 13F and 13D/G ownership analytics, ISS/Glass Lewis ratings,
shareholder-proposal analysis, board interlocks, comparing pay across companies (peer pay
benchmarking), and a "governance score" (do not invent one).

## Docs to update in the same PR

`docs/database.md` (`exec_comp_facts`), `docs/api.md`/`openapi.json`, `docs/ui.md`, prompt
registry, concept-map docs, spec Appendix H, ADR-0045 (three-tier reliability model; why no
governance score).

## Definition of Done

- [x] Proxy sections are detected in at least two fixture proxies (e.g. NVDA and JPM)
- [x] Summary Compensation Table rows pass the sum-to-total validation; a deliberately
      corrupted fixture row is rejected and logged (test)
- [x] CEO pay ratio extraction validates against median × ratio ≈ CEO total within 2%; failure
      stores nothing
- [x] PvP XBRL facts persist where the fixture has them; absence yields `reason` not zeros
- [x] Every Tier C field has a verbatim quote or is null; a fabricated quote is rejected (test
      with a recorded bad response)
- [x] `independence_ratio` is computed in code only; a test proves the LLM output is not used
- [x] Prompt-injection fixture does not alter fields
- [x] Proxy fiscal year comes from document content, verified by a test where the filing month
      would suggest the wrong year
- [x] Governance endpoint returns coverage and explicit nulls; history endpoint returns a
      series
- [x] UI shows populated, partially populated and empty states; AI vs table-extracted facts are
      visually distinguished
- [x] Docs and ADR-0045 written; `make check` and `make openapi` clean
