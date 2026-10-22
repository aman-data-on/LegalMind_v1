import { expect, test, type Page } from "@playwright/test";

import { createAnalysedReview, csrfToken, evaluationIds, openFindingsTab,
         storageStatePath } from "./support";

/**
 * The review workflow, end to end (owner, 2026-10-22; AB-103). One Review followed from
 * "sent" to "complete" and back: at every step the Summary's stage, the Findings header,
 * the card and the document legend say the same thing — the server's own derivation —
 * and a failed decision never reads as a recorded one.
 *
 * The STRUCTURAL fixture gives one point to decide (a 24-month cap against the
 * structural 12); it exercises the path, never a legal conclusion (rule 21).
 */

async function stageLine(page: Page) {
  await page.getByRole("tab", { name: "Summary" }).click();
  return page.locator(".ws-stage__line");
}

async function send(owner: Page, reviewId: string, email: string) {
  const got = await (await owner.request.get(`/api/v1/reviews/${reviewId}/assignments`)).json();
  const person = got.data.eligible.find((p: { email: string }) => p.email === email);
  expect(person, `${email} is offered as a reviewer`).toBeTruthy();
  const sent = await owner.request.post(`/api/v1/reviews/${reviewId}/assignments`, {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrfToken(owner) },
    data: { user_id: person.user_id },
  });
  expect(sent.status()).toBe(201);
}

test.describe("the review workflow (AB-103)", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("is followed from sent to complete, and said the same everywhere", async ({
    page, browser,
  }) => {
    const { reviewId, contractId } = await createAnalysedReview(page);

    // ---- the owner: analysed, not yet sent ---------------------------------
    await page.goto(`/dashboard?id=${contractId}`);
    await expect(await stageLine(page)).toContainText("Not yet sent for review");
    await expect(page.locator(".ws-stage__count")).toContainText("0 of 1 point decided");
    await expect(page.locator(".ws-stage__next")).toContainText("sends it to a reviewer");

    const counselState = storageStatePath("counsel");
    const legal = await browser.newContext({ storageState: counselState });
    const reviewer = await legal.newPage();
    const counselEmail = (await (await reviewer.request.get("/api/v1/auth/session")).json())
      .data.email;
    await send(page, reviewId, counselEmail);

    // ---- the reviewer: with Legal, decides in the card ----------------------
    await reviewer.goto(`/dashboard?id=${contractId}`);
    await expect(await stageLine(reviewer)).toContainText("With Legal");
    await openFindingsTab(reviewer);
    await expect(reviewer.locator(".ws-pane__stage")).toContainText("0 of 1 decided");
    const card = reviewer.locator("article[data-finding-id]").first();
    await card.locator(".ws-decision__open").click();
    await card.locator(".ws-decision__form select").selectOption("REQUIRE_COMPANY_STANDARD");
    await expect(card.locator(".ws-decision__effect")).toContainText("changes to send");
    await card.getByLabel("Justification (required)").fill("STRUCTURAL browser-suite decision.");
    await card.getByRole("button", { name: "Record decision" }).click();
    await expect(card.locator("[data-status]").first())
      .toHaveText("Change requested — our wording to send");

    // the same words on every surface, from the server
    const decidedNext = "Every point is decided — the decision on the contract is next";
    await expect(reviewer.locator(".ws-pane__stage")).toContainText(decidedNext);
    await expect(await stageLine(reviewer)).toContainText(decidedNext);
    await expect(reviewer.locator(".ws-decided")).toContainText(
      "Change requested — our wording to send");
    await expect(reviewer.locator(".ws-legend")).toContainText("Decided by a reviewer");

    // ---- the contract decision closes the review --------------------------
    const panel = reviewer.locator(".ws-contract");
    await panel.getByLabel("Sign after our changes").check();
    await panel.getByLabel("Reason (required)").fill("STRUCTURAL browser-suite decision.");
    await panel.getByRole("button", { name: "Record the decision" }).click();
    await expect(await stageLine(reviewer)).toContainText(
      "Review complete: Sign after our changes");
    await expect(reviewer.locator(".ws-stage__note")).toContainText("not approval to sign");

    // ---- the owner sees the same stage and the decision on the card -------
    await page.reload();
    await expect(await stageLine(page)).toContainText("Review complete: Sign after our changes");
    await openFindingsTab(page);
    await expect(page.locator("article[data-finding-id] .ws-decision__done").first())
      .toContainText("Change requested — our wording to send");
    await expect(page.locator(".ws-decision__open")).toHaveCount(0);   // no Decide for the owner

    // ---- a late clarification reopens it ---------------------------------
    const [evaluationId] = await evaluationIds(reviewer, reviewId);
    const late = await reviewer.request.post(`/api/v1/evaluations/${evaluationId}/decisions`, {
      headers: { "Content-Type": "application/json",
                 "X-CSRF-Token": await csrfToken(reviewer) },
      data: { decision_type: "REQUEST_CLARIFICATION", expected_version: 1,
              justification: "STRUCTURAL browser-suite decision." },
    });
    expect(late.status()).toBe(201);
    await reviewer.reload();
    await expect(await stageLine(reviewer)).toContainText("Waiting for the client's clarification");
    await legal.close();
  });

  test("a refused decision is shown as refused and records nothing", async ({
    page, browser,
  }) => {
    const { reviewId, contractId } = await createAnalysedReview(page);
    const legal = await browser.newContext({ storageState: storageStatePath("counsel") });
    const reviewer = await legal.newPage();
    await reviewer.route("**/api/v1/evaluations/*/decisions", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({
        error: { code: "DECISION_VERSION_CONFLICT", message: "conflict", request_id: "e2e" } }) });
    });
    await reviewer.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(reviewer);
    const card = reviewer.locator("article[data-finding-id]").first();
    await card.locator(".ws-decision__open").click();
    await card.getByLabel("Justification (required)").fill("STRUCTURAL browser-suite decision.");
    await card.getByRole("button", { name: "Record decision" }).click();
    await expect(card.locator(".ws-decision__conflict")).toContainText("Not recorded");
    await expect(card.locator('[role="status"]')).toHaveCount(0);   // no success line
    const [evaluationId] = await evaluationIds(reviewer, reviewId);
    const chain = await (await reviewer.request.get(
      `/api/v1/evaluations/${evaluationId}/decisions`)).json();
    expect(chain.data).toHaveLength(0);
    await legal.close();
  });

  test("a read-only review says why, never 'updated by another user'", async ({ page, browser }) => {
    const { contractId } = await createAnalysedReview(page);
    const legal = await browser.newContext({ storageState: storageStatePath("counsel") });
    const reviewer = await legal.newPage();
    const why = "This contract is archived; restore it to record a decision.";
    await reviewer.route("**/api/v1/evaluations/*/decisions", async (route) => {
      if (route.request().method() !== "POST") return route.fallback();
      await route.fulfill({ status: 409, contentType: "application/json", body: JSON.stringify({
        error: { code: "REVIEW_READ_ONLY", message: why, request_id: "e2e" } }) });
    });
    await reviewer.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(reviewer);
    const card = reviewer.locator("article[data-finding-id]").first();
    await card.locator(".ws-decision__open").click();
    await card.getByLabel("Justification (required)").fill("STRUCTURAL browser-suite decision.");
    await card.getByRole("button", { name: "Record decision" }).click();
    await expect(card.locator('.ws-decision [role="alert"]')).toContainText(why);
    await expect(card.locator(".ws-decision__conflict")).toHaveCount(0);
    await legal.close();
  });
});
