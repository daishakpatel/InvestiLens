# ADR-0045: Governance from proxies in three reliability tiers; no governance score

- **Status:** Accepted
- **Date:** 2026-10-24
- **Spec refs:** §13, §17, Appendix H (FR-GV-001 … FR-GV-012, DR-GV-001 … DR-GV-003, AGT-GV-001)

## Problem

Analysts read the annual proxy (DEF 14A) to see who controls a company and how its executives are
paid. Only part of a proxy is structured. Since fiscal 2022 proxies tag Pay Versus Performance in
Inline XBRL; everything else is prose and tables laid out differently by every filer:
- NVIDIA splits a name and position over two rows;
- JPMorgan and Apple span the name cell down three rows;
- AMD prints names on their own row;
- JPMorgan puts a differently shaped "pay decisions" table before its Summary Compensation Table.

A proxy's fiscal year is not its filing year: JPMorgan files in April for the year ended the
previous December. A wrong figure here (a CEO's pay, an independence count) is worse than none.

## Decision

Each fact is extracted at the reliability its source allows. Anything that fails its check is
shown as not found or not stated, never guessed or repaired.

**Tier A, exact.** These are the SEC `ecd` (Executive Compensation Disclosure) taxonomy elements
the proxies tag, checked against the fixture companyfacts and the filings' Inline XBRL:
- `ecd:PeoTotalCompAmt`, `ecd:PeoActuallyPaidCompAmt`, `ecd:NonPeoNeoAvgTotalCompAmt`,
  `ecd:NonPeoNeoAvgCompActuallyPaidAmt`;
- `ecd:TotalShareholderRtnAmt`, `ecd:PeerGroupTotalShareholderRtnAmt`, `ecd:CoSelectedMeasureAmt`
  (with `ecd:CoSelectedMeasureName`);
- the PvP table's `us-gaap:NetIncomeLoss`.

They are read from `financial_facts` for the proxy's accession (cited `xbrl:<id>`). Where
companyfacts kept no copy (it keeps them only under a filer's newest proxy, and none for Apple,
AMD or Intel in the dev data), they are read from the proxy's own Inline XBRL and cited to its
PvP table chunk. Dimensioned values (one per PEO, as Intel tags them) are not used. TSR is stored
with unit `index`, the worth of $100 invested, never as money.

**Tier B, validated tables.**
- The Summary Compensation Table is read as a grid with rowspan and colspan expanded. Values map
  to the header whose columns they fall under. A lone one- or two-digit cell is a footnote marker.
- A row is stored only if its components sum to its total within $1; otherwise it is rejected and
  logged. The first candidate table with a valid row wins.
- The PEO is the officer named most often in `ecd:PeoName` (matched on name words without titles,
  because Apple tags several officers with it), else the first officer listed. The PFO is the
  first current officer titled CFO.
- The CEO pay ratio is kept only if median pay × ratio is within 2% of the CEO's validated total.

**Tier C, quoted text.** One `governance_v1` call per proxy over paragraphs chosen
deterministically by governance topic (headings are too uneven; NVIDIA states its board size
under a say-on-pay heading). The model fills a field only with a verbatim quote from a paragraph
it was shown. The backend then:
- checks the quote is verbatim and is not itself instruction-like;
- checks every number against the quote (spelled-out numbers count);
- requires booleans to be booleans and committee names to appear in the quote;
- drops the independent-director count if one quote counts nominees and the other the current
  board, because those are different populations.

The independence ratio is computed in code from the two verified counts.

**Fiscal year.** It comes from content: the latest period of the proxy's own PvP XBRL facts, else
the latest year in its table, named like the metrics (the year the fiscal year ends in).

**Storage and timing.**
- Proxies are split into keyword sections at parse time (`sec-ingest-v4`), with
  `documents.metadata['proxy_sections']`.
- Tiers A and B go to a new table, `exec_comp_facts`. These describe a proxy year's pay, not the
  company's financial periods, so they don't belong in `financial_metrics`.
- Tier C is cached on the document under (prompt version, model), like ADR-0044's summaries.
- All tiers are built after parsing or with `make governance-backfill`, never on page load.
  A DEFA14A is stored but extracted only if it carries a compensation table.

**No governance score.** There is no composite score: weighting board, pay and structure is an
opinion the data cannot support, and ISS/Glass Lewis-style ratings are out of scope.

## Consequences

Analysts get exact pay figures with sources, every AI statement backed by a quote, and explicit
gaps. On the dev data, all 15 proxies of 5 companies parse with no rejected rows. Pay ratios
validate for NVIDIA, JPMorgan, Apple and Intel; AMD states median pay away from its ratio
sentence, so its ratio is not found.

The costs:
- Tier C coverage is uneven: Apple and JPMorgan give board counts only in graphics or tables, so
  "not stated" is common, and independence ratios exist only where a proxy states both counts
  for one group (Intel).
- `sec-ingest-v4` renumbers proxy chunk IDs (proxies had no embeddings in dev, so none were
  lost).
- The PvP fallback cites a table chunk rather than an `xbrl:` fact.

Revisit if counting directors from the nominee table is wanted. That would have to be a
deterministic table parse, not a model computing. Also revisit if Tier C needs querying across
companies (then move it to a table).
