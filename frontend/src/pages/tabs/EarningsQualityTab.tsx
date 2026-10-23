import { useParams } from "react-router-dom";

import { CashEarningsChart } from "../../charts/CashEarningsChart";
import { shortPeriod } from "../../charts/series";
import { useCitations } from "../../components/citations/CitationContext";
import { QualityCard } from "../../components/quality/QualityCard";
import { FreshnessBadge } from "../../components/ui/Badge";
import { DataTable } from "../../components/ui/DataTable";
import type { Column } from "../../components/ui/DataTable";
import { Section } from "../../components/ui/Section";
import { AsyncContent } from "../../components/ui/States";
import { formatQuality } from "../../lib/earningsQuality";
import { metricLabel } from "../../lib/metricCatalog";
import { useEarningsQuality } from "../../lib/queries";
import type { EarningsQualityResponse, QualityMeasure } from "../../types";

// The five cards (FR-EQ-011): a lead measure each, with a companion where one sharpens it.
const CARDS = [
  { title: "Accruals", lead: "accruals_ratio", companion: "accruals_ratio_bs" },
  { title: "Cash conversion", lead: "fcf_conversion", companion: "cash_conversion_cycle" },
  { title: "Dilution", lead: "dilution" },
  { title: "Beneish M-score", lead: "beneish_m" },
  { title: "Altman Z · Piotroski F", lead: "altman_z", companion: "piotroski_f" },
] as const;

function byName(data: EarningsQualityResponse) {
  return (name: string) => data.measures.find((m) => m.metric_name === name);
}

/** Five fiscal years of every measure; a cell without a value says why in one word. */
function TrendTable({ data }: { data: EarningsQualityResponse }) {
  const columns: Column<QualityMeasure>[] = [
    { key: "measure", header: "Measure", render: (m) => m.label },
    ...data.fiscal_years.map(
      (year): Column<QualityMeasure> => ({
        key: String(year),
        header: shortPeriod(`FY${year}`),
        numeric: true,
        render: (m) => {
          const point = m.points.find((p) => p.fiscal_year === year);
          if (!point || point.status === "insufficient_data")
            return <span className="text-subtle">Insufficient</span>;
          if (point.status === "not_applicable") return <span className="text-subtle">N/A</span>;
          return formatQuality(m.metric_name, point.value);
        },
      }),
    ),
  ];
  return (
    <DataTable
      density="compact"
      startAtEnd
      label="Earnings quality by fiscal year"
      columns={columns}
      rows={data.measures}
      rowKey={(m) => m.metric_name}
    />
  );
}

/** Every number behind the latest figures, each opening its source (CIT-003, FR-EQ-011). */
function Inputs({ data }: { data: EarningsQualityResponse }) {
  const { open } = useCitations();
  return (
    <div className="divide-y divide-border">
      {data.measures.map((measure) => {
        const point = measure.points.at(-1);
        // A measure that does not apply used nothing, so it has no inputs to show.
        const inputs = point?.status === "not_applicable" ? [] : (point?.inputs.filter((i) => i.source_id) ?? []);
        if (!point || inputs.length === 0) return null;
        return (
          <details key={measure.metric_name} className="group py-2" data-testid={`inputs-${measure.metric_name}`}>
            <summary className="cursor-pointer text-sm text-text marker:text-subtle">
              {measure.label} · {shortPeriod(point.period)}
              <span className="text-subtle"> · {inputs.length} inputs</span>
            </summary>
            <ul className="mt-2 grid gap-x-8 gap-y-1 pb-2 sm:grid-cols-2">
              {inputs.map((input) => (
                <li key={input.name} className="flex min-w-0 items-baseline justify-between gap-3 text-caption">
                  <span className="truncate text-muted">
                    {input.name.startsWith("prior_")
                      ? `${metricLabel(input.name.slice(6))} (prior year)`
                      : metricLabel(input.name)}
                  </span>
                  <button
                    type="button"
                    onClick={() => open(input.source_id ?? "")}
                    className="tnum shrink-0 text-text underline decoration-border-strong underline-offset-2 hover:decoration-text"
                    aria-label={`Open source ${input.source_id ?? ""}`}
                  >
                    {input.value === null || input.value === undefined
                      ? "N/A"
                      : formatInput(input.name, input.value)}
                  </button>
                </li>
              ))}
            </ul>
          </details>
        );
      })}
    </div>
  );
}

const PER_SHARE_OR_COUNT = /shares/;

function formatInput(name: string, value: string): string {
  const n = Number(value);
  if (!Number.isFinite(n)) return value;
  if (PER_SHARE_OR_COUNT.test(name)) return `${(n / 1e6).toLocaleString("en-US", { maximumFractionDigits: 0 })}M shares`;
  if (Math.abs(n) < 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 4 });
  const sign = n < 0 ? "−" : "";
  const size = Math.abs(n);
  return size >= 1e9 ? `${sign}$${(size / 1e9).toFixed(2)}B` : `${sign}$${(size / 1e6).toFixed(1)}M`;
}

/** Earnings quality: do reported earnings turn into cash, and does the accounting look
 *  aggressive? Screening signals with their inputs, never conclusions (§37.7). */
export default function EarningsQualityTab() {
  const { ticker = "" } = useParams();
  const quality = useEarningsQuality(ticker);
  return (
    <AsyncContent
      query={quality}
      isEmpty={(d) => d.fiscal_years.length === 0}
      emptyMessage="No fiscal years are stored for this company yet, so there is nothing to score."
    >
      {(data) => {
        const find = byName(data);
        return (
          <div className="space-y-16">
            <div>
              <p className="mb-6 flex flex-wrap items-center gap-x-3 text-caption text-subtle">
                <span>
                  Signals to investigate, not conclusions. Computed from SEC filings for each fiscal
                  year; open any input to see where it came from.
                </span>
                <FreshnessBadge freshness={data.freshness} />
              </p>
              <div className="grid gap-x-8 gap-y-8 sm:grid-cols-2 lg:grid-cols-5">
                {CARDS.map((card) => {
                  const lead = find(card.lead);
                  if (!lead) return null;
                  return (
                    <QualityCard
                      key={card.lead}
                      title={card.title}
                      lead={lead}
                      companion={"companion" in card ? find(card.companion) : undefined}
                    />
                  );
                })}
              </div>
              {data.notes.length > 0 && (
                <p className="mt-6 text-caption text-subtle">{data.notes.join(" ")}</p>
              )}
            </div>

            <Section title="Cash vs earnings">
              <div className="pt-6">
                <CashEarningsChart
                  ticker={data.ticker}
                  accruals={find("accruals_ratio")}
                  conversion={find("fcf_conversion")}
                />
              </div>
            </Section>

            <Section title="Five-year trend">
              <div className="pt-4">
                <TrendTable data={data} />
              </div>
            </Section>

            <Section title="Inputs">
              <p className="pt-4 text-caption text-subtle">
                Every figure behind the latest year's measures. Select a value to open its source.
              </p>
              <Inputs data={data} />
            </Section>
          </div>
        );
      }}
    </AsyncContent>
  );
}
