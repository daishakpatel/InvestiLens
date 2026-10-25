import { expect, test } from "@playwright/test";

import { TICKER } from "./helpers";

// Phase 7h (Instructions/33_phase7h_peer_sets_and_valuation_bands.md): the Financials valuation
// section draws each multiple on its 5-year range with today's marker and the peer-median tick,
// labelled in text with sample sizes; a multiple that is not meaningful says why instead; peers
// left out are listed with the reason. The Compare view shows the peer set with "why these
// peers?". The first test reads the dev stack after `scripts/build_metrics.py`; the rest mock.
// Spec refs: FR-PS-010, FR-PS-013, FR-PS-014, FR-PS-014.

const bandsUrl = `**/api/v1/companies/${TICKER}/valuation-bands*`;
const peerSet = {
  id: 7,
  name: "Default peers",
  kind: "system_default",
  members: [
    { ticker: "AMD", name: "Advanced Micro Devices", rationale: "same SIC 3674; market cap 0.6× target" },
    { ticker: "AVGO", name: "Broadcom", rationale: "same SIC 3674; market cap 0.4× target" },
    { ticker: "QCOM", name: "Qualcomm", rationale: "same SIC 3674; market cap 0.3× target" },
  ],
  insufficient: false,
  reason: null,
};
const own = { n: 6, min: "20", median: "40", max: "60", percentile: "0.33", label: "in the middle half of its 5-year range", reason: null };

const bands = {
  company_ticker: TICKER,
  as_of: "2026-10-23",
  peer_set: peerSet,
  disclaimer: "Positions within ranges, not judgements of value. Not investment advice.",
  bands: [
    {
      multiple: "pe_ratio",
      unit: "x",
      status: "ok",
      value: "30",
      reason: null,
      own,
      peers: {
        n: 2,
        median: "25",
        percentile: "0.5",
        premium_to_peer_median: "0.2",
        label: "20% above peer median",
        reason: null,
        excluded: [{ ticker: "QCOM", reason: "Not available: a price, share count or four quarters of figures is missing." }],
      },
      history: [],
    },
    {
      multiple: "ev_ebitda",
      unit: "x",
      status: "not_meaningful",
      value: null,
      reason: "Not meaningful: earnings, EBITDA, cash flow or book value is zero or negative.",
      own: { n: 3, reason: "No value today, so no position in the range." },
      peers: { n: 0, reason: "No value today to compare with the peers.", excluded: [] },
      history: [],
    },
    {
      multiple: "fcf_yield",
      unit: "ratio",
      status: "ok",
      value: "0.045",
      reason: null,
      own: { n: 6, min: "0.01", median: "0.03", max: "0.05", percentile: "0.83", label: "in the top quartile of its 5-year range", reason: null },
      peers: { n: 3, median: "0.03", premium_to_peer_median: "0.5", label: "50% above peer median", excluded: [] },
      history: [],
    },
  ],
};

test("dev data: bands with today's marker and sample sizes", async ({ page }) => {
  await page.goto(`/company/${TICKER}/financials#valuation`);
  const section = page.getByTestId("valuation-bands");
  await expect(section.getByText("Valuation bands")).toBeVisible();
  const pe = page.getByTestId("band-pe_ratio");
  await expect(pe.getByText(/^Today \d/)).toBeVisible();
  await expect(pe.getByText(/\(n=\d\)/)).toBeVisible();
  await expect(section.getByText(/Not investment advice/)).toBeVisible();
});

for (const theme of ["dark", "light"] as const) {
  test(`all states render with text labels (${theme})`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem("il-theme", t), theme);
    await page.route(bandsUrl, (route) => route.fulfill({ json: bands }));
    await page.goto(`/company/${TICKER}/financials#valuation`);
    const pe = page.getByTestId("band-pe_ratio");
    await expect(pe.getByText("Today 30.0×")).toBeVisible();
    await expect(pe.getByText("Peer median 25.0×")).toBeVisible();
    await expect(pe.getByText(/20% above peer median \(n=2\)/)).toBeVisible();
    await expect(pe.getByRole("list", { name: "Peers left out" })).toContainText("QCOM");
    const ebitda = page.getByTestId("band-ev_ebitda");
    await expect(ebitda.getByRole("status")).toHaveText(/^Not meaningful/);
    await expect(ebitda.getByRole("img")).toHaveCount(0);  // no bar drawn
    await expect(page.getByTestId("band-fcf_yield").getByText("Today 4.5%")).toBeVisible();
    await expect(page.getByTestId("valuation-bands")).not.toContainText(/cheap|expensive|undervalued|overvalued/i);
  });
}

test("compare: why these peers, and editing needs sign-in", async ({ page }) => {
  await page.route(`**/api/v1/companies/${TICKER}/peer-sets`, (route) =>
    route.fulfill({ json: { company_ticker: TICKER, peer_sets: [peerSet] } }),
  );
  await page.route(bandsUrl, (route) => route.fulfill({ json: bands }));
  await page.goto(`/compare?tickers=${TICKER},AMD`);
  const panel = page.getByTestId("peer-sets");
  await panel.getByText("Why these peers?").click();
  await expect(panel.getByText(/same SIC 3674; market cap 0\.6/)).toBeVisible();
  await expect(panel.getByText(/left out of the P\/E band/)).toBeVisible();
  await panel.getByRole("button", { name: "Edit" }).click();
  await expect(panel.getByText("Sign in to make a peer set of your own.")).toBeVisible();
});
