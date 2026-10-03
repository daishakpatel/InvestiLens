import { useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fiscalCalendarLabel, formatMetricValue, formatPercent, toNumber } from "../lib/format";
import type { MetricSeriesPoint } from "../types";

export interface ChartRow {
  period: string;
  periodEnd: string | null | undefined;
  value: number | null;
  yoy: number | null;
}

function toRows(points: MetricSeriesPoint[]): ChartRow[] {
  return points.map((p, i) => {
    const value = toNumber(p.value);
    const prev = i > 0 ? toNumber(points[i - 1]?.value ?? null) : null;
    const yoy = value !== null && prev !== null && prev !== 0 ? (value - prev) / prev : null;
    return { period: p.period, periodEnd: p.period_end, value, yoy };
  });
}

function ChartTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: { payload: ChartRow }[];
  unit: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="rounded-md border border-border bg-surface p-2 text-xs shadow-lg">
      <div className="font-medium">{fiscalCalendarLabel(row.period, row.periodEnd)}</div>
      <div>{formatMetricValue(row.value === null ? null : String(row.value), unit)}</div>
      {row.yoy !== null && <div className="text-muted">YoY {formatPercent(row.yoy)}</div>}
    </div>
  );
}

export function MetricChart({
  title,
  points,
  unit,
  kind = "bar",
  showYoY = false,
}: {
  title: string;
  points: MetricSeriesPoint[];
  unit: string;
  kind?: "bar" | "line";
  showYoY?: boolean;
}) {
  const [showTable, setShowTable] = useState(false);
  const rows = toRows(points);
  const axisTick = { fill: "var(--text-muted)", fontSize: 12 };

  return (
    <figure className="m-0">
      <figcaption className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <button
          type="button"
          aria-pressed={showTable}
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2"
        >
          {showTable ? "View chart" : "View data table"}
        </button>
      </figcaption>

      {showTable ? (
        <DataTable rows={rows} unit={unit} />
      ) : (
        <div
          role="img"
          aria-label={`${title} by fiscal period. Use “View data table” for exact values.`}
          className="h-64 w-full"
        >
          <ResponsiveContainer width="100%" height="100%">
            {kind === "line" ? (
              <LineChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="period" tick={axisTick} />
                <YAxis tick={axisTick} width={48} />
                <RTooltip content={<ChartTooltip unit={unit} />} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="var(--chart-1)"
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
                {showYoY && (
                  <Line
                    type="monotone"
                    dataKey="yoy"
                    stroke="var(--chart-2)"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                )}
              </LineChart>
            ) : (
              <ComposedChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
                <CartesianGrid stroke="var(--border)" vertical={false} />
                <XAxis dataKey="period" tick={axisTick} />
                <YAxis tick={axisTick} width={48} />
                <RTooltip
                  content={<ChartTooltip unit={unit} />}
                  cursor={{ fill: "var(--surface-2)" }}
                />
                <Bar dataKey="value" fill="var(--chart-1)" isAnimationActive={false} />
                {showYoY && (
                  <Line
                    type="monotone"
                    dataKey="yoy"
                    stroke="var(--chart-2)"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                )}
              </ComposedChart>
            )}
          </ResponsiveContainer>
        </div>
      )}
    </figure>
  );
}

function DataTable({ rows, unit }: { rows: ChartRow[]; unit: string }) {
  return (
    <div className="max-h-64 overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-surface-2 text-xs uppercase text-muted">
          <tr>
            <th scope="col" className="px-2 py-1">
              Period
            </th>
            <th scope="col" className="px-2 py-1">
              Ended
            </th>
            <th scope="col" className="px-2 py-1 text-right">
              Value
            </th>
            <th scope="col" className="px-2 py-1 text-right">
              YoY
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.period} className="border-t border-border">
              <td className="px-2 py-1">{r.period}</td>
              <td className="px-2 py-1">{r.periodEnd ?? "—"}</td>
              <td className="px-2 py-1 text-right tabular-nums">
                {formatMetricValue(r.value === null ? null : String(r.value), unit)}
              </td>
              <td className="px-2 py-1 text-right tabular-nums">
                {r.yoy === null ? "—" : formatPercent(r.yoy)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
