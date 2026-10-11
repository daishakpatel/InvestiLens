import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { openPalette, signUp, TICKER } from "./helpers";

// UI plan Step 2 (Instructions/UI_plan/02_app_shell_and_navigation.md): the app shell, command
// palette, company frame, and global states. Needs the dev stack running with the seed companies.
// Spec refs: §9.1-§9.2 (search, disambiguation), FR-001, FR-012, UI-003, UI-006, §28.2.

const DISCLAIMER = /not investment advice/i;
const company = `/company/${TICKER}`;

async function scrollWidthOverflow(page: Page): Promise<number> {
  return page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
}

test.describe("command palette (§9.1, FR-001, UI-003)", () => {
  for (const path of ["/", company, "/compare", "/login"]) {
    test(`opens with Ctrl/⌘+K and "/" on ${path}`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole("note").filter({ hasText: DISCLAIMER })).toBeVisible(); // FR-012
      const dialog = await openPalette(page, "ControlOrMeta+k");
      await page.keyboard.press("Escape");
      await expect(dialog).toBeHidden();
      await openPalette(page, "/");
      // "/" typed into the palette is text, not a shortcut.
      await page.keyboard.type("a/b");
      await expect(page.getByRole("combobox")).toHaveValue("a/b");
    });
  }

  test("a company is reachable from a cold load with the keyboard alone", async ({ page }) => {
    await page.goto("/");
    await openPalette(page, "/");
    await page.keyboard.type(TICKER.toLowerCase());
    await expect(page.getByRole("option").first()).toContainText(TICKER);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`${company}$`));
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("an ambiguous query never navigates until the user picks a row (§9.2)", async ({ page }) => {
    // Hold search responses back so Enter can arrive before any result is on screen.
    await page.route("**/companies/search**", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 800));
      await route.continue();
    });
    await page.goto("/compare");
    const dialog = await openPalette(page);
    await page.keyboard.type("n");
    await page.keyboard.press("Enter"); // nothing is highlighted yet: must do nothing
    await expect(dialog).toBeVisible();
    await expect(page).toHaveURL(/\/compare$/);

    const options = page.getByRole("option");
    await expect(options.nth(1)).toBeVisible(); // several matches: ambiguous
    await expect(page).toHaveURL(/\/compare$/);

    const second = (await options.nth(1).innerText()).split(/\s+/)[0];
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(new RegExp(`/company/${second}$`));
  });

  test("no match says so, and offers no fallback destination", async ({ page }) => {
    await page.goto("/");
    await openPalette(page);
    await page.keyboard.type("zzzzqq");
    await expect(page.getByText(/No companies match/)).toBeVisible();
    await expect(page.getByRole("option")).toHaveCount(0);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe("company frame", () => {
  test("has five tabs and every pre-rebuild URL still lands somewhere", async ({ page }) => {
    await page.goto(company);
    const tabs = page.getByRole("navigation", { name: "Company sections" }).getByRole("link");
    await expect(tabs).toHaveText(["Overview", "Financials", "Research", "Filings", "News"]);

    const redirects: [from: string, to: RegExp][] = [
      ["overview", new RegExp(`${company}$`)],
      ["valuation", new RegExp(`${company}/financials#valuation$`)],
      ["risks", new RegExp(`${company}/research#risks$`)],
      ["management", new RegExp(`${company}/research#management$`)],
      ["ownership", new RegExp(`${company}$`)],
      ["financials", new RegExp(`${company}/financials$`)],
      ["filings", new RegExp(`${company}/filings$`)],
      ["news", new RegExp(`${company}/news$`)],
      ["research", new RegExp(`${company}/research$`)],
      ["chat", new RegExp(`${company}/chat$`)],
    ];
    for (const [from, to] of redirects) {
      await page.goto(`${company}/${from}`);
      await expect(page).toHaveURL(to);
      await expect(page.getByRole("heading", { level: 1 })).not.toHaveText(/not found/i);
    }
  });

  test("the sub-header pins with the price and moves nothing", async ({ page }) => {
    await page.goto(`${company}/financials`);
    const nav = page.getByRole("navigation", { name: "Company sections" });
    const quote = page.getByTestId("pinned-quote");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expect(quote).toHaveCSS("opacity", "0");

    const before = await page.evaluate(() => ({
      height: document.documentElement.scrollHeight,
      navHeight: document.querySelector('nav[aria-label="Company sections"]')!.getBoundingClientRect().height,
    }));
    await page.mouse.wheel(0, 900);
    await expect(quote).toHaveCSS("opacity", "1");
    await expect(quote).toContainText(TICKER);
    await expect(quote).toContainText("$");

    const box = await nav.boundingBox();
    expect(Math.round(box!.y)).toBe(56); // directly under the 56 px top bar
    const after = await page.evaluate(() => ({
      height: document.documentElement.scrollHeight,
      navHeight: document.querySelector('nav[aria-label="Company sections"]')!.getBoundingClientRect().height,
    }));
    expect(after).toEqual(before); // pinning changed no heights: no layout shift
  });

  test("an unknown ticker gets a way forward, not an error box", async ({ page }) => {
    await page.goto("/company/ZZZZ");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("No company found");
    await expect(page.getByRole("navigation", { name: "Company sections" })).toHaveCount(0);
    await page.getByRole("button", { name: "Search companies" }).last().click();
    await expect(page.getByRole("dialog", { name: "Search companies" })).toBeVisible();
  });

  test("an unknown address shows the 404 page with search", async ({ page }) => {
    await page.goto("/no/such/page");
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Page not found");
    await expect(page.getByRole("button", { name: "Search companies" }).last()).toBeVisible();
    await expect(page.getByRole("note").filter({ hasText: DISCLAIMER })).toBeVisible();
  });
});

test.describe("layout (UI-006)", () => {
  test("no horizontal page scroll at 360 px", async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 360, height: 780 } });
    const page = await context.newPage();
    const paths = ["/", "/login", company, `${company}/financials`, `${company}/research`];
    paths.push(`${company}/filings`, `${company}/news`, `${company}/chat`, "/company/ZZZZ");
    for (const path of paths) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      expect(await scrollWidthOverflow(page), `${path} overflows`).toBeLessThanOrEqual(0);
    }
    // The tab strip scrolls inside itself and brings the active tab into view.
    await page.goto(`${company}/news`);
    await expect(page.getByRole("link", { name: "News", exact: true })).toBeInViewport();
    await context.close();
  });

  test("phones get search and both tools without a hamburger", async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 390, height: 800 } });
    const page = await context.newPage();
    await page.goto(company);
    await page.getByRole("button", { name: "Search companies" }).click();
    await expect(page.getByRole("dialog", { name: "Search companies" })).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Menu" }).click();
    await expect(page.getByRole("menuitem", { name: "Compare" })).toBeVisible();
    await page.getByRole("menuitem", { name: "Portfolio" }).click();
    await expect(page).toHaveURL(/\/portfolio$/);
    await context.close();
  });
});

test.describe("global states (§28.2)", () => {
  test("an outage shows one banner, no per-panel errors, and recovers by itself", async ({ page }) => {
    await page.route("**/api/v1/**", (route) => route.abort());
    await page.goto(company);
    const banner = page.getByRole("status").filter({ hasText: /Can’t reach InvestiLens/ });
    await expect(banner).toBeVisible();
    await expect(banner).toHaveCount(1);
    await expect(page.getByRole("alert")).toHaveCount(0);

    await page.unroute("**/api/v1/**");
    await expect(banner).toBeHidden({ timeout: 15_000 });
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible(); // loaded without a click
  });

  test("one failing endpoint is not treated as an outage and is not retried in a loop", async ({ page }) => {
    let calls = 0;
    await page.route("**/research/latest", (route) => {
      calls += 1;
      return route.fulfill({ status: 500, contentType: "application/problem+json", body: "{}" });
    });
    await page.goto(`${company}/research`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await page.waitForTimeout(4000);
    expect(calls).toBeLessThanOrEqual(3); // first try, one retry, and StrictMode's remount at most
    await expect(page.getByText(/Can’t reach InvestiLens/)).toHaveCount(0);
  });
});

test.describe("account", () => {
  test("theme is switched from the menu and persists (UI-007)", async ({ page }) => {
    await page.emulateMedia({ colorScheme: "light" });
    await page.goto("/");
    await expect(page.locator("html")).not.toHaveClass(/light/); // dark regardless of the OS
    await page.getByRole("button", { name: "Menu" }).click();
    await page.getByRole("menuitemradio", { name: "Light" }).click();
    await expect(page.locator("html")).toHaveClass(/light/);
    await page.reload();
    await expect(page.locator("html")).toHaveClass(/light/);
  });

  test("sign-in validates inline and reports the API's own message", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByText("Enter a valid email address.")).toBeVisible();
    await expect(page.getByLabel("Email")).toBeFocused();

    await page.getByRole("button", { name: "Create an account" }).click();
    await expect(page.getByText("At least 12 characters.")).toBeVisible(); // rule shown up front
    await page.getByLabel("Email").fill("someone@example.com");
    await page.getByLabel("Password").fill("short");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.getByText("Use at least 12 characters.")).toBeVisible();

    await page.getByRole("button", { name: "Sign in", exact: true }).click(); // back to sign-in
    await page.getByLabel("Email").fill("nobody-here@example.com");
    await page.getByLabel("Password").fill("definitely-not-the-password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(page.getByRole("alert")).toContainText(/\S/); // whatever the API said, verbatim
  });

  test("signing in returns to the page you came from, and the session survives a reload", async ({ page }) => {
    await page.goto(`${company}/filings`);
    await page.getByRole("link", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.getByRole("button", { name: "Create an account" }).click();
    const email = `e2e-${Date.now()}@example.com`;
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Password").fill("correct-horse-battery-staple");
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page).toHaveURL(new RegExp(`${company}/filings$`));

    await page.reload();
    await page.getByRole("button", { name: "Account menu" }).click();
    await expect(page.getByText(email)).toBeVisible();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page.getByRole("link", { name: "Sign in" })).toBeVisible();
  });

  test("helper: sign-up lands signed in", async ({ page }) => {
    await signUp(page);
  });
});
