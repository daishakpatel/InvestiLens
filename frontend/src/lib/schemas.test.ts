import { describe, expect, it } from "vitest";

import { parse } from "./schemas";

// UI-001: every response is validated at runtime; a malformed payload must fail fast and loudly
// rather than flowing into the UI as `undefined`.
describe("parse.searchResults", () => {
  it("accepts a well-formed search payload", () => {
    const out = parse.searchResults([
      { ticker: "NVDA", cik: "0001045810", name: "NVIDIA", exchange: "NASDAQ", score: 0.9 },
    ]);
    expect(out[0]?.ticker).toBe("NVDA");
  });

  it("throws on a malformed payload (wrong types)", () => {
    expect(() => parse.searchResults([{ ticker: 1, score: "high" }])).toThrow();
    expect(() => parse.searchResults({ not: "an array" })).toThrow();
  });
});

describe("parse.news", () => {
  it("passes through tier and cluster_id (Phase 4d news fields)", () => {
    const out = parse.news({
      ticker: "NVDA",
      items: [{ news_id: "1", title: "Headline", tier: 4, cluster_id: "c1" }],
      freshness: { as_of: "2026-10-06T00:00:00Z", source: "news", freshness_status: "fresh" },
    });
    expect(out.items[0]?.tier).toBe(4);
    expect(out.items[0]?.cluster_id).toBe("c1");
  });

  it("rejects an unknown freshness_status", () => {
    expect(() =>
      parse.news({
        ticker: "NVDA",
        items: [],
        freshness: { as_of: "x", source: "news", freshness_status: "exploded" },
      }),
    ).toThrow();
  });
});

describe("parse.filingDiff", () => {
  const filing = { filing_id: "2", filing_type: "10-K", accession_number: "a-2" };
  const payload = {
    company_ticker: "NVDA",
    filing,
    against: { ...filing, filing_id: "1" },
    similarity_method: "lexical",
    caption_detection: "emphasis",
    counts: { unchanged: 0, reworded: 1, new: 0, removed: 0 },
    items: [
      {
        section: "Item 1A",
        kind: "risk_factor",
        status: "reworded",
        decided_by: "heading",
        similarity: 0.9,
        old: { heading: "H", source_ids: ["1_1A_0"] },
        new: { heading: "H", source_ids: ["2_1A_0"] },
        word_diff: [{ op: "insert", text: "more" }],
      },
    ],
  };

  it("keeps both filings' source ids on a diff item (CIT-001)", () => {
    const item = parse.filingDiff(payload).items[0];
    expect(item?.old?.source_ids).toEqual(["1_1A_0"]);
    expect(item?.new?.source_ids).toEqual(["2_1A_0"]);
  });

  it("rejects an unknown change status", () => {
    const bad = { ...payload, items: [{ ...payload.items[0], status: "tweaked" }] };
    expect(() => parse.filingDiff(bad)).toThrow();
  });
});
