# ADR-0028: UI rebuild — design system, theme default & frontend dependencies

- **Status:** Accepted
- **Date:** 2026-10-10
- **Spec refs:** §27.3 (UI-001 to UI-007), FR-010, FR-011, FR-012; `Instructions/UI_plan/`

## Problem

The owner rejected the Phase 4c/4d interface as dated and asked for a dark-first, minimalist
rebuild in the manner of Robinhood and TradingView (`Instructions/UI_plan/00_README.md`). Step 1
needs decisions that every later step inherits: which theme is the default, what the colour tokens
are and whether they are legible, and which dependencies the rebuild may use, so they are argued
once rather than per screen.

## Decision

**Theme.** Dark is the default for every visitor regardless of OS preference; light applies only
when the user chooses it (`localStorage["il-theme"] = "light"`, class `.light` on `<html>`, set
by a pre-paint script). Tokens live only in `frontend/src/index.css`: dark on `:root`, light on
`:root.light`. No hex colour appears anywhere else in `frontend/src`.

**Dependencies** (four, all runtime; no others without a new ADR):

- `@fontsource-variable/inter` — Inter, self-hosted. The API's CSP and offline dev/tests rule out
  a font CDN.
- `radix-ui` (unified package) — behaviour only for Dialog/Drawer, Popover, Tooltip, Tabs,
  DropdownMenu, ToggleGroup, Checkbox, Switch. Focus trapping, roving focus, and aria wiring are
  where hand-rolled components were weakest; all styling stays ours.
- `cmdk` — command palette, used from Step 2. Installed now so dependencies are settled once.
- `lucide-react` — icons, imported per icon; replaces text glyphs (☀ ☾ ▲ ▼ ↗ ×).
- Charts stay on Recharts. Not adopted: a component kit (shadcn, MUI, Chakra), a CSS-in-JS
  runtime, or a second chart library.

**Primitives** live in `frontend/src/components/ui/`, one small file each, imported directly (no
barrel). `Section` (borderless heading + content) replaces `Panel` as the default container;
FR-010 is met by one `AiMark` on an AI section's heading instead of a "Data"/"AI" badge on every
panel. `/_ui` is a dev-only gallery of every primitive; `e2e` `npm run screenshots` captures it and
the main screens in both themes at 1440 px and 390 px.

**Measured contrast** (WCAG 2.x relative-luminance formula; foreground on `bg` / `surface` /
`surface-2`). The plan's starting values passed in dark. In light, `positive`, `negative`,
`warning`, and `subtle` failed and were darkened; the table shows the shipped values.

| Token | Dark | Ratios | Light | Ratios |
|-------|------|--------|-------|--------|
| `text` | `#f3f5f7` | 18.0 / 17.0 / 15.8 | `#0b0d10` | 19.5 / 18.3 / 17.2 |
| `muted` | `#a1a7b0` | 8.1 / 7.7 / 7.1 | `#565d68` | 6.6 / 6.3 / 5.9 |
| `subtle` | `#6b727d` | 4.1 / 3.8 / 3.6 | `#6f7681` (was `#868d97`: 3.4 / 3.2 / 3.0) | 4.6 / 4.3 / 4.1 |
| `primary` | `#5b8cff` | 6.2 / 5.9 / 5.5 | `#2456e6` | 5.9 / 5.6 / 5.2 |
| `positive` | `#2fd27a` | 10.0 / 9.4 / 8.7 | `#067a3c` (was `#0a8a45`: 4.4 / 4.2 / 3.9) | 5.4 / 5.1 / 4.8 |
| `negative` | `#ff5c5c` | 6.5 / 6.2 / 5.7 | `#c8261a` (was `#d92d20`: 4.8 / 4.5 / 4.3) | 5.6 / 5.3 / 5.0 |
| `warning` | `#f5b84a` | 11.1 / 10.5 / 9.7 | `#9a5106` (was `#b25e09`: 4.7 / 4.4 / 4.1) | 5.9 / 5.6 / 5.2 |
| `ai` | `#a78bfa` | 7.2 / 6.8 / 6.3 | `#6d3fe0` | 6.1 / 5.8 / 5.4 |
| `primary-contrast` on `primary` | `#0a0b0d` | 6.2 | `#ffffff` | 5.9 |

Chart series colours (Okabe–Ito hues, UI-003) are at least 7.1:1 on the dark canvas and 3.6:1 on
the light one, above the 3:1 needed for graphical objects.

## Consequences

`text`, `muted`, and every semantic colour pass AA (4.5:1) on `bg`, `surface`, and `surface-2` in
both themes. Known shortfalls, accepted for now: dark `subtle` is 3.6 to 4.1:1, so it is for
non-essential text only (units, timestamps, axis ticks), never for anything a user must read;
input and hairline borders (`border-strong` about 1.5:1) do not meet the 3:1 non-text guideline,
so fields rely on their filled background, label, and focus ring. Radix adds one shared chunk of
about 18 kB gzip; the entry bundle grew 0.4 kB gzip. The font package emits seven subset files but
browsers fetch only the Latin one for our content. Revisit if a second accent colour is wanted, if
an accessibility audit (Step 5) rejects the border contrast, or if Radix's unified package stops
tree-shaking cleanly.
