import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { TICKER } from "./helpers";

// Phase 7b (Instructions/27_phase7b_quarterly_and_ttm_metrics.md): the Overview's Annual /
// Quarterly toggle draws quarterly bars with the trailing twelve months as a line, and says how
// many of the four quarters a TTM needs are stored instead of showing an empty box.
// Needs the dev stack with metrics rebuilt (`scripts/build_metrics.py`).
// Spec refs: FR-QT-010, FR-QT-012, DR-QT-002.

const company = `/company/${TICKER}`;
const CAPTION = "Bars are quarters; the line is the trailing twelve months.";

async function quarterly(page: Page) {
  await page.goto(company);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const performance = page.getByRole("region", { name: "Performance" });
  await performance.getByRole("radio", { name: "Quarterly" }).click();
  return performance;
}

test("quarterly bars carry a TTM line, with the figures as a table", async ({ page }) => {
  const performance = await quarterly(page);
  await expect(performance.getByText(CAPTION)).toHaveCount(2); // revenue and net income
  await performance.getByRole("button", { name: "View Revenue as a table" }).click();
  const table = performance.getByRole("region", { name: "Revenue, as a table" });
  await expect(table.getByRole("columnheader", { name: "TTM" })).toBeVisible();
  await expect(table.getByRole("cell", { name: /^Q\d-FY\d{4}$/ }).first()).toBeVisible();

  await performance.getByRole("radio", { name: "Annual" }).click();
  await expect(performance.getByText(CAPTION)).toHaveCount(0);
});

test("an incomplete TTM window says how many quarters exist", async ({ page }) => {
  // The coverage report is mocked: a revenue quarter missing from the latest four.
  await page.route(`**/api/v1/companies/${TICKER}/metrics/coverage`, async (route) => {
    const quarters = ["Q3-FY2026", "Q4-FY2026", "Q1-FY2027", "Q2-FY2027"];
    await route.fulfill({
      json: {
        ticker: TICKER,
        quarters,
        metrics: [
          {
            metric_name: "revenue",
            applicable: true,
            present: quarters.filter((q) => q !== "Q4-FY2026"),
            missing: [{ period: "Q4-FY2026", reason: "missing_fy" }],
          },
          { metric_name: "net_income", applicable: true, present: quarters, missing: [] },
        ],
        freshness: { as_of: new Date().toISOString(), source: "sec", freshness_status: "fresh" },
      },
    });
  });
  const performance = await quarterly(page);
  await expect(performance.getByText(/3 of 4 quarters available/)).toHaveCount(1);
});
