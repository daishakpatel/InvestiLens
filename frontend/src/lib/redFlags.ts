// Display rules for the red-flag panel (Phase 7e). A flag is a reported event, never a verdict:
// severity says how closely to read it. Colour rule (FR-RF-012): warning and critical use the
// warning token, info is neutral; green and red never appear, and a text label always does.
import { formatDate } from "./format";
import type { RedFlagItem } from "../types";

export type FlagTone = "warning" | "neutral";

const SEVERITY_LABEL: Record<RedFlagItem["severity"], string> = {
  critical: "Read closely",
  warning: "Worth reading",
  info: "For awareness",
};

export function severityTone(severity: RedFlagItem["severity"]): FlagTone {
  return severity === "info" ? "neutral" : "warning";
}

export function severityLabel(severity: RedFlagItem["severity"]): string {
  return SEVERITY_LABEL[severity];
}

/** "Scanned through Oct 22, 2026; nothing reported." — the empty state is a fact, not a blank. */
export function emptyText(lastScannedAt: string | null | undefined): string {
  return lastScannedAt
    ? `Scanned through ${formatDate(lastScannedAt)}; nothing reported.`
    : "This company's filings have not been scanned yet.";
}

/** Flags filed in the 365 days up to `now`: the number on the Overview tab. */
export function recentCount(items: readonly RedFlagItem[], now: Date = new Date()): number {
  const cutoff = new Date(now);
  cutoff.setUTCDate(cutoff.getUTCDate() - 365);
  const floor = cutoff.toISOString().slice(0, 10);
  return items.filter((item) => (item.event_date ?? "") >= floor).length;
}

/** What the flag is about beyond its label: "Roles: CFO, Director". */
export function detailText(item: RedFlagItem): string | null {
  const roles = item.details["roles"];
  if (Array.isArray(roles) && roles.length > 0) return `Roles: ${roles.map(String).join(", ")}`;
  return null;
}
