# UI Step 5 — Compare, Portfolio, Watchlist, Light Theme & Polish

**Prerequisites:** Steps 1 to 4 done (read every `## Hand-off`).
**Blocks:** nothing. This is the last step of the rebuild.
**Spec refs:** §37.1, §37.2 (comparison, portfolio), §26.2 (watchlist, alerts), FR-007, FR-012,
UI-003, UI-004, UI-006, UI-007, LGL-006.

## Objective

Bring the remaining tools up to the new standard, finally give the watchlist and alerts a UI,
then do the pass that separates "restyled" from "finished": a light theme that is designed rather
than inverted, consistent motion, accessibility, performance, and a visual regression net so the
quality holds.

## Scope

### 1. Compare (`pages/ComparePage.tsx`, `charts/ComparisonBars.tsx`)

- **Picker:** selected companies as removable chips with an "Add company" control that opens the
  command palette in pick mode (2 to 6 companies). Peer suggestions appear as one-tap chips under
  it. The selection lives in the URL so a comparison can be shared.
- **Main view:** one `DataTable`, metrics as rows and companies as columns, best value per row in
  `text` weight 600 and the rest in `muted` (no green/red: "best" is not a gain). The percentile
  appears as a thin inline bar inside the cell.
- Selecting a metric row shows its bar chart beneath the table, on the Step 3 chart system.
- The calendar-year alignment note and any N/A reasons are one `subtle` line under the table.
- **AI commentary** is an explicit action ("Explain the differences") with the `AiMark`, cited
  through the citation drawer, sign-in gated. Its insufficient-evidence result is a plain note.

### 2. Portfolio (`pages/PortfolioPage.tsx`)

- **Left column:** the holdings editor as a compact table (ticker, weight input, remove), with a
  running total that turns `warning` when weights do not sum to 100% and a "Normalize" action.
- **Right column:** results that update instantly from `lib/portfolioRecompute.ts` as weights
  change: headline `Stat`s (weighted revenue growth, margin, concentration), sector exposure as a
  single stacked horizontal bar with a legend, a correlation heat table, and risk themes as a
  cited list.
- Missing-data cases (no price history, no report for a holding) each get one sentence saying
  what is missing for which ticker.
- "Hypothetical portfolio. Not investment advice." is stated under the title (LGL-006, FR-012).

### 3. Watchlist, alerts & notifications (new; the API already exists)

Add the hooks this needs to `lib/queries.ts` and Zod schemas to `lib/schemas.ts`, following the
existing patterns, for: `GET/POST /watchlists`, `DELETE /watchlists/{id}`, `GET/POST /alerts`,
`DELETE /alerts/{id}`, `GET /notifications`, `POST /notifications/{id}/read`. Check
`docs/api.md` and `services/api.d.ts` for exact shapes; if an operation the UI needs is missing
(for example adding an item to an existing watchlist), design around it and list it in the
hand-off. Do not change the backend.

- **Watch button** on the company header: toggles the company in the user's default watchlist.
  Signed out, it opens the sign-in prompt.
- **Home, signed in:** the Watchlist section becomes rows of ticker, name, last close, day
  `Delta`, and a 30-day sparkline, each linking to the company. Empty state invites the first add.
- **Alerts:** a bell `IconButton` on the company header opens a `Popover` listing the alert types
  as switches: New 10-K, New 10-Q, New 8-K, Price move (with a threshold input), News, and New
  risk factor. Each switch creates or deletes the alert.
- **Notifications:** a bell in the top bar with an unread dot; a `Popover` lists recent
  notifications, newest first, marking them read when opened. Poll on a slow interval (60 s) and
  on window focus.

### 4. Light theme pass

Dark was designed first; light must not be an afterthought.

- Walk every screen in light using the screenshot set. Fix, at token level where possible:
  borders that vanish on white, tints that are too heavy, charts whose lines are too faint, the
  diff's insert/delete tints, the heat-table scale, focus rings on accent backgrounds.
- Light uses the one soft shadow for floating layers (menus, drawer, palette); dark uses none.
- Re-verify contrast for anything adjusted and update the numbers in ADR-0028.

### 5. Motion and micro-interactions

- One shared set of transitions: hover and press 120 ms; drawer, palette, and tab indicator
  200 ms ease-out; skeleton shimmer 1.2 s. Remove any one-off durations.
- Price and stat values cross-fade when they change (range switch, scrub). Rows and chips fade in
  on mount; nothing slides more than 8 px.
- Buttons have a pressed state; toggles confirm with state, not with a toast. Toasts are reserved
  for results the user cannot otherwise see (export finished, alert saved, copy succeeded).
- Confirm everything is suppressed under `prefers-reduced-motion`.

### 6. Accessibility audit

- Run `@axe-core/playwright` (already scaffolded in `e2e/`) on Home, each company tab, the
  assistant open, the citation drawer open, Compare, and Portfolio, in both themes. Zero serious
  or critical violations.
- Keyboard walk-through of the full happy path with no mouse. Logical focus order, no traps,
  visible focus everywhere, Escape closes the topmost layer only.
- Every chart has an accessible name and a table alternative; every icon-only button has a label;
  live regions announce streaming answers and async results once, not per token.
- Touch targets at least 40 px on mobile.

### 7. Performance

- Run Lighthouse on the built app (`npm run build && npm run preview`) for Home and
  `/company/NVDA`. Target 90 or above for Performance and Accessibility (UI-004). Record the
  scores in `docs/testing.md`; if a target is missed, record the real number and the cause.
- Confirm route-level splitting still holds: Recharts, the assistant, and the command palette
  each load on demand. Report gzip sizes before the rebuild (from git history) and after.
- Inter is preloaded with `font-display: swap` and subset to Latin. No layout shift on first
  paint of the hero (reserve the chart height).

### 8. Visual regression and clean-up

- Promote the screenshot script into a real check: `e2e/tests/visual.spec.ts` using Playwright's
  `toHaveScreenshot` for the key screens in both themes at 1440 px and 390 px, against mock-mode
  data so runs are deterministic. Commit the baselines. Wire it into the on-demand E2E workflow
  (`.github/workflows/e2e.yml`), not the per-PR gate, consistent with ADR-0019.
- Update `e2e/tests/happy-path.spec.ts` for the final UI.
- Remove the `/_ui` route from the production bundle (dev-only import), any unused component,
  token, or dependency, and every leftover from the old UI. `npm ls` and a dead-export check
  should come back clean.
- Write `docs/ui.md`: the design principles, the token table, the primitive list with one-line
  usage notes, and the rules for adding a new screen. Keep it to what a new contributor needs.
- Update the frontend sections of `README.md` (screenshots of the new Home and Company page in
  dark).

## Out of scope for this file

New product features beyond the watchlist/alerts UI named above. Backend changes. A mobile app.
Onboarding tours, marketing pages, analytics events (UI-008 stays optional).

## Definition of Done

- [ ] Compare and Portfolio use the new primitives and chart system; a comparison is shareable by
      URL; weight changes update portfolio results with no network request
- [ ] A signed-in user can watch a company, see it on Home with price and sparkline, turn on a
      "New risk factor" alert, and see a notification arrive in the top-bar bell (simulate one
      via the existing alert-dispatch test path or a seeded notification)
- [ ] Every screen has been reviewed in light and dark at 1440 px and 390 px; captures listed
- [ ] axe reports zero serious or critical violations on all listed screens in both themes
- [ ] The full happy path is completable by keyboard alone
- [ ] Lighthouse scores for Home and `/company/NVDA` recorded in `docs/testing.md` (target 90+)
- [ ] Visual regression baselines committed and the spec passes twice in a row locally
- [ ] No old-UI component, unused dependency, or hard-coded colour remains
- [ ] `docs/ui.md` written; ADR-0028 updated with final contrast numbers
- [ ] `make check` green and `npm run build` succeeds
- [ ] `## Hand-off` section appended to this file, including an honest list of anything that
      still falls short of the references and why
