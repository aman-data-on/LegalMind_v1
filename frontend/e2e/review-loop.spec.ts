import { expect, test } from "@playwright/test";

import { createAnalysedReview, openFindingsTab, showDocument, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The review loop, both directions — 2026-09-05.
 *
 * Finding -> evidence already worked. Two things did not: following a citation
 * threw the reader out of the ORIGINAL document into the extracted text, and
 * from a clause there was no way back to what the analysis said about it. The
 * loop the reviewer actually works in is
 *
 *     finding -> exact evidence -> related finding(s) -> finding
 *
 * and it must close without losing the reader's place.
 */
test("a citation keeps the reader in the view they are reading", async ({ page }) => {
  const { contractId } = await createAnalysedReview(page);
  await page.goto(`/dashboard?id=${contractId}`);
  await showDocument(page);
  const doc = page.locator('[data-region="document"]');
  await expect(doc.locator(".ws-row").first()).toBeVisible();

  // The fixture is a .docx, so there is no Original view to be ejected from and
  // the text view is the only representation — the citation must still land.
  const targetId = await doc.locator(".ws-row").last().getAttribute("data-evidence-id");
  await page.goto(`/dashboard?id=${contractId}&evidence=${targetId}`);
  await expect(doc.locator(".ws-row--lit")).toHaveAttribute("data-evidence-id", targetId!);
  // Backward compatible: no transition happened, so no "back" affordance is
  // offered. An affordance that undoes nothing is noise.
  await expect(doc.locator(".ws-doccard__cited")).toHaveCount(0);
});

test("a clause carries the way back to the finding that cites it", async ({ page }) => {
  const { contractId } = await createAnalysedReview(page);
  await page.goto(`/dashboard?id=${contractId}`);
  await showDocument(page);
  const doc = page.locator('[data-region="document"]');

  // Reverse link: the clause the analysis cited names its finding.
  const link = doc.locator(".ws-row__findings button").first();
  await expect(link).toBeVisible({ timeout: 20_000 });
  // Named, not counted — the reader knows what they are opening.
  await expect(link).not.toHaveText(/^\d+ finding/);

  // LEGAL-02 on the new affordance. The `owner` account holds `finding.view`
  // and NOT `legal_position.view`, so the reverse link may name the
  // classification and the requirement — both already on the finding card —
  // and must carry no internal legal position: no rule outcome, no expected
  // value, no threshold. It adds no request and no field of its own; it is an
  // index over the list the server already redacted.
  await expect(link).not.toHaveText(/ACCEPTABLE|UNACCEPTABLE|APPROVAL_REQUIRED/);
  await expect(link).not.toHaveText(/expected|threshold|months of fees/i);

  await link.click();
  // It lands on the real card in the existing Findings area, focused.
  const card = page.locator("article[data-finding-id]");
  await expect(card.first()).toBeVisible();
  await expect(page.locator("article[data-finding-id]:focus")).toHaveCount(1);

  // And the forward direction still works from there — the loop closes.
  await openFindingsTab(page);
  const cite = page.locator(".ws-evidence__loc").first();
  if (await cite.count()) {
    await cite.click();
    await expect(doc.locator(".ws-row--lit")).toHaveCount(1);
  }
});

test("a clause with no finding offers no reverse link at all", async ({ page }) => {
  const { contractId } = await createAnalysedReview(page, { analyse: false });
  await page.goto(`/dashboard?id=${contractId}`);
  await showDocument(page);
  const doc = page.locator('[data-region="document"]');
  await expect(doc.locator(".ws-row").first()).toBeVisible();
  // No analysis has run, so nothing cites anything. The honest state is an
  // absent control, never a dead one.
  await expect(doc.locator(".ws-row__findings")).toHaveCount(0);
});
