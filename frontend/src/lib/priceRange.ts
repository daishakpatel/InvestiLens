// Slicing a daily price series into chart ranges, and measuring the change across one.
// Pure functions over the series the page already has: choosing a range never refetches.
import { toNumber } from "./format";

export type RangeKey = "1M" | "3M" | "6M" | "1Y" | "5Y";

export const RANGES: { key: RangeKey; months: number; phrase: string }[] = [
  { key: "1M", months: 1, phrase: "past month" },
  { key: "3M", months: 3, phrase: "past 3 months" },
  { key: "6M", months: 6, phrase: "past 6 months" },
  { key: "1Y", months: 12, phrase: "past year" },
  { key: "5Y", months: 60, phrase: "past 5 years" },
];

export interface PriceBar {
  date: string; // ISO date
  close: number; // as traded that day
  adj: number; // split- and dividend-adjusted; continuous across corporate actions (DR-025)
}

/** Usable bars, oldest first. A day without a close is dropped; a missing adjusted close falls
 *  back to the raw close. */
export function toBars(
  points: readonly { date: string; close?: string | null; adj_close?: string | null }[] | undefined,
): PriceBar[] {
  const bars: PriceBar[] = [];
  for (const point of points ?? []) {
    const close = toNumber(point.close ?? null);
    if (close === null) continue;
    bars.push({ date: point.date, close, adj: toNumber(point.adj_close ?? null) ?? close });
  }
  return bars;
}

function monthsBefore(isoDate: string, months: number): string {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCMonth(date.getUTCMonth() - months);
  return date.toISOString().slice(0, 10);
}

const DAY_MS = 86_400_000;
const daysBetween = (from: string, to: string) => (Date.parse(to) - Date.parse(from)) / DAY_MS;

/** The bars within `months` of the latest one. */
export function sliceRange(bars: readonly PriceBar[], months: number): PriceBar[] {
  const last = bars.at(-1);
  if (!last) return [];
  const start = monthsBefore(last.date, months);
  return bars.filter((bar) => bar.date >= start);
}

/** Ranges the series can actually fill. A range is offered when the data reaches back at least
 *  90% of the way: a series one trading day short of five years still earns "5Y", but two months
 *  of data are never drawn under a "1Y" label. */
export function availableRanges(bars: readonly PriceBar[]): RangeKey[] {
  const first = bars[0];
  const last = bars.at(-1);
  if (!first || !last || bars.length < 2) return [];
  const covered = daysBetween(first.date, last.date);
  return RANGES.filter(
    ({ months }) => covered >= 0.9 * daysBetween(monthsBefore(last.date, months), last.date),
  ).map(({ key }) => key);
}

export interface RangeChange {
  abs: number;
  pct: number | null; // ratio; null when the opening price is not positive
}

/** Change from the first bar of a range to the bar at `index` (default: the last), measured on
 *  adjusted closes so a split inside the range is not read as a crash. */
export function rangeChange(bars: readonly PriceBar[], index = bars.length - 1): RangeChange | null {
  const open = bars[0];
  const at = bars[index];
  if (!open || !at) return null;
  const abs = at.adj - open.adj;
  return { abs, pct: open.adj > 0 ? abs / open.adj : null };
}
