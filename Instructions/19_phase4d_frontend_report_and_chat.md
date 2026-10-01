# Phase 4d — Frontend: AI Research, Filings, News & Chat

**Prerequisites:** `18_phase4c_frontend_dashboard.md` done (dashboard shell and tab structure
exist); `14_phase3b_research_report_generation.md` and `15_phase3c_chat_qa.md` should be far
enough along to return real data, though this can be built against mocked report/chat
responses first.
**Blocks:** nothing downstream — this is the most visible, demo-critical part of the frontend.
**Full spec sections:** §27.1 (Pages 4–7), §27.2 (report card UI), §13.7 (citation UI — the
most important part of this file), §10.14 (chat feature requirements).

## Objective

Build the parts of the UI that make the project's core idea visible: a generated report you
can trust because every claim is clickable back to its source, plus the filing viewer, news
feed, and chat interface.

## Scope

1. **Filings page (§27.1 Page 4):** searchable filing list, in-app viewer with section
   navigation (Item 1, 1A, 7, 7A, 8, notes), in-document keyword + semantic search. Leave a
   placeholder for the filing-diff view if Phase 6b hasn't landed yet.
2. **News page (§27.1 Page 5):** filter by date/category/source/relevance; cluster view
   ("N sources") with tier badges, reading from Phase 1e's data.
3. **AI Research page (§27.1 Page 6, §27.2):** render the full generated report as cards:

   ```text
   ┌─────────────────────────────────────┐
   │ Executive Summary                   │
   │                                     │
   │ NVIDIA's revenue increased... [1]   │
   │                                     │
   │ NVIDIA's data-center business... [2]│
   └─────────────────────────────────────┘
   ```

   Every section from the `ResearchReport` schema gets a card. Each card shows a `Data` vs
   `AI interpretation` badge per FR-010. Include version history and a "what changed since
   last report" view if `supersedes_report_id` is populated; a PDF/Markdown export button.
4. **Citation UI (§13.7 — the most important piece of this file):**
   - Numbered, keyboard-focusable inline citation chips
   - Clicking one opens a modal calling `GET /sources/{source_id}`, showing the source title,
     section path (or page, for PDFs), and the **highlighted supporting span**
   - "Open original filing" deep link, "Copy citation," and — specifically for
     `derived_metric` sources — a "View derivation" button that shows the formula and input
     chain (this is what makes the project's citation architecture visible and impressive)
   - Reference list at the end of each report/answer with tier badges
5. **Insiders & Ownership tab:** if Phase 6/insider data exists, render Form 4 and 13F data
   here; otherwise leave a clearly-labeled "coming soon" state rather than a broken tab.
6. **Chat page (§27.1 Page 7):**
   - Streaming answer rendering (consuming `POST /chat/stream`'s SSE)
   - Citations resolve inline as the answer completes
   - Tool-trace panel ("Checked: XBRL revenue FY2023–25, 10-K MD&A...")
   - Suggested follow-up questions
   - Thumbs up/down feedback control wired to `POST /chat/messages/{id}/feedback`
   - Clear abstention rendering when the backend returns "insufficient evidence" — this should
     look intentional, not like an error
7. **Report generation UX:** trigger `POST /research`, show job progress (reuse the SSE
   progress pattern from Phase 4c's data-refresh UI), and render the completed report when
   ready; handle the "AI failed but data is still available" fallback state from spec §10.16.

## Out of scope for this file

Company comparison and portfolio pages (Phase 6). Filing-diff rendering specifics beyond a
placeholder (Phase 6b). Admin UI.

## Definition of Done

- [ ] A full generated report renders as cards for all report sections, each with correct
      Data/AI-interpretation badging
- [ ] Every citation chip opens a working modal with the highlighted supporting span
- [ ] A derived-metric citation's "View derivation" shows the correct formula and input chain
- [ ] Chat streams tokens, resolves citations inline, and shows the tool-trace panel
- [ ] An abstained chat answer renders clearly as "insufficient evidence," not as a broken
      response
- [ ] Report generation shows live progress via SSE and correctly falls back to "data
      available, AI generation failed" when that happens
- [ ] Filing viewer navigates by section and supports in-document search
- [ ] News page filters and clusters correctly with tier badges visible
