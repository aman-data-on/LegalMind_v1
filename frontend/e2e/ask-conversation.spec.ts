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

  test("Enter inside an IME composition picks the word and sends nothing", async ({ page }) => {
    let calls = 0;
    await page.route("**/api/v1/conversations/*/messages", async (route) => {
      calls += 1;
      await route.continue();
    });
    await page.goto("/dashboard/ask");
    const box = page.getByLabel("Your question");
    await box.fill("नमस्ते");
    await box.evaluate((el) => el.dispatchEvent(new KeyboardEvent("keydown", {
      key: "Enter", keyCode: 229, isComposing: true, bubbles: true })));
    await page.waitForTimeout(500);
    expect(calls).toBe(0);
    await expect(box).toHaveValue("नमस्ते");
  });

  test("a long paste is kept whole, counted, and comes back to the box when refused", async ({
    page,
  }) => {
    await page.route("**/api/v1/conversations/*/messages", (route) => route.fulfill({
      status: 422, contentType: "application/json",
      body: JSON.stringify({ error: { code: "BUSINESS_RULE",
        message: "the question exceeds 2000 characters", request_id: "e2e" } }),
    }));
    await page.goto("/dashboard/ask");
    const box = page.getByLabel("Your question");
    await box.focus();
    const pasted = "An email the reader pasted. ".repeat(110);   // ~3,000 characters
    await page.keyboard.insertText(pasted);
    // Never cut at 2,000 without a word (the old `maxLength`).
    await expect(box).toHaveValue(pasted);
    await expect(page.locator(".ws-chat__count")).toContainText("/ 2,000 characters");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Try again" })).toBeVisible({ timeout: 30_000 });
    // The reader's words are back to be shortened, not only held by "Try again".
    await expect(box).toHaveValue(pasted);
  });

  test("the next question can be typed while an answer is found, and keeps its line breaks", async ({
    page,
  }) => {
    await page.route("**/api/v1/conversations/*/messages", async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 2500));
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: {
        conversation_id: "e2e", message_id: "e2e-live", answer_state: "ANSWERED",
        text: "You're welcome.", routed_to_evaluator: false, citations: [], positions: [],
        domains: [] } }) });
    });
    await page.goto("/dashboard/ask");
    const box = page.getByLabel("Your question");
    await box.fill("thanks\nand one more line");
    await page.keyboard.press("Enter");
    // The reader's question, as asked: two lines in the bubble, not one.
    await expect(page.locator(".ws-turn--user .ws-ask__q").first())
      .toHaveText(/thanks\s*\n\s*and one more line/);
    await expect(box).toBeEditable();
    await box.fill("my next question");
    await expect(page.locator(".ws-ask__answer").first()).toContainText(
      "You're welcome", { timeout: 30_000 });
    // The draft typed meanwhile survives the answer's arrival.
    await expect(box).toHaveValue("my next question");
  });

  test("an answer opens at its start, and never pulls a reader who scrolled up", async ({
    page,
  }) => {
    const para = "The company position on this point is set out in the approved standard. ".repeat(6);
    const long = (tag: string) => `Start of ${tag}. ${para}\n\n${para}\n\n${para}\n\n${para}`;
    const turns = Array.from({ length: 5 }, (_, i) => [
      { id: `q${i}`, ordinal: 2 * i, role: "USER", content: `Question ${i}`, answer_state: null,
        routed_to_evaluator: false, document_version_id: null, version_number: null, citations: [] },
      { id: `a${i}`, ordinal: 2 * i + 1, role: "ASSISTANT", content: long(`answer ${i}`),
        answer_state: "ANSWERED", routed_to_evaluator: false, document_version_id: null,
        version_number: null, citations: [] },
    ]).flat();
    let posts = 0;
    await page.route("**/api/v1/conversations/e2e-scroll", (route) => route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ data: { id: "e2e-scroll", contract_id: null, messages: turns } }),
    }));
    await page.route("**/api/v1/conversations/e2e-scroll/messages", async (route) => {
      posts += 1;
      await new Promise((resolve) => setTimeout(resolve, 1500));
      await route.fulfill({ contentType: "application/json", body: JSON.stringify({ data: {
        conversation_id: "e2e-scroll", message_id: `live-${posts}`, answer_state: "ANSWERED",
        text: long(`live ${posts}`), routed_to_evaluator: false, citations: [],
        positions: [], domains: [] } }) });
    });
    await page.goto("/dashboard/ask?id=e2e-scroll");
    const log = page.locator(".ws-chat__log");
    await expect(page.getByText("Start of answer 4.")).toBeVisible();

    // Following along: the new answer's question and first line are in view.
    await page.getByLabel("Your question").fill("first new question");
    await page.keyboard.press("Enter");
    await expect(page.getByText("Start of live 1.")).toBeInViewport({ timeout: 15_000 });

    // Scrolled up to re-read: the arrival moves nothing, and says so.
    await page.getByLabel("Your question").fill("second new question");
    await page.keyboard.press("Enter");
    await log.evaluate((el) => { el.scrollTop = 0; });
    await expect(page.getByRole("button", { name: "New answer below" }))
      .toBeVisible({ timeout: 15_000 });
    expect(await log.evaluate((el) => el.scrollTop)).toBeLessThan(50);
    await page.getByRole("button", { name: "New answer below" }).click();
    await expect(page.getByRole("button", { name: /New answer below|Jump to latest/ }))
      .toHaveCount(0);
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
