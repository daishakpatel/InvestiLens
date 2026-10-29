import { Sparkles } from "lucide-react";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Outlet, useLocation, useParams } from "react-router-dom";

import type { CompanyOutletContext } from "../components/company/outletContext";
import { PanelProvider, useAssistant } from "../components/panel/PanelProvider";
import { Container } from "../components/ui/Container";
import { Delta } from "../components/ui/Delta";
import { Skeleton } from "../components/ui/Skeleton";
import { ErrorState, LoadingState } from "../components/ui/States";
import { RouteTabs } from "../components/ui/Tabs";
import type { TabDef } from "../components/ui/Tabs";
import { AlertsButton } from "../components/watch/AlertsButton";
import { WatchButton } from "../components/watch/WatchButton";
import { ApiError } from "../lib/apiClient";
import { useApiStatus } from "../lib/apiStatus";
import { formatUsd } from "../lib/format";
import { useCompany, usePrices, useRedFlags } from "../lib/queries";
import { latestQuote } from "../lib/quote";
import { recentCount } from "../lib/redFlags";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import type { CompanyResponse } from "../types";
import { NotFound } from "./NotFoundPage";

// The UI plan's five tabs, plus Earnings (Phase 7j, which also holds Earnings quality from 7d) and
// Thesis (7k). The assistant is not one of them: "Ask" in the header opens it as a panel beside
// whichever tab is showing.
const TABS: TabDef[] = [
  { to: "", label: "Overview" },
  { to: "financials", label: "Financials" },
  { to: "news", label: "News" },
  { to: "earnings", label: "Earnings" },
  { to: "research", label: "Research" },
  { to: "thesis", label: "Thesis" },
  { to: "footnotes", label: "Footnotes" },
  { to: "governance", label: "Governance" },
  { to: "filings", label: "Filings" },
];

const TOP_BAR_PX = 56;
const TAB_BAR_PX = 48;
const ACTION =
  "inline-flex h-9 items-center gap-2 rounded-control border border-border-strong px-3.5 text-sm " +
  "font-medium transition-colors hover:bg-surface-2 active:bg-surface-3";

/** True once `element` has scrolled out from under the pinned bars. */
function useScrolledPast(element: HTMLElement | null, offsetPx: number): boolean {
  const [past, setPast] = useState(false);
  useEffect(() => {
    if (!element) return;
    const observer = new IntersectionObserver(
      ([entry]) => setPast(entry ? !entry.isIntersecting : false),
      { rootMargin: `-${offsetPx}px 0px 0px 0px` },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [element, offsetPx]);
  return past;
}

function HeaderSkeleton() {
  return (
    <div role="status" aria-label="Loading company" className="space-y-3">
      <Skeleton className="h-7 w-72 max-w-full" />
      <Skeleton className="w-48" />
    </div>
  );
}

function CompanyHeader({ data }: { data: CompanyResponse }) {
  const c = data.company;
  const assistant = useAssistant();
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
      <div className="min-w-0">
        <h1 className="text-heading font-semibold">{c.name}</h1>
        <p className="mt-0.5 text-sm text-muted">
          {[c.ticker, c.exchange, c.sector].filter(Boolean).join(" · ")}
        </p>
      </div>
      <div className="flex items-center gap-2 print:hidden">
        <button
          type="button"
          aria-expanded={assistant.isOpen}
          onClick={assistant.toggle}
          className={`${ACTION} ${assistant.isOpen ? "bg-surface-2" : ""}`}
        >
          <Sparkles aria-hidden className="size-4 text-ai" />
          Ask
        </button>
        <WatchButton ticker={c.ticker} />
        <AlertsButton ticker={c.ticker} />
      </div>
    </div>
  );
}

export default function CompanyDashboard() {
  const { ticker = "" } = useParams();
  const base = `/company/${ticker}`;
  const { pathname } = useLocation();
  const company = useCompany(ticker);
  // The Overview tab counts the red flags filed in the last year (FR-RF-012).
  const flags = useRedFlags(ticker);
  const flagCount = flags.data ? recentCount(flags.data.items) : 0;
  const tabs = TABS.map((tab) =>
    tab.to === "" ? { ...tab, count: { value: flagCount, label: `${flagCount} red flags in the last year` } } : tab,
  );
  const prices = usePrices(ticker);
  const { online, reachable } = useApiStatus();
  const quote = latestQuote(prices.data?.points);

  const [header, setHeader] = useState<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const stuck = useScrolledPast(header, TOP_BAR_PX);

  // The pinned bar repeats the price only where the page is not already showing it. A tab that
  // leads with the price (Overview's hero) registers that element, and the bar waits until it
  // has scrolled away. Tabs that show no price get it in the bar from the start.
  const [quoteElement, setQuoteElement] = useState<HTMLElement | null>(null);
  const quotePast = useScrolledPast(quoteElement, TOP_BAR_PX + TAB_BAR_PX);
  const isOverview = pathname.replace(/\/$/, "").toLowerCase() === base.toLowerCase();
  const showQuote = quoteElement ? quotePast : isOverview ? stuck : true;
  const outlet = useMemo<CompanyOutletContext>(() => ({ quoteAnchor: setQuoteElement }), []);

  useDocumentTitle(company.data ? `${company.data.company.ticker} · ${company.data.company.name}` : ticker);

  // Changing tab while reading far down the page starts the new tab at its top, just under the
  // pinned bars, instead of leaving the reader at an arbitrary depth in different content.
  useEffect(() => {
    if (header && header.getBoundingClientRect().bottom < TOP_BAR_PX) {
      contentRef.current?.scrollIntoView();
    }
    // Only a tab change should do this, not the header element arriving.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    <PanelProvider key={ticker.toUpperCase()} assistantFor={ticker.toUpperCase()}>
      <Container className="pb-5 pt-8">
        {/* Reserves the header's height while the company loads: on a phone the actions wrap
            beneath the name, so it is twice as tall as on a desktop. */}
        <div ref={setHeader} className="min-h-27 sm:min-h-13">
          {company.data ? (
            <CompanyHeader data={company.data} />
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

      {/* The tab strip is always this 48 px bar, so pinning it moves nothing. The ticker and price
          sit beside the tabs whenever the page itself is not showing the price. On phones, where
          the strip is short, they appear only once the bar is pinned. */}
      <div className="sticky top-14 z-20 border-b border-border bg-bg/80 backdrop-blur-md print:hidden">
        <Container className="flex h-12 items-center justify-between gap-6">
          <RouteTabs base={base} tabs={tabs} label="Company sections" />
          <div
            data-testid="pinned-quote"
            aria-hidden={!showQuote}
            className={`shrink-0 items-baseline gap-2 text-sm transition-opacity duration-(--duration-slow) ${
              showQuote ? `opacity-100 ${stuck ? "flex" : "hidden md:flex"}` : "hidden opacity-0 md:flex"
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
            <Outlet context={outlet} />
          </Suspense>
        </div>
      </Container>
    </PanelProvider>
  );
}
