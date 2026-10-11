import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { openPalette, signUp, TICKER } from "./helpers";

// The spec §30.3 happy path, end to end:
//   Search NVDA → load dashboard → generate report → ask question → receive citation → open source
// Plus an axe accessibility scan on the dashboard (scope #10). Requires a running, seeded stack
// with a completed research report for the ticker (`make seed`, or a worker to generate one) and
// an LLM or FakeLLM that can answer with citations. The test creates its own account, because
// reports and chat need a signed-in user (ADR-0006). See docs/testing.md for setup.

test("search → dashboard → report → chat → citation → source", async ({ page }) => {
  await signUp(page);

  // 1. Search from the home page with the command palette (keyboard-first, §9.1).
  await page.goto("/");
  await openPalette(page, "/");
  await page.getByRole("combobox").fill("nvidia");
  await page.getByRole("option", { name: new RegExp(TICKER, "i") }).first().click();

  // 2. The company page loads: name as the heading, ticker beside it, five tabs.
  await expect(page).toHaveURL(new RegExp(`/company/${TICKER}$`, "i"));
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(new RegExp(`^${TICKER} · `))).toBeVisible();
  const tabs = page.getByRole("navigation", { name: "Company sections" });

  // 3. Open the AI research report (generating it if none exists yet).
  await tabs.getByRole("link", { name: "Research" }).click();
  const generate = page.getByRole("button", { name: /generate/i });
  if (await generate.isVisible().catch(() => false)) {
    await generate.click();
  }
  await expect(page.getByText(/executive summary/i)).toBeVisible({ timeout: 120_000 });

  // 4. Ask a question (the header's "Ask" action) and receive an answer carrying a citation chip.
  await page.getByRole("link", { name: "Ask" }).click();
  await page.getByRole("textbox", { name: "Ask a question" }).fill("What drove revenue growth?");
  await page.getByRole("button", { name: /send|ask/i }).click();
  const citation = page.getByRole("button", { name: /^Open source \d+$/ }).first();
  await expect(citation).toBeVisible({ timeout: 30_000 });

  // 5. Open the source: the citation view shows the supporting passage + link to the original.
  await citation.click();
  const source = page.getByRole("dialog");
  await expect(source).toBeVisible();
  await expect(source.getByRole("link", { name: /original/i })).toBeVisible();
});

test("dashboard has no serious accessibility violations", async ({ page }) => {
  await page.goto(`/company/${TICKER}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);
});
