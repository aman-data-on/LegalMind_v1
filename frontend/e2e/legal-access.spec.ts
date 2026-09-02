import { expect, test } from "@playwright/test";

import {
  createAnalysedReview,
  csrfToken,
  evaluationIds,
  fixture,
  storageStatePath,
} from "./support";

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
    const { reviewId } = await createAnalysedReview(page);
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
    await legalPage.goto(`/reviews?id=${reviewId}`);
    const evaluation = legalPage.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();
    await expect(evaluation.locator(".outcome")).toHaveCount(1);

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

    // ---- and then Legal scope ENDS, which is worth stating plainly -------
    // That decision resolved the last outstanding Evaluation, so `_advance_if_resolved`
    // moved the Review LEGAL_REVIEW → RESOLVED (Step 30 r7/r16) — and a RESOLVED Review
    // with no active escalation is no longer in Legal scope. So the Legal Reviewer who
    // just decided immediately loses sight of the Review.
    //
    // This is `REC-09` behaving exactly as locked, and it is faithful to Step 24 r18:
    // "a resolved Review remains accessible to its owner … while Legal access remains
    // governed by Legal scope/assignment." It is asserted rather than worked around,
    // and reported to the owner as a consequence they may wish to revisit — widening
    // the definition here would be inventing beyond what was approved.
    const afterDecision = await legalPage.request.get(`/api/v1/reviews/${reviewId}`);
    expect(afterDecision.status()).toBe(404);
    await legal.close();

    // r18's first half, unchanged: the owner keeps access to their resolved Review,
    // and never stopped being its owner (r16, r17).
    const ownerAfter = await page.request.get(`/api/v1/reviews/${reviewId}`);
    expect(ownerAfter.status()).toBe(200);
    const body = (await ownerAfter.json()).data;
    expect(body.status).toBe("RESOLVED");
    expect(body.created_by).toBe(ownerId);
    expect(f.accounts.owner.email).not.toBe(f.accounts.counsel.email);
  });

  test("an un-analysed Review stays invisible to Legal", async ({ page, browser }) => {
    // The widening is bounded by `REC-09`'s two conditions. A Review with no Findings
    // is DRAFT, in no Legal scope, and `SEC-07`'s non-disclosure still applies.
    const { reviewId } = await createAnalysedReview(page, { analyse: false });

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
