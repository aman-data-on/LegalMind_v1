import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, storageStatePath } from "./support";

/**
 * Internal legal position must not leak — locked LEGAL-02, SEC-07, 49.7 r4, 52.4.
 *
 * The backend suite already proves the *payload* omits these fields. What it cannot
 * prove is what a browser ends up holding: the response passes through Next's
 * same-origin proxy, is parsed by the application's fetch wrapper, and is rendered.
 * A leak could be introduced at any of those points — a proxy that merges a default,
 * a component that renders a placeholder, a serializer that nulls instead of omitting.
 *
 * The locked distinction under test is **omitted, not nulled** (49.7 r4). `null` still
 * discloses that an internal position exists for this object, which is the disclosure
 * LEGAL-02 prevents; the key must simply not be there.
 *
 * `owner` holds `USER` and therefore not `legal_position.view`; `counsel` holds
 * `LEGAL_REVIEWER` and does. Same object, two callers, one difference.
 */

const CONFIDENTIAL_KEYS = [
  "rule_outcome",
  "expected_value",
  "operator",
  "comparison",
  "explanation",
  "rule_configuration",
];

test.describe("LEGAL-02 — confidential fields are absent, not null", () => {
  // `owner` holds USER, and therefore not `legal_position.view`. Sessions come from
  // `auth.setup.ts`: S-5 caps logins at 10 per 300s and re-authenticating per test
  // exhausted it — the control working as locked.
  test.use({ storageState: storageStatePath("owner") });

  test("a user without legal_position.view receives no such key", async ({ page }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    // Read through the same origin the browser uses, so the proxy is in the path.
    const response = await page.request.get(`/api/v1/reviews/${reviewId}/findings`);
    expect(response.ok()).toBeTruthy();
    const findings = (await response.json()).data;
    expect(findings.length).toBeGreaterThan(0);

    const evaluations = findings.flatMap((finding: any) => finding.evaluations);
    expect(
      evaluations.length,
      "49.7 r1 — a Finding is never returned without its Evaluations",
    ).toBeGreaterThan(0);

    for (const evaluation of evaluations) {
      for (const key of CONFIDENTIAL_KEYS) {
        // `not.toHaveProperty` is the assertion that matters: a `null` value would
        // satisfy a truthiness check and still disclose existence.
        expect(evaluation, `${key} must be omitted, not nulled`).not.toHaveProperty(key);
      }
    }
  });

  test("nothing confidential is rendered on the Review screen either", async ({
    page,
  }) => {
    const f = fixture();
    const { reviewId } = await createAnalysedReview(page);

    await page.goto(`/reviews/${reviewId}`);
    // Wait for an Evaluation to have rendered before asserting an absence, or the
    // assertion would pass against an empty screen — the commonest way a
    // confidentiality test proves nothing.
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    // Locked 52.4 renders these **presence-tested**: when the server omits a field
    // there is no element at all, not an empty span and not a placeholder. So the
    // assertion is on elements, not on substrings of the page text.
    await expect(evaluation.locator(".outcome")).toHaveCount(0);
    await expect(evaluation.locator(".evaluation__explanation")).toHaveCount(0);
    const labels = await evaluation.locator(".evaluation__facts dt").allInnerTexts();
    expect(labels).toContain("Found in contract");     // the contract's own value
    expect(labels).not.toContain("Company Standard");  // an internal position
    expect(labels).not.toContain("Comparison");

    // The scoped Evaluation is still fully identified — omission removes the legal
    // position, not the audit trail (45B.10 / AM-19).
    await expect(evaluation).toHaveAttribute("data-scope", "GENERAL");
    await expect(evaluation.locator(".evaluation__provenance")).toContainText(
      "NUMERIC-COMPARISON-v1",
    );
  });

});

test.describe("LEGAL-02 — a caller WITH the permission does receive it", () => {
  // The other half of the comparison. Without it, the tests above could pass simply
  // because nothing was ever populated — an omission and an empty field look
  // identical from outside.
  //
  // `counsel` builds its OWN Review rather than reading the owner's, because of
  // finding `F-6`: Review visibility is ownership or an active `review_assignments`
  // row, and no endpoint can create that row, so cross-user Legal access is
  // unreachable through the API. Same STRUCTURAL fixture, so the difference that
  // matters — `legal_position.view` — is still the only one.
  test.use({ storageState: storageStatePath("counsel") });

  test("a Legal Reviewer sees the position the owner could not", async ({ page }) => {
    const { reviewId } = await createAnalysedReview(page);

    const response = await page.request.get(`/api/v1/reviews/${reviewId}/findings`);
    expect(response.status()).toBe(200);

    const evaluations = (await response.json()).data.flatMap(
      (finding: any) => finding.evaluations,
    );
    expect(evaluations.length).toBeGreaterThan(0);
    expect(
      evaluations.some((e: any) => "rule_outcome" in e),
      "a caller WITH legal_position.view must receive rule_outcome",
    ).toBeTruthy();
  });

  test("and the screen renders it", async ({ page }) => {
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/reviews/${reviewId}`);
    const evaluation = page.locator("li.evaluation").first();
    await expect(evaluation).toBeVisible();

    // The mirror image of the owner's screen: the elements that were absent there are
    // present here, which is what makes their absence meaningful rather than incidental.
    await expect(evaluation.locator(".outcome")).toHaveCount(1);
    const labels = await evaluation.locator(".evaluation__facts dt").allInnerTexts();
    expect(labels).toContain("Company Standard");
  });
});
