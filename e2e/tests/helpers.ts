import { expect } from "@playwright/test";
import type { Page } from "@playwright/test";

export const TICKER = process.env.E2E_TICKER ?? "NVDA";

/** Create a throwaway account through the UI and land signed in. AI features need a user
 *  (ADR-0006), and going through the form also exercises the sign-in page. */
export async function signUp(page: Page): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto("/login");
  await page.getByRole("button", { name: "Create an account" }).click();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery-staple");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page.getByRole("button", { name: "Account menu" })).toBeVisible();
  return email;
}

/** Open the command palette with the keyboard and return its dialog. Waits for the app to have
 *  mounted first: `goto` resolves on the load event, a few milliseconds before React attaches
 *  the global key listener, which a test can outrun and a person cannot. */
export async function openPalette(page: Page, key = "ControlOrMeta+k") {
  const dialog = page.getByRole("dialog", { name: "Search companies" });
  await expect(page.getByRole("note").first()).toBeVisible(); // the footer: the app has rendered
  await expect(async () => {
    if (!(await dialog.isVisible())) await page.keyboard.press(key);
    await expect(dialog).toBeVisible({ timeout: 1000 });
  }).toPass();
  return dialog;
}

/** Wait for entrance animations (a panel sliding in, a menu fading in) to finish. Measurements
 *  taken mid-animation are wrong: a fading layer has blended colours, a sliding one is offset.
 *  Endless animations (a skeleton's shimmer) are ignored. */
export async function settled(page: Page): Promise<void> {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((animation) => animation.effect?.getComputedTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );
}
