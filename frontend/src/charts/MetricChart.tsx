import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as RTooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Column } from "../components/ui/DataTable";
import { Delta } from "../components/ui/Delta";
import { fiscalCalendarLabel, formatDate } from "../lib/format";
import { metricDisplay, metricKind, metricLabel } from "../lib/metricCatalog";
import type { MetricSeriesPoint } from "../types";
import { ChartFrame } from "./ChartFrame";
import {
  ACTIVE_DOT,
  AXIS,
  BAR,
  BAR_CURSOR,
  CROSSHAIR,
  GRID,
  INK,
  INK_STRONG,
  LINE,
  NEGATIVE,
  POSITIVE,
  ZERO_LINE,
} from "./chartTheme";
import { ChartTooltip } from "./ChartTooltip";
import { axisFor, formatTick, formatValue, pickScale, shortPeriod, toRows } from "./series";
import type { Display, SeriesRow } from "./series";

interface PlotRow extends SeriesRow {
  label: string;
}

const MARGIN = { top: 8, right: 4, bottom: 0, left: 0 };
const SOURCE = "Source: SEC filings";

function valueText(row: SeriesRow, display: Display): string {
  return row.value === null ? "N/A" : formatValue(row.value, display);
}

function changeText(row: SeriesRow, display: Display): string | null {
  if (row.change === null) return null;
  const sign = row.change > 0 ? "+" : row.change < 0 ? "−" : "";
  const size = (Math.abs(row.change) * 100).toFixed(1);
  return `${sign}${size}${display === "percent" ? " pts" : "%"} vs prior period`;
}

/** One metric over fiscal periods: bars for amounts, a line for ratios, always a single series in
 *  neutral ink. `showChange` adds a strip of period-over-period changes beneath, on its own scale
 *  (two measures never share an axis) and coloured by direction, since that series *is* a change. */
export function MetricChart({
  name,
  points,
  csvName,
  showChange = false,
  compact = false,
  href,
  loading = false,
  emptyMessage,
}: {
  name: string; // the API metric name; label, mark, and number format follow from it
  points: readonly MetricSeriesPoint[];
  csvName: string;
  showChange?: boolean;
  compact?: boolean; // Overview: no y-axis or grid, the latest value in the header instead
  href?: string;
  loading?: boolean;
  emptyMessage?: string;
}) {
  const title = metricLabel(name);
  const kind = metricKind(name);
  const display = metricDisplay(name, points[0]?.unit ?? "USD");
  const inPoints = display === "percent";
  const rows: PlotRow[] = toRows(points, display).map((row) => ({
    ...row,
    label: shortPeriod(row.period),
  }));
  const hasData = rows.some((row) => row.value !== null);
  const values = rows.map((row) => row.value);
  const scale = pickScale(values);
  const axis = axisFor(values, kind === "bar");
  const hasNegative = rows.some((row) => (row.value ?? 0) < 0);
  const latest = [...rows].reverse().find((row) => row.value !== null);
  // The change strip is a second plot; a shared id keeps the two hovers in step.
  const sync = showChange ? { syncId: `metric-${csvName}` } : {};

  const columns: Column<PlotRow>[] = [
    { key: "period", header: "Period", render: (row) => row.period },
    ...(rows.some((row) => row.periodEnd)
      ? [{ key: "ended", header: "Ended", render: (row: PlotRow) => (row.periodEnd ? formatDate(row.periodEnd) : "") }]
      : []),
    { key: "value", header: "Value", numeric: true, render: (row) => valueText(row, display) },
    {
      key: "change",
      header: "Change",
      numeric: true,
      render: (row) => <Delta value={row.change} digits={1} points={inPoints} />,
    },
  ];

  const tooltip = (
    <RTooltip
      isAnimationActive={false}
      cursor={kind === "line" ? CROSSHAIR : BAR_CURSOR}
      content={({ active, payload }) => {
        const row = active ? (payload?.[0]?.payload as PlotRow | undefined) : undefined;
        if (!row) return null;
        return (
          <ChartTooltip
            value={valueText(row, display)}
            title={`${title} · ${fiscalCalendarLabel(row.period, row.periodEnd)}`}
            lines={[changeText(row, display), SOURCE]}
          />
        );
      }}
    />
  );

  return (
    <ChartFrame
      title={title}
      {...(href ? { href } : {})}
      description={`${title} by fiscal period${latest ? `; latest ${latest.period}: ${valueText(latest, display)}` : ""}. The same figures are available as a table.`}
      heightClass={compact ? "h-36" : "h-56"}
      state={loading ? "loading" : hasData ? "ready" : "empty"}
      {...(emptyMessage ? { emptyMessage } : {})}
      summary={
        compact && latest ? (
          <span className="flex items-baseline gap-2 text-sm">
            <span className="text-muted">{valueText(latest, display)}</span>
            <Delta value={latest.change} digits={1} points={inPoints} />
          </span>
        ) : undefined
      }
      table={{ columns, rows, rowKey: (row) => row.period }}
      csv={{
        filename: `${csvName}.csv`,
        headers: ["period", "period_end", "value", "unit"],
        rows: points.map((point) => [point.period, point.period_end, point.value, point.unit]),
      }}
      footer={
        showChange && !compact ? (
          <div className="mt-1">
            <div className="h-12 w-full" aria-hidden>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows} margin={{ ...MARGIN, top: 2, left: 52 }} {...sync}>
                  <XAxis dataKey="label" hide />
                  <YAxis hide domain={["auto", "auto"]} />
                  <ReferenceLine y={0} {...ZERO_LINE} />
                  <Bar dataKey="change" maxBarSize={BAR.maxBarSize} isAnimationActive={false}>
                    {rows.map((row) => (
                      <Cell key={row.period} fill={(row.change ?? 0) < 0 ? NEGATIVE : POSITIVE} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="pl-[52px] text-caption text-subtle">
              Change vs prior period{inPoints ? ", in points" : ""}
            </p>
          </div>
        ) : undefined
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={MARGIN} {...sync}>
          {!compact && <CartesianGrid {...GRID} />}
          <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={12} />
          {!compact && (
            <YAxis
              {...AXIS}
              width={52}
              domain={axis.domain}
              ticks={axis.ticks}
              tickFormatter={(value: number) => formatTick(value, display, scale)}
            />
          )}
          {hasNegative && <ReferenceLine y={0} {...ZERO_LINE} />}
          {tooltip}
          {kind === "line" ? (
            <Line
              dataKey="value"
              type="monotone"
              stroke={INK}
              {...LINE}
              dot={rows.length === 1 ? ACTIVE_DOT : false}
              activeDot={ACTIVE_DOT}
              isAnimationActive={false}
            />
          ) : (
            <Bar
              dataKey="value"
              fill={INK}
              activeBar={{ fill: INK_STRONG }}
              {...BAR}
              isAnimationActive={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
