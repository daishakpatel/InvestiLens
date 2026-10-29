import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { TICKER, withoutPrices } from "./helpers";

// UI plan Step 3 (Instructions/UI_plan/03_company_overview_and_data.md): the price hero, key
// figures, Overview, and Financials. Needs the dev stack with the seed companies; AMD is served
// without prices for the no-price case (`withoutPrices`).
// Spec refs: §9.4, §10.2-§10.8, §12 (DR-040 to DR-042), FR-011, FR-013, UI-003, UI-006.

const company = `/company/${TICKER}`;
const NO_PRICES = "AMD";
const BANK = "JPM"; // gross margin is not applicable to its sector (DR-042)

const hero = (page: Page) => page.getByTestId("hero-price");
const chart = (page: Page) => page.getByRole("slider", { name: /price/i });

/** Move keyboard focus onto an element the way a person would. A tooltip opens for keyboard
 *  focus only; a scripted `.focus()` alone does not count as keyboard use. */
async function tabTo(page: Page, target: Locator) {
  await target.focus();
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await expect(target).toBeFocused();
}

async function loaded(page: Page, path: string) {
  await page.goto(path);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await page.waitForLoadState("networkidle");
}

test.describe("price hero (§9.4, FR-011)", () => {
  test("leads with a 48 px price and a change for the chosen range", async ({ page }) => {
    await loaded(page, company);
    await expect(hero(page)).toHaveText(/^\$[\d,]+\.\d{2}$/);
    await expect(hero(page)).toHaveCSS("font-size", "48px");
    const price = page.getByRole("region", { name: "Price" });
    await expect(price).toContainText("past year");
    await expect(price).toContainText(/[+−]\$[\d,.]+ \([+−][\d.]+%\)/); // signed, not colour alone
    await expect(price).toContainText("End-of-day close · as of"); // FR-011: no "live" pretence
  });

  test("changing range slices what is loaded and never refetches", async ({ page }) => {
    let priceRequests = 0;
    page.on("request", (request) => {
      if (/\/prices(\?|$)/.test(request.url())) priceRequests += 1;
    });
    await loaded(page, company);
    const afterLoad = priceRequests;
    const price = page.getByRole("region", { name: "Price" });
    for (const [range, phrase] of [
      ["1M", "past month"],
      ["5Y", "past 5 years"],
      ["3M", "past 3 months"],
    ]) {
      await page.getByRole("radio", { name: range, exact: true }).click();
      await expect(price).toContainText(phrase);
    }
    expect(priceRequests).toBe(afterLoad);
  });

  test("scrubs with the mouse and moves nothing else on the page", async ({ page }) => {
    await loaded(page, company);
    const latest = await hero(page).innerText();
    const price = page.getByRole("region", { name: "Price" });
    const measure = () =>
      page.evaluate(() => ({
        page: document.documentElement.scrollHeight,
        chart: document.querySelector('[role="slider"]')!.getBoundingClientRect().top,
      }));
    const before = await measure();

    const box = (await chart(page).boundingBox())!;
    await page.mouse.move(box.x + box.width * 0.25, box.y + box.height / 2);
    await expect(hero(page)).not.toHaveText(latest);
    await expect(price).toContainText(/\w{3} \d{1,2}, \d{4} to \w{3} \d{1,2}, \d{4}/);
    expect(await measure()).toEqual(before); // no layout shift while scrubbing

    await page.mouse.move(box.x + box.width / 2, box.y + box.height + 200);
    await expect(hero(page)).toHaveText(latest); // leaving restores the latest price
  });

  test("scrubs with the arrow keys, one trading day at a time (UI-003)", async ({ page }) => {
    await loaded(page, company);
    const latest = await hero(page).innerText();
    await chart(page).focus();
    const last = Number(await chart(page).getAttribute("aria-valuemax"));

    await page.keyboard.press("ArrowLeft");
    await expect(chart(page)).toHaveAttribute("aria-valuenow", String(last - 1));
    await expect(chart(page)).toHaveAttribute("aria-valuetext", /\w{3} \d{1,2}, \d{4}: \$/);
    await page.keyboard.press("Home");
    await expect(chart(page)).toHaveAttribute("aria-valuenow", "0");
    await page.keyboard.press("Escape");
    await expect(hero(page)).toHaveText(latest);
  });

  test("scrubs with a finger, and lifting it restores the latest price", async ({ browser }) => {
    const context = await browser.newContext({ hasTouch: true, viewport: { width: 390, height: 800 } });
    const page = await context.newPage();
    await loaded(page, company);
    const latest = await hero(page).innerText();
    const box = (await chart(page).boundingBox())!;
    const at = (fraction: number) => ({
      clientX: box.x + box.width * fraction,
      clientY: box.y + box.height / 2,
      pointerType: "touch",
      bubbles: true,
    });
    await chart(page).dispatchEvent("pointerdown", at(0.2));
    await chart(page).dispatchEvent("pointermove", at(0.3));
    await expect(hero(page)).not.toHaveText(latest);
    await chart(page).dispatchEvent("pointerup", at(0.3));
    await expect(hero(page)).toHaveText(latest);
    await context.close();
  });

  test("offers the same prices as a table and as a CSV (FR-013)", async ({ page }) => {
    await loaded(page, company);
    await page.getByRole("button", { name: "View prices as a table" }).click();
    await expect(page.getByRole("columnheader", { name: "Adjusted close" })).toBeVisible();
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download prices as CSV" }).click();
    expect((await download).suggestedFilename()).toBe(`${TICKER}_prices_1Y.csv`);
  });
});

test.describe("overview", () => {
  test("a company with no prices gets a clean page: no empty chart, no dashes", async ({ page }) => {
    await withoutPrices(page, NO_PRICES);
    await loaded(page, `/company/${NO_PRICES}`);
    await expect(page.getByText(`No price data is available for ${NO_PRICES} yet.`)).toBeVisible();
    await expect(page.getByRole("slider")).toHaveCount(0);
    const figures = page.getByRole("region", { name: "Key figures" });
    await expect(figures).toContainText("Revenue");
    await expect(figures).not.toContainText("—");
    await expect(figures).not.toContainText("Market cap"); // omitted until it has a value
  });

  test("a metric that does not apply is left out, never shown as 0 (DR-041, DR-042)", async ({ page }) => {
    await loaded(page, `/company/${BANK}`);
    const figures = page.getByRole("region", { name: "Key figures" });
    await expect(figures).toContainText("Net income");
    await expect(figures).not.toContainText("Gross margin");

    await loaded(page, `/company/${BANK}/financials`);
    const margins = page.getByRole("region", { name: "Margins", exact: true });
    await expect(margins).toContainText("Not applicable to this company’s sector.");
    await expect(margins.getByRole("row", { name: /Gross margin/ })).toContainText("N/A");
  });

  test("key figures explain where they come from on keyboard focus (§9.4)", async ({ page }) => {
    await loaded(page, company);
    const figures = page.getByRole("region", { name: "Key figures" });
    await tabTo(page, figures.locator('[tabindex="0"]').first());
    await expect(page.getByRole("tooltip")).toContainText("SEC filings (XBRL)");
  });

  test("the pinned bar shows the price only when the page is not already showing it", async ({ page }) => {
    await loaded(page, company);
    const quote = page.getByTestId("pinned-quote");
    await expect(quote).toHaveCSS("opacity", "0"); // the hero is on screen
    await page.mouse.wheel(0, 900);
    await expect(quote).toHaveCSS("opacity", "1");
    await expect(quote).toContainText("$");

    await loaded(page, `${company}/financials`);
    await expect(page.getByTestId("pinned-quote")).toHaveCSS("opacity", "1"); // no hero here
  });
});

test.describe("charts (FR-013, UI-003)", () => {
  test("every chart has a table view and a CSV download", async ({ page }) => {
    await loaded(page, `${company}/financials`);
    const revenue = page.getByRole("figure").filter({ hasText: "Revenue" }).first();
    await revenue.getByRole("button", { name: "View Revenue as a table" }).click();
    await expect(revenue.getByRole("columnheader", { name: "Period" })).toBeVisible();
    await expect(revenue.getByRole("row").nth(1)).toContainText(/FY\d{4}/);

    const download = page.waitForEvent("download");
    await revenue.getByRole("button", { name: "Download Revenue as CSV" }).click();
    expect((await download).suggestedFilename()).toBe(`${TICKER}_revenue_FY.csv`);

    const charts = await page.getByRole("figure").count();
    expect(await page.getByRole("button", { name: /as a table$/ }).count()).toBe(charts - 1);
  });

  test("charts follow the theme switch without a reload", async ({ page }) => {
    await loaded(page, `${company}/financials`);
    const bar = page.locator(".recharts-bar-rectangle path").first();
    const dark = await bar.evaluate((el) => getComputedStyle(el).fill);
    await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("menuitemradio", { name: "Light" }).click();
    await expect.poll(() => bar.evaluate((el) => getComputedStyle(el).fill)).not.toBe(dark);
  });
});

test.describe("financials (§10.2-§10.8, §12)", () => {
  test("one controls row scopes five sections", async ({ page }) => {
    await loaded(page, `${company}/financials`);
    const nav = page.getByRole("navigation", { name: "Financial sections" });
    await expect(nav.getByRole("link")).toHaveText([
      "Income",
      "Margins",
      "Cash flow",
      "Balance sheet",
      "Valuation",
    ]);
    await expect(page.getByRole("radiogroup", { name: "Period" })).toHaveCount(1);

    await nav.getByRole("link", { name: "Balance sheet" }).click();
    await expect(page).toHaveURL(/#balance-sheet$/);
    await expect(page.getByRole("heading", { name: "Balance sheet" })).toBeInViewport();
    await expect(nav.getByRole("link", { name: "Balance sheet" })).toHaveAttribute("aria-current", "location");
  });

  test("a period with no data says so instead of leading to empty charts", async ({ page }) => {
    // A company with fewer than four reported quarters has no TTM (DR-QT-002): mocked here.
    await page.route(
      (url) => url.pathname.endsWith("/financials") && url.searchParams.get("period_type") === "TTM",
      (route) =>
        route.fulfill({
          json: {
            ticker: TICKER,
            period_type: "TTM",
            series: [{ metric_name: "revenue", points: [] }],
            freshness: { as_of: new Date().toISOString(), source: "sec", freshness_status: "fresh" },
          },
        }),
    );
    await loaded(page, `${company}/financials`);
    const trailing = page.getByText("TTM", { exact: true });
    await expect(trailing).toHaveAttribute("aria-disabled", "true");
    // The innermost focusable wrapper (the option itself, not the group around it).
    await tabTo(page, page.locator('[tabindex="0"]', { has: trailing }).last());
    await expect(page.getByRole("tooltip")).toContainText("need four reported quarters");

    // Phase 7b: every fiscal quarter is stored now, balances included.
    await page.getByRole("radio", { name: "Quarterly" }).click();
    await expect(page.getByText(/The latest eight fiscal quarters/)).toBeVisible();
    await expect(page.getByRole("figure").filter({ hasText: "Revenue" }).first()).toBeVisible();
    await expect(page.getByRole("region", { name: "Balance sheet", exact: true })).not.toContainText(/No fiscal quarters figures/);
  });

  test("show growth caps each bar with what it added or lost, with a key", async ({ page }) => {
    await loaded(page, `${company}/financials`);
    const income = page.getByRole("region", { name: "Income", exact: true });
    await expect(income.getByText("Added", { exact: true }).first()).toBeHidden();
    await page.getByRole("switch", { name: "Show growth" }).click();
    await expect(income.getByText("Added", { exact: true }).first()).toBeVisible();
    await expect(income.getByText("Lost", { exact: true }).first()).toBeVisible();
  });

  test("statement figures show their lineage on hover, and by keyboard (DR-040, CIT-003)", async ({ page }) => {
    await loaded(page, `${company}/financials`);
    const income = page.getByRole("table").first();
    await income.scrollIntoViewIfNeeded();
    await expect(page.getByText(/US dollars in billions/).first()).toBeVisible();

    const cell = income.getByRole("row", { name: /Revenue/ }).getByRole("cell").last();
    await cell.hover();
    await page.mouse.move(0, 0);
    await cell.hover();
    await expect(page.getByRole("tooltip")).toContainText("As reported in SEC filings");

    await page.mouse.move(0, 0);
    const margins = page.getByRole("table").nth(1);
    await tabTo(page, margins.locator('[tabindex="0"]', { hasText: "Gross margin" }));
    await expect(page.getByRole("tooltip")).toContainText("Formula: gross_margin");
  });

  test("the old Valuation tab's content lives here, and says plainly when there is none", async ({ page }) => {
    await loaded(page, `${company}/valuation`);
    await expect(page).toHaveURL(/financials#valuation$/);
    await expect(page.getByRole("region", { name: "Valuation", exact: true })).toBeVisible();
  });
});

test("overview and financials fit a 360 px screen (UI-006)", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 360, height: 780 } });
  const page = await context.newPage();
  for (const ticker of [TICKER, NO_PRICES, BANK]) {
    for (const tab of ["", "/financials"]) {
      await loaded(page, `/company/${ticker}${tab}`);
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${ticker}${tab} overflows`).toBeLessThanOrEqual(0);
    }
  }
  await context.close();
});
