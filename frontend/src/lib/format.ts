// Display formatting only. Backend sends money/ratios as decimal strings (NUMERIC); we parse to
// Number purely to render — never to recompute a financial value (that stays server-side).

export function toNumber(value: string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

const compactUsd = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 2,
});

export function formatUsdCompact(value: string | number | null | undefined): string {
  const n = typeof value === "number" ? value : toNumber(value ?? null);
  if (n === null) return "—";
  return `$${compactUsd.format(n)}`;
}

export function formatUsd(value: string | number | null | undefined): string {
  const n = typeof value === "number" ? value : toNumber(value ?? null);
  if (n === null) return "—";
  return n.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function formatPercent(ratio: string | number | null | undefined, digits = 1): string {
  const r = typeof ratio === "number" ? ratio : toNumber(ratio ?? null);
  if (r === null) return "—";
  return `${(r * 100).toFixed(digits)}%`;
}

export function formatNumber(value: string | number | null | undefined, digits = 2): string {
  const n = typeof value === "number" ? value : toNumber(value ?? null);
  if (n === null) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: digits });
}

/** Unit-aware metric rendering: USD → compact money, ratio → percent, else a plain number. */
export function formatMetricValue(
  value: string | null | undefined,
  unit: string | null | undefined,
): string {
  if (toNumber(value ?? null) === null) return "—";
  const u = (unit ?? "").toLowerCase();
  if (u === "usd") return formatUsdCompact(value ?? null);
  if (u === "ratio") return formatPercent(value ?? null);
  if (u === "shares") return formatNumber(value ?? null, 0);
  return formatNumber(value ?? null);
}

const dateFmt = new Intl.DateTimeFormat("en-US", { year: "numeric", month: "short", day: "numeric" });

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : dateFmt.format(d);
}

export function freshnessLabel(asOf: string | null | undefined): string {
  const d = formatDate(asOf);
  return d === "—" ? "Not yet updated" : `Updated ${d}`;
}

/** "FY2025" plus the calendar end date, keeping fiscal and calendar periods distinct (DR). */
export function fiscalCalendarLabel(period: string, periodEnd: string | null | undefined): string {
  return periodEnd ? `${period} · ended ${formatDate(periodEnd)}` : period;
}

export function toCsv(headers: string[], rows: (string | number | null | undefined)[][]): string {
  const escape = (cell: string | number | null | undefined): string => {
    const s = cell === null || cell === undefined ? "" : String(cell);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [headers, ...rows].map((row) => row.map(escape).join(",")).join("\n");
}

export function downloadText(filename: string, text: string, mime = "text/plain;charset=utf-8;"): void {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadCsv(filename: string, csv: string): void {
  downloadText(filename, csv, "text/csv;charset=utf-8;");
}
