import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import report from "../fixtures/research-nvda.json" with { type: "json" };
import { settled } from "./helpers";

// UI plan Step 4: the reading surfaces (Research, Filings, News) and the two things that open
// beside them, the evidence behind a citation and the assistant. Needs the dev stack running
// against the seeded NVDA data (see docs/testing.md); the filing ids below are that data's.
//
// The research report is a fixture: dev databases hold FakeLLM placeholder reports, too sparse to
// exercise the layout. Its source ids are real, so every citation in it resolves against the API.
const company = "/company/NVDA";
const LATEST_PARSED_10K = "15"; // 10-K filed Feb 25, 2026; compared with the one filed Feb 26, 2025

const panel = (page: Page) => page.getByRole("dialog");
const overflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

async function openResearch(page: Page) {
  await page.route("**/companies/NVDA/research/latest", (route) => route.fulfill({ json: report }));
  await page.goto(`${company}/research`);
  await expect(page.getByRole("heading", { name: "AI research" })).toBeVisible();
}

/** Create an account from the assistant's sign-in prompt, landing back on the company page. */
async function signUpFromAssistant(page: Page) {
  await page.goto(company);
  await page.getByRole("button", { name: "Ask" }).click();
  await panel(page).getByRole("link", { name: "Sign in to ask" }).click();
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Email").fill(`e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("textbox", { name: "Ask a question about NVDA" })).toBeVisible();
}

test.describe("desktop", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("a citation opens beside the text, swaps in place, and returns focus (CIT-006)", async ({ page }) => {
    await openResearch(page);
    const summary = page.locator("#summary");
    const business = page.locator("#business");
    const first = summary.getByRole("button", { name: "Open source 1", exact: true });
    const second = business.getByRole("button", { name: "Open source 5", exact: true });

    await first.click();
    await expect(panel(page)).toHaveAccessibleName("Source");
    await expect(panel(page).getByRole("heading", { level: 3 })).toHaveText("Item 1");
    await expect(first).toHaveAttribute("aria-pressed", "true");
    // The passage is the filing's own text and links to the original at the SEC (CIT-002).
    await expect(panel(page).getByText("Researchers and developers use our computing solutions")).toBeVisible();
    await expect(panel(page).getByRole("link", { name: "Open original" })).toHaveAttribute(
      "href",
      /^https:\/\/www\.sec\.gov\//,
    );

    // The page behind is not blocked: it scrolls, and another citation can be opened.
    await page.mouse.move(400, 500);
    await page.mouse.wheel(0, 200);
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0);
    await second.click();
    await expect(panel(page)).toHaveCount(1);
    await expect(second).toHaveAttribute("aria-pressed", "true");
    await expect(first).toHaveAttribute("aria-pressed", "false");
    await expect(panel(page).getByText("Our networking offerings include")).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(panel(page)).toHaveCount(0);
    await expect(second).toBeFocused();

    // Evidence belongs to the page that cited it: it closes when the reader moves to another tab.
    await first.click();
    await expect(panel(page)).toBeVisible();
    await page.getByRole("navigation", { name: "Company sections" }).getByRole("link", { name: "News" }).click();
    await expect(page).toHaveURL(/\/news$/);
    await expect(panel(page)).toHaveCount(0);
  });

  test("a calculated figure shows how it was derived (CIT-006)", async ({ page }) => {
    await openResearch(page);
    await page.locator("#profitability").getByRole("button", { name: "Open source 6", exact: true }).first().click();
    await expect(panel(page).getByRole("region", { name: "How this was calculated" })).toBeVisible();
  });

  test("research is one document: one AI mark, working contents, every claim cited (FR-010, FR-020)", async ({
    page,
  }) => {
    await openResearch(page);
    const article = page.getByRole("article");
    await expect(article.getByText("AI generated")).toHaveCount(1);

    // FR-020: a claim without a source is never shown, and every paragraph shown has a citation.
    await expect(page.getByText("must never be shown")).toHaveCount(0);
    const uncited = await page.evaluate(() =>
      ["summary", "business", "revenue", "profitability", "balance-sheet", "cash-flow", "cases", "risks"]
        .flatMap((id) => [...document.querySelectorAll(`#${id} p.leading-relaxed`)])
        .filter((p) => !p.querySelector('button[aria-label^="Open source"]'))
        .map((p) => p.textContent),
    );
    expect(uncited).toEqual([]);

    // Evidence strength is mentioned only where it is weak (HAL-002), and never as a score.
    await expect(page.locator("#profitability").getByText("Limited evidence")).toHaveCount(1);
    await expect(page.locator("#summary").getByText(/supported/i)).toHaveCount(0);

    // A section the model could not support is listed, not filled in.
    await expect(page.locator("#valuation")).toHaveCount(0);
    await expect(page.locator("#not-covered")).toContainText("Not enough evidence to write about: valuation.");

    const contents = page.getByRole("navigation", { name: "Report contents" });
    await contents.getByRole("link", { name: "Risks" }).click();
    await expect(page.getByRole("heading", { name: "Risks", level: 3 })).toBeInViewport();
    await expect(contents.getByRole("link", { name: "Risks" })).toHaveAttribute("aria-current", "location");

    // References name their sources once they come into view.
    await contents.getByRole("link", { name: "References" }).click();
    await expect(page.getByRole("list", { name: "References" }).getByRole("listitem").first()).not.toHaveText(
      /^\s*1\s*Source\s*$/,
    );
  });

  test("risks carry their change status and filter to new or reworded (FR-027)", async ({ page }) => {
    // The old Risks tab's address lands on the section, not on the top of the report.
    await page.route("**/companies/NVDA/research/latest", (route) => route.fulfill({ json: report }));
    await page.goto(`${company}/risks`);
    await expect(page).toHaveURL(/\/research#risks$/);
    await expect(page.getByRole("heading", { name: "Risks", level: 3 })).toBeInViewport();
    await expect(
      page.getByRole("navigation", { name: "Report contents" }).getByRole("link", { name: "Risks" }),
    ).toHaveAttribute("aria-current", "location");

    const risks = page.locator("#risks");
    await expect(risks.getByRole("listitem")).toHaveCount(3);
    await expect(risks.getByText("New in the latest filing")).toBeVisible();
    await risks.getByRole("radio", { name: "New or reworded (2)" }).click();
    await expect(risks.getByRole("listitem")).toHaveCount(2);
    await expect(risks.getByText("Unchanged from the prior filing")).toHaveCount(0);
  });

  test("a language count opens its statements, and each statement its source (FR-027)", async ({ page }) => {
    await openResearch(page);
    const cell = page.getByRole("button", { name: /Show the statements counted/ }).first();
    await cell.click();
    await expect(panel(page)).toHaveAccessibleName("Counted statements");
    await panel(page).getByRole("button", { name: "Open source 1", exact: true }).click();
    await expect(panel(page)).toHaveAccessibleName("Source");
    await expect(panel(page)).toHaveCount(1);

    // Escape goes back one level before it closes; then focus returns to the cell.
    await page.keyboard.press("Escape");
    await expect(panel(page)).toHaveAccessibleName("Counted statements");
    await page.keyboard.press("Escape");
    await expect(panel(page)).toHaveCount(0);
    await expect(cell).toBeFocused();
  });

  test("no report: says so and offers to make one; an unreadable one is not passed off as none", async ({
    page,
  }) => {
    await page.route("**/companies/NVDA/research/latest", (route) =>
      route.fulfill({ status: 404, json: { title: "no report", status: 404 } }),
    );
    await page.goto(`${company}/research`);
    await expect(page.getByRole("link", { name: /sign in/i }).last()).toBeVisible();
    await expect(page.getByText(/could not be read/i)).toHaveCount(0);
    // Management language is deterministic, so it shows with or without a report.
    await expect(page.getByRole("button", { name: /Show the statements counted/ }).first()).toBeVisible();

    await page.unroute("**/companies/NVDA/research/latest");
    await page.route("**/companies/NVDA/research/latest", (route) =>
      route.fulfill({ status: 500, json: { title: "boom", status: 500 } }),
    );
    await page.goto(`${company}/research`);
    await expect(page.getByText(/could not be read/i)).toBeVisible({ timeout: 20_000 });
  });

  test("filing changes: a plain summary, an inline word diff, both filings one click away (§37.4)", async ({
    page,
  }) => {
    await page.goto(`${company}/filings?filing=${LATEST_PARSED_10K}`);
    await expect(page.getByRole("heading", { name: "10-K filed Feb 25, 2026" })).toBeVisible();
    await expect(page.getByTestId("diff-summary")).toHaveText(
      /^\d+ new risk factors?, \d+ reworded and \d+ unchanged since the 10-K filed Feb 26, 2025\.$/,
    );

    const row = page.getByRole("button", { name: /Failure to meet the evolving needs/ });
    await row.click();
    await expect(row).toHaveAttribute("aria-expanded", "true");
    const item = page.getByRole("listitem").filter({ has: row });
    await expect(item.locator("ins").first()).toBeVisible();
    await expect(item.locator("del").first()).toBeVisible();

    const more = item.getByRole("button", { name: "Show more context" });
    const before = (await item.innerText()).length;
    await more.click();
    await expect(item.getByRole("button", { name: "Show less context" })).toHaveAttribute("aria-expanded", "true");
    expect((await item.innerText()).length).toBeGreaterThan(before);

    // "Prior filing" and "This filing" both open in the panel.
    await item.getByRole("button", { name: "Open source 1", exact: true }).click();
    await expect(panel(page).getByRole("link", { name: "Open original" })).toHaveAttribute("href", /nvda-20250126/);
    await item.getByRole("button", { name: "Open source 10", exact: true }).click();
    await expect(panel(page)).toHaveCount(1);
    await expect(panel(page).getByRole("link", { name: "Open original" })).toHaveAttribute("href", /nvda-20260125/);
    await panel(page).getByRole("button", { name: "Close panel" }).click();

    // Status chips filter the list; the wider comparison counts passages, not risk factors.
    const rows = page.locator("li").filter({ has: page.locator("button[aria-expanded]") });
    const shown = await rows.count();
    await page.getByRole("button", { name: /^Unchanged/ }).click();
    expect(await rows.count()).toBeGreaterThan(shown);
    await page.getByRole("switch", { name: "Risk factors only" }).click();
    await expect(page.getByTestId("diff-summary")).toContainText("passage");

    await page.getByRole("tab", { name: "Outline" }).click();
    await expect(page).toHaveURL(/view=outline/);
    await expect(page.getByRole("list", { name: "Filing sections" }).getByRole("listitem").first()).toBeVisible();
  });

  test("filings: nothing to compare is said plainly, and an 8-K has only an outline (§37.4)", async ({ page }) => {
    // Risk factors unreadable (422): said as it is, with the wider comparison offered.
    await page.route(/\/filings\/15\/diff\?.*kind=risk_factor/, (route) =>
      route.fulfill({ status: 422, json: { title: "one of the filings has no parsed sections", status: 422 } }),
    );
    await page.goto(`${company}/filings?filing=${LATEST_PARSED_10K}`);
    await expect(page.getByText("The risk factors could not be read")).toBeVisible();
    await page.getByRole("button", { name: "Compare all sections" }).click();
    await expect(page.getByTestId("diff-summary")).toContainText("passage");

    // The oldest 10-K has no earlier one (404).
    await page.getByRole("radio", { name: "10-K" }).click();
    await page.getByRole("navigation", { name: "Filings" }).getByRole("link").last().click();
    await expect(page.getByText(/There is no earlier 10-K on file/)).toBeVisible();

    await page.getByRole("radio", { name: "8-K" }).click();
    await page.getByRole("navigation", { name: "Filings" }).getByRole("link").first().click();
    await expect(page.getByRole("heading", { name: /^8-K filed/ })).toBeVisible();
    await expect(page.getByRole("tab")).toHaveCount(0);
  });

  test("links from API data are only ever plain web addresses (SEC-, LGL-004)", async ({ page }) => {
    await page.route("**/companies/NVDA/filings?*", (route) =>
      route.fulfill({
        json: [
          {
            filing_id: "15",
            filing_type: "10-K",
            filing_date: "2026-02-25",
            period_end: "2026-01-25",
            accession_number: "0001045810-26-000021",
            primary_document_url: "javascript:alert(document.domain)",
          },
        ],
      }),
    );
    await page.goto(`${company}/filings`);
    await expect(page.getByRole("heading", { name: "10-K filed Feb 25, 2026" })).toBeVisible();
    await expect(page.getByText("Original document not available")).toBeVisible();
    await expect(page.locator('a[href^="javascript"]')).toHaveCount(0);

    const item = (id: string, extra: object) => ({
      news_id: id,
      title: `Headline ${id}`,
      description: "A short summary.",
      url: `https://news.example/${id}`,
      publisher: "Example Wire",
      published_at: "2026-09-22T15:00:00+00:00",
      category: "Earnings",
      relevance_score: 0.9,
      tier: 2,
      cluster_id: null,
      ...extra,
    });
    await page.route("**/companies/NVDA/news?*", (route) =>
      route.fulfill({
        json: {
          ticker: "NVDA",
          next_cursor: null,
          freshness: { as_of: "2026-10-01T22:00:00+00:00", source: "news", freshness_status: "fresh" },
          items: [
            item("1", { url: "javascript:alert(1)", title: "Unsafe link headline" }),
            item("2", { cluster_id: "evt_a", title: "Lead story" }),
            item("3", { cluster_id: "evt_a", tier: 5, publisher: "Other Blog", title: "Same event, blog" }),
            item("4", { cluster_id: "evt_a", tier: 4, publisher: "Finance Daily", title: "Same event, daily" }),
            item("5", { published_at: "2026-09-20T15:00:00+00:00", category: "Product", title: "Older story" }),
          ],
        },
      }),
    );
    await page.goto(`${company}/news`);
    await expect(page.getByText("Unsafe link headline")).toBeVisible();
    await expect(page.locator('a[href^="javascript"]')).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Unsafe link headline/ })).toHaveCount(0);
    // Every headline that is a link leaves the app in a new tab that cannot reach back.
    for (const link of await page.getByRole("link", { name: /opens in a new tab/ }).all()) {
      await expect(link).toHaveAttribute("target", "_blank");
      await expect(link).toHaveAttribute("rel", /noopener/);
    }

    // Two days, newest first; the three reports of one event fold into its best-sourced one.
    await expect(page.getByRole("heading", { level: 3 })).toHaveText(["Sep 22, 2026", "Sep 20, 2026"]);
    await expect(page.getByText("Same event, blog")).toHaveCount(0);
    const more = page.getByRole("button", { name: "+2 more sources" });
    await more.click();
    await expect(more).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByText("Same event, blog")).toBeVisible();
    // The source tier is named only for the weaker tiers.
    await expect(page.getByText(/Tier 5/)).toHaveCount(1);
    await expect(page.getByText(/Tier 2/)).toHaveCount(0);

    await page.getByRole("button", { name: "Filter" }).click();
    await page.getByLabel("Category").selectOption("Product");
    await expect(page.getByRole("button", { name: "Filter, 1 active" })).toBeVisible();
    await expect(page.getByText("Older story")).toBeVisible();
    await expect(page.getByText("Lead story")).toHaveCount(0);
    await page.getByRole("button", { name: "Clear filters" }).click();
    await expect(page.getByText("Lead story")).toBeVisible();
  });

  test("the assistant: opens anywhere, survives tab changes, cites, declines honestly (FR-030)", async ({
    page,
  }) => {
    await page.route("**/companies/NVDA/research/latest", (route) => route.fulfill({ json: report }));
    // Signed out: the questions are a preview, and signing in comes back to the open panel.
    await page.goto(`${company}/financials`);
    const ask = page.getByRole("button", { name: "Ask" });
    await expect(ask).toHaveAttribute("aria-expanded", "false");
    await ask.click();
    await expect(ask).toHaveAttribute("aria-expanded", "true");
    await expect(panel(page)).toHaveAccessibleName("Ask about NVDA");
    await expect(panel(page).getByRole("list", { name: "Suggested questions" }).getByRole("listitem")).toHaveCount(4);
    await expect(panel(page).getByRole("textbox")).toHaveCount(0);

    await signUpFromAssistant(page);
    await expect(page).toHaveURL(new RegExp(`${company}$`));
    const composer = page.getByRole("textbox", { name: "Ask a question about NVDA" });

    // At this width the panel docks: it sits beside the page rather than over it.
    const dock = await panel(page).boundingBox();
    const main = await page.getByRole("heading", { level: 1 }).boundingBox();
    expect(dock!.width).toBe(440);
    expect(main!.x + main!.width).toBeLessThanOrEqual(dock!.x);

    // Shift+Enter is a new line; Enter sends.
    await composer.fill("What was NVDA’s revenue");
    await composer.press("Shift+Enter");
    await expect(composer).toHaveValue("What was NVDA’s revenue\n");
    await composer.fill("What was NVDA’s revenue in the latest fiscal year?");
    await composer.press("Enter");
    await expect(composer).toHaveValue("");
    const citation = panel(page).getByRole("button", { name: /^Open source \d+$/ }).first();
    await expect(citation).toBeVisible({ timeout: 30_000 });
    await expect(panel(page).getByText("How this was answered")).toBeVisible();

    // It stays, with the conversation, while the reader moves between tabs.
    await page.getByRole("navigation", { name: "Company sections" }).getByRole("link", { name: "News" }).click();
    await expect(page).toHaveURL(/\/news$/);
    await expect(panel(page).getByText("What was NVDA’s revenue in the latest fiscal year?")).toBeVisible();

    // A citation in an answer opens inside the same panel, with a way back. Never two panels.
    await citation.click();
    await expect(panel(page)).toHaveCount(1);
    await expect(panel(page)).toHaveAccessibleName("Source");
    await panel(page).getByRole("button", { name: "Back to conversation" }).click();
    await expect(panel(page)).toHaveAccessibleName("Ask about NVDA");
    await expect(citation).toBeVisible();

    await panel(page).getByRole("button", { name: "Helpful", exact: true }).click();
    await expect(panel(page).getByText(/thank/i)).toBeVisible();

    // An out-of-scope request is declined as a deliberate state, not an error (LGL-006).
    await composer.fill("Should I buy NVDA stock right now?");
    await composer.press("Enter");
    await expect(
      panel(page).getByText(/Outside what Assay Desk covers|Not enough evidence to answer/).last(),
    ).toBeVisible({ timeout: 30_000 });
    await expect(panel(page).getByRole("alert")).toHaveCount(0);

    // A page citation while the assistant is open also goes inside it.
    await page.getByRole("navigation", { name: "Company sections" }).getByRole("link", { name: "Research" }).click();
    await page.locator("#summary").getByRole("button", { name: "Open source 1", exact: true }).click();
    await expect(panel(page)).toHaveCount(1);
    await expect(panel(page).getByRole("button", { name: "Back to conversation" })).toBeVisible();

    // Closing returns to the page; the Ask button reflects it.
    await panel(page).getByRole("button", { name: "Close panel" }).click();
    await expect(panel(page)).toHaveCount(0);
    await expect(ask).toHaveAttribute("aria-expanded", "false");
  });

  test("the assistant by keyboard, and its address (UI-003)", async ({ page }) => {
    // The tab behind the panel is held back, as on a slow connection: the panel must open
    // without it, and closing it while the tab is still loading must not bring it back.
    await page.route("**/OverviewTab*", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.continue();
    });
    await page.goto(`${company}/chat`);
    await expect(page).toHaveURL(new RegExp(`${company}$`));
    await expect(panel(page)).toHaveAccessibleName("Ask about NVDA");
    await panel(page).getByRole("button", { name: "Close panel" }).click();
    await expect(page.getByRole("slider")).toBeVisible(); // the Overview tab has arrived
    await expect(panel(page)).toHaveCount(0);

    const ask = page.getByRole("button", { name: "Ask" });
    await ask.focus();
    await page.keyboard.press("Enter");
    await expect(panel(page)).toBeVisible();
    // Focus moves into the panel; Escape there closes it and hands focus back to Ask.
    await expect.poll(() => page.evaluate(() => !!document.activeElement?.closest('[role="dialog"]'))).toBe(true);
    await page.keyboard.press("Escape");
    await expect(panel(page)).toHaveCount(0);
    await expect(ask).toBeFocused();
  });

  for (const theme of ["dark", "light"] as const) {
    test(`no serious accessibility violations, ${theme} (UI-003)`, async ({ page }) => {
      await page.addInitScript((t) => {
        if (t === "light") localStorage.setItem("il-theme", "light");
      }, theme);
      const scan = async (label: string) => {
        await page.waitForLoadState("networkidle");
        await settled(page);
        const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
        const serious = results.violations.filter((v) => ["serious", "critical"].includes(v.impact ?? ""));
        expect(serious, `${label}: ${JSON.stringify(serious, null, 2)}`).toEqual([]);
      };

      await openResearch(page);
      await scan("research");
      await page.locator("#summary").getByRole("button", { name: "Open source 1", exact: true }).click();
      await expect(panel(page).getByRole("link", { name: "Open original" })).toBeVisible();
      await scan("research with a source open");

      await page.goto(`${company}/filings?filing=${LATEST_PARSED_10K}`);
      await page.getByRole("button", { name: /Failure to meet the evolving needs/ }).click();
      await scan("filings, changes");

      await page.goto(`${company}/news`);
      await expect(page.getByRole("heading", { name: "News" })).toBeVisible();
      await scan("news");

      await page.getByRole("button", { name: "Ask" }).click();
      await expect(panel(page)).toBeVisible();
      await scan("assistant open");
    });
  }
});

test.describe("phone", () => {
  test.use({ viewport: { width: 360, height: 780 } });

  test("filings: the list is the page, a filing opens as its own view (UI-006)", async ({ page }) => {
    await page.goto(`${company}/filings`);
    const list = page.getByRole("navigation", { name: "Filings" });
    await expect(list).toBeVisible();
    await expect(page.getByRole("article")).toHaveCount(0);
    expect(await overflow(page)).toBeLessThanOrEqual(0);

    await list.getByRole("radio", { name: "10-K" }).click();
    await list.getByRole("link", { name: /Filed Feb 25, 2026/ }).click();
    await expect(page).toHaveURL(/filing=15/);
    await expect(list).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "10-K filed Feb 25, 2026" })).toBeFocused();
    await expect(page.getByTestId("diff-summary")).toBeVisible();
    await page.getByRole("button", { name: /Failure to meet the evolving needs/ }).click();
    expect(await overflow(page)).toBeLessThanOrEqual(0);

    // A citation on a phone is a full-screen sheet; closing it returns to the filing.
    await page.getByRole("button", { name: "Open source 1", exact: true }).click();
    await expect(panel(page)).toBeVisible();
    await settled(page);
    const sheet = await panel(page).boundingBox();
    expect(sheet!.width).toBe(360);
    await panel(page).getByRole("button", { name: "Close panel" }).click();

    await page.getByRole("link", { name: "All filings" }).click();
    await expect(page.getByRole("navigation", { name: "Filings" })).toBeVisible();
  });

  test("research, news and the assistant fit a 360 px screen (UI-006)", async ({ page }) => {
    await openResearch(page);
    expect(await overflow(page), "research").toBeLessThanOrEqual(0);
    // The contents become a jump menu.
    await page.getByRole("combobox", { name: "Jump to a section" }).selectOption("risks");
    await expect(page.getByRole("heading", { name: "Risks", level: 3 })).toBeInViewport();

    await page.goto(`${company}/news`);
    await expect(page.getByRole("heading", { name: "News" })).toBeVisible();
    expect(await overflow(page), "news").toBeLessThanOrEqual(0);

    await page.getByRole("button", { name: "Ask" }).click();
    await settled(page);
    const sheet = await panel(page).boundingBox();
    expect(sheet).toMatchObject({ x: 0, y: 0, width: 360, height: 780 });
    await panel(page).getByRole("button", { name: "Close panel" }).click();
    await expect(panel(page)).toHaveCount(0);
  });
});
