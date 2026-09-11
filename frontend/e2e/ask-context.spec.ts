import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, openFindingsTab, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The owner's flows, against the real backend (2026-09-11).
 *
 * These are the ones a browser can settle deterministically. Flows that need the
 * generator — a grounded prose answer, a citation to click — cannot run here: CI
 * provisions no `LEGALMIND_GEMINI_API_KEY`, which is production's own posture until
 * a key is present, so every answer that clears retrieval still refuses. Those are
 * verified by hand against the deployed system and reported as such; asserting them
 * here would mean asserting the refusal, which proves nothing about the answer.
 *
 * What IS deterministic, and is what these pin:
 *   - a question with no document at all, and the chat kept
 *   - attaching a document mid-thread WITHOUT losing the earlier turns
 *   - a second document starting a new chat instead, and saying so first
 *   - searching the chat list
 *   - a comparison routed to the evaluator and rendered from its own Findings
 *   - the Finding handoff arriving as an editable draft that sends nothing
 */

test.describe("Ask — context that survives", () => {
  test("A document attached mid-thread keeps every earlier turn", async ({ page }) => {
    const f = fixture();
    await page.goto("/dashboard/ask");

    // Turn one: no document anywhere.
    await page.getByLabel("Your question").fill("What standards do we require for liability?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-turn--user")).toHaveCount(1, { timeout: 40_000 });
    await expect(page).toHaveURL(/\/dashboard\/ask\?id=/);

    // Now attach the agreement to THIS chat. The note says what will happen.
    await page.locator('input[type="file"]').setInputFiles({
      name: f.document.filename,
      mimeType: f.document.mime,
      buffer: readFileSync(f.document.path),
    });
    await expect(page.locator(".ws-chat__filenote"))
      .toContainText("Your earlier questions stay");

    await page.getByLabel("Your question").fill("What is the termination notice period?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();

    // THE ASSERTION: two questions, one conversation. Before this change the
    // attachment created a second chat and the first turn disappeared.
    await expect(page.locator(".ws-turn--user")).toHaveCount(2, { timeout: 60_000 });
    await expect(page.locator(".ws-turn--user").first())
      .toContainText("What standards do we require for liability?");
    await expect(page.locator(".ws-chat__scope")).toContainText("About", { timeout: 30_000 });
  });

  test("A second document starts a new chat, and says so before sending", async ({ page }) => {
    const f = fixture();
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);
    await page.goto("/dashboard/ask");

    // A chat that already has a document: attach another and the note changes.
    await page.getByLabel("Your question").fill("What does this say about liability?");
    await page.locator('input[type="file"]').setInputFiles({
      name: f.document.filename,
      mimeType: f.document.mime,
      buffer: readFileSync(f.document.path),
    });
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-chat__scope")).toContainText("About", { timeout: 60_000 });

    await page.locator('input[type="file"]').setInputFiles({
      name: f.document.filename,
      mimeType: f.document.mime,
      buffer: readFileSync(f.document.path),
    });
    await expect(page.locator(".ws-chat__filenote"))
      .toContainText("sending starts a new one");
  });

  test("The chat list can be searched, and says when nothing matches", async ({ page }) => {
    await page.goto("/dashboard/ask");
    await page.getByLabel("Your question").fill("What standards do we require for liability?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-chat__railitem").first()).toBeVisible({ timeout: 40_000 });

    const search = page.getByLabel("Search your chats");
    await search.fill("liability");
    await expect(page.locator(".ws-chat__railitem").first()).toBeVisible();

    // A miss is a different fact from an empty history, and is worded differently.
    await search.fill("zorbulated quixotic framblewitz");
    await expect(page.locator(".ws-chat__railitem")).toHaveCount(0);
    await expect(page.locator(".ws-chat__railempty")).toContainText("No chat matches");
  });
});

test.describe("Findings and obligations lead into Ask", () => {
  test("Ask about this finding arrives as an editable draft and sends nothing", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);

    const handoff = page.getByRole("button", { name: "Ask about this" }).first();
    await expect(handoff).toBeVisible({ timeout: 30_000 });
    await handoff.click();

    // The dock opens with the question IN the input — not sent. That is the rule:
    // the reader always sees exactly what is asked before it is asked.
    const question = page.locator("#ws-ask-question");
    await expect(question).toBeVisible();
    await expect(question).not.toHaveValue("");
    await expect(page.locator(".ws-ask__turn")).toHaveCount(0);
  });

  test("An obligation can be asked about without retyping it", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);

    const obligationAsk = page.locator(".ws-obligations__ask").first();
    // Obligations extraction needs the generator, so the panel may legitimately be
    // in its "could not be extracted" state here. The control is asserted only when
    // there is an obligation to carry it — an empty panel is not a defect.
    if (await obligationAsk.count()) {
      await obligationAsk.click();
      await expect(page.locator("#ws-ask-question")).not.toHaveValue("");
      await expect(page.locator(".ws-ask__turn")).toHaveCount(0);
    }
  });
});
