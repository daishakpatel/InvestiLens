# UI guide

How the frontend looks and behaves, and how to add to it. The decisions behind it, with measured
contrast, are in [ADR-0028](decisions/0028-ui-rebuild-design-system.md); the five-step rebuild
that produced it is recorded in `Instructions/UI_plan/`.

## Principles

1. **Content is the interface.** A section is a heading and its content, set apart by space or a
   hairline. No card inside a card.
2. **One hero per screen.** The price, the report, the comparison table. Everything else is
   visibly secondary.
3. **Colour is information.** Green and red mean gain and loss and nothing else. `primary` marks
   the one accent. AI-generated content carries a small violet mark. Everything else is grey.
4. **Numbers are typeset.** Tabular figures, right-aligned in tables, one formatter per kind of
   value (`lib/format.ts`, `charts/series.ts`). N/A is never shown as zero.
5. **Evidence one click away, never in the way.** A citation is a superscript that opens the
   source beside the text.
6. **Fast and calm.** Loading states are shaped like what replaces them, so nothing jumps.

Dark is the default for everyone; light is a choice (the account menu), never inferred from the
operating system.

## Tokens

All colour lives in `frontend/src/index.css`: dark on `:root`, light on `:root.light`. Components
use the Tailwind utilities generated from the tokens and never a literal colour.

| Token | Utility | Use |
|-------|---------|-----|
| `--bg` | `bg-bg` | Page canvas |
| `--surface` | `bg-surface` | Raised layers: panels, menus, row hover |
| `--surface-2` | `bg-surface-2` | Inputs, chips, the selected item |
| `--surface-3` | `bg-surface-3` | Pressed |
| `--border`, `--border-strong` | `border-border`, `border-border-strong` | Hairlines; inputs and floating layers |
| `--text`, `--text-muted`, `--text-subtle` | `text-text`, `text-muted`, `text-subtle` | Primary, secondary, tertiary text |
| `--primary`, `--primary-contrast` | `bg-primary`, `text-primary-contrast` | The accent and text on it |
| `--positive`, `--negative` | `text-positive`, `text-negative` | Gains and losses only |
| `--warning` | `text-warning` | Caveats: stale data, weights that do not add up |
| `--ai` | `text-ai` | The AI mark |
| `--scrim` | `bg-scrim` | Behind a modal layer |
| `--chart-ink`, `--chart-ink-strong`, `--chart-grid` | via `charts/chartTheme.ts` | A single series, its hovered mark, gridlines |
| `--chart-1` … `--chart-6` | `var(--chart-n)` | Categorical hues (see Charts) |
| `--duration-fast`, `--duration-slow` | default, `duration-(--duration-slow)` | 120 ms and 200 ms |

Type: Inter Variable, Latin subsets only, self-hosted. Scale: `text-caption` 12, `text-label` 13,
`text-sm` 14, `text-body` 15, `text-title` 18, `text-heading` 24, `text-display-s` 32,
`text-display-l` 48. Weights 400, 500, 600. `tnum` on anything numeric.

Shape: `rounded-control` (6 px), `rounded-surface` (10 px), `rounded-full` for pills. Page width
1240 px through `Container`. No shadows in dark; `shadow-float` on floating layers in light.

## Motion

One set, defined in the theme. Hover and press are 120 ms (every `transition-*` utility defaults
to it). Things that arrive take 200 ms ease-out: `animate-fade-in` for menus, rows and chips,
`animate-slide-in` for the side panel. A figure that changes replays `animate-value`. Nothing
travels more than 8 px, and all of it is off under `prefers-reduced-motion`.

On a Radix layer (popover, menu, tooltip, the palette) write the entrance as
`data-[state=open]:animate-fade-in`. Radix keeps a closing layer mounted while an animation is
running on it, so an unconditional animation leaves a ghost behind.

## Primitives (`components/ui/`)

| Component | Use it for |
|-----------|-----------|
| `Button`, `IconButton` | Actions. `primary` at most once per view; an icon button always has a `label`. |
| `Input`, `Select` | Fields. Native `select`, skinned. 40 px tall on touch devices. |
| `Switch` | A setting that applies at once. Its state is the confirmation; no toast. |
| `SegmentedControl` | Two to five exclusive choices (range, period, filter). |
| `RouteTabs`, `PillTabs` | Page sections backed by routes; views inside a page. |
| `Badge`, `FreshnessBadge` | A status dot with text, only where the status matters. |
| `Stat`, `Delta` | A labelled figure with its lineage on hover; a signed change (sign, arrow and colour). |
| `Section` | Heading, optional actions, content. `kind="ai"` adds the AI mark. |
| `Skeleton`, `Spinner` | Loading. Match the skeleton to the shape and height of what replaces it. |
| `LoadingState`, `EmptyState`, `ErrorState`, `AsyncContent` | The four states every data region has. |
| `Tooltip`, `Popover`, `DropdownMenu` | Explanation on hover or focus; a small form; a list of actions. |
| `DataTable` | Any table: sticky header, pinned first column, keyboard-scrollable when it overflows. |
| `AiMark` | Marks AI-generated content, once per section. |
| `Container` | Page width and gutters. |

Elsewhere: `components/panel/PanelProvider` (the one side panel: citations, and the assistant on
a company page), `components/citations/` (chips, cited text, the source view),
`components/CommandPaletteContext` (`open()` to search, `pick()` to choose a company for a page),
`components/SignInHint` (what a signed-out reader sees in place of a personal feature).

## Charts (`charts/`)

- `ChartFrame` gives every chart its title, a table view of the same data, and a CSV download.
  Build a new chart inside it.
- A single measure is drawn in neutral ink (`MetricChart`, `ComparisonBars`). A line that is
  itself a change (the price over a range) takes `positive` or `negative`.
- The six categorical hues exist for parts of a whole that only colour can tell apart (sector
  exposure). Use them in order, never cycled, and keep neighbouring slots adjacent: that is what
  they are validated for. A seventh category folds into "Other".
- Never two scales on one axis. `Sparkline` is plain SVG for list rows, with no chart library.

## Earnings quality tab (Phase 7d)

`/company/:ticker/quality` (`pages/tabs/EarningsQualityTab.tsx`):
- Five `QualityCard`s (accruals, cash conversion, dilution, Beneish, Altman · Piotroski). Each has
  a lead figure, an optional companion figure, the TTM and peer context, and a one-line
  explanation.
- `CashEarningsChart`: net income, operating cash flow and FCF as bars, with the accruals ratio on
  a right axis, built from the measures' own inputs.
- A five-year `DataTable`.
- An inputs disclosure whose every value opens the citation drawer.

Rules:
- Every score carries the screening caveat (`role="note"`).
- A figure that is missing or N/A is a sentence saying why, never a zero or a dash.
- Colour follows the gain/loss rule: only "above the Beneish threshold" is toned, and it uses
  `warning`. Altman zones and everything else stay neutral, and a text label always goes with the
  colour.
- The chart's series use categorical hues, because none of them is a gain or a loss.

## Red flags (Phase 7e)

The Overview's "Red flags" section (`components/company/RedFlags.tsx`) heads the right column.
- Each row shows the label (the rule's explanation as a tooltip), a severity badge with words,
  then the form and filing date and any roles. Below that come the filing's own words (two lines,
  quoted, a button that opens the citation drawer) and an "Open filing" link.
- Severity follows the gain/loss colour rule: `warning` tone for warning and critical (worded "Read
  closely" / "Worth reading"), neutral for info ("For awareness"). Never green or red.
- Three rows show, then "Show all n".
- The empty state reads "Scanned through <date>; nothing reported.", and the error state offers
  "Try again".
- A "How to read this" disclosure says flags are reported events, not conclusions.
- The Overview tab carries the count of flags filed in the last year (`TabDef.count`, hidden at 0).

## Footnotes tab (Phase 7f)

`/company/:ticker/footnotes` (`pages/tabs/FootnotesTab.tsx`), between Earnings quality and
Research.
- A category sidebar (`note_taxonomy_v1` order; horizontal scroll on narrow screens) selects one
  category. Its notes are listed as links that open the note's first paragraph in the citation
  drawer.
- "Reported figures": schedules (debt maturities, undiscounted lease payments) as a `LadderChart`
  only when every window is reported; other XBRL facts in a compact table, derived ones marked
  "Derived" with the formula as a tooltip; then what the filing did not tag, in words. Every
  value opens its source.
- "Summary · Note N" sections use `Section kind="ai"`. Each bullet carries a citation chip and the
  quote it rests on. Abstained summaries read "Not summarised …"; pending ones "Not summarised
  yet".
- "Compare with prior year" opens `FilingDiffView` with `note={category, label}` (no baseline
  picker, no risk-factor switch).
- Low-confidence segmentation and a missing 10-K are stated in a warning note above the layout.

## Governance tab (Phase 7g)

`/company/:ticker/governance` (`pages/tabs/GovernanceTab.tsx`), after Footnotes.
- The header states the proxy's fiscal year and filing date, with a proxy-year selector, and a
  warning listing sections not found in the proxy.
- Left: "Board" under `Section kind="ai"`. Each field shows its value or "Not stated"; hovering
  shows the quote, selecting it opens the paragraph. The independence ratio is shown as computed
  in code.
- Right, "CEO pay" (badge "Extracted from filing tables"): the CEO's Summary Compensation Table
  rows by fiscal year (name once above; short component headers so Total stays on screen), a
  note when rows were rejected, the pay ratio with the CEO total it was checked against, and
  other named officers in a disclosure.
- "Pay versus performance" (badge "From the proxy's XBRL"): `PayVsTsrChart` (CEO pay actually
  paid as bars, TSR and peer TSR on $100 as lines), or the reason it is missing.
- "CEO total pay over time": `LadderChart` over `/governance/history` (`columnHeader`/`source`
  props).
- With no processed proxy, an empty state gives the reason and how many proxies were ingested.

## Valuation bands and peer sets (Phase 7h)

- Financials → Valuation (`components/valuation/ValuationBands.tsx`): under the existing stats, a
  "Valuation bands" block with a peer-set select. Each multiple gets a `RangeBar`: the 5-year
  min–max as a darker segment on a track, a marker labelled "Today 26.4×", and a dashed tick
  labelled "Peer median 30.0×". Every mark has text; colour only separates the track from the
  range. Below it: the 5-year range and median, the positional labels with `n`, and peers left
  out (struck through, with the reason). A multiple that is `not_meaningful`, missing or has
  insufficient history shows its reason instead of a bar. Multiples print as `x.x×`, yields as `%`.
- Compare (`components/valuation/PeerSetPanel.tsx`): under the company picker, the first company's
  peer sets as chips. "Why these peers?" lists each member's rationale, greying members the P/E
  band had to leave out. "Compare with these" puts the set on the page (six companies at most,
  stated when cut), and "Edit" opens an editor (name, up to 12 tickers) that saves a user set
  (signed-in only; the server's message names unknown tickers).

## Guidance vs actual (Phase 7i)

Filings tab, earnings area (`components/guidance/GuidanceSection.tsx`, `lib/guidance.ts`), above
"Earnings-day price reaction", under the AI marker (the figures are read by a model and kept only
if they match the release's words):
- A one-line scope note: company guidance only, no consensus estimates.
- The track-record line: "Revenue came in above the guided range in 7 of 7 quarters, within it in 0
  and below it in 0. (n=7)", or "Insufficient history (n=3)" below 4 comparable quarters.
  Positional wording only; never "conservative", "sandbagging" or "reliable".
- A range-vs-actual dot plot for revenue, oldest quarter first: each row puts the guided range
  (a band) and the actual (a dot) on one shared axis of "% from the guided midpoint", so quarters
  of different size compare; the right column and each row's accessible name state the result in
  text. A row opens the guidance quote.
- A table (Period, Metric with a GAAP/Non-GAAP tag, Guided, Actual, Result chip with text, vs
  midpoint). The guided figure is a dotted-underline button opening the citation drawer on the
  release paragraph; revisions are listed under it ("Revised 2026-08-26: …"). The actual opens its
  metric's evidence. A non-comparable row stays, with its explanation in the Actual cell ("Guided
  on a non-GAAP basis; GAAP actual not comparable."). Money deltas are `+5.7%`, margin deltas
  `+0.4 pts`.
- States: loading/error from `AsyncContent`; empty "No guidance has been read from this company's
  earnings releases yet."

## Adding a screen

1. Add the route in `App.tsx` as a `lazy` import, so it is its own chunk.
2. Wrap the page in `Container`. Give it one `h1` and call `useDocumentTitle`.
3. Fetch through a hook in `lib/queries.ts`, validated by a schema in `lib/schemas.ts`. Types come
   from `services/api.d.ts`.
4. Design all four states. Shape the loading state like the content. Say what is missing and why.
5. AI-generated content sits under a `Section kind="ai"`, with every claim cited. Text that
   arrives without citations is not shown. Citations need `PanelProvider` above them.
6. Any link built from API data goes through `safeHttpUrl`. API text is rendered as text.
7. State a reader would share or go back to (a selection, a tab, a filter) belongs in the URL.
8. Check it at 360 px, by keyboard alone, and in both themes. Add it to
   `e2e/tests/screenshots.spec.ts`, and to `visual.spec.ts` if it is a key screen.
