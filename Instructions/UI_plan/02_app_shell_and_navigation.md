# UI Step 2 — App Shell, Search, Home & Company Frame

**Prerequisites:** Step 1 done (read its `## Hand-off`). Primitives under `components/ui/` exist.
**Blocks:** Steps 3 and 4 (they fill the frame built here).
**Spec refs:** §9.1 to §9.4 (search, disambiguation, dashboard header), FR-001, FR-012, UI-006.

## Objective

Rebuild how a user moves through the product: the global shell, a keyboard-first search, a home
page worth landing on, and the company page frame with five tabs instead of ten. After this step
the navigation and skeleton of every screen are final; Steps 3 and 4 only fill in content.

## Scope

### 1. Global shell (`components/AppShell.tsx`)

- **Top bar**, 56 px, sticky, `bg` at 80% opacity with backdrop blur and a bottom hairline:
  wordmark on the left; a search trigger in the centre that looks like an input and shows the
  `⌘K` hint; Compare and Portfolio links; an account menu on the right.
- **Account menu** (DropdownMenu): signed out shows a single "Sign in" button. Signed in shows an
  avatar initial that opens email, theme switch (Dark / Light), and Sign out. The theme toggle
  lives here now, not in the bar.
- **Content width** 1240 px, centred, 24 px gutters. Drop the outer `max-w-6xl` box feeling: the
  bar spans the full viewport, content is centred beneath it.
- **Footer:** one quiet line carrying the disclaimer (FR-012) on every page. Keep the text from
  `lib/config.ts`.
- **Mobile (below 768 px):** the bar keeps wordmark, a search icon, and the account menu. Compare
  and Portfolio move into the account menu. No hamburger drawer.
- Route transitions: keep `Suspense`, but the fallback is a page-shaped skeleton, not a spinner.

### 2. Command palette search (`components/CommandPalette.tsx`, replaces inline `SearchBox` use)

- Opens with `⌘K` / `Ctrl+K`, with `/`, or by clicking the trigger. Built on `cmdk` inside a
  Radix Dialog.
- Empty state lists Recent (from `lib/recentSearches.ts`) and Popular tickers.
- Typing queries `useCompanySearch` (already debounced by React Query keying; add a 150 ms input
  debounce). Each result row: ticker in medium weight, company name, exchange in `subtle`.
- Arrow keys move, Enter opens the company, Escape closes. Loading shows three skeleton rows; no
  results shows one sentence, never a blank list.
- **Disambiguation (§9.2) is preserved:** the palette always shows the list and the user picks; a
  bare Enter on an ambiguous query selects the highlighted row, it never silently best-guesses.
  `DisambiguationPicker` becomes unnecessary; delete it if nothing else uses it.
- Secondary actions at the bottom of the list: "Compare companies", "Analyze a portfolio".

### 3. Home (`pages/HomePage.tsx`)

The current page is a search box and four chips. Replace it with a landing that sells the product
in one screen and gets a returning user to a company in one click.

- **Hero:** one line of 48 px type stating the promise (evidence-grounded research on US public
  companies), one line of `muted` supporting text, and the large search trigger. Nothing else
  above the fold on a laptop.
- **Tickers row:** Popular (and Recent when present) as rows, each with ticker, name, last close,
  and day change using `Delta`. Use `usePrices` per ticker; if prices are missing show the row
  without the price cells rather than dashes.
- **What you get:** three short, plain blocks (Financials with lineage, AI research with
  citations, Filing change detection), each linking into NVDA as a live example. Text only, no
  illustrations, no marketing gradients.
- **Signed-in:** a "Watchlist" section placeholder with an honest empty state. The watchlist UI
  itself is built in Step 5; leave a single clearly named slot component for it.

### 4. Auth (`pages/AuthPage.tsx`)

- Centred 400 px form on the bare canvas, wordmark above, no card border. Sign in and Create
  account as two states of one form with a text switch beneath.
- Inline field errors, the password-length rule shown up front, a loading state on the button,
  and the API's problem message surfaced verbatim on failure.

### 5. Company page frame (`pages/CompanyDashboard.tsx`, `App.tsx`)

- **Header (not a boxed card):** company name at 24 px with ticker, exchange, and sector in
  `muted` on one line. On the right, an "Ask" button (opens the assistant panel, wired in Step 4;
  for now it navigates to the existing chat route) and a Watch button (disabled with a tooltip
  until Step 5).
- **Sticky sub-header:** when the header scrolls away, a 48 px bar pins under the top bar with
  ticker, last price, day `Delta`, and the tab list. This is the Robinhood/TradingView behaviour
  that keeps context while reading long pages.
- **Tabs:** Overview, Financials, Research, Filings, News, using the underline `Tabs` primitive.
  The tab strip scrolls horizontally on mobile with no visible scrollbar.
- **Routes:** implement the mapping in `00_README.md`. For this step the merged tabs may simply
  stack the existing tab components (Financials renders Financials then Valuation; Research
  renders Research, Risks, Management) so nothing is lost. Add redirects for `/valuation`,
  `/risks`, `/management`, `/ownership`, `/chat`. Remove the Ownership tab and `PlaceholderTab`.
- The price and the key stats stay where they are for now; Step 3 replaces them with the hero.
- Company not found: a full-page `EmptyState` with the search trigger, not a red box.

### 6. Global states

- A top-of-page 2 px progress line while any route-level query is pending for more than 300 ms.
- An offline / API-unreachable banner that appears once, not one error box per panel.
- A real 404 page with the search trigger.

## Out of scope for this file

Redesigning tab contents (Steps 3 and 4). The assistant panel and citation drawer (Step 4).
Watchlist, Compare, Portfolio internals (Step 5). No backend changes.

## Definition of Done

- [x] `⌘K`, `Ctrl+K`, and `/` open the palette from every page; a company can be reached from a
      cold load using only the keyboard
- [x] An ambiguous query never auto-navigates without the user choosing a row (§9.2)
- [x] Company page shows five tabs; all five old URLs redirect to their new home; no route 404s
      that previously worked
- [x] The sticky sub-header appears on scroll with price and tabs, with no layout shift
- [x] Disclaimer present on every page (FR-012); theme switch works from the account menu
- [x] Usable at 360 px wide: no horizontal page scroll on Home, Auth, or any company tab
- [x] `e2e/tests/happy-path.spec.ts` selectors updated for the new shell (do not delete the test)
- [x] `npm run screenshots` captures for Home, Auth, and Company in both themes and both widths
      are listed in the hand-off
- [x] `make check` green and `npm run build` succeeds
- [x] `## Hand-off` section appended to this file

## Hand-off

Done 2026-10-10. `make check` green (450 backend, 29 frontend tests); `npm run build` succeeds;
`e2e/tests/shell.spec.ts` 19/19; axe reports no serious or critical violations on 11 routes plus
the open palette and menu, in both themes.

**What shipped**

- **Routing (`App.tsx`):** a `RootLayout` wraps every route with the command palette, the
  loading line, the outage banner, and scroll reset. `/login` sits outside `AppShell` on the bare
  canvas. Company routes: index is Overview (`/company/:ticker`), plus `financials`, `research`,
  `filings`, `news`, and `chat`. Redirects: `overview` and `ownership` to the index, `valuation`
  to `financials#valuation`, `risks` to `research#risks`, `management` to `research#management`,
  anything else under a company to its index.
- **Shell (`components/AppShell.tsx`):** full-width sticky bar (56 px) with a three-column grid so
  the search field is centred on the page; `AccountMenu` (lazy chunk); `Footer` with the
  disclaimer. **Pages now own their width**: wrap page content in `components/ui/Container`
  (1240 px, 24/16 px gutters). `<main>` is full width, so a page can run something edge to edge
  (the company sub-header does; Step 4's docked assistant can).
- **Command palette:** `components/CommandPaletteContext.tsx` (provider, `useCommandPalette().open()`,
  the ⌘K / Ctrl+K / "/" listener) and `components/CommandPalette.tsx` (cmdk in a Radix Dialog,
  lazy, preloaded when idle). `components/SearchTrigger.tsx` has four variants: `bar`, `hero`,
  `icon`, `button`. §9.2 holds by construction: results are selectable only once the debounce has
  settled *and* the response for exactly the typed text has arrived, so Enter can never open a
  row the user did not see highlighted. Tools ("Compare companies", "Analyze a portfolio") show
  when idle or when the text names them, never as a fallback for a search with no matches.
- **Company frame (`pages/CompanyDashboard.tsx`):** header (name, meta, Ask, Watch, price, stats),
  then one sticky 48 px bar holding `RouteTabs` and, once the header has scrolled away, the
  ticker and price (`data-testid="pinned-quote"`). The bar is always the same element at the
  same height, so pinning shifts nothing. Changing tab while pinned scrolls the new tab to its
  top. Unknown ticker (API 404) renders `NotFound` with the search button, no tabs.
- **Home, Auth, 404:** rebuilt as specified. `components/home/WatchlistSlot.tsx` is the single
  slot Step 5 fills. `pages/NotFoundPage.tsx` exports `NotFound({ title, message })`.
- **Global states:** `components/RouteProgress.tsx` (2 px line, first loads only, after 300 ms);
  `lib/apiStatus.tsx` + `components/ApiStatusBanner.tsx` (one banner; `AsyncContent` shows a
  quiet "waiting" skeleton instead of an error while the API is unreachable, and failed queries
  reload on recovery). `useApiStatus()` gives `{ online, reachable, retry }` to anything that
  renders its own error state.
- **New helpers:** `lib/quote.ts` (`latestQuote`), `lib/shortcuts.ts`, `lib/useMediaQuery.ts`,
  `lib/useDocumentTitle.ts`, `lib/useScrollToHash.ts`, `POPULAR_COMPANIES` and
  `PASSWORD_MIN_LENGTH` in `lib/config.ts`.
- **Primitive changes:** `RouteTabs` no longer draws its own border, is 48 px tall, supports an
  index tab (`to: ""`), keeps the active tab in view and fades the edge that hides more tabs;
  `Section` takes an `id`; `DropdownMenu` is non-modal and has `MenuRadioGroup`; `Input` accepts
  a `ref`; `Skeleton` lets a caller's width/height replace the shape default; `useTheme()` now
  returns `setTheme` (no `toggle`); `Dialog.tsx` exports `useReturnFocus`.
- **Deleted:** `SearchBox`, `DisambiguationPicker`, `ThemeToggle`, `RisksTab`, `ManagementTab`,
  `PlaceholderTab`. (Step 4's list of files to delete is shorter as a result.)

**Deviations from this file, and why**

- **The account menu exists for signed-out visitors too** (an icon button beside "Sign in").
  The plan put the theme switch and the mobile Compare/Portfolio links in the account menu and
  gave signed-out users no menu, which would have left them without either.
- **`/company/:ticker/chat` is a real route, not a redirect.** The plan asked both for a redirect
  and for "Ask" to open the existing chat; chat has to live somewhere until Step 4 builds the
  panel. It is not a tab: the header's "Ask" link leads to it.
- **Research is the report plus the language tracker, not three stacked tabs.** `ReportView`
  already renders the Risks and Management sections, so stacking `RisksTab` and `ManagementTab`
  under it would have shown them twice.
- **Home rows use a new `useRecentPrices` hook** (last 45 days) instead of `usePrices`: the full
  series is 179 kB per ticker, too much for a list row. If a company's latest bar is older than
  45 days the row shows no quote.
- **Popular is NVDA, AAPL, JPM** (the seed set). The old list included MSFT, which no
  environment has, so it was a dead link.
- **Home's hero lets the next heading show at the fold** as a cue to scroll, rather than filling
  the screen exactly.
- **Data-layer edits outside the plan's allowance:** `lib/queries.ts` gained `useRecentPrices`;
  `lib/auth.tsx` now restores the session once per page load (see the first bug below);
  `main.tsx` no longer retries 4xx responses (a 404 used to cost a second request and a second
  of skeleton before "not found" appeared).
- **Token change:** `subtle` (both themes) and light `muted` were strengthened after the first
  axe run flagged them. `00_README.md` and ADR-0028 carry the new values and ratios.

**Bugs found and fixed here**

- **Session lost on every reload in development.** React StrictMode ran the session-restore
  effect twice, sending two refreshes with the same cookie; the second was rejected as token
  reuse and its "signed out" result won. Restore is now single-flight (`lib/auth.tsx`).
- **Outage detector could loop forever** (my bug, caught before hand-off): it refetched failed
  queries after every successful health probe, so one endpoint that always returns 500 produced
  about 24,000 requests in a few minutes. It now refetches only on recovery from an actual
  outage (`afterProbe`, unit-tested, plus an E2E check).
- **Light and dark `subtle` text failed AA contrast** (see token change above).
- **Home overflowed horizontally on phones** when a company name was long (an `auto` grid track
  sized to the untruncated name).

**Backend problems found, NOT fixed (this step is frontend-only)**

- **Concurrent token refreshes can hang the whole API.** In `app/auth/service.py::refresh`, the
  reuse-detection path runs `revoke_family` (an UPDATE) and then raises, so the endpoint never
  commits: the revocation is rolled back (AUTH-002 is therefore not actually enforced) and the
  row locks stay held until the request's session is torn down. A second concurrent refresh for
  the same family blocks on that lock inside an `async def` handler, which blocks the event
  loop, which stops the first request's teardown from ever running. The API then answers
  nothing, including `/health`, until restarted. It happened during this step (the owner's
  signed-in tab was being hot-reloaded). The single-flight fix above removes the easy trigger
  from one tab; several tabs reloading at once can still cause it. Needs its own task: commit
  the revocation before raising, decide on a grace window for near-simultaneous refreshes, add
  a `lock_timeout`, and test it.
- **`GET /companies/{ticker}/research/latest` returns 500 in the dev database.** The stored
  "complete" reports are Phase 0b seed placeholders (`{"summary": "placeholder"}`) that fail
  `ResearchReport` validation. The UI treats any error there as "no report yet". Run `make seed`
  for real reports before Step 4, or the Research tab has nothing to design against.

**Verified in a real browser**

`e2e/tests/shell.spec.ts` (committed) covers every Definition of Done item that can be checked
mechanically. `e2e/tests/happy-path.spec.ts` has the new selectors; its accessibility test
passes, and its main test passes through sign-up, palette search, and the company page, then
stops at "executive summary" because this database has no valid report and no worker (see
above). Its chat and citation steps are therefore unverified against the new shell.

Captures, `e2e/screenshots/{dark,light}/{1440,390}/` (16 per folder, 64 total): `ui`, `home`,
`palette`, `palette-results`, `auth`, `company-overview`, `company-pinned`, `company-financials`,
`company-research`, `company-filings`, `company-news`, `company-chat`, `company-not-found`,
`not-found`, `compare`, `portfolio`. All were produced; dark and light, desktop and phone samples
of home, palette, auth, company (top and pinned), research, and not-found were looked at, as
were one-off captures of the signed-in home page and the open account menu.

**Bundle (gzip), Step 1 → Step 2**

| Chunk | Step 1 | Step 2 |
|-------|--------|--------|
| entry `index` | 89.83 kB | 91.56 kB |
| CSS | 7.44 kB | 8.42 kB |
| `CompanyDashboard` | 4.90 kB | 3.24 kB |
| `HomePage` | 2.17 kB | 1.77 kB |
| `AuthPage` | 0.87 kB | 1.70 kB |
| `CommandPalette` (lazy, new) | n/a | 7.76 kB |
| `AccountMenu` (lazy, new) | n/a | 5.57 kB |

**Left for later steps**

- Tab *contents* are untouched: sections still sit 16 px inside their headings, page-level
  buttons and tables are still hand-written, stats with no data still show "—", chart axis
  labels are still clipped (Steps 3 and 4).
- Compare and Portfolio only moved onto `Container`; their internals are Step 5.
- The Watch button is a disabled placeholder with a tooltip (Step 5). "Ask" navigates to the
  chat page (Step 4 makes it a panel; keep `/chat` as its deep link).
- The screenshot spec captures signed-out states only. Steps that add signed-in screens should
  add a signed-in pass using `signUp` from `e2e/tests/helpers.ts`.
- Each `shell.spec.ts` run leaves a few `e2e-…@example.com` users in the dev database, and one
  happy-path run left a queued research job for NVDA.
- Not reviewed: Clyde and Albert live (still no general browser).
