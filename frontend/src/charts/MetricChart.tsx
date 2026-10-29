import {
  Bar,
  CartesianGrid,
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
import { fiscalCalendarLabel, formatDate, toNumber } from "../lib/format";
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
import {
  axisFor,
  formatTick,
  formatValue,
  growthSplit,
  pickScale,
  shortPeriod,
  toRows,
  trendByQuarter,
} from "./series";
import type { Display, GrowthSplit, SeriesRow } from "./series";

interface PlotRow extends SeriesRow, GrowthSplit {
  label: string;
  trend: number | null; // the TTM ending with this quarter, when a trend is drawn
  trendSourceId: string | null;
}

const MARGIN = { top: 8, right: 4, bottom: 0, left: 0 };
const SOURCE = "Source: SEC filings";

function valueText(row: SeriesRow, display: Display): string {
  return row.value === null ? "N/A" : formatValue(row.value, display);
}

function sourceText(sourceId: string | null): string {
  return sourceId ? `Source: ${sourceId}` : SOURCE;
}

function changeText(row: SeriesRow, display: Display): string | null {
  if (row.change === null) return null;
  const sign = row.change > 0 ? "+" : row.change < 0 ? "−" : "";
  const size = (Math.abs(row.change) * 100).toFixed(1);
  return `${sign}${size}${display === "percent" ? " pts" : "%"} vs prior period`;
}

/** The hover lines for a capped bar: where the prior period stood, and exactly what was added or
 *  lost since, in the metric's own unit and as a change. */
function capLines(row: PlotRow, display: Display): string[] {
  if (row.prior === null || (row.added === null && row.lost === null)) return [];
  const pct = changeText(row, display)?.replace(" vs prior period", "") ?? "";
  return [
    `Prior period ${formatValue(row.prior, display)}`,
    row.added !== null
      ? `Added ${formatValue(row.added, display)} (${pct})`
      : `Lost ${formatValue(row.lost ?? 0, display)} (${pct})`,
  ];
}

const LOST = { fill: "transparent", stroke: NEGATIVE, strokeWidth: 1.5, strokeDasharray: "3 2" } as const;

function KeyMark({ className }: { className: string }) {
  return <span aria-hidden className={`inline-block size-2.5 rounded-[2px] ${className}`} />;
}

/** One metric over fiscal periods: bars for amounts, a line for ratios, always a single series in
 *  neutral ink. `showChange` caps each bar with its growth on the same axis: grey up to the prior
 *  period's level, a green cap for what was added, a dashed outline for what was lost. A ratio's
 *  line shows its latest change beside the title; every point's change is in the tooltip.
 *  `trend` (quarterly bars only) draws the trailing-twelve-month figure as a line over the bars:
 *  the same measure in the same unit, so it shares their axis (FR-QT-012). */
export function MetricChart({
  name,
  points,
  csvName,
  showChange = false,
  compact = false,
  href,
  loading = false,
  emptyMessage,
  trend,
  note,
}: {
  name: string; // the API metric name; label, mark, and number format follow from it
  points: readonly MetricSeriesPoint[];
  csvName: string;
  showChange?: boolean;
  compact?: boolean; // Overview: no y-axis or grid, the latest value in the header instead
  href?: string;
  loading?: boolean;
  emptyMessage?: string;
  trend?: readonly MetricSeriesPoint[]; // TTM points, matched to the quarter each ends with
  note?: string | null; // one line beneath the plot, e.g. "3 of 4 quarters available"
}) {
  const title = metricLabel(name);
  const kind = metricKind(name);
  const display = metricDisplay(name, points[0]?.unit ?? "USD");
  const inPoints = display === "percent";
  const ttm = trend && kind === "bar" ? trendByQuarter(trend) : null;
  const rows: PlotRow[] = toRows(points, display).map((row, i, all) => {
    const point = ttm?.get(row.period);
    return {
      ...row,
      ...growthSplit(row.value, i > 0 ? (all[i - 1]?.value ?? null) : null),
      label: shortPeriod(row.period),
      trend: point ? toNumber(point.value) : null,
      trendSourceId: point?.source_id ?? null,
    };
  });
  const hasData = rows.some((row) => row.value !== null);
  const values = [...rows.map((row) => row.value), ...rows.map((row) => row.trend)];
  const scale = pickScale(values);
  const axis = axisFor(values, kind === "bar");
  const hasNegative = rows.some((row) => (row.value ?? 0) < 0);
  const latest = [...rows].reverse().find((row) => row.value !== null);
  const growth = showChange && !compact;
  const caps = growth && kind === "bar";

  const columns: Column<PlotRow>[] = [
    { key: "period", header: "Period", render: (row) => row.period },
    ...(rows.some((row) => row.periodEnd)
      ? [{ key: "ended", header: "Ended", render: (row: PlotRow) => (row.periodEnd ? formatDate(row.periodEnd) : "") }]
      : []),
    { key: "value", header: "Value", numeric: true, render: (row) => valueText(row, display) },
    ...(ttm
      ? [
          {
            key: "ttm",
            header: "TTM",
            numeric: true,
            render: (row: PlotRow) => (row.trend === null ? "" : formatValue(row.trend, display)),
          },
        ]
      : []),
    // A compact quarterly table has no room for a fifth column; its header shows the change.
    ...(compact && ttm
      ? []
      : [
          {
            key: "change",
            header: "Change",
            numeric: true,
            render: (row: PlotRow) => <Delta value={row.change} digits={1} points={inPoints} />,
          },
        ]),
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
            lines={[
              ...(caps && row.prior !== null && (row.added !== null || row.lost !== null)
                ? capLines(row, display)
                : [changeText(row, display)]),
              row.formula,
              sourceText(row.sourceId),
              row.trend !== null && `TTM ${formatValue(row.trend, display)} · ${sourceText(row.trendSourceId)}`,
            ]}
          />
        );
      }}
    />
  );

  const capKey = (
    <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-subtle">
      <span className="inline-flex items-center gap-1.5">
        <KeyMark className="bg-(--chart-ink)" />
        Prior period
      </span>
      <span className="inline-flex items-center gap-1.5">
        <KeyMark className="bg-positive" />
        Added
      </span>
      <span className="inline-flex items-center gap-1.5">
        <KeyMark className="border-[1.5px] border-dashed border-negative" />
        Lost
      </span>
    </p>
  );

  return (
    <ChartFrame
      title={title}
      {...(href ? { href } : {})}
      description={`${title} by fiscal period${ttm ? ", with the trailing twelve months as a line" : ""}${caps ? ", each bar split into the prior period's level and the amount added or lost" : ""}${latest ? `; latest ${latest.period}: ${valueText(latest, display)}` : ""}. The same figures are available as a table.`}
      heightClass={compact ? "h-36" : "h-56"}
      state={loading ? "loading" : hasData ? "ready" : "empty"}
      {...(emptyMessage ? { emptyMessage } : {})}
      summary={
        compact && latest ? (
          <span className="flex items-baseline gap-2 text-sm">
            <span className="text-muted">{valueText(latest, display)}</span>
            <Delta value={latest.change} digits={1} points={inPoints} />
          </span>
        ) : growth && latest && latest.change !== null ? (
          <span className="flex items-baseline gap-2 text-sm">
            <span className="text-subtle">{latest.label}</span>
            <Delta value={latest.change} digits={1} points={inPoints} />
          </span>
        ) : undefined
      }
      table={{ columns, rows, rowKey: (row) => row.period }}
      csv={{
        filename: `${csvName}.csv`,
        headers: ["period", "period_end", "value", "unit", "source_id", ...(ttm ? ["ttm"] : [])],
        rows: points.map((point) => [
          point.period,
          point.period_end,
          point.value,
          point.unit,
          point.source_id,
          ...(ttm ? [ttm.get(point.period)?.value ?? null] : []),
        ]),
      }}
      footer={
        <>
          {caps && capKey}
          {(ttm || note) && (
            <p className="mt-2 text-caption text-subtle">
              {[ttm && "Bars are quarters; the line is the trailing twelve months.", note]
                .filter(Boolean)
                .join(" ")}
            </p>
          )}
        </>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={MARGIN}>
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
          ) : caps ? (
            [
              <Bar key="base" dataKey="base" stackId="growth" fill={INK} maxBarSize={BAR.maxBarSize} isAnimationActive={false} />,
              <Bar key="added" dataKey="added" stackId="growth" fill={POSITIVE} {...BAR} isAnimationActive={false} />,
              <Bar key="lost" dataKey="lost" stackId="growth" {...LOST} {...BAR} isAnimationActive={false} />,
            ]
          ) : (
            <Bar
              dataKey="value"
              fill={INK}
              activeBar={{ fill: INK_STRONG }}
              {...BAR}
              isAnimationActive={false}
            />
          )}
          {ttm && (
            <Line
              dataKey="trend"
              type="monotone"
              stroke={INK_STRONG}
              {...LINE}
              dot={false}
              activeDot={ACTIVE_DOT}
              isAnimationActive={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
