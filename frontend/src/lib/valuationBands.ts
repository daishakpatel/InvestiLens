// Valuation bands (Phase 7h). Display only: values, percentiles and labels come computed.
import type { ValuationBand } from "../types";
import { toNumber } from "./format";

const LABELS: Record<string, string> = {
  pe_ratio: "P/E (TTM)",
  ps_ratio: "P/S",
  ev_revenue: "EV/Revenue",
  ev_ebitda: "EV/EBITDA",
  ev_fcf: "EV/FCF",
  pb_ratio: "P/B",
  fcf_yield: "FCF yield",
  earnings_yield: "Earnings yield",
};

export const multipleLabel = (multiple: string): string => LABELS[multiple] ?? multiple;

/** Multiples as "12.3×", yields as "4.5%" (FR-PS-014). */
export function bandValue(value: string | number | null | undefined, unit: ValuationBand["unit"]): string {
  const n = typeof value === "number" ? value : toNumber(value ?? null);
  if (n === null) return "—";
  return unit === "ratio" ? `${(n * 100).toFixed(1)}%` : `${n.toFixed(1)}×`;
}

export interface BandGeometry {
  low: number;
  high: number;
  today: number; // 0-100, position along the track
  rangeStart: number;
  rangeEnd: number;
  peerMedian: number | null;
}

/** Where to draw the 5-year range, today's marker and the peer-median tick, as percentages of a
 *  scale wide enough for all three; null when there is nothing to draw (not ok, no range). */
export function bandGeometry(band: ValuationBand): BandGeometry | null {
  const today = toNumber(band.value ?? null);
  const min = toNumber(band.own.min ?? null);
  const max = toNumber(band.own.max ?? null);
  if (band.status !== "ok" || today === null || min === null || max === null) return null;
  const median = toNumber(band.peers.median ?? null);
  const values = [min, max, today, ...(median === null ? [] : [median])];
  let low = Math.min(...values);
  let high = Math.max(...values);
  const pad = (high - low) * 0.05 || Math.abs(high) * 0.05 || 1;
  low -= pad;
  high += pad;
  const at = (v: number) => ((v - low) / (high - low)) * 100;
  return { low, high, today: at(today), rangeStart: at(min), rangeEnd: at(max), peerMedian: median === null ? null : at(median) };
}

/** The sentence under a bar: positions and sample sizes, never a judgement of value. `shown`
 *  is a reason already printed in place of the bar, so it is not repeated. */
export function bandSummary(band: ValuationBand, shown?: string | null): string {
  const ownReason = band.own.reason === shown ? "" : (band.own.reason ?? "");
  const own = band.own.label ? `${band.own.label} (n=${band.own.n})` : ownReason;
  const peers = band.peers.label ? `${band.peers.label} (n=${band.peers.n})` : (band.peers.reason ?? "");
  return [own, peers].filter(Boolean).join(" · ");
}
