import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, storageStatePath } from "./support";

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
  // ENTIRELY through the UI (2026-08-31 UX correction): one upload act chains
  // create → version → current-standards snapshot → Review → analysis.
  const f = fixture();
  await page.goto("/workspace");
  await page.setInputFiles('input[type="file"]', f.document.path);
  await page.getByLabel(/^Document type/).selectOption("MSA");
  await page.getByRole("button", { name: "Upload and analyze" }).click();
  await page.waitForURL(/\/workspace\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  const contractId = page.url().match(/workspace\/([0-9a-f-]{36})/)![1];

  // The workspace shows the document, the finding — and Ask, all at once.
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  const finding = page.locator("article[data-finding-id]").first();
  await expect(finding).toBeVisible();
  await expect(finding).toContainText("DEVIATION");

  // The drill (2026-08-31 v2): the summary strip's counts are pressable
  // filters — category → finding → evidence without leaving the pane.
  const filters = page.locator(".ws-filter");
  await expect(filters.getByRole("button", { name: /^DEVIATION \(\d+\)$/ })).toBeVisible();
  await filters.getByRole("button", { name: /^DEVIATION/ }).click();
  await expect(finding).toBeVisible();
  // …and the drill ends in verbatim text: the cited excerpt sits beside the
  // finding, and its location button lights the passage in the document.
  await expect(finding.locator(".ws-evidence__quote").first()).toBeVisible();
  await finding.locator(".ws-evidence__loc").first().click();
  await expect(page.locator(".ws-row--lit")).toBeVisible();

  // Finding → Ask handoff: an EDITABLE draft lands in the input, nothing sends.
  await finding.getByRole("button", { name: "Ask about this" }).click();
  await expect(page.getByLabel("Question")).toHaveValue(/What does this document say about/);

  // Export — the analysis leaves as a real file (owner directive §30).
  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "PDF", exact: true }).click();
  expect((await downloaded).suggestedFilename()).toMatch(/analysis\.pdf$/);

  // Chat, immediately — the open finding gates nothing (AM-25 r1).
  await page.getByLabel("Question").fill("Explain the zorbulated framblewitz stipulations");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator(".ws-ask__answer--refusal").first()).toHaveText(REFUSAL_TEXT, {
    timeout: 20_000,
  });
  // …and the finding is still open beside it. Nothing was auto-resolved.
  await expect(finding).toContainText("Decision required");

  // The report exists and speaks in counts — reached from the Reviews queue.
  const listed = await page.request.get(`/api/v1/reviews?contract_id=${contractId}`);
  const reviewId = (await listed.json()).data[0].id;
  await page.goto(`/workspace/reviews/${reviewId}`);
  await expect(page.getByText(/awaits? a Legal Decision/)).toBeVisible();

  // And the Documents list now answers "what did analysis find".
  await page.goto("/workspace");
  const row = page.locator("tbody tr").filter({ has: page.locator(`a[href="/workspace/${contractId}"]`) });
  await expect(row.locator(".ws-cell-chips")).toContainText("DEVIATION");
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
  await expect(picker).toBeVisible({ timeout: 20_000 });
  await expect(picker.locator("option")).toHaveCount(2);
  await expect(picker).toHaveValue(/^(?!$)/); // a concrete id
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();

  // v2 got its OWN analysis IN THE FLOW (2026-08-31 v2: the revised upload
  // chains the same best-effort analysis as a first upload — one loop).
  await expect(page.locator("article[data-finding-id]").first()).toBeVisible({ timeout: 20_000 });
  const contract = (await (await page.request.get(`/api/v1/contracts/${v1.contractId}`)).json()).data;
  expect(contract.document_versions.length).toBe(2);
  const listed = await page.request.get(
    `/api/v1/reviews?contract_id=${v1.contractId}`);
  const reviewIds = (await listed.json()).data.map((r: { id: string }) => r.id);
  const review2 = { id: reviewIds.find((id: string) => id !== v1.reviewId)! };
  expect(review2.id).toBeTruthy();

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
