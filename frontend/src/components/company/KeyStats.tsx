import { DataRefreshChecklist } from "../DataRefreshChecklist";
import { changeBetween, formatValue } from "../../charts/series";
import { fiscalCalendarLabel, freshnessLabel, toNumber } from "../../lib/format";
import { metricDisplay, metricLabel } from "../../lib/metricCatalog";
import { useDataFreshness, useFinancials, useValuation } from "../../lib/queries";
import type { MetricSeries } from "../../types";
import { FreshnessBadge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Delta } from "../ui/Delta";
import { Popover } from "../ui/Popover";
import { Skeleton } from "../ui/Skeleton";
import { Stat } from "../ui/Stat";

const REPORTED = ["revenue", "net_income", "eps_diluted", "gross_margin"];
const PRICE_BASED = ["market_cap", "pe_ratio"]; // shown only once the backend computes them

const FORMULAS: Record<string, string> = {
  gross_margin: "gross profit ÷ revenue",
  market_cap: "price × diluted shares",
  pe_ratio: "price ÷ diluted EPS",
};

interface StatData {
  name: string;
  value: string;
  period?: string;
  change: number | null;
  points: boolean;
}

/** The latest period of a series, or nothing if that period has no value. An N/A is left out
 *  rather than shown as a dash, and an older year is never passed off as the latest. */
function latestOf(series: MetricSeries | undefined): StatData | null {
  const point = series?.points.at(-1);
  const value = toNumber(point?.value ?? null);
  if (!series || !point || value === null) return null;
  const prior = toNumber(series.points.at(-2)?.value ?? null);
  const display = metricDisplay(series.metric_name, point.unit);
  return {
    name: series.metric_name,
    value: formatValue(value, display),
    period: fiscalCalendarLabel(point.period, point.period_end),
    change: changeBetween(value, prior, display),
    points: display === "percent",
  };
}

function DataStatus({ ticker }: { ticker: string }) {
  const freshness = useDataFreshness(ticker);
  return (
    <Popover
      trigger={
        <Button variant="ghost" size="sm" className="-ml-2.5">
          Data status
        </Button>
      }
    >
      {freshness.data ? (
        <DataRefreshChecklist sources={freshness.data.sources} />
      ) : (
        <p className="text-muted">{freshness.isError ? "Status is unavailable." : "Checking…"}</p>
      )}
    </Popover>
  );
}

/** The headline figures under the price: the latest fiscal year, each with its change on the
 *  year before and, on hover or focus, where it comes from (§9.4). */
export function KeyStats({ ticker }: { ticker: string }) {
  const financials = useFinancials(ticker, REPORTED, "FY");
  const valuation = useValuation(ticker);

  if (financials.isPending) {
    return (
      <div role="status" aria-label="Loading key figures" className="flex flex-wrap gap-x-12 gap-y-4">
        {REPORTED.map((name) => (
          <Skeleton key={name} className="h-11 w-28" />
        ))}
      </div>
    );
  }

  const reported = REPORTED.map((name) =>
    latestOf(financials.data?.series.find((series) => series.metric_name === name)),
  ).filter((stat): stat is StatData => stat !== null);

  const priceBased: StatData[] = PRICE_BASED.flatMap((name) => {
    const metric = valuation.data?.metrics.find((m) => m.formula_id === name);
    const value = toNumber(metric?.value ?? null);
    return metric && value !== null
      ? [{ name, value: formatValue(value, metricDisplay(name, metric.unit)), change: null, points: false }]
      : [];
  });

  const stats = [...reported, ...priceBased];
  const updated = financials.data ? freshnessLabel(financials.data.freshness.as_of) : undefined;

  if (stats.length === 0) {
    return <p className="text-muted">No reported financials are available for this company yet.</p>;
  }

  return (
    <section aria-label="Key figures">
      <div className="grid grid-cols-2 gap-x-8 gap-y-5 sm:flex sm:flex-wrap sm:gap-x-12">
        {stats.map((stat) => (
          <Stat
            key={stat.name}
            label={metricLabel(stat.name)}
            value={stat.value}
            delta={<Delta value={stat.change} digits={1} points={stat.points} />}
            meta={{
              source: PRICE_BASED.includes(stat.name) ? "Market data and SEC filings" : "SEC filings (XBRL)",
              period: stat.period,
              formula: FORMULAS[stat.name],
              lastUpdated: updated,
            }}
          />
        ))}
      </div>
      <p className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-subtle">
        <span>Latest fiscal year, change on the year before</span>
        {financials.data && <FreshnessBadge freshness={financials.data.freshness} />}
        <DataStatus ticker={ticker} />
      </p>
    </section>
  );
}
