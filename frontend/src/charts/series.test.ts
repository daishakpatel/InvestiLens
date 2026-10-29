import { describe, expect, it } from "vitest";

import {
  axisFor,
  changeBetween,
  displayOf,
  formatCell,
  formatTick,
  formatValue,
  growthSplit,
  pickScale,
  pickTableScale,
  shortPeriod,
  toRows,
  trendByQuarter,
} from "./series";

// UI plan Step 3 chart system. DR-041: N/A is never 0, and growth from a non-positive base is
// not reported. Money is scaled for display only (conventions: "$M / $B only at display time").
describe("changeBetween", () => {
  it("is a relative change for amounts and multiples, a difference for percentages", () => {
    expect(changeBetween(150, 100, "money")).toBeCloseTo(0.5);
    expect(changeBetween(0.71, 0.75, "percent")).toBeCloseTo(-0.04); // margins move in points
    expect(changeBetween(4.4, 4.0, "multiple")).toBeCloseTo(0.1);
  });

  it("is undefined from a missing, zero, or negative base (DR-041 NEGATIVE_BASE)", () => {
    expect(changeBetween(50, -10, "money")).toBeNull();
    expect(changeBetween(50, 0, "money")).toBeNull();
    expect(changeBetween(50, null, "money")).toBeNull();
    expect(changeBetween(null, 50, "money")).toBeNull();
  });
});

describe("toRows", () => {
  it("keeps N/A as null rather than zero, and derives each period's change", () => {
    const rows = toRows(
      [
        { period: "FY2024", period_end: "2024-01-28", value: "100.0", unit: "USD" },
        { period: "FY2025", period_end: null, value: null, unit: "USD" },
        { period: "FY2026", period_end: "2026-01-25", value: "300.0", unit: "USD" },
      ],
      "money",
    );
    expect(rows.map((r) => r.value)).toEqual([100, null, 300]);
    expect(rows.map((r) => r.change)).toEqual([null, null, null]); // no prior on either side
    expect(rows[1]?.periodEnd).toBeNull();
  });

  it("carries each point's source ID and, for derived figures, its formula (CIT-003)", () => {
    const [direct, derived] = toRows(
      [
        { period: "Q3-FY2026", value: "1", unit: "USD", source_id: "xbrl:NVDA:revenue:Q3-FY2026" },
        {
          period: "Q4-FY2026",
          value: "2",
          unit: "USD",
          source_id: "derived:NVDA:revenue:Q4-FY2026",
          formula: "Q4 = FY - (Q1 + Q2 + Q3)",
        },
      ],
      "money",
    );
    expect(direct).toMatchObject({ sourceId: "xbrl:NVDA:revenue:Q3-FY2026", formula: null });
    expect(derived?.formula).toBe("Q4 = FY - (Q1 + Q2 + Q3)");
  });
});

describe("trendByQuarter", () => {
  it("keys each TTM point by the quarter it ends with (FR-QT-012)", () => {
    const trend = trendByQuarter([
      { period: "TTM-Q1-FY2026", value: "10", unit: "USD" },
      { period: "TTM-Q2-FY2026", value: "12", unit: "USD" },
    ]);
    expect(trend.get("Q2-FY2026")?.value).toBe("12");
    expect(trend.has("TTM-Q2-FY2026")).toBe(false);
  });
});

describe("axisFor", () => {
  it("gives bars round ticks from zero", () => {
    expect(axisFor([3.4e9, 60.9e9, 215.9e9], true)).toEqual({
      domain: [0, 300e9],
      ticks: [0, 100e9, 200e9, 300e9],
    });
  });

  it("does not spend a whole tick step on one small loss", () => {
    const axis = axisFor([-0.1e9, 33e9, 130.4e9], true);
    expect(axis.ticks).toEqual([0, 50e9, 100e9, 150e9]); // no −50B tick
    expect(axis.domain[0]).toBeLessThan(-0.1e9);
    expect(axis.domain[0]).toBeGreaterThan(-1e9);
  });

  it("keeps a real negative range, with zero as a tick", () => {
    const axis = axisFor([-4.95e9, 6.7e9, 96.7e9], true);
    expect(axis.ticks).toContain(0);
    expect(axis.domain[0]).toBeLessThanOrEqual(-4.95e9);
  });

  it("frames a line of ratios without forcing zero", () => {
    expect(axisFor([0.33, 0.52, 0.75], false)).toEqual({ domain: [0.2, 0.8], ticks: [0.2, 0.4, 0.6, 0.8] });
  });

  it("copes with an empty or flat series", () => {
    expect(axisFor([null, null], true).ticks).toEqual([0, 1]);
    expect(axisFor([5, 5], false).domain[1]).toBeGreaterThan(5);
  });
});

describe("scales and formatting", () => {
  it("picks one scale from the largest magnitude", () => {
    expect(pickScale([4.2e9, 215.9e9, null]).suffix).toBe("B");
    expect(pickScale([-8.1e8, 3e6]).suffix).toBe("M");
    expect(pickScale([]).suffix).toBe("");
  });

  it("knows a margin from a multiple, which the API unit alone does not say", () => {
    expect(displayOf("ratio")).toBe("percent");
    expect(displayOf("ratio", true)).toBe("multiple");
    expect(displayOf("x")).toBe("multiple"); // P/E, EV/EBITDA from the valuation endpoint
    expect(displayOf("USD")).toBe("money");
    expect(displayOf("USD/shares")).toBe("perShare");
    expect(displayOf("shares")).toBe("count");
  });

  it("tables a balance sheet in the unit that keeps small lines readable", () => {
    expect(pickTableScale([4.4e12, 0.4e12]).suffix).toBe("B"); // JPM: 4,424.9, not 4.4
    expect(pickTableScale([215.9e9, 3.4e9]).suffix).toBe("B");
    expect(pickTableScale([4.2e9, 0.3e9]).suffix).toBe("M");
  });

  it("prints axis ticks compactly, by display kind", () => {
    const billions = pickScale([216e9]);
    expect(formatTick(216e9, "money", billions)).toBe("$216B");
    expect(formatTick(-4.95e9, "money", billions)).toBe("−$5B");
    expect(formatTick(0.71, "percent", billions)).toBe("71%");
    expect(formatTick(4.45, "multiple", billions)).toBe("4.5×");
    expect(formatTick(4.9, "perShare", billions)).toBe("$4.90");
    expect(formatTick(24.6e9, "count", billions)).toBe("24.6B");
  });

  it("prints full values for tooltips and stats", () => {
    expect(formatValue(215.938e9, "money")).toBe("$215.94B");
    expect(formatValue(-4.95e9, "money")).toBe("−$4.95B");
    expect(formatValue(0.71068, "percent")).toBe("71.1%");
    expect(formatValue(4.4532, "multiple")).toBe("4.45×");
    expect(formatValue(4.9, "perShare")).toBe("$4.90");
  });

  it("prints table cells in the scale the caption names", () => {
    const billions = pickScale([216e9]);
    expect(formatCell(215.938e9, "money", billions)).toBe("215.9");
    expect(formatCell(-4.95e9, "money", billions)).toBe("−5.0");
    expect(formatCell(-0.03e9, "money", billions)).toBe("0.0"); // never "−0.0"
    expect(formatCell(0.71068, "percent", billions)).toBe("71.1%");
    expect(formatCell(4.4532, "multiple", billions)).toBe("4.45×");
    expect(formatCell(4.9, "perShare", billions)).toBe("4.90");
  });

  it("shortens fiscal period labels for axes", () => {
    expect(shortPeriod("FY2026")).toBe("FY26");
    expect(shortPeriod("Q4-FY2026")).toBe("Q4 FY26");
    expect(shortPeriod("TTM-Q4-FY2026")).toBe("TTM Q4 FY26");
  });
});

// "Show growth" caps (FR-FIN growth view): a bar is the prior period's level plus what it added,
// or its own level with the amount lost outlined above it, on the same axis.
describe("growthSplit", () => {
  it("stacks the amount added on the prior period's level", () => {
    expect(growthSplit(215.9, 130.5)).toEqual({ prior: 130.5, base: 130.5, added: 215.9 - 130.5, lost: null });
  });

  it("outlines the amount lost above a bar that shrank", () => {
    expect(growthSplit(2.94, 11.93)).toEqual({ prior: 11.93, base: 2.94, added: null, lost: 11.93 - 2.94 });
  });

  it("keeps the bar whole with no prior period, or when either period is not positive", () => {
    expect(growthSplit(3.4, null)).toEqual({ prior: null, base: 3.4, added: null, lost: null });
    expect(growthSplit(0.3, -0.1)).toEqual({ prior: -0.1, base: 0.3, added: null, lost: null });
    expect(growthSplit(-0.1, 0.3)).toEqual({ prior: 0.3, base: -0.1, added: null, lost: null });
    expect(growthSplit(null, 4)).toEqual({ prior: 4, base: null, added: null, lost: null });
  });

  it("adds nothing when the value is unchanged", () => {
    expect(growthSplit(5, 5)).toEqual({ prior: 5, base: 5, added: null, lost: null });
  });
});
