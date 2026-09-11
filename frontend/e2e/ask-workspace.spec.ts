import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, postOk, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The Ask workspace against the real backend (owner instruction, 2026-09-11).
 *
 * What only a browser proves here is the COMPOSED product flow: a question asked
 * with no document at all, a document attached from the composer, and a
 * comparison question answered by the deterministic evaluator's own Findings
 * rather than by the assistant. No credential for the generator exists in this
 * environment — production's posture — so every answer that clears retrieval
 * still refuses; that is the point of asserting the SHAPE of the exchange (a
 * turn arrives, it is recorded, the rail lists it) rather than any wording the
 * generator would supply.
 */

test.describe("Ask — the AI workspace", () => {
  test("A question can be asked with no document, and the chat is kept", async ({ page }) => {
    await page.goto("/dashboard/ask");

    // The screen IS the capability now: a composer, not a sentence telling the
    // reader that asking happens somewhere else.
    const composer = page.getByLabel("Your question");
    await expect(composer).toBeVisible();

    await composer.fill("What standards do we require for liability?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();

    // One exchange: the question, and an answer turn of some state. The state
    // depends on the deployment's sources; that a turn arrives does not.
    await expect(page.locator(".ws-turn--user")).toHaveCount(1, { timeout: 30_000 });
    await expect(page.locator(".ws-ask__answer").first()).toBeVisible({ timeout: 30_000 });

    // The conversation became addressable, and the rail records it — the page's
    // other half, without a table anywhere.
    await expect(page).toHaveURL(/\/dashboard\/ask\?id=/);
    await expect(page.locator(".ws-chat__railitem").first()).toContainText(
      "What standards do we require for liability?",
    );
    await expect(page.locator("table")).toHaveCount(0);

    // AI-03 item 16 at the composed-page level.
    expect((await page.locator("body").innerText()).toLowerCase()).not.toContain("confidence");
  });

  test("A document attached in the composer starts a chat about it", async ({ page }) => {
    const f = fixture();
    await page.goto("/dashboard/ask");

    await page.locator('input[type="file"]').setInputFiles({
      name: f.document.filename,
      mimeType: f.document.mime,
      buffer: readFileSync(f.document.path),
    });
    // The attachment is visible BEFORE sending, and says what sending will do.
    await expect(page.locator(".ws-chat__file")).toContainText(f.document.filename);

    await page.getByLabel("Your question").fill("What is the termination notice period?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();

    // The chat is now scoped to the uploaded document, by name, with a way into it.
    const scope = page.locator(".ws-chat__scope");
    await expect(scope).toContainText("About", { timeout: 60_000 });
    await expect(scope.getByRole("link")).toHaveAttribute("href", /\/dashboard\?id=/);
    await expect(page.locator(".ws-ask__answer").first()).toBeVisible({ timeout: 60_000 });
  });

  test("A comparison question is answered by the evaluator's Findings, as a table", async ({
    page,
  }) => {
    // A real analysed Review — the deterministic result the assistant is
    // forbidden to produce and required to hand off to (`AM-25` r4).
    const { contractId } = await createAnalysedReview(page);
    const conversation = await postOk(page, "/conversations", { contract_id: contractId });

    await page.goto(`/dashboard/ask?id=${conversation.id}`);
    await page.getByLabel("Your question").fill("Compare this agreement with our standards.");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();

    // Routed, not answered: the label says which engine spoke.
    const routed = page.locator(".ws-ask__answer--routed");
    await expect(routed).toBeVisible({ timeout: 60_000 });
    await expect(routed).toContainText("Compared by the evaluator, not the assistant");

    // The table the owner asked for, built from the Findings themselves.
    const table = page.locator(".ws-chat__table");
    await expect(table).toBeVisible({ timeout: 30_000 });
    await expect(table.locator("thead")).toContainText("Requirement");
    await expect(table.locator("thead")).toContainText("Result");
    // The three reader words, and nothing outside that vocabulary.
    await expect(table.locator("tbody tr").first()).toContainText(
      /Acceptable|Requires modification|Needs a decision/,
    );
  });

  test("The global Ask entry point reaches the workspace from an ordinary screen", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await page.getByRole("link", { name: "Ask", exact: true }).last().click();
    await expect(page).toHaveURL(/\/dashboard\/ask/);
    await expect(page.getByLabel("Your question")).toBeVisible();
  });
});
