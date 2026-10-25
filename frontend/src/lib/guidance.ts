// Guidance vs actual (Phase 7i). Display only: ranges, outcomes and labels come computed; nothing
// here judges how a company guides (FR-GD-012).
import type { GuidanceRow, GuidanceValue, TrackRecordQuarter } from "../types";
import { formatMetricValue, formatPercent, toNumber } from "./format";

type Result = NonNullable<GuidanceValue["outcome"]>["result"];

export const RESULT_LABEL: Record<Result, string> = {
  above_range: "Above range",
  within_range: "Within range",
  below_range: "Below range",
  not_comparable: "Not comparable",
  actual_unavailable: "Not reported yet",
};

export const BASIS_LABEL: Record<GuidanceRow["basis"], string> = {
  gaap: "GAAP",
  non_gaap: "Non-GAAP",
  unspecified: "",
};

export const EMPTY_TEXT = "No guidance has been read from this company's earnings releases yet.";

/** Whether the result is a comparison at all (the chip gets the data tone only then). */
export const isCompared = (result: Result): boolean =>
  result === "above_range" || result === "within_range" || result === "below_range";

function unitFor(row: Pick<GuidanceRow, "unit" | "metric">): string {
  if (row.unit !== "usd") return "ratio";
  return row.metric.startsWith("eps") ? "usd/shares" : "usd";
}

/** One figure in the row's unit: "$108B", "$1.25", "74.0%". */
export function guidedFigure(row: Pick<GuidanceRow, "unit" | "metric">, value: string | null | undefined): string {
  return formatMetricValue(value ?? null, unitFor(row));
}

/** The guided range as stated: "$105.84B–$110.16B", or the single figure. */
export function guidedText(row: Pick<GuidanceRow, "unit" | "metric">, value: GuidanceValue): string {
  if (value.point !== null) return guidedFigure(row, value.point);
  return `${guidedFigure(row, value.low)}–${guidedFigure(row, value.high)}`;
}

/** Signed distance from the guided midpoint, under a "vs midpoint" header: "+4.6%" for money,
 *  "+0.5 pts" for a ratio (a margin's percentage change would read as points to most people). */
export function deltaText(row: Pick<GuidanceRow, "unit">, value: GuidanceValue): string | null {
  const outcome = value.outcome;
  if (!outcome || !isCompared(outcome.result)) return null;
  if (row.unit === "usd") {
    const pct = toNumber(outcome.delta_vs_mid_pct);
    return pct === null ? null : `${pct >= 0 ? "+" : "−"}${formatPercent(Math.abs(pct))}`;
  }
  const points = toNumber(outcome.delta_vs_mid);
  return points === null ? null : `${points >= 0 ? "+" : "−"}${(Math.abs(points) * 100).toFixed(1)} pts`;
}

/** "Revised 2026-08-26: 16.0%–18.0%" lines for a row's later releases. */
export function revisionText(row: GuidanceRow, revision: GuidanceValue): string {
  const date = revision.issued_at ? revision.issued_at.slice(0, 10) : "date unknown";
  return `Revised ${date}: ${guidedText(row, revision)}`;
}

export interface QuarterGeometry {
  label: string;
  rangeStart: number; // 0-100 along the shared axis
  rangeEnd: number;
  actual: number | null;
  actualPct: number | null; // actual vs guided midpoint, as a decimal
  result: Result;
  sourceId: string;
}

/** Each guided quarter on one axis of "% from the guided midpoint", so quarters of very
 *  different size compare: the guided range is a band, the actual a dot. The axis is symmetric
 *  around 0 and wide enough for every band and dot. Oldest first, left to right in reading. */
export function dotPlot(quarters: TrackRecordQuarter[]): { quarters: QuarterGeometry[]; extent: number } {
  const rows = quarters
    .map((q) => {
      const low = toNumber(q.low);
      const high = toNumber(q.high);
      if (low === null || high === null || low + high === 0) return null;
      const mid = (low + high) / 2;
      const actual = toNumber(q.actual_value);
      return { q, lowPct: (low - mid) / mid, highPct: (high - mid) / mid, actualPct: actual === null ? null : (actual - mid) / mid };
    })
    .filter((r): r is NonNullable<typeof r> => r !== null)
    .reverse();
  const furthest = Math.max(0.01, ...rows.flatMap((r) => [Math.abs(r.lowPct), Math.abs(r.highPct), Math.abs(r.actualPct ?? 0)]));
  const extent = Math.ceil(furthest * 110 - 1e-9) / 100; // a whole percent past 1.1x the furthest mark
  const at = (pct: number) => ((pct + extent) / (2 * extent)) * 100;
  return {
    extent,
    quarters: rows.map(({ q, lowPct, highPct, actualPct }) => ({
      label: q.period_label,
      rangeStart: at(lowPct),
      rangeEnd: at(highPct),
      actual: actualPct === null ? null : at(actualPct),
      actualPct,
      result: q.result,
      sourceId: q.source_id,
    })),
  };
}
