import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

// The spec §30.3 happy path, end to end:
//   Search NVDA → load dashboard → generate report → ask question → receive citation → open source
// Plus an axe accessibility scan on the dashboard (scope #10). Requires a running, seeded stack
// with a signed-in user and a completed research report (ADR-0006: report + chat need auth; the
// Celery worker from Phase 5d produces the report). See docs/testing.md for setup.

const TICKER = process.env.E2E_TICKER ?? "NVDA";

test("search → dashboard → report → chat → citation → source", async ({ page }) => {
  // 1. Search from the home page.
  await page.goto("/");
  const search = page.getByRole("combobox", { name: /search/i });
  await search.fill("nvidia");
  await page.getByRole("option", { name: new RegExp(TICKER, "i") }).first().click();

  // 2. Dashboard loads with the company header.
  await expect(page).toHaveURL(new RegExp(`/company/${TICKER}`, "i"));
  await expect(page.getByRole("heading", { level: 1 })).toContainText(TICKER);

  // 3. Open the AI research report (generating it if none exists yet).
  await page.getByRole("link", { name: /research/i }).click();
  const generate = page.getByRole("button", { name: /generate/i });
  if (await generate.isVisible().catch(() => false)) {
    await generate.click();
  }
  await expect(page.getByText(/executive summary/i)).toBeVisible({ timeout: 120_000 });

  // 4. Ask a question in chat and receive an answer carrying a citation chip.
  await page.getByRole("link", { name: /chat/i }).click();
  await page.getByRole("textbox").fill("What drove revenue growth?");
  await page.getByRole("button", { name: /send|ask/i }).click();
  const citation = page.getByRole("button", { name: /^\[?\d+\]?$/ }).first();
  await expect(citation).toBeVisible({ timeout: 30_000 });

  // 5. Open the source: the citation modal shows the supporting passage + link to the original.
  await citation.click();
  const modal = page.getByRole("dialog");
  await expect(modal).toBeVisible();
  await expect(modal.getByRole("link", { name: /original/i })).toBeVisible();
});

test("dashboard has no serious accessibility violations", async ({ page }) => {
  await page.goto(`/company/${TICKER}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});
