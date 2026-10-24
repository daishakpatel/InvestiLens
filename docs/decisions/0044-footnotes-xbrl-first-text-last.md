# ADR-0044: Footnotes are XBRL first, text last; notes live in document metadata

- **Status:** Accepted
- **Date:** 2026-10-23
- **Spec refs:** §13, §14, §17, Appendix H (FR-FN-001 … FR-FN-012, AGT-FN-001 … AGT-FN-003)

## Problem

Debt maturities, lease obligations, tax positions and contingencies live in the notes to the
financial statements, the part of a filing that free-text retrieval handles worst. Four things
force decisions:
- Notes must be found reliably. NVIDIA and JPMorgan print their statements under Item 15, not
  Item 8, and the chunker did not break at note boundaries there, so a chunk could straddle two
  notes.
- The exact numbers must not come from a model. Companies tag different concepts: Apple and
  JPMorgan tag a maturity ladder (`LongTermDebtMaturitiesRepaymentsOfPrincipal…`, JPMorgan in the
  "Rolling" variants since FY2023). NVIDIA tags none, only each note's principal and remaining
  term on `LongtermDebtTypeAxis`, which companyfacts drops along with every dimensioned fact and
  numeric duration (the lease term).
- Narrative notes (revenue recognition, contingencies, segments) need a summary that cannot
  invent anything.
- Notes need storing somewhere.

## Decision

**Segmentation.** Notes are segmented from chunk rows at parse time
(`ingestion/documents/notes.py`). A heading is "Note N – Title" (any dash, any case, title
possibly on the next line) or "N. Title". It is only looked for in the financial-statement
sections (10-K Items 8 and 15; 10-Q Part I Item 1, or JPMorgan's unitemized Part I). Note
numbers must increase and the first heading's style is kept, which rejects cross-reference lines
and numbered lists. Notes under unnumbered bold headings (Intel) are not detected and the filing
is flagged `low_confidence`.

**Chunking.** The chunker starts a new chunk at every note heading in those sections and keeps a
bare "Note 11 -" with its title line. This bumps the parser to `sec-ingest-v3`.

**Classification.** Categories come from title keywords in a fixed priority order
(`note_taxonomy_v1`: debt, leases, revenue recognition, income taxes, commitments and
contingencies, segments, stock compensation, goodwill and intangibles, derivatives, fair value,
other). Ties are recorded in `also_matches`.

**Storage.** Notes are stored in `documents.metadata['notes']`, not a `filing_notes` table. Every
read is "the notes of this filing" (the list endpoint, the note-scoped diff), and no query
crosses filings by category, so a table and migration would buy nothing. Summaries are cached
beside them in `metadata['note_summaries']` under `{note_id}|{prompt_version}|{model}` (model is
`mock` when the mock client answers). A re-parse drops them, because they cite chunk IDs.

**Facts.** Footnote facts come from a `footnote_metrics` block in `concept_map_v1.yaml` and are
persisted by `finance/footnote_builder.py` after the ratio builder, as FY rows
`xbrl:{T}:{metric}:FY{yr}`:
- For the latest year only, a metric that companyfacts lacks is read from that 10-K's inline XBRL
  (undimensioned, at the year end).
- If no ladder concept exists at all, the ladder is built from per-instrument principal and
  remaining term (`DebtInstrumentCarryingAmount` + `DebtInstrumentTerm`), bucketed by term and
  stored as `derived:` rows whose lineage names every note.
- Whatever is still missing becomes `metric_gaps` (`not_tagged`, `filing_unavailable`,
  `MISSING_INPUT`), never zero.
- Two derived figures carry their formula and inputs: `debt_due_within_2y_share` (needs the whole
  ladder) and `lease_adjusted_debt` = FY `total_debt` + operating lease liabilities (needs both;
  always labelled "Lease-adjusted").

**Summaries.** Only revenue recognition, commitments and contingencies, and segments are
summarised: one `note_summary_v1` structured call per note. A bullet is kept only if:
- it cites a paragraph the model was shown;
- its quote is verbatim in that paragraph, ignoring whitespace and typographic quotes
  (`citation/quotes.py`);
- every number in it matches a number in the quote within the verifier's 1% tolerance.

If no bullet survives, the summary abstains ("Not summarised"). Summaries are generated after
parsing (`parse_documents`, the EDGAR poller, `make footnote-summaries`), never on page load.

**Note diff.** `GET /filings/{id}/notes/{category}/diff` calls the existing
`filings.service.diff_filings` with a new `scope` of paragraph IDs. There is no second alignment
engine, and no scope means the whole filing, as before.

## Consequences

Analysts get exact ladders and lease figures with a source behind every number, and every AI
sentence is backed by a quote they can open. The costs:
- `sec-ingest-v3` renumbers chunk IDs after the notes in Item 8/15 filings. On the dev DB, 216
  re-split chunks lost their embeddings, and old report citations into those sections stop
  resolving, as with ADR-0041.
- Bucketing NVIDIA's ladder assumes `DebtInstrumentTerm` is the remaining term, which is how
  NVIDIA tags its "Expected Remaining Term" column. A filer using it for the original term would
  be mis-bucketed. That is why the fallback runs only when no ladder concept exists.
- Lease-adjusted debt inherits `total_debt`'s inputs: JPMorgan's FY `total_debt` holds short-term
  borrowings only (no long-term debt tag is mapped for it), so its lease-adjusted debt
  understates.

Revisit if a covered filer uses unnumbered note headings (read emphasis from the raw HTML, as
`filings.units` does for risk factors), or if summaries need querying across filings (then move
them to a table).
