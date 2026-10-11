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

- [ ] `⌘K`, `Ctrl+K`, and `/` open the palette from every page; a company can be reached from a
      cold load using only the keyboard
- [ ] An ambiguous query never auto-navigates without the user choosing a row (§9.2)
- [ ] Company page shows five tabs; all five old URLs redirect to their new home; no route 404s
      that previously worked
- [ ] The sticky sub-header appears on scroll with price and tabs, with no layout shift
- [ ] Disclaimer present on every page (FR-012); theme switch works from the account menu
- [ ] Usable at 360 px wide: no horizontal page scroll on Home, Auth, or any company tab
- [ ] `e2e/tests/happy-path.spec.ts` selectors updated for the new shell (do not delete the test)
- [ ] `npm run screenshots` captures for Home, Auth, and Company in both themes and both widths
      are listed in the hand-off
- [ ] `make check` green and `npm run build` succeeds
- [ ] `## Hand-off` section appended to this file
