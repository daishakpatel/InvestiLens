import { describe, expect, it } from "vitest";

import { latestQuote } from "./quote";

// §9.4 dashboard header: the last close and its day change come from the two newest sessions.
describe("latestQuote", () => {
  it("returns the last close and the change vs the prior session", () => {
    const quote = latestQuote([
      { date: "2026-09-28", close: "90.00" },
      { date: "2026-09-29", close: "100.00" },
      { date: "2026-09-30", close: "104.00" },
    ]);
    expect(quote).toEqual({ close: 104, changePct: 0.04, date: "2026-09-30" });
  });

  it("has no change with a single session, and no quote with no usable close (never 0)", () => {
    expect(latestQuote([{ date: "2026-09-30", close: "104.00" }])?.changePct).toBeNull();
    expect(latestQuote([])).toBeNull();
    expect(latestQuote(undefined)).toBeNull();
    expect(latestQuote([{ date: "2026-09-30", close: null }])).toBeNull();
  });
});
