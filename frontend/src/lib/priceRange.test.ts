import { describe, expect, it } from "vitest";

import { availableRanges, rangeChange, sliceRange, toBars } from "./priceRange";
import type { PriceBar } from "./priceRange";

/** One bar per calendar day from `start`, `days` long, price rising 1 per day. */
function daily(start: string, days: number): PriceBar[] {
  const t0 = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: days }, (_, i) => ({
    date: new Date(t0 + i * 86_400_000).toISOString().slice(0, 10),
    close: 100 + i,
    adj: 100 + i,
  }));
}

// UI plan Step 3 (price hero): ranges are sliced client-side, and only real ranges are offered.
describe("toBars", () => {
  it("drops days with no close and falls back to the raw close when unadjusted (DR-025)", () => {
    const bars = toBars([
      { date: "2026-01-02", close: "10.00", adj_close: "1.00" },
      { date: "2026-01-03", close: null, adj_close: "1.10" },
      { date: "2026-01-04", close: "12.00", adj_close: null },
    ]);
    expect(bars).toEqual([
      { date: "2026-01-02", close: 10, adj: 1 },
      { date: "2026-01-04", close: 12, adj: 12 },
    ]);
    expect(toBars(undefined)).toEqual([]);
  });
});

describe("sliceRange", () => {
  it("keeps the bars within N months of the latest bar", () => {
    const bars = daily("2025-01-01", 500); // ends 2026-05-15
    const month = sliceRange(bars, 1);
    expect(month[0]?.date).toBe("2026-04-15");
    expect(month.at(-1)?.date).toBe("2026-05-15");
    expect(sliceRange([], 12)).toEqual([]);
  });
});

describe("availableRanges", () => {
  it("offers only ranges the data can fill", () => {
    expect(availableRanges(daily("2026-01-01", 100))).toEqual(["1M", "3M"]);
    expect(availableRanges(daily("2021-01-01", 2000))).toEqual(["1M", "3M", "6M", "1Y", "5Y"]);
  });

  it("still offers a range the data is only a few days short of", () => {
    // 2021-10-01 → 2026-09-30 is one day short of five years (the dev price fixture).
    expect(availableRanges(daily("2021-10-01", 1826))).toContain("5Y");
  });

  it("offers nothing for an empty or single-bar series", () => {
    expect(availableRanges([])).toEqual([]);
    expect(availableRanges(daily("2026-01-01", 1))).toEqual([]);
  });
});

describe("rangeChange", () => {
  it("measures on adjusted closes, so a split is not a crash (DR-025)", () => {
    const bars: PriceBar[] = [
      { date: "2024-06-07", close: 1000, adj: 100 }, // before a 10:1 split
      { date: "2024-06-10", close: 110, adj: 110 },
    ];
    expect(rangeChange(bars)).toEqual({ abs: 10, pct: 0.1 });
  });

  it("can measure to any bar (scrubbing) and has no percentage on a non-positive open", () => {
    const bars = daily("2026-01-01", 11);
    expect(rangeChange(bars, 5)).toEqual({ abs: 5, pct: 0.05 });
    expect(rangeChange([{ date: "a", close: 0, adj: 0 }, { date: "b", close: 1, adj: 1 }])?.pct).toBeNull();
    expect(rangeChange([])).toBeNull();
  });
});
