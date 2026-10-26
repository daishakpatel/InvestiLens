import { execFileSync } from "node:child_process";
import { mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// Phase 7l Part E (Instructions/37_phase7l_measured_results_and_polish.md): the five-minute path,
// against the demo build (DEMO_MODE API on the seeded demo database, production frontend build).
// `scripts/vertical_slice.sh` starts that stack, runs this spec and turns its frames into
// docs/media/demo.gif. Spec refs: NFR-ME-007, NFR-ME-010, NFR-ME-012.
//
// 1. NVIDIA overview: quarterly/TTM toggle, red-flag panel, earnings quality;
// 2. the cited question from /demo, then its citation in the drawer (recorded answer);
// 3. the latest earnings brief, and guidance vs actual;
// 4. a thesis KPI that breaks on new data, and the in-app notification. The data step reuses the
//    Phase 7k helper on its throwaway company (ZZTH) in the demo database.

const backend = fileURLToPath(new URL("../../backend", import.meta.url));
const frames = fileURLToPath(new URL("../test-results/vertical-slice/", import.meta.url));
const demoDb = process.env.DEMO_DATABASE_URL;
const thesisData = (...args: string[]) =>
  execFileSync("uv", ["run", "python", "../scripts/e2e_thesis.py", ...args], {
    cwd: backend,
    encoding: "utf8",
    env: { ...process.env, DATABASE_URL: demoDb ?? "" },
  });

let frameNo = 0;
async function frame(page: Page, name: string): Promise<void> {
  frameNo += 1;
  await page.waitForTimeout(400); // let transitions finish so the frame shows the settled state
  await page.screenshot({ path: `${frames}${String(frameNo).padStart(2, "0")}-${name}.png` });
}

test.describe.configure({ mode: "serial" });
test.skip(!demoDb, "set DEMO_DATABASE_URL (scripts/vertical_slice.sh does) to run against the demo");

test.beforeAll(() => {
  mkdirSync(frames, { recursive: true });
  thesisData("teardown");
  thesisData("setup");
});
test.afterAll(() => thesisData("teardown"));

test("the five-minute path runs on the demo with no console errors", async ({ page }) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 1280, height: 800 });
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${message.text()} ${message.location().url}`);
  });
  page.on("pageerror", (error) => errors.push(error.message));

  // --- the guided path's start: the banner and three scenarios ---------------------------
  await page.goto("/demo");
  await expect(page.getByRole("note").filter({ hasText: /^Demo: fixture data as of .+\. Not investment advice\.$/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Open: / })).toHaveCount(3);
  await frame(page, "demo");

  // --- 1. NVIDIA at a glance --------------------------------------------------------------
  await page.getByRole("button", { name: "Open: NVIDIA at a glance" }).click();
  await expect(page).toHaveURL(/\/company\/NVDA$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("NVIDIA");
  const performance = page.getByRole("region", { name: "Performance" });
  await performance.getByRole("radio", { name: "Quarterly" }).click();
  await performance.getByRole("button", { name: "View Revenue as a table" }).click();
  await expect(performance.getByRole("region", { name: "Revenue, as a table" }).getByRole("columnheader", { name: "TTM" })).toBeVisible();
  await frame(page, "overview-quarterly");
  const flags = page.getByRole("region", { name: "Red flags" });
  await flags.scrollIntoViewIfNeeded();
  await expect(flags.getByText("Scanned through", { exact: false })).toBeVisible();
  await frame(page, "red-flags");
  const tabs = page.getByRole("navigation", { name: "Company sections" });
  await tabs.getByRole("link", { name: "Earnings quality" }).click();
  await expect(page.getByRole("region", { name: "Cash vs earnings" })).toBeVisible();
  await frame(page, "earnings-quality");

  // --- 2. a cited answer, and its source ------------------------------------------------
  await page.goto("/demo");
  await page.getByRole("button", { name: "Open: Ask a cited question" }).click();
  const assistant = page.getByRole("dialog");
  await expect(assistant.getByText("What changed in risk factors vs last year?")).toBeVisible();
  const citation = assistant.getByRole("button", { name: /^Open source \d+$/ }).first();
  await expect(citation).toBeVisible({ timeout: 30_000 });
  await frame(page, "cited-answer");
  await citation.click();
  await expect(assistant.getByRole("button", { name: "Back to conversation" })).toBeVisible();
  await expect(assistant.getByRole("heading", { level: 3 })).toBeVisible();
  await frame(page, "citation-drawer");
  await assistant.getByRole("button", { name: "Close panel" }).click();
  await expect(assistant).toBeHidden();

  // --- 3. the latest brief, and guidance vs actual ----------------------------------------
  await tabs.getByRole("link", { name: "Earnings", exact: true }).click();
  await expect(page.getByRole("region", { name: "Reported figures" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Against company guidance" })).toBeVisible();
  await frame(page, "earnings-brief");
  await tabs.getByRole("link", { name: "Filings", exact: true }).click();
  const guidance = page.getByRole("region", { name: "Guidance vs actual" });
  await guidance.scrollIntoViewIfNeeded();
  await expect(guidance).toContainText(/revenue/i);
  await frame(page, "guidance-vs-actual");

  // --- 4. a thesis KPI that breaks, and the notification -----------------------------------
  thesisData("alert", "--email", "demo@example.com");
  await page.goto("/company/ZZTH/thesis");
  await page.getByRole("button", { name: "New thesis" }).click();
  await page.getByLabel("Title").fill("Margins hold");
  await page.getByLabel("Stance").selectOption("watch");
  await page.getByLabel("Thesis text").fill("Pricing power keeps **gross margin** above 70%.");
  await page.getByRole("button", { name: "Save thesis" }).click();
  const thesis = page.getByRole("article", { name: "Margins hold" });
  await thesis.getByRole("button", { name: "Add KPI" }).click();
  await page.getByLabel("Metric").selectOption("gross_margin");
  await page.getByLabel("Period").selectOption("TTM");
  await page.getByLabel("Threshold").fill("70");
  await page.getByLabel("Label").fill("Margins hold above 70%");
  await page.getByRole("form", { name: "KPI" }).getByRole("button", { name: "Add KPI" }).click();
  await expect(page.getByRole("list", { name: "KPIs" }).getByText("Met", { exact: true })).toBeVisible();
  await frame(page, "thesis-kpi-met");

  thesisData("cross");
  await page.reload();
  await expect(page.getByRole("list", { name: "KPIs" }).getByText("Broken", { exact: true })).toBeVisible();
  await frame(page, "thesis-kpi-broken");
  thesisData("dispatch");
  await page.reload();
  await page.getByRole("button", { name: /Notifications, 1 unread/ }).click();
  // Newest first; a reused demo database keeps earlier runs' (already read) notifications.
  await expect(page.getByText(/Your KPI 'Margins hold above 70%' .* is now broken/).first()).toBeVisible();
  await frame(page, "notification");

  expect(errors, "unexpected console errors on the five-minute path").toEqual([]);
});
