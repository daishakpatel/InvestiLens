# UI Step 3 — Company Hero, Overview & Financial Data

**Prerequisites:** Steps 1 and 2 done (read both `## Hand-off` sections). The five-tab company
frame exists.
**Blocks:** Step 5's polish pass. Independent of Step 4; the two can run in either order.
**Spec refs:** §9.4 (dashboard header), §10.2 to §10.8 (financial panels), §12 (metrics, DR-040 to
DR-042), FR-011, FR-013, UI-003.

## Objective

Make the first screen of a company page the best screen in the product: a price hero in the
Robinhood mould, an Overview that answers "what is this business and how is it doing" at a glance,
and a Financials tab where charts and tables feel like one calm system. This is the step that
decides whether the product feels premium.

This step is large. If it will not fit one session, split it at the line marked **3b** and hand
off in between.

## Scope

### 1. Chart system (`frontend/src/charts/`)

Build the shared pieces first; every chart below uses them.

- `chartTheme.ts`: reads tokens from CSS variables at render so charts follow the theme switch
  without a reload. Axis ticks in `subtle` at 12 px, tabular figures; **no vertical gridlines**,
  horizontal gridlines as a 1 px `border` dash or none; no axis lines; no chart border.
- `ChartTooltip`: one tooltip component for all charts. `surface` background, hairline border,
  label in `muted`, value in `text` with tabular figures, period and source line beneath.
- `ChartFrame`: title row, optional controls, the chart, and the **"View as table" toggle plus
  CSV export** that FR-013 requires. Keep `MetricChart`'s existing table and export behaviour;
  move it here so every chart gets it.
- Loading is a `Skeleton` of the chart's shape. Empty is one sentence saying which data is
  missing and why (for example "Quarterly figures are not available for this company yet").
- Bars: 2 px top radius, `text` at 85% for a single series, direction colours only when the
  series is itself a change (growth, margin delta). Lines: 1.75 px, no dots except on hover.

### 2. Price hero (`components/company/PriceHero.tsx`)

Replaces the price and stat row in the company header on the Overview tab.

- **The number:** last close at 48 px, tabular. Beneath it, the change over the *selected range*
  as absolute and percent with `Delta`, and the range label ("past year"). Colour of the line and
  the delta follow the sign of that change.
- **The chart:** full content width, 320 px tall (220 px on mobile), a single line with a very
  faint gradient fill beneath it, no axes, no gridlines. A dotted baseline at the range's opening
  price. Recharts `AreaChart` fed by `usePrices`.
- **Scrubbing:** hovering or dragging moves a vertical cursor; the big number and delta update to
  the hovered day and the date appears above the cursor. Leaving restores the latest values.
  Keyboard: the chart is focusable and arrow keys move the cursor one session at a time.
- **Range selector** under the chart: 1M, 3M, 6M, 1Y, 5Y, as a text `SegmentedControl`. Slice the
  already-fetched series client-side; do not refetch per range. Hide ranges the data cannot fill.
- **Honesty:** prices in dev are synthetic and end-of-day. Show "End-of-day close · as of
  <date>" from the freshness data in `subtle` text (FR-011). No "live" styling, no pulsing dot.
- **No price data** (AMD and INTC today): the hero collapses to the company name block and a
  one-line note; the page must not show an empty chart box.
- Use adjusted close for the line so the 2024 split does not draw a cliff; show raw close as the
  headline number.

### 3. Key stats (`components/company/KeyStats.tsx`)

- A single row of `Stat`s under the hero, separated by space, not boxes: Revenue, Net income,
  EPS, Gross margin, plus Market cap and P/E **only when they have values**. A stat with no data
  is omitted, not rendered as "—".
- Each keeps its source / period / formula tooltip (§9.4) and, where a prior period exists, a
  year-over-year `Delta`.
- On mobile the row becomes a two-column grid.

### 4. Overview tab (`pages/tabs/OverviewTab.tsx`)

Top to bottom: Price hero, Key stats, then two columns on desktop (one on mobile).

- **Left, wider:** "Performance" with two compact charts side by side, Revenue and Net income
  over the last five fiscal years, each linking to the Financials tab.
- **Right:** "About" as a definition list (sector, industry, exchange, fiscal year end, CIK), and
  "Latest" showing the three most recent filings and three most recent headlines as plain rows
  linking to their tabs.
- **Research teaser:** if a report exists, show the first two executive-summary claims with the
  `AiMark` and their citation chips, and a link to the Research tab. If none exists, one line and
  a "Generate research" button.
- Move `DataRefreshChecklist` out of the main flow into a popover behind a small "Data status"
  control near the freshness text. It is diagnostic, not content.

**— 3b: split here if needed —**

### 5. Financials tab (`pages/tabs/FinancialsTab.tsx`, absorbs `ValuationTab.tsx`)

- **Controls row**, sticky under the sub-header: period `SegmentedControl` (Annual, Quarterly,
  TTM) and a "Show growth" switch. Disable, with a tooltip, any period the company has no data
  for instead of leading to six empty charts.
- **In-page section nav** (pill `Tabs`, scroll-spy): Income, Margins, Cash flow, Balance sheet,
  Valuation.
- Each section is a heading, a two-column grid of charts on `ChartFrame`, and no surrounding box.
- **Statement table** per section: a `DataTable` with metrics as rows and periods as columns,
  newest on the right, numbers in $M or $B chosen per table with the unit in the caption (convert
  at display time only, never in data). Hovering a cell shows the lineage tooltip that
  `useMetricLineage` already powers; N/A cells show the reason code in the tooltip (DR-041).
- **Valuation section:** render whichever valuation metrics exist as `Stat`s. When none exist,
  one sentence explaining that price-based ratios are not computed yet. Delete `ValuationTab`.
- CSV export remains available for every table and chart (FR-013).

### 6. Earnings reaction

The "Earnings-day price reaction" table currently lives on the Filings tab. Leave the data
there, but restyle it with `DataTable` and `Delta` here since it shares this step's components.

## Out of scope for this file

Research, Filings diff, News, chat, citations (Step 4). Compare and Portfolio (Step 5). No new
endpoints, no intraday data, no technical indicators, no candlesticks.

## Definition of Done

- [ ] `/company/NVDA` opens on a hero with a 48 px price, a range-aware delta, and a chart that
      scrubs by mouse, touch, and arrow keys with no layout shift
- [ ] Changing range does not trigger a network request; ranges with no data are not offered
- [ ] A company with no prices (AMD) renders a clean Overview with no empty chart or dash-filled
      stats; JPM shows no gross-margin stat or shows N/A with its reason, never 0
- [ ] Every chart follows the theme switch without reload and offers a table view and CSV export
- [ ] Financials has one controls row, five sections, statement tables with lineage tooltips, and
      `ValuationTab.tsx` is deleted
- [ ] No categorical chart colour is used for a single series; gains and losses always carry a
      sign or arrow as well as colour (UI-003)
- [ ] Overview and Financials are usable at 360 px wide
- [ ] `npm run screenshots` captures for Overview and Financials (NVDA, AMD, JPM) in both themes
      and widths are listed in the hand-off
- [ ] `make check` green and `npm run build` succeeds; Recharts is still in its own chunk
- [ ] `## Hand-off` section appended to this file
