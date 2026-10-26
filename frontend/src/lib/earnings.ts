// Phase 7j: wording and selection for the Earnings tab. Every number comes from the API; this
// only formats it and picks which stored version to show.
import type { BriefMissing, CalendarEvent, MetricRow, StoredBrief } from "../types";
import { formatDate, formatPercent, formatUsd, toNumber } from "./format";

type Kind = StoredBrief["kind"];

const TIME_LABEL: Record<CalendarEvent["report_time"], string> = {
  amc: "after the close",
  bmo: "before the open",
  unknown: "",
};

const SOURCE_LABEL: Record<CalendarEvent["source"], string> = {
  sec_8k: "Reported in an 8-K",
  announcement: "Announced by the company",
  estimated: "Estimated from last year's date",
};

/** "Nov 18, 2026 · after the close", "~Nov 18, 2026" for an estimate (FR-EB-002). */
export function reportDateText(
  date: string | null | undefined,
  estimated: boolean,
  time: CalendarEvent["report_time"] = "unknown",
): string {
  if (!date) return "Date not known yet";
  const when = `${estimated ? "~" : ""}${formatDate(date)}`;
  return TIME_LABEL[time] ? `${when} · ${TIME_LABEL[time]}` : when;
}

export function dateSourceText(source: CalendarEvent["source"]): string {
  return SOURCE_LABEL[source];
}

/** A figure in its own unit: compact money, dollars per share, or a percentage. */
export function figureText(value: string | null | undefined, unit: MetricRow["unit"]): string {
  const n = toNumber(value ?? null);
  if (n === null) return "—";
  if (unit === "ratio") return formatPercent(n, 1);
  if (unit === "usd_per_share") return formatUsd(n);
  const abs = Math.abs(n);
  const [size, word] = abs >= 1e9 ? [1e9, "B"] : abs >= 1e6 ? [1e6, "M"] : [1, ""];
  return `${n < 0 ? "−" : ""}$${(abs / size).toFixed(size === 1 ? 0 : 2)}${word}`;
}

/** "+17.9%" growth, or "+26 bps" for a margin; "—" when there is nothing to compare. */
export function changeText(value: string | null | undefined, kind: MetricRow["change_kind"]): string {
  const n = toNumber(value ?? null);
  if (n === null) return "—";
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  return kind === "points"
    ? `${sign}${Math.round(Math.abs(n) * 10000)} bps`
    : `${sign}${formatPercent(Math.abs(n), 1)}`;
}

export function moveText(value: string | null | undefined): string {
  return changeText(value, "growth");
}

/** "2.6× average volume", or null without volume data. */
export function volumeText(value: string | null | undefined): string | null {
  const n = toNumber(value ?? null);
  return n === null ? null : `${n.toFixed(1)}× the 20-day average volume`;
}

export function missingReason(missing: readonly BriefMissing[], section: string): string | null {
  return missing.find((m) => m.section === section)?.reason ?? null;
}

export interface Versions {
  current: StoredBrief;
  versions: StoredBrief[]; // the same quarter's versions, newest first
}

/** The version to show for one kind: the `selectedId` one if it is of that kind, else the newest
 *  version of the latest quarter. Items arrive latest quarter first, then newest version. */
export function pickVersions(
  items: readonly StoredBrief[],
  kind: Kind,
  selectedId: number | null = null,
): Versions | null {
  const ofKind = items.filter((i) => i.kind === kind);
  const current = ofKind.find((i) => i.id === selectedId) ?? ofKind[0];
  if (!current) return null;
  const versions = ofKind
    .filter((i) => i.fiscal_year === current.fiscal_year && i.fiscal_period === current.fiscal_period)
    .sort((a, b) => b.version - a.version);
  return { current, versions };
}

/** The option label in the version switcher: "v2 · after 10-Q filed". */
export function versionLabel(item: StoredBrief): string {
  return `v${item.version} · ${item.inputs_label}`;
}
