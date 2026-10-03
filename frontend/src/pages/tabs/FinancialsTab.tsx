import { useState } from "react";
import { useParams } from "react-router-dom";

import { MetricChart } from "../../charts/MetricChart";
import { AsyncContent, Panel } from "../../components/Panel";
import { Tooltip } from "../../components/primitives";
import { downloadCsv, toCsv } from "../../lib/format";
import { useFinancials, useMetricLineage } from "../../lib/queries";
import type { FinancialsResponse, MetricSeries } from "../../types";

interface ChartConfig {
  name: string;
  title: string;
  kind: "bar" | "line";
}

const CHARTS: ChartConfig[] = [
  { name: "revenue", title: "Revenue", kind: "bar" },
  { name: "gross_margin", title: "Gross Margin", kind: "line" },
  { name: "operating_income", title: "Operating Income", kind: "bar" },
  { name: "net_income", title: "Net Income", kind: "bar" },
  { name: "fcf", title: "Free Cash Flow", kind: "bar" },
  { name: "eps", title: "EPS", kind: "line" },
];
const METRIC_NAMES = CHARTS.map((c) => c.name);

const PERIODS: { value: string; label: string }[] = [
  { value: "FY", label: "Annual" },
  { value: "Q", label: "Quarterly" },
  { value: "TTM", label: "TTM" },
];

function seriesUnit(series: MetricSeries | undefined): string {
  return series?.points[0]?.unit ?? "USD";
}

function LineageTooltip({ ticker, series }: { ticker: string; series: MetricSeries }) {
  const [open, setOpen] = useState(false);
  const latest = series.points.at(-1)?.period ?? "";
  const lineage = useMetricLineage(ticker, series.metric_name, latest, open && latest !== "");

  return (
    <span
      onMouseEnter={() => setOpen(true)}
      onFocus={() => setOpen(true)}
      className="text-xs text-muted hover:text-text"
    >
      <Tooltip
        label={
          lineage.isPending ? (
            "Loading lineage…"
          ) : lineage.data && lineage.data.inputs.length > 0 ? (
            <div>
              <div className="font-medium">{lineage.data.formula_id}</div>
              <ul className="mt-1 space-y-0.5">
                {lineage.data.inputs.map((i) => (
                  <li key={i.name} className="text-muted">
                    {i.name}
                    {i.value ? `: ${i.value}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            "As-reported value (no derivation)."
          )
        }
      >
        ⓘ lineage
      </Tooltip>
    </span>
  );
}

function exportCsv(ticker: string, periodType: string, data: FinancialsResponse): void {
  const rows = data.series.flatMap((s) =>
    s.points.map((p) => [s.metric_name, p.period, p.period_end, p.value, p.unit]),
  );
  const csv = toCsv(["metric", "period", "period_end", "value", "unit"], rows);
  downloadCsv(`${ticker}_financials_${periodType}.csv`, csv);
}

export default function FinancialsTab() {
  const { ticker = "" } = useParams();
  const [periodType, setPeriodType] = useState("FY");
  const [showYoY, setShowYoY] = useState(false);
  const financials = useFinancials(ticker, METRIC_NAMES, periodType);

  return (
    <Panel
      title="Financials"
      freshness={financials.data?.freshness}
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <div role="group" aria-label="Period type" className="flex rounded-md border border-border">
            {PERIODS.map((p) => (
              <button
                key={p.value}
                type="button"
                aria-pressed={periodType === p.value}
                onClick={() => setPeriodType(p.value)}
                className={`px-2 py-1 text-xs ${
                  periodType === p.value ? "bg-primary text-primary-contrast" : "hover:bg-surface-2"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
          <label className="flex items-center gap-1 text-xs">
            <input type="checkbox" checked={showYoY} onChange={(e) => setShowYoY(e.target.checked)} />
            YoY overlay
          </label>
          <button
            type="button"
            disabled={!financials.data}
            onClick={() => financials.data && exportCsv(ticker, periodType, financials.data)}
            className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2 disabled:opacity-50"
          >
            Export CSV
          </button>
        </div>
      }
    >
      <AsyncContent
        query={financials}
        isEmpty={(d) => d.series.every((s) => s.points.length === 0)}
        emptyMessage={`No ${periodType} data available for these metrics.`}
      >
        {(data) => (
          <div className="grid grid-cols-1 gap-6 p-4 lg:grid-cols-2">
            {CHARTS.map((cfg) => {
              const series = data.series.find((s) => s.metric_name === cfg.name);
              const points = series?.points ?? [];
              return (
                <div key={cfg.name} className="rounded-lg border border-border p-3">
                  {points.length === 0 ? (
                    <div className="text-sm text-muted">
                      <div className="mb-1 font-medium text-text">{cfg.title}</div>
                      Not available for this period type.
                    </div>
                  ) : (
                    <>
                      <MetricChart
                        title={cfg.title}
                        points={points}
                        unit={seriesUnit(series)}
                        kind={cfg.kind}
                        showYoY={showYoY}
                      />
                      {series && (
                        <div className="mt-1 flex justify-end">
                          <LineageTooltip ticker={ticker} series={series} />
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </AsyncContent>
    </Panel>
  );
}
