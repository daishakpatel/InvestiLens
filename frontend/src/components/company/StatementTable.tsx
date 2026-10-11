import { Download } from "lucide-react";
import { useState } from "react";
import type { ReactNode } from "react";

import { formatCell, formatValue, pickTableScale, shortPeriod } from "../../charts/series";
import type { Display } from "../../charts/series";
import { downloadCsv, toCsv, toNumber } from "../../lib/format";
import { metricDisplay, metricLabel, reasonText } from "../../lib/metricCatalog";
import { useMetricLineage } from "../../lib/queries";
import type { MetricSeries } from "../../types";
import { IconButton } from "../ui/Button";
import { DataTable } from "../ui/DataTable";
import type { Column } from "../ui/DataTable";
import { Tooltip } from "../ui/Tooltip";

interface Row {
  name: string;
  display: Display;
  values: Map<string, number | null>; // period → value; null = N/A, absent = not reported
}

/** Fiscal periods in time order: "FY2025" < "Q4-FY2025" < "FY2026". */
function periodOrder(period: string): number {
  const year = Number(/FY(\d{4})/.exec(period)?.[1] ?? 0);
  const quarter = Number(/Q(\d)/.exec(period)?.[1] ?? 0);
  return year * 10 + quarter;
}

/** Where a figure comes from (CIT-003), or why there is none (DR-041). Fetched when first shown. */
function Lineage({ ticker, name, period }: { ticker: string; name: string; period: string }) {
  const lineage = useMetricLineage(ticker, name, period, true);
  if (lineage.isPending) return <span className="text-muted">Loading lineage…</span>;
  if (lineage.isError) return <span className="text-muted">Lineage is unavailable.</span>;
  const { formula_id, formula_version, inputs, warnings, value, unit } = lineage.data;
  const amount = toNumber(value);
  return (
    <div className="max-w-64 space-y-1 text-left">
      <div className="font-medium">
        {metricLabel(name)} · {period}
      </div>
      {warnings.length > 0 ? (
        <div className="text-warning">{reasonText(warnings[0])}</div>
      ) : (
        amount !== null && <div className="tnum">{formatValue(amount, metricDisplay(name, unit))}</div>
      )}
      {inputs.length > 0 ? (
        <>
          <div className="text-muted">
            Formula: {formula_id}
            {formula_version ? ` (${formula_version})` : ""}
          </div>
          <ul className="text-muted">
            {inputs.map((input) => (
              <li key={input.name}>
                {metricLabel(input.name)}
                {input.source_id ? ` · filing ${input.source_id}` : ""}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <div className="text-muted">As reported in SEC filings (XBRL)</div>
      )}
    </div>
  );
}

/** A cell that explains itself on hover. The tooltip machinery is mounted only once the pointer
 *  arrives: a statement can hold several hundred cells, and almost none are ever hovered. */
function Figure({
  ticker,
  name,
  period,
  children,
}: {
  ticker: string;
  name: string;
  period: string;
  children: ReactNode;
}) {
  const [armed, setArmed] = useState(false);
  const [open, setOpen] = useState(false);
  if (!armed) return <span onPointerEnter={() => setArmed(true)}>{children}</span>;
  return (
    <Tooltip
      plain
      focusable={false}
      onOpenChange={setOpen}
      label={open ? <Lineage ticker={ticker} name={name} period={period} /> : null}
    >
      {children}
    </Tooltip>
  );
}

/** The metric's name, with the lineage of its latest period on hover or keyboard focus: the
 *  route to formulas and N/A reasons for anyone not using a pointer. */
function MetricName({ ticker, name, period }: { ticker: string; name: string; period: string }) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip
      onOpenChange={setOpen}
      label={open ? <Lineage ticker={ticker} name={name} period={period} /> : null}
    >
      {metricLabel(name)}
    </Tooltip>
  );
}

/** A financial statement: metrics down the side, fiscal periods across, newest on the right.
 *  Amounts share one scale, named in the caption; scaling happens here, at display time only. */
export function StatementTable({
  ticker,
  title,
  names,
  series,
  periodNoun,
}: {
  ticker: string;
  title: string;
  names: string[];
  series: MetricSeries[];
  periodNoun: string; // "Fiscal years", "Fiscal quarters"
}) {
  const rows: Row[] = names.flatMap((name) => {
    const found = series.find((s) => s.metric_name === name);
    const first = found?.points[0];
    if (!found || !first) return []; // nothing reported for this period type: leave the row out
    return [
      {
        name,
        display: metricDisplay(name, first.unit),
        values: new Map(found.points.map((point) => [point.period, toNumber(point.value)])),
      },
    ];
  });
  if (rows.length === 0) return null;

  const periods = [...new Set(rows.flatMap((row) => [...row.values.keys()]))].sort(
    (a, b) => periodOrder(a) - periodOrder(b),
  );
  const latest = periods.at(-1) ?? "";
  const amounts = rows
    .filter((row) => row.display === "money")
    .flatMap((row) => [...row.values.values()]);
  const scale = pickTableScale(amounts);

  const columns: Column<Row>[] = [
    {
      key: "metric",
      header: title,
      render: (row) => <MetricName ticker={ticker} name={row.name} period={latest} />,
    },
    ...periods.map(
      (period): Column<Row> => ({
        key: period,
        header: shortPeriod(period),
        numeric: true,
        render: (row) => {
          if (!row.values.has(period)) return null;
          const value = row.values.get(period) ?? null;
          return (
            <Figure ticker={ticker} name={row.name} period={period}>
              {value === null ? (
                <span className="text-subtle">N/A</span>
              ) : (
                formatCell(value, row.display, scale)
              )}
            </Figure>
          );
        },
      }),
    ),
  ];

  const hasAmounts = amounts.some((value) => value !== null);
  const hasPerShare = rows.some((row) => row.display === "perShare");
  const caption = [
    hasAmounts && `US dollars in ${scale.word}`,
    hasPerShare && "per-share amounts in dollars",
    `${periodNoun}, newest on the right`,
    "hover a figure for its source",
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div>
      <div className="mb-1 flex items-center justify-between gap-3">
        <p className="text-caption text-subtle">{caption}</p>
        <IconButton
          size="sm"
          label={`Download the ${title.toLowerCase()} table as CSV`}
          onClick={() =>
            downloadCsv(
              `${ticker}_${title.toLowerCase().replace(/\s+/g, "_")}.csv`,
              toCsv(
                ["metric", ...periods],
                rows.map((row) => [row.name, ...periods.map((period) => row.values.get(period))]),
              ),
            )
          }
        >
          <Download aria-hidden className="size-3.5" />
        </IconButton>
      </div>
      <DataTable
        density="compact"
        startAtEnd
        label={`${title} statement`}
        columns={columns}
        rows={rows}
        rowKey={(row) => row.name}
      />
    </div>
  );
}
