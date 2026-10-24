import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";

import { useCitations } from "../components/citations/CitationContext";
import type { Column } from "../components/ui/DataTable";
import type { LadderRow } from "../lib/footnotes";
import { ChartFrame } from "./ChartFrame";
import { AXIS, BAR, BAR_CURSOR, GRID, INK } from "./chartTheme";
import { ChartTooltip } from "./ChartTooltip";
import { axisFor, formatTick, formatValue, pickScale } from "./series";

/** One measure as bars, each opening its source: a maturity or payment schedule by year from
 *  the fiscal year end (FR-FN-012), or a figure by fiscal year (FR-GV-011). Neutral ink. */
export function LadderChart({
  title,
  rows,
  period,
  slug,
  columnHeader = "Due in",
  source = "XBRL",
}: {
  title: string;
  rows: LadderRow[];
  period: string;
  slug: string;
  columnHeader?: string; // what each bar is: a window from the year end, or a fiscal year
  source?: string;
}) {
  const { open } = useCitations();
  const values = rows.map((r) => r.value);
  const scale = pickScale(values);
  const axis = axisFor(values, true);
  const text = (r: LadderRow) => formatValue(r.value, "money");
  const columns: Column<LadderRow>[] = [
    { key: "window", header: columnHeader, render: (r) => r.window },
    {
      key: "value",
      header: period,
      numeric: true,
      render: (r) => (
        <button
          type="button"
          onClick={() => open(r.sourceId)}
          className="underline decoration-border-strong underline-offset-2 hover:decoration-text"
          aria-label={`${r.window}: ${text(r)}. Open source`}
        >
          {text(r)}
        </button>
      ),
    },
  ];
  return (
    <ChartFrame
      title={title}
      description={`${title} as of ${period}: ${rows.map((r) => `${r.window} ${text(r)}`).join(", ")}. The same figures are available as a table.`}
      table={{ columns, rows, rowKey: (r) => r.window }}
      csv={{
        filename: `${slug}.csv`,
        headers: ["due_in", "value_usd", "source_id"],
        rows: rows.map((r) => [r.window, r.value, r.sourceId]),
      }}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="window" {...AXIS} />
          <YAxis
            {...AXIS}
            width={52}
            domain={axis.domain}
            ticks={axis.ticks}
            tickFormatter={(value: number) => formatTick(value, "money", scale)}
          />
          <RTooltip
            isAnimationActive={false}
            cursor={BAR_CURSOR}
            content={({ active, payload }) => {
              const r = active ? (payload?.[0]?.payload as LadderRow | undefined) : undefined;
              return r ? <ChartTooltip value={text(r)} title={`${title} · ${r.window}`} lines={[period, `Source: ${source}`]} /> : null;
            }}
          />
          <Bar
            dataKey="value"
            fill={INK}
            {...BAR}
            maxBarSize={40}
            isAnimationActive={false}
            cursor="pointer"
            onClick={(entry: { payload?: LadderRow }) => entry.payload && open(entry.payload.sourceId)}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
