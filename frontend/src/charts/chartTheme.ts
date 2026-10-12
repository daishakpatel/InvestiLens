// Shared chart styling. Every value is a CSS variable from index.css, resolved by the browser at
// paint time, so charts follow the theme switch with no re-render and no reload.
//
// The look, fixed across charts: a single series in neutral ink (never a categorical hue); bars
// at most 24 px wide with a 4 px rounded data end; 2 px lines; solid hairline horizontal gridlines
// only; no axis lines, no tick marks, no chart border.

export const INK = "var(--chart-ink)";
export const INK_STRONG = "var(--chart-ink-strong)"; // the hovered mark
export const POSITIVE = "var(--positive)";
export const NEGATIVE = "var(--negative)";
export const SURFACE = "var(--bg)"; // rings and gaps are drawn in the canvas colour

const AXIS_TICK = {
  fill: "var(--text-subtle)",
  fontSize: 12,
  style: { fontVariantNumeric: "tabular-nums" },
} as const;

export const AXIS = { tickLine: false, axisLine: false, tick: AXIS_TICK } as const;
export const GRID = { stroke: "var(--chart-grid)", vertical: false } as const;
export const ZERO_LINE = { stroke: "var(--border-strong)", strokeWidth: 1 } as const;

export const BAR = { maxBarSize: 24, radius: [4, 4, 0, 0] as [number, number, number, number] };
export const LINE = { strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round" } as const;
/** The dot on a hovered line point: 8 px, ringed in the canvas colour so it reads over the line. */
export const ACTIVE_DOT = { r: 4, fill: INK_STRONG, stroke: SURFACE, strokeWidth: 2 } as const;

export const CROSSHAIR = { stroke: "var(--border-strong)", strokeWidth: 1 } as const;
export const BAR_CURSOR = { fill: "var(--surface-2)" } as const;
