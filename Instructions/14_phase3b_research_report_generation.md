# Phase 3b — Research Report Generation

**Prerequisites:** `07_phase1c_financial_metrics.md`, `09_phase1e_news_ingestion.md`,
`12_phase2c_rag_retrieval_pipeline.md`, and `13_phase3a_citation_system.md` all done — this
file is where everything converges.
**Blocks:** `16_phase4a_fastapi_endpoints.md`'s `/research` endpoints (they call this),
`18_phase4c_frontend_dashboard.md` / `19_phase4d_frontend_report_and_chat.md` (nothing to
display without this).
**Full spec sections:** §10 (every report section's detailed requirements — this is the big
one, read all of it), §17 (generation architecture + the full `ResearchReport` schema).

## Objective

Generate the full, citation-verified research report for a company, section by section, using
Phase 1c's numbers, Phase 1e's news, Phase 2c's retrieved evidence, and Phase 3a's
verification — and nothing else.

## Scope

Build one generator per section, each a separate LLM call with only its own evidence subset
(cheaper, more controllable, retryable independently). Assemble into the full `ResearchReport`
schema from Phase 0c. For every section below, follow the detailed requirements in spec §10 —
this task file summarizes what not to skip; the full spec has the exact example text, JSON
shapes, and v2 enhancements.

1. **Executive summary** (§10.1) — 4–7 claims, must touch growth, profitability, a risk, and a
   valuation datapoint when data exists; include an evidence-strength badge.
2. **Company overview** (§10.2) — description/segments/geography from 10-K Item 1 and XBRL
   dimensional facts; competitive-positioning language labeled "as described by the company."
3. **Revenue analysis** (§10.3) — the LLM receives Phase 1c's computed JSON (already includes
   YoY/CAGR) and explains it; never asks the LLM to compute a number. Include the growth
   waterfall and TTM series if Phase 1c/1d support them.
4. **Profitability analysis** (§10.4) — margins, EBITDA (respecting the reliability rule),
   margin bridge.
5. **Balance sheet analysis** (§10.5) — debt/equity, liquidity, working-capital trend.
6. **Cash flow analysis** (§10.6) — FCF, FCF conversion, SBC, capex intensity.
7. **Valuation** (§10.7) — current multiples plus historical distribution if price history
   supports it (Phase 1d); explicit distinction between data and AI interpretation.
8. **News summary** (§10.8) — pull from Phase 1e's categorized, deduplicated news; 2-sentence
   summaries with citations.
9. **Risks** (§10.10) — extract from SEC filings only (Tier 1); never invent a risk; each risk
   needs ≥ 1 citation or it's rejected by Phase 3a.
10. **Management commentary** (§10.11) — group by topic (AI Demand, Revenue Outlook, Margins,
    Capital Spending, Competition, Regulation, Product Roadmap); track how topics evolve across
    periods.
11. **Bull/bear factors** (§10.12–10.13) — generate **both from the same evidence pool**
    (never let bull and bear cherry-pick independently); hedged language only ("potential
    upside factors include…"), never certainty.

**Cross-cutting requirements:**

- Use the LLM provider's **structured output / JSON schema mode**; on a schema failure, allow
  one repair attempt, then mark that section `insufficient_evidence_sections`.
- Every section's output passes through Phase 3a's full verification pipeline before being
  included in the assembled report. A section that ends up with zero verified claims still
  produces a valid (mostly empty, clearly labeled) report section — never fail the whole
  report because one section came back thin.
- Record `prompt_version`, `model`, and `data_version` (hash of the metric snapshot + document
  set used) on every `research_reports` row — this is what makes generation reproducible and
  auditable.
- Async job pattern: report generation runs as a background job (Celery — the task itself can
  be a stub queued via Phase 1a's existing job infrastructure pattern; full job plumbing is
  formalized in Phase 5's background-jobs work, but this file needs the actual generation
  logic to be callable as a job).
- If AI generation fails entirely, the structured financial panels (already computed in Phase
  1c) must still be available — generation failure never take down the rest of the dashboard.
- Report versioning: store `supersedes_report_id` so a later phase can build "what changed
  since last report."

## Out of scope for this file

No chat/Q&A (Phase 3c) — reports are a fixed generation flow, not a conversation. No PDF
export or UI rendering (Phase 4). No filing-diff-aware risk `change_status` (Phase 6) — leave
that field null for now if the diff feature isn't built yet.

## Definition of Done

- [ ] A full `ResearchReport` generates for NVDA, AAPL, and JPM against real ingested data
- [ ] Every claim in the generated report has ≥ 1 citation that passed Phase 3a's verification
- [ ] JPM's report correctly omits or labels "not applicable" for bank-inapplicable metrics
      rather than showing nonsense numbers
- [ ] Bull and bear factors for the same company don't contradict each other on the underlying
      facts (they can disagree on interpretation, not on numbers)
- [ ] A forced section-generation failure (e.g. malformed LLM output in a test) results in that
      section being marked insufficient, not a total report failure
- [ ] `research_reports` correctly records `prompt_version`, `model`, and `data_version`
- [ ] Regenerating with identical inputs and `prompt_version` produces materially the same
      report (temperature near 0)
