# Phase 1a — SEC Filing Ingestion

**Prerequisites:** Phase 0 complete (schema exists, mock `FilingsProvider` exists).
**Blocks:** Phase 1b (concept map needs real `financial_facts` rows), Phase 2a (chunking
needs real filing documents).
**Full spec sections:** §21.1–21.3 (ingestion worker + rules), §6/LGL-002 (SEC fair-access),
DR-020…030 (financial correctness rules that start here).

## Objective

Build the real SEC EDGAR client and ingestion pipeline: find companies, pull their filings and
XBRL facts, store them, and make the pipeline idempotent and safe to re-run.

## Scope

1. **Company resolution.** Use `company_tickers.json` from EDGAR to populate/refresh
   `companies` and `company_identifiers` (ticker↔CIK, handles ticker changes and share
   classes like Alphabet A/C).
2. **Filing discovery.** Use the `submissions` API to list a company's filings; detect new
   ones by `accession_number` (never re-process an accession already in `filings`).
3. **Download.** Primary document + exhibits + the `companyfacts` XBRL JSON. Store raw bytes
   in object storage (MinIO locally), record `content_hash`, and insert a row in `documents`
   and `filings`.
4. **XBRL facts.** Parse `companyfacts` into `financial_facts` rows: `concept_tag`,
   `context_id`, `period_start/end`, `period_type`, `dimensions`, `value`, `unit`, `decimals`,
   `filed_date`. Store **every** fact — don't filter to "known" concepts yet, that happens in
   Phase 1b.
5. **8-K item classification** — tag each 8-K with its item codes (e.g. 2.02, 5.02, 1.01, 8.01)
   into the `filings.items` array, parsed from the filing's own item headers.
6. **Amendments.** Detect 10-K/A and 10-Q/A; link via `filings.amends_filing_id`; never
   overwrite the original row.
7. **Provider client requirements (DR-002, LGL-002):**
   - Descriptive `User-Agent` header with a contact email, on every request.
   - Rate limit: design target ≤ 5 req/s to `sec.gov`/`data.sec.gov`.
   - Timeouts, retry with exponential backoff + jitter, circuit breaker on repeated failure.
   - SSRF guard: only ever fetch from an allowlist of SEC hosts.
8. **Idempotency (ING-001):** re-running the whole pipeline against an already-ingested
   company produces zero duplicate rows. Unique key is `accession_number` for filings,
   `content_hash` for other documents.
9. **Backfill policy (ING-002):** last 5 fiscal years of 10-K, last 12 quarters of 10-Q, last
   24 months of 8-K, configurable per company.
10. **Run tracking & failure isolation (ING-003…005):** every run recorded in
    `ingestion_runs`; unparseable records go to `ingestion_dead_letters` with the error, not
    silently dropped; one company's failure doesn't abort a batch of others.
11. **New-filing poller** (can be a Celery Beat task stub here, wired up fully in Phase 5d/
    background jobs): poll EDGAR periodically for watched companies and trigger the pipeline
    above for anything new.

## Out of scope for this file

Don't compute financial metrics yet — that's Phase 1b/1c, which consumes `financial_facts`.
Don't chunk/embed document text yet — that's Phase 2a/2b, which consumes `documents`/`filings`.

## Definition of Done

- [ ] Running the pipeline against NVDA, AAPL, and JPM (against the frozen fixtures from
      Phase 0d, and once confirmed working, against live EDGAR) populates `companies`,
      `company_identifiers`, `documents`, `filings`, and `financial_facts`
- [ ] Re-running produces zero duplicate rows (test this explicitly)
- [ ] Every filing has `accession_number`, `content_hash`, `source_url`, and correct metadata
- [ ] 8-K item codes are populated and correct for a sample of real 8-Ks
- [ ] A deliberately malformed/missing filing goes to `ingestion_dead_letters` instead of
      crashing the run
- [ ] `ingestion_runs` shows accurate counts and status for each run
- [ ] All EDGAR requests carry the required `User-Agent` and respect the rate limit (verified
      in a test with a mock server asserting header + call spacing)
