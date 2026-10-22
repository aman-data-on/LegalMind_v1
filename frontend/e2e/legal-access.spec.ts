import { expect, test } from "@playwright/test";

import {
  createAnalysedReview,
  csrfToken,
  evaluationIds,
  fixture,
  storageStatePath, openFindingsTab } from "./support";

/**
 * Cross-user Legal access — locked `REC-09`, Step 24 r5/r6/r16, Step 30.
 *
 * This is the spec that proves `F-6` is actually fixed, and it is here rather than in
 * the backend suite for a specific reason: the backend suite could not see the defect.
 * Nine of its test sites insert a `review_assignments` row with `db.add()`, so every
 * Legal-workflow test ran against a state the product had no way to produce. A browser
 * cannot fake a database row, so this spec can only pass if the real authorization path
 * works.
 *
 * The shape under test is the locked one: **the owner never grants anything.** `owner`
 * creates and analyses a Review; `counsel` — a different account, with no assignment and
 * no ownership — reaches it because the Review is in Legal scope, decides on it, and
 * still does not become its owner (r16, r17).
 */

test.describe("REC-09 — a Legal Reviewer reaches another user's Review", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("sees it, decides on it, and does not own it", async ({ page, browser }) => {
    const f = fixture();

    // ---- as the owner: create and analyse -------------------------------
    const { reviewId, contractId } = await createAnalysedReview(page);
    // Step 30 — the STRUCTURAL cap (24) exceeds the configured maximum (12), so an
    // Evaluation requires a decision and the engine derives LEGAL_REVIEW. That is
    // `REC-09` condition (b), reached with no human escalation at all.
    const asOwner = await (await page.request.get(`/api/v1/reviews/${reviewId}`)).json();
    expect(asOwner.data.status).toBe("LEGAL_REVIEW");
    const ownerId = asOwner.data.created_by;

    // ---- as counsel: a different session, no assignment, no ownership ----
    const legal = await browser.newContext({
      storageState: storageStatePath("counsel"),
    });
    const legalPage = await legal.newPage();

    const seen = await legalPage.request.get(`/api/v1/reviews/${reviewId}`);
    expect(
      seen.status(),
      "before REC-09 this was 404 and the Legal workflow was unreachable",
    ).toBe(200);
    expect((await seen.json()).data.created_by).toBe(ownerId);

    // It appears in the Legal caller's Review list too — `REC-09` creates no queue
    // resource, so the list under the same scope rule *is* the Legal queue.
    const listed = await (
      await legalPage.request.get("/api/v1/reviews?page_size=100")
    ).json();
    expect(listed.data.map((r: { id: string }) => r.id)).toContain(reviewId);

    // The Review screen renders for them, including the internal legal position that
    // `LEGAL-02` gates on `legal_position.view` — which counsel holds and the owner
    // does not (see confidentiality.spec.ts for the other half).
    await legalPage.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(legalPage);
    const evaluation = legalPage.locator(".ws-evaluation").first();
    await expect(evaluation).toBeVisible();
    await expect(evaluation.locator(".ws-evaluation__outcome")).toHaveCount(1);

    // ---- and the decision goes through ---------------------------------
    const [evaluationId] = await evaluationIds(legalPage, reviewId);
    const decided = await legalPage.request.post(
      `/api/v1/evaluations/${evaluationId}/decisions`,
      {
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": await csrfToken(legalPage),
        },
        data: {
          decision_type: "ACCEPT_DEVIATION",
          justification:
            "STRUCTURAL browser-suite decision. Not a legal position (rule 21).",
          expected_version: 0,
        },
      },
    );
    expect(decided.status()).toBe(201);

    // ---- Legal keeps it until the contract is decided (AM-174) -----------
    // That decision resolved the last outstanding Evaluation, so the Review moved
    // LEGAL_REVIEW → RESOLVED (Step 30 r7/r16). Until AM-174 the decider lost sight of it
    // at once — reported to the owner as a consequence to revisit, and revisited: a
    // RESOLVED Review Legal decided stays in scope (`REC-09` (b), widened) so the
    // reviewer can decide the contract; deciding it CLOSES the Review and scope ends.
    const afterDecision = await legalPage.request.get(`/api/v1/reviews/${reviewId}`);
    expect(afterDecision.status()).toBe(200);

    // r18's first half, unchanged: the owner keeps access to their resolved Review,
    // and never stopped being its owner (r16, r17).
    const ownerAfter = await page.request.get(`/api/v1/reviews/${reviewId}`);
    expect(ownerAfter.status()).toBe(200);
    const body = (await ownerAfter.json()).data;
    expect(body.status).toBe("RESOLVED");
    expect(body.created_by).toBe(ownerId);
    expect(f.accounts.owner.email).not.toBe(f.accounts.counsel.email);

    const closed = await legalPage.request.post(`/api/v1/reviews/${reviewId}/outcome`, {
      headers: { "Content-Type": "application/json",
                 "X-CSRF-Token": await csrfToken(legalPage) },
      data: { outcome: "SIGN_AS_IS",
              justification: "STRUCTURAL browser-suite decision. Not a legal position.",
              expected_version: 0 },
    });
    expect(closed.status()).toBe(201);
    expect((await closed.json()).data.review_status).toBe("CLOSED");
    expect((await legalPage.request.get(`/api/v1/reviews/${reviewId}`)).status()).toBe(404);
    expect((await page.request.get(`/api/v1/reviews/${reviewId}`)).status()).toBe(200);
    await legal.close();
  });

  test("an un-analysed Review stays invisible to Legal", async ({ page, browser }) => {
    // The widening is bounded by `REC-09`'s two conditions. A Review with no Findings
    // is DRAFT, in no Legal scope, and `SEC-07`'s non-disclosure still applies.
    const { reviewId, contractId } = await createAnalysedReview(page, { analyse: false });

    const legal = await browser.newContext({
      storageState: storageStatePath("counsel"),
    });
    const legalPage = await legal.newPage();
    expect((await legalPage.request.get(`/api/v1/reviews/${reviewId}`)).status()).toBe(
      404,
    );
    await legal.close();
  });
});
