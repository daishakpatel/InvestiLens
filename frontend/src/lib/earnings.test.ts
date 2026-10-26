import { describe, expect, it } from "vitest";

import type { StoredBrief } from "../types";
import {
  changeText,
  figureText,
  missingReason,
  pickVersions,
  reportDateText,
  versionLabel,
  volumeText,
} from "./earnings";

function stored(id: number, kind: StoredBrief["kind"], fy: number, fp: string, version: number): StoredBrief {
  return {
    id,
    kind,
    fiscal_year: fy,
    fiscal_period: fp,
    period_label: `${fp} FY${fy}`,
    version,
    inputs_label: version === 1 ? "after earnings release" : "after 10-Q filed",
    created_at: "2026-08-27T00:00:00Z",
  };
}

describe("earnings dates (FR-EB-002)", () => {
  it("marks an estimate with ~ and names the session", () => {
    expect(reportDateText("2026-11-18", true)).toBe("~Nov 18, 2026");
    expect(reportDateText("2026-11-18", false, "amc")).toBe("Nov 18, 2026 · after the close");
    expect(reportDateText(null, true)).toBe("Date not known yet");
  });
});

describe("figures", () => {
  it("prints each unit and change kind", () => {
    expect(figureText("96221000000", "usd")).toBe("$96.22B");
    expect(figureText("-5400000", "usd")).toBe("−$5.40M");
    expect(figureText("2.46", "usd_per_share")).toBe("$2.46");
    expect(figureText("0.7498", "ratio")).toBe("75.0%");
    expect(figureText(null, "usd")).toBe("—");
    expect(changeText("0.178962", "growth")).toBe("+17.9%");
    expect(changeText("-0.5", "growth")).toBe("−50.0%");
    expect(changeText("0.000418", "points")).toBe("+4 bps");
    expect(changeText(null, "points")).toBe("—");
    expect(volumeText("2.598")).toBe("2.6× the 20-day average volume");
    expect(volumeText(null)).toBeNull();
  });

  it("finds a section's missing reason", () => {
    const missing = [{ section: "what_changed", reason: "10-Q not yet filed." }];
    expect(missingReason(missing, "what_changed")).toBe("10-Q not yet filed.");
    expect(missingReason(missing, "reaction")).toBeNull();
  });
});

describe("version switcher (FR-EB-015)", () => {
  const items = [
    stored(5, "brief", 2027, "Q2", 2),
    stored(4, "brief", 2027, "Q2", 1),
    stored(6, "preview", 2027, "Q3", 1),
    stored(2, "brief", 2027, "Q1", 1),
  ];

  it("shows the newest version of the latest quarter, with its siblings", () => {
    const picked = pickVersions(items, "brief");
    expect(picked?.current.id).toBe(5);
    expect(picked?.versions.map((v) => v.id)).toEqual([5, 4]);
    expect(picked && versionLabel(picked.current)).toBe("v2 · after 10-Q filed");
  });

  it("honours a linked version and ignores one of another kind", () => {
    expect(pickVersions(items, "brief", 4)?.current.id).toBe(4);
    expect(pickVersions(items, "brief", 2)?.versions.map((v) => v.id)).toEqual([2]);
    expect(pickVersions(items, "brief", 6)?.current.id).toBe(5);
    expect(pickVersions(items, "preview")?.current.id).toBe(6);
    expect(pickVersions([], "brief")).toBeNull();
  });
});
