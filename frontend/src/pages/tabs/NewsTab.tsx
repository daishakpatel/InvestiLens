import { useParams } from "react-router-dom";

import { AsyncContent, Panel } from "../../components/Panel";
import { Badge } from "../../components/primitives";
import { formatDate } from "../../lib/format";
import { useNews } from "../../lib/queries";

export default function NewsTab() {
  const { ticker = "" } = useParams();
  const news = useNews(ticker);

  return (
    <Panel title="News" freshness={news.data?.freshness}>
      <AsyncContent
        query={news}
        isEmpty={(d) => d.items.length === 0}
        emptyMessage="No recent news for this company."
      >
        {(data) => (
          <ul className="divide-y divide-border">
            {data.items.map((n) => (
              <li key={n.news_id} className="px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <a
                    href={n.url ?? "#"}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-sm font-medium hover:underline"
                  >
                    {n.title}
                  </a>
                  {n.category && <Badge tone="neutral">{n.category}</Badge>}
                </div>
                <div className="mt-1 text-xs text-muted">
                  {n.publisher ?? "Unknown"} · {formatDate(n.published_at)}
                </div>
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
      <p className="px-4 py-2 text-xs text-muted">
        Clustered view, source-tier badges, and relevance filters arrive in Phase 4d.
      </p>
    </Panel>
  );
}
