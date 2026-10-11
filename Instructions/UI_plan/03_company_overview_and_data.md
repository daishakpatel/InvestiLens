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

- [x] `/company/NVDA` opens on a hero with a 48 px price, a range-aware delta, and a chart that
      scrubs by mouse, touch, and arrow keys with no layout shift
- [x] Changing range does not trigger a network request; ranges with no data are not offered
- [x] A company with no prices (AMD) renders a clean Overview with no empty chart or dash-filled
      stats; JPM shows no gross-margin stat or shows N/A with its reason, never 0
- [x] Every chart follows the theme switch without reload and offers a table view and CSV export
- [x] Financials has one controls row, five sections, statement tables with lineage tooltips, and
      `ValuationTab.tsx` is deleted
- [x] No categorical chart colour is used for a single series; gains and losses always carry a
      sign or arrow as well as colour (UI-003)
- [x] Overview and Financials are usable at 360 px wide
- [x] `npm run screenshots` captures for Overview and Financials (NVDA, AMD, JPM) in both themes
      and widths are listed in the hand-off
- [x] `make check` green and `npm run build` succeeds; Recharts is still in its own chunk
- [x] `## Hand-off` section appended to this file

## Hand-off

Done 2026-10-11. `make check` green (450 backend, 54 frontend tests); `npm run build` succeeds;
`e2e/tests/company.spec.ts` 18/18 and `shell.spec.ts` 19/19; axe reports no serious or critical
violations on Overview (NVDA, AMD, JPM), Financials (NVDA, JPM; with growth, table view and
Quarterly on), Filings, Home and Compare, in both themes. Not split at 3b: it fit one session.

**What shipped**

- **Chart system (`frontend/src/charts/`):**
  - `chartTheme.ts`: every colour is a CSS variable, so charts follow the theme with no re-render.
    Fixed look: one series in neutral ink (`--chart-ink`, hovered mark `--chart-ink-strong`), bars
    at most 24 px with a 4 px rounded data end, 2 px lines, solid hairline horizontal gridlines
    only, no axis lines or tick marks.
  - `series.ts` (pure, unit-tested): `displayOf` / `Display` (money, percent, multiple, perShare,
    count), `toRows`, `changeBetween`, `axisFor` (round ticks; bars from zero), `pickScale`,
    `pickTableScale`, `formatTick`, `formatValue`, `formatCell`, `shortPeriod`.
  - `ChartTooltip.tsx` (value first, then what it is, then source), `ChartFrame.tsx` (title,
    optional link and summary, table-view toggle, CSV download, loading and empty states).
  - `MetricChart.tsx`: `<MetricChart name points csvName showChange? compact? href? />`. Label,
    bar-or-line, and number format all come from the metric name via `lib/metricCatalog.ts`.
    `showChange` adds a strip of period-over-period changes beneath, on its own scale.
- **`lib/metricCatalog.ts`:** labels for every API metric, which "ratio" metrics are multiples
  (current ratio, debt/equity, P/E…) rather than percentages, the Financials sections, and plain
  wording for the N/A reason codes. Use `metricLabel(name)` anywhere a metric is named (Compare
  still prints raw names such as `yoy_growth`: Step 5).
- **Price hero (`components/company/PriceHero.tsx`)** and **`lib/priceRange.ts`:** 48 px price,
  change over the chosen range, a line coloured by that change with a dotted line at the range's
  opening price, range selector that slices the loaded series, table view and CSV. Scrubbing uses
  pointer events on the wrapper (one path for mouse, touch, and pen); the wrapper is a
  `role="slider"` so arrow keys, Page Up/Down, Home/End and Escape work and screen readers get
  the date and price as `aria-valuetext`.
- **`components/company/KeyStats.tsx`**, **`StatementTable.tsx`**, **`outletContext.ts`**.
- **Overview (`pages/tabs/OverviewTab.tsx`)**, now a lazy route: hero, key figures, Performance
  (two compact charts), research teaser, About, Latest. `DataRefreshChecklist` moved into a
  "Data status" popover.
- **Financials (`pages/tabs/FinancialsTab.tsx`):** one controls row (section links with
  scroll-spy, Annual / Quarterly / TTM, Show growth), four statement sections of four charts
  plus a table each, then Valuation. `ValuationTab.tsx` is deleted.
- **Company frame:** the header is now name, meta, Ask, Watch only. The price lives in the
  Overview hero; the pinned bar shows ticker and price whenever the page itself is not showing
  it (always on other tabs; on Overview once the hero has scrolled away; on phones only when
  pinned). A tab that shows the price registers the element via
  `useCompanyOutlet().quoteAnchor`.
- **Primitive changes:** `DataTable` (`fill`, `startAtEnd`, `label`; a table that scrolls
  becomes a labelled, focusable region; header and caption accept nodes), `Tooltip`
  (`onOpenChange`, `focusable`), `Delta` (`points` for changes in a percentage),
  `SegmentedControl` (a disabled option can carry a `hint`), `Stat` (proportional figures).
- **Earnings-day table** on Filings uses `DataTable` and `Delta`.

**Bugs found and fixed here**

- **Every date-only value rendered one day early west of UTC.** `formatDate("2026-09-30")`
  printed "Sep 29, 2026" in US time zones: filing dates, period ends, and trading days across
  the whole app. Date-only strings are now printed as written; timestamps still use the
  reader's time zone. Regression test in `format.test.ts`.
- **Two charts could never show data.** The Financials tab asked for `fcf` and `eps`; the API's
  names are `free_cash_flow` and `eps_diluted`. Free cash flow, EPS, and the header's EPS stat
  had always shown "not available" as a result.
- **"Latest filings" would have been the oldest.** The filings endpoint pages by id, not date,
  and for NVDA the first 25 are the oldest. Overview asks for 200 and sorts by filing date.
  The Filings tab still shows the first 25 in id order: fix it in Step 4.
- **Chart axis labels were clipped** ("0000000"): axes now print compact round ticks ($100B).
- **Current ratio printed as a percentage** (445%) because margins and multiples share the API
  unit "ratio". The catalogue now marks multiples (4.45×).

**Deviations from this file, and why**

- **Gridlines are solid and lines are 2 px with 4 px bar ends**, not dashed / 1.75 px / 2 px as
  written. The dataviz guidance loaded for this step treats dashed gridlines as noise that reads
  as a threshold, and these are its mark sizes. The hero's opening-price line *is* a threshold,
  so it stays dotted.
- **"Show growth" is a strip under each chart, not an overlay.** An overlay needs a second
  y-scale on the same plot, which invents a visual relationship between the two series.
- **A single series is neutral grey, not `text` at 85%.** That read as heavy white blocks on the
  dark canvas; `--chart-ink` is a mid grey with the hovered bar in full ink.
- **While scrubbing, the hero shows that day's adjusted close**, not the raw close, so the
  figure agrees with the line (raw NVDA closes before the 2024 split are ten times larger). At
  rest it shows the latest raw close, as specified. The caption says the line is adjusted.
- **Quarterly is offered but thin:** the database holds only fiscal fourth quarters, for three
  metrics. The page says so, draws only charts that have data, and TTM (no data at all) is
  disabled with an explanation.
- **Statement cells are not tab stops.** Up to 285 focusable cells per table would bury keyboard
  users. Each row's metric name is focusable and shows the lineage for the latest period; cells
  show their own on hover. Lineage tooltips mount only when first hovered.
- **Data-layer edits:** `useFilings(ticker, limit)`; `useFinancials` keeps the previous figures
  as placeholder data when only the period type changes (never across companies).
- **Period-over-period changes are computed in the browser** (`changeBetween`) from two values
  already on screen, for display. They are not stored or sent anywhere, and growth from a zero
  or negative base is not reported (DR-041).

**Backend problems found, NOT fixed (frontend-only step)**

- **The API stalls when about 16 requests overlap.** Handlers are `async def` but use blocking
  database sessions that are only returned to the pool after the response (the `get_db`
  dependency's teardown). The pool holds 15 connections (SQLAlchemy defaults; `app/db.py` sets
  none). When all are out, the next handler blocks the event loop waiting for one, so no
  teardown can run and nothing is returned until the 30-second pool timeout. Two Playwright
  workers were enough; so are three browser tabs loading at once. This is the same root cause as
  the token-refresh hang in Step 2's hand-off. The E2E suites now run with one worker to stay
  under it. It needs a backend task: run handlers in the threadpool (`def`) or release sessions
  before the response, and set pool size and timeouts deliberately.
- Still open from Step 2: the token-refresh deadlock, and `research/latest` returning 500 on the
  seed placeholder reports (the Overview research teaser therefore shows "Generate research").

**Verified in a real browser**

`e2e/tests/company.spec.ts` (committed) covers the Definition of Done mechanically. Captures in
`e2e/screenshots/{dark,light}/{1440,390}/` (23 per folder, 92 total); new or changed this step:
`company-overview`, `company-overview-scrub`, `company-overview-no-prices` (AMD),
`company-overview-bank` (JPM), `company-pinned`, `company-financials`,
`company-financials-growth`, `company-financials-table` (a lineage tooltip open),
`company-financials-no-prices`, `company-financials-bank`. Looked at: dark and light desktop
Overview (NVDA, AMD, JPM), the scrub state, Financials full page, the growth and table states,
JPM Financials in light, and phone Overview and Financials.

**Bundle (gzip), Step 2 → Step 3**

| Chunk | Step 2 | Step 3 |
|-------|--------|--------|
| entry `index` | 91.56 kB | 91.41 kB |
| CSS | 8.42 kB | 8.95 kB |
| `CompanyDashboard` | 3.24 kB | 2.60 kB |
| `OverviewTab` (now lazy) | in entry | 7.69 kB |
| `FinancialsTab` | 10.32 kB | 5.04 kB |
| shared chart system (`Stat-*`) | n/a | 13.92 kB |
| Recharts (own chunk) | 98.24 kB | 98.33 kB |

**Left for later steps**

- Research, Filings, News, and chat contents are untouched (Step 4); those sections still sit
  16 px inside their headings.
- `ComparisonBars` is not on the new chart system, and the categorical palette it uses fails
  validation in dark (noted in Step 5's file).
- Valuation shows a sentence, because the backend persists no price-based metrics.
- The research teaser's "with citations" branch is untested against real data: no valid report
  exists in this database.
- Statement tables open scrolled to the newest column; the oldest are a scroll away. A phone
  shows about three periods at a time.
- Not reviewed: Clyde and Albert live.
