import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, openFindingsTab, storageStatePath } from "./support";

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
 * Who lacks the grant changed under AB-12 r7 (2026-09-05): every Department User
 * now holds `legal_position.view` for their OWN deals, because the department is
 * the audience for the organisation's position. So the caller here is `reader`,
 * an account on a custom role carrying every USER grant EXCEPT the position —
 * the shape an administrator could create for a read-only outsider — and the gate
 * is asserted on it end to end. `counsel` (LEGAL_REVIEWER) holds the grant. Same
 * object, two callers, one difference.
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
  // `reader` holds everything a USER holds except `legal_position.view` (AB-12
  // r7 gave USER itself the grant). Sessions come from `auth.setup.ts`: S-5 caps
  // logins at 10 per 300s and re-authenticating per test exhausted it — the
  // control working as locked.
  test.use({ storageState: storageStatePath("reader") });

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
    const { contractId } = await createAnalysedReview(page);

    /*
     * Ported to the new workspace 2026-09-04. The legacy `/reviews?id=` screen
     * this used to drive is being retired, and LEGAL-02 is the last thing that
     * may lose browser coverage in the move — so the same property is asserted
     * on the surface a reviewer actually uses now: the workspace's Findings pane.
     */
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    // Wait for an Evaluation to have rendered before asserting an absence, or the
    // assertion would pass against an empty screen — the commonest way a
    // confidentiality test proves nothing.
    const evaluation = page.locator(".ws-evaluation").first();
    await expect(evaluation).toBeVisible();

    // Locked 52.4 renders these **presence-tested**: when the server omits a field
    // there is no element at all, not an empty span and not a placeholder. So the
    // assertion is on elements, not on substrings of the page text.
    await expect(evaluation.locator(".ws-evaluation__outcome")).toHaveCount(0);
    await expect(evaluation.locator(".ws-explain")).toHaveCount(0);
    const labels = await evaluation.locator(".ws-facts dt").allInnerTexts();
    expect(labels).toContain("Contract");              // the contract's own value
    expect(labels).not.toContain("Company standard");  // an internal position
    expect(labels).not.toContain("Comparison");

    // The scoped Evaluation is still fully identified — omission removes the legal
    // position, not the audit trail (45B.10 / AM-19).
    await expect(evaluation).toHaveAttribute("data-scope", "GENERAL");
    // Provenance survives the omission (45B.10 / AM-19): the reader loses the
    // legal position, never the record of what produced the result. Porting this
    // test off the legacy screen is what found the new UI nesting this line
    // inside the omitted explanation block, so an owner saw a verdict with no
    // provenance at all — fixed in the same change.
    await expect(evaluation.locator(".ws-evaluation__provenance"))
      .toContainText("NUMERIC-COMPARISON-v1");
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
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    const evaluation = page.locator(".ws-evaluation").first();
    await expect(evaluation).toBeVisible();

    // The mirror image of the owner's screen: the elements that were absent there
    // are PRESENT here — count, not visibility (2026-09-08): the rule-outcome
    // chip moved from the always-visible header into the "How this was
    // determined" disclosure (a readability change, not a permission change),
    // so it is no longer visible without a click even for a caller who holds
    // `legal_position.view`. `legal-access.spec.ts` already proves this same
    // element the same way (`toHaveCount(1)`); this test now matches it rather
    // than asserting a visibility default the redesign deliberately dropped.
    await expect(evaluation.locator(".ws-evaluation__outcome")).toHaveCount(1);
    const labels = await evaluation.locator(".ws-facts dt").allInnerTexts();
    expect(labels).toContain("Company standard");

    // And it is real, renderable content — not dead markup sitting unreachable
    // in a disclosure nobody can open: expanding it makes the chip visible.
    await evaluation.locator(".ws-determined > summary").click();
    await expect(evaluation.locator(".ws-evaluation__outcome")).toBeVisible();
  });
});
