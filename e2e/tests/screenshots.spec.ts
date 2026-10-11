import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

// Review captures for the UI rebuild (Instructions/UI_plan): every key screen, dark and light,
// desktop and phone width. Not an assertion suite — it writes PNGs to e2e/screenshots/ for a human
// to look at. Needs the dev stack running and seeded; `/_ui` exists on the dev server only.
// Run: `npm run screenshots`. Add an entry here when a step adds or changes a screen.
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
    name: "company-pinned",
    path: "/company/NVDA/financials",
    viewport: true,
    prepare: async (page) => {
      await page.mouse.wheel(0, 700);
      await page.waitForTimeout(400);
    },
  },
  { name: "company-financials", path: "/company/NVDA/financials" },
  { name: "company-research", path: "/company/NVDA/research" },
  { name: "company-filings", path: "/company/NVDA/filings" },
  { name: "company-news", path: "/company/NVDA/news" },
  { name: "company-chat", path: "/company/NVDA/chat" },
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
      const page = await context.newPage();
      for (const shot of SHOTS) {
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
