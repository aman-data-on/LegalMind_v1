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

// `AM-29` r4's constant, as `backend/legalmind/assist/state.py` declares it.
const REFUSAL_TEXT =
  "Information not found in the selected document. " +
  "The available material does not answer this question.";

test.describe("the reviews queue and the report", () => {
  test("an analysed review is queued, and its report shows counts — never a grade", async ({
    page,
  }) => {
    const { contractId, reviewId } = await createAnalysedReview(page);

    await page.goto("/documents/reviews");
    await expect(page.getByRole("heading", { name: "Reviews" })).toBeVisible();
    // The nav offers the new destinations and nothing legacy.
    await expect(page.locator('nav a[href="/documents/reviews"]')).toHaveAttribute(
      "aria-current",
      "page",
    );
    await expect(page.locator('a[href^="/contracts"], a[href^="/reviews"]')).toHaveCount(0);

    const row = page.locator(`tr[data-review-id="${reviewId}"]`);
    await expect(row).toBeVisible();
    // The document is named, not a bare id, and links into its workspace.
    await expect(row.getByRole("link", { name: /Structural MSA/ })).toHaveAttribute(
      "href",
      `/documents?id=${contractId}`,
    );

    await row.getByRole("link", { name: "Report" }).click();
    await expect(page).toHaveURL(`/documents/reviews?id=${reviewId}`);
    await expect(page.getByText("requirements in the snapshot produced Findings")).toBeVisible();
    await expect(page.getByText(/awaits? a Legal Decision/)).toBeVisible();
    await expect(page.getByText("never grades the document")).toBeVisible();

    // F-9/36.10 and AI-03 item 16, on the rendered page: counts exist, but no
    // confidence figure, no risk label, no verdict wording.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
    expect(body).not.toContain("risk");
    expect(body).not.toContain("verdict");

    await page.getByRole("link", { name: "Open the workspace" }).click();
    await expect(page).toHaveURL(`/documents?id=${contractId}`);
  });

  test("the status filter narrows through the API's allow-list", async ({ page }) => {
    await createAnalysedReview(page);
    await page.goto("/documents/reviews");
    await expect(page.locator("tbody tr").first()).toBeVisible();

    // The fixture pipeline never leaves a Review CANCELLED-adjacent: filtering to
    // CLOSED must yield the empty state, honestly worded — not an error.
    await page.getByRole("button", { name: "Closed" }).click();
    await expect(page.getByText("Nothing visible to your account has this status.")).toBeVisible();
    await page.getByRole("button", { name: "All" }).click();
    await expect(page.locator("tbody tr").first()).toBeVisible();
  });
});

test.describe("ask history", () => {
  test("an asked question is listed, and its transcript replays the identical refusal", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    const created = await apiPost(page, "/conversations", { contract_id: contractId });
    const conversationId = (await created.json()).data.id;
    // Vocabulary the document cannot contain — nothing retrieved, so the turn is
    // recorded as NO_EVIDENCE_RETRIEVED (the same cause the live ask spec pins).
    const question = "Explain the zorbulated quixotic framblewitz stipulations";
    const asked = await apiPost(page, `/conversations/${conversationId}/messages`, { question });
    expect(asked.status(), await asked.text()).toBe(201);

    await page.goto("/documents/ask");
    await expect(page.getByRole("heading", { name: "Ask history" })).toBeVisible();
    await page.getByRole("link", { name: question }).click();

    await expect(page).toHaveURL(`/documents/ask?id=${conversationId}`);
    await expect(page.locator(".ws-turn--user")).toContainText(question);
    const refusal = page.locator(".ws-ask__answer--refusal");
    await expect(refusal).toHaveText(REFUSAL_TEXT);
    await expect(refusal).toHaveAttribute("data-state", "NO_EVIDENCE_RETRIEVED");

    // The record is quiet, and no confidence figure exists anywhere on it.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
  });
});
