import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";

import type { Column } from "../components/ui/DataTable";
import { toNumber } from "../lib/format";
import { metricDisplay, metricLabel } from "../lib/metricCatalog";
import type { ComparisonCompany, ComparisonMetricRow } from "../types";
import { ChartFrame } from "./ChartFrame";
import { AXIS, BAR, BAR_CURSOR, GRID, INK, ZERO_LINE } from "./chartTheme";
import { ChartTooltip } from "./ChartTooltip";
import { axisFor, formatTick, formatValue, pickScale } from "./series";

interface Row {
  ticker: string;
  period: string;
  value: number | null;
}

/** One metric across the compared companies (§37.1). The companies are named on the axis, so the
 *  bars stay in neutral ink like every other single-measure chart: colour would add nothing. */
export function ComparisonBars({
  row,
  companies,
}: {
  row: ComparisonMetricRow;
  companies: readonly ComparisonCompany[];
}) {
  const title = metricLabel(row.metric_name);
  const display = metricDisplay(row.metric_name, row.unit);
  const periods = new Map(companies.map((c) => [c.ticker, c.fiscal_period ?? ""]));
  const rows: Row[] = row.cells.map((cell) => ({
    ticker: cell.ticker,
    period: periods.get(cell.ticker) ?? "",
    value: toNumber(cell.result.value),
  }));
  const values = rows.map((r) => r.value);
  const scale = pickScale(values);
  const axis = axisFor(values, true);
  const text = (r: Row) => (r.value === null ? "N/A" : formatValue(r.value, display));

  const columns: Column<Row>[] = [
    { key: "company", header: "Company", render: (r) => r.ticker },
    { key: "period", header: "Fiscal period", render: (r) => r.period },
    { key: "value", header: title, numeric: true, render: text },
  ];

  return (
    <ChartFrame
      title={title}
      description={`${title} by company: ${rows.map((r) => `${r.ticker} ${text(r)}`).join(", ")}. The same figures are available as a table.`}
      state={values.some((v) => v !== null) ? "ready" : "empty"}
      emptyMessage={`${title} is not available for these companies.`}
      table={{ columns, rows, rowKey: (r) => r.ticker }}
      csv={{
        filename: `compare_${row.metric_name}.csv`,
        headers: ["ticker", "fiscal_period", "value", "unit"],
        rows: row.cells.map((cell) => [cell.ticker, periods.get(cell.ticker), cell.result.value, row.unit]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="ticker" {...AXIS} />
          <YAxis
            {...AXIS}
            width={52}
            domain={axis.domain}
            ticks={axis.ticks}
            tickFormatter={(value: number) => formatTick(value, display, scale)}
          />
          {values.some((v) => (v ?? 0) < 0) && <ReferenceLine y={0} {...ZERO_LINE} />}
          <RTooltip
            isAnimationActive={false}
            cursor={BAR_CURSOR}
            content={({ active, payload }) => {
              const r = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
              return r ? <ChartTooltip value={text(r)} title={`${title} · ${r.ticker}`} lines={[r.period, "Source: SEC filings"]} /> : null;
            }}
          />
          <Bar dataKey="value" fill={INK} {...BAR} maxBarSize={40} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
