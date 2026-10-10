import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatMetricValue, toNumber } from "../lib/format";
import type { ComparisonCell } from "../types";

// One chart per metric (one axis — never mixing scales, per the dataviz rules). Companies are the
// categories; each keeps a fixed colour across the small-multiple grid so identity is consistent.
const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)", "var(--chart-6)"];

interface Row {
  ticker: string;
  value: number | null;
  color: string;
}

function CellTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: { payload: Row }[];
  unit: string;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="rounded-md border border-border bg-surface p-2 text-xs shadow-lg">
      <div className="font-medium">{row.ticker}</div>
      <div>{formatMetricValue(row.value === null ? null : String(row.value), unit)}</div>
    </div>
  );
}

export function ComparisonBars({
  metricName,
  unit,
  cells,
}: {
  metricName: string;
  unit: string;
  cells: ComparisonCell[];
}) {
  const [showTable, setShowTable] = useState(false);
  const rows: Row[] = cells.map((c, i) => ({
    ticker: c.ticker,
    value: toNumber(c.result.value),
    color: COLORS[i % COLORS.length] ?? "var(--chart-1)",
  }));
  const hasData = rows.some((r) => r.value !== null);
  const axisTick = { fill: "var(--text-muted)", fontSize: 12 };

  return (
    <figure className="m-0">
      <figcaption className="mb-2 flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{metricName}</span>
        <button
          type="button"
          aria-pressed={showTable}
          onClick={() => setShowTable((v) => !v)}
          className="rounded-md border border-border px-2 py-1 text-xs hover:bg-surface-2"
        >
          {showTable ? "Chart" : "Table"}
        </button>
      </figcaption>
      {!hasData ? (
        <p className="py-8 text-center text-sm text-muted">No data for this period.</p>
      ) : showTable ? (
        <table className="w-full text-left text-sm">
          <tbody>
            {rows.map((r) => (
              <tr key={r.ticker} className="border-t border-border">
                <td className="px-2 py-1">{r.ticker}</td>
                <td className="px-2 py-1 text-right tabular-nums">
                  {formatMetricValue(r.value === null ? null : String(r.value), unit)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div
          role="img"
          aria-label={`${metricName} by company. Use the Table toggle for exact values.`}
          className="h-48 w-full"
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
              <CartesianGrid stroke="var(--border)" vertical={false} />
              <XAxis dataKey="ticker" tick={axisTick} />
              <YAxis tick={axisTick} width={52} />
              <RTooltip content={<CellTooltip unit={unit} />} cursor={{ fill: "var(--surface-2)" }} />
              <Bar dataKey="value" isAnimationActive={false} radius={[4, 4, 0, 0]}>
                {rows.map((r) => (
                  <Cell key={r.ticker} fill={r.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </figure>
  );
}
