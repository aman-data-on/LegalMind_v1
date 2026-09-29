import { expect, test } from "@playwright/test";

import { createAnalysedReview, storageStatePath } from "./support";

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

  test("a failed first question with a file attached is retried in the chat that holds the file", async ({
    page,
  }) => {
    let calls = 0;
    await page.route("**/api/v1/conversations/*/messages", async (route) => {
      calls += 1;
      if (calls === 1) await route.abort("failed");
      else await route.continue();
    });
    await page.goto("/dashboard/ask");
    await page.locator('input[type="file"]').setInputFiles({
      name: "retry-check.txt", mimeType: "text/plain",
      buffer: Buffer.from("A plain test file for the retry path.\n"),
    });
    await page.getByLabel("Your question").fill("thanks");
    await page.keyboard.press("Enter");
    const retry = page.getByRole("button", { name: "Try again" });
    await expect(retry).toBeVisible({ timeout: 60_000 });
    await retry.click();
    // The retry has no file left to upload; it goes to the chat the upload made
    // rather than a new chat with no document, which the server refuses.
    await expect(page.locator(".ws-ask__answer").first()).toContainText(
      "You're welcome", { timeout: 30_000 });
    expect(calls).toBe(2);
    await expect(page.locator(".ws-ask__turns").getByRole("alert")).toHaveCount(0);
  });

  test("a chat without a document does not offer to compare one", async ({ page }) => {
    await page.goto("/dashboard/ask");
    const openers = page.getByRole("group", { name: "Example questions" });
    await expect(openers).toBeVisible();
    await expect(openers).not.toContainText("Compare this agreement");
  });

  test("the document dock recovers a failed send with Try again, and keeps focus", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    let calls = 0;
    await page.route("**/api/v1/conversations/*/messages", async (route) => {
      calls += 1;
      if (calls === 1) await route.abort("failed");
      else await route.continue();
    });
    await page.goto(`/dashboard?id=${contractId}`);
    await page.getByRole("button", { name: /Ask about this document/i }).click();
    const input = page.getByLabel("Your question about this document");
    await input.fill("thanks");
    await page.keyboard.press("Enter");
    const retry = page.locator(".ws-dock__panel").getByRole("button", { name: "Try again" });
    await expect(retry).toBeVisible({ timeout: 30_000 });
    await retry.click();
    await expect(page.locator(".ws-dock__panel .ws-ask__answer").first())
      .toContainText("You're welcome", { timeout: 30_000 });
    await expect(input).toBeFocused();
    // One turn: the retry replaced the failed one rather than stacking beside it.
    await expect(page.locator(".ws-dock__panel .ws-ask__turn")).toHaveCount(1);
    expect(calls).toBe(2);
  });
});
