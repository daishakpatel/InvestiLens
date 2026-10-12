import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import report from "../fixtures/research-nvda.json" with { type: "json" };
import { settled, signUp } from "./helpers";

// UI plan Step 5: the tools (Compare, Portfolio), the personal features (watchlist, alerts,
// notifications), and the cross-cutting promises (keyboard-only use, reduced motion, axe).
// Needs the dev stack with the seeded companies NVDA, AMD, INTC, AAPL and JPM.

const figure = (page: Page, metric: string, column: number) =>
  page.getByRole("row", { name: new RegExp(`^${metric}`) }).getByRole("cell").nth(column);

/** Press Tab (or Shift+Tab) until `target` has focus: proof it is reachable by keyboard alone. */
async function tabUntil(page: Page, target: Locator, key: "Tab" | "Shift+Tab" = "Tab", limit = 80) {
  for (let i = 0; i < limit; i++) {
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) return;
    await page.keyboard.press(key);
  }
  await expect(target).toBeFocused();
}

test.describe("compare (§37.1)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("one table, the strongest figure emphasised, and a chart for the chosen metric", async ({ page }) => {
    await page.goto("/compare");
    await expect(page.getByRole("list", { name: "Companies compared" }).getByRole("link")).toHaveText([
      "NVDA",
      "AMD",
      "INTC",
    ]);
    // Strongest is the highest margin but the lowest debt; never green or red.
    await expect(figure(page, "Gross margin", 1).locator("span.font-semibold")).toHaveText(/%$/);
    await expect(figure(page, "Gross margin", 2).locator("span.font-semibold")).toHaveCount(0);
    await expect(figure(page, "Total debt", 2).locator("span.font-semibold")).toHaveText(/^\$/); // AMD
    for (const tone of [".text-positive", ".text-negative"]) {
      await expect(page.getByRole("table").first().locator(tone)).toHaveCount(0);
    }
    // A metric nobody has is named in the note, not shown as a row of blanks or zeros.
    await expect(page.getByRole("row", { name: /^P\/E/ })).toHaveCount(0);
    await expect(page.getByText(/Not available for any of them: P\/E/)).toBeVisible();

    // Choosing a row charts it; the chart keeps its table view and CSV (FR-013).
    await page.getByRole("button", { name: "Net margin", exact: true }).click();
    await expect(page).toHaveURL(/metric=net_margin/);
    await expect(page.getByRole("img", { name: /^Net margin by company/ })).toBeVisible();
    await page.getByRole("button", { name: "View Net margin as a table" }).click();
    await expect(page.getByRole("table").last()).toContainText("FY2026");
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download Net margin as CSV" }).click();
    expect((await download).suggestedFilename()).toBe("compare_net_margin.csv");
  });

  test("the selection lives in the URL, and what the URL says is checked", async ({ page }) => {
    await page.goto("/compare?tickers=nvda,%3Cscript%3E,JPM,nvda&metric=roe");
    const chips = page.getByRole("list", { name: "Companies compared" }).getByRole("link");
    await expect(chips).toHaveText(["NVDA", "JPM"]);
    await expect(page.getByRole("img", { name: /^Return on equity by company/ })).toBeVisible();
    // A figure a bank does not report is N/A with its reason, never zero.
    const gap = figure(page, "Gross margin", 2);
    await expect(gap).toHaveText("N/A");
    await gap.getByText("N/A").hover();
    await expect(page.getByRole("tooltip")).toContainText(/not|No /i);

    // Add through the search palette, in pick mode: it adds to the page instead of navigating.
    await page.getByRole("button", { name: "Add company" }).click();
    const palette = page.getByRole("dialog", { name: "Add a company to compare" });
    await palette.getByRole("combobox").fill("amd");
    await palette.getByRole("option", { name: /AMD/ }).first().click();
    await expect(page).toHaveURL(/tickers=NVDA%2CJPM%2CAMD/);
    await expect(chips).toHaveText(["NVDA", "JPM", "AMD"]);

    // One-tap peers, then remove; fewer than two companies is an instruction, not an error.
    await page.getByRole("button", { name: /^Add INTC,/ }).click();
    await expect(chips).toHaveCount(4);
    for (const ticker of ["INTC", "AMD", "JPM"]) await page.getByRole("button", { name: `Remove ${ticker}` }).click();
    await expect(page.getByText("Add at least two companies to compare them.")).toBeVisible();
  });

  test("the AI explanation is asked for, marked as AI, and gated on sign-in (FR-010, ADR-0006)", async ({
    page,
  }) => {
    await page.goto("/compare");
    const section = page.getByRole("region", { name: "The differences, explained" });
    await expect(section.getByText("AI generated")).toHaveCount(1);
    await expect(section.getByRole("button", { name: "Explain the differences" })).toHaveCount(0);
    await section.getByRole("link", { name: "Sign in" }).click();
    await expect(page).toHaveURL(/\/login$/);

    await signUp(page);
    await page.goto("/compare");
    await section.getByRole("button", { name: "Explain the differences" }).click();
    // Mock mode has no model behind it (it returns a placeholder with no citations), so the
    // honest outcome is the plain "not enough" note; with a model, cited text. Either way it is
    // never an error, and never uncited prose.
    await expect(section.getByText(/MOCK_COMPLETION/)).toHaveCount(0);
    const note = section.getByText("Not enough cited evidence to explain the differences.");
    const cited = section.getByRole("button", { name: /^Open source \d+$/ }).first();
    await expect(note.or(cited)).toBeVisible({ timeout: 60_000 });
    await expect(section.getByRole("alert")).toHaveCount(0);
  });
});

test.describe("portfolio (§37.2)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("weights recompute the results with no request; a new company asks the server once", async ({
    page,
  }) => {
    await page.goto("/portfolio");
    await expect(page.getByText("Hypothetical portfolio. Not investment advice.")).toBeVisible(); // LGL-006
    const effective = page.getByText("Effective holdings").locator("xpath=..");
    await expect(effective).toContainText("2.9");
    await expect(page.getByText(/Gross margin is not reported by JPM/)).toBeVisible();
    await expect(page.getByRole("img", { name: /^Sector exposure: Financials 30%, Technology 70%$/ })).toBeVisible();

    const requests: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/")) requests.push(`${request.method()} ${new URL(request.url()).pathname}`);
    });

    const nvda = page.getByRole("spinbutton", { name: "NVDA weight, percent" });
    await nvda.fill("80");
    await expect(effective).not.toContainText("2.9");
    await expect(page.getByRole("img", { name: /^Sector exposure: Financials 21%, Technology 79%$/ })).toBeVisible();
    // 80 + 30 + 30: said, and the results still use the weights in proportion.
    await expect(page.getByText("Weights do not add up to 100%.")).toBeVisible();
    await page.getByRole("button", { name: "Normalize to 100%" }).click();
    await expect(page.getByRole("row", { name: /^Total/ })).toContainText("100%");
    await expect(nvda).toHaveValue("57.2");
    // A field can be cleared while typing; an empty weight counts as zero, not as an error.
    await nvda.fill("");
    await expect(page.getByRole("img", { name: /Financials 50%, Technology 50%/ })).toBeVisible();
    expect(requests, "changing weights must not touch the network").toEqual([]);

    await page.getByRole("button", { name: "Add holding" }).click();
    const palette = page.getByRole("dialog", { name: "Add a holding" });
    await expect(palette.getByRole("option", { name: /NVDA/ })).toHaveCount(0); // already held
    await palette.getByRole("combobox").fill("amd");
    await palette.getByRole("option", { name: /AMD/ }).first().click();
    await expect(page.getByRole("spinbutton", { name: "AMD weight, percent" })).toHaveValue("10");
    // AMD has no price history in the dev data: said in a sentence, not hidden.
    await expect(page.getByText(/There is no price history for AMD/)).toBeVisible();
    expect(requests.filter((r) => r === "POST /api/v1/portfolio/analyze")).toHaveLength(1);

    for (const ticker of ["NVDA", "AAPL", "JPM", "AMD"]) await page.getByRole("button", { name: `Remove ${ticker}` }).click();
    await expect(page.getByText("Add a holding to see what the portfolio adds up to.")).toBeVisible();
  });

  test("risk themes are AI-derived, marked so, and cited (FR-010, FR-020)", async ({ page }) => {
    await page.goto("/portfolio");
    const themes = page.getByRole("region", { name: "Risk themes" });
    await expect(themes.getByText("AI generated")).toHaveCount(1);
    const chip = themes.getByRole("button", { name: /^Open source \d+$/ }).first();
    const none = themes.getByText(/No risk themes yet/);
    await expect(chip.or(none)).toBeVisible();
    if (await chip.isVisible()) {
      await chip.click();
      await expect(page.getByRole("dialog", { name: "Source" })).toBeVisible();
    }
  });
});

test.describe("watchlist, alerts and notifications (§26.2, FR-007)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("signed out, Watch and the alerts bell explain and offer sign-in", async ({ page }) => {
    await page.goto("/company/NVDA");
    await page.getByRole("button", { name: "Watch", exact: true }).click();
    await expect(page.getByText(/Sign in to keep a watchlist/)).toBeVisible();
    await page.keyboard.press("Escape");
    await page.getByRole("button", { name: "Alerts for NVDA" }).click();
    await page.getByRole("link", { name: "Sign in" }).last().click();
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("button", { name: "Notifications" })).toHaveCount(0);
  });

  test("watch a company, see it on Home, turn on an alert, and receive a notification", async ({ page }) => {
    await page.clock.install();
    await signUp(page);

    // Home starts with an invitation, not an empty box.
    await page.goto("/");
    const watchlist = page.getByRole("region", { name: "Watchlist" });
    await expect(watchlist.getByText(/Nothing watched yet/)).toBeVisible();

    await page.goto("/company/NVDA");
    await page.getByRole("button", { name: "Watch", exact: true }).click();
    const watching = page.getByRole("button", { name: "Watching" });
    await expect(watching).toHaveAttribute("aria-pressed", "true"); // the state is the confirmation
    await expect(page.getByRole("status").filter({ hasText: /watch/i })).toHaveCount(0); // no toast

    await page.getByRole("button", { name: "Alerts for NVDA" }).click();
    const risk = page.getByRole("switch", { name: /New risk factor/ });
    await risk.click();
    await expect(risk).toBeChecked();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Alerts for NVDA, some on" })).toBeVisible();

    // Both survive a reload: they are the server's state, not the page's.
    await page.reload();
    await expect(watching).toBeVisible();
    await page.getByRole("button", { name: "Alerts for NVDA, some on" }).click();
    await expect(risk).toBeChecked();
    await page.keyboard.press("Escape");

    // On Home: ticker, name, last close, day change, and a month's sparkline.
    await page.goto("/");
    const row = watchlist.getByRole("link", { name: /NVDA/ });
    await expect(row).toContainText("NVIDIA");
    await expect(row).toContainText(/\$\d/);
    await expect(row).toContainText(/[+−]\d/);
    await expect(row.locator("svg polyline")).toHaveCount(1);

    // The bell: nothing yet (the real endpoint), then an alert arrives on the next poll.
    const bell = page.getByRole("button", { name: /^Notifications/ });
    await expect(bell).toHaveAccessibleName("Notifications");
    let read = false;
    const marked: string[] = [];
    await page.route("**/api/v1/notifications?*", (route) =>
      route.fulfill({
        json: [
          {
            id: "501",
            title: "NVDA: new risk factor in the latest 10-K",
            body: "Commercial arrangements expose us to counterparty risks.",
            channel: "in_app",
            company_id: "1",
            read,
            created_at: "2026-10-11T15:00:00+00:00",
          },
        ],
      }),
    );
    await page.route("**/api/v1/notifications/*/read", (route) => {
      marked.push(new URL(route.request().url()).pathname);
      read = true;
      return route.fulfill({ status: 204 });
    });
    await page.clock.fastForward(61_000); // the 60-second poll
    await expect(bell).toHaveAccessibleName("Notifications, 1 unread");
    await bell.click();
    await expect(page.getByText("NVDA: new risk factor in the latest 10-K")).toBeVisible();
    await expect(page.getByText("New:", { exact: false })).toHaveCount(1);
    await expect.poll(() => marked).toEqual(["/api/v1/notifications/501/read"]); // opened = read
    await page.keyboard.press("Escape");
    await expect(bell).toHaveAccessibleName("Notifications");

    // Unwatch: the row goes, and Home returns to the invitation.
    await page.goto("/company/NVDA");
    await watching.click();
    await expect(page.getByRole("button", { name: "Watch", exact: true })).toHaveAttribute("aria-pressed", "false");
    await page.goto("/");
    await expect(watchlist.getByText(/Nothing watched yet/)).toBeVisible();
  });
});

test.describe("across the app (UI-003)", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  test("the happy path by keyboard alone: search, company, research, a citation, the assistant", async ({
    page,
  }) => {
    await signUp(page); // typed into a form; everything after this uses keys only
    await page.goto("/");
    await expect(page.getByRole("note").first()).toBeVisible();
    await page.keyboard.press("/");
    await page.keyboard.type("nvidia");
    await expect(page.getByRole("option", { name: /NVDA/ }).first()).toBeVisible();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/company\/NVDA$/);

    const tabs = page.getByRole("navigation", { name: "Company sections" });
    await tabUntil(page, tabs.getByRole("link", { name: "Filings" }));
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/filings$/);
    const filing = page.getByRole("navigation", { name: "Filings" }).getByRole("link", { name: /^10-K Filed Feb 25, 2026/ });
    await tabUntil(page, filing);
    await page.keyboard.press("Enter");
    const change = page.getByRole("button", { name: /Failure to meet the evolving needs/ });
    await tabUntil(page, change);
    await page.keyboard.press("Enter");
    await expect(change).toHaveAttribute("aria-expanded", "true");

    // A citation opens beside the text; Escape closes that layer only and returns focus.
    const chip = page.getByRole("button", { name: "Open source 1", exact: true });
    await tabUntil(page, chip);
    await page.keyboard.press("Enter");
    const panel = page.getByRole("dialog");
    await expect(panel).toHaveAccessibleName("Source");
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    await expect(chip).toBeFocused();
    await expect(change).toHaveAttribute("aria-expanded", "true"); // the page beneath is untouched

    // The assistant: open, ask, get a cited answer, close.
    const ask = page.getByRole("button", { name: "Ask" });
    await tabUntil(page, ask, "Shift+Tab");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("textbox", { name: "Ask a question about NVDA" })).toBeFocused();
    await page.keyboard.type("What was NVDA's revenue in the latest fiscal year?");
    await page.keyboard.press("Enter");
    await expect(panel.getByRole("button", { name: /^Open source \d+$/ }).first()).toBeVisible({ timeout: 30_000 });
    await page.keyboard.press("Escape");
    await expect(panel).toHaveCount(0);
    await expect(ask).toBeFocused();
  });

  test("motion is switched off for readers who ask for less of it", async ({ browser }) => {
    const context = await browser.newContext({ reducedMotion: "reduce" });
    const page = await context.newPage();
    await page.goto("/compare");
    const chip = page.getByRole("list", { name: "Companies compared" }).getByRole("listitem").first();
    await expect(chip).toBeVisible();
    const seconds = await chip.evaluate((el) => parseFloat(getComputedStyle(el).animationDuration));
    expect(seconds).toBeLessThan(0.001);
    await context.close();
  });

  for (const theme of ["dark", "light"] as const) {
    test(`no serious accessibility violations on Home, the company page and the tools, ${theme}`, async ({
      page,
    }) => {
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

      await signUp(page);
      await page.goto("/company/NVDA");
      await page.getByRole("button", { name: "Watch", exact: true }).click();
      await expect(page.getByRole("button", { name: "Watching" })).toBeVisible();
      await scan("overview");
      await page.getByRole("button", { name: "Alerts for NVDA" }).click();
      await expect(page.getByRole("switch").first()).toBeVisible();
      await scan("alerts popover");
      await page.keyboard.press("Escape");

      await page.goto("/company/NVDA/financials");
      await scan("financials");

      await page.goto("/");
      await expect(page.getByRole("region", { name: "Watchlist" }).getByRole("link")).toHaveCount(1);
      await scan("home with a watchlist");
      await page.getByRole("button", { name: "Notifications" }).click();
      await scan("notifications");
      await page.keyboard.press("Escape");

      await page.goto("/compare");
      await expect(page.getByRole("img", { name: /by company/ })).toBeVisible();
      await scan("compare");
      await page.getByRole("button", { name: "Add company" }).click();
      await scan("compare, picking a company");
      await page.keyboard.press("Escape");

      await page.goto("/portfolio");
      await expect(page.getByRole("img", { name: /^Sector exposure/ })).toBeVisible();
      await scan("portfolio");
    });
  }
});

test.describe("phone (UI-003, UI-006)", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("every control answers to a touch target at least 40 px across", async ({ page }) => {
    const paths = ["/", "/login", "/company/NVDA", "/company/NVDA/financials", "/company/NVDA/filings?filing=15"];
    paths.push("/company/NVDA/research", "/company/NVDA/news", "/compare", "/portfolio");
    await page.route("**/companies/NVDA/research/latest", (route) => route.fulfill({ json: report }));
    for (const path of paths) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      // Hit-tested, not measured: a control may look smaller than the area that answers for it.
      const small = await page.evaluate(() => {
        const failures: string[] = [];
        const selector = 'button, a[href], input, select, textarea, summary, [role="tab"], [role="radio"], [role="switch"]';
        for (const el of document.querySelectorAll<HTMLElement>(selector)) {
          const style = getComputedStyle(el);
          const box = el.getBoundingClientRect();
          if (box.width <= 1 || style.visibility === "hidden" || el.closest('[aria-hidden="true"]')) continue;
          // Exempt, as in WCAG 2.5.8: a link or control set inline in a run of text or figures.
          if (style.display === "inline" || el.hasAttribute("data-inline")) continue;
          if ((el as HTMLButtonElement).disabled) continue;
          el.scrollIntoView({ block: "center", inline: "center" });
          const r = el.getBoundingClientRect();
          const cx = r.left + r.width / 2;
          const cy = r.top + r.height / 2;
          const reach = (dx: number, dy: number) => {
            const hit = document.elementFromPoint(cx + dx, cy + dy);
            return hit !== null && (hit === el || el.contains(hit) || hit.closest("label")?.contains(el) === true);
          };
          const tall = r.height >= 40 || (reach(0, -19) && reach(0, 19));
          const wide = r.width >= 40 || (reach(-19, 0) && reach(19, 0));
          if (!tall || !wide) {
            const name = (el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 30);
            failures.push(`${el.tagName.toLowerCase()} "${name}" ${Math.round(r.width)}×${Math.round(r.height)}`);
          }
        }
        return [...new Set(failures)];
      });
      expect(small, `${path}: controls with a touch target under 40 px`).toEqual([]);
    }
  });

  test("the tools fit a 360 px screen", async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width: 360, height: 780 } });
    const page = await context.newPage();
    for (const path of ["/compare", "/portfolio", "/"]) {
      await page.goto(path);
      await page.waitForLoadState("networkidle");
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${path} overflows`).toBeLessThanOrEqual(0);
    }
    await context.close();
  });
});
