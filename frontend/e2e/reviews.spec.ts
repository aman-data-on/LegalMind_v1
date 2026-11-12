import { expect, test } from "@playwright/test";

import { apiPost, createAnalysedReview, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * P1 (slice 5) — the reviews queue, the report, and ask history, against the
 * real backend.
 *
 * What only the browser adds: the report's numbers are the API's numbers on a
 * composed page that renders no grade (F-9/36.10 at the page level), and a
 * recorded conversation replays the byte-identical refusal sentence the live
 * pane showed (`AM-29` r4 — the record must not become the oracle).
 */

test.describe("the reviews queue and the report", () => {
  test("an analysed review is queued, and its report shows counts — never a grade", async ({
    page,
  }) => {
    const { contractId, reviewId } = await createAnalysedReview(page);

    // UX Batch 2 (owner, 2026-11-11 "go with your recommendation"): the legacy Reviews
    // QUEUE is Legal's. A contract owner (this account, no `legal.review`) asking for it
    // lands on Contracts; the report itself still opens by its link (the contract's ⋯).
    await page.goto("/dashboard/reviews");
    await expect(page).toHaveURL(/\/contracts$/);
    await expect(page.locator('nav a[href="/dashboard/reviews"]')).toHaveCount(0);
    await expect(page.locator('a[href^="/contracts?"], a[href^="/reviews"]')).toHaveCount(0);

    await page.goto(`/dashboard/reviews?id=${reviewId}`);
    // AB-103: the page shows the report the download contains — the summary and
    // next steps first, the audit record last
    const report = page.getByRole("article", { name: "Review report" });
    await expect(report.getByRole("heading", { name: "Summary" })).toBeVisible();
    await expect(report.getByText(/was checked against our standard terms on 1 point/))
      .toBeVisible();
    await expect(report.getByRole("heading", { name: "Next steps" })).toBeVisible();
    // the audit record is folded at the end (owner, 2026-10-27) — and opens on request
    await report.getByText("Audit record", { exact: true }).click();
    await expect(report.getByText(/never grades the document/)).toBeVisible();
    await expect(report.getByText(/of our standards found something/)).toBeVisible();

    // F-9/36.10 and AI-03 item 16, on the rendered page: counts exist, but no
    // confidence figure, no risk label, no verdict wording.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
    expect(body).not.toContain("risk");
    expect(body).not.toContain("verdict");

    await page.getByRole("link", { name: "Open the workspace" }).click();
    await expect(page).toHaveURL(new RegExp(`/contracts/${contractId}$`));
  });

  test("the status filter narrows through the API's allow-list", async ({ browser }) => {
    // the queue is Legal's since UX Batch 2: read it as counsel (legal.review)
    const context = await browser.newContext({ storageState: storageStatePath("counsel") });
    const page = await context.newPage();
    await page.goto("/dashboard/reviews");
    await expect(page.getByRole("heading", { name: "Reviews" })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();

    // Since AM-174 a decision on the contract CLOSES a Review, so other specs may leave
    // one: filtering to CLOSED shows only closed Reviews, or the empty state honestly
    // worded — never an error, never a Review in another status.
    await page.getByRole("button", { name: "Closed" }).click();
    await expect(page.locator("tbody tr").first()
      .or(page.getByText("Nothing visible to your account has this status."))).toBeVisible();
    await expect(page.locator("tbody tr").filter({ hasNotText: "Closed" })).toHaveCount(0);
    await page.getByRole("button", { name: "All" }).click();
    await expect(page.locator("tbody tr").first()
      .or(page.getByText(/Nothing visible to your account/))).toBeVisible();
    await context.close();
  });
});

test.describe("ask history", () => {
  test("an asked question is listed, and its transcript replays the identical refusal", async ({
    page,
  }) => {
    // A chat with no document: the Ask page lists only its own chats (a document's
    // chats are listed on that document's page).
    const created = await apiPost(page, "/conversations", {});
    const conversationId = (await created.json()).data.id;
    // Vocabulary the document cannot contain — nothing retrieved, so the turn is
    // recorded as NO_EVIDENCE_RETRIEVED (the same cause the live ask spec pins).
    const question = "Explain the zorbulated quixotic framblewitz stipulations";
    const asked = await apiPost(page, `/conversations/${conversationId}/messages`, { question });
    expect(asked.status(), await asked.text()).toBe(201);
    const live = (await asked.json()).data;

    await page.goto("/dashboard/ask");
    // The screen is the Ask workspace since 2026-09-11: the record lives in its
    // rail, beside a composer, rather than on a page of its own. The property
    // under test is unchanged — the question is listed, and opening it replays
    // the identical refusal.
    await expect(page.getByLabel("Your question")).toBeVisible();
    // Target the conversation this test created, by id. Matching on question
    // TEXT made the spec depend on no other spec ever asking the same thing in
    // the shared e2e database — which stopped being true, and is not a property
    // this test is about.
    await page.getByRole("link", { name: question })
      .and(page.locator(`a[href="/dashboard/ask?id=${conversationId}"]`))
      .click();

    await expect(page).toHaveURL(`/dashboard/ask?id=${conversationId}`);
    await expect(page.locator(".ws-turn--user")).toContainText(question);
    const refusal = page.locator(".ws-ask__answer--refusal");
    // The replay is the refusal the live ask gave, word for word.
    await expect(refusal).toHaveText(live.text);
    await expect(refusal).toHaveAttribute("data-state", live.answer_state);

    // The record is quiet, and no confidence figure exists anywhere on it.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
  });
});
