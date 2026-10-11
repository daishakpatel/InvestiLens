import type { BadgeTone } from "../ui/Badge";

export type ChangeStatus = "new" | "removed" | "reworded" | "unchanged";

/** How a passage compares with the same company's previous filing (§37.4). `new` is flagged as a
 *  caution and `removed` as a loss of disclosure; neither is a gain or a price move, so neither
 *  uses green. */
export const CHANGE_STATUS: Record<ChangeStatus, { label: string; inReport: string; tone: BadgeTone }> = {
  new: { label: "New", inReport: "New in the latest filing", tone: "warning" },
  removed: { label: "Removed", inReport: "Removed from the latest filing", tone: "negative" },
  reworded: { label: "Reworded", inReport: "Reworded in the latest filing", tone: "data" },
  unchanged: { label: "Unchanged", inReport: "Unchanged from the prior filing", tone: "neutral" },
};

/** Most newsworthy first: what was added and dropped, then edited, then left alone. */
export const CHANGE_ORDER: ChangeStatus[] = ["new", "removed", "reworded", "unchanged"];

export function isChangeStatus(value: string | null | undefined): value is ChangeStatus {
  return value != null && value in CHANGE_STATUS;
}
