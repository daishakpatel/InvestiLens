import { test } from "@playwright/test";

// Review captures for the UI rebuild (Instructions/UI_plan): every key screen, dark and light,
// desktop and phone width. Not an assertion suite — it writes PNGs to e2e/screenshots/ for a human
// to look at. Needs the dev stack running and seeded; `/_ui` exists on the dev server only.
// Run: `npm run screenshots`. Add a route here when a step adds or changes a screen.
const ROUTES: [name: string, path: string][] = [
  ["ui", "/_ui"],
  ["home", "/"],
  ["company-overview", "/company/NVDA/overview"],
  ["company-financials", "/company/NVDA/financials"],
  ["company-filings", "/company/NVDA/filings"],
  ["company-management", "/company/NVDA/management"],
  ["company-research", "/company/NVDA/research"],
  ["compare", "/compare?tickers=NVDA,AMD,INTC"],
  ["portfolio", "/portfolio"],
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
      for (const [name, path] of ROUTES) {
        await page.goto(path);
        await page.waitForLoadState("networkidle");
        await page.evaluate(() => document.fonts.ready);
        await page.screenshot({ path: `screenshots/${theme}/${width}/${name}.png`, fullPage: true });
      }
      await context.close();
    });
  }
}
