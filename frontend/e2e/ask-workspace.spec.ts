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

  test("A file attached in Ask is this chat's material, never a contract (AM-133)", async ({
    page,
  }) => {
    const f = fixture();
    const contracts = async () =>
      (await (await page.request.get("/api/v1/contracts?page_size=1")).json()).pagination.total;
    const before = await contracts();
    await page.goto("/dashboard/ask");

    await page.locator('input[type="file"]').setInputFiles({
      name: f.document.filename,
      mimeType: f.document.mime,
      buffer: readFileSync(f.document.path),
    });
    // The attachment is visible BEFORE sending, and says what sending will do.
    await expect(page.locator(".ws-chat__card")).toContainText(f.document.filename);
    // The chat-only rule is one visible control away (`AM-226` r2): the ⓘ is on screen.
    await expect(page.getByRole("button", { name: "About attached files" })).toBeVisible();
    await expect(page.locator("#ws-chat-filehint")).toContainText("not added to the Dashboard");

    await page.getByLabel("Your question").fill("What is the termination notice period?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-ask__answer").first()).toBeVisible({ timeout: 60_000 });

    // Listed as the chat's material by its own name; no document scope, no contract.
    await expect(page.locator(".ws-chat__material")).toContainText(f.document.filename);
    // And above the question it was sent with, again after reopening (`AM-226` r7).
    await expect(page.locator(".ws-chat__cards--sent")).toContainText(f.document.filename);
    await page.reload();
    await expect(page.locator(".ws-chat__cards--sent")).toContainText(f.document.filename);
    await expect(page.locator(".ws-chat__scope")).toHaveCount(0);
    expect(await contracts()).toBe(before);
  });

  test("A long paste becomes a Pasted text card, asked about in one message", async ({
    page,
  }) => {
    await page.goto("/dashboard/ask");
    const box = page.getByLabel("Your question");
    // A synthetic paste never inserts text itself; what the page decides is whether the
    // browser may: `dispatchEvent` is false exactly when the page took the paste over.
    const paste = (text: string) => box.evaluate((el, value) => {
      const data = new DataTransfer();
      data.setData("text/plain", value);
      return el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: data,
                                                            bubbles: true, cancelable: true }));
    }, text);

    // A short paste is left to the browser: text in the box, no card.
    await box.focus();
    expect(await paste("Clause 9: liability is capped at twelve months of fees.")).toBe(true);
    await expect(page.locator(".ws-chat__card")).toHaveCount(0);

    // Too long to send as a question (over 5,000 characters): a card beside the box,
    // and the box stays free for the question.
    const email = "The provider decommissioned the wrong server and data was lost. ".repeat(90);
    expect(await paste(email)).toBe(false);
    await expect(page.locator(".ws-chat__card")).toContainText("Pasted text.txt");
    await expect(box).toHaveValue("");
    await expect(box).toHaveAttribute("placeholder",
      "Ask about this file, or press Send to summarise it");

    await box.fill("What does the client want?");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-ask__answer").first()).toBeVisible({ timeout: 60_000 });
    // One message: the reader's question, not the email; the text is the chat's material.
    await expect(page.locator("[data-role=user]")).toHaveCount(1);
    await expect(page.locator("[data-role=user]")).toContainText("What does the client want?");
    await expect(page.locator(".ws-chat__material")).toContainText("Pasted text.txt");
    await expect(page.locator(".ws-chat__title")).toHaveText("What does the client want?");
  });

  test("A compliance question in Ask points to the Dashboard (AM-133)", async ({ page }) => {
    await page.goto("/dashboard/ask");
    await page.getByLabel("Your question").fill("Compare this agreement with our standards.");
    await page.getByRole("button", { name: /Send question|Searching/ }).click();
    await expect(page.locator(".ws-ask__answer").first())
      .toContainText("upload the document on the Dashboard", { timeout: 60_000 });
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
      /Matches our standard|Change needed|Missing|Needs a decision/,
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

  test("A chat is renamed and deleted from the rail, through the server (AM-116)", async ({
    page,
  }) => {
    const { id } = await postOk(page, "/conversations", {});
    await page.goto(`/dashboard/ask?id=${id}`);
    const row = page.locator(".ws-chat__railrow", {
      has: page.locator(`a[href="/dashboard/ask?id=${id}"]`),
    });

    await row.getByRole("button", { name: /^More options/ }).click();
    await row.getByRole("button", { name: /^Rename chat/ }).click();
    await page.getByLabel("Chat name").fill("Liability questions");
    await page.getByLabel("Chat name").press("Enter");
    await expect(row).toContainText("Liability questions");
    await page.reload();                     // persisted, not only on screen
    await expect(row).toContainText("Liability questions");

    await row.getByRole("button", { name: /^More options/ }).click();
    await row.getByRole("button", { name: /^Delete chat/ }).click();
    const dialog = page.getByRole("dialog", { name: "Delete this chat?" });
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(row).toBeVisible();         // nothing goes without the confirmation
    await row.getByRole("button", { name: /^More options/ }).click();
    await row.getByRole("button", { name: /^Delete chat/ }).click();
    await dialog.getByRole("button", { name: "Delete chat" }).click();
    await expect(row).toHaveCount(0);
    await expect(page).toHaveURL(/\/dashboard\/ask$/);
    await page.reload();
    await expect(row).toHaveCount(0);
  });

  test("A model that cannot answer holds Send, says why, and nothing is sent (AM-226)", async ({
    page,
  }) => {
    await page.goto("/dashboard/ask");
    const picker = page.getByRole("combobox", { name: /^Model: Gemini$/ });
    await expect(picker).toBeVisible();
    await picker.click();
    await page.getByRole("option", { name: "DeepSeek (Not available right now)" }).click();
    await expect(page.getByRole("combobox",
      { name: /^Model: DeepSeek, not available right now$/ })).toBeVisible();
    const box = page.getByLabel("Your question");
    await box.fill("What standards do we require for liability?");
    await expect(page.getByText("Choose an available model to send")).toBeVisible();
    await expect(page.getByRole("button", { name: "Send question" })).toBeDisabled();
    await box.press("Enter");
    await expect(page.locator(".ws-turn--user")).toHaveCount(0);
    await expect(page.getByLabel("Your question")).toHaveValue(
      "What standards do we require for liability?");
  });
});
