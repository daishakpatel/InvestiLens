import { describe, expect, it } from "vitest";

import type { FootnoteFact, NoteItem } from "../types";
import { categoriesFor, categoryLabel, formatFact, gapReason, ladderRows, tableFacts } from "./footnotes";

const fact = (metric: string, value: string | null, unit = "USD"): FootnoteFact => ({
  metric,
  label: metric,
  value,
  unit,
  period: "FY2026",
  source_id: `xbrl:NVDA:${metric}:FY2026`,
  is_derived: false,
  formula: null,
  from_inline_xbrl: false,
});

const note = (category: string): NoteItem => ({
  note_id: `note-${category}`,
  number: 1,
  title: category,
  category,
  also_matches: [],
  paragraph_ids: ["1_15_1"],
  summary: null,
});

const LADDER = ["y1", "y2", "y3", "y4", "y5", "after"].map((w, i) => fact(`debt_maturity_${w}`, String(i * 1e9)));

describe("footnotes (FR-FN-012)", () => {
  it("orders categories by the taxonomy and skips empty ones", () => {
    const facts = {
      company_ticker: "NVDA",
      fiscal_year: 2026,
      categories: [
        { category: "income_taxes", facts: [fact("unrecognized_tax_benefits", "1")], gaps: [] },
        { category: "stock_comp", facts: [], gaps: [] },
      ],
    };
    expect(categoriesFor([note("other"), note("debt"), note("segments")], facts)).toEqual([
      "debt",
      "income_taxes",
      "segments",
      "other",
    ]);
    expect(categoryLabel("commitments_contingencies")).toBe("Commitments & contingencies");
  });

  it("formats money, rates and years", () => {
    expect(formatFact(fact("x", "1250000000"))).toBe("$1.25B");
    expect(formatFact(fact("x", "0.0438", "ratio"))).toBe("4.4%");
    expect(formatFact(fact("x", "8.8", "years"))).toBe("8.8 years");
    expect(formatFact(fact("x", null))).toBe("N/A");
  });

  it("charts a ladder only when every window is reported", () => {
    expect(ladderRows(LADDER, "debt_maturity")?.map((r) => r.window)).toEqual([
      "Year 1",
      "Year 2",
      "Year 3",
      "Year 4",
      "Year 5",
      "After 5",
    ]);
    expect(ladderRows(LADDER.slice(1), "debt_maturity")).toBeNull();
    expect(ladderRows([...LADDER.slice(1), fact("debt_maturity_y1", null)], "debt_maturity")).toBeNull();
  });

  it("keeps charted windows out of the table but keeps totals", () => {
    const rows = tableFacts([...LADDER, fact("lease_payments_total", "1"), fact("lease_payments_y1", "1")], [
      "debt_maturity",
      "lease_payments",
    ]);
    expect(rows.map((f) => f.metric)).toEqual(["lease_payments_total"]);
  });

  it("explains gaps in words", () => {
    expect(gapReason("not_tagged")).toBe("Not tagged in the filing's XBRL");
    expect(gapReason("weird")).toBe("Not available");
  });
});
