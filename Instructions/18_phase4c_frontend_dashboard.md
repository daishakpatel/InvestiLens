# Phase 4c — Frontend: Home, Dashboard & Financials

**Prerequisites:** `03_phase0c_api_contracts.md` done (generated TypeScript client exists) —
you can start against mocked/stubbed API responses before Phase 1–3 finish real logic, then
swap to real data as it lands.
**Blocks:** nothing downstream depends on this specifically, but it's needed for the project to
be demoable at all.
**Full spec sections:** §27.1–27.3 (frontend spec: Home, Dashboard, Financials pages + global
UI rules), §9 (core UX flow this implements).

## Objective

Build the home search page, the company dashboard shell, and the interactive financials page —
the parts of the UI that don't depend on AI generation being finished.

## Scope

1. **Stack setup:** React + TypeScript + Tailwind + Recharts + React Query, Vite, React
   Router, Zod for runtime-validating API responses, generated API client from Phase 0c wired
   in.
2. **Home page (§9.1, §27.1 Page 1):** search box with autocomplete (ticker/name/exchange),
   popular companies, recent searches, watchlist quick links when authenticated.
3. **Company resolution & ambiguity (§9.2):** handle the disambiguation case (e.g. multiple
   matches) with a picker, not a silent best-guess.
4. **Data-refresh progress UI (§9.3):** SSE-driven checklist ("Updating research data... ✓
   Company information ✓ SEC filings...") with per-source pending/running/done/failed states.
5. **Dashboard shell (§9.4, §27.1 Page 2):** company header (price, market cap, revenue, net
   income, EPS, P/E, each with a tooltip showing source/period/formula/last_updated) and tabs:
   Overview, Financials, Valuation, SEC Filings, News, AI Research, Risks, Management,
   Insiders & Ownership, Chat. Build the tab shells now even if some tabs' content lands in
   later files (Phase 4d covers AI Research/Chat/Filings/News in more depth).
6. **Financials page (§27.1 Page 3):** interactive Recharts charts for Revenue, Gross Margin,
   Operating Income, Net Income, FCF, EPS. Include: annual/quarterly/TTM toggle, YoY overlay,
   hover tooltip with formula lineage (pulls from the `/metrics/{name}/lineage` endpoint),
   "View data table" toggle, CSV export, fiscal-vs-calendar period labeling.
7. **Global UI rules (FR-010…013, applied everywhere in this file):**
   - Visually distinguish "Data" panels from "AI interpretation" panels (a badge is enough)
   - Every panel shows freshness (`Updated Sep 27, 2026`) and a stale/failed state, sourced
     from the `as_of`/`freshness_status` fields on API responses
   - Persistent "not investment advice" disclaimer in the footer/layout
   - Loading, empty, error, stale, and partial-data states for every panel — not just the
     happy path
8. **Accessibility & performance (UI-001…008):** keyboard-navigable, aria labels and a
   data-table alternative for every chart, colorblind-safe palette, route-level code
   splitting, responsive layout, light/dark theme, no secrets in the frontend bundle.

## Out of scope for this file

AI Research report rendering, citation UI, chat interface, filing viewer, and news feed are
`19_phase4d_frontend_report_and_chat.md`. Auth screens (login/register forms) belong wherever
Phase 4b's frontend counterpart is handled — if not otherwise assigned, add simple auth forms
here since the dashboard needs a logged-in state, but keep them minimal.

## Definition of Done

- [ ] Home page search + autocomplete works against the real `/companies/search` endpoint
- [ ] Ambiguous company searches show a disambiguation picker, not a silent guess
- [ ] Dashboard header displays all key metrics with correct freshness/tooltip info
- [ ] Financials page renders real charts from `/companies/{ticker}/financials` with working
      annual/quarterly/TTM toggle and CSV export
- [ ] Every panel has visually distinct loading, empty, error, and stale states
- [ ] Disclaimer is visible on every dashboard page
- [ ] Lighthouse accessibility score ≥ 90 on the dashboard (target from NFR-011/UI-004)
