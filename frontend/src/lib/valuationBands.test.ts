import { describe, expect, it } from "vitest";

import type { ValuationBand } from "../types";
import { bandGeometry, bandSummary, bandValue, multipleLabel } from "./valuationBands";

const band = (over: Partial<ValuationBand> = {}): ValuationBand => ({
  multiple: "pe_ratio",
  unit: "x",
  status: "ok",
  value: "30",
  reason: null,
  own: { n: 6, min: "20", median: "40", max: "60", percentile: "0.33", label: "in the middle half of its 5-year range", reason: null },
  peers: { n: 4, median: "25", percentile: "0.5", premium_to_peer_median: "0.2", label: "20% above peer median", reason: null, excluded: [] },
  history: [],
  ...over,
});

describe("valuation bands (FR-PS-014)", () => {
  it("formats multiples with × and yields as %", () => {
    expect(bandValue("26.36", "x")).toBe("26.4×");
    expect(bandValue("0.0438", "ratio")).toBe("4.4%");
    expect(bandValue(null, "x")).toBe("—");
    expect(multipleLabel("ev_ebitda")).toBe("EV/EBITDA");
    expect(multipleLabel("other")).toBe("other");
  });

  it("places range, today and the peer median on one scale", () => {
    const g = bandGeometry(band());
    expect(g).not.toBeNull();
    if (!g) return;
    expect(g.rangeStart).toBeLessThan(g.today);
    expect(g.today).toBeLessThan(g.rangeEnd);
    expect(g.peerMedian).not.toBeNull();
    expect((g.peerMedian ?? Infinity) < g.today).toBe(true);
    const noPeers = bandGeometry(band({ peers: { ...band().peers, median: null } }));
    expect(noPeers?.peerMedian).toBeNull();
    const flat = bandGeometry(band({ value: "5", own: { ...band().own, min: "5", max: "5" }, peers: { ...band().peers, median: null } }));
    expect(flat?.today).toBe(50);
  });

  it("draws nothing for a value that is not meaningful or has no range", () => {
    expect(bandGeometry(band({ status: "not_meaningful", value: null }))).toBeNull();
    expect(bandGeometry(band({ own: { ...band().own, min: null, max: null } }))).toBeNull();
  });

  it("summarises positions with sample sizes, or the reasons", () => {
    expect(bandSummary(band())).toBe(
      "in the middle half of its 5-year range (n=6) · 20% above peer median (n=4)",
    );
    const short = band({
      own: { n: 2, label: null, reason: "Insufficient history: 1 fiscal year ends with a value (3 needed for a band)." },
      peers: { n: 0, label: null, reason: "Insufficient peers: the peer set has fewer than three companies.", excluded: [] },
    });
    expect(bandSummary(short)).toContain("Insufficient history");
    expect(bandSummary(short)).toContain("Insufficient peers");
    for (const text of [bandSummary(band()), bandSummary(short)]) {
      expect(text).not.toMatch(/cheap|expensive|undervalued|overvalued|bargain/i);
    }
  });
});

describe("band summary without repeats", () => {
  it("drops the reason already shown in place of the bar", () => {
    const b = band({ status: "ok", own: { n: 3, label: null, reason: "Insufficient history: x." } });
    expect(bandSummary(b, "Insufficient history: x.")).toBe("20% above peer median (n=4)");
  });
});
