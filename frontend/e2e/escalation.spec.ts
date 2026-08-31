import { expect, test } from "@playwright/test";

import {
  createAnalysedReview,
  csrfToken,
  evaluationIds,
  storageStatePath,
} from "./support";

/**
 * Escalation, and the access it confers — locked Steps 4 and 22, `ROLE-04`,
 * Step 24 r5, `AM-23`, `REC-09` condition (a).
 *
 * Two locked properties meet here, and a browser is what exercises both at once:
 *
 * 1. **Escalation is not approval.** `ROLE-04`: it means "this requires authorized
 *    review". A normal User may escalate (Step 22 r4) and may approve nothing (r5), so
 *    the screen offers the first and never the second — and says which it is.
 * 2. **Escalation brings a Review into Legal scope.** Locked Step 24 r5 — "escalation
 *    makes the Review available to the authorized Legal workflow" — is `REC-09`'s
 *    condition (a), and it is the *only* route for a Review that has already been
 *    resolved: Step 30's state machine has no `RESOLVED -> LEGAL_REVIEW` edge, so
 *    condition (b) can never bring one back.
 *
 * The second is the one that matters. It is the path a user takes when they disagree
 * with a resolved outcome, and before `REC-09` no Legal user could ever have seen it.
 */

test.describe("ROLE-04 — escalation is a request for review, not an approval", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("the owner can escalate and cannot approve", async ({ page }) => {
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/reviews?id=${reviewId}`);
    const escalation = page.locator(".escalation").first();
    await expect(escalation).toBeVisible();

    // Step 22 r4 / ROLE-03 — a normal User may escalate…
    await expect(
      escalation.getByLabel("Escalate for authorized review — reason"),
    ).toBeVisible();
    // …and Step 22 r5 — may approve nothing. The decision form is not rendered for a
    // caller without `legal.decision`, and `gating.spec.ts` proves the endpoint refuses
    // them as well, which is the half that actually protects anything.
    await expect(page.locator(".decision__form")).toHaveCount(0);
    await expect(page.getByRole("button", { name: /approve/i })).toHaveCount(0);
  });
});

test.describe("REC-09 (a) — escalation reaches Legal even after resolution", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("a resolved Review becomes visible to Legal again once escalated", async ({
    page,
    browser,
  }) => {
    const { reviewId } = await createAnalysedReview(page);
    const [evaluationId] = await evaluationIds(page, reviewId);

    // ---- resolve it, which takes it OUT of Legal scope -------------------
    // A Legal Decision on the last outstanding Evaluation advances the Review to
    // RESOLVED (Step 30 r7/r16), and a RESOLVED Review with no active escalation is not
    // in Legal scope — `legal-access.spec.ts` pins that consequence.
    const legal = await browser.newContext({
      storageState: storageStatePath("counsel"),
    });
    const legalPage = await legal.newPage();
    const decided = await legalPage.request.post(
      `/api/v1/evaluations/${evaluationId}/decisions`,
      {
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": await csrfToken(legalPage),
        },
        data: {
          decision_type: "ACCEPT_DEVIATION",
          justification: "STRUCTURAL browser-suite decision. Not a legal position.",
          expected_version: 0,
        },
      },
    );
    expect(decided.status()).toBe(201);
    expect((await legalPage.request.get(`/api/v1/reviews/${reviewId}`)).status()).toBe(
      404,
    );

    // ---- the owner escalates, from the screen ---------------------------
    await page.goto(`/reviews?id=${reviewId}`);
    const escalation = page.locator(".escalation").first();
    await expect(escalation).toBeVisible();
    await escalation
      .getByLabel("Escalate for authorized review — reason")
      .fill("STRUCTURAL escalation for the browser suite. Not a legal position.");

    const raised = page.waitForResponse(
      (r) => r.url().includes("/escalate") && r.request().method() === "POST",
    );
    await escalation.getByRole("button", { name: "Escalate" }).click();
    expect((await raised).status()).toBe(201);

    // ROLE-04's wording, rendered only after the fact so it describes what happened.
    await expect(page.locator(".escalation").first()).toContainText(
      "request for review, not an approval",
    );

    // ---- and Legal can see it again -------------------------------------
    // Locked Step 24 r5, reachable at last. The Review is still RESOLVED, so condition
    // (a) is doing the work rather than the lifecycle.
    const seen = await legalPage.request.get(`/api/v1/reviews/${reviewId}`);
    expect(
      seen.status(),
      "escalation must make a resolved Review available to Legal again (Step 24 r5)",
    ).toBe(200);
    expect((await seen.json()).data.status).toBe("RESOLVED");

    await legal.close();
  });
});
