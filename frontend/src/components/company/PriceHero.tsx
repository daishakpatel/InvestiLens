import { ArrowDownRight, ArrowUpRight, ChartLine, Download, Table2 } from "lucide-react";
import { useId, useMemo, useState } from "react";
import type { KeyboardEvent, PointerEvent } from "react";
import {
  Area,
  AreaChart,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";

import { NEGATIVE, POSITIVE, SURFACE } from "../../charts/chartTheme";
import { useApiStatus } from "../../lib/apiStatus";
import { downloadCsv, formatDate, formatPercent, formatUsd, toCsv } from "../../lib/format";
import { availableRanges, rangeChange, RANGES, sliceRange, toBars } from "../../lib/priceRange";
import type { PriceBar, RangeKey } from "../../lib/priceRange";
import { usePrices } from "../../lib/queries";
import { FreshnessBadge } from "../ui/Badge";
import { IconButton } from "../ui/Button";
import { DataTable } from "../ui/DataTable";
import type { Column } from "../ui/DataTable";
import { SegmentedControl } from "../ui/SegmentedControl";
import { Skeleton } from "../ui/Skeleton";
import { ErrorState } from "../ui/States";
import { useCompanyOutlet } from "./outletContext";

const PLOT = "h-[220px] md:h-[320px]";
const PAGE_STEP = 21; // about one month of sessions

const TABLE_COLUMNS: Column<PriceBar>[] = [
  { key: "date", header: "Date", render: (bar) => formatDate(bar.date) },
  { key: "close", header: "Close", numeric: true, render: (bar) => formatUsd(bar.close) },
  { key: "adj", header: "Adjusted close", numeric: true, render: (bar) => formatUsd(bar.adj) },
];

/** The date riding above the cursor. Anchored inward near either edge so it is never clipped. */
function CursorDate({
  viewBox,
  text,
  position,
}: {
  viewBox?: { x?: number };
  text: string;
  position: number; // 0 (left edge) … 1 (right edge)
}) {
  const anchor = position < 0.12 ? "start" : position > 0.88 ? "end" : "middle";
  return (
    <text x={viewBox?.x ?? 0} y={12} textAnchor={anchor} fontSize={12} fill="var(--text-muted)">
      {text}
    </text>
  );
}

function ChangeLine({
  abs,
  pct,
  caption,
}: {
  abs: number;
  pct: number | null;
  caption: string;
}) {
  const flat = abs === 0;
  const up = abs > 0;
  const Arrow = up ? ArrowUpRight : ArrowDownRight;
  const sign = up ? "+" : flat ? "" : "−";
  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-2 text-body">
      {/* Direction is carried by the sign and the arrow as well as the colour (UI-003). */}
      <span
        className={`tnum inline-flex items-center gap-1 font-medium ${
          flat ? "text-muted" : up ? "text-positive" : "text-negative"
        }`}
      >
        {!flat && <Arrow aria-hidden className="size-4" />}
        {sign}
        {formatUsd(Math.abs(abs))}
        {pct !== null && ` (${sign}${formatPercent(Math.abs(pct), 2)})`}
      </span>
      <span className="text-muted">{caption}</span>
    </p>
  );
}

/** The company page's lead: the price, how it has moved over a chosen range, and a line you can
 *  run a finger, a mouse, or the arrow keys along. End-of-day data, presented as such. */
export function PriceHero({ ticker }: { ticker: string }) {
  const prices = usePrices(ticker);
  const { online, reachable } = useApiStatus();
  const { quoteAnchor } = useCompanyOutlet();
  const gradientId = useId();
  const bars = useMemo(() => toBars(prices.data?.points), [prices.data]);
  const ranges = useMemo(() => availableRanges(bars), [bars]);
  const [chosen, setChosen] = useState<RangeKey | null>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const [view, setView] = useState<"chart" | "table">("chart");

  if (prices.isPending || (prices.isError && !(online && reachable))) {
    return (
      <div role="status" aria-label="Loading price">
        {/* Shaped like the loaded hero down to the range row and caption, so nothing beneath
            it moves when the prices arrive. */}
        <Skeleton className="h-12 w-52" />
        <Skeleton className="mt-3 w-64" />
        <Skeleton shape="chart" className={`mt-6 ${PLOT}`} />
        <Skeleton className="mt-3 h-7 w-52 pointer-coarse:h-10" />
        <Skeleton className="mt-3 h-8 w-full max-w-md sm:h-4" />
      </div>
    );
  }
  if (prices.isError) {
    return <ErrorState message="The price history could not be loaded." onRetry={() => void prices.refetch()} />;
  }

  const last = bars.at(-1);
  if (!last) {
    // No chart box, no dashes: say what is missing and let the rest of the page carry on.
    return <p className="text-muted">No price data is available for {ticker.toUpperCase()} yet.</p>;
  }

  const range = chosen && ranges.includes(chosen) ? chosen : ranges.includes("1Y") ? "1Y" : (ranges.at(-1) ?? null);
  const spec = RANGES.find((r) => r.key === range);
  const shown = spec ? sliceRange(bars, spec.months) : bars;
  const open = shown[0] ?? last;
  const phrase = spec ? spec.phrase : `since ${formatDate(open.date)}`;

  const at = cursor !== null ? (shown[cursor] ?? last) : last;
  const scrubbing = cursor !== null && shown[cursor] !== undefined;
  const change = rangeChange(shown, scrubbing ? cursor : shown.length - 1) ?? { abs: 0, pct: null };
  const overall = rangeChange(shown) ?? { abs: 0, pct: null };
  const color = overall.abs < 0 ? NEGATIVE : POSITIVE;

  const move = (index: number) => setCursor(Math.max(0, Math.min(shown.length - 1, index)));
  const onKeyDown = (event: KeyboardEvent) => {
    const from = cursor ?? shown.length - 1;
    const steps: Record<string, number> = {
      ArrowLeft: from - 1,
      ArrowRight: from + 1,
      PageDown: from - PAGE_STEP,
      PageUp: from + PAGE_STEP,
      Home: 0,
      End: shown.length - 1,
    };
    if (event.key === "Escape") return setCursor(null);
    const next = steps[event.key];
    if (next === undefined) return;
    event.preventDefault(); // arrows and Home/End would otherwise scroll the page
    move(next);
  };
  // Mouse, touch, and pen share one path. The line runs edge to edge with evenly spaced sessions,
  // so the pointer's horizontal position maps straight onto a session index.
  const scrubTo = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    move(Math.round(((event.clientX - box.left) / box.width) * (shown.length - 1)));
  };

  return (
    <section aria-label="Price">
      {/* While scrubbing, the figure is that day's adjusted close, to agree with the line. */}
      <div ref={quoteAnchor}>
        <p className="tnum text-display-s font-semibold md:text-display-l" data-testid="hero-price">
          {formatUsd(scrubbing ? at.adj : last.close)}
        </p>
        {/* Keyed by range: switching range replays a brief dip on the change beneath the price.
            Scrubbing does not, since the figures then change on every frame. */}
        <div key={range ?? "none"} className="animate-value">
          <ChangeLine
            abs={change.abs}
            pct={change.pct}
            caption={scrubbing ? `${formatDate(open.date)} to ${formatDate(at.date)}` : phrase}
          />
        </div>
      </div>

      {shown.length > 1 &&
        (view === "table" ? (
          <div className={`mt-6 ${PLOT}`}>
            <DataTable
              density="compact"
              fill
              label="Price history, as a table"
              columns={TABLE_COLUMNS}
              rows={[...shown].reverse()}
              rowKey={(bar) => bar.date}
            />
          </div>
        ) : (
          <div
            role="slider"
            tabIndex={0}
            aria-label={`${ticker.toUpperCase()} price, ${phrase}. Use the arrow keys to move through trading days.`}
            aria-valuemin={0}
            aria-valuemax={shown.length - 1}
            aria-valuenow={cursor ?? shown.length - 1}
            aria-valuetext={`${formatDate(at.date)}: ${formatUsd(at.adj)}`}
            onKeyDown={onKeyDown}
            onBlur={() => setCursor(null)}
            onPointerDown={scrubTo}
            onPointerMove={scrubTo}
            onPointerLeave={() => setCursor(null)}
            onPointerCancel={() => setCursor(null)}
            // A finger lifting ends the scrub; a mouse button releasing does not (it still hovers).
            onPointerUp={(event) => event.pointerType !== "mouse" && setCursor(null)}
            // pan-y: a vertical swipe still scrolls the page; a horizontal one scrubs the line.
            className={`mt-6 w-full touch-pan-y select-none rounded-control ${PLOT}`}
          >
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={shown} margin={{ top: 22, right: 0, bottom: 4, left: 0 }}>
                <defs>
                  <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={color} stopOpacity={0.14} />
                    <stop offset="100%" stopColor={color} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" hide />
                <YAxis hide domain={["dataMin", "dataMax"]} />
                {/* Where the range opened: the line above or below it is the gain or loss. */}
                <ReferenceLine y={open.adj} stroke="var(--text-subtle)" strokeDasharray="1 5" strokeLinecap="round" />
                <Area
                  dataKey="adj"
                  type="linear"
                  stroke={color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  fill={`url(#${gradientId})`}
                  dot={false}
                  activeDot={false}
                  isAnimationActive={false}
                />
                {scrubbing && (
                  <ReferenceLine
                    x={at.date}
                    stroke="var(--border-strong)"
                    label={
                      <CursorDate
                        text={formatDate(at.date)}
                        position={shown.length > 1 ? (cursor ?? 0) / (shown.length - 1) : 1}
                      />
                    }
                  />
                )}
                {scrubbing && (
                  <ReferenceDot x={at.date} y={at.adj} r={4} fill={color} stroke={SURFACE} strokeWidth={2} />
                )}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ))}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        {ranges.length > 1 && range ? (
          <SegmentedControl
            label="Price range"
            value={range}
            onValueChange={(next) => {
              setChosen(next);
              setCursor(null);
            }}
            options={ranges.map((key) => ({ value: key, label: key }))}
          />
        ) : (
          <span />
        )}
        {shown.length > 1 && (
          <div className="flex items-center">
            <IconButton
              size="sm"
              label={view === "chart" ? "View prices as a table" : "View prices as a chart"}
              aria-pressed={view === "table"}
              onClick={() => setView(view === "chart" ? "table" : "chart")}
            >
              {view === "chart" ? (
                <Table2 aria-hidden className="size-3.5" />
              ) : (
                <ChartLine aria-hidden className="size-3.5" />
              )}
            </IconButton>
            <IconButton
              size="sm"
              label="Download prices as CSV"
              onClick={() =>
                downloadCsv(
                  `${ticker.toUpperCase()}_prices_${range ?? "all"}.csv`,
                  toCsv(
                    ["date", "close", "adjusted_close"],
                    shown.map((bar) => [bar.date, bar.close, bar.adj]),
                  ),
                )
              }
            >
              <Download aria-hidden className="size-3.5" />
            </IconButton>
          </div>
        )}
      </div>

      <p className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-subtle">
        <span>
          End-of-day close · as of {formatDate(last.date)}
          {shown.length > 1 && " · the line shows split- and dividend-adjusted closes"}
        </span>
        {prices.data.freshness.freshness_status !== "fresh" && (
          <FreshnessBadge freshness={prices.data.freshness} />
        )}
      </p>
    </section>
  );
}
