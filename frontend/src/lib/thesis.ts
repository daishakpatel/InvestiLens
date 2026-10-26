// Phase 7k: wording, units and evidence links for the thesis tracker. Thresholds are exact
// decimal strings; a ratio is typed as a percent and stored as a decimal (FR-TH-005).
import type { ThesisEvent, ThesisKpi } from "../types";
import { formatDate, formatPercent, formatUsd, toNumber } from "./format";

type Unit = ThesisKpi["unit"];
type State = ThesisKpi["state"];

export const COMPARATOR_SYMBOL: Record<ThesisKpi["comparator"], string> = {
  gte: "≥",
  lte: "≤",
  gt: ">",
  lt: "<",
};

export const STATE_LABEL: Record<State, string> = { met: "Met", broken: "Broken", no_data: "No data" };

export const STANCE_LABEL = { long: "Long", short: "Short", watch: "Watch", avoid: "Avoid" } as const;

/** Move the decimal point `places` to the right (negative: left), exactly, on a string. */
export function shiftDecimal(value: string, places: number): string | null {
  const m = /^\s*(-)?(\d*)(?:\.(\d*))?\s*$/.exec(value);
  if (!m || (!m[2] && !m[3])) return null;
  const sign = m[1] ?? "";
  let digits = (m[2] ?? "") + (m[3] ?? "");
  let point = (m[2] ?? "").length + places;
  if (point < 0) {
    digits = "0".repeat(-point) + digits;
    point = 0;
  }
  if (point > digits.length) digits += "0".repeat(point - digits.length);
  const whole = digits.slice(0, point).replace(/^0+(?=\d)/, "") || "0";
  const frac = digits.slice(point).replace(/0+$/, "");
  const out = frac ? `${whole}.${frac}` : whole;
  return out === "0" ? "0" : `${sign}${out}`;
}

/** What the user types → the stored threshold: a ratio is typed as a percent ("25" → "0.25"). */
export function toThreshold(input: string, unit: Unit): string | null {
  return unit === "ratio" ? shiftDecimal(input, -2) : shiftDecimal(input, 0);
}

/** The stored threshold → what the form shows ("0.25" → "25" for a ratio). */
export function toInput(threshold: string, unit: Unit): string {
  return (unit === "ratio" ? shiftDecimal(threshold, 2) : shiftDecimal(threshold, 0)) ?? threshold;
}

export const INPUT_SUFFIX: Record<Unit, string> = {
  usd: "USD",
  usd_per_share: "$ / share",
  ratio: "%",
  multiple: "×",
  score: "score",
  days: "days",
};

/** A value in its unit: "$96.22B", "$2.46", "74.98%", "26.4×", "7", "45 days". */
export function valueText(value: string | null | undefined, unit: Unit): string {
  const n = toNumber(value ?? null);
  if (n === null) return "—";
  switch (unit) {
    case "ratio":
      return formatPercent(n, 2);
    case "usd_per_share":
      return formatUsd(n);
    case "multiple":
      return `${n.toFixed(1)}×`;
    case "days":
      return `${n.toFixed(0)} days`;
    case "score":
      return n.toFixed(2).replace(/\.?0+$/, "");
    default: {
      const abs = Math.abs(n);
      const [size, word] = abs >= 1e9 ? [1e9, "B"] : abs >= 1e6 ? [1e6, "M"] : [1, ""];
      return `${n < 0 ? "−" : ""}$${(abs / size).toFixed(size === 1 ? 0 : 2)}${word}`;
    }
  }
}

export function kpiRuleText(kpi: Pick<ThesisKpi, "metric_label" | "comparator" | "threshold" | "unit" | "period_type">): string {
  return `${kpi.metric_label} (${kpi.period_type}) ${COMPARATOR_SYMBOL[kpi.comparator]} ${valueText(kpi.threshold, kpi.unit)}`;
}

/** One timeline line in plain words; KPI states only, never a verdict on the thesis (FR-TH-012). */
export function eventText(event: ThesisEvent, kpis: ReadonlyMap<number, ThesisKpi>): string {
  const payload = event.payload as Record<string, unknown>;
  const label = typeof payload.label === "string" ? payload.label : "";
  switch (event.kind) {
    case "kpi_met":
    case "kpi_broken": {
      const kpi = event.kpi_id === null ? undefined : kpis.get(event.kpi_id);
      const state = event.kind === "kpi_met" ? "met" : "broken";
      const value = typeof payload.value === "string" ? payload.value : null;
      const name = kpi ? `'${kpi.label}'` : "A deleted KPI";
      const period = typeof payload.period === "string" ? ` for ${payload.period}` : "";
      return `${name} is now ${state}: ${kpi ? valueText(value, kpi.unit) : (value ?? "")}${period}.`;
    }
    case "red_flag":
      return `Red flag reported: ${label || "a filing event"}.`;
    case "brief_published":
      return `${label || "An earnings brief"} published.`;
    case "status_changed":
      return `Thesis ${payload.to === "closed" ? "closed" : "reopened"}.`;
    default:
      return event.note ?? "";
  }
}

/** Where an event's evidence opens: a brief on the Earnings tab; a metric or red flag in the
 *  citation drawer (null href, `sourceId` set). */
export function eventEvidence(
  event: ThesisEvent,
  ticker: string,
): { href: string | null; sourceId: string | null } {
  const ref = event.ref_id;
  if (!ref) return { href: null, sourceId: null };
  if (ref.startsWith("earnings_brief:")) {
    return { href: `/company/${encodeURIComponent(ticker)}/earnings?brief=${ref.slice("earnings_brief:".length)}`, sourceId: null };
  }
  return { href: null, sourceId: ref };
}

export function evaluatedText(kpi: Pick<ThesisKpi, "last_period" | "last_period_end">): string {
  if (!kpi.last_period) return "No reported value yet";
  return kpi.last_period_end ? `${kpi.last_period} · ended ${formatDate(kpi.last_period_end)}` : kpi.last_period;
}
