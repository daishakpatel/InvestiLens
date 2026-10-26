import { describe, expect, it } from "vitest";

import { evidenceHref } from "./alertEvidence";

describe("notification evidence links (FR-AL-018)", () => {
  it("opens the filing, the news tab, or the company page", () => {
    expect(evidenceHref({ ticker: "NVDA", source_ids: ["filing:15", "1_12"] })).toBe("/company/NVDA/filings?filing=15");
    expect(evidenceHref({ ticker: "NVDA", source_ids: ["news:9"] })).toBe("/company/NVDA/news");
    expect(evidenceHref({ ticker: "NVDA", source_ids: ["price:NVDA:2026-01-14:2026-01-15"] })).toBe("/company/NVDA");
  });

  it("opens a ready brief on the Earnings tab (FR-EB-009)", () => {
    expect(evidenceHref({ ticker: "NVDA", source_ids: ["earnings_brief:42"] })).toBe("/company/NVDA/earnings?brief=42");
  });

  it("has nowhere to go without a company", () => {
    expect(evidenceHref({ ticker: null, source_ids: ["filing:1"] })).toBeNull();
  });
});
