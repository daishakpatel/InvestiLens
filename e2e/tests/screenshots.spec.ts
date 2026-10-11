import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import report from "../fixtures/research-nvda.json" with { type: "json" };

// Review captures for the UI rebuild (Instructions/UI_plan): every key screen, dark and light,
// desktop and phone width. Not an assertion suite — it writes PNGs to e2e/screenshots/ for a human
// to look at. Needs the dev stack running and seeded; `/_ui` exists on the dev server only.
// Run: `npm run screenshots`. Add an entry here when a step adds or changes a screen.
// The NVDA research report is the fixture reading.spec.ts uses: dev databases hold FakeLLM
// placeholder reports, which show nothing of the layout.
interface Shot {
  name: string;
  path: string;
  /** Put the page into the state to capture (open a layer, scroll). */
  prepare?: (page: Page) => Promise<void>;
  /** Capture only the viewport: for states that depend on scroll position or an open layer. */
  viewport?: boolean;
}

const SHOTS: Shot[] = [
  { name: "ui", path: "/_ui" },
  { name: "home", path: "/" },
  {
    name: "palette",
    path: "/",
    viewport: true,
    prepare: async (page) => {
      await page.keyboard.press("ControlOrMeta+k");
      await expect(page.getByRole("dialog", { name: "Search companies" })).toBeVisible();
    },
  },
  {
    name: "palette-results",
    path: "/compare",
    viewport: true,
    prepare: async (page) => {
      await page.keyboard.press("ControlOrMeta+k");
      await page.getByRole("combobox").fill("n");
      await expect(page.getByRole("option").first()).toBeVisible();
    },
  },
  { name: "auth", path: "/login" },
  { name: "company-overview", path: "/company/NVDA" },
  {
    // The hero mid-scrub: cursor, date label, and the figure for that day.
    name: "company-overview-scrub",
    path: "/company/NVDA",
    viewport: true,
    prepare: async (page) => {
      const chart = page.getByRole("slider");
      const box = await chart.boundingBox();
      if (box) await page.mouse.move(box.x + box.width * 0.4, box.y + box.height / 2);
    },
  },
  { name: "company-overview-no-prices", path: "/company/AMD" },
  { name: "company-overview-bank", path: "/company/JPM" },
  {
    name: "company-pinned",
    path: "/company/NVDA",
    viewport: true,
    prepare: async (page) => {
      await page.mouse.wheel(0, 900);
      await page.waitForTimeout(400);
    },
  },
  { name: "company-financials", path: "/company/NVDA/financials" },
  {
    name: "company-financials-growth",
    path: "/company/NVDA/financials",
    viewport: true,
    prepare: async (page) => {
      await page.getByRole("switch", { name: "Show growth" }).click();
      await page.waitForTimeout(300);
    },
  },
  {
    // A statement table at reading size, with a lineage tooltip open.
    name: "company-financials-table",
    path: "/company/NVDA/financials",
    viewport: true,
    prepare: async (page) => {
      const table = page.getByRole("table").first();
      await table.scrollIntoViewIfNeeded();
      await page.mouse.wheel(0, 160);
      // Hover a figure so its lineage tooltip is in the capture; carry on if it is not found.
      const figure = table.locator("td", { hasText: /^215\.9$/ }).first();
      await figure.hover({ timeout: 3000 }).catch(() => undefined);
      await page.mouse.move(0, 0);
      await figure.hover({ timeout: 3000 }).catch(() => undefined);
      await page.waitForTimeout(900);
    },
  },
  { name: "company-financials-no-prices", path: "/company/AMD/financials" },
  { name: "company-financials-bank", path: "/company/JPM/financials" },
  { name: "company-research", path: "/company/NVDA/research" },
  {
    // A citation open beside the text.
    name: "company-research-source",
    path: "/company/NVDA/research",
    viewport: true,
    prepare: async (page) => {
      await page.locator("#summary").getByRole("button", { name: "Open source 1", exact: true }).click();
      await expect(page.getByRole("dialog").getByRole("heading", { level: 3 })).toBeVisible();
    },
  },
  {
    // The statements behind one count in the management-language table.
    name: "company-research-statements",
    path: "/company/NVDA/research#management",
    viewport: true,
    prepare: async (page) => {
      await page.getByRole("button", { name: /Show the statements counted/ }).first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
    },
  },
  { name: "company-research-none", path: "/company/AMD/research" },
  {
    // Changes view of the latest parsed 10-K, with one reworded risk factor expanded.
    name: "company-filings",
    path: "/company/NVDA/filings?filing=15",
    prepare: async (page) => {
      const row = page.getByRole("button", { name: /Failure to meet the evolving needs/ });
      if (await row.isVisible().catch(() => false)) await row.click();
    },
  },
  { name: "company-filings-outline", path: "/company/NVDA/filings?filing=15&view=outline" },
  { name: "company-filings-list", path: "/company/NVDA/filings" },
  { name: "company-news", path: "/company/NVDA/news" },
  {
    name: "company-news-filter",
    path: "/company/NVDA/news",
    viewport: true,
    prepare: async (page) => {
      await page.getByRole("button", { name: "Filter" }).click();
    },
  },
  { name: "company-assistant", path: "/company/NVDA/chat", viewport: true },
  { name: "company-not-found", path: "/company/ZZZZ" },
  { name: "not-found", path: "/no/such/page" },
  { name: "compare", path: "/compare" },
  { name: "portfolio", path: "/portfolio" },
];

for (const theme of ["dark", "light"] as const) {
  for (const width of [1440, 390]) {
    test(`screenshots ${theme} ${width}`, async ({ browser }) => {
      const context = await browser.newContext({
        viewport: { width, height: 900 },
        // Opposite of the theme under test: proves the app ignores the OS preference.
        colorScheme: theme === "dark" ? "light" : "dark",
      });
      // Only an explicit choice of light leaves dark (ADR-0028).
      await context.addInitScript((t) => {
        if (t === "light") localStorage.setItem("il-theme", "light");
        else localStorage.removeItem("il-theme");
      }, theme);
      await context.route("**/companies/NVDA/research/latest", (route) => route.fulfill({ json: report }));
      const page = await context.newPage();
      for (const shot of SHOTS) {
        // A blank page first: two shots that differ only by hash would otherwise share a
        // document, and the second would inherit whatever the first left open.
        await page.goto("about:blank");
        await page.goto(shot.path);
        await page.waitForLoadState("networkidle");
        await page.evaluate(() => document.fonts.ready);
        await shot.prepare?.(page);
        await page.screenshot({
          path: `screenshots/${theme}/${width}/${shot.name}.png`,
          fullPage: !shot.viewport,
        });
      }
      await context.close();
    });
  }
}
