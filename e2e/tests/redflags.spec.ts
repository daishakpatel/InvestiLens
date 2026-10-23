import { expect, test } from "@playwright/test";

import { TICKER } from "./helpers";

// Phase 7e (Instructions/30_phase7e_red_flag_panel.md): the Overview's Red flags section lists
// reported filing events, each quote opening its source in the citation drawer; the Overview tab
// carries a count; an empty result says when the company was scanned; an error can be retried.
// Needs the dev stack with flags scanned (`make redflags-backfill`).
// Spec refs: FR-RF-008, FR-RF-012, FR-RF-013, FR-RF-014.

const company = `/company/${TICKER}`;

test("flags list with severity words, and a quote opens its source", async ({ page }) => {
  await page.goto(company);
  const panel = page.getByRole("region", { name: "Red flags" });
  const rows = panel.locator("[data-testid^='red-flag-']");
  await expect(rows.first()).toBeVisible();
  await expect(panel.getByText(/Read closely|Worth reading|For awareness/).first()).toBeVisible();
  await expect(panel.getByText("Scanned through", { exact: false })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Overview/ }).getByLabel(/red flags in the last year/)).toBeVisible();

  await panel.getByText("How to read this").click();
  await expect(panel.getByText(/not a conclusion about the company/)).toBeVisible();

  await rows.first().getByRole("button", { name: /^Show the source of:/ }).click();
  const drawer = page.getByRole("dialog");
  await expect(drawer).toHaveAccessibleName("Source");
  await expect(drawer.getByRole("link", { name: /sec\.gov|Open|filing/i }).first()).toBeVisible();
});

test("an empty result says when the company was scanned", async ({ page }) => {
  await page.route(`**/api/v1/companies/${TICKER}/red-flags*`, (route) =>
    route.fulfill({
      json: { items: [], last_scanned_at: "2026-10-22T05:00:00Z", taxonomy_version: "red_flag_taxonomy_v1" },
    }),
  );
  await page.goto(company);
  const panel = page.getByRole("region", { name: "Red flags" });
  await expect(panel.getByText(/^Scanned through .*; nothing reported\.$/)).toBeVisible();
});

test("an error can be retried", async ({ page }) => {
  await page.route(`**/api/v1/companies/${TICKER}/red-flags*`, (route) =>
    route.fulfill({ status: 500, json: { title: "Internal Server Error", status: 500 } }),
  );
  await page.goto(company);
  const panel = page.getByRole("region", { name: "Red flags" });
  await expect(panel.getByText("Red flags could not be loaded.")).toBeVisible({ timeout: 30_000 });
  await expect(panel.getByRole("button", { name: "Try again" })).toBeVisible();
});
