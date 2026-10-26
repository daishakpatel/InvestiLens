import { describe, expect, it } from "vitest";

import type { ThesisEvent, ThesisKpi } from "../types";
import { eventEvidence, eventText, kpiRuleText, shiftDecimal, toInput, toThreshold, valueText } from "./thesis";

const kpi = {
  id: 4,
  metric_label: "Gross margin",
  comparator: "gte",
  threshold: "0.7",
  unit: "ratio",
  period_type: "TTM",
  label: "Margins hold",
} as ThesisKpi;

const event = (over: Partial<ThesisEvent>): ThesisEvent => ({
  id: 1,
  kind: "kpi_broken",
  occurred_at: "2026-10-25T00:00:00Z",
  kpi_id: 4,
  ref_type: "metric",
  ref_id: "derived:NVDA:gross_margin:TTM-Q3-FY2027",
  note: null,
  payload: { value: "0.6812", period: "TTM-Q3-FY2027" },
  ...over,
});

describe("thresholds are exact decimals (FR-TH-005)", () => {
  it("types a ratio as a percent and stores the decimal", () => {
    expect(toThreshold("25", "ratio")).toBe("0.25");
    expect(toThreshold("0.5", "ratio")).toBe("0.005");
    expect(toThreshold("-12.75", "ratio")).toBe("-0.1275");
    expect(toThreshold("100", "ratio")).toBe("1");
    expect(toThreshold("26.4", "multiple")).toBe("26.4");
    expect(toThreshold("abc", "ratio")).toBeNull();
    expect(toThreshold("", "usd")).toBeNull();
    expect(toInput("0.70000000", "ratio")).toBe("70");
    expect(toInput("2.46000000", "usd_per_share")).toBe("2.46");
    expect(shiftDecimal("0.1", 1)).toBe("1");
    expect(shiftDecimal("-0.00", 2)).toBe("0");
  });
});

describe("KPI and timeline wording (FR-TH-012)", () => {
  it("shows values in their unit", () => {
    expect(valueText("0.6812", "ratio")).toBe("68.12%");
    expect(valueText("96221000000", "usd")).toBe("$96.22B");
    expect(valueText("26.4", "multiple")).toBe("26.4×");
    expect(valueText("7.00", "score")).toBe("7");
    expect(valueText(null, "ratio")).toBe("—");
    expect(kpiRuleText(kpi)).toBe("Gross margin (TTM) ≥ 70.00%");
  });

  it("states KPI changes and links each event to its evidence", () => {
    const kpis = new Map([[4, kpi]]);
    expect(eventText(event({}), kpis)).toBe("'Margins hold' is now broken: 68.12% for TTM-Q3-FY2027.");
    expect(eventText(event({ kpi_id: null }), kpis)).toBe("A deleted KPI is now broken: 0.6812 for TTM-Q3-FY2027.");
    expect(eventText(event({ kind: "red_flag", payload: { label: "Auditor change" } }), kpis)).toBe(
      "Red flag reported: Auditor change.",
    );
    expect(eventText(event({ kind: "status_changed", payload: { to: "closed" } }), kpis)).toBe("Thesis closed.");
    expect(eventText(event({ kind: "user_note", note: "Checked the 10-Q." }), kpis)).toBe("Checked the 10-Q.");
    expect(eventEvidence(event({}), "NVDA")).toEqual({ href: null, sourceId: "derived:NVDA:gross_margin:TTM-Q3-FY2027" });
    expect(eventEvidence(event({ ref_id: "earnings_brief:9" }), "NVDA").href).toBe("/company/NVDA/earnings?brief=9");
    expect(eventEvidence(event({ ref_id: null }), "NVDA")).toEqual({ href: null, sourceId: null });
  });
});
