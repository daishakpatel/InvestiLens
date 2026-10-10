// What-if recompute math (§37.2 item 10): weight changes recompute aggregates client-side,
// matching the backend formulas (ADR-0026), with no backend round-trip.
import { describe, expect, it } from "vitest";

import { normalizeWeights, recompute } from "./portfolioRecompute";
import type { HoldingData, RiskStats } from "../types";

const holdings: HoldingData[] = [
  {
    ticker: "A",
    sector: "Technology",
    metrics: { gross_margin: mr("0.70"), net_margin: mr("0.50") },
    annualized_volatility: "0.20",
  },
  {
    ticker: "B",
    sector: "Technology",
    metrics: { gross_margin: mr("0.40"), net_margin: mr("0.10") },
    annualized_volatility: "0.30",
  },
  {
    // A "bank" with no gross margin → excluded from that weighted metric (partial coverage).
    ticker: "C",
    sector: "Financials",
    metrics: { net_margin: mr("0.30") },
    annualized_volatility: "0.10",
  },
] as HoldingData[];

const correlation: RiskStats["correlation"] = [
  { ticker: "A", correlations: { A: "1", B: "0", C: "0" } },
  { ticker: "B", correlations: { A: "0", B: "1", C: "0" } },
  { ticker: "C", correlations: { A: "0", B: "0", C: "1" } },
];

function mr(value: string): HoldingData["metrics"][string] {
  return { value, unit: "ratio", inputs: [], formula_id: "x", warnings: [] } as HoldingData["metrics"][string];
}

describe("normalizeWeights", () => {
  it("scales to sum to 1", () => {
    const w = normalizeWeights({ A: 30, B: 70 });
    expect(w.A ?? 0).toBeCloseTo(0.3, 10);
    expect((w.A ?? 0) + (w.B ?? 0)).toBeCloseTo(1, 10);
  });
});

describe("recompute", () => {
  it("weights equal thirds → HHI 1/3 and effective holdings 3", () => {
    const r = recompute(holdings, { A: 1, B: 1, C: 1 }, correlation);
    expect(r.hhi).toBeCloseTo(1 / 3, 10);
    expect(r.effectiveHoldings).toBeCloseTo(3, 6);
  });

  it("renormalizes a weighted metric over covered holdings", () => {
    const r = recompute(holdings, { A: 1, B: 1, C: 1 }, correlation);
    const gm = r.weightedMetrics.find((m) => m.metricName === "gross_margin");
    // C has no gross margin → coverage 2/3, value = (0.70 + 0.40)/2 = 0.55.
    expect(gm?.coverage).toBeCloseTo(2 / 3, 10);
    expect(gm?.value ?? NaN).toBeCloseTo(0.55, 10);
  });

  it("sector exposure sums by sector, largest first", () => {
    const r = recompute(holdings, { A: 2, B: 2, C: 1 }, correlation);
    expect(r.sectorExposure[0]).toEqual({ sector: "Technology", weight: 0.8 });
    expect(r.sectorExposure[1]).toEqual({ sector: "Financials", weight: 0.2 });
  });

  it("recomputes portfolio volatility from vols + correlation (uncorrelated case)", () => {
    const r = recompute(holdings, { A: 1, B: 0, C: 0 }, correlation);
    expect(r.portfolioVolatility).toBeCloseTo(0.2, 10); // all weight on A → its own vol
  });

  it("changing weights changes the result (live what-if, no round-trip)", () => {
    const even = recompute(holdings, { A: 1, B: 1, C: 1 }, correlation);
    const tilted = recompute(holdings, { A: 8, B: 1, C: 1 }, correlation);
    expect(tilted.hhi).toBeGreaterThan(even.hhi); // more concentrated
    const gmEven = even.weightedMetrics.find((m) => m.metricName === "net_margin")?.value ?? NaN;
    const gmTilted = tilted.weightedMetrics.find((m) => m.metricName === "net_margin")?.value ?? NaN;
    expect(gmTilted).toBeGreaterThan(gmEven); // tilts toward A's higher margin
  });
});
