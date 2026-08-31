import { expect, test } from "@playwright/test";

import { createAnalysedReview, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The Ask surface, in the exact state a user meets it today — `AM-29`, `AM-31`.
 *
 * The backend suite proves the API returns the right refusal states; the Vitest
 * static render proves the component draws each state. What only a browser adds is
 * the COMPOSED page under the real deployment posture: no `LEGALMIND_GEMINI_API_KEY`
 * is set here (CI asserts no provider credential exists), so every ask that clears
 * retrieval still cannot generate — which is precisely production until the `AM-31`
 * gate opens. If that path surfaced as an error banner or a crash, every user of the
 * shipped system would meet it, and no isolated test would have noticed the
 * composition.
 *
 * Two properties are asserted at the page level because they are locked at the
 * product level:
 *
 * 1. **The refusal wording is byte-identical whatever the cause** (`AM-29` r4). One
 *    ask has evidence but no generator; the other retrieves nothing at all. Different
 *    causes, different states server-side — and the same rendered sentence, because a
 *    wording difference would be the oracle r6/r7 exist to prevent.
 * 2. **A refusal renders on the quiet surface, and no confidence figure exists
 *    anywhere on the page** (`AM-29`, `AI-03` item 16). The system saying "not found"
 *    is the system working.
 */

// `AM-29` r4's constant, as `backend/legalmind/assist/state.py` declares it. Asserted
// verbatim so a drift in EITHER repository shows up here as a wording mismatch.
const REFUSAL_TEXT =
  "Information not found in the selected document. " +
  "The available material does not answer this question.";

test.describe("Ask about this document", () => {
  test("both refusal causes render the identical quiet sentence, and no confidence appears", async ({
    page,
  }) => {
    // A contract with an uploaded, inline-indexed document is all the panel needs —
    // no Review and no analysis (`AM-25` r1: asking is not judging).
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/contracts?id=${contractId}`);
    await expect(
      page.getByRole("heading", { name: "Ask about this document" }),
    ).toBeVisible();

    const question = page.getByLabel("Question");
    const ask = page.getByRole("button", { name: "Ask" });

    // Cause 1 — retrieval finds the fixture's liability sentence, but no generator
    // credential exists, so the server refuses with EVIDENCE_INSUFFICIENT.
    //
    // Every content word here appears in the fixture sentence "Liability shall not
    // exceed 24 months of fees paid." — deliberately. Lexical search ANDs every
    // stemmed term, so a single word the document lacks ("clause", "say") returns
    // nothing, and CI provisions no embedding model to rescue the query the way a
    // developer's machine does. The gate must open on the branch both environments
    // share, or the spec proves different things in different places (it did — the
    // first version passed locally on vectors and failed in CI).
    await question.fill("liability shall not exceed fees paid");
    await ask.click();
    const first = page.locator(".ask-answer--refusal").first();
    await expect(first).toHaveText(REFUSAL_TEXT, { timeout: 20_000 });
    await expect(first).toHaveAttribute("data-state", "EVIDENCE_INSUFFICIENT");

    // Cause 2 — vocabulary the document cannot contain: nothing is retrieved and
    // the gate never opens (NO_EVIDENCE_RETRIEVED).
    await question.fill("Explain the zorbulated quixotic framblewitz stipulations");
    await ask.click();
    const refusals = page.locator(".ask-answer--refusal");
    await expect(refusals).toHaveCount(2, { timeout: 20_000 });
    await expect(refusals.nth(1)).toHaveText(REFUSAL_TEXT);
    await expect(refusals.nth(1)).toHaveAttribute("data-state", "NO_EVIDENCE_RETRIEVED");

    // r4, on the rendered page: different causes, one sentence. The data-state
    // attributes differ (they drive nothing visible but keep the DOM honest for
    // tests); the words the user reads do not.
    expect(await refusals.nth(0).innerText()).toBe(await refusals.nth(1).innerText());

    // Quiet surface, not an error: neither refusal wears the error banner.
    await expect(page.locator(".ask-turn .banner--error")).toHaveCount(0);

    // AI-03 item 16 at the composed-page level: no confidence figure anywhere.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
  });
});
