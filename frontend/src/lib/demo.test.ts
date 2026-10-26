import { describe, expect, it } from "vitest";

import { demoBannerText, RISK_QUESTION, SCENARIOS } from "./demo";

describe("demo banner and guided path (NFR-ME-007, NFR-ME-010)", () => {
  it("names the fixture date and the disclaimer", () => {
    expect(demoBannerText("2026-05-28")).toMatch(/^Demo: fixture data as of .+2026\. Not investment advice\.$/);
    expect(demoBannerText(null)).toBe("Demo: fixture data. Not investment advice.");
  });

  it("offers exactly three scenarios, each an in-app path", () => {
    expect(SCENARIOS).toHaveLength(3);
    for (const scenario of SCENARIOS) expect(scenario.to.startsWith("/company/NVDA")).toBe(true);
    expect(SCENARIOS[1]?.to).toContain(encodeURIComponent(RISK_QUESTION));
  });
});
