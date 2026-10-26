import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { expect, test } from "@playwright/test";

import { signUp } from "./helpers";

// Phase 7k (Instructions/36_phase7k_thesis_tracker.md), against the dev stack: write a thesis,
// add a KPI, then move the metric across the threshold in the data and see the KPI break, the
// timeline event and the in-app notification.
// The data steps run `scripts/e2e_thesis.py` on a throwaway company (ZZTH) that is deleted
// afterwards, so no real company's data is touched:
// - "cross" stores a new reported row and runs the real evaluator;
// - "dispatch" runs one real alert-dispatch tick (the job the beat runs every 5 minutes).
// Spec refs: FR-TH-004, FR-TH-009, FR-TH-015, FR-TH-016, FR-TH-018.

const backend = fileURLToPath(new URL("../../backend", import.meta.url));
const script = (...args: string[]) =>
  execFileSync("uv", ["run", "python", "../scripts/e2e_thesis.py", ...args], { cwd: backend, encoding: "utf8" });

test.beforeAll(() => {
  script("teardown");
  script("setup");
});
test.afterAll(() => script("teardown"));

test("write a thesis, add a KPI, see it break on new data and get notified", async ({ page }) => {
  test.setTimeout(180_000);
  const email = await signUp(page);
  await page.goto("/company/ZZTH/thesis");
  await expect(page.getByText("No thesis on ZZTH yet.")).toBeVisible();

  await page.getByRole("button", { name: "New thesis" }).click();
  await page.getByLabel("Title").fill("Margins hold");
  await page.getByLabel("Stance").selectOption("long");
  await page
    .getByLabel("Thesis text")
    .fill("Pricing power keeps **gross margin** above 70%.\n\n<script>window.pwned = 1</script>\n\n- data center\n- software");
  await page.getByRole("button", { name: "Save thesis" }).click();

  const thesis = page.getByRole("article", { name: "Margins hold" });
  await expect(thesis.getByRole("heading", { name: "Margins hold" })).toBeVisible();
  const body = thesis.getByTestId("thesis-body");
  await expect(body.locator("strong")).toHaveText("gross margin");
  await expect(body).toContainText("<script>window.pwned = 1</script>"); // shown as text
  expect(await page.evaluate(() => (window as unknown as { pwned?: number }).pwned)).toBeUndefined();

  await thesis.getByRole("button", { name: "Add KPI" }).click();
  await page.getByLabel("Metric").selectOption("gross_margin");
  await page.getByLabel("Period").selectOption("TTM");
  await page.getByLabel("Threshold").fill("70");
  await page.getByLabel("Label").fill("Margins hold above 70%");
  await page.getByRole("form", { name: "KPI" }).getByRole("button", { name: "Add KPI" }).click();
  const kpis = page.getByRole("list", { name: "KPIs" });
  await expect(kpis.getByText("Met", { exact: true })).toBeVisible();
  await expect(kpis.getByRole("button", { name: /Latest 72\.00%/ })).toBeVisible();

  // The data crosses the threshold: the real evaluator, then one real alert-dispatch tick.
  script("alert", "--email", email);
  script("cross");
  await page.reload();
  const chip = page.getByRole("list", { name: "KPIs" }).getByText("Broken", { exact: true });
  await expect(chip).toBeVisible();
  await expect(chip).toHaveClass(/text-warning/); // not red: broken is not a loss (FR-TH-015)
  await expect(page.getByRole("list", { name: "Thesis timeline" })).toContainText(
    "'Margins hold above 70%' is now broken: 66.00% for TTM-Q3-FY2026.",
  );
  script("dispatch");
  await page.reload();
  await page.getByRole("button", { name: /Notifications, 1 unread/ }).click();
  await expect(page.getByText(/Your KPI 'Margins hold above 70%' \(Gross margin ≥ 70%\) is now broken/)).toBeVisible();
  await page.screenshot({ path: "test-results/thesis-notified.png" });
  await page.keyboard.press("Escape");

  // An edit adds a revision; History shows the words that changed.
  await thesis.getByRole("button", { name: "Edit" }).first().click();
  await page.getByLabel("Thesis text").fill("Pricing power keeps **gross margin** above 72%.");
  await page.getByRole("button", { name: "Save (adds a revision)" }).click();
  await page.getByRole("button", { name: "History" }).click();
  const history = page.getByRole("dialog", { name: "History" });
  await expect(history.getByText("Revision 2", { exact: false })).toBeVisible();
  await expect(history.locator("ins, del, mark, [data-op]").first()).toBeVisible();
  await page.screenshot({ path: "test-results/thesis-history.png", fullPage: true });
});
