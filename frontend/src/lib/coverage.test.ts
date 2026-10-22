import { describe, expect, it } from "vitest";

import type { MetricsCoverageResponse } from "../types";
import { availabilityNote, latestTtmAvailability } from "./coverage";

// FR-QT-010 / DR-042: a missing quarter is counted; a sector N/A metric is not a gap.
const coverage: MetricsCoverageResponse = {
  ticker: "TST",
  quarters: ["Q1-FY2025", "Q2-FY2025", "Q3-FY2025", "Q4-FY2025", "Q1-FY2026"],
  metrics: [
    {
      metric_name: "revenue",
      applicable: true,
      present: ["Q1-FY2025", "Q2-FY2025", "Q3-FY2025", "Q4-FY2025", "Q1-FY2026", "TTM-Q1-FY2026"],
      missing: [],
    },
    {
      metric_name: "operating_cash_flow",
      applicable: true,
      present: ["Q1-FY2025", "Q2-FY2025", "Q4-FY2025", "Q1-FY2026"],
      missing: [{ period: "Q3-FY2025", reason: "missing_ytd_3q" }],
    },
    { metric_name: "gross_margin", applicable: false, present: [], missing: [] },
    { metric_name: "fcf_margin", applicable: true, present: ["TTM-Q1-FY2026"], missing: [] },
  ],
  freshness: { as_of: "2026-10-21T00:00:00Z", source: "sec", freshness_status: "fresh" },
};

describe("latestTtmAvailability", () => {
  it("counts the latest four stored quarters that hold a value", () => {
    expect(latestTtmAvailability(coverage, "revenue")).toEqual({ available: 4, needed: 4 });
    expect(latestTtmAvailability(coverage, "operating_cash_flow")).toEqual({ available: 3, needed: 4 });
  });

  it("says nothing for a sector N/A metric, a TTM-only ratio, an unknown metric, or no report", () => {
    expect(latestTtmAvailability(coverage, "gross_margin")).toBeNull();
    expect(latestTtmAvailability(coverage, "fcf_margin")).toBeNull(); // no quarters of its own
    expect(latestTtmAvailability(coverage, "unknown")).toBeNull();
    expect(latestTtmAvailability(undefined, "revenue")).toBeNull();
  });
});

describe("availabilityNote", () => {
  it("speaks only when the latest window is short of four quarters", () => {
    expect(availabilityNote({ available: 3, needed: 4 })).toMatch(/^3 of 4 quarters available/);
    expect(availabilityNote({ available: 4, needed: 4 })).toBeNull();
    expect(availabilityNote(null)).toBeNull();
  });
});
