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
  const byId = `/contracts/${contractId}`;
  // [retired URL, the server's redirect, the screen the reader ends on]. The last two
  // differ where the screen moves on by itself: the contract page drops the carried-over
  // `?id=`, and the Reviews queue sends a reader without `legal.review` (this admin) to
  // Contracts once the session loads (reviews.spec.ts). Checking the screen against the
  // server's address raced that second move (CI 2026-11-24).
  for (const [from, redirect, screen] of [
    ["/dashboard", "/contracts", "/contracts"],
    [`/dashboard?id=${contractId}`, `${byId}?id=${contractId}`, byId],
    [`/contracts?id=${contractId}`, `${byId}?id=${contractId}`, byId],
    ["/reviews", "/dashboard/reviews", "/contracts"],
    [`/reviews?id=${reviewId}`, `/dashboard/reviews?id=${reviewId}`, `/dashboard/reviews?id=${reviewId}`],
    ["/audit", "/dashboard/admin/audit", "/dashboard/admin/audit"],
    ["/configuration", "/dashboard/configuration", "/dashboard/configuration"],
    ["/admin", "/dashboard/admin", "/dashboard/admin"],
  ] as const) {
    // `goto` resolves with the last redirect's response: the server's answer, before
    // any script on the page has run
    const landed = new URL((await page.goto(from))!.url());
    expect(landed.pathname + landed.search).toBe(redirect);
    await expect(page).toHaveURL(new RegExp(screen.replace(/[?]/g, "\\?") + "$"));
    console.log(`  ${from}  ->  ${landed.pathname}${landed.search}  ->  ${screen}`);
  }
});
