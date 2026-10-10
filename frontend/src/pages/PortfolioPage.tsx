import { useMemo, useState } from "react";

import { Panel } from "../components/Panel";
import { ErrorState, LoadingState } from "../components/primitives";
import { formatPercent } from "../lib/format";
import { recomputeFrom } from "../lib/portfolioRecompute";
import { usePortfolioAnalysis } from "../lib/queries";
import type { PortfolioAnalysis } from "../types";

interface HoldingInput {
  ticker: string;
  weight: number;
}

const DEFAULT: HoldingInput[] = [
  { ticker: "NVDA", weight: 40 },
  { ticker: "AAPL", weight: 30 },
  { ticker: "JPM", weight: 30 },
];

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<HoldingInput[]>(DEFAULT);
  const [analysis, setAnalysis] = useState<PortfolioAnalysis | null>(null);
  // Live weights drive the client-side what-if recompute after an analysis (§37.2 item 10).
  const [liveWeights, setLiveWeights] = useState<Record<string, number>>({});
  const analyze = usePortfolioAnalysis();

  const runAnalysis = () => {
    analyze.mutate(holdings, {
      onSuccess: (data) => {
        setAnalysis(data);
        const w: Record<string, number> = {};
        for (const h of data.holdings) w[h.ticker] = Number(h.weight);
        setLiveWeights(w);
      },
    });
  };

  const recomputed = useMemo(
    () => (analysis ? recomputeFrom(analysis, liveWeights) : null),
    [analysis, liveWeights],
  );

  const setHolding = (i: number, patch: Partial<HoldingInput>) =>
    setHoldings(holdings.map((h, j) => (j === i ? { ...h, ...patch } : h)));

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-6">
      <h1 className="mb-1 text-xl font-semibold">Portfolio analysis</h1>
      <p className="mb-4 text-sm text-muted">
        Enter hypothetical holdings as ticker + weight. All figures are deterministic analysis of a
        hypothetical portfolio — not a recommendation to buy, sell, hold, or rebalance.
      </p>

      <Panel title="Holdings">
        <div className="flex flex-col gap-2 p-4">
          {holdings.map((h, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                value={h.ticker}
                onChange={(e) => setHolding(i, { ticker: e.target.value.toUpperCase() })}
                aria-label={`Holding ${i + 1} ticker`}
                className="w-28 rounded-md border border-border bg-surface px-2 py-1 text-sm"
              />
              <input
                type="number"
                min={0}
                value={h.weight}
                onChange={(e) => setHolding(i, { weight: Number(e.target.value) })}
                aria-label={`Holding ${i + 1} weight`}
                className="w-24 rounded-md border border-border bg-surface px-2 py-1 text-sm"
              />
              <span className="text-xs text-muted">%</span>
              <button
                type="button"
                aria-label={`Remove holding ${i + 1}`}
                onClick={() => setHoldings(holdings.filter((_, j) => j !== i))}
                className="text-muted hover:text-text"
              >
                ×
              </button>
            </div>
          ))}
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setHoldings([...holdings, { ticker: "", weight: 10 }])}
              className="rounded-md border border-border px-2 py-1 text-sm hover:bg-surface-2"
            >
              Add holding
            </button>
            <button
              type="button"
              onClick={runAnalysis}
              disabled={analyze.isPending || holdings.filter((h) => h.ticker).length < 1}
              className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-contrast hover:opacity-90 disabled:opacity-50"
            >
              {analyze.isPending ? "Analyzing…" : "Analyze"}
            </button>
          </div>
        </div>
      </Panel>

      {analyze.isPending && <LoadingState />}
      {analyze.isError && <ErrorState message={analyze.error.message} onRetry={runAnalysis} />}

      {analysis && recomputed && (
        <div className="mt-4 flex flex-col gap-4">
          <WhatIf
            analysis={analysis}
            liveWeights={liveWeights}
            onChange={(ticker, w) => setLiveWeights({ ...liveWeights, [ticker]: w })}
          />
          <Aggregates recomputed={recomputed} />
          <SectorExposure recomputed={recomputed} />
          <RiskStatsPanel analysis={analysis} />
          <RiskThemes analysis={analysis} />
          {analysis.notes.length > 0 && (
            <ul className="list-disc pl-5 text-xs text-muted">
              {analysis.notes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          )}
          <p className="text-xs text-muted">{analysis.disclaimer}</p>
        </div>
      )}
    </main>
  );
}

type Recomputed = NonNullable<ReturnType<typeof recomputeFrom>>;

function WhatIf({
  analysis,
  liveWeights,
  onChange,
}: {
  analysis: PortfolioAnalysis;
  liveWeights: Record<string, number>;
  onChange: (ticker: string, weight: number) => void;
}) {
  return (
    <Panel title="What-if weights">
      <div className="flex flex-col gap-3 p-4">
        <p className="text-xs text-muted">
          Drag to re-weight; metrics below recompute instantly (no re-fetch).
        </p>
        {analysis.holdings.map((h) => (
          <label key={h.ticker} className="flex items-center gap-3 text-sm">
            <span className="w-16 font-medium">{h.ticker}</span>
            <input
              type="range"
              min={0}
              max={100}
              value={liveWeights[h.ticker] ?? 0}
              onChange={(e) => onChange(h.ticker, Number(e.target.value))}
              className="flex-1"
              aria-label={`${h.ticker} weight`}
            />
            <span className="w-12 text-right tabular-nums">{(liveWeights[h.ticker] ?? 0).toFixed(0)}</span>
          </label>
        ))}
      </div>
    </Panel>
  );
}

function Aggregates({ recomputed }: { recomputed: Recomputed }) {
  return (
    <Panel title="Weighted metrics & concentration">
      <div className="grid gap-4 p-4 sm:grid-cols-2 lg:grid-cols-3">
        <Stat
          label="Concentration (HHI)"
          value={recomputed.hhi.toFixed(3)}
          sub={`${recomputed.effectiveHoldings.toFixed(1)} effective holdings`}
        />
        {recomputed.weightedMetrics.map((m) => (
          <Stat
            key={m.metricName}
            label={m.metricName}
            value={m.value === null ? "—" : formatPercent(m.value)}
            sub={m.coverage < 1 ? `${formatPercent(m.coverage, 0)} coverage` : undefined}
          />
        ))}
      </div>
    </Panel>
  );
}

function SectorExposure({ recomputed }: { recomputed: Recomputed }) {
  const max = Math.max(...recomputed.sectorExposure.map((s) => s.weight), 0.0001);
  return (
    <Panel title="Sector exposure">
      <div className="flex flex-col gap-2 p-4">
        {recomputed.sectorExposure.map((s) => (
          <div key={s.sector} className="text-sm">
            <div className="flex justify-between">
              <span>{s.sector}</span>
              <span className="tabular-nums text-muted">{formatPercent(s.weight, 0)}</span>
            </div>
            <div className="mt-1 h-2 w-full rounded-full bg-surface-2">
              <div
                className="h-2 rounded-full bg-[var(--chart-1)]"
                style={{ width: `${(s.weight / max) * 100}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function RiskStatsPanel({ analysis }: { analysis: PortfolioAnalysis }) {
  const risk = analysis.risk_stats;
  if (!risk) return null;
  return (
    <Panel title="Risk (price-based)">
      <div className="p-4">
        <div className="mb-3 flex flex-wrap gap-6 text-sm">
          <Stat
            label="Portfolio volatility (annualized)"
            value={risk.portfolio_volatility ? formatPercent(risk.portfolio_volatility) : "—"}
          />
        </div>
        {risk.correlation.length > 0 && (
          <div className="overflow-auto">
            <table className="text-sm">
              <thead className="text-xs uppercase text-muted">
                <tr>
                  <th className="px-2 py-1" />
                  {risk.correlation.map((r) => (
                    <th key={r.ticker} className="px-2 py-1 text-right">
                      {r.ticker}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {risk.correlation.map((r) => (
                  <tr key={r.ticker} className="border-t border-border">
                    <th scope="row" className="px-2 py-1 text-left font-normal">
                      {r.ticker}
                    </th>
                    {risk.correlation.map((c) => (
                      <td key={c.ticker} className="px-2 py-1 text-right tabular-nums">
                        {r.correlations[c.ticker] ? Number(r.correlations[c.ticker]).toFixed(2) : "—"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {risk.notes.map((n) => (
          <p key={n} className="mt-2 text-xs text-muted">
            {n}
          </p>
        ))}
      </div>
    </Panel>
  );
}

function RiskThemes({ analysis }: { analysis: PortfolioAnalysis }) {
  return (
    <Panel title="Aggregated risk themes">
      <div className="p-4">
        {analysis.risk_themes.length === 0 ? (
          <p className="text-sm text-muted">
            No cited risk themes yet — they aggregate each holding&apos;s research-report risk
            factors (generate a report per holding to populate them).
          </p>
        ) : (
          <ul className="flex flex-col gap-3 text-sm">
            {analysis.risk_themes.map((t) => (
              <li key={t.category}>
                <div className="font-medium">
                  {t.category.replace(/_/g, " ")}{" "}
                  <span className="text-xs text-muted">
                    ({t.holding_count} holding{t.holding_count === 1 ? "" : "s"},{" "}
                    {formatPercent(t.portfolio_weight, 0)} of portfolio)
                  </span>
                </div>
                <ul className="mt-1 list-disc pl-5 text-xs text-muted">
                  {t.contributions.map((c, i) => (
                    <li key={i}>
                      <span className="font-medium">{c.ticker}:</span> {c.description}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Panel>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string | undefined }) {
  return (
    <div>
      <div className="text-xs uppercase text-muted">{label}</div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      {sub && <div className="text-xs text-muted">{sub}</div>}
    </div>
  );
}
