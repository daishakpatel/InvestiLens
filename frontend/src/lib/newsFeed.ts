// Shaping the news list into a feed (§10.8): stories about the same event collapse into one
// entry, entries are newest first, and the feed is grouped under day headings.
import type { NewsItem } from "../types";

export interface Story {
  key: string;
  lead: NewsItem;
  others: NewsItem[]; // the same event from other outlets
}

export interface NewsFilters {
  category: string; // "" = any
  publisher: string; // "" = any
  minRelevance: number; // 0 = any
}

export const NO_FILTERS: NewsFilters = { category: "", publisher: "", minRelevance: 0 };

export function activeFilterCount(filters: NewsFilters): number {
  return Number(filters.category !== "") + Number(filters.publisher !== "") + Number(filters.minRelevance > 0);
}

export function filterNews(items: readonly NewsItem[], filters: NewsFilters): NewsItem[] {
  return items.filter(
    (item) =>
      (!filters.category || item.category === filters.category) &&
      (!filters.publisher || item.publisher === filters.publisher) &&
      (item.relevance_score ?? 0) >= filters.minRelevance,
  );
}

const time = (item: NewsItem) => (item.published_at ? Date.parse(item.published_at) || 0 : 0);

/** Group items by event cluster. The lead is the best-sourced report of the event (lowest tier
 *  number, §15), then the most recent; items without a cluster stand alone. Newest story first. */
export function toStories(items: readonly NewsItem[]): Story[] {
  const groups = new Map<string, NewsItem[]>();
  for (const item of items) {
    const key = item.cluster_id ?? `solo:${item.news_id}`;
    const group = groups.get(key);
    if (group) group.push(item);
    else groups.set(key, [item]);
  }
  const stories: Story[] = [];
  for (const [key, group] of groups) {
    const ranked = [...group].sort((a, b) => (a.tier ?? 9) - (b.tier ?? 9) || time(b) - time(a));
    const [lead, ...others] = ranked;
    if (lead) stories.push({ key, lead, others });
  }
  return stories.sort((a, b) => time(b.lead) - time(a.lead));
}

/** The local calendar day a story was published, as a sortable key; "" when undated. */
function dayKey(item: NewsItem): string {
  if (!item.published_at) return "";
  const date = new Date(item.published_at);
  if (Number.isNaN(date.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Stories under day headings, newest day first; undated stories last. */
export function groupByDay(stories: readonly Story[]): { day: string; stories: Story[] }[] {
  const days = new Map<string, Story[]>();
  for (const story of stories) {
    const key = dayKey(story.lead);
    const list = days.get(key);
    if (list) list.push(story);
    else days.set(key, [story]);
  }
  return [...days.entries()]
    .sort(([a], [b]) => (a === "" ? 1 : b === "" ? -1 : b.localeCompare(a)))
    .map(([day, list]) => ({ day, stories: list }));
}
