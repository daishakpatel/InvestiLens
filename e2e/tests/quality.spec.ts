import { expect, test } from "@playwright/test";

import { TICKER } from "./helpers";

// Phase 7d (Instructions/29_phase7d_earnings_quality_and_beneish.md): the Earnings quality tab
// shows five measure cards with the screening caveat under each score, a cash-vs-earnings chart,
// a five-year table, and an inputs disclosure whose every figure opens its source. Needs the dev
// stack with metrics rebuilt (`scripts/build_metrics.py`).
// Spec refs: FR-EQ-011, FR-EQ-012, FR-EQ-013, FR-EQ-014, DR-EQ-001.

const CAVEAT = "Screening heuristic. Calibrated on US non-financial companies.";

test("five cards, the caveat under each score, and a chart with its table", async ({ page }) => {
  await page.goto(`/company/${TICKER}/quality`);
  const cards = page.locator("[data-testid^='quality-card-']");
  await expect(cards).toHaveCount(5);
  await expect(page.getByTestId("quality-card-beneish_m").getByText(/threshold/)).toBeVisible();
  await expect(page.getByRole("note").filter({ hasText: CAVEAT })).toHaveCount(2); // Beneish, Altman
  await expect(page.getByRole("heading", { name: "Cash vs earnings" })).toBeVisible();
  const chart = "Net income, cash flow and free cash flow";
  await page.getByRole("button", { name: `View ${chart} as a table` }).click();
  // A table is a named scroll region only when it overflows, so find it by its headers.
  await expect(page.getByRole("columnheader", { name: "Accruals ratio" })).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "Measure" })).toBeVisible();
  await expect(page.getByRole("row", { name: /^Beneish M-score/ })).toBeVisible();
});

test("an input opens its source in the citation drawer (CIT-003)", async ({ page }) => {
  await page.goto(`/company/${TICKER}/quality`);
  const inputs = page.getByTestId("inputs-beneish_m");
  await inputs.locator("summary").click();
  const first = inputs.getByRole("button", { name: /^Open source xbrl:/ }).first();
  await expect(first).toBeVisible();
  await first.click();
  const panel = page.getByRole("dialog");
  await expect(panel).toHaveAccessibleName("Source");
  await expect(panel.getByText(/Not found|could not be found/i)).toHaveCount(0);
});

test("a bank says why the scores are not computed (DR-EQ-001)", async ({ page }) => {
  await page.goto("/company/JPM/quality");
  const beneish = page.getByTestId("quality-card-beneish_m");
  await expect(beneish.getByText(/N\/A\. Not computed for banks/)).toBeVisible();
  await expect(beneish.getByText(/threshold/)).toHaveCount(0);
});
