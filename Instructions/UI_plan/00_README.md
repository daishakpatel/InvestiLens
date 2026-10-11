# InvestiLens UI Rebuild — Plan Index & Design Direction

The current UI works but reads as a generic admin dashboard: navy-slate dark theme, boxed panels
inside boxed panels, ten equal-weight tabs, small type, no hero, no motion. This folder is a
five-step rebuild of the whole frontend experience. Give an agent **one step file per session, in
order**, exactly like the files in `Instructions/`.

| Step | File | Outcome |
|------|------|---------|
| 1 | `01_design_system_and_theme.md` | New tokens, type, primitives; dark by default. Every page already looks different. |
| 2 | `02_app_shell_and_navigation.md` | New shell, ⌘K search, home page, company page frame, 10 tabs → 5. |
| 3 | `03_company_overview_and_data.md` | Price-chart hero, Overview, Financials (incl. valuation), chart system. |
| 4 | `04_research_and_reading.md` | AI research, filings + diff, news, citation drawer, docked chat. |
| 5 | `05_tools_light_theme_and_polish.md` | Compare, Portfolio, Watchlist, light-theme pass, motion, a11y, visual tests. |

This file is the shared contract for all five. Read it at the start of every step.

## Who this is for

One person researching a US public company: they arrive with a ticker, want the price and the
shape of the business in five seconds, then go deep into filings and AI research with the evidence
one click away. The product's edge is **trust**: every AI claim is cited, every number has lineage.
The redesign must make that feel premium, not bury it in badges.

## Design direction: "quiet terminal"

Reference products the owner likes: Robinhood, TradingView, Clyde (joinclyde.com), Albert
(albert.com), all in dark mode. What to take from them:

- **Robinhood:** one enormous number, one chart, almost no chrome. Colour only means gain or loss.
  Generous vertical rhythm. Range selector as plain text buttons.
- **TradingView:** near-black neutral canvas, hairline borders instead of shadows, dense but calm
  data tables, tabular numerals everywhere, a fast keyboard-first symbol search.
- **Clyde / Albert:** confident large type, soft rounded surfaces, friendly empty states, restraint
  with accent colour. (These two were not reviewed live when this plan was written. If you have a
  browser, look at them before Step 1 and note anything that should change the tokens below.)

Principles, in priority order:

1. **Content is the interface.** Remove a container before adding one. No card inside a card. A
   section is a heading plus content separated by space or a hairline, not a bordered box.
2. **One hero per screen.** Each screen has a single dominant element (the price, the report
   summary, the diff). Everything else is visibly secondary.
3. **Colour is information.** Green and red mean up and down, nothing else. The accent marks the
   one primary action or the active state. AI-generated content has its own quiet violet mark.
   Everything else is grey.
4. **Numbers are typeset.** Tabular numerals, right-aligned in tables, units de-emphasised, the
   same formatter everywhere (`lib/format.ts`).
5. **Evidence one click away, never in the way.** Citations stay, but as small superscripts that
   open a side drawer, so the reader keeps their place.
6. **Fast and calm.** Skeletons shaped like the content, 120 to 200 ms transitions, no spinners
   for anything under a second, no layout shift.

## Tokens (source of truth: `frontend/src/index.css`)

Keep the existing token **names** (`bg`, `surface`, `surface-2`, `border`, `text`, `muted`,
`primary`, `positive`, `negative`, `warning`, `ai`) so existing utility classes keep compiling,
change their **values**, and add the new ones marked ★. Dark is the base; light overrides it.

| Token | Dark (default) | Light | Use |
|-------|----------------|-------|-----|
| `bg` | `#0a0b0d` | `#ffffff` | Page canvas |
| `surface` | `#111316` | `#f7f8f9` | Raised areas: drawer, menus, table header |
| `surface-2` | `#181b20` | `#eff1f3` | Hover, inputs, chips |
| `surface-3` ★ | `#20242a` | `#e6e9ec` | Pressed, selected row |
| `border` | `#22262d` | `#e4e7eb` | Hairlines |
| `border-strong` ★ | `#2f343c` | `#cfd4da` | Inputs, focused containers |
| `text` | `#f3f5f7` | `#0b0d10` | Primary text, numbers |
| `muted` | `#a1a7b0` | `#4d545e` | Secondary text, labels |
| `subtle` ★ | `#848c97` | `#656c77` | Tertiary: units, timestamps, axis ticks |
| `primary` | `#5b8cff` | `#2456e6` | The accent: primary action, active nav, focus ring |
| `primary-contrast` | `#0a0b0d` | `#ffffff` | Text on accent |
| `positive` | `#2fd27a` | `#067a3c` | Gains only |
| `negative` | `#ff5c5c` | `#c8261a` | Losses, destructive |
| `warning` | `#f5b84a` | `#9a5106` | Stale data, caveats |
| `ai` | `#a78bfa` | `#6d3fe0` | AI-generated content marker |

Steps 1 and 2 measured contrast and adjusted values (Step 2 raised `subtle` and light `muted`
after the first axe run); the table above is what shipped, and the ratios are in ADR-0028. If you change a value, re-measure it; change values, not roles. The accent is deliberately not green: green is reserved for gains.

Chart series colours stay the colourblind-safe Okabe-Ito set (UI-003), retuned for the new canvas.
A single-series price or metric line uses `text` (neutral) or `positive`/`negative` by direction,
never a categorical colour.

**Type.** Inter Variable, self-hosted (the API's CSP and offline dev rule out a font CDN).
`font-feature-settings: "tnum", "cv11", "ss01"` on numeric contexts. Scale in px:
12 caption, 13 label, 14 body-small, 15 body, 18 title, 24 heading, 32 display-s, 48 display-l
(the price). Weights 400, 500, 600 only. Tighten tracking on 24 px and above (-0.01 to -0.02em).
Labels are sentence case, never ALL-CAPS-with-tracking.

**Space and shape.** 4 px grid. Page max width 1240 px, 24 px gutters (16 px on mobile).
Section gap 48 px, block gap 24 px. Radius: 6 px controls, 10 px surfaces, full for pills.
No box shadows in dark; one soft shadow for floating layers (menus, drawer) in light.

**Motion.** 120 ms for hover and press, 200 ms ease-out for drawers and tab indicators.
Numbers that update may cross-fade; nothing bounces. All of it off under
`prefers-reduced-motion` (the rule already exists in `index.css`).

## Information architecture

Company page: ten tabs become five, plus an always-available assistant.

| New tab | Absorbs | Route |
|---------|---------|-------|
| Overview | Overview | `/company/:ticker` |
| Financials | Financials, Valuation | `/company/:ticker/financials` |
| Research | AI Research, Risks, Management | `/company/:ticker/research` |
| Filings | SEC Filings (outline, diff, earnings reaction) | `/company/:ticker/filings` |
| News | News | `/company/:ticker/news` |
| "Ask" (docked panel, not a tab) | Chat | opens over any tab; `/company/:ticker/chat` deep-links to it |

"Insiders & Ownership" has no data behind it (Form 4 / 13F are not ingested) and is removed from
navigation until it does. Old tab URLs (`/valuation`, `/risks`, `/management`, `/ownership`,
`/chat`) must redirect, not 404.

Top level: Home (search + watchlist), Compare, Portfolio, account menu.

## Non-negotiables carried over from the spec

The rebuild changes presentation, never these behaviours. Each already has code; keep it working.

- **FR-010** AI-generated content is visibly distinguished from data. (New form: a small violet
  "AI" mark on the section heading, not a badge on every panel. Plain data needs no label.)
- **FR-011** Data freshness is shown; **FR-012** the not-investment-advice disclaimer is on every
  page; **FR-013** every chart has a data-table alternative and CSV export where it has one today.
- **UI-001** types come from `services/api.d.ts`; responses are validated by `lib/schemas.ts`.
- **UI-002** every data region has loading, empty, error, and partial states.
- **UI-003** keyboard access, visible focus, aria labels, colourblind-safe charts, and never colour
  alone (gains and losses also carry a sign or arrow).
- **UI-004** route-level code splitting stays; **UI-006** usable at 360 px wide.
- **CIT-001/006** citation chips, numbering, and the source view keep working everywhere.
- "N/A" is never rendered as 0. A metric with no data is omitted or shown as N/A with its reason.

## Rules for every step

- **Frontend only.** Do not change `backend/`, `docs/openapi.json`, or `services/api.d.ts`. If a
  screen needs data the API does not expose, say so in the hand-off notes and design the empty
  state. Do not fake data.
- **Do not touch the data layer** (`lib/queries.ts`, `lib/schemas.ts`, `lib/apiClient.ts`,
  `lib/auth.tsx`, `lib/chatStream.ts`) except to add a hook a step explicitly calls for.
- **Dependencies** are decided once, in Step 1's ADR. Do not add others without an ADR.
- **Delete what you replace.** No `*Old.tsx`, no dead components, no unused tokens.
- **Gate:** `make check` passes (eslint, tsc, vitest, plus the backend suite it also runs) and
  `cd frontend && npm run build` succeeds, at the end of every step.
- **You must look at it.** Lint and types do not tell you a UI is good. Step 1 sets up a
  screenshot script; every later step runs it and attaches the dark and light captures of the
  screens it changed to its hand-off. If you cannot run a browser, say so plainly in the hand-off
  so the owner knows the step is unreviewed.
- **Known data gaps to design around, not hide:** Market Cap and P/E are usually missing
  (price-derived metrics are not persisted); quarterly/TTM series are often empty; dev prices are
  synthetic; a research report exists only after one is generated or seeded (`make seed`).

## Hand-off note (end of every step)

Append a short section to the step file you just finished, titled `## Hand-off`, with: what
shipped, what was deliberately left, any token or component API the next step should know about,
and the screenshot paths. The next agent reads it first.
