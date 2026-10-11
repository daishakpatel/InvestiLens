# UI Step 1 — Design System, Theme & Primitives

**Prerequisites:** `00_README.md` in this folder read in full. `make check` green on the current
branch. Dev stack runnable (`docker compose up -d postgres redis`, backend on :8000,
`cd frontend && npm run dev`).
**Blocks:** Steps 2 to 5. Nothing else may restyle a page until this lands.
**Spec refs:** §27 frontend requirements (UI-001 to UI-007), FR-010, FR-012.

## Objective

Replace the visual foundation: tokens, typography, and the primitive components every screen is
built from. No page is redesigned here, but because pages are built on tokens and primitives, the
whole app should already look like a different product when this step is done. Dark becomes the
default theme.

## Scope

### 1. Decisions (write `docs/decisions/0028-ui-rebuild-design-system.md` first)

Record these, with the one-line reason each. They are recommendations; if you reject one, say why
in the ADR.

- **Fonts:** `@fontsource-variable/inter`, imported once in `main.tsx`. Self-hosted because the
  API sets a strict CSP and tests and dev run offline.
- **Accessible behaviour primitives:** `radix-ui` (the unified package) for Dialog, Popover,
  Tooltip, Tabs, DropdownMenu, and ToggleGroup. Focus trapping, escape handling, and aria wiring
  are where the hand-rolled versions are weakest; styling stays ours.
- **Command palette:** `cmdk` (used in Step 2). Decide here so dependencies are settled once.
- **Icons:** `lucide-react`, imported per icon. Replaces the `☀ ☾ ▲ ▼ ↗` text glyphs.
- **Charts:** stay on Recharts. Do not add a second chart library; the price hero in Step 3 is a
  Recharts area chart.
- **Not adopting:** a component kit (shadcn, MUI, Chakra) or a CSS-in-JS runtime. Tailwind v4
  tokens plus a small set of our own components is enough.

### 2. Tokens (`frontend/src/index.css`)

- Rewrite the token block from the table in `00_README.md`: dark values on `:root`, light values
  under `:where(.light)`. Flip the variant: dark is the base, `.light` is the override. Keep
  `@custom-variant dark` working (define it as "not `.light`") so existing `dark:` utilities
  don't break; there are few of them, remove any you can.
- Add the new tokens (`surface-3`, `border-strong`, `subtle`) to `@theme inline`, along with the
  type scale, radius (`--radius-control: 6px`, `--radius-surface: 10px`), and the two durations.
- Retune the six chart colours for both canvases. Keep them the Okabe-Ito hues (UI-003).
- **Verify contrast** for every text/background pair you ship in both themes and record the
  ratios in the ADR. Adjust values until `text` and `muted` pass 4.5:1 on `bg`, `surface`, and
  `surface-2`. A small script using the WCAG formula is fine; do not eyeball it.
- Set base styles: `body` 15 px Inter, `-webkit-font-smoothing: antialiased`,
  `font-feature-settings` for tabular numerals available as a `.tnum` utility, selection colour,
  thin dark scrollbars, the focus ring in `primary`.

### 3. Theme behaviour (`index.html`, `lib/theme.tsx`, `components/chrome.tsx`)

- Default is **dark for everyone**, regardless of OS preference. Light applies only when the user
  has chosen it (`localStorage["il-theme"] === "light"`). Update the pre-paint script so there is
  no flash in either case.
- `<meta name="color-scheme" content="dark light">` and a `theme-color` meta that tracks the theme.
- Theme toggle becomes an icon button with a proper label; it will move into the account menu in
  Step 2, so keep it a standalone component.

### 4. Primitives (`frontend/src/components/ui/`)

Build or rebuild these, one small file each. Variants are props, not new components. Every one
must be keyboard-operable, have a visible focus state, and look right in both themes.

- `Button` (primary, secondary, ghost, danger; sizes sm and md; loading state) and `IconButton`.
- `Input`, `Select`, `Checkbox`, `Switch`.
- `SegmentedControl` (Radix ToggleGroup): the range selector, FY/Quarterly toggles.
- `Tabs` underline style with an animated active indicator (page tabs) and a pill style (in-page).
- `Badge`: quiet by default (text plus a 6 px dot), tones as today. Used far less than now.
- `Stat`: label, value, optional delta with direction arrow and sign. Replaces `MetricTile`; keep
  its source/period/formula tooltip content.
- `Delta`: the signed, coloured, arrowed percentage, one implementation used everywhere.
- `Section`: heading row (title, optional AI mark, optional freshness, optional actions) plus
  content, **no border and no background**. This replaces `Panel` as the default container.
- `Surface`: the one bordered, raised container, for the cases that truly need separation.
- `Skeleton` (text line, block, chart, table-row shapes), `EmptyState` (icon, one sentence, one
  optional action), `ErrorState` (message plus retry).
- `Tooltip`, `Popover`, `Dialog`, `Drawer` (right-side sheet built on Dialog), `DropdownMenu`.
- `DataTable`: sticky header, right-aligned numeric columns in tabular figures, row hover,
  compact and comfortable densities, horizontal scroll with a pinned first column on mobile.
- `AiMark`: the small violet sparkle-plus-"AI" label that satisfies FR-010.

Keep `AsyncContent` (it encodes UI-002) but restyle its states with the new `Skeleton`,
`EmptyState`, and `ErrorState`.

### 5. Migrate, then delete

- Point every existing usage of `Panel`, `MetricTile`, the old `Badge`/`Tabs`/`Spinner`/tooltip to
  the new primitives with the lightest possible edit. Pages keep their current layout in this
  step; they only change skin.
- Delete the old primitives once nothing imports them.

### 6. A place to see it, and a way to capture it

- Add a dev-only route `/_ui` (not linked, excluded from production nav) that renders every
  primitive in every variant and state. This is the review surface for this step.
- Add `e2e/tests/screenshots.spec.ts` (Playwright is already scaffolded in `e2e/`): visit `/_ui`,
  `/`, `/company/NVDA`, `/compare`, `/portfolio` in dark and light at 1440 px and 390 px wide, and
  save full-page PNGs to `e2e/screenshots/<theme>/<width>/`. Add an `npm run screenshots` script.
  Git-ignore the output. Every later step uses this.
  The `e2e/` dependencies have never been installed: run `npm install && npm run install-browsers`
  there first. It needs the dev stack running with seeded data (`make seed`).

## Out of scope for this file

No layout, navigation, or information-architecture changes (Step 2). No chart redesign beyond
colours (Step 3). No new features. No backend changes.

## Definition of Done

- [x] ADR-0028 written, including the measured contrast ratios for both themes
- [x] A first-time visitor with OS light mode gets the dark theme with no flash; choosing light
      persists across reloads with no flash
- [x] All tokens from `00_README.md` exist in `index.css`; no hard-coded hex colours remain in
      `frontend/src` outside `index.css` (grep proves it)
- [x] Every primitive listed above exists under `components/ui/`, is shown on `/_ui` in all
      variants, and is operable by keyboard alone
- [x] No file imports the old `Panel`, `MetricTile`, or old primitives; they are deleted
- [x] `npm run screenshots` produces dark and light captures; they are listed in the hand-off
- [x] `make check` green and `npm run build` succeeds; no route chunk grew by more than 40 kB gzip
      (report before and after sizes)
- [x] `## Hand-off` section appended to this file

## Hand-off

Done 2026-10-10. `make check` green (450 backend, 19 frontend tests); `npm run build` succeeds.

**What shipped**

- **Tokens and theme** (`frontend/src/index.css`, `index.html`, `lib/theme.tsx`): dark on `:root`,
  light on `:root.light` (not `:where(.light)`: that lost to `:root` on specificity and produced a
  half-light page). Dark is the default regardless of OS setting; light persists via
  `localStorage["il-theme"]`. Four light values were darkened after measuring; ratios in ADR-0028,
  and the table in `00_README.md` now matches what shipped.
- **Utilities you can use:** colours `bg-surface-3`, `border-border-strong`, `text-subtle`; type
  `text-caption | label | body | title | heading | display-s | display-l`; `rounded-control`,
  `rounded-surface`; `shadow-float` (nothing in dark, soft in light); `tnum` for tabular figures;
  `duration-(--duration-slow)` for 200 ms; `animate-shimmer`; variants `light:` and `dark:`.
- **Primitives** in `frontend/src/components/ui/` (import each file directly, there is no barrel):
  `Button`/`IconButton`, `Input` (exports the shared `FIELD` class), `Select`, `Checkbox`,
  `Switch`, `SegmentedControl`, `Tabs` (`RouteTabs`, `PillTabs`, `PillTabPanel`), `Badge`
  (`Badge`, `EvidenceBadge`, `FreshnessBadge`), `Stat`, `Delta`, `Section` (`Section`, `Surface`),
  `Skeleton` (`Skeleton`, `Spinner`), `States` (`LoadingState`, `EmptyState`, `ErrorState`,
  `AsyncContent`), `Tooltip`, `Popover`, `Dialog` (`Dialog`, `Drawer`), `DropdownMenu`
  (`DropdownMenu`, `MenuItem`, `MenuLabel`, `MenuSeparator`), `DataTable`, `AiMark`, `cn`.
- **API notes:** `Section` takes the old `Panel` props (`title`, `kind`, `freshness`, `actions`);
  `kind="ai"` renders the `AiMark`, data sections carry no label. `Delta` takes a ratio and
  renders sign, arrow, and colour. `Dialog`/`Drawer` are controlled (`open`, `onOpenChange`) and
  return focus to whatever opened them. `Tooltip` wraps non-interactive children in a focusable
  span; pass `asChild` for buttons and `plain` to drop the dotted underline.
- **Migration:** `Panel`, `MetricTile`, `components/Tabs.tsx`, and `components/primitives.tsx` are
  deleted; all 35 panels are `Section`s. Text glyphs are lucide icons. The company header and tab
  area are no longer boxed.
- **Review tooling:** `/_ui` (dev server only; confirmed absent from the production bundle) and
  `cd e2e && npm run screenshots`, which writes `e2e/screenshots/{dark,light}/{1440,390}/` for
  `ui`, `home`, `company-overview`, `company-financials`, `company-filings`,
  `company-management`, `company-research`, `compare`, `portfolio` (36 PNGs, git-ignored). The
  spec sets the OS colour scheme opposite to the theme under test, so the dark captures also prove
  the OS preference is ignored. Add routes to `ROUTES` in `e2e/tests/screenshots.spec.ts` as
  screens change.
- **Verified in a real browser:** all 36 captures were produced and a sample of dark and light,
  desktop and phone, was looked at. A throwaway Playwright run (not committed) confirmed keyboard
  operation of dialog, drawer, menu, popover, segmented control, pill tabs, checkbox, switch, and
  tooltip, focus return on close, dark with OS-light, and light persisting across a reload.

**Bundle (gzip), before → after**

| Chunk | Before | After |
|-------|--------|-------|
| entry `index` | 89.46 kB | 89.83 kB |
| CSS | 5.36 kB | 7.44 kB |
| `CompanyDashboard` | 1.82 kB | 4.90 kB |
| shared Radix chunk (`Tooltip-*`) | n/a | 18.19 kB (new) |
| `FinancialsTab` | 10.04 kB | 10.06 kB |
| Recharts chunk | 98.24 kB | 98.24 kB |

Inter adds seven woff2 subset files; browsers fetch only Latin (48 kB) for our content.

**Deliberately left for later steps**

- Pages kept their layout. Section content still carries its old `px-4`/`p-4`, so it sits 16 px
  inside its heading. Steps 2 to 4 rebuild those pages; remove the inner padding as you go.
- Page-level buttons, inputs, and tables are still hand-written class strings. They pick up the
  new tokens but are not yet `Button`/`Input`/`DataTable`. Convert them when you touch a page
  (`grep -rn 'bg-primary' src/pages` finds the primary buttons).
- `CitationModal` is still the hand-rolled modal (Step 4 replaces it with `Drawer`).
- `SearchBox` and `DisambiguationPicker` are untouched apart from tokens (Step 2 replaces them).
- Charts only changed colour. Y-axis tick labels on the Financials bar charts are clipped
  ("0000000"); that predates this step and belongs to Step 3's chart system.
- Stats with no data still render "—" (Market Cap, EPS, P/E on NVDA). Step 3 omits them.
- `cmdk` is installed but unused until Step 2.
- The content column is still `max-w-6xl`; Step 2 moves it to 1240 px.
- Not done: reviewing Clyde and Albert live (no general browser here, only the local Playwright
  run), and an axe pass (Step 5).
