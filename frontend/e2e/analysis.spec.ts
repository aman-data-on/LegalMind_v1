import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, storageStatePath } from "./support";

// `owner` holds USER only — the caller who submits analysis and owns the Review.
// The session is established once in `auth.setup.ts`; S-5 limits logins (10/300s) and
// a spec that re-authenticated per test exhausted it.
test.use({ storageState: storageStatePath("owner") });

/**
 * Submitting analysis from the screen — locked 44.2/44.40, 55.1, 52.7, Step 30.
 *
 * What a browser adds here is the **whole path**: the control is rendered from the
 * caller's permissions, the request crosses Next's same-origin proxy with the CSRF
 * pair, the pipeline runs, and the screen reports progress *only* from the Review's
 * lifecycle state (52.7). Each of those is tested in isolation elsewhere; none of the
 * isolated tests would notice the proxy dropping a header or the screen inventing a
 * progress state.
 *
 * Analysis is **inline** in this configuration — no broker is set, so the response
 * carries the outcome (see `playwright.config.ts`). The queued path is covered by
 * `backend/tests/test_worker.py` and the poll rule by
 * `src/__tests__/analysis-queue.test.ts`; a browser test of it would need Redis for no
 * additional guarantee.
 */

test.describe("The analysis surface", () => {
  test("a Review with no Findings offers analysis, and running it produces them", async ({
    page,
  }) => {
    const f = fixture();
    // Deliberately NOT analysed — this test drives the control on screen.
    const { reviewId } = await createAnalysedReview(page, { analyse: false });

    await page.goto(`/reviews/${reviewId}`);
    await expect(page.getByRole("heading", { name: /Analyse this Review/i })).toBeVisible();
    // Step 30 — a fresh Review is DRAFT, and the screen reads that from the server.
    await expect(page.getByText("DRAFT")).toBeVisible();

    await page.getByRole("button", { name: "Run analysis" }).click();

    // 52.7 — the lifecycle IS the progress report. LEGAL_REVIEW because the
    // STRUCTURAL cap (24) deviates from the structural standard (12) and the
    // fixture rule is the authorized blanket form (AM-33): any deviation requires
    // a decision. The fixture exercises the path, not a legal conclusion.
    await expect(page.locator("li.evaluation").first()).toBeVisible();
    await expect(page.getByText("LEGAL_REVIEW").first()).toBeVisible();
    await expect(page.getByText(f.configuration.requirement_code)).toBeVisible();
  });

  test("re-submitting reports the existing analysis rather than duplicating it", async ({
    page,
  }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    // 43.28 / 49.8 — a repeat is not an error, and must not produce a second Finding.
    const before = await (
      await page.request.get(`/api/v1/reviews/${reviewId}/findings`)
    ).json();
    const repeat = await page.request.post(`/api/v1/reviews/${reviewId}/analyze`, {
      headers: {
        "X-CSRF-Token": decodeURIComponent(
          (await page.context().cookies()).find((c) => c.name === "legalmind_csrf")!
            .value,
        ),
      },
    });
    expect(repeat.ok()).toBeTruthy();
    expect((await repeat.json()).data.already_analysed).toBe(true);

    const after = await (
      await page.request.get(`/api/v1/reviews/${reviewId}/findings`)
    ).json();
    expect(after.data.length).toBe(before.data.length);
  });

  test("an analysed Review no longer offers analysis", async ({ page }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    await page.goto(`/reviews/${reviewId}`);
    await expect(page.locator("li.evaluation").first()).toBeVisible();
    // The control is gone because Findings exist — offering it would promise
    // something 43.28 refuses.
    await expect(
      page.getByRole("heading", { name: /Analyse this Review/i }),
    ).toHaveCount(0);
  });

  test("the evidence trail is on screen, not just in the database", async ({ page }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    await page.goto(`/reviews/${reviewId}`);
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    // Rule 11 / 45B.3 — evidence must survive the evaluator, and rule 12 requires a
    // Finding to be reconstructible. The provenance line carries the evaluator
    // version and the evidence count, which is the visible end of that chain.
    await expect(evaluation.locator(".evaluation__provenance")).toContainText(
      "evidence reference",
    );
    await expect(evaluation.locator(".evaluation__provenance")).toContainText(
      "NUMERIC-COMPARISON-v1",
    );
  });
});
