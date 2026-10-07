import { defineConfig, devices } from "@playwright/test";

// Points at a running frontend (which proxies /api to the backend). Override with E2E_BASE_URL.
// The stack must be up and seeded before this runs — see docs/testing.md. Not wired into
// `make check`; it is the tier-2 suite (ADR-0019).
export default defineConfig({
  testDir: "./tests",
  timeout: 120_000, // report generation can take up to ~90s (NFR-003)
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
