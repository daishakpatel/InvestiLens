// The comparison page's selection and ranking rules (§37.1), kept pure so they can be tested.
import type { ComparisonMetricRow } from "../types";
import { toNumber } from "./format";
import { metricBetter } from "./metricCatalog";

export const MIN_COMPANIES = 2;
export const MAX_COMPANIES = 6;

const TICKER = /^[A-Z][A-Z0-9.-]{0,9}$/;

/** The `?tickers=` parameter as a clean list: upper-cased, valid symbols only, no repeats, at
 *  most six. The URL is user-supplied, so anything else in it is dropped rather than sent on. */
export function parseTickers(param: string | null): string[] {
  const symbols = (param ?? "")
    .split(",")
    .map((part) => part.trim().toUpperCase())
    .filter((part) => TICKER.test(part));
  return [...new Set(symbols)].slice(0, MAX_COMPANIES);
}

/** The company with the strongest figure in a row, or null when there is no single one: fewer
 *  than two figures, a tie, or a metric where neither direction is better. */
export function leader(row: ComparisonMetricRow): string | null {
  const better = metricBetter(row.metric_name);
  if (!better) return null;
  const figures = row.cells.flatMap((cell) => {
    const value = toNumber(cell.result.value);
    return value === null ? [] : [{ ticker: cell.ticker, value }];
  });
  if (figures.length < 2) return null;
  const sorted = [...figures].sort((a, b) => (better === "higher" ? b.value - a.value : a.value - b.value));
  const [first, second] = sorted;
  return first && second && first.value !== second.value ? first.ticker : null;
}
