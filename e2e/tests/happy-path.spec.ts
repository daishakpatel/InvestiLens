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
  await expect(page.getByRole("heading", { name: "AI research" })).toBeVisible({ timeout: 120_000 });

  // 4. Ask a question (the header's "Ask" opens the assistant beside the page) and receive an
  //    answer carrying a citation. A figure question: mock mode answers those deterministically.
  await page.getByRole("button", { name: "Ask" }).click();
  const assistant = page.getByRole("dialog");
  await assistant.getByRole("textbox", { name: "Ask a question" }).fill(`What was ${TICKER}'s revenue in the latest fiscal year?`);
  await assistant.getByRole("button", { name: "Send question" }).click();
  const citation = assistant.getByRole("button", { name: /^Open source \d+$/ }).first();
  await expect(citation).toBeVisible({ timeout: 30_000 });

  // 5. Open the source: it replaces the conversation in the same panel, with a way back.
  await citation.click();
  await expect(assistant).toHaveAccessibleName("Source");
  await expect(assistant.getByRole("heading", { level: 3 })).toBeVisible();
  await expect(assistant.getByRole("button", { name: "Back to conversation" })).toBeVisible();
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
