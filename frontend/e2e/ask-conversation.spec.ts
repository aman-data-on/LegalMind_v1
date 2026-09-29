import { expect, test } from "@playwright/test";

import { storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The Ask conversation as a person uses it (`AM-109`, 2026-09-29).
 *
 * "hi" came back as a statute-corpus refusal; "Try again" put back nothing and sent
 * nothing; a chat with no document offered to compare "this agreement". None of it
 * needs the generator, so all of it runs in CI.
 */
test.describe("Ask — the conversation", () => {
  test("a greeting is greeted, not refused, and searches nothing", async ({ page }) => {
    await page.goto("/dashboard/ask");
    await page.getByLabel("Your question").fill("hi");
    await page.keyboard.press("Enter");
    const answer = page.locator(".ws-ask__answer").first();
    await expect(answer).toContainText("Hello.", { timeout: 30_000 });
    await expect(answer).not.toContainText("couldn't find");
    await expect(page.locator(".ws-turn--user")).toHaveCount(1);
    // Focus comes back to the composer for the next question.
    await expect(page.getByLabel("Your question")).toBeFocused();
  });

  test("a failed send is sent again by Try again", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/v1/conversations/*/messages", async (route) => {
      calls += 1;
      if (calls === 1) await route.abort("failed");
      else await route.continue();
    });
    await page.goto("/dashboard/ask");
    await page.getByLabel("Your question").fill("thanks");
    await page.keyboard.press("Enter");
    const retry = page.getByRole("button", { name: "Try again" });
    await expect(retry).toBeVisible({ timeout: 30_000 });
    await retry.click();
    await expect(page.locator(".ws-ask__answer").first()).toContainText(
      "You're welcome", { timeout: 30_000 });
    expect(calls).toBe(2);
    // One chat, not an orphan per attempt.
    await expect(page).toHaveURL(/\/dashboard\/ask\?id=/);
  });

  test("a chat without a document does not offer to compare one", async ({ page }) => {
    await page.goto("/dashboard/ask");
    const openers = page.getByRole("group", { name: "Example questions" });
    await expect(openers).toBeVisible();
    await expect(openers).not.toContainText("Compare this agreement");
  });
});
