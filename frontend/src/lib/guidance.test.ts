// FR-GD-012/014/015/016: guidance display helpers. No characterisation words in any UI copy.
import { describe, expect, it } from "vitest";

import type { GuidanceRow, GuidanceValue, TrackRecordQuarter } from "../types";
import { BASIS_LABEL, EMPTY_TEXT, RESULT_LABEL, deltaText, dotPlot, guidedText, isCompared, revisionText } from "./guidance";

const OUTCOME: NonNullable<GuidanceValue["outcome"]> = {
  result: "above_range",
  actual_value: "112000000000",
  actual_source_ids: ["xbrl:NVDA:revenue:Q3-FY2027"],
  delta_vs_low: "6160000000",
  delta_vs_high: "1840000000",
  delta_vs_mid: "4000000000",
  delta_vs_mid_pct: "0.037037",
  reason_code: null,
  explanation: null,
  computed_at: "2026-11-20T00:00:00Z",
};

const value = (over: Partial<GuidanceValue> = {}): GuidanceValue => ({
  id: 1,
  issued_at: "2026-08-26T20:20:00Z",
  low: "105840000000",
  high: "110160000000",
  point: null,
  midpoint: "108000000000",
  derived_range: true,
  quote: "Revenue is expected to be $108.0 billion, plus or minus 2%",
  source_id: "2716_0_5",
  release: { document_id: 2716, title: "NVDA 8-K EX-99.1", url: null },
  outcome: OUTCOME,
  ...over,
});

const row = (over: Partial<GuidanceRow> = {}): GuidanceRow => ({
  ...value(),
  fiscal_year: 2027,
  fiscal_period: "Q3",
  period_label: "Q3 FY2027",
  metric: "revenue",
  metric_label: "Revenue",
  basis: "unspecified",
  unit: "usd",
  revisions: [],
  ...over,
});

describe("guidance text", () => {
  it("prints ranges, single figures and margins in their units", () => {
    expect(guidedText(row(), value())).toBe("$105.84B–$110.16B");
    const eps = row({ metric: "eps_gaap" });
    expect(guidedText(eps, value({ low: null, high: null, point: "1.25" }))).toBe("$1.25");
    const margin = row({ metric: "gross_margin", unit: "ratio" });
    expect(guidedText(margin, value({ low: "0.735", high: "0.745" }))).toBe("73.5%–74.5%");
  });

  it("states the delta from the midpoint, in points for a ratio", () => {
    expect(deltaText(row(), value())).toBe("+3.7%");
    const below = value({ outcome: { ...OUTCOME, delta_vs_mid_pct: "-0.05" } });
    expect(deltaText(row(), below)).toBe("−5.0%");
    const margin = row({ unit: "ratio" });
    const ratio = value({ outcome: { ...OUTCOME, delta_vs_mid: "0.004" } });
    expect(deltaText(margin, ratio)).toBe("+0.4 pts");
    const missing = value({ outcome: { ...OUTCOME, delta_vs_mid: null, delta_vs_mid_pct: null } });
    expect(deltaText(row(), missing)).toBeNull();
    expect(deltaText(margin, missing)).toBeNull();
  });

  it("gives non-comparable and unreported rows no delta (FR-GD-016)", () => {
    const notComparable = value({
      outcome: { ...OUTCOME, result: "not_comparable", explanation: "Guided on a non-GAAP basis; GAAP actual not comparable." },
    });
    expect(deltaText(row(), notComparable)).toBeNull();
    expect(deltaText(row(), value({ outcome: null }))).toBeNull();
    expect(isCompared("not_comparable")).toBe(false);
    expect(isCompared("below_range")).toBe(true);
  });

  it("lists revisions with their release date", () => {
    expect(revisionText(row(), value({ issued_at: "2026-11-19T21:00:00Z" }))).toBe("Revised 2026-11-19: $105.84B–$110.16B");
    expect(revisionText(row(), value({ issued_at: null }))).toMatch(/^Revised date unknown/);
  });

  it("never characterises how a company guides", () => {
    const copy = [...Object.values(RESULT_LABEL), ...Object.values(BASIS_LABEL), EMPTY_TEXT].join(" ");
    expect(copy).not.toMatch(/sandbag|conservative|aggressive|reliab|credib|lowball|beat/i);
  });
});

describe("dotPlot", () => {
  const quarter = (label: string, low: string, high: string, actual: string | null): TrackRecordQuarter => ({
    period_label: label,
    low,
    high,
    actual_value: actual,
    result: actual === null ? "actual_unavailable" : "above_range",
    delta_vs_mid_pct: null,
    source_id: label,
  });

  it("puts every quarter on one symmetric axis, oldest first", () => {
    const plot = dotPlot([quarter("Q2", "98", "102", "110"), quarter("Q1", "49", "51", "50"), quarter("Q0", "0", "0", "1")]);
    expect(plot.extent).toBe(0.11); // 10% above midpoint, plus a margin
    expect(plot.quarters.map((q) => q.label)).toEqual(["Q1", "Q2"]); // zero midpoint dropped
    const [q1, q2] = plot.quarters;
    expect(q1?.actual).toBeCloseTo(50);
    expect(q2?.rangeStart).toBeCloseTo(((-0.02 + 0.11) / 0.22) * 100);
    expect(q2?.actualPct).toBeCloseTo(0.1);
    const pending = dotPlot([quarter("Q3", "98", "102", null)]);
    expect(pending.quarters[0]?.actual).toBeNull();
    expect(pending.extent).toBe(0.03);
  });
});
