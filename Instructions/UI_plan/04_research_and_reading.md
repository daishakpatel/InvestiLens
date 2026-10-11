# UI Step 4 — Research, Filings, News & the Assistant

**Prerequisites:** Steps 1 and 2 done (read their `## Hand-off`). Step 3 is not required.
A completed research report in the dev DB (`make seed`) so the Research tab has content to design
against.
**Blocks:** Step 5's polish pass.
**Spec refs:** §10.9 to §10.16 (report sections), §13 (citations, CIT-001 to CIT-006), §37.4,
§37.5, FR-010, FR-020, FR-027, FR-030, HAL-002.

## Objective

The reading experiences are where InvestiLens earns trust. Today they are stacks of bordered
cards with badges on every row and a modal that hides what you were reading. Rebuild them as a
calm, editorial reading surface where evidence opens beside the text, and make the assistant
available from anywhere on a company page.

This step is large. If it will not fit one session, split it at the line marked **4b**.

## Scope

### 1. Citation drawer (`components/citations/`)

Do this first; everything below depends on it.

- Replace `CitationModal` with a **right-side `Drawer`** (420 px, full-width sheet on mobile). The
  page behind stays readable and scrollable, so the reader keeps their place.
- Citation chips become small superscript numerals in `primary`, no background until hover.
  Clicking one opens the drawer; clicking another swaps its content without closing; the chip
  for the open source is highlighted in the text.
- Drawer content, in order: source title and type, tier and date in `muted`, the quoted passage
  with the cited span highlighted, section path, "Open original" link, "Copy citation". For a
  derived metric keep the existing derivation view (formula, version, inputs, lineage chips).
- Keep `CitationContext`'s `open(sourceId)` API so no caller changes. Keep `ReferenceList`,
  restyled as a quiet numbered list.
- Loading and error states inside the drawer; Escape and the close button both dismiss; focus
  returns to the chip that opened it.

### 2. Research tab (`pages/tabs/ResearchTab.tsx`, absorbs Risks and Management)

One long, well-typeset document rather than twelve cards.

- **Layout:** a reading column of at most 720 px, with a sticky table of contents on the left on
  desktop (scroll-spy) and a "Jump to" select on mobile.
- **Header:** "AI research" with the `AiMark`, generated date, and data-freshness in `subtle`;
  Export Markdown and Print actions as ghost buttons. This one header satisfies FR-010 for the
  whole document; do not repeat an AI badge on every section.
- **Prose sections** (summary through valuation): section heading, then each claim as a
  paragraph with its superscript citations. Evidence strength (HAL-002) is shown only when it is
  *not* strong: a small `warning` "Limited evidence" note after the claim. Strong and supported
  claims carry no badge. Never show a raw score.
- **Bull and bear factors** side by side as two plain columns with a `positive` and a `negative`
  hairline on top; stacked on mobile.
- **Risks:** a list, each with its category as `muted` text, the description with citations, and
  the change status from the filing diff ("New in latest 10-K", "Reworded", "Unchanged") as a
  quiet `Badge`. A filter row lets the reader show only New and Reworded.
- **Management:** the cited management statements, then the language-tracking grid (below).
- **Sections with insufficient evidence** are listed once at the end, plainly, as "Not enough
  evidence to write about: …". Abstaining is a feature; do not style it as an error.
- **No report yet:** a centred `EmptyState` explaining what a report contains, with one
  "Generate research" button (sign-in prompt if anonymous). While generating, show the job's
  progress and keep the FR-030 fallback links to Financials and Filings.
- `RisksTab.tsx` and `ManagementTab.tsx` are deleted; their old routes already redirect.

### 3. Management language grid (`components/filings/LanguageTracker.tsx`)

- Keep it a grid (topics × filings); it is the right form. Restyle as a heat table: cells are
  flat rectangles with 2 px gaps, intensity as `primary` opacity, the value in tabular figures
  inside each cell, "first appears" / "drops out" as a small dot marker with a tooltip rather
  than text inside the cell.
- Selecting a cell opens the counted statements **in the citation drawer** (a list of sentences,
  each opening its source), not in a block under the table.
- The hedging row stays visually separated and keeps its "word count, not an AI judgment" note.

**— 4b: split here if needed —**

### 4. Filings tab (`pages/tabs/FilingsTab.tsx`, `components/filings/FilingDiffView.tsx`)

- **Layout:** a 300 px filing list on the left (sticky, own scroll), detail on the right. On
  mobile the list is the page and a filing opens as its own view with a back control.
- **List:** filter chips for type (All, 10-K, 10-Q, 8-K) above a text filter. Rows show type,
  period end, and filed date; the selected row uses `surface-2`, no border change.
- **Detail** has two views switched by pill `Tabs`: **Changes** (default for 10-K and 10-Q) and
  **Outline**.
- **Changes view:** a summary line in plain words ("1 new risk factor, 16 reworded, 8 unchanged
  since the 10-K filed Feb 26, 2025"), a baseline picker, a "Risk factors only" switch, and the
  status filters as toggle chips. Each change is a row: status, heading, section, similarity for
  reworded items. Expanding a reworded row shows the word diff inline with insertions in
  `positive` on a faint tint and deletions struck through in `negative`; long unchanged runs stay
  collapsed with a "show more context" control. New and removed rows expand to the full passage.
  "Prior filing" and "This filing" source links open the citation drawer.
- Keep the low-confidence and "boundaries were estimated" notices; they are honesty signals.
  Render them as one quiet `warning` line, not a banner.
- **Outline view:** the section list with its filter, and "Open original" as the primary action.
- Earnings reaction table sits beneath, styled in Step 3 (style it here if Step 3 has not run).

### 5. News tab (`pages/tabs/NewsTab.tsx`)

- A single feed, newest first, grouped under day headings. Each item: headline at 15 px medium,
  publisher and time in `subtle`, category as `muted` text, two-line summary. Source tier shows
  only as a small label for tier 4 and 5 publishers, since that is when it matters.
- Clustered stories collapse to the lead headline with "+3 more sources" that expands in place.
- Filters (category, publisher, minimum relevance) live in one `Popover` behind a "Filter"
  button with an active-count indicator, instead of a permanent row of selects.
- Headlines link out in a new tab; no article body is ever shown (LGL-004).

### 6. Assistant panel (`components/assistant/`, replaces `pages/tabs/ChatTab.tsx`)

- The "Ask" button in the company header opens a **docked right panel** (440 px) that pushes the
  page content rather than covering it on wide screens (1440 px and up), overlays as a `Drawer`
  below that, and is full-screen on mobile. It stays open while the user changes tabs.
  `/company/:ticker/chat` opens the page with the panel open.
- When both the assistant and the citation drawer are wanted, the citation content opens
  **inside** the assistant panel as a pushed view with a back control. Never two side panels.
- **Empty state:** three or four suggested questions for this company as tappable rows.
- **Messages:** user messages right-aligned on `surface-2`; answers unboxed on the canvas with
  the `AiMark`, streaming text, superscript citations, and a collapsed "How this was answered"
  disclosure holding the tool trace.
- Abstentions and refusals keep their intentional, non-error styling: a neutral note explaining
  why (no evidence, out of scope, not investment advice).
- Composer pinned to the bottom: auto-growing textarea, Enter sends, Shift+Enter newline, a stop
  control while streaming. Thumbs up / down under each answer keep posting feedback.
- Anonymous users see the suggested questions and a sign-in prompt in place of the composer.
- Keep `lib/chatStream.ts` and the answer-text citation parsing untouched; this is a re-skin and
  a relocation, not a rewrite of the chat logic.

## Out of scope for this file

Compare, Portfolio, Watchlist (Step 5). New report sections, new chat capabilities, in-app
rendering of full filing text (no endpoint exposes it). No backend changes.

## Definition of Done

- [x] Clicking a citation anywhere opens the drawer beside the content; the page behind remains
      scrollable; a second citation swaps content; focus returns to the chip on close
- [x] Research reads as one document with a working table of contents; exactly one AI mark heads
      it (FR-010); every rendered claim still has at least one citation chip (FR-020)
- [x] Risks show change status and can be filtered to New and Reworded
- [x] The Changes view shows a plain-language summary and an inline word diff for NVDA's latest
      10-K; both filings' passages open in the drawer
- [x] The assistant opens from any company tab, survives tab changes, streams an answer with
      working citations, and shows abstention and refusal as intentional states
- [x] There is never more than one side panel open at once
- [x] `ChatTab.tsx`, `RisksTab.tsx`, `ManagementTab.tsx`, and `CitationModal.tsx` are deleted
- [x] Research, Filings, News, and the assistant are usable at 360 px wide and by keyboard alone
- [x] `npm run screenshots` captures for Research, Filings (Changes), News, and the assistant
      open, in both themes and widths, are listed in the hand-off
- [x] `make check` green (including `xssGuard.test.ts`: no `dangerouslySetInnerHTML` introduced)
      and `npm run build` succeeds
- [x] `## Hand-off` section appended to this file

## Hand-off

Done 2026-10-11. `make check` green (450 backend, 68 frontend tests, `xssGuard.test.ts` included);
`npm run build` succeeds; `e2e/tests/reading.spec.ts` 15/15 (new), and the whole e2e suite passes
with one worker (58/58). axe reports no serious or critical violations on Research, Research
with a source open, Filings (Changes, a row expanded), News, and the assistant open, in both
themes. Not split at 4b.

**What shipped**

- **One side panel (`components/panel/`).** `CompanyPanels` (wraps the company page, keyed per
  ticker) owns both things that can open beside the page, the assistant and the evidence behind a
  citation, and renders exactly one `SidePanel`. That is what makes "never two panels" structural
  rather than a rule to remember. Three presentations:
  - `docked`: the assistant at 1440 px and up. Part of the layout; the page narrows beside it.
  - `overlay`: below 1440 px, and for evidence at any desktop width. Non-modal: the page scrolls,
    other citations can be clicked, clicking outside does not dismiss.
  - `sheet`: under 768 px. Full screen and modal.

  A citation in the page (`useCitations().open(sourceId)`, unchanged API) replaces what the panel
  shows and remembers the chip for focus return. A citation inside the panel (in an answer, in a
  list of statements) pushes a view with Back. Escape goes back one level before it closes. Page
  evidence closes when the reader changes tab, filing, or view; the assistant and anything open
  inside it stay. `useAssistant()` gives `{ isOpen, open, toggle }`.
- **Citations (`components/citations/`).** `CitationChip` is a superscript numeral, tinted while
  its source is open. `SourceView` (kind, tier, date, the passage with the cited span marked,
  section path, Open original, Copy citation; the derivation view for calculated figures),
  `StatementsView`, `ReferenceList` (titles resolved as rows scroll into view).
  `CitationModal.tsx` is deleted.
- **Research (`components/research/ReportDocument.tsx`, `GenerateReport.tsx`).** A 720 px reading
  column with a sticky contents list (scroll-spy, `lib/useActiveSection.ts`, now shared with
  Financials) and a jump menu on phones. One AI mark. "Limited evidence" is the only strength
  label shown. Bull and bear columns, risks with change status and an "All / New or reworded"
  filter, management statements and the language table, "Not covered", References. Export
  Markdown and Print (print styles force ink on white and hide the app chrome). A claim with no
  source ids is not rendered, as a last check on FR-020. No report: what a report is and one
  button; a report that exists but fails to load says so instead of "none yet".
  `ReportView.tsx` is deleted.
- **Management language (`components/filings/LanguageTracker.tsx`).** Heat table; a figure opens
  the counted statements in the panel, and each statement opens its source.
- **Filings (`pages/tabs/FilingsTab.tsx`, `components/filings/FilingDiffView.tsx`).** Sticky
  300 px list with type chips and a text filter; the open filing and view live in the URL
  (`?filing=&view=`). Changes: a summary sentence (`lib/diffSummary.ts`), baseline picker, "Risk
  factors only", status chips with counts, expandable rows, inline word diff with "Show more
  context", passage links for both filings. Outline: section list and filter. On a phone the
  list is the page and a filing opens as its own view with a back link. The list is sorted by
  filing date (the API pages by id).
- **News (`pages/tabs/NewsTab.tsx`, `lib/newsFeed.ts`).** One feed under day headings; the same
  event from several outlets folds into its best-sourced report with "+N more sources"; filters
  in a popover with an active count; tier named only for tiers 4 and 5.
- **Assistant (`components/assistant/`).** `useConversation` (state, streaming, stop, errors)
  lives at provider level so the conversation survives tab changes. `Assistant.tsx`: suggested
  questions, answers with the AI mark and superscript citations, "How this was answered", neutral
  notes for abstention and refusal, thumbs, a composer (Enter sends, Shift+Enter is a new line,
  stop while streaming), and a sign-in prompt for anonymous readers that returns to the open
  panel. `/company/:ticker/chat` opens the panel and redirects to the company page.
  `lib/chatStream.ts` and the `[n]` parsing are untouched. `ChatTab.tsx` is deleted.
- **`lib/safeUrl.ts`.** Every link built from API data (news URLs, a filing's original, a
  source's deep link) goes through `safeHttpUrl`, which accepts only absolute http(s). React does
  not block `javascript:` hrefs, and these URLs come from third parties. A rejected URL renders
  as plain text, never as a dead link.

**Deviations from this file, and why**

- The panel is 440 px in both roles (the file says 420 for citations, 440 for the assistant):
  one panel that changes width when it changes content would jump.
- Evidence overlays; it never docks. Docking would reflow the paragraph being read every time a
  citation is clicked. The cost: below about 1500 px the panel covers the right edge of the
  reading column while it is open.
- "Open original" sits in the filing's header in both views, not only in Outline.
- A reworded passage's sources show as numbered chips, one per stored excerpt, because a risk
  factor spans several excerpts. NVDA's have about ten on each side.
- Similarity is shown to one decimal above 99.5%, so a reworded passage never reads "100% same".
- News loads the 25 most recent items and says so when there are more; no paging.
- Filings and News are now lazy routes. Loading them eagerly took the entry bundle to 123 kB.

**Bugs found and fixed along the way**

- Old `/risks` and `/management` links redirected to `/research#…` but landed at the top of the
  page: the scroll ran before the report had loaded. `useScrollToHash(ready)` now waits.
- Arriving by `/company/:ticker/chat` and closing the panel before the tab behind it had loaded
  reopened it: the route's effect depended on a callback whose identity changed on close.
  `open` and `toggle` are now stable. `reading.spec.ts` holds the tab chunk back to cover it.

**Backend findings, not fixed (frontend-only step)**

> Update, later on 2026-10-11: the question length, the refresh-token reuse path, and the
> connection-pool stall are fixed (ADR-0029, ADR-0030); e2e runs in parallel again. The other
> two items below still stand.

- `ChatRequest.question` has no maximum length. The composer caps at 2,000 characters, which is
  a convenience, not a control.
- Mock-mode answers are raw strings ("revenue FY2026 = 215938000000.00000000 USD."). The UI shows
  answer text as issued; formatting belongs to the backend.
- NVDA's newest 10-K in the dev database is a seed row with no parsed sections, so the Filings
  tab opens on "risk factors could not be read" with "Compare all sections" offered. Real data
  will not have this; the filing used in tests and captures is id 15.
- Still open from earlier steps: the refresh-token reuse path and the connection-pool stall
  (e2e runs with one worker because of it).

**Test data**

`make seed` was not run (it would re-run mock ingestion over the live-ingested data). Only its
report half was: FakeLLM reports now exist for NVDA, AAPL, and JPM, so `/research/latest` returns
200, but they are placeholder sentences with most sections under "Not covered". Tests and
captures therefore mock that one endpoint with `e2e/fixtures/research-nvda.json`. Its claims
quote the values of real source records and every source id in it resolves. **The research
layout has not been seen against a real LLM report.**

**Captures**

`e2e/screenshots/{dark,light}/{1440,390}/` (29 per folder). New or changed this step:
`company-research`, `company-research-source`, `company-research-statements`,
`company-research-none` (AMD), `company-filings` (Changes, one row expanded),
`company-filings-outline`, `company-filings-list`, `company-news`, `company-news-filter`,
`company-assistant` (replaces `company-chat`). Looked at: Research full page in dark at 1440 and
390, with a source open in dark and light, the statements view, the no-report state; Filings
Changes in dark and light at 1440 and dark at 390; News and its filter in dark; the assistant
signed out (dark 1440) and mid-conversation with a declined question and with a source pushed
(dark 1440, light 1280, dark 390; throwaway captures, since the capture script is signed out).

**Bundle (gzip), Step 3 → Step 4**

| Chunk | Step 3 | Step 4 |
|-------|--------|--------|
| entry `index` | 91.41 kB | 93.16 kB |
| CSS | 8.95 kB | 9.61 kB |
| `CompanyDashboard` | 2.60 kB | 1.91 kB |
| `CompanyPanels` (panel, assistant, source views) | n/a | 7.29 kB |
| `ResearchTab` | n/a | 6.34 kB |
| `FilingsTab` (now lazy) | in entry | 5.10 kB |
| `NewsTab` (now lazy) | in entry | 2.44 kB |

The assistant ships in the company page's chunk, not the entry bundle and not a chunk of its own.
Splitting it further would save about 3 kB and cost the composer its focus on first open.

**Left for Step 5**

- Light-theme pass on the diff tints and the heat table; both pass axe but were tuned in dark.
- The assistant as its own chunk, if Step 5's "loads on demand" is read strictly.
- Print was checked under emulated print media (ink on white, chrome hidden), not in a
  browser's print preview: page breaks are unreviewed.
- The mid-stream state and the stop control were not exercised: mock-mode answers complete
  almost at once. They are covered by reading the code, not by a test.
