// Assign citation numbers across a whole report in first-appearance order (CIT-006), so inline
// chips and the reference list agree. Pure function — easy to unit-test.
import type { ResearchReport } from "../types";

export interface ReportNumbering {
  numberOf: (sourceId: string) => number;
  order: string[]; // unique source ids in appearance order (index + 1 = citation number)
}

export function buildNumbering(report: ResearchReport): ReportNumbering {
  const map = new Map<string, number>();
  const order: string[] = [];
  const add = (ids: string[]): void => {
    for (const id of ids) {
      if (!map.has(id)) {
        order.push(id);
        map.set(id, order.length);
      }
    }
  };

  for (const claim of report.executive_summary) add(claim.source_ids);
  for (const claim of report.company_overview) add(claim.source_ids);
  for (const claim of report.revenue_analysis) add(claim.source_ids);
  for (const claim of report.profitability_analysis) add(claim.source_ids);
  for (const claim of report.balance_sheet_analysis) add(claim.source_ids);
  for (const claim of report.cash_flow_analysis) add(claim.source_ids);
  for (const claim of report.valuation_analysis) add(claim.source_ids);
  for (const n of report.news_summary) add(n.source_ids);
  for (const r of report.risks) add(r.source_ids);
  for (const m of report.management_commentary) add(m.source_ids);
  for (const f of [...report.bull_factors, ...report.bear_factors]) {
    for (const claim of f.claims) add(claim.source_ids);
  }

  return { numberOf: (id) => map.get(id) ?? 0, order };
}
