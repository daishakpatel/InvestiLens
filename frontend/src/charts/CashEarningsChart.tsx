import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { toNumber } from "../lib/format";
import type { QualityMeasure } from "../types";
import { ChartFrame } from "./ChartFrame";
import { ChartTooltip } from "./ChartTooltip";
import { ACTIVE_DOT, AXIS, BAR, BAR_CURSOR, GRID, LINE, ZERO_LINE } from "./chartTheme";
import { formatTick, formatValue, pickScale, shortPeriod } from "./series";

// Categorical hues, not green/red: none of these is a gain or a loss (FR-EQ-012).
const SERIES = [
  { key: "netIncome", label: "Net income", color: "var(--chart-1)" },
  { key: "operatingCashFlow", label: "Operating cash flow", color: "var(--chart-3)" },
  { key: "freeCashFlow", label: "Free cash flow", color: "var(--chart-5)" },
] as const;
const ACCRUALS_COLOR = "var(--chart-2)";

interface Row {
  period: string;
  label: string;
  netIncome: number | null;
  operatingCashFlow: number | null;
  freeCashFlow: number | null;
  accruals: number | null;
}

function input(measure: QualityMeasure | undefined, period: string, name: string): number | null {
  const point = measure?.points.find((p) => p.period === period);
  return toNumber(point?.inputs.find((i) => i.name === name)?.value);
}

/** The rows behind the chart: each year's figures, as the measures' own inputs carry them. */
export function cashEarningsRows(
  accruals: QualityMeasure | undefined,
  conversion: QualityMeasure | undefined,
): Row[] {
  return (accruals?.points ?? []).map((point) => ({
    period: point.period,
    label: shortPeriod(point.period),
    netIncome: input(accruals, point.period, "net_income"),
    operatingCashFlow: input(accruals, point.period, "operating_cash_flow"),
    freeCashFlow: input(conversion, point.period, "free_cash_flow"),
    accruals: toNumber(point.value),
  }));
}

/** Net income vs operating cash flow vs free cash flow per year, with the accruals ratio as a
 *  line (FR-EQ-014): the gap between the first two bars is what the line measures. */
export function CashEarningsChart({
  ticker,
  accruals,
  conversion,
}: {
  ticker: string;
  accruals: QualityMeasure | undefined;
  conversion: QualityMeasure | undefined;
}) {
  const rows = cashEarningsRows(accruals, conversion);
  const amounts = rows.flatMap((r) => [r.netIncome, r.operatingCashFlow, r.freeCashFlow]);
  const scale = pickScale(amounts);
  const hasData = amounts.some((v) => v !== null);
  const money = (v: number | null) => (v === null ? "N/A" : formatValue(v, "money"));
  const pct = (v: number | null) => (v === null ? "N/A" : formatValue(v, "percent"));

  return (
    <ChartFrame<Row>
      title="Net income, cash flow and free cash flow"
      description={`Net income, operating cash flow and free cash flow for ${ticker} by fiscal year, with the accruals ratio as a line. The same figures are available as a table.`}
      heightClass="h-64"
      state={hasData ? "ready" : "empty"}
      emptyMessage="Net income and cash flow are not reported for these years."
      table={{
        columns: [
          { key: "period", header: "Fiscal year", render: (r) => r.label },
          ...SERIES.map((s) => ({
            key: s.key,
            header: s.label,
            numeric: true,
            render: (r: Row) => money(r[s.key]),
          })),
          { key: "accruals", header: "Accruals ratio", numeric: true, render: (r) => pct(r.accruals) },
        ],
        rows,
        rowKey: (r) => r.period,
      }}
      csv={{
        filename: `${ticker}_cash_vs_earnings.csv`,
        headers: ["period", "net_income", "operating_cash_flow", "free_cash_flow", "accruals_ratio"],
        rows: rows.map((r) => [r.period, r.netIncome, r.operatingCashFlow, r.freeCashFlow, r.accruals]),
      }}
      footer={
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-caption text-muted">
          {SERIES.map((s) => (
            <li key={s.key} className="flex items-center gap-1.5">
              <span aria-hidden className="size-2 rounded-sm" style={{ background: s.color }} />
              {s.label}
            </li>
          ))}
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="h-0.5 w-3 rounded" style={{ background: ACCRUALS_COLOR }} />
            Accruals ratio (right axis)
          </li>
        </ul>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" {...AXIS} />
          <YAxis
            yAxisId="money"
            {...AXIS}
            width={56}
            tickFormatter={(v: number) => formatTick(v, "money", scale)}
          />
          <YAxis
            yAxisId="ratio"
            orientation="right"
            {...AXIS}
            width={44}
            tickFormatter={(v: number) => formatTick(v, "percent", scale)}
          />
          <ReferenceLine yAxisId="money" y={0} {...ZERO_LINE} />
          <Tooltip
            cursor={BAR_CURSOR}
            isAnimationActive={false}
            content={({ active, payload }) => {
              const row = active ? (payload?.[0]?.payload as Row | undefined) : undefined;
              if (!row) return null;
              return (
                <ChartTooltip
                  value={`Accruals ${pct(row.accruals)}`}
                  title={row.period}
                  lines={SERIES.map((s) => `${s.label}: ${money(row[s.key])}`)}
                />
              );
            }}
          />
          {SERIES.map((s) => (
            <Bar
              key={s.key}
              yAxisId="money"
              dataKey={s.key}
              fill={s.color}
              {...BAR}
              maxBarSize={14}
              isAnimationActive={false}
            />
          ))}
          <Line
            yAxisId="ratio"
            dataKey="accruals"
            type="monotone"
            stroke={ACCRUALS_COLOR}
            {...LINE}
            dot={false}
            activeDot={ACTIVE_DOT}
            connectNulls={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
