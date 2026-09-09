import { expect, test } from "@playwright/test";

import { createAnalysedReview, storageStatePath, openFindingsTab } from "./support";

test.use({ storageState: storageStatePath("counsel") });

/**
 * Keyboard navigation on the Review screen — Phase 4 hardening (2026-08-27).
 *
 * The property that matters most here is a NEGATIVE one: no single keystroke may
 * complete a Legal Decision. `a`/`r` preselect a decision type and move focus to
 * the mandatory justification — they must never POST. A browser is the only place
 * that can prove a key press does not become a network request.
 */

/*
 * Ported to the workspace 2026-09-04, together with the FEATURE itself: the
 * shortcut layer existed only in the legacy Review screen, so this spec was the
 * one that could not be retargeted by changing a URL. `useWorkspaceShortcuts`
 * now owns the global keys and the finding card owns the decision keys, on the
 * bindings other professional tools use (j/k with n/p kept as aliases).
 *
 * The property that matters is unchanged and asserted below: no keystroke
 * records a Legal Decision.
 */
test.describe("workspace keyboard shortcuts", () => {
  test("? opens the help dialog; Escape closes it and returns focus", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    await expect(page.locator("article[data-finding-id]").first()).toBeVisible();

    await page.keyboard.press("?");
    const dialog = page.getByRole("dialog", { name: "Keyboard shortcuts" });
    await expect(dialog).toBeVisible();
    // The help renders from the same table the handlers use.
    await expect(dialog).toContainText("never submits");

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });

  test("n focuses the current finding; d jumps to its decision form", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    const card = page.locator("article[data-finding-id]").first();
    await expect(card).toBeVisible();

    await page.keyboard.press("n");
    await expect(card).toBeFocused();

    await page.keyboard.press("d");
    await expect(card.locator(".ws-decision__form select")).toBeFocused();
  });

  test("a and r prepare a decision and never record one", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await openFindingsTab(page);
    const card = page.locator("article[data-finding-id]").first();
    await expect(card).toBeVisible();

    let decisionPosts = 0;
    page.on("request", (request) => {
      if (request.url().includes("/decisions") && request.method() === "POST") {
        decisionPosts += 1;
      }
    });

    const select = card.locator(".ws-decision__form select");
    const justification = card.getByLabel("Justification (required)");

    // Prepare ACCEPT_DEVIATION: type preselected, justification focused.
    await page.keyboard.press("n");
    await page.keyboard.press("a");
    await expect(select).toHaveValue("ACCEPT_DEVIATION");
    await expect(justification).toBeFocused();

    // While typing, single-key shortcuts are inert — a justification containing
    // "r", "a" or "n" must not steer the form.
    await justification.fill("draft rationale with a, r and n in it");
    await expect(select).toHaveValue("ACCEPT_DEVIATION");

    // Blur the field, then prepare REJECT.
    await page.locator("h1").click();
    await page.keyboard.press("r");
    await expect(select).toHaveValue("REJECT");
    await expect(justification).toBeFocused();

    // The negative that matters: nothing was recorded by any of the above.
    expect(decisionPosts, "no keyboard path may POST a decision").toBe(0);
    await expect(page.locator(".ws-decision").locator("p", { hasText: /^Current:/ })).toHaveCount(0);
  });
});
