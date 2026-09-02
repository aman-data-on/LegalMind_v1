import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, storageStatePath } from "./support";

// `counsel` holds LEGAL_REVIEWER + LEGAL_DECISION_AUTHORITY (+ USER, see `F-6`).
test.use({ storageState: storageStatePath("counsel") });

/**
 * Recording a Legal Decision — locked 52.7, 52.5, Step 31, AB-1.
 *
 * Locked 52.7: "Optimistic UI is **not** used for Legal Decisions. A decision is
 * displayed only after the server confirms it, because a `409` (version collision) is a
 * real and meaningful outcome." A component test can check that a re-fetch callback
 * fires; only a browser can show that the rendered result arrived over the network.
 *
 * The failure this prevents is specific. An optimistic UI would display a decision a
 * `409` had actually rejected — and Step 31's chain is append-only with version
 * collision detection precisely because concurrent decisions are expected. A user
 * acting on a decision the server never accepted is acting on a legal record that does
 * not exist.
 *
 * `counsel` builds its own Review here — see `F-6` in `e2e_bootstrap.py`: no endpoint
 * can create the `review_assignments` row that would let Legal reach someone else's.
 */

const JUSTIFICATION =
  "STRUCTURAL browser-suite decision. Not a legal position (rule 21).";

test.describe("52.7 — the decision shown is the decision recorded", () => {
  test("controls attach to the scoped Evaluation, not to the Finding", async ({
    page,
  }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    await page.goto(`/reviews?id=${reviewId}`);
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    // AB-1 / 52.5 — a Finding is a derived summary; a decision belongs to one scoped
    // Evaluation. So the form must live inside the Evaluation element, and there must
    // be no decision control outside one.
    await expect(evaluation).toHaveAttribute("data-scope", "GENERAL");
    await expect(evaluation.getByRole("button", { name: "Record decision" })).toBeVisible();
    expect(
      await page.getByRole("button", { name: "Record decision" }).count(),
      "one decision control per Evaluation requiring one, and none elsewhere",
    ).toBe(await page.locator("li.evaluation .decision__form").count());
  });

  test("the rendered result comes from a server re-read", async ({ page }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/reviews?id=${reviewId}`);
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    // Watch the network, not the DOM: "no optimistic UI" means a GET follows the POST
    // and the displayed state comes from the GET.
    const posted = page.waitForResponse(
      (r) => r.url().includes("/decisions") && r.request().method() === "POST",
    );
    const refetched = page.waitForResponse(
      (r) =>
        r.url().includes(`/reviews/${reviewId}/findings`) &&
        r.request().method() === "GET",
    );

    // Step 31 r11 / AM-15 — a justification is mandatory, and the field says so.
    await evaluation.getByLabel("Justification (required)").fill(JUSTIFICATION);
    await evaluation.getByRole("button", { name: "Record decision" }).click();

    expect((await posted).status()).toBe(201);
    expect(
      (await refetched).status(),
      "the screen must re-read the Findings after deciding (52.7)",
    ).toBe(200);

    // "Current decision" is rendered from the Evaluation payload the re-read
    // returned — not from local state, so it cannot drift from what was recorded.
    await expect(page.locator(".decision__current").first()).toContainText("version 1");
  });

  test("a stale version is refused and reported, never absorbed", async ({ page }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    const findings = await (
      await page.request.get(`/api/v1/reviews/${reviewId}/findings`)
    ).json();
    const evaluationId = findings.data[0].evaluations[0].id;

    // Decide once through the API, so the browser's copy is now stale.
    await page.goto(`/reviews?id=${reviewId}`);
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    const csrf = decodeURIComponent(
      (await page.context().cookies()).find((c) => c.name === "legalmind_csrf")!.value,
    );
    const first = await page.request.post(
      `/api/v1/evaluations/${evaluationId}/decisions`,
      {
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        data: {
          decision_type: "ACCEPT_DEVIATION",
          justification: JUSTIFICATION,
          expected_version: 0,
        },
      },
    );
    expect(first.status()).toBe(201);

    // Now submit from the page, which still believes version 0 is current.
    await evaluation.getByLabel("Justification (required)").fill(JUSTIFICATION);
    await evaluation.getByRole("button", { name: "Record decision" }).click();

    // 49.7 / N-1 Option C — a collision is a 409, surfaced as its own state. The
    // screen must say it was NOT recorded; an optimistic UI would have shown success.
    await expect(page.locator(".decision__conflict")).toContainText("Not recorded");
    await expect(page.locator(".decision__conflict")).toContainText(
      "already updated by another user",
    );

    // Phase 4: the form FREEZES until the user explicitly loads the latest state —
    // no automatic re-fetch shifts the ground under a decision-maker mid-read.
    await expect(
      evaluation.getByRole("button", { name: "Record decision" }),
    ).toBeDisabled();

    await evaluation
      .getByRole("button", { name: "Refresh to see the latest decision" })
      .click();

    // The refresh re-reads from the server; what renders is what actually won.
    await expect(page.locator(".decision__current").first()).toContainText("version 1");
    await expect(
      evaluation.getByRole("button", { name: "Record decision" }),
    ).toBeEnabled();
  });

  test("a Finding cannot be resolved from the screen", async ({ page }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/reviews?id=${reviewId}`);
    await expect(page.locator("li.evaluation").first()).toBeVisible();

    // D-3.6 / Step 30 r3, r16 — resolution is DERIVED server-side. No resolve control
    // exists and no endpoint backs one, which is what makes the "hidden carve-out"
    // failure structurally impossible: a conforming aggregate cap cannot be used to
    // close a Finding whose exception still needs a decision.
    await expect(page.getByRole("button", { name: /resolve/i })).toHaveCount(0);
    await expect(page.getByRole("button", { name: /close finding/i })).toHaveCount(0);
  });
});
