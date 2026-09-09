import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * Version comparison — locked 33.15, owner decision 2026-09-04 (#3).
 *
 * The fixture uploads the SAME document twice, so every numbered clause is
 * UNCHANGED. That is the useful case to pin: a comparison whose honest answer
 * is "nothing differs" must SAY so rather than render an empty panel, and the
 * unchanged clauses must still be reachable — "did the rest of the document stay
 * put?" is the second question every reader asks.
 *
 * The last assertion is the 33.16 boundary, on the screen rather than in the
 * payload: the comparison may report what the text does and must never imply
 * acceptability. So no verdict word appears in the panel, whatever the engine
 * concluded about the same clauses one tab away.
 */
test("comparison reports clause-level changes and never a verdict", async ({ page }) => {
  const f = fixture();
  // No analysis needed: identical bytes make every clause UNCHANGED, and an
  // unchanged clause quotes no Finding by design.
  const v1 = await createAnalysedReview(page, { analyse: false });

  await page.goto(`/dashboard?id=${v1.contractId}`);
  // With one version there is nothing to compare against, so no control.
  await expect(page.getByRole("button", { name: "Compare versions" })).toHaveCount(0);

  await page.getByRole("button", { name: "Upload a revised version" }).click();
  await page.setInputFiles('input[type="file"]', f.document.path);
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(page.locator(".ws-version select option")).toHaveCount(2, { timeout: 20_000 });

  await page.getByRole("button", { name: "Compare versions" }).click();
  const panel = page.locator(".ws-compare");
  await expect(panel).toBeVisible();
  await expect(panel.getByText("Comparing…")).toHaveCount(0, { timeout: 20_000 });

  // Same bytes twice: nothing changed, and the panel says that in words.
  await expect(panel.locator(".ws-compare__counts")).toContainText("Nothing changed");
  await expect(panel.getByText("No numbered clause differs")).toBeVisible();

  // The unchanged clauses are one click away, not dropped.
  const reveal = panel.getByRole("button", { name: /Show \d+ unchanged clause/ });
  await expect(reveal).toBeVisible();
  await reveal.click();
  const row = panel.locator(".ws-compare__row").first();
  await expect(row).toBeVisible();
  await expect(row.locator(".ws-compare__status")).toHaveText("unchanged");
  // An unchanged clause shows its wording ONCE: there is no superseded reading
  // to put beneath it, and printing the same text twice would invent a change.
  await expect(row.locator(".ws-compare__side")).toHaveCount(1);
  await expect(panel.getByText("matched on the document")).toBeVisible();

  // 33.16 — the comparison is not a legal position.
  await expect(panel).not.toContainText(/acceptable|unacceptable|approved|rejected|risk/i);
});
