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
| `muted` | `#a1a7b0` | 8.1 / 7.7 / 7.1 | `#4d545e` (was `#565d68`: 6.6 / 6.3 / 5.9) | 7.7 / 7.2 / 6.8 |
| `subtle` | `#848c97` (was `#6b727d`: 4.1 / 3.8 / 3.6) | 5.8 / 5.5 / 5.1 | `#656c77` (was `#868d97`, then `#6f7681`: 4.6 / 4.3 / 4.1) | 5.3 / 5.0 / 4.7 |
| `primary` | `#5b8cff` | 6.2 / 5.9 / 5.5 | `#2456e6` | 5.9 / 5.6 / 5.2 |
| `positive` | `#2fd27a` | 10.0 / 9.4 / 8.7 | `#067a3c` (was `#0a8a45`: 4.4 / 4.2 / 3.9) | 5.4 / 5.1 / 4.8 |
| `negative` | `#ff5c5c` | 6.5 / 6.2 / 5.7 | `#c8261a` (was `#d92d20`: 4.8 / 4.5 / 4.3) | 5.6 / 5.3 / 5.0 |
| `warning` | `#f5b84a` | 11.1 / 10.5 / 9.7 | `#9a5106` (was `#b25e09`: 4.7 / 4.4 / 4.1) | 5.9 / 5.6 / 5.2 |
| `ai` | `#a78bfa` | 7.2 / 6.8 / 6.3 | `#6d3fe0` | 6.1 / 5.8 / 5.4 |
| `primary-contrast` on `primary` | `#0a0b0d` | 6.2 | `#ffffff` | 5.9 |

**Categorical chart colours** (re-stepped in UI plan Step 5). The first set, Okabe–Ito hues
lightened for the dark canvas, failed the palette validator in dark: too light for the band, and
its worst neighbouring pair was 5.9 ΔE apart under deuteranopia. The shipped set is sky blue,
amber, bluish green, vermillion, indigo, reddish purple, in that order, darker in dark and with
indigo replacing the second blue so no two slots read as the same hue.

| Slot | Dark | On `bg` | Light | On `bg` |
|------|------|---------|-------|---------|
| 1 sky blue | `#3d9bd1` | 6.4 | `#0072b2` | 5.2 |
| 2 amber | `#c98500` | 6.4 | `#b87400` | 3.8 |
| 3 bluish green | `#009e73` | 5.8 | `#008563` | 4.6 |
| 4 vermillion | `#d55e00` | 5.1 | `#c85200` | 4.5 |
| 5 indigo | `#7a6ff0` | 5.0 | `#5b4fc7` | 6.2 |
| 6 reddish purple | `#c06a9b` | 5.4 | `#b85c92` | 4.2 |

Validator results, neighbouring slots: lightness band, chroma floor and 3:1 contrast pass in both
themes; worst pair under colour-vision deficiency 8.8 ΔE in dark and 8.2 in light (target 8);
worst pair in normal vision 17.2 and 19.3 (floor 15). The set does **not** pass for every pair
(amber and vermillion are 4.6 apart under deuteranopia), so a chart must keep neighbouring slots
adjacent and never place distant ones side by side; the one user, the portfolio's sector bar,
orders its segments by slot. A single series is drawn in neutral ink and uses none of these.

Tints measured in Step 5: inserted text in a diff on its 10% tint, 8.7 dark and 4.7 light (the
tint was 15% until axe measured light at 4.4); text on the strongest heat-table cell, 6.5 and 7.6;
on the strongest correlation cell, 6.4 and 8.0 or better.

## Consequences

`text`, `muted`, `subtle`, and every semantic colour pass AA (4.5:1) on `bg`, `surface`, and
`surface-2` in both themes. `subtle` originally shipped at 3.6 to 4.1:1 in dark on the theory that
it carried only non-essential text; UI plan Step 2's first axe run flagged it (it is used for the
search placeholder, data freshness, and the disclaimer), so it was raised, and light `muted` was
darkened to keep the two apart. Known shortfall, accepted for now: input and hairline borders (`border-strong` about 1.5:1) do not meet the 3:1 non-text guideline,
so fields rely on their filled background, label, and focus ring. Radix adds one shared chunk of
about 18 kB gzip; the entry bundle grew 0.4 kB gzip. The font package emits seven subset files but
browsers fetch only the Latin one for our content. Revisit if a second accent colour is wanted, if
an accessibility audit (Step 5) rejects the border contrast, or if Radix's unified package stops
tree-shaking cleanly.

## Addendum: UI plan Step 5 (2026-10-11)

- **Motion** is one set in the theme: 120 ms for hover and press (the default for every
  transition), 200 ms ease-out for things that arrive, 1.2 s for the skeleton shimmer, nothing
  further than 8 px, all off under `prefers-reduced-motion`. Entrances on Radix layers are tied
  to the open state, because Radix keeps a closing layer mounted while an animation runs on it.
- **Touch targets** are at least 40 px on coarse pointers without changing how controls look:
  an invisible centred pseudo-element extends each one. Controls packed side by side, or clipped
  by a scroll area, are made 40 px themselves on touch instead.
- **Font** is now only Inter's Latin and Latin-extended subsets, declared in `index.css`; the
  Latin file is preloaded by the build. Other scripts fall back to the system font.
- **`--scrim`** joins the tokens (the backdrop of the search palette), which removes the last
  literal colour from the components.
- **Removed** as unused by any screen: the `Dialog`, `Drawer`, `Checkbox` and `Surface`
  primitives and `EvidenceBadge`. The side panel replaced the drawer.
- No dependency was added.
