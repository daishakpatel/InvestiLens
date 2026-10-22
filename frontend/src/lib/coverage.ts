// Quarterly coverage (Phase 7b, FR-QT-010): how many of the four quarters a TTM figure needs are
// stored, so a card can say "3 of 4 quarters available" instead of showing an empty box.
import type { MetricsCoverageResponse } from "../types";

export const TTM_QUARTERS = 4;

export interface QuarterAvailability {
  available: number;
  needed: number;
}

const isTtm = (period: string) => period.startsWith("TTM-");

/** Of the latest four stored quarters, how many hold a value for `metric`. Null when the metric
 *  is not in the report, has no quarters of its own (a TTM ratio is computed from other
 *  metrics' sums), or is not applicable to the sector: N/A is not a gap (DR-042). */
export function latestTtmAvailability(
  coverage: MetricsCoverageResponse | undefined,
  metric: string,
): QuarterAvailability | null {
  const entry = coverage?.metrics.find((m) => m.metric_name === metric);
  if (!coverage || !entry || !entry.applicable) return null;
  const quarterly =
    entry.present.some((p) => !isTtm(p)) || entry.missing.some((m) => !isTtm(m.period));
  if (!quarterly) return null;
  const latest = coverage.quarters.slice(-TTM_QUARTERS);
  const present = new Set(entry.present);
  return { available: latest.filter((q) => present.has(q)).length, needed: TTM_QUARTERS };
}

/** The one-line note for a TTM-dependent card whose latest window is incomplete, else null. */
export function availabilityNote(availability: QuarterAvailability | null): string | null {
  if (!availability || availability.available >= availability.needed) return null;
  return `${availability.available} of ${availability.needed} quarters available, so the latest trailing twelve months is not shown.`;
}
