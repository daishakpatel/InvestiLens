import { describe, expect, it } from "vitest";

import { activeFilterCount, filterNews, groupByDay, NO_FILTERS, toStories } from "./newsFeed";
import type { NewsItem } from "../types";

const item = (over: Partial<NewsItem> & { news_id: string }): NewsItem => ({
  title: `Headline ${over.news_id}`,
  ...over,
});

// §10.8 news panel: event clustering ("N sources"), newest first, filters. LGL-004: headlines only.
describe("toStories", () => {
  it("collapses a cluster into one story led by its best-sourced report (§15 tiers)", () => {
    const stories = toStories([
      item({ news_id: "1", cluster_id: "evt", tier: 5, published_at: "2026-09-22T10:00:00Z" }),
      item({ news_id: "2", cluster_id: "evt", tier: 4, published_at: "2026-09-22T08:00:00Z" }),
      item({ news_id: "3", published_at: "2026-09-23T09:00:00Z" }),
    ]);
    expect(stories.map((s) => s.lead.news_id)).toEqual(["3", "2"]); // newest story first
    expect(stories[1]?.others.map((o) => o.news_id)).toEqual(["1"]);
  });

  it("keeps unclustered items separate, and copes with undated ones", () => {
    const stories = toStories([item({ news_id: "a" }), item({ news_id: "b" })]);
    expect(stories).toHaveLength(2);
    expect(stories.every((s) => s.others.length === 0)).toBe(true);
  });
});

describe("groupByDay", () => {
  it("puts stories under day headings, newest day first and undated last", () => {
    const groups = groupByDay(
      toStories([
        item({ news_id: "old", published_at: "2026-09-20T15:00:00Z" }),
        item({ news_id: "undated" }),
        item({ news_id: "new", published_at: "2026-09-22T15:00:00Z" }),
      ]),
    );
    expect(groups.map((g) => g.stories[0]?.lead.news_id)).toEqual(["new", "old", "undated"]);
    expect(groups.at(-1)?.day).toBe("");
  });
});

describe("filters", () => {
  const items = [
    item({ news_id: "1", category: "Earnings", publisher: "A", relevance_score: 0.9 }),
    item({ news_id: "2", category: "Legal", publisher: "B", relevance_score: 0.2 }),
    item({ news_id: "3", category: "Earnings", publisher: "B" }), // no score counts as 0
  ];

  it("apply category, publisher, and minimum relevance together", () => {
    expect(filterNews(items, NO_FILTERS)).toHaveLength(3);
    expect(filterNews(items, { ...NO_FILTERS, category: "Earnings" }).map((i) => i.news_id)).toEqual(["1", "3"]);
    expect(
      filterNews(items, { category: "Earnings", publisher: "B", minRelevance: 0.5 }),
    ).toEqual([]);
  });

  it("count how many are active, for the Filter button", () => {
    expect(activeFilterCount(NO_FILTERS)).toBe(0);
    expect(activeFilterCount({ category: "Earnings", publisher: "", minRelevance: 0.4 })).toBe(2);
  });
});
