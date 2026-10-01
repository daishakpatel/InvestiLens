# ADR-0004: Content anchors, not page numbers, for citations

- **Status:** Accepted
- **Date:** 2026-09-28
- **Spec refs:** §13.2, §13.3 (CIT-001, CIT-002)

## Problem

v1 cited sources by page number. SEC filings are HTML, which has no stable pagination: page
breaks depend on the renderer, viewport, and print settings. A "page 47" citation can't be
reproduced or verified, and many sources (XBRL facts, computed metrics, news) have no pages at
all.

## Decision

Cite through backend-issued `source_id`s, each resolving to a typed anchor. For text chunks the
anchor is `document_id` + `section_path` + `paragraph_id` + `char_start`/`char_end`. Tables use
`table_id` + row/column labels. XBRL facts use `accession_number` + `concept_tag` +
`context_id`. Derived metrics use `formula_id` + input source IDs. News uses `news_id` + span.
`page` is populated only for PDF sources.

## Consequences

Every citation resolves deterministically to an exact span that can be highlighted in the UI
and re-verified later, and derived numbers carry full lineage. The chunker must preserve
section structure and character offsets. Anchors are coupled to the parsed document version,
so re-parsing a filing must keep or remap IDs.
