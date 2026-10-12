import { ArrowRight } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { MetricChart } from "../../charts/MetricChart";
import { CitationChip } from "../../components/citations/CitationChip";
import { KeyStats } from "../../components/company/KeyStats";
import { PriceHero } from "../../components/company/PriceHero";
import { Section } from "../../components/ui/Section";
import { Skeleton } from "../../components/ui/Skeleton";
import { formatDate } from "../../lib/format";
import { metricLabel } from "../../lib/metricCatalog";
import {
  useCompany,
  useFilings,
  useFinancials,
  useLatestResearch,
  useNews,
} from "../../lib/queries";
import { buildNumbering } from "../../lib/reportCitations";

const PERFORMANCE = ["revenue", "net_income"];
const YEARS_SHOWN = 5;
const LATEST_COUNT = 3;
const LINK = "inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline";

function Lines({ count }: { count: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-3 pt-4">
      {Array.from({ length: count }, (_, i) => (
        <Skeleton key={i} className={i % 2 ? "w-3/5" : "w-4/5"} />
      ))}
    </div>
  );
}

function Performance({ ticker }: { ticker: string }) {
  const financials = useFinancials(ticker, PERFORMANCE, "FY");
  return (
    <Section title="Performance">
      <div className="grid gap-x-10 gap-y-8 pt-5 sm:grid-cols-2">
        {PERFORMANCE.map((name) => {
          const series = financials.data?.series.find((s) => s.metric_name === name);
          const points = (series?.points ?? []).slice(-YEARS_SHOWN);
          return (
            <MetricChart
              key={name}
              compact
              name={name}
              href={`/company/${ticker}/financials#income`}
              points={points}
              csvName={`${ticker}_${name}_FY`}
              loading={financials.isPending}
              emptyMessage={`${metricLabel(name)} has not been reported in the filings we hold.`}
            />
          );
        })}
      </div>
    </Section>
  );
}

function ResearchTeaser({ ticker }: { ticker: string }) {
  const latest = useLatestResearch(ticker);
  const to = `/company/${ticker}/research`;
  return (
    <Section title="Research" kind="ai">
      {latest.isPending ? (
        <Lines count={3} />
      ) : latest.isSuccess && latest.data.report.executive_summary.length > 0 ? (
        <div className="space-y-3 pt-4">
          {latest.data.report.executive_summary.slice(0, 2).map((claim) => (
            <p key={claim.claim_id} className="max-w-2xl text-body">
              {claim.text}{" "}
              {claim.source_ids.map((id) => (
                <CitationChip
                  key={id}
                  number={buildNumbering(latest.data.report).numberOf(id)}
                  sourceId={id}
                />
              ))}
            </p>
          ))}
          <Link to={to} className={LINK}>
            Read the full research
            <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      ) : (
        <div className="space-y-3 pt-4">
          <p className="max-w-2xl text-muted">
            No research report has been generated for {ticker.toUpperCase()} yet. A report covers
            the business, its financials and its risks, with every claim cited.
          </p>
          <Link to={to} className={LINK}>
            Generate research
            <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
      )}
    </Section>
  );
}

function About({ ticker }: { ticker: string }) {
  const company = useCompany(ticker);
  const c = company.data?.company;
  const rows = c
    ? [
        ["Sector", c.sector],
        ["Industry", c.industry],
        ["Exchange", c.exchange],
        ["Fiscal year ends", c.fiscal_year_end],
        ["CIK", c.cik],
      ].filter((row): row is [string, string] => Boolean(row[1]))
    : [];
  return (
    <Section title="About">
      {company.isPending ? (
        <Lines count={4} />
      ) : (
        <dl className="pt-2 text-sm">
          {rows.map(([term, detail]) => (
            <div key={term} className="flex justify-between gap-6 border-b border-border/60 py-2.5">
              <dt className="shrink-0 text-muted">{term}</dt>
              <dd className="text-right">{detail}</dd>
            </div>
          ))}
        </dl>
      )}
    </Section>
  );
}

function Latest({ ticker }: { ticker: string }) {
  // The filings list is paged by id, not date: fetch enough to be sure the newest are in it.
  const filings = useFilings(ticker, 200);
  const news = useNews(ticker);
  const recentFilings = [...(filings.data ?? [])]
    .sort((a, b) => (b.filing_date ?? "").localeCompare(a.filing_date ?? ""))
    .slice(0, LATEST_COUNT);
  const headlines = (news.data?.items ?? []).slice(0, LATEST_COUNT);
  const row = "-mx-2 block rounded-control px-2 py-2 transition-colors hover:bg-surface pointer-coarse:py-2.5";

  return (
    <Section title="Latest">
      {filings.isPending || news.isPending ? (
        <Lines count={5} />
      ) : recentFilings.length === 0 && headlines.length === 0 ? (
        <p className="pt-4 text-sm text-muted">No filings or news have been ingested yet.</p>
      ) : (
        <div className="space-y-5 pt-3">
          {recentFilings.length > 0 && (
            <div>
              <h3 className="text-label text-muted">Filings</h3>
              <ul>
                {recentFilings.map((filing) => (
                  <li key={filing.filing_id}>
                    <Link to={`/company/${ticker}/filings`} className={`${row} flex justify-between gap-4 text-sm`}>
                      <span className="font-medium">{filing.filing_type}</span>
                      <span className="text-muted">Filed {formatDate(filing.filing_date)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {headlines.length > 0 && (
            <div>
              <h3 className="text-label text-muted">News</h3>
              <ul>
                {headlines.map((item) => (
                  <li key={item.news_id}>
                    <Link to={`/company/${ticker}/news`} className={`${row} text-sm`}>
                      <span className="line-clamp-2">{item.title}</span>
                      <span className="text-caption text-subtle">
                        {[item.publisher, item.published_at && formatDate(item.published_at)]
                          .filter(Boolean)
                          .join(" · ")}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

/** The first screen of a company: the price and how it has moved, the headline figures, then
 *  how the business has performed beside what it is and what has happened lately. */
export default function OverviewTab() {
  const { ticker = "" } = useParams();
  return (
    <div className="space-y-12">
      <PriceHero ticker={ticker} />
      <KeyStats ticker={ticker} />
      <div className="grid gap-x-16 gap-y-12 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-12">
          <Performance ticker={ticker} />
          <ResearchTeaser ticker={ticker} />
        </div>
        <div className="space-y-12">
          <About ticker={ticker} />
          <Latest ticker={ticker} />
        </div>
      </div>
    </div>
  );
}
