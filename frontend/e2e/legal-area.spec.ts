import { expect, test } from "@playwright/test";

import { createAnalysedReview, storageStatePath } from "./support";

// The legal function's own account: LEGAL_REVIEWER + LEGAL_DECISION_AUTHORITY + USER.
test.use({ storageState: storageStatePath("counsel") });

/**
 * Slice 6 — the Legal area, against the real backend.
 *
 * The property that matters: the queue is a pointer, not a court. A Finding
 * whose Evaluations await a decision appears here, and its row lands the
 * ruler in the document workspace — focused on that exact Finding, beside the
 * evidence and the decision form slice 2 built. The queue itself disposes of
 * nothing.
 */

test.describe("the Legal queue", () => {
  test("a decision-required finding queues, and its row lands focused on the finding card", async ({
    page,
  }) => {
    const { contractId, reviewId } = await createAnalysedReview(page);

    // The fixture's 24-month cap deviates from the 12-month standard; under the
    // zero-tolerance rule that is UNACCEPTABLE → DECISION_REQUIRED (D-3.5a).
    const listed = await page.request.get(
      `/api/v1/reviews/${reviewId}/findings?status=DECISION_REQUIRED`,
    );
    expect(listed.ok()).toBeTruthy();
    const findings = (await listed.json()).data;
    expect(findings.length).toBeGreaterThan(0);
    const finding = findings[0];

    await page.goto("/workspace/legal");
    await expect(page.getByRole("heading", { name: "Legal" })).toBeVisible();
    await expect(page.locator('nav a[href="/workspace/legal"]')).toHaveAttribute(
      "aria-current",
      "page",
    );

    const row = page.locator(`tr[data-finding-id="${finding.id}"]`);
    await expect(row).toBeVisible();
    // The requirement code as the API returns it — the STRUCTURAL e2e config
    // deliberately carries no real code (rule 21), so nothing is hardcoded here.
    await expect(row).toContainText(finding.requirement.code);
    await expect(row).toContainText("DEVIATION");

    // The deep link: workspace, `?finding=`, and focus ON the finding card —
    // the ruler arrives beside the evidence, not at the top of a long page.
    await row.getByRole("link", { name: new RegExp(finding.requirement.code) }).click();
    await expect(page).toHaveURL(`/workspace/${contractId}?finding=${finding.id}`);
    const card = page.locator(`article[data-finding-id="${finding.id}"]`);
    await expect(card).toBeVisible();
    await expect(card).toBeFocused();
    // The decision flow is present right there (counsel holds legal.decision).
    await expect(card.getByRole("button", { name: "Record decision" }).first()).toBeVisible();
  });

  test("no queue and no Legal nav for an account without legal.review", async ({
    browser,
  }) => {
    // `owner` holds USER only — the nav must not offer Legal, and the screen
    // itself must refuse with the restricted state, not an empty queue.
    const context = await browser.newContext({ storageState: storageStatePath("owner") });
    const page = await context.newPage();
    await page.goto("/workspace/legal");
    await expect(page.getByText("Access restricted")).toBeVisible();
    await expect(page.locator('nav a[href="/workspace/legal"]')).toHaveCount(0);
    await context.close();
  });
});
