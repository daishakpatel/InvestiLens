import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { AsyncContent, Panel } from "../../components/Panel";
import { Badge } from "../../components/primitives";
import { formatDate, formatPercent } from "../../lib/format";
import { useNews } from "../../lib/queries";
import type { NewsItem } from "../../types";

interface Cluster {
  key: string;
  items: NewsItem[];
}

function cluster(items: NewsItem[]): Cluster[] {
  const groups = new Map<string, NewsItem[]>();
  for (const it of items) {
    // Items without a cluster id are their own singleton (keyed by news_id).
    const key = it.cluster_id ?? `solo:${it.news_id}`;
    const list = groups.get(key);
    if (list) list.push(it);
    else groups.set(key, [it]);
  }
  return [...groups.entries()].map(([key, group]) => ({ key, items: group }));
}

export default function NewsTab() {
  const { ticker = "" } = useParams();
  const news = useNews(ticker);
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [minRel, setMinRel] = useState(0);

  const items = useMemo(() => news.data?.items ?? [], [news.data]);
  const categories = useMemo(
    () => [...new Set(items.map((i) => i.category).filter((c): c is string => Boolean(c)))].sort(),
    [items],
  );
  const sources = useMemo(
    () => [...new Set(items.map((i) => i.publisher).filter((p): p is string => Boolean(p)))].sort(),
    [items],
  );

  const filtered = items.filter(
    (i) =>
      (!category || i.category === category) &&
      (!source || i.publisher === source) &&
      (i.relevance_score ?? 0) >= minRel,
  );
  const clusters = cluster(filtered);

  return (
    <Panel
      title="News"
      freshness={news.data?.freshness}
      actions={
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <select
            aria-label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1"
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            aria-label="Source"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="rounded-md border border-border bg-surface px-2 py-1"
          >
            <option value="">All sources</option>
            {sources.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1">
            Relevance ≥ {minRel.toFixed(1)}
            <input
              type="range"
              min={0}
              max={1}
              step={0.1}
              value={minRel}
              onChange={(e) => setMinRel(Number(e.target.value))}
              aria-label="Minimum relevance"
            />
          </label>
        </div>
      }
    >
      <AsyncContent
        query={news}
        isEmpty={() => filtered.length === 0}
        emptyMessage="No news matches these filters."
      >
        {() => (
          <ul className="divide-y divide-border">
            {clusters.map((c) => (
              <li key={c.key} className="px-4 py-3">
                <ClusterItem items={c.items} />
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
    </Panel>
  );
}

function tierTone(tier: number | null | undefined): "positive" | "neutral" {
  return tier != null && tier <= 4 ? "positive" : "neutral";
}

function ClusterItem({ items }: { items: NewsItem[] }) {
  const lead = items[0];
  if (!lead) return null;
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <a
          href={lead.url ?? "#"}
          target="_blank"
          rel="noreferrer noopener"
          className="text-sm font-medium hover:underline"
        >
          {lead.title}
        </a>
        <div className="flex shrink-0 items-center gap-1">
          {items.length > 1 && <Badge tone="data">{items.length} sources</Badge>}
          {lead.category && <Badge tone="neutral">{lead.category}</Badge>}
          {lead.tier != null && <Badge tone={tierTone(lead.tier)}>Tier {lead.tier}</Badge>}
        </div>
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{lead.publisher ?? "Unknown"}</span>
        <span>· {formatDate(lead.published_at)}</span>
        {lead.relevance_score != null && <span>· relevance {formatPercent(lead.relevance_score, 0)}</span>}
      </div>
      {items.length > 1 && (
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted">
          Also reported by:
          {items.slice(1).map((i) => (
            <a
              key={i.news_id}
              href={i.url ?? "#"}
              target="_blank"
              rel="noreferrer noopener"
              className="hover:underline"
            >
              {i.publisher ?? "source"}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
