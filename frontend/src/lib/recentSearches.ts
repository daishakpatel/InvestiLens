// Recent searches, persisted per-browser (no PII, no secrets — a convenience only, §9.1).
const KEY = "il-recent-searches";
const MAX = 6;

export interface RecentSearch {
  ticker: string;
  name: string;
}

export function getRecentSearches(): RecentSearch[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? (parsed as RecentSearch[]).slice(0, MAX) : [];
  } catch {
    return [];
  }
}

export function addRecentSearch(entry: RecentSearch): void {
  try {
    const existing = getRecentSearches().filter((e) => e.ticker !== entry.ticker);
    localStorage.setItem(KEY, JSON.stringify([entry, ...existing].slice(0, MAX)));
  } catch {
    // Storage unavailable (private mode) — recents are best-effort.
  }
}
