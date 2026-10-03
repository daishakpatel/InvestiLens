import { Suspense } from "react";
import { Outlet, useParams } from "react-router-dom";

import { MetricTile } from "../components/MetricTile";
import type { MetricMeta } from "../components/MetricTile";
import { FreshnessBadge } from "../components/Panel";
import { LoadingState } from "../components/primitives";
import { Tabs } from "../components/Tabs";
import type { TabDef } from "../components/Tabs";
import {
  formatNumber,
  formatPercent,
  formatUsd,
  formatUsdCompact,
  freshnessLabel,
  toNumber,
} from "../lib/format";
import { useCompany, useFinancials, usePrices, useValuation } from "../lib/queries";
import type { MetricResult, MetricSeries } from "../types";

const TABS: TabDef[] = [
  { to: "overview", label: "Overview" },
  { to: "financials", label: "Financials" },
  { to: "valuation", label: "Valuation" },
  { to: "filings", label: "SEC Filings" },
  { to: "news", label: "News" },
  { to: "research", label: "AI Research" },
  { to: "risks", label: "Risks" },
  { to: "management", label: "Management" },
  { to: "ownership", label: "Insiders & Ownership" },
  { to: "chat", label: "Chat" },
];

function lastPoint(series: MetricSeries | undefined): { value: string | null; period: string } | null {
  const pt = series?.points.at(-1);
  return pt ? { value: pt.value, period: pt.period } : null;
}

function findMetric(metrics: MetricResult[] | undefined, id: string): MetricResult | undefined {
  return metrics?.find((m) => m.formula_id === id);
}

function CompanyHeader({ ticker }: { ticker: string }) {
  const company = useCompany(ticker);
  const prices = usePrices(ticker);
  const valuation = useValuation(ticker);
  const financials = useFinancials(ticker, ["revenue", "net_income", "eps"], "FY");

  if (company.isPending) return <LoadingState label="Loading company…" />;
  if (company.isError) {
    const msg = company.error instanceof Error ? company.error.message : "Company not found.";
    return (
      <div role="alert" className="rounded-xl border border-border bg-surface p-6 text-negative">
        {msg}
      </div>
    );
  }

  const c = company.data.company;
  const fresh = company.data.freshness;
  const updated = freshnessLabel(fresh.as_of);

  const points = prices.data?.points ?? [];
  const last = points.at(-1);
  const prev = points.at(-2);
  const lastClose = toNumber(last?.close ?? null);
  const prevClose = toNumber(prev?.close ?? null);
  const changePct = lastClose !== null && prevClose ? (lastClose - prevClose) / prevClose : null;

  const revenue = lastPoint(financials.data?.series.find((s) => s.metric_name === "revenue"));
  const netIncome = lastPoint(financials.data?.series.find((s) => s.metric_name === "net_income"));
  const eps = lastPoint(financials.data?.series.find((s) => s.metric_name === "eps"));
  const marketCap = findMetric(valuation.data?.metrics, "market_cap");
  const pe = findMetric(valuation.data?.metrics, "pe_ratio");

  const secMeta = (period?: string, formula?: string): MetricMeta => ({
    source: "SEC filings (XBRL)",
    period: period ?? undefined,
    formula: formula ?? undefined,
    lastUpdated: updated,
  });

  return (
    <section className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">{c.name}</h1>
          <p className="text-sm text-muted">
            {c.ticker}
            {c.exchange ? ` · ${c.exchange}` : ""}
            {c.sector ? ` · ${c.sector}` : ""}
          </p>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold tabular-nums">{formatUsd(lastClose)}</div>
          {changePct !== null && (
            <div className={changePct >= 0 ? "text-positive" : "text-negative"}>
              {changePct >= 0 ? "▲" : "▼"} {formatPercent(Math.abs(changePct), 2)}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
        <MetricTile
          label="Market Cap"
          value={formatUsdCompact(marketCap?.value ?? null)}
          meta={secMeta(undefined, "price × shares")}
        />
        <MetricTile
          label="Revenue"
          value={formatUsdCompact(revenue?.value ?? null)}
          meta={secMeta(revenue?.period)}
        />
        <MetricTile
          label="Net Income"
          value={formatUsdCompact(netIncome?.value ?? null)}
          meta={secMeta(netIncome?.period)}
        />
        <MetricTile
          label="EPS"
          value={eps?.value ? formatUsd(eps.value) : "—"}
          meta={secMeta(eps?.period)}
        />
        <MetricTile
          label="P/E"
          value={pe?.value ? `${formatNumber(pe.value, 1)}×` : "—"}
          meta={secMeta(undefined, "price ÷ EPS")}
        />
      </div>

      <div className="mt-4">
        <FreshnessBadge freshness={fresh} />
      </div>
    </section>
  );
}

export default function CompanyDashboard() {
  const { ticker = "" } = useParams();
  const base = `/company/${ticker}`;

  return (
    <div className="space-y-4 py-4">
      <CompanyHeader ticker={ticker} />
      <div className="rounded-xl border border-border bg-surface shadow-sm">
        <Tabs base={base} tabs={TABS} />
        <div className="p-4">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </div>
      </div>
    </div>
  );
}
