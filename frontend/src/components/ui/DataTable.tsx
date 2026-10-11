import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  header: string;
  numeric?: boolean; // right-aligned, tabular figures
  render: (row: Row) => ReactNode;
}

/** The standard table: sticky header, right-aligned numerals, row hover. Scrolls horizontally on
 *  narrow screens with the first column pinned. */
export function DataTable<Row>({
  columns,
  rows,
  rowKey,
  caption,
  density = "comfortable",
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  caption?: string;
  density?: "comfortable" | "compact";
}) {
  const pad = density === "compact" ? "px-3 py-1.5" : "px-3 py-2.5";
  const align = (column: Column<Row>) => (column.numeric ? "text-right tnum" : "text-left");
  const pinned = "sticky left-0 bg-bg"; // first column stays put while the rest scrolls
  return (
    <div className="max-h-[32rem] overflow-auto">
      <table className="w-full border-separate border-spacing-0 text-sm">
        {caption && <caption className="pb-2 text-left text-label text-muted">{caption}</caption>}
        <thead>
          <tr>
            {columns.map((column, i) => (
              <th
                key={column.key}
                scope="col"
                className={`sticky top-0 z-10 border-b border-border bg-bg text-label font-medium text-muted ${pad} ${align(column)} ${i === 0 ? "left-0 z-20" : ""}`}
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
                  className={`border-b border-border/60 transition-colors group-hover:bg-surface ${pad} ${align(column)} ${i === 0 ? `${pinned} font-medium` : ""}`}
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
