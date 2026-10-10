import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { ComparisonBars } from "../charts/ComparisonBars";
import { AsyncContent, Panel } from "../components/Panel";
import { Badge, EmptyState } from "../components/primitives";
import { useAuth } from "../lib/auth";
import { formatMetricValue, formatPercent } from "../lib/format";
import { useComparison, useComparisonCommentary, usePeers } from "../lib/queries";
import type { ComparisonResponse } from "../types";

const DEFAULT_TICKERS = ["NVDA", "AMD", "INTC"];
const CHART_METRICS = ["gross_margin", "net_margin", "yoy_growth"];

export default function ComparePage() {
  const [tickers, setTickers] = useState<string[]>(DEFAULT_TICKERS);
  const [draft, setDraft] = useState("");
  const comparison = useComparison(tickers, []);

  const add = () => {
    const t = draft.trim().toUpperCase();
    if (t && !tickers.includes(t) && tickers.length < 6) setTickers([...tickers, t]);
    setDraft("");
  };
  const remove = (t: string) => setTickers(tickers.filter((x) => x !== t));

  return (
    <main className="mx-auto w-full max-w-6xl px-4 py-6">
      <h1 className="mb-1 text-xl font-semibold">Compare companies</h1>
      <p className="mb-4 text-sm text-muted">
        Side-by-side metrics, aligned to a common calendar year and ranked within the selected peer
        set. Analysis only — never a buy/sell recommendation.
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        {tickers.map((t) => (
          <span
            key={t}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-surface-2 px-3 py-1 text-sm"
          >
            <Link to={`/company/${t}`} className="font-medium hover:underline">
              {t}
            </Link>
            <button
              type="button"
              aria-label={`Remove ${t}`}
              onClick={() => remove(t)}
              className="text-muted hover:text-text"
            >
              ×
            </button>
          </span>
        ))}
        {tickers.length < 6 && (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              add();
            }}
            className="inline-flex items-center gap-1"
          >
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Add ticker"
              aria-label="Add ticker"
              className="w-28 rounded-md border border-border bg-surface px-2 py-1 text-sm"
            />
            <button
              type="submit"
              className="rounded-md border border-border px-2 py-1 text-sm hover:bg-surface-2"
            >
              Add
            </button>
          </form>
        )}
      </div>

      {tickers.length < 2 ? (
        <EmptyState message="Add at least two companies to compare." />
      ) : (
        <AsyncContent query={comparison}>
          {(data) => (
            <div className="flex flex-col gap-4">
              <CalendarizationNote data={data} />
              <MetricTable data={data} />
              <Panel title="Side-by-side">
                <div className="grid gap-6 p-4 sm:grid-cols-2 lg:grid-cols-3">
                  {CHART_METRICS.map((name) => {
                    const row = data.metrics.find((m) => m.metric_name === name);
                    if (!row) return null;
                    return (
                      <ComparisonBars
                        key={name}
                        metricName={row.metric_name}
                        unit={row.unit}
                        cells={row.cells}
                      />
                    );
                  })}
                </div>
              </Panel>
              <CommentaryPanel tickers={tickers} />
              <PeersPanel
                ticker={tickers[0] ?? ""}
                onAdd={(t) => !tickers.includes(t) && setTickers([...tickers, t])}
              />
              {data.notes.length > 0 && (
                <ul className="list-disc pl-5 text-xs text-muted">
                  {data.notes.map((n) => (
                    <li key={n}>{n}</li>
                  ))}
                </ul>
              )}
              <p className="text-xs text-muted">{data.disclaimer}</p>
            </div>
          )}
        </AsyncContent>
      )}
    </main>
  );
}

function CalendarizationNote({ data }: { data: ComparisonResponse }) {
  return (
    <Panel title={`Comparison period — calendar year ${data.calendar_year ?? "—"}`}>
      <div className="flex flex-wrap gap-4 p-4 text-sm">
        {data.companies.map((c) => (
          <div key={c.ticker} className="min-w-32">
            <div className="font-medium">{c.ticker}</div>
            <div className="text-muted">
              {c.fiscal_period ?? "—"} · FYE {c.fiscal_year_end ?? "—"}
            </div>
            <div className="text-xs text-muted">{c.sector ?? "—"}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function MetricTable({ data }: { data: ComparisonResponse }) {
  return (
    <Panel title="Metrics">
      <div className="overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface-2 text-xs uppercase text-muted">
            <tr>
              <th scope="col" className="px-3 py-2">
                Metric
              </th>
              {data.companies.map((c) => (
                <th key={c.ticker} scope="col" className="px-3 py-2 text-right">
                  {c.ticker}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.metrics.map((row) => (
              <tr key={row.metric_name} className="border-t border-border">
                <th scope="row" className="px-3 py-2 font-normal">
                  {row.metric_name}
                </th>
                {row.cells.map((cell) => (
                  <td key={cell.ticker} className="px-3 py-2 text-right tabular-nums">
                    <div>{formatMetricValue(cell.result.value, row.unit)}</div>
                    {cell.percentile != null && cell.result.value != null && (
                      <div className="text-xs text-muted">
                        {formatPercent(cell.percentile, 0)} pctile
                      </div>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function CommentaryPanel({ tickers }: { tickers: string[] }) {
  const { user } = useAuth();
  const commentary = useComparisonCommentary();

  return (
    <Panel
      title="AI commentary"
      kind="ai"
      actions={
        user ? (
          <button
            type="button"
            disabled={commentary.isPending}
            onClick={() => commentary.mutate({ tickers })}
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2 disabled:opacity-50"
          >
            {commentary.isPending ? "Generating…" : "Generate"}
          </button>
        ) : (
          <Link to="/login" className="text-xs text-muted hover:underline">
            Sign in to generate
          </Link>
        )
      }
    >
      <div className="p-4 text-sm">
        {commentary.isError && (
          <p className="text-negative">Could not generate commentary. {commentary.error.message}</p>
        )}
        {commentary.data ? (
          commentary.data.sufficient && commentary.data.rendered_text ? (
            <>
              <p className="whitespace-pre-wrap">{commentary.data.rendered_text}</p>
              {commentary.data.citations.length > 0 && (
                <p className="mt-2 text-xs text-muted">
                  {commentary.data.citations.length} verified citation(s). Every statement is cited;
                  unsupported claims and any recommendation are withheld.
                </p>
              )}
            </>
          ) : (
            <p className="text-muted">
              Insufficient cited evidence to describe the differences — the deterministic metrics
              above remain available.
            </p>
          )
        ) : (
          <p className="text-muted">
            Generate a cited, verified summary of the differences (same verification as research
            reports; never a recommendation).
          </p>
        )}
      </div>
    </Panel>
  );
}

function PeersPanel({ ticker, onAdd }: { ticker: string; onAdd: (t: string) => void }) {
  const peers = usePeers(ticker);
  const content = useMemo(() => peers.data?.peers ?? [], [peers.data]);
  return (
    <Panel title={`Suggested peers for ${ticker}`}>
      <div className="p-4">
        {content.length === 0 ? (
          <p className="text-sm text-muted">No peer suggestions.</p>
        ) : (
          <ul className="flex flex-col gap-2 text-sm">
            {content.map((p) => (
              <li key={p.ticker} className="flex items-center justify-between gap-2">
                <span>
                  <span className="font-medium">{p.ticker}</span> — {p.name}{" "}
                  <span className="text-xs text-muted">({p.reason})</span>
                  {p.market_cap?.value != null && (
                    <Badge tone="data">{formatMetricValue(p.market_cap.value, p.market_cap.unit)}</Badge>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => onAdd(p.ticker)}
                  className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2"
                >
                  Add
                </button>
              </li>
            ))}
          </ul>
        )}
        {(peers.data?.notes ?? []).map((n) => (
          <p key={n} className="mt-2 text-xs text-muted">
            {n}
          </p>
        ))}
      </div>
    </Panel>
  );
}
