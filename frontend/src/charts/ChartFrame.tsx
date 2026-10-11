import { ChartColumn, Download, Table2 } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { IconButton } from "../components/ui/Button";
import { DataTable } from "../components/ui/DataTable";
import type { Column } from "../components/ui/DataTable";
import { Skeleton } from "../components/ui/Skeleton";
import { downloadCsv, toCsv } from "../lib/format";

type Cell = string | number | null | undefined;

interface ChartFrameProps<Row> {
  title: string;
  href?: string; // makes the title a link (for example from Overview into Financials)
  summary?: ReactNode; // beside the title: the latest value, a delta
  /** What the chart shows, for assistive tech (the plot itself is one image). */
  description: string;
  heightClass?: string; // must include the x-axis band, so nothing scrolls inside the frame
  state?: "ready" | "loading" | "empty";
  emptyMessage?: string; // one sentence: which data is missing, and why
  table: { columns: Column<Row>[]; rows: Row[]; rowKey: (row: Row) => string };
  csv: { filename: string; headers: string[]; rows: Cell[][] };
  footer?: ReactNode;
  children: ReactNode; // the plot
}

/** The frame every chart sits in: title, the plot, and the two things FR-013 requires of any
 *  chart: the same data as a table, and a CSV download. No border, no background. */
export function ChartFrame<Row>({
  title,
  href,
  summary,
  description,
  heightClass = "h-56",
  state = "ready",
  emptyMessage = "No data available.",
  table,
  csv,
  footer,
  children,
}: ChartFrameProps<Row>) {
  const [view, setView] = useState<"chart" | "table">("chart");
  const ready = state === "ready";

  return (
    <figure className="m-0 min-w-0">
      <figcaption className="mb-3 flex min-h-7 items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
          <h3 className="text-sm font-medium text-text">
            {href ? (
              <Link to={href} className="hover:underline">
                {title}
              </Link>
            ) : (
              title
            )}
          </h3>
          {ready && summary}
        </div>
        {ready && (
          <div className="flex shrink-0 items-center">
            <IconButton
              size="sm"
              label={view === "chart" ? `View ${title} as a table` : `View ${title} as a chart`}
              aria-pressed={view === "table"}
              onClick={() => setView(view === "chart" ? "table" : "chart")}
            >
              {view === "chart" ? (
                <Table2 aria-hidden className="size-3.5" />
              ) : (
                <ChartColumn aria-hidden className="size-3.5" />
              )}
            </IconButton>
            <IconButton
              size="sm"
              label={`Download ${title} as CSV`}
              onClick={() => downloadCsv(csv.filename, toCsv(csv.headers, csv.rows))}
            >
              <Download aria-hidden className="size-3.5" />
            </IconButton>
          </div>
        )}
      </figcaption>

      {state === "loading" ? (
        <Skeleton shape="chart" className={heightClass} />
      ) : state === "empty" ? (
        // No reserved plot height: a missing chart is one sentence, not an empty box.
        <p className="max-w-sm text-sm text-muted">{emptyMessage}</p>
      ) : view === "table" ? (
        <div className={heightClass}>
          <DataTable density="compact" fill label={`${title}, as a table`} {...table} />
        </div>
      ) : (
        <div role="img" aria-label={description} className={`w-full ${heightClass}`}>
          {children}
        </div>
      )}
      {ready && footer}
    </figure>
  );
}
