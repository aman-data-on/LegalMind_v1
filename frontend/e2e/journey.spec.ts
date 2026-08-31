import { expect, test } from "@playwright/test";

import { apiPost, createAnalysedReview, fixture, snapshotId, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The complete user journeys of the 2026-08-31 product-intent clarification
 * (§23/§31), end to end against the real backend.
 *
 * Journey 1 — upload → analyze → report → findings → ask. Chat is available the
 * moment the document is analyzed and is NOT conditional on resolving anything:
 * the ask succeeds (with an honest refusal, since no generator credential
 * exists) while a DEVIATION finding still awaits a Legal Decision.
 *
 * Journey 2 — the revised version. Uploading v2 through the workspace creates a
 * REAL new version with its own analysis; v1's document text, findings and
 * report stay reachable exactly as they were (nothing is marked resolved by the
 * upload — rule 14), and the ask surface follows the latest version honestly.
 */

const REFUSAL_TEXT =
  "Information not found in the selected document. " +
  "The available material does not answer this question.";

test("journey: upload → analysis → report → findings → ask, with findings still open", async ({
  page,
}) => {
  const { contractId, reviewId } = await createAnalysedReview(page);

  // The report exists and speaks in counts.
  await page.goto(`/workspace/reviews/${reviewId}`);
  await expect(page.getByText(/awaits? a Legal Decision/)).toBeVisible();

  // The workspace shows the document, the finding — and Ask, all at once.
  await page.goto(`/workspace/${contractId}`);
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  const finding = page.locator("article[data-finding-id]").first();
  await expect(finding).toBeVisible();
  await expect(finding).toContainText("DEVIATION");

  // Chat, immediately — the open finding gates nothing (AM-25 r1).
  await page.getByLabel("Question").fill("Explain the zorbulated framblewitz stipulations");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".ws-ask__answer--refusal").first()).toHaveText(REFUSAL_TEXT, {
    timeout: 20_000,
  });
  // …and the finding is still open beside it. Nothing was auto-resolved.
  await expect(finding).toContainText("Decision required");
});

test("journey: a revised version is a real new analysis; v1 stays historically valid", async ({
  page,
}) => {
  const f = fixture();
  const v1 = await createAnalysedReview(page);

  // Upload the revision through the workspace's own control.
  await page.goto(`/workspace/${v1.contractId}`);
  await page.getByRole("button", { name: "Upload a revised version" }).click();
  await expect(page.getByText("becomes a NEW version")).toBeVisible();
  await page.setInputFiles('input[type="file"]', f.document.path);
  await page.getByRole("button", { name: "Upload", exact: true }).click();

  // The workspace lands on v2; the picker knows both versions.
  const picker = page.locator(".ws-version select");
  await expect(picker).toBeVisible();
  await expect(picker.locator("option")).toHaveCount(2);
  await expect(picker).toHaveValue(/^(?!$)/); // a concrete id
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();

  // v2 gets its OWN analysis — a genuinely new Review, not a status flip on v1.
  const contract = (await (await page.request.get(`/api/v1/contracts/${v1.contractId}`)).json()).data;
  expect(contract.document_versions.length).toBe(2);
  const v2Id = contract.document_versions[0].id;
  const created = await apiPost(page, "/reviews", {
    document_version_id: v2Id,
    configuration_snapshot_id: snapshotId(),
  });
  const review2 = (await created.json()).data;
  expect(review2.id).not.toBe(v1.reviewId);
  await apiPost(page, `/reviews/${review2.id}/analyze`, {});

  // v2's findings are its own.
  await page.reload();
  await expect(page.locator("article[data-finding-id]").first()).toBeVisible();

  // Switch to v1: its document text and ITS findings render; Ask defers to the
  // latest version, plainly, instead of misattributing answers.
  await picker.selectOption({ index: 1 });
  await expect(page).toHaveURL(/[?&]version=/);
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  await expect(page.locator("article[data-finding-id]").first()).toBeVisible();
  await expect(page.getByText("Ask answers about the latest version")).toBeVisible();

  // v1's Review and report remain exactly where they were.
  await page.goto(`/workspace/reviews/${v1.reviewId}`);
  await expect(page.getByText(/awaits? a Legal Decision/)).toBeVisible();

  // And the reviews queue lists both analyses.
  await page.goto("/workspace/reviews");
  await expect(page.locator(`tr[data-review-id="${v1.reviewId}"]`)).toBeVisible();
  await expect(page.locator(`tr[data-review-id="${review2.id}"]`)).toBeVisible();
});
