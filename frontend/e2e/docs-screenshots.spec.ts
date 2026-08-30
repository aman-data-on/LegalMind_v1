import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { createAnalysedReview, storageStatePath } from "./support";

/**
 * Captures the illustration screenshots for docs/design/UI_PATTERNS.md.
 *
 * Not a test suite in the assertion sense — a reproducible way to regenerate the
 * documentation images from the real application with the STRUCTURAL fixture, so
 * the docs never carry a hand-mocked or stale picture. Gated behind DOCS_SHOTS=1
 * and skipped everywhere else.
 *
 * Everything captured is synthetic fixture data (rule 21 / locked 54.6: no real
 * legal material, and none exists in the e2e database to leak).
 */

const ASSETS = join(__dirname, "..", "..", "docs", "design", "assets");

test.describe("documentation screenshots", () => {
  test.describe("confidential omission — authorized view", () => {
    test.use({ storageState: storageStatePath("counsel") });

    test("counsel sees the rule outcome", async ({ page }) => {
      test.skip(!process.env.DOCS_SHOTS, "run with DOCS_SHOTS=1 to regenerate docs images");
      mkdirSync(ASSETS, { recursive: true });
      const { reviewId } = await createAnalysedReview(page);
      await page.goto(`/reviews/${reviewId}`);
      const evaluation = page.locator("li.evaluation").first();
      await expect(evaluation).toBeVisible();
      await evaluation.screenshot({
        path: join(ASSETS, "omission-legal-view.png"),
      });
    });
  });

  test.describe("confidential omission — ordinary view", () => {
    test.use({ storageState: storageStatePath("owner") });

    test("an ordinary user's evaluation row is simply shorter", async ({ page }) => {
      test.skip(!process.env.DOCS_SHOTS, "run with DOCS_SHOTS=1 to regenerate docs images");
      mkdirSync(ASSETS, { recursive: true });
      const { reviewId } = await createAnalysedReview(page);
      await page.goto(`/reviews/${reviewId}`);
      const evaluation = page.locator("li.evaluation").first();
      await expect(evaluation).toBeVisible();
      // LEGAL-02 / 52.4: no lock icon, no placeholder — the field is absent.
      await expect(evaluation.locator(".outcome")).toHaveCount(0);
      await evaluation.screenshot({
        path: join(ASSETS, "omission-user-view.png"),
      });
    });
  });

  test.describe("the refusal state", () => {
    test.use({ storageState: storageStatePath("owner") });

    test("a refusal renders quietly with the identical wording", async ({ page }) => {
      test.skip(!process.env.DOCS_SHOTS, "run with DOCS_SHOTS=1 to regenerate docs images");
      mkdirSync(ASSETS, { recursive: true });
      const { contractId } = await createAnalysedReview(page, { analyse: false });
      await page.goto(`/contracts/${contractId}`);
      const ask = page.getByPlaceholder("What does this document say about…");
      await ask.fill("What is the moon made of?");
      await page.getByRole("button", { name: "Ask" }).click();
      const answer = page.locator(".ask-answer--refusal").first();
      await expect(answer).toContainText("Information not found");
      await page.locator(".ask-turn").first().screenshot({
        path: join(ASSETS, "refusal-state.png"),
      });
    });
  });
});
