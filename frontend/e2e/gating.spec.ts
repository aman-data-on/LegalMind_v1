import { expect, test } from "@playwright/test";

import {
  createAnalysedReview,
  csrfToken,
  evaluationIds,
  storageStatePath,
} from "./support";

/**
 * UI gating is presentation only — locked 52.3, 47.6, SEC-02, ROLE-05, SEC-07.
 *
 * Locked 52.3 hides controls the caller cannot use; locked 47.6 makes the server the
 * only thing that actually enforces it. **Both halves have to hold at once**, and this
 * is the one place they can be checked together: the control is absent from the real
 * DOM, and the same caller's request to the endpoint behind it is still refused.
 *
 * The dangerous half is the second. A hidden control invites the belief that hiding is
 * the protection — and SEC-02 and ROLE-05 exist because that belief, applied to
 * `legal.decision`, would be a super-role bypass.
 */

const PROBE = {
  decision_type: "ACCEPT_DEVIATION",
  justification: "STRUCTURAL probe — must be refused.",
  expected_version: 0,
};

async function attemptDecision(page: import("@playwright/test").Page, id: string) {
  return page.request.post(`/api/v1/evaluations/${id}/decisions`, {
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": await csrfToken(page),
    },
    data: PROBE,
  });
}

test.describe("A user without legal.decision", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("sees no decision form, and is refused when reaching past it", async ({
    page,
  }) => {
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/reviews/${reviewId}`);
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    // Half one — the form is not rendered.
    await expect(page.locator(".decision__form")).toHaveCount(0);
    await expect(page.getByRole("button", { name: "Record decision" })).toHaveCount(0);
    // But the Evaluation still shows that a decision is required: concealing *that*
    // would hide legitimate work rather than an unavailable control.
    await expect(evaluation.locator(".evaluation__flag")).toContainText(
      "Decision required",
    );

    // Half two — the endpoint refuses the same caller. Reaching past the UI is the
    // only thing that proves the UI was never the control.
    const [evaluationId] = await evaluationIds(page, reviewId);
    const response = await attemptDecision(page, evaluationId);
    // 47.7 — the object IS visible to this caller (they own the Review), so the
    // refusal is a 403 about the operation rather than a 404 about the object.
    expect(response.status()).toBe(403);
    expect((await response.json()).error.code).toBe("FORBIDDEN");
  });
});

test.describe("A super-role holder without legal authority", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("cannot decide by any route (SEC-02, ROLE-05)", async ({ page }) => {
    // `admin` holds SUPER_ADMIN — `user.manage`, `role.manage`, `platform.manage`,
    // `audit.view` — and deliberately neither `legal.decision` nor
    // `legal_position.view`. Locked SEC-02: no super-role bypass may ever reach legal
    // authority. Checked over real HTTP, because "by any route" is a claim about routes.
    const { reviewId } = await createAnalysedReview(page);
    const [evaluationId] = await evaluationIds(page, reviewId);

    const response = await attemptDecision(page, evaluationId);
    expect(response.status()).toBe(403);
    expect((await response.json()).error.message).toContain("legal.decision");
  });
});

test.describe("Out-of-scope objects", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("are a 404 byte-identical to a non-existent one (SEC-07, 49.5 r1)", async ({
    page,
    browser,
  }) => {
    // NOT analysed, deliberately. This spec previously used an analysed Review, and
    // locked `REC-09` made that a 200 for `counsel` — correctly, because an analysed
    // Review with an Evaluation awaiting a decision is in **Legal scope**. The rule
    // under test here is non-disclosure of an out-of-scope object, so the fixture has
    // to be genuinely out of scope: a DRAFT Review with no Findings and no escalation.
    const { reviewId } = await createAnalysedReview(page, { analyse: false });

    // A second, genuinely separate session. `counsel` neither owns this Review, holds
    // an assignment, nor has Legal scope over it, so existence must not be disclosed.
    const other = await browser.newContext({
      storageState: storageStatePath("counsel"),
    });
    const otherPage = await other.newPage();

    const real = await otherPage.request.get(`/api/v1/reviews/${reviewId}`);
    const invented = await otherPage.request.get(
      "/api/v1/reviews/00000000-0000-4000-8000-000000000000",
    );

    expect(real.status()).toBe(404);
    expect(invented.status()).toBe(404);
    // 49.5 r1 — the two must be byte-identical. The correlation id is deliberately
    // per-request (49.9), so it is the one part excluded from the comparison.
    const strip = (body: string) => body.replace(/"request_id": ?"[^"]*"/, "");
    expect(strip(await real.text())).toBe(strip(await invented.text()));

    await other.close();
  });
});
