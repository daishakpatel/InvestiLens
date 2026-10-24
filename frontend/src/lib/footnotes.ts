// Footnotes tab helpers (Phase 7f). Display only: every figure arrives computed from XBRL.
import { formatValue } from "../charts/series";
import type { FootnoteFact, FootnoteFactsResponse, NoteItem } from "../types";
import { toNumber } from "./format";

/** note_taxonomy_v1 in reading order; "other" last. */
export const CATEGORY_ORDER = [
  "debt",
  "leases",
  "revenue_recognition",
  "income_taxes",
  "commitments_contingencies",
  "segments",
  "stock_comp",
  "goodwill_intangibles",
  "derivatives",
  "fair_value",
  "other",
] as const;

const LABELS: Record<string, string> = {
  debt: "Debt",
  leases: "Leases",
  revenue_recognition: "Revenue recognition",
  income_taxes: "Income taxes",
  commitments_contingencies: "Commitments & contingencies",
  segments: "Segments",
  stock_comp: "Stock compensation",
  goodwill_intangibles: "Goodwill & intangibles",
  derivatives: "Derivatives",
  fair_value: "Fair value",
  other: "Other notes",
};

export const categoryLabel = (category: string): string => LABELS[category] ?? category;

/** Categories with a note or a fact, in taxonomy order. */
export function categoriesFor(notes: readonly NoteItem[], facts: FootnoteFactsResponse | undefined): string[] {
  const present = new Set(notes.map((n) => n.category));
  for (const group of facts?.categories ?? []) {
    if (group.facts.length > 0) present.add(group.category);
  }
  return CATEGORY_ORDER.filter((c) => present.has(c));
}

/** "$1.25B", "4.38%", "8.8 years". */
export function formatFact(fact: Pick<FootnoteFact, "value" | "unit">): string {
  const n = toNumber(fact.value);
  if (n === null) return "N/A";
  if (fact.unit === "years") return `${n.toLocaleString("en-US", { maximumFractionDigits: 1 })} years`;
  return formatValue(n, fact.unit === "ratio" ? "percent" : fact.unit === "USD" ? "money" : "count");
}

const WINDOWS = ["y1", "y2", "y3", "y4", "y5", "after"] as const;
const WINDOW_LABELS: Record<(typeof WINDOWS)[number], string> = {
  y1: "Year 1",
  y2: "Year 2",
  y3: "Year 3",
  y4: "Year 4",
  y5: "Year 5",
  after: "After 5",
};

export interface LadderRow {
  window: string;
  value: number;
  sourceId: string;
}

/** A maturity or payment schedule (`debt_maturity_*`, `lease_payments_*`) as chart rows, or
 *  null unless every window is reported: a ladder with a missing year would read as a zero. */
export function ladderRows(facts: readonly FootnoteFact[], prefix: string): LadderRow[] | null {
  const rows: LadderRow[] = [];
  for (const window of WINDOWS) {
    const fact = facts.find((f) => f.metric === `${prefix}_${window}`);
    const value = toNumber(fact?.value);
    if (!fact || value === null) return null;
    rows.push({ window: WINDOW_LABELS[window], value, sourceId: fact.source_id });
  }
  return rows;
}

/** Facts shown in the table: everything except the ladder windows the chart already plots. */
export const tableFacts = (facts: readonly FootnoteFact[], charted: readonly string[]): FootnoteFact[] =>
  facts.filter((f) => !charted.some((prefix) => f.metric.startsWith(`${prefix}_`) && !f.metric.endsWith("_total")));

const GAP_REASONS: Record<string, string> = {
  not_tagged: "Not tagged in the filing's XBRL",
  filing_unavailable: "The 10-K could not be read",
  MISSING_INPUT: "An input is missing",
};

export const gapReason = (code: string): string => GAP_REASONS[code] ?? "Not available";
