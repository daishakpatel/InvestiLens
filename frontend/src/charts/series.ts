// Turning a metric series into chart rows, and choosing how to print its numbers.
// Display only: values arrive from the API already computed (DR-040); the one thing derived here
// is the period-over-period change between two values that are both on screen.
import { toNumber } from "../lib/format";
import type { MetricSeriesPoint } from "../types";

export interface SeriesRow {
  period: string;
  periodEnd: string | null;
  value: number | null; // null = N/A for that period (never drawn as 0, DR-041)
  change: number | null;
  sourceId: string | null; // backend-issued, opens in the citation drawer
  formula: string | null; // derived figures only: "Q3 = 9M YTD - 6M YTD" (CIT-003)
}

/** How a metric is printed. The API's `unit` cannot say this alone: a margin and a current
 *  ratio are both "ratio", but one reads as 71% and the other as 4.45×. */
export type Display = "money" | "percent" | "multiple" | "perShare" | "count";

export function displayOf(unit: string, multiple = false): Display {
  const u = unit.toLowerCase();
  if (u === "x") return "multiple"; // valuation multiples arrive with their own unit (ADR-0036)
  if (u === "ratio") return multiple ? "multiple" : "percent";
  if (u === "usd") return "money";
  if (u === "usd/shares") return "perShare";
  return "count";
}

/** Change vs the prior period. A percentage (a margin) changes by a difference, in points;
 *  anything else by a relative change, which is undefined from a zero or negative base (DR-041
 *  NEGATIVE_BASE), so none is reported there. */
export function changeBetween(
  current: number | null,
  prior: number | null,
  display: Display,
): number | null {
  if (current === null || prior === null) return null;
  if (display === "percent") return current - prior;
  return prior > 0 ? (current - prior) / prior : null;
}

export function toRows(points: readonly MetricSeriesPoint[], display: Display): SeriesRow[] {
  return points.map((point, i) => {
    const value = toNumber(point.value);
    const prior = i > 0 ? toNumber(points[i - 1]?.value ?? null) : null;
    return {
      period: point.period,
      periodEnd: point.period_end ?? null,
      value,
      change: changeBetween(value, prior, display),
      sourceId: point.source_id ?? null,
      formula: point.formula ?? null,
    };
  });
}

/** TTM points keyed by the quarter they end with: "TTM-Q2-FY2026" → "Q2-FY2026", so a TTM line
 *  sits on the bar of its last quarter. */
export function trendByQuarter(trend: readonly MetricSeriesPoint[]): Map<string, MetricSeriesPoint> {
  return new Map(trend.map((point) => [point.period.replace(/^TTM-/, ""), point]));
}

export interface Scale {
  divisor: number;
  suffix: "" | "K" | "M" | "B" | "T";
  word: string; // for table captions: "billions"
}

const SCALES: Scale[] = [
  { divisor: 1e12, suffix: "T", word: "trillions" },
  { divisor: 1e9, suffix: "B", word: "billions" },
  { divisor: 1e6, suffix: "M", word: "millions" },
  { divisor: 1e3, suffix: "K", word: "thousands" },
  { divisor: 1, suffix: "", word: "units" },
];

/** One scale for a whole axis or table, from its largest magnitude, so every figure in it reads
 *  in the same unit ($B throughout, never $B beside $M). */
export function pickScale(values: readonly (number | null)[]): Scale {
  const max = Math.max(0, ...values.map((v) => Math.abs(v ?? 0)));
  return SCALES.find((scale) => max >= scale.divisor) ?? { divisor: 1, suffix: "", word: "units" };
}

function niceStep(raw: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / magnitude;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * magnitude;
}

export interface Axis {
  domain: [number, number];
  ticks: number[];
}

/** Round tick values and the range they span. Bars measure from zero, so their axis includes it
 *  (`fromZero`); a line of ratios need not. A minimum only slightly below zero (one small loss
 *  in a long history) extends the range just far enough to draw it, rather than adding a whole
 *  empty tick step beneath the baseline. */
export function axisFor(values: readonly (number | null)[], fromZero: boolean): Axis {
  const present = values.filter((value): value is number => value !== null);
  if (present.length === 0) return { domain: [0, 1], ticks: [0, 1] };
  let min = Math.min(...present);
  let max = Math.max(...present);
  if (fromZero) {
    min = Math.min(0, min);
    max = Math.max(0, max);
  }
  if (min === max) max = min + Math.abs(min || 1);

  const step = niceStep((max - min) / 3);
  const hi = Math.ceil(max / step - 1e-9) * step;
  let lo = Math.floor(min / step + 1e-9) * step;
  if (fromZero && min < 0 && -min < step * 0.3) lo = min * 1.5;

  const ticks: number[] = [];
  for (let i = Math.ceil(lo / step - 1e-9); i * step <= hi + step * 1e-9; i++) {
    ticks.push(Number((i * step).toPrecision(12)));
  }
  return { domain: [lo, hi], ticks };
}

/** The scale for a statement table: the largest unit that still leaves the biggest figure at
 *  least two digits before the point. A bank with $4.4T in assets is tabled in billions
 *  (4,424.9), not trillions, where every smaller line would round to 0.1 or 0.4. */
export function pickTableScale(values: readonly (number | null)[]): Scale {
  const max = Math.max(0, ...values.map((v) => Math.abs(v ?? 0)));
  return SCALES.find((scale) => max >= scale.divisor * 10) ?? { divisor: 1, suffix: "", word: "units" };
}

const trim = (n: number, digits: number) =>
  n.toLocaleString("en-US", { maximumFractionDigits: digits });

const scaled = (value: number, scale: Scale, digits: number) =>
  `${trim(Math.abs(value) / scale.divisor, scale.suffix ? digits : 0)}${scale.suffix}`;

/** A short axis tick: "$216B", "71%", "4.5×", "$4.90". */
export function formatTick(value: number, display: Display, scale: Scale): string {
  const sign = value < 0 ? "−" : "";
  switch (display) {
    case "percent":
      return `${sign}${trim(Math.abs(value) * 100, 0)}%`;
    case "multiple":
      return `${sign}${trim(Math.abs(value), 1)}×`;
    case "perShare":
      return `${sign}$${Math.abs(value).toFixed(2)}`;
    case "money":
      return `${sign}$${scaled(value, scale, 1)}`;
    default:
      return `${sign}${scaled(value, scale, 1)}`;
  }
}

/** A value in full, for tooltips, stats and chart tables: "$215.94B", "71.1%", "4.45×". */
export function formatValue(value: number, display: Display): string {
  const sign = value < 0 ? "−" : "";
  const size = Math.abs(value);
  switch (display) {
    case "percent":
      return `${sign}${(size * 100).toFixed(1)}%`;
    case "multiple":
      return `${sign}${size.toFixed(2)}×`;
    case "perShare":
      return `${sign}$${size.toFixed(2)}`;
    case "money":
      return `${sign}$${scaled(value, pickScale([value]), 2)}`;
    default:
      return `${sign}${scaled(value, pickScale([value]), 2)}`;
  }
}

/** A statement-table cell, in the scale the table's caption names: "215.9", "71.1%", "4.45×". */
export function formatCell(value: number, display: Display, scale: Scale): string {
  if (display === "money" || display === "count") {
    const digits = scale.suffix ? 1 : 0;
    const body = (Math.abs(value) / scale.divisor).toLocaleString("en-US", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    });
    // A loss too small to register at this scale is "0.0", not "−0.0".
    return value < 0 && Number(body.replace(/,/g, "")) !== 0 ? `−${body}` : body;
  }
  return display === "perShare" ? formatValue(value, display).replace("$", "") : formatValue(value, display);
}

/** "FY2026" → "FY26", "Q4-FY2026" → "Q4 FY26", "TTM-Q4-FY2026" → "TTM Q4 FY26": axis labels
 *  that fit under a bar. */
export function shortPeriod(period: string): string {
  return period.replaceAll("-", " ").replace(/FY(\d{2})(\d{2})/, "FY$2");
}
