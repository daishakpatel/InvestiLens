import { Suspense } from "react";
import { Outlet, useParams } from "react-router-dom";

import { CitationProvider } from "../components/citations/CitationContext";
import { FreshnessBadge } from "../components/ui/Badge";
import { Stat } from "../components/ui/Stat";
import type { StatMeta } from "../components/ui/Stat";
import { LoadingState } from "../components/ui/States";
import { RouteTabs } from "../components/ui/Tabs";
import type { TabDef } from "../components/ui/Tabs";
import {
  formatNumber,
  formatUsd,
  formatUsdCompact,
  freshnessLabel,
  toNumber,
} from "../lib/format";
import { useCompany, useFinancials, usePrices, useValuation } from "../lib/queries";
import type { MetricResult, MetricSeries } from "../types";
import { Delta } from "../components/ui/Delta";

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
      <div role="alert" className="py-6 text-negative">
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

  const secMeta = (period?: string, formula?: string): StatMeta => ({
    source: "SEC filings (XBRL)",
    period: period ?? undefined,
    formula: formula ?? undefined,
    lastUpdated: updated,
  });

  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-heading font-semibold">{c.name}</h1>
          <p className="text-sm text-muted">
            {c.ticker}
            {c.exchange ? ` · ${c.exchange}` : ""}
            {c.sector ? ` · ${c.sector}` : ""}
          </p>
        </div>
        <div className="text-right">
          <div className="tnum text-heading font-semibold">{formatUsd(lastClose)}</div>
          <Delta value={changePct} className="text-sm" />
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-x-10 gap-y-4">
        <Stat
          label="Market Cap"
          value={formatUsdCompact(marketCap?.value ?? null)}
          meta={secMeta(undefined, "price × shares")}
        />
        <Stat
          label="Revenue"
          value={formatUsdCompact(revenue?.value ?? null)}
          meta={secMeta(revenue?.period)}
        />
        <Stat
          label="Net Income"
          value={formatUsdCompact(netIncome?.value ?? null)}
          meta={secMeta(netIncome?.period)}
        />
        <Stat
          label="EPS"
          value={eps?.value ? formatUsd(eps.value) : "—"}
          meta={secMeta(eps?.period)}
        />
        <Stat
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
    <CitationProvider>
      <div className="space-y-6 py-6">
        <CompanyHeader ticker={ticker} />
        <div>
          <RouteTabs base={base} tabs={TABS} label="Company sections" />
          <div className="pt-6">
            <Suspense fallback={<LoadingState />}>
              <Outlet />
            </Suspense>
          </div>
        </div>
      </div>
    </CitationProvider>
  );
}
