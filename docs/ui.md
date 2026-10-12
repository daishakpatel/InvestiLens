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
