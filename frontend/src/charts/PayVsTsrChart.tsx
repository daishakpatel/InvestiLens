import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { PvpRow } from "../lib/governance";
import { ChartFrame } from "./ChartFrame";
import { ChartTooltip } from "./ChartTooltip";
import { ACTIVE_DOT, AXIS, BAR, BAR_CURSOR, GRID, LINE } from "./chartTheme";
import { formatTick, formatValue, pickScale } from "./series";

// Categorical hues: neither series is a gain or a loss.
const PAY_COLOR = "var(--chart-1)";
const TSR_COLOR = "var(--chart-2)";
const PEER_COLOR = "var(--chart-3)";

const money = (v: number | null) => (v === null ? "N/A" : formatValue(v, "money"));
const tsr = (v: number | null) => (v === null ? "N/A" : `$${v.toFixed(0)}`);

/** CEO compensation actually paid per fiscal year beside total shareholder return (the worth of
 *  $100 invested), as the proxy's Pay Versus Performance table tags them (FR-GV-012). */
export function PayVsTsrChart({ ticker, rows }: { ticker: string; rows: PvpRow[] }) {
  const scale = pickScale(rows.map((r) => r.actuallyPaid));
  return (
    <ChartFrame<PvpRow>
      title="CEO pay vs shareholder return"
      description={`Compensation actually paid to the ${ticker} CEO by fiscal year, with total shareholder return on $100 invested, for the company and its peer group. The same figures are available as a table.`}
      heightClass="h-60"
      state={rows.some((r) => r.actuallyPaid !== null || r.tsr !== null) ? "ready" : "empty"}
      emptyMessage="The proxy tags no pay-versus-performance figures."
      table={{
        columns: [
          { key: "year", header: "Fiscal year", render: (r) => r.label },
          { key: "cap", header: "CEO pay actually paid", numeric: true, render: (r) => money(r.actuallyPaid) },
          { key: "sct", header: "CEO total (table)", numeric: true, render: (r) => money(r.summaryTotal) },
          { key: "tsr", header: "TSR ($100)", numeric: true, render: (r) => tsr(r.tsr) },
          { key: "peer", header: "Peer TSR ($100)", numeric: true, render: (r) => tsr(r.peerTsr) },
        ],
        rows,
        rowKey: (r) => String(r.year),
      }}
      csv={{
        filename: `${ticker}_pay_vs_performance.csv`,
        headers: ["fiscal_year", "ceo_compensation_actually_paid", "ceo_summary_total", "tsr", "peer_tsr"],
        rows: rows.map((r) => [r.year, r.actuallyPaid, r.summaryTotal, r.tsr, r.peerTsr]),
      }}
      footer={
        <ul className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-caption text-muted">
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="size-2 rounded-sm" style={{ background: PAY_COLOR }} />
            CEO pay actually paid
          </li>
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="h-0.5 w-3 rounded" style={{ background: TSR_COLOR }} />
            TSR, $100 invested (right axis)
          </li>
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="h-0.5 w-3 rounded" style={{ background: PEER_COLOR }} />
            Peer group TSR
          </li>
        </ul>
      }
    >
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 8, right: 4, bottom: 0, left: 0 }}>
          <CartesianGrid {...GRID} />
          <XAxis dataKey="label" {...AXIS} />
          <YAxis yAxisId="pay" {...AXIS} width={56} tickFormatter={(v: number) => formatTick(v, "money", scale)} />
          <YAxis yAxisId="tsr" orientation="right" {...AXIS} width={48} tickFormatter={(v: number) => `$${v}`} />
          <Tooltip
            cursor={BAR_CURSOR}
            isAnimationActive={false}
            content={({ active, payload }) => {
              const row = active ? (payload?.[0]?.payload as PvpRow | undefined) : undefined;
              return row ? (
                <ChartTooltip
                  value={money(row.actuallyPaid)}
                  title={`CEO pay actually paid · ${row.label}`}
                  lines={[`TSR ${tsr(row.tsr)}`, `Peer TSR ${tsr(row.peerTsr)}`, "Source: proxy XBRL"]}
                />
              ) : null;
            }}
          />
          <Bar yAxisId="pay" dataKey="actuallyPaid" fill={PAY_COLOR} {...BAR} maxBarSize={28} isAnimationActive={false} />
          {(["tsr", "peerTsr"] as const).map((key) => (
            <Line
              key={key}
              yAxisId="tsr"
              dataKey={key}
              type="monotone"
              stroke={key === "tsr" ? TSR_COLOR : PEER_COLOR}
              {...LINE}
              dot={false}
              activeDot={ACTIVE_DOT}
              isAnimationActive={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
