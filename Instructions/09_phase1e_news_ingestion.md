# Phase 1e — News Ingestion

**Prerequisites:** Phase 0 complete. Can run in parallel with Phase 1a–1d.
**Blocks:** Phase 2a/2b treat news as just another `documents` row once ingested (news isn't
chunked/embedded the same way filings are, but it does need a `document_id` for citation
purposes); Phase 3b's news summary section.
**Full spec sections:** §10.8 (news feature requirements incl. v2 enhancements), §6/LGL-004
(news licensing), §23.1 (`news` table).

## Objective

Get deduplicated, categorized, relevance-scored news flowing into the `news` table through a
real provider (behind the `NewsProvider` interface), respecting the provider's license terms.

## Scope

1. **Implement the real `NewsProvider`** for the provider chosen in ADR-0008. Same reliability
   bar as other providers (timeout/retry/circuit breaker/logging/cache).
2. **Licensing (LGL-004):** store headline, URL, publisher, timestamp, and a short
   description/summary always. Store full article `content` **only if** the provider's terms
   permit it — check ADR-0008 before deciding; if unsure, don't store full text, store the
   summary and a link.
3. **Deduplication:** content-hash exact-duplicate detection, plus near-duplicate clustering
   (embedding similarity above a threshold within a time window) so the same story from
   multiple outlets collapses into one `event_cluster_id` with "N sources."
4. **Categorization:** classify each item into one of: Earnings, Product, Regulation, Legal,
   Management, Partnerships, M&A, Industry, Macro. A small/cheap LLM call or a rule-based
   classifier is fine here — this is a labeling task, not a factual-claim task, so it doesn't
   need the full citation-verification machinery from Phase 3a. Store the category on `news`.
5. **Entity resolution & relevance scoring:** score 0–1 how relevant an article actually is to
   the company (a passing mention of NVIDIA in an unrelated article should score low); store
   `relevance_score`; make the threshold for "shown by default" configurable.
6. **Source credibility tier:** tag each publisher with a tier per spec §15 (Tier 4 for
   licensed/reputable financial news, Tier 5 for everything else) — store on the `news` row or
   look up by publisher at render time, whichever is simpler given your schema.
7. **2-sentence AI summaries:** generate a short summary per news item; because this summary
   feeds into the report later, keep the output traceable back to the article text/description
   even though full entailment-checking machinery isn't required at this stage (Phase 3a's
   `NewsItemSummary` schema expects `source_ids`).
8. **Freshness:** near-real-time polling for watched companies (target ≤ 15 min).

## Out of scope for this file

Don't build the event-clustering UI or filters — that's Phase 4d. Don't wire this into the
research report's citation-verification pipeline in detail — Phase 3a/3b will consume
`news`/`NewsItemSummary` and apply the full verification pass there; this file just needs to
produce clean, well-shaped rows with a category, relevance score, and a summary tied to a
`document_id`.

## Definition of Done

- [ ] `news` table populates for seed companies with headline, publisher, URL, timestamp,
      category, relevance_score, and (if licensed) content
- [ ] Exact and near-duplicate stories collapse into one `event_cluster_id`
- [ ] Every stored item has a category from the fixed taxonomy
- [ ] A deliberately low-relevance mention (company named only in passing) scores below the
      display threshold in a test
- [ ] Every AI-written summary is traceable to the underlying article text/description (no
      summary invents a fact not in the source)
- [ ] Licensing decision from ADR-0008 is respected — full-text storage only if permitted
