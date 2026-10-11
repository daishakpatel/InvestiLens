import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  header: ReactNode;
  numeric?: boolean; // right-aligned, tabular figures
  render: (row: Row) => ReactNode;
}

/** The standard table: sticky header, right-aligned numerals, row hover. Scrolls horizontally on
 *  narrow screens with the first column pinned. `startAtEnd` opens it scrolled to the last
 *  column, for tables that run oldest → newest and should show the newest first. `fill` makes
 *  it take its parent's height (a chart frame) instead of capping its own. When its content
 *  overflows, the scroll area becomes a labelled, focusable region so it can be scrolled from
 *  the keyboard (WCAG 2.1.1). */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  caption,
  density = "comfortable",
  startAtEnd = false,
  fill = false,
  label = "Data table",
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  caption?: ReactNode;
  density?: "comfortable" | "compact";
  startAtEnd?: boolean;
  fill?: boolean;
  label?: string; // names the scroll region for assistive tech
}) {
  const scroller = useRef<HTMLDivElement>(null);
  const [scrolls, setScrolls] = useState(false);
  const columnKeys = columns.map((column) => column.key).join("|");
  useLayoutEffect(() => {
    const element = scroller.current;
    if (!element) return;
    if (startAtEnd) element.scrollLeft = element.scrollWidth;
    const measure = () =>
      setScrolls(
        element.scrollWidth > element.clientWidth || element.scrollHeight > element.clientHeight,
      );
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [startAtEnd, columnKeys, rows.length]);

  const pad = density === "compact" ? "px-3 py-1.5" : "px-3 py-2.5";
  const align = (column: Column<Row>) => (column.numeric ? "text-right tnum" : "text-left");
  // The first column stays put while the rest scrolls beneath it; its edge is drawn so a
  // half-covered neighbour reads as scrolled under, not as clipped.
  const pinned = "sticky left-0 bg-bg border-r border-r-border/60";
  return (
    <div
      ref={scroller}
      {...(scrolls ? { tabIndex: 0, role: "region", "aria-label": label } : {})}
      className={`overflow-auto ${fill ? "h-full" : "max-h-[32rem]"}`}
    >
      <table className="w-full border-separate border-spacing-0 text-sm">
        {caption && <caption className="pb-2 text-left text-label text-muted">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column, i) => (
              <th
                key={column.key}
                scope="col"
                className={`sticky top-0 z-10 whitespace-nowrap border-b border-border bg-bg text-label font-medium text-muted ${pad} ${align(column)} ${i === 0 ? "left-0 z-20 border-r border-r-border/60" : ""}`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} className="group">
              {columns.map((column, i) => (
                <td
                  key={column.key}
                  className={`whitespace-nowrap border-b border-border/60 transition-colors group-hover:bg-surface ${pad} ${align(column)} ${i === 0 ? `${pinned} font-medium` : ""}`}
                >
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
