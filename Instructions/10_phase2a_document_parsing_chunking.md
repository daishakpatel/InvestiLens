# Phase 2a — Document Parsing & Chunking

**Prerequisites:** `05_phase1a_sec_ingestion.md` done (real filing documents exist in
`documents`/`filings`).
**Blocks:** `11_phase2b_embeddings_and_indexes.md` (embeds what this file chunks).
**Full spec sections:** §22 (full document processing & chunking spec — this file implements
it in full), §13.3 (citation anchors — chunk IDs must support these).

## Objective

Turn raw filing HTML into clean, section-aware, stably-identified chunks — including tables as
first-class citizens — ready for embedding. This is the step that makes or breaks retrieval
quality later, so don't rush the section-detection and table-handling parts.

## Scope

1. **HTML parsing pipeline** (spec §22.1): raw document → HTML parsing → remove boilerplate →
   section detection → text normalization → paragraph segmentation → table extraction →
   chunking → metadata attachment → (embedding happens in Phase 2b).
2. **Section detection (DP-001):** detect Items (Item 1, 1A, 1B, 2, 3, 7, 7A, 8, 9A… for
   10-K; Parts/Items for 10-Q). Handle table-of-contents duplicate headings and inline XBRL
   wrappers. When headings are inconsistent, fall back to heuristics and log a confidence
   score rather than guessing silently.
3. **Inline XBRL (DP-002):** parse `ix:` facts directly from the filing HTML where present, as
   a cross-check against the separately-ingested `companyfacts` data from Phase 1a/1b — flag
   discrepancies rather than silently picking one.
4. **Text normalization (DP-003):** unicode normalization, whitespace cleanup, strip page
   headers/footers, fix hyphenation artifacts, handle footnotes sensibly.
5. **Hidden text removal (DP-004):** strip `display:none` and other invisible elements. This is
   also your first line of defense against prompt injection hidden in filing markup — note
   this connection in a code comment so Phase 2c/RAG agents know it's already handled here.
6. **Stable chunk IDs (DP-006):** deterministic `paragraph_id`/`chunk_id` derived from
   `(document_id, section_path, index)` so citations remain stable if the document is
   reprocessed with the same parser version. Track `parser_version` on every chunk.
7. **Financial-aware chunking (CH-001…008):**
   - Never let a chunk cross an Item boundary.
   - Target 300–500 tokens, ~10–15% overlap on paragraph boundaries, max 800.
   - Each risk-factor heading + body is one logical unit (split if oversized, but repeat the
     heading in every child chunk).
   - **Tables as first-class chunks:** extract each financial table to structured rows/columns,
     render as Markdown, generate a text caption (e.g. "Consolidated Statements of Income,
     FY2023–2025, USD millions"), store as `chunk_type = table` with `table_id` and cell
     references. Never split a table mid-row.
   - Prepend a contextual header (company, filing type, period, section path) before the chunk
     text — this gets embedded but isn't shown to the user in citations.
   - Track `parent_section_id` on each chunk for later context-expansion in retrieval.
   - Content-hash each chunk; cluster near-duplicates (e.g. repeated risk-factor boilerplate
     across years).
   - Flag MD&A "driver" language (e.g. "the increase was primarily due to…") with
     `is_driver_language` via a lexicon — this helps causal-explanation questions later.
   - Chunk footnotes/statement notes by note title, preserving the note number.
8. **PDF path (DP-005):** page-aware extraction with real page numbers for any PDF source
   (earnings releases, transcripts) — this is the *only* place `page` gets populated.

## Out of scope for this file

No embeddings, no vector storage, no retrieval logic — that's Phase 2b/2c. This file's output
is rows in `document_chunks` with text, anchors, and metadata populated; `embedding` stays
null until Phase 2b runs.

## Definition of Done

- [ ] Section detection correctly identifies Items on the seed companies' 10-Ks with ≥ 95%
      accuracy on a small hand-labeled sample
- [ ] No chunk crosses an Item boundary (test this directly)
- [ ] At least one full financial statement table is correctly extracted as a `table_chunk`
      with correct row/column structure, not flattened into prose
- [ ] Chunk IDs are deterministic — reprocessing the same document with the same parser
      version produces identical chunk IDs
- [ ] Hidden/invisible HTML content is stripped and does not appear in any chunk's text
- [ ] Near-duplicate risk-factor boilerplate across two years of the same company's 10-Ks is
      detected and clustered
