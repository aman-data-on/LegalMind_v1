import { expect, test } from "@playwright/test";

/**
 * The retired application's URLs still answer — 2026-09-04.
 *
 * `/contracts`, `/reviews`, `/audit`, `/configuration` and `/admin` were a
 * complete second UI that kept answering long after the new one replaced it.
 * The pages are deleted; the addresses are not, because someone has them
 * bookmarked and a 404 is a worse answer than the screen that replaced them.
 *
 * This spec exists so a future change cannot quietly turn those bookmarks into
 * dead ends — including the query string, which is what makes
 * `/reviews?id=X` land on that Review's report rather than the queue.
 */
import { createAnalysedReview, storageStatePath } from "./support";
test.use({ storageState: storageStatePath("admin") });
test("the retired URLs land on the screens that replaced them", async ({ page }) => {
  const { reviewId, contractId } = await createAnalysedReview(page);
  for (const [from, expected] of [
    ["/contracts", "/dashboard"],
    [`/contracts?id=${contractId}`, `/dashboard?id=${contractId}`],
    ["/reviews", "/dashboard/reviews"],
    [`/reviews?id=${reviewId}`, `/dashboard/reviews?id=${reviewId}`],
    ["/audit", "/dashboard/admin/audit"],
    ["/configuration", "/dashboard/configuration"],
    ["/admin", "/dashboard/admin"],
  ] as const) {
    await page.goto(from);
    await expect(page).toHaveURL(new RegExp(expected.replace(/[?]/g, "\\?") + "$"));
    console.log(`  ${from}  ->  ${new URL(page.url()).pathname}${new URL(page.url()).search}`);
  }
});
