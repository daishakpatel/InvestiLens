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

- [ ] Clicking a citation anywhere opens the drawer beside the content; the page behind remains
      scrollable; a second citation swaps content; focus returns to the chip on close
- [ ] Research reads as one document with a working table of contents; exactly one AI mark heads
      it (FR-010); every rendered claim still has at least one citation chip (FR-020)
- [ ] Risks show change status and can be filtered to New and Reworded
- [ ] The Changes view shows a plain-language summary and an inline word diff for NVDA's latest
      10-K; both filings' passages open in the drawer
- [ ] The assistant opens from any company tab, survives tab changes, streams an answer with
      working citations, and shows abstention and refusal as intentional states
- [ ] There is never more than one side panel open at once
- [ ] `ChatTab.tsx`, `RisksTab.tsx`, `ManagementTab.tsx`, and `CitationModal.tsx` are deleted
- [ ] Research, Filings, News, and the assistant are usable at 360 px wide and by keyboard alone
- [ ] `npm run screenshots` captures for Research, Filings (Changes), News, and the assistant
      open, in both themes and widths, are listed in the hand-off
- [ ] `make check` green (including `xssGuard.test.ts`: no `dangerouslySetInnerHTML` introduced)
      and `npm run build` succeeds
- [ ] `## Hand-off` section appended to this file
