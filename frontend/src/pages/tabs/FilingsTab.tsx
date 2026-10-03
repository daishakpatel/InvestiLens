import { useParams } from "react-router-dom";

import { AsyncContent, Panel } from "../../components/Panel";
import { Badge } from "../../components/primitives";
import { formatDate } from "../../lib/format";
import { useFilings } from "../../lib/queries";

export default function FilingsTab() {
  const { ticker = "" } = useParams();
  const filings = useFilings(ticker);

  return (
    <Panel title="SEC filings">
      <AsyncContent
        query={filings}
        isEmpty={(d) => d.length === 0}
        emptyMessage="No filings ingested for this company yet."
      >
        {(data) => (
          <ul className="divide-y divide-border">
            {data.map((f) => (
              <li key={f.filing_id} className="flex items-center justify-between gap-4 px-4 py-3">
                <div className="flex items-center gap-3">
                  <Badge tone="data">{f.filing_type}</Badge>
                  <span className="text-sm">
                    Filed {formatDate(f.filing_date)}
                    {f.period_end ? ` · period ${formatDate(f.period_end)}` : ""}
                  </span>
                </div>
                {f.primary_document_url && (
                  <a
                    href={f.primary_document_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="text-sm text-primary hover:underline"
                  >
                    View ↗
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </AsyncContent>
      <p className="px-4 py-2 text-xs text-muted">
        In-filing search and a section-navigable viewer arrive in Phase 4d.
      </p>
    </Panel>
  );
}
