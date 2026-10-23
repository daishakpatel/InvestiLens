# ADR-0041: 8-K items are full dotted codes; chunk IDs change on re-parse

- **Status:** Accepted
- **Date:** 2026-10-22
- **Spec refs:** §10.x, §13, FR-EX-001 … FR-EX-015, DR-EX-001 … DR-EX-003 (Appendix H), CIT-002, DP-006

## Problem

Section detection read "Item 5.02" as item "5", so a CFO departure (5.02), a change of control
(5.01) and a shareholder vote (5.07) were indistinguishable, and the red-flag work in Phase 7e
would have been built on wrong codes. The same "last heading wins" rule, keyed on the bare item
number, let a 10-Q's Part II "Item 1" and "Item 2" overwrite Part I's, so every 10-Q's financial
statements, notes and MD&A were never chunked. Fixing either changes chunk boundaries and the
`paragraph_id`s citations point at (`{document}_{item}_{n}`). The parse step also had no notion of
"already parsed", so every run re-chunked everything, and chunks of an older parser version were
never deleted, so an old citation kept resolving to a superseded parse.

## Decision

8-K item codes are full dotted codes ("5.02"), parsed by `ingestion/documents/eightk_items.py`
(trailing periods, upper case, non-breaking spaces, en/em dashes, one-row layout tables), and
10-Q codes are part-qualified ("P1-1" = Part I Item 1, stored with section key
`10q_part1_item1_notes`); 10-K codes are unchanged. One parser version, `PARSER_VERSION =
"sec-ingest-v2"`, is stamped on every chunk and, once a document is parsed, on
`documents.parser_version` (ingest leaves it NULL), so `parse_company_documents` skips documents
that are current; `make reparse-8k` re-parses only stale 8-Ks and is a no-op the second time. A
re-parse replaces all of a document's chunks, whatever their version: an old citation to a
re-parsed chunk then resolves to not-found (a 404 from `GET /sources/{id}`), never to other text,
because new 8-K and 10-Q IDs contain the dotted or part-qualified code and cannot equal an old
`{doc}_5_0` or `{doc}_1_0`. Embeddings carry over to new rows with the same `content_hash`, so
re-parsing unchanged text (every 10-K) costs no embedding spend. The filing index's item list
stays the 8-K's classification (`filings.items`); parsed headings bound the text; a disagreement
is kept on the document (`items_metadata`, `items_parsed`, `items_mismatch`) and logged.

## Consequences

Phase 7e can classify 8-Ks by exact item, 7f can reach 10-Q notes, and the daily parse costs
nothing for unchanged documents. Citations stored before the upgrade to an 8-K or 10-Q chunk stop
resolving once `make reparse-8k` / the parse step runs, which is the intended loud failure; a
report regenerated afterwards cites the new IDs. Readers that filter chunks by `PARSER_VERSION`
(filing diff, management language) see a filing only after it is re-parsed, so a deploy runs the
parse step for every company. Revisit if citations must survive re-parses (that would need a
content-addressed ID, not a positional one).
