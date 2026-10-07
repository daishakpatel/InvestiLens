import { describe, expect, it } from "vitest";

import { formatMetricValue, formatPercent, toCsv, toNumber } from "./format";

describe("toNumber", () => {
  it("parses decimal strings and rejects non-numbers", () => {
    expect(toNumber("123.45")).toBe(123.45);
    expect(toNumber(null)).toBeNull();
    expect(toNumber("")).toBeNull();
    expect(toNumber("not-a-number")).toBeNull();
  });
});

describe("formatPercent (ratio → percent unit conversion)", () => {
  it("scales a ratio by 100 and keeps the N/A sentinel", () => {
    expect(formatPercent("0.1234")).toBe("12.3%");
    expect(formatPercent(0.5, 0)).toBe("50%");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("formatMetricValue (unit-aware rendering)", () => {
  it("renders by unit and never prints 0 for a null value", () => {
    expect(formatMetricValue("1500000000", "usd")).toMatch(/^\$/); // compact money
    expect(formatMetricValue("0.71", "ratio")).toBe("71.0%");
    expect(formatMetricValue("12000000", "shares")).toBe("12,000,000");
    expect(formatMetricValue(null, "usd")).toBe("—"); // N/A stays N/A, DR-041
  });
});

describe("toCsv", () => {
  it("escapes commas, quotes, and newlines (FR-013 export)", () => {
    const csv = toCsv(["a", "b"], [["x,y", 'has "quote"']]);
    expect(csv).toBe('a,b\n"x,y","has ""quote"""');
  });
});
