import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RedFlagList } from "../components/company/RedFlags";
import type { RedFlagItem, RedFlagsResponse } from "../types";
import { detailText, emptyText, recentCount, severityLabel, severityTone } from "./redFlags";

// FR-RF-012..014: every state renders; severity is warning or neutral, never green or red.

function item(overrides: Partial<RedFlagItem> = {}): RedFlagItem {
  return {
    source_id: "redflag:NVDA:non_reliance:0000000000-26-904020",
    ticker: "NVDA",
    rule_key: "non_reliance",
    label: "Non-reliance on previously issued financial statements",
    severity: "critical",
    explanation: "Item 4.02: the company says earlier financial statements should no longer be relied on.",
    rule_source: "SEC Form 8-K (SEC 873, 02-25), Item 4.02",
    event_date: "2026-03-03",
    snippet: "On March 2, 2026, the Audit Committee concluded that the statements should no longer be relied upon.",
    filing: {
      id: 1,
      filing_type: "8-K",
      accession_number: "0000000000-26-904020",
      filing_date: "2026-03-03",
      url: "https://www.sec.gov/Archives/edgar/data/1/x.htm",
    },
    details: { item: "4.02" },
    ...overrides,
  };
}

const response = (items: RedFlagItem[], scanned: string | null = "2026-10-22T05:00:00Z"): RedFlagsResponse => ({
  items,
  last_scanned_at: scanned,
  taxonomy_version: "red_flag_taxonomy_v1",
});

const render = (props: Parameters<typeof RedFlagList>[0]) => renderToStaticMarkup(createElement(RedFlagList, props));
const noop = () => undefined;

describe("severity display", () => {
  it("uses the warning tone for warning and critical, neutral for info, with words", () => {
    expect(severityTone("critical")).toBe("warning");
    expect(severityTone("warning")).toBe("warning");
    expect(severityTone("info")).toBe("neutral");
    expect(severityLabel("critical")).toBe("Read closely");
    expect(severityLabel("info")).toBe("For awareness");
  });

  it("counts flags filed in the last year and lists roles", () => {
    const now = new Date("2026-10-22T12:00:00Z");
    const items = [item({ event_date: "2026-03-03" }), item({ event_date: "2025-09-01" }), item({ event_date: null })];
    expect(recentCount(items, now)).toBe(1);
    expect(detailText(item({ details: { roles: ["CFO", "Director"] } }))).toBe("Roles: CFO, Director");
    expect(detailText(item())).toBeNull();
  });

  it("says what an empty panel means", () => {
    expect(emptyText("2026-10-22T05:00:00Z")).toMatch(/^Scanned through .*2026; nothing reported\.$/);
    expect(emptyText(null)).toBe("This company's filings have not been scanned yet.");
  });
});

describe("RedFlagList renders every state (FR-RF-012/013)", () => {
  it("populated: label, date, quoted snippet, severity words and the filing link", () => {
    const html = render({ state: "ready", data: response([item()]), onOpen: noop });
    expect(html).toContain("Non-reliance on previously issued financial statements");
    expect(html).toContain("8-K · filed");
    expect(html).toContain("<q");
    expect(html).toContain("Read closely");
    expect(html).toContain("bg-warning");
    expect(html).toContain('href="https://www.sec.gov/Archives/edgar/data/1/x.htm"');
    expect(html).toContain("Open filing");
    expect(html).toContain("Scanned through");
    expect(html).not.toMatch(/bg-(positive|negative)|text-(positive|negative)/);
  });

  it("info flags are neutral and an unsafe filing link is dropped", () => {
    const html = render({
      state: "ready",
      data: response([
        item({ severity: "info", rule_key: "exec_departure", filing: { ...item().filing, url: "javascript:alert(1)" } }),
      ]),
      onOpen: noop,
    });
    expect(html).toContain("bg-subtle");
    expect(html).not.toContain("bg-warning");
    expect(html).not.toContain("javascript:");
  });

  it("empty: the scanned-through date instead of a blank", () => {
    const html = render({ state: "ready", data: response([]), onOpen: noop });
    expect(html).toMatch(/Scanned through .*; nothing reported\./);
    expect(render({ state: "ready", data: response([], null), onOpen: noop })).toContain("not been scanned yet");
  });

  it("loading and error states", () => {
    expect(render({ state: "loading", onOpen: noop })).toContain('aria-label="Loading red flags"');
    const error = render({ state: "error", onOpen: noop, onRetry: noop });
    expect(error).toContain("Red flags could not be loaded.");
    expect(error).toContain("Try again");
  });

  it("shows three and offers the rest", () => {
    const many = Array.from({ length: 7 }, (_, i) => item({ source_id: `redflag:NVDA:x:${i}` }));
    const html = render({ state: "ready", data: response(many), onOpen: noop });
    expect(html.match(/data-testid="red-flag-/g)).toHaveLength(3);
    expect(html).toContain("Show all 7");
  });
});
