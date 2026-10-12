import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import report from "../fixtures/research-nvda.json" with { type: "json" };
import { settled } from "./helpers";

// Visual regression (UI plan Step 5): the key screens, dark and light, at 1440 px and 390 px,
// compared with committed baselines. Run with `npm run visual`.
//
// It needs only the frontend. Every API response is replayed from `fixtures/visual.har`, the
// clock is fixed, and the research report is the fixture the other specs use, so the pictures do
// not depend on what is in the database or on today's date.
//
// - A screen changed on purpose: `npm run visual -- --update-snapshots`, then look at the diff.
// - The API's responses changed shape: `npm run visual:record` against the dev stack, then
//   update the snapshots.
// Baselines are per operating system (text is drawn differently on each); those committed are
// macOS. On another system the first run writes its own.
const HAR = "fixtures/visual.har";
const NOW = new Date("2026-10-11T12:00:00Z");
const RECORDING = process.env.VISUAL_RECORD === "1";

const SCREENS: { name: string; path: string }[] = [
  { name: "home", path: "/" },
  { name: "company-overview", path: "/company/NVDA" },
  { name: "company-financials", path: "/company/NVDA/financials" },
  { name: "company-research", path: "/company/NVDA/research" },
  { name: "company-filings", path: "/company/NVDA/filings?filing=15" },
  { name: "company-news", path: "/company/NVDA/news" },
  { name: "company-assistant", path: "/company/NVDA/chat" },
  { name: "compare", path: "/compare" },
  { name: "portfolio", path: "/portfolio" },
];

async function prepare(page: Page, theme: "dark" | "light") {
  await page.clock.setFixedTime(NOW);
  await page.addInitScript((t) => {
    if (t === "light") localStorage.setItem("il-theme", "light");
  }, theme);
  // A request the recording does not hold is refused rather than sent to a live API: the
  // screen then shows its error state, and the comparison fails loudly.
  await page.routeFromHAR(HAR, {
    url: "**/api/v1/**",
    update: RECORDING,
    updateContent: "embed",
    updateMode: "minimal",
    notFound: "abort",
  });
  await page.route("**/companies/NVDA/research/latest", (route) => route.fulfill({ json: report }));
}

async function open(page: Page, path: string) {
  await page.goto(path);
  await page.waitForLoadState("networkidle");
  await page.evaluate(() => document.fonts.ready);
  await settled(page);
}

// Tagged so that `npm test` (behaviour) leaves these out; `npm run visual` runs them.
test.describe("visual regression @visual", () => {
  test.skip(RECORDING, "recording the API responses, not comparing");
  for (const theme of ["dark", "light"] as const) {
    for (const width of [1440, 390]) {
      for (const screen of SCREENS) {
        test(`${screen.name} ${theme} ${width}`, async ({ page }) => {
          await page.setViewportSize({ width, height: 900 });
          await prepare(page, theme);
          await open(page, screen.path);
          await expect(page).toHaveScreenshot(`${screen.name}-${theme}-${width}.png`, {
            maxDiffPixelRatio: 0.01,
          });
        });
      }
    }
  }
});

// One context walks every screen at both widths so that all the responses land in one file.
test("record the API responses the visual spec replays @visual", async ({ page }) => {
  test.skip(!RECORDING, "set VISUAL_RECORD=1 (npm run visual:record) with the dev stack running");
  await prepare(page, "dark");
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 900 });
    for (const screen of SCREENS) await open(page, screen.path);
  }
});
