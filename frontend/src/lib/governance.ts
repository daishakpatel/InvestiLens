// Governance tab helpers (Phase 7g). Display only: every figure arrives extracted and validated.
import type { CompensationRow, GovernanceField, PayVersusPerformancePoint } from "../types";
import { toNumber } from "./format";

// Short headers so seven components and the total fit beside each other.
const COMPONENTS: [string, string][] = [
  ["salary", "Salary"],
  ["bonus", "Bonus"],
  ["stock_awards", "Stock"],
  ["option_awards", "Options"],
  ["non_equity_incentive", "Incentive"],
  ["pension_nqdc", "Pension"],
  ["all_other", "Other"],
];

/** The pay components any row reports, in the Summary Compensation Table's order. */
export function componentColumns(rows: readonly CompensationRow[]): [string, string][] {
  return COMPONENTS.filter(([key]) => rows.some((r) => key in r.components));
}

const ROLES: Record<CompensationRow["role"], string> = { peo: "CEO", pfo: "CFO", neo: "Officer" };
export const roleLabel = (role: CompensationRow["role"]): string => ROLES[role];

/** A Tier C value as words; null is "Not stated" (absent from the proxy, or not verifiable). */
export function fieldText(field: GovernanceField): string {
  const value = field.value;
  if (value === null || value === undefined) return "Not stated";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.join(", ");
  const n = toNumber(value);
  if (n === null) return value;
  const text = n.toLocaleString("en-US", { maximumFractionDigits: 1 });
  return field.name === "say_on_pay_support_pct" ? `${text}%` : text;
}

/** "129:1" from the stored multiple. */
export function ratioText(ratio: string | null | undefined): string {
  const n = toNumber(ratio ?? null);
  return n === null ? "Not found" : `${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}:1`;
}

export interface PvpRow {
  year: number;
  label: string;
  actuallyPaid: number | null; // CEO compensation actually paid (SEC definition)
  summaryTotal: number | null; // CEO total in the Summary Compensation Table
  tsr: number | null; // value of $100 invested
  peerTsr: number | null;
}

export function pvpRows(points: readonly PayVersusPerformancePoint[]): PvpRow[] {
  return points.map((p) => ({
    year: p.fiscal_year,
    label: `FY${String(p.fiscal_year).slice(2)}`,
    actuallyPaid: toNumber(p.values.peo_actually_paid_comp ?? null),
    summaryTotal: toNumber(p.values.peo_total_comp ?? null),
    tsr: toNumber(p.values.tsr ?? null),
    peerTsr: toNumber(p.values.peer_group_tsr ?? null),
  }));
}
