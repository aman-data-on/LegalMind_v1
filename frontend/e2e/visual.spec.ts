import { expect, test } from "@playwright/test";

import { apiPost, createAnalysedReview, storageStatePath } from "./support";

/**
 * Design QA — visual regression baselines (Phase 4/7 hardening, 2026-08-27).
 *
 * Runs ONLY under `npm run design-qa` (DESIGN_QA=1). Deliberately not part of the
 * default e2e run: the default suite's specs create data in a shared database, so
 * a screenshot's row counts would depend on spec ordering and grow with the
 * suite. Under design-qa the database is freshly bootstrapped and only this file
 * runs, so every page below renders exactly the same content every time.
 *
 * Threshold: 0.1% of pixels (maxDiffPixelRatio 0.001). Volatile content — ids in
 * headings, snapshot ids, dates — is masked rather than excluded, so a layout
 * regression under a mask's neighborhood still fails.
 *
 * Baselines are Linux/Chromium renderings (this repo's CI runner and the
 * Playwright-pinned browser). Regenerate deliberately with
 * `npm run design-qa -- --update-snapshots` and review the image diff like any
 * other diff.
 */

const SHOT = {
  maxDiffPixelRatio: 0.001,
  animations: "disabled" as const,
};

test.use({
  viewport: { width: 1280, height: 900 },
  colorScheme: "light",
  reducedMotion: "reduce",
});

test.describe("signed out", () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test("login page", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await page.goto("/login");
    await expect(page.getByLabel("Work email")).toBeVisible();
    await expect(page).toHaveScreenshot("login.png", SHOT);
  });
});

test.describe("signed in (counsel)", () => {
  test.use({ storageState: storageStatePath("counsel") });

  test("reviews list — empty state", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    // First spec in this file to touch reviews: under design-qa the database is
    // fresh, so this state is genuinely empty, not accidentally empty.
    await page.goto("/reviews");
    await expect(page.getByText("No reviews.")).toBeVisible();
    await expect(page).toHaveScreenshot("reviews-empty.png", SHOT);
  });

  test("review detail — findings, evaluations, decision panel", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const { reviewId } = await createAnalysedReview(page);
    await page.goto(`/reviews/${reviewId}`);
    await expect(page.locator("article.finding").first()).toBeVisible();
    await expect(page).toHaveScreenshot("review-detail.png", {
      ...SHOT,
      fullPage: true,
      // Ids and snapshot references differ every run; the layout around them
      // must not.
      mask: [page.locator("h1"), page.locator(".page-meta")],
    });
  });

  test("workspace — document pane, slice 1", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/workspace/${contractId}`);
    await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
    await expect(page).toHaveScreenshot("workspace.png", {
      ...SHOT,
      // The contract name carries a timestamp; the layout around it must not move.
      mask: [page.locator(".ws-context h1")],
    });
  });

  test("contract page — upload surface and Ask panel", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    const created = await apiPost(page, "/contracts", {
      name: `Visual baseline ${Date.now()}`,
      contract_type: "MSA",
    });
    const contract = (await created.json()).data;
    await page.goto(`/contracts/${contract.id}`);
    await expect(page.getByRole("heading", { name: "Ask about this document" })).toBeVisible();
    await expect(page).toHaveScreenshot("contract.png", {
      ...SHOT,
      fullPage: true,
      mask: [page.locator("h1")],
    });
  });
});

test.describe("signed in (admin)", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("admin — users and roles", async ({ page }) => {
    test.skip(!process.env.DESIGN_QA, "visual baselines run via npm run design-qa");
    await page.goto("/admin");
    await expect(page.locator("table").first()).toBeVisible();
    await expect(page).toHaveScreenshot("admin.png", {
      ...SHOT,
      fullPage: true,
      // Bootstrap account rows are fixed; their creation dates are today's.
      mask: [page.getByText(/20\d\d-\d\d-\d\d/)],
    });
  });
});
