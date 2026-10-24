import { describe, expect, it } from "vitest";

import type { CompensationRow, GovernanceField } from "../types";
import { componentColumns, fieldText, pvpRows, ratioText, roleLabel } from "./governance";

const field = (name: string, value: string | boolean | string[] | null): GovernanceField => ({
  name,
  label: name,
  value,
});

const row = (components: Record<string, string>): CompensationRow => ({
  person: "Pat Example",
  role: "peo",
  fiscal_year: 2025,
  components,
  total: "1",
  source_id: "1_SCT_t0001",
});

describe("governance (FR-GV-012)", () => {
  it("says Not stated for a missing field and words for the rest", () => {
    expect(fieldText(field("dual_class", null))).toBe("Not stated");
    expect(fieldText(field("dual_class", false))).toBe("No");
    expect(fieldText(field("lead_independent_director", true))).toBe("Yes");
    expect(fieldText(field("committees", ["Audit", "Compensation"]))).toBe("Audit, Compensation");
    expect(fieldText(field("say_on_pay_support_pct", "92.5"))).toBe("92.5%");
    expect(fieldText(field("board_size", "10"))).toBe("10");
    expect(fieldText(field("board_size", "ten"))).toBe("ten");
  });

  it("shows only the pay columns some row reports, in table order", () => {
    expect(componentColumns([row({ all_other: "1", salary: "2" }), row({ bonus: "3" })]).map(([k]) => k)).toEqual([
      "salary",
      "bonus",
      "all_other",
    ]);
    expect(roleLabel("pfo")).toBe("CFO");
  });

  it("formats the pay ratio and the PvP series", () => {
    expect(ratioText("129.00000000")).toBe("129:1");
    expect(ratioText(null)).toBe("Not found");
    expect(
      pvpRows([{ fiscal_year: 2026, values: { peo_actually_paid_comp: "5", tsr: "1445.67" }, source_ids: {} }]),
    ).toEqual([{ year: 2026, label: "FY26", actuallyPaid: 5, summaryTotal: null, tsr: 1445.67, peerTsr: null }]);
  });
});
