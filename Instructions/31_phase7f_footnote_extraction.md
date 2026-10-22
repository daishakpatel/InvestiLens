# Phase 7f — Footnote Extraction (Debt, Leases, Revenue Recognition, Contingencies, Segments)

**Prerequisites:** 7c (10-Q Part I kept, full 10-K sections) and Phase 2c (RAG) done.
**Blocks:** 7j (briefs can cite footnote facts). Optional input to 7e (`material_weakness`
already covered separately).
**Full spec sections:** §13 (parsing), §14 (retrieval), §17 (report schema). Requirement IDs:
`FR-FN-001` … `FR-FN-012`, `AGT-FN-001` … `AGT-FN-003`.

## Objective

Analysts spend much of their time in the *notes to the financial statements*, because that is
where debt maturities, lease obligations, revenue-recognition policy changes and contingent
liabilities live. The app can already answer generic questions with RAG, but footnotes are the
least reliable part to leave to free-text retrieval. This file makes notes first-class: locate
them, classify them, extract a small set of **verifiable facts** from the structured XBRL where
possible, and use bounded AI summarisation only for the text that cannot be reduced to numbers.

**Design principle.** Prefer XBRL facts over reading text. Many footnote values (debt maturity
schedule, lease liability, unrecognised tax benefits) are tagged in XBRL. Use those first: they
are exact. Use the LLM only for the narrative, and make it prove each claim with a quote.

## Scope

### 1. Note segmentation

1. Add `ingestion/documents/notes.py`: from a 10-K (and 10-Q Part I Item 1), split the notes into
   `Note(number, title, text_span, paragraph_ids)`. Notes appear as "Note 7 – Debt" or "7. Debt"
   or under bold headings with no number. Use heading detection first; fall back to the
   `DocumentChunk` order. Log (do not crash) when segmentation finds fewer than 5 notes in a
   10-K (flag `notes_segmentation_low_confidence`).
2. Classify each note into a fixed taxonomy `note_taxonomy_v1` using **title keywords only**
   (deterministic): `debt`, `leases`, `revenue_recognition`, `income_taxes`,
   `commitments_contingencies`, `segments`, `stock_comp`, `goodwill_intangibles`, `derivatives`,
   `fair_value`, `other`. A note that matches two categories picks the first by a documented
   priority order; ties are recorded in metadata. Unit test with at least 15 real note titles
   from the fixtures plus tricky ones ("Commitments and Contingencies – Leases").
3. Store as `Document.doc_metadata['notes']` or a new `filing_notes` table. Pick the table
   (`filing_notes(id, document_id, number, title, category, first_paragraph_id,
   last_paragraph_id)`) if you need to query by category; otherwise metadata. State the choice
   and reason in the ADR.

### 2. XBRL-first fact extraction

4. For each category, define a small list of XBRL concepts that give exact numbers, add them to
   the concept map, and persist them with `xbrl:` source IDs:
   - **debt:** maturities by year (next five years + thereafter), total debt, weighted-average
     interest rate if tagged, revolver capacity
   - **leases:** operating and finance lease liabilities, weighted-average remaining term and
     discount rate, undiscounted future payments by year
   - **income_taxes:** effective tax rate, unrecognised tax benefits, valuation allowance
   - **commitments:** purchase obligations (NVDA reports large ones), legal accrual if tagged
   - **stock_comp:** SBC expense (already mapped) and unrecognised comp cost
   Use dimensioned facts carefully: many maturities are `LongTermDebtMaturityYearOne` etc. as
   separate concepts rather than dimensions. Inspect the fixture XBRL before deciding.
5. Persist into `financial_metrics` with metric names like `debt_maturity_y1` … `y5`,
   `debt_maturity_after`. Missing concepts become `metric_gaps` rows (from 7b), not zeros.
6. Derived: `debt_due_within_2y_share` = (y1+y2)/total maturities; `lease_adjusted_debt` =
   total debt + operating lease liabilities, with the formula and both inputs recorded. The
   label must say "lease-adjusted" whenever it is shown.

### 3. Bounded AI summaries of narrative notes

7. For categories `revenue_recognition`, `commitments_contingencies`, `segments` produce a
   short structured summary via the existing generation pipeline: schema
   `NoteSummary { note_id, bullets: [{text, quote, paragraph_id}], abstain: bool }`. Every
   bullet must carry a `quote` that appears **verbatim** in the cited paragraph (reuse the
   citation verifier's exact-substring check) and any number in `text` must match a number in
   the quote (the existing ~1% tolerance rule). Drop bullets that fail; if none survive, set
   `abstain=true` and show "Not summarised".
8. Prompt rules (add to the prompt-contract tests): the note text is untrusted data; no advice;
   no forward-looking predictions; "a change from prior year" claims are not allowed here (that
   is the filing diff's job).
9. Cache summaries keyed by `(document_id, note_id, prompt_version, model)`. Never regenerate on
   page load.

### 4. Year-over-year note comparison (reuse, don't rebuild)

10. Where two consecutive 10-Ks have the same note category, expose the existing filing-diff
    machinery (`filings/diff.py`) scoped to that note: `GET /filings/{id}/notes/{category}/diff
    ?against=`. Do not write a second diff engine. If the diff module cannot take a section
    scope, add the scope parameter there with tests, and keep its current behavior as the default.

### 5. API and UI

11. `GET /companies/{ticker}/notes?filing_id=` lists notes with category. `GET
    /companies/{ticker}/footnote-facts` returns the XBRL-derived facts grouped by category
    (debt ladder, lease summary, tax). Additive; update docs and openapi.
12. UI: a "Footnotes" tab with a category sidebar, the XBRL facts as a small table (debt
    maturity ladder as a bar chart using the existing library), the cited AI bullets under an AI
    Section marker (`Section kind="ai"`), and a "Compare with prior year" button that opens the
    existing diff view scoped to the note. Each bullet and number opens the citation drawer.
13. Where the AI summary abstained or segmentation was low-confidence, say so on the page.

## Out of scope

Reading numbers out of footnote tables with an LLM, OCR, full-text footnote search (RAG
already covers), segment profitability analytics, pension/OPEB modelling, and tax-rate
reconciliation analysis.

## Docs to update in the same PR

`docs/database.md`, `docs/api.md`/`openapi.json`, concept-map docs, `docs/ui.md`, prompt registry
docs (new `note_summary_v1` prompt), spec Appendix H, ADR-0044 (XBRL-first, text last; note
storage choice).

## Definition of Done

- [ ] Note segmentation finds the expected notes in NVDA, AAPL and JPM 10-K fixtures (assert
      count and titles), and logs low confidence rather than raising
- [ ] Title-keyword classification passes the 15+ title test set including the ambiguous cases
- [ ] Debt maturity ladder for NVDA and AAPL persisted from XBRL and matches the filing by hand
      check (recorded in a test comment with the page/line reference)
- [ ] Missing concepts produce `metric_gaps`, never zero
- [ ] `lease_adjusted_debt` rows carry formula and inputs that resolve to source IDs
- [ ] Every AI bullet's quote is a verbatim substring of its cited paragraph; a bullet with a
      fabricated quote or a mismatching number is dropped (test with a recorded bad LLM response)
- [ ] Abstention path displays "Not summarised" and is tested
- [ ] Prompt-injection test: a note containing "ignore previous instructions" does not change
      output structure
- [ ] Note-scoped diff reuses `filings/diff.py` with no duplicated alignment code
- [ ] Footnotes tab renders facts, AI bullets (marked as AI) and the diff entry point
- [ ] Docs and ADR-0044 written; `make check` and `make openapi` clean
