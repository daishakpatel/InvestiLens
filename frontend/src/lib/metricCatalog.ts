// What each backend metric is called on screen, how it is drawn, and how the Financials tab
// groups them. Names are the API's `metric_name`s (Appendix B concept map, §12 formulas).

import { displayOf } from "../charts/series";
import type { Display } from "../charts/series";

export type MetricKind = "bar" | "line";

interface MetricInfo {
  label: string;
  kind: MetricKind; // amounts are bars (magnitude); ratios are lines (trend)
  multiple?: true; // a "ratio" that reads as 4.45× rather than as a percentage
  /** Which end of a ranking is the stronger one. Default: higher. "neither" for figures where
   *  more is not better or worse in itself (a valuation multiple, a share count). */
  better?: "lower" | "neither";
}

const METRICS: Record<string, MetricInfo> = {
  revenue: { label: "Revenue", kind: "bar" },
  cost_of_revenue: { label: "Cost of revenue", kind: "bar" },
  gross_profit: { label: "Gross profit", kind: "bar" },
  operating_income: { label: "Operating income", kind: "bar" },
  ebitda: { label: "EBITDA", kind: "bar" },
  net_income: { label: "Net income", kind: "bar" },
  eps_diluted: { label: "EPS (diluted)", kind: "bar" },
  shares_diluted_weighted: { label: "Diluted shares", kind: "bar", better: "neither" },
  yoy_growth: { label: "Revenue growth", kind: "line" },

  gross_margin: { label: "Gross margin", kind: "line" },
  operating_margin: { label: "Operating margin", kind: "line" },
  net_margin: { label: "Net margin", kind: "line" },
  fcf_margin: { label: "Free cash flow margin", kind: "line" },
  roe: { label: "Return on equity", kind: "line" },
  roa: { label: "Return on assets", kind: "line" },

  operating_cash_flow: { label: "Operating cash flow", kind: "bar" },
  capex: { label: "Capital expenditure", kind: "bar", better: "neither" },
  free_cash_flow: { label: "Free cash flow", kind: "bar" },
  depreciation_amortization: { label: "Depreciation & amortization", kind: "bar" },
  stock_based_compensation: { label: "Stock-based compensation", kind: "bar" },
  sbc_pct_revenue: { label: "Stock-based comp. / revenue", kind: "line" },
  capex_intensity: { label: "Capex / revenue", kind: "line" },

  cash_and_equivalents: { label: "Cash & equivalents", kind: "bar" },
  short_term_investments: { label: "Short-term investments", kind: "bar" },
  receivables: { label: "Receivables", kind: "bar" },
  inventory: { label: "Inventory", kind: "bar" },
  current_assets: { label: "Current assets", kind: "bar" },
  total_assets: { label: "Total assets", kind: "bar" },
  payables: { label: "Payables", kind: "bar" },
  current_liabilities: { label: "Current liabilities", kind: "bar" },
  short_term_debt: { label: "Short-term debt", kind: "bar", better: "lower" },
  long_term_debt: { label: "Long-term debt", kind: "bar", better: "lower" },
  total_debt: { label: "Total debt", kind: "bar", better: "lower" },
  total_liabilities: { label: "Total liabilities", kind: "bar", better: "lower" },
  shareholders_equity: { label: "Shareholders’ equity", kind: "bar" },
  current_ratio: { label: "Current ratio", kind: "line", multiple: true },
  debt_to_equity: { label: "Debt / equity", kind: "line", multiple: true, better: "lower" },

  market_cap: { label: "Market cap", kind: "bar" },
  enterprise_value: { label: "Enterprise value", kind: "bar" },
  pe_ratio: { label: "P/E", kind: "line", multiple: true, better: "neither" },
  ps_ratio: { label: "P/S", kind: "line", multiple: true, better: "neither" },
  ev_revenue: { label: "EV / revenue", kind: "line", multiple: true, better: "neither" },
  ev_ebitda: { label: "EV / EBITDA", kind: "line", multiple: true, better: "neither" },
  fcf_yield: { label: "Free cash flow yield", kind: "line" },
};

export function metricLabel(name: string): string {
  return METRICS[name]?.label ?? name.replace(/_/g, " ");
}

/** "higher" or "lower" when one end of a ranking is the stronger; null when neither is. */
export function metricBetter(name: string): "higher" | "lower" | null {
  const better = METRICS[name]?.better;
  return better === "neither" ? null : (better ?? "higher");
}

export function metricKind(name: string): MetricKind {
  return METRICS[name]?.kind ?? "bar";
}

export function metricDisplay(name: string, unit: string): Display {
  return displayOf(unit, METRICS[name]?.multiple === true);
}

/** How to print a known metric when only its name is at hand (a cited source carries no unit).
 *  Null for an unknown metric: the caller then shows the value as the API sent it. */
export function metricDisplayByName(name: string): Display | null {
  const info = METRICS[name];
  if (!info) return null;
  if (name === "eps_diluted") return "perShare";
  if (name === "shares_diluted_weighted") return "count";
  if (info.kind === "line") return info.multiple ? "multiple" : "percent";
  return "money";
}

export interface FinancialSection {
  id: string; // also the in-page anchor
  title: string;
  charts: string[]; // four, as a two-column grid
  table: string[]; // statement rows, in reading order
}

export const FINANCIAL_SECTIONS: FinancialSection[] = [
  {
    id: "income",
    title: "Income",
    charts: ["revenue", "operating_income", "net_income", "eps_diluted"],
    table: [
      "revenue",
      "cost_of_revenue",
      "gross_profit",
      "operating_income",
      "ebitda",
      "net_income",
      "eps_diluted",
    ],
  },
  {
    id: "margins",
    title: "Margins",
    charts: ["gross_margin", "operating_margin", "net_margin", "roe"],
    table: ["gross_margin", "operating_margin", "net_margin", "fcf_margin", "roe", "roa"],
  },
  {
    id: "cash-flow",
    title: "Cash flow",
    charts: ["operating_cash_flow", "free_cash_flow", "capex", "stock_based_compensation"],
    table: [
      "operating_cash_flow",
      "capex",
      "free_cash_flow",
      "depreciation_amortization",
      "stock_based_compensation",
      "sbc_pct_revenue",
      "capex_intensity",
    ],
  },
  {
    id: "balance-sheet",
    title: "Balance sheet",
    charts: ["cash_and_equivalents", "total_debt", "shareholders_equity", "current_ratio"],
    table: [
      "cash_and_equivalents",
      "short_term_investments",
      "receivables",
      "inventory",
      "current_assets",
      "total_assets",
      "payables",
      "current_liabilities",
      "short_term_debt",
      "long_term_debt",
      "total_debt",
      "total_liabilities",
      "shareholders_equity",
      "current_ratio",
      "debt_to_equity",
    ],
  },
];

export const ALL_FINANCIAL_METRICS = [
  ...new Set(FINANCIAL_SECTIONS.flatMap((section) => [...section.charts, ...section.table])),
];

// Why a metric has no value (DR-041 reason codes), in plain words.
const REASONS: Record<string, string> = {
  NOT_APPLICABLE_SECTOR: "Not applicable to this company’s sector",
  MISSING_INPUT: "An input is not reported in the filings",
  NEGATIVE_BASE: "Not meaningful: the base is zero or negative",
  NO_DATA_FOR_PERIOD: "No figure for this period",
};

export function reasonText(code: string | undefined): string {
  return (code && REASONS[code]) ?? "Not available";
}
