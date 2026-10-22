# Phase 7c — SEC Exhibits, Extra Form Types & the 8-K Item Parsing Fix

**Prerequisites:** Phase 1a (SEC ingestion) and 2a (document parsing/chunking) done.
**Blocks:** 7e (red flags need correct 8-K item codes), 7f (footnotes need full 10-K sections),
7g (needs DEF 14A ingestion), 7i (needs EX-99.1 press releases), 7j.
**Full spec sections:** §10.x (SEC ingestion), §13 (parsing), `TODO.md` ("EX-99.1", "DEF 14A",
"10-Q Part I dropped", "prolific-filer history"). Requirement IDs: `FR-EX-001` … `FR-EX-014`,
`DR-EX-001` … `DR-EX-003`.

## Objective

Teach the ingestion layer to fetch and store the documents the rest of Phase 7 depends on, and
fix two bugs that would silently corrupt them. This is the plumbing file: it ships no new
analyst-facing screen, but 7e, 7f, 7g and 7i cannot work without it. Because the output is
invisible, the Definition of Done is strict about test evidence.

## Known defects this file must fix (confirmed in the current code)

1. **8-K item-code collision.** `documents/sections.py` uses `_ITEM_RE` that collapses
   `Item 5.02` to code `"5"` and `Item 2.02` to `"2"`. So 5.01, 5.02 and 5.07 are
   indistinguishable, and a CFO-departure 8-K (5.02) looks the same as a shareholder-vote
   8-K (5.07). Any red-flag logic built on the current codes would be wrong.
2. **Filing-type allowlist drops forms.** `_within_backfill` and the form allowlist in
   `ingestion/sec/pipeline.py` exclude DEF 14A, NT 10-K and NT 10-Q, and `list_filings` only reads
   the "recent" block of the submissions JSON, so prolific filers lose older filings.
3. **10-Q Part I dropped.** The 10-Q section splitter keeps only some items; Part I Item 1
   (financial statements and notes) is discarded, so footnote text for quarters is unreachable.

## Scope

### 1. Fix 8-K item parsing

1. Replace the section-code logic for 8-K documents with a dedicated parser
   (`ingestion/documents/eightk_items.py`) that recognises `Item N.NN` (dotted two-digit
   suffix) and returns the **full** code (`"5.02"`). Keep the existing collapsed codes for
   10-K/10-Q where the dotted form does not occur.
2. Handle real-world formatting: `Item 5.02.` with trailing period, `ITEM 5.02`, non-breaking
   spaces, `Item 5.02 –` with dash variants, and items split across a table-of-contents entry
   and the real heading (use the later occurrence when two matches are within 300 chars of
   each other and the first is followed by a page number). Write tests from these literal
   strings.
3. Extract the 8-K item list from the filing index metadata (`FilingRef.items`) as a second
   source of truth and **reconcile**: if the parsed headings and the index metadata disagree,
   store both, set `doc_metadata['items_mismatch']=true`, and log a warning. Prefer the
   metadata for classification; prefer the parsed headings for text boundaries.
4. Bump `PARSER_VERSION` (to `sec-ingest-v2`) so existing 8-K documents are re-parsed. Provide
   a management command `make reparse-8k` that re-chunks only 8-Ks and is safe to re-run
   (idempotent via the `(company_id, content_hash)` unique key plus parser version).
5. Paragraph IDs for 8-K chunks must now include the full item code so citations survive:
   check how `DocumentChunk.paragraph_id` is built and make sure an old citation to a
   re-parsed chunk fails loudly (resolver returns not-found) rather than pointing at the wrong
   paragraph. State the chosen behavior in the ADR.

### 2. Exhibit fetching (EX-99.1 / EX-99.2)

6. Extend the `SecSource` ABC with `list_exhibits(filing) -> list[ExhibitRef]` and
   `fetch_exhibit(exhibit_ref) -> bytes`. `ExhibitRef`: `filing_accession`, `exhibit_type`
   (`EX-99.1`, `EX-99.2`, `EX-10.x` ignored for now), `filename`, `url`, `size_bytes`.
   Implement on `LiveSecSource` using the filing index (`-index.json`); implement on
   `MockSecSource` from fixtures; both go through `HardenedHttpClient` (timeout, retry,
   logging, rate limit per SEC fair-access rules, declared User-Agent).
7. Only fetch exhibits for 8-Ks whose item list contains **2.02** (results of operations)
   or **7.01/8.01** with an EX-99 attached. Skip everything else to stay inside SEC rate
   limits.
8. Store each exhibit as a `Document` with `document_type='earnings_release'` (this is the
   type `EarningsReleaseSource` and tier-2 already expect), `source_tier=2`, `source_url`,
   `published_at` = the 8-K acceptance time, and `doc_metadata={'parent_accession': ...,
   'exhibit_type': ...}`. Chunk through the normal pipeline so RAG can retrieve it.
9. Exhibit HTML is often table-heavy. Add a test that a press-release table (revenue,
   EPS, guidance ranges) survives chunking with its row/column structure intact enough that
   the number and its label end up in the same chunk. Look at `chunker.py`'s table handling
   before changing it.

### 3. New form types

10. Add `DEF 14A`, `DEFA14A` (supplemental proxy; store, flag as supplemental), `NT 10-K`,
    `NT 10-Q`, and `8-K/A` to the allowlist. `NT 10-K`/`NT 10-Q` get `document_type`
    `late_filing_notice`; they are small and are a red-flag input in 7e.
11. `list_filings` must page through `filings.files[]` (older submission JSON shards) when
    the backfill window requires it, not just `filings.recent`. Test with a fixture where the
    needed filing is only in a shard.
12. Backfill windows: 10-K 5 years, 10-Q 12 quarters, 8-K 2 years, DEF 14A 3 years,
    NT forms 3 years. Make these config values, not constants.
13. Keep 10-Q Part I Item 1. Update the 10-Q splitter so Part I Item 1 ("Financial Statements"
    and "Notes to Condensed Consolidated Financial Statements") is chunked with section key
    `10q_part1_item1_notes`. Add a regression test with a fixture 10-Q.

### 4. Pipeline wiring

14. `parse_documents` currently parses every filing with a raw location. Make it skip
    documents whose `parser_version` already equals current, and skip `late_filing_notice`
    items beyond metadata extraction (no embedding spend on a two-page notice).
15. Embedding cost guard: exhibits and DEF 14A are added to `generate_embeddings` but gated
    by a config flag `EMBED_EXHIBITS` (default true in dev with mocks, documented cost note).
16. The poller (`poller.py`) must pick up new exhibit-bearing 8-Ks within one poll interval:
    when an 8-K with Item 2.02 appears, enqueue exhibit fetch in the same task chain.

## Out of scope

Parsing proxy-statement *content* (that is 7g), extracting footnotes (7f), extracting
guidance numbers (7i), Form 4 / 13F / Schedule 13D ingestion (insider trades stay in
`TODO.md`), PDF exhibits, and any exhibit other than EX-99.x.

## Docs to update in the same PR

`docs/database.md` (new `document_type` values, `doc_metadata` keys), `docs/architecture.md`
(ingestion diagram: exhibit step), provider interface docs (`SecSource` additions), spec
Appendix H, and ADR-0041 ("8-K items are full dotted codes; chunk IDs change on re-parse").

## Definition of Done

- [ ] Unit tests prove `Item 5.01`, `5.02`, `5.07`, `2.02`, `2.06`, `4.02` each parse to the
      exact dotted code, including the dash, nbsp and table-of-contents cases listed above
- [ ] An 8-K with items 5.02 and 9.01 yields two sections with codes `5.02` and `9.01`
- [ ] Items-mismatch between metadata and parsed headings sets the flag and logs a warning
- [ ] `make reparse-8k` is idempotent (second run changes nothing) and bumps parser version
- [ ] Mock and live `SecSource` implement `list_exhibits`/`fetch_exhibit`, with
      timeout/retry/logging, and the live one honors the declared User-Agent and rate limit
- [ ] An Item 2.02 fixture 8-K produces an `earnings_release` Document (tier 2) whose
      chunks contain the headline revenue and EPS row, each number in the same chunk as its label
- [ ] DEF 14A, DEFA14A, NT 10-K, NT 10-Q and 8-K/A are ingested from fixtures and listed in
      the documents API with correct `document_type`
- [ ] A filing present only in an older `files[]` shard is found (fixture test)
- [ ] 10-Q Part I Item 1 text is chunked and retrievable (regression test)
- [ ] An old citation to a re-parsed 8-K chunk resolves to not-found, not to wrong text
- [ ] `parse_documents` skips up-to-date documents (test counts parser invocations)
- [ ] Docs, Appendix H and ADR-0041 written; `make check` clean
