import { expect, test } from "@playwright/test";

import { fixture, signIn } from "./support";

/**
 * The header's bell and account menu are real controls: open, outside-click,
 * Escape-with-focus-return, one popover at a time, and Sign out ends the session.
 */
test.describe("top bar — bell and account menu", () => {
  test.beforeEach(async ({ page }) => {
    await signIn(page, fixture().accounts.owner);
    await page.goto("/dashboard");
  });

  test("the account menu opens, closes on outside click and on Escape", async ({ page }) => {
    const toggle = page.locator("[data-toggle='user']");
    await expect(toggle).toHaveAttribute("aria-expanded", "false");
    await toggle.click();
    await expect(toggle).toHaveAttribute("aria-expanded", "true");
    await expect(page.getByRole("menuitem", { name: "Sign out" })).toBeFocused();

    await page.mouse.click(600, 400);
    await expect(page.getByRole("menu", { name: "Account" })).toHaveCount(0);

    await toggle.click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("menu", { name: "Account" })).toHaveCount(0);
    await expect(toggle).toBeFocused();
  });

  test("the bell opens an honest panel and only one popover is open at a time", async ({ page }) => {
    const bell = page.locator("[data-toggle='bell']");
    await bell.click();
    await expect(page.getByRole("dialog", { name: "Notifications" })).toContainText("Nothing to show");

    await page.locator("[data-toggle='user']").click();
    await expect(page.getByRole("dialog", { name: "Notifications" })).toHaveCount(0);
    await expect(page.getByRole("menu", { name: "Account" })).toBeVisible();

    await bell.click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Notifications" })).toHaveCount(0);
    await expect(bell).toBeFocused();
  });

  test("Sign out ends the session and lands on /login", async ({ page }) => {
    await page.locator("[data-toggle='user']").click();
    await page.getByRole("menuitem", { name: "Sign out" }).click();
    await expect(page).toHaveURL(/\/login/);
  });
});
