import { describe, expect, it } from "vitest";

import type { ComparisonMetricRow } from "../types";
import { leader, parseTickers } from "./compare";

const row = (metric: string, values: Record<string, string | null>): ComparisonMetricRow =>
  ({
    metric_name: metric,
    unit: "ratio",
    cells: Object.entries(values).map(([ticker, value]) => ({
      ticker,
      result: { value, unit: "ratio", inputs: [], formula_id: metric, warnings: [] },
      percentile: null,
    })),
  }) as ComparisonMetricRow;

// §37.1: the selection is shareable by URL, so the URL is parsed defensively.
describe("parseTickers", () => {
  it("cleans a shared list: case, spaces, repeats, and at most six", () => {
    expect(parseTickers(" nvda, AMD ,nvda,brk.b")).toEqual(["NVDA", "AMD", "BRK.B"]);
    expect(parseTickers("A,B,C,D,E,F,G,H")).toHaveLength(6);
  });

  it("drops anything that is not a ticker", () => {
    expect(parseTickers("NVDA,<script>,../x,,AMD")).toEqual(["NVDA", "AMD"]);
    expect(parseTickers(null)).toEqual([]);
  });
});

// §37.1 / UI plan Step 5: the strongest figure in a row is emphasised; "strongest" depends on the metric.
describe("leader", () => {
  it("is the highest for a margin and the lowest for debt", () => {
    expect(leader(row("gross_margin", { NVDA: "0.71", AMD: "0.49" }))).toBe("NVDA");
    expect(leader(row("total_debt", { NVDA: "8468", INTC: "46585" }))).toBe("NVDA");
  });

  it("is nobody for a valuation multiple, a tie, or a row with one figure (N/A is not zero)", () => {
    expect(leader(row("pe_ratio", { NVDA: "40", AMD: "30" }))).toBeNull();
    expect(leader(row("net_margin", { NVDA: "0.2", AMD: "0.2" }))).toBeNull();
    expect(leader(row("net_margin", { NVDA: "-0.1", AMD: null }))).toBeNull();
  });
});
