import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { AsyncContent, Panel } from "../../components/Panel";
import { Badge, EmptyState, LoadingState } from "../../components/primitives";
import { formatDate } from "../../lib/format";
import { useFilings, useFilingSections } from "../../lib/queries";
import type { FilingSummary } from "../../types";

export default function FilingsTab() {
  const { ticker = "" } = useParams();
  const filings = useFilings(ticker);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<FilingSummary | null>(null);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
      <Panel title="SEC filings">
        <AsyncContent query={filings} isEmpty={(d) => d.length === 0} emptyMessage="No filings ingested.">
          {(data) => (
            <div>
              <div className="p-2">
                <input
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  aria-label="Filter filings"
                  placeholder="Filter by type or date…"
                  className="w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm"
                />
              </div>
              <ul className="max-h-[28rem] divide-y divide-border overflow-auto">
                {data
                  .filter((f) =>
                    `${f.filing_type} ${f.filing_date ?? ""} ${f.accession_number}`
                      .toLowerCase()
                      .includes(query.toLowerCase()),
                  )
                  .map((f) => (
                    <li key={f.filing_id}>
                      <button
                        type="button"
                        aria-pressed={selected?.filing_id === f.filing_id}
                        onClick={() => setSelected(f)}
                        className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-surface-2 ${
                          selected?.filing_id === f.filing_id ? "bg-surface-2" : ""
                        }`}
                      >
                        <Badge tone="data">{f.filing_type}</Badge>
                        <span className="text-muted">{formatDate(f.filing_date)}</span>
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </AsyncContent>
      </Panel>

      {selected ? (
        <FilingViewer filing={selected} />
      ) : (
        <Panel title="Filing viewer">
          <EmptyState message="Select a filing to view its sections." />
        </Panel>
      )}
    </div>
  );
}

function FilingViewer({ filing }: { filing: FilingSummary }) {
  const sections = useFilingSections(filing.filing_id);
  const [term, setTerm] = useState("");

  const filtered = useMemo(() => {
    const items = sections.data?.sections ?? [];
    const t = term.trim().toLowerCase();
    if (!t) return items;
    return items.filter((s) => `${s.title} ${s.section_path.join(" ")}`.toLowerCase().includes(t));
  }, [sections.data, term]);

  return (
    <Panel
      title={`${filing.filing_type} · ${formatDate(filing.filing_date)}`}
      actions={
        filing.primary_document_url ? (
          <a
            href={filing.primary_document_url}
            target="_blank"
            rel="noreferrer noopener"
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2"
          >
            Open original ↗
          </a>
        ) : undefined
      }
    >
      <div className="p-3">
        <input
          type="search"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          aria-label="Search within filing sections"
          placeholder="Search sections (Item 1A, risk, revenue…)"
          className="mb-3 w-full rounded-md border border-border bg-surface px-3 py-1.5 text-sm"
        />
        {sections.isPending ? (
          <LoadingState />
        ) : filtered.length === 0 ? (
          <EmptyState message={term ? `No sections match “${term}”.` : "No section outline available."} />
        ) : (
          <nav aria-label="Filing sections">
            <ol className="space-y-1 text-sm">
              {filtered.map((s, i) => (
                <li key={i} className="flex items-center justify-between gap-2 border-b border-border/60 py-1.5">
                  <span>{s.section_path.length ? s.section_path.join(" › ") : s.title}</span>
                  {s.char_start != null && (
                    <span className="text-xs text-muted">chars {s.char_start}–{s.char_end ?? "?"}</span>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        )}
        <p className="mt-3 text-xs text-muted">
          Section outline + keyword navigation. Full in-app text rendering and semantic in-document
          search require a filing-content endpoint (later phase); “Open original” links to the SEC
          document meanwhile.
        </p>
      </div>
    </Panel>
  );
}
