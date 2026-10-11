import { Sparkles, Star } from "lucide-react";
import { Suspense, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";

import { CitationProvider } from "../components/citations/CitationContext";
import { FreshnessBadge } from "../components/ui/Badge";
import { Container } from "../components/ui/Container";
import { Delta } from "../components/ui/Delta";
import { Skeleton } from "../components/ui/Skeleton";
import { Stat } from "../components/ui/Stat";
import type { StatMeta } from "../components/ui/Stat";
import { ErrorState, LoadingState } from "../components/ui/States";
import { RouteTabs } from "../components/ui/Tabs";
import type { TabDef } from "../components/ui/Tabs";
import { Tooltip } from "../components/ui/Tooltip";
import { ApiError } from "../lib/apiClient";
import { useApiStatus } from "../lib/apiStatus";
import {
  formatNumber,
  formatUsd,
  formatUsdCompact,
  freshnessLabel,
} from "../lib/format";
import { useCompany, useFinancials, usePrices, useValuation } from "../lib/queries";
import { latestQuote } from "../lib/quote";
import type { Quote } from "../lib/quote";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import type { CompanyResponse, MetricResult, MetricSeries } from "../types";
import { NotFound } from "./NotFoundPage";

// Five tabs (UI plan IA). Chat is not one of them: it is the "Ask" action in the header.
const TABS: TabDef[] = [
  { to: "", label: "Overview" },
  { to: "financials", label: "Financials" },
  { to: "research", label: "Research" },
  { to: "filings", label: "Filings" },
  { to: "news", label: "News" },
];

const TOP_BAR_PX = 56;
const ACTION =
  "inline-flex h-9 items-center gap-2 rounded-control border border-border-strong px-3.5 text-sm " +
  "font-medium transition-colors hover:bg-surface-2 active:bg-surface-3";

function lastPoint(series: MetricSeries | undefined): { value: string | null; period: string } | null {
  const pt = series?.points.at(-1);
  return pt ? { value: pt.value, period: pt.period } : null;
}

function findMetric(metrics: MetricResult[] | undefined, id: string): MetricResult | undefined {
  return metrics?.find((m) => m.formula_id === id);
}

/** True once `ref` has scrolled out from under the top bar. */
function useScrolledPast(ref: RefObject<HTMLElement | null>): boolean {
  const [past, setPast] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => setPast(entry ? !entry.isIntersecting : false),
      { rootMargin: `-${TOP_BAR_PX}px 0px 0px 0px` },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [ref]);
  return past;
}

function HeaderSkeleton() {
  return (
    <div role="status" aria-label="Loading company" className="space-y-3">
      <Skeleton className="h-7 w-72 max-w-full" />
      <Skeleton className="w-48" />
      <Skeleton className="mt-5 h-8 w-36" />
      <Skeleton shape="row" className="mt-6 h-11 max-w-2xl" />
    </div>
  );
}

function KeyStats({ ticker, updated }: { ticker: string; updated: string }) {
  const valuation = useValuation(ticker);
  const financials = useFinancials(ticker, ["revenue", "net_income", "eps"], "FY");
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
    <div className="mt-6 flex flex-wrap gap-x-10 gap-y-4">
      <Stat
        label="Market cap"
        value={formatUsdCompact(marketCap?.value ?? null)}
        meta={secMeta(undefined, "price × shares")}
      />
      <Stat
        label="Revenue"
        value={formatUsdCompact(revenue?.value ?? null)}
        meta={secMeta(revenue?.period)}
      />
      <Stat
        label="Net income"
        value={formatUsdCompact(netIncome?.value ?? null)}
        meta={secMeta(netIncome?.period)}
      />
      <Stat label="EPS" value={eps?.value ? formatUsd(eps.value) : "—"} meta={secMeta(eps?.period)} />
      <Stat
        label="P/E"
        value={pe?.value ? `${formatNumber(pe.value, 1)}×` : "—"}
        meta={secMeta(undefined, "price ÷ EPS")}
      />
    </div>
  );
}

function CompanyHeader({
  data,
  quote,
  base,
}: {
  data: CompanyResponse;
  quote: Quote | null;
  base: string;
}) {
  const c = data.company;
  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <h1 className="text-heading font-semibold">{c.name}</h1>
          <p className="mt-0.5 text-sm text-muted">
            {[c.ticker, c.exchange, c.sector].filter(Boolean).join(" · ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <NavLink
            to={`${base}/chat`}
            className={({ isActive }) => `${ACTION} ${isActive ? "bg-surface-2" : ""}`}
          >
            <Sparkles aria-hidden className="size-4 text-ai" />
            Ask
          </NavLink>
          <Tooltip asChild label="Watchlists arrive in a later update.">
            {/* aria-disabled, not disabled: it must stay focusable for the tooltip to be reachable. */}
            <button type="button" aria-disabled="true" className={`${ACTION} cursor-not-allowed opacity-60`}>
              <Star aria-hidden className="size-4" />
              Watch
            </button>
          </Tooltip>
        </div>
      </div>

      {quote && (
        <div className="mt-5 flex items-baseline gap-3">
          <span className="tnum text-display-s font-semibold">{formatUsd(quote.close)}</span>
          <Delta value={quote.changePct} />
        </div>
      )}
      <KeyStats ticker={c.ticker} updated={freshnessLabel(data.freshness.as_of)} />
      <div className="mt-4">
        <FreshnessBadge freshness={data.freshness} />
      </div>
    </>
  );
}

export default function CompanyDashboard() {
  const { ticker = "" } = useParams();
  const base = `/company/${ticker}`;
  const { pathname } = useLocation();
  const company = useCompany(ticker);
  const prices = usePrices(ticker);
  const { online, reachable } = useApiStatus();
  const quote = latestQuote(prices.data?.points);

  const headerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const stuck = useScrolledPast(headerRef);

  useDocumentTitle(company.data ? `${company.data.company.ticker} · ${company.data.company.name}` : ticker);

  // Changing tab while reading far down the page starts the new tab at its top, just under the
  // pinned bars, instead of leaving the reader at an arbitrary depth in different content.
  useEffect(() => {
    const header = headerRef.current;
    if (header && header.getBoundingClientRect().bottom < TOP_BAR_PX) {
      contentRef.current?.scrollIntoView();
    }
  }, [pathname]);

  if (company.error instanceof ApiError && company.error.status === 404) {
    return (
      <NotFound
        title={`No company found for “${ticker.toUpperCase()}”`}
        message="We don’t have data for that ticker. Check the symbol, or search by company name."
      />
    );
  }

  return (
    <CitationProvider>
      <Container className="pb-6 pt-8">
        <div ref={headerRef}>
          {company.data ? (
            <CompanyHeader data={company.data} quote={quote} base={base} />
          ) : company.isError && online && reachable ? (
            <ErrorState
              message={company.error instanceof Error ? company.error.message : "Could not load this company."}
              onRetry={() => void company.refetch()}
            />
          ) : (
            <HeaderSkeleton />
          )}
        </div>
      </Container>

      {/* The tab strip is always this 48 px bar, so pinning it moves nothing. Once the header has
          scrolled away, the ticker and price fade in beside the tabs to keep the context. */}
      <div className="sticky top-14 z-20 border-b border-border bg-bg/80 backdrop-blur-md">
        <Container className="flex h-12 items-center justify-between gap-6">
          <RouteTabs base={base} tabs={TABS} label="Company sections" />
          <div
            data-testid="pinned-quote"
            aria-hidden={!stuck}
            className={`shrink-0 items-baseline gap-2 text-sm transition-opacity duration-(--duration-slow) ${
              stuck ? "flex opacity-100" : "hidden opacity-0 md:flex"
            }`}
          >
            <span className="font-medium">{ticker.toUpperCase()}</span>
            {quote && (
              <>
                <span className="tnum">{formatUsd(quote.close)}</span>
                {/* Wrapped, not classed: Delta sets its own display, which would win over `hidden`. */}
                <span className="hidden sm:inline">
                  <Delta value={quote.changePct} />
                </span>
              </>
            )}
          </div>
        </Container>
      </div>

      <Container>
        <div ref={contentRef} className="pt-8">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </div>
      </Container>
    </CitationProvider>
  );
}
