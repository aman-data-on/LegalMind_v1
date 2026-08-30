import { expect, test } from "@playwright/test";

import { apiPost, createAnalysedReview, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * Workspace slice 1 — the document pane and the cross-pane highlight, against the
 * real backend (PRODUCT_UX_ROADMAP §G: the risk slice).
 *
 * The property that matters: pointing at an evidence row — from the outline or
 * from a shared URL — scrolls to it, lights it, and moves focus to it. Everything
 * downstream (verdict click, citation click) reuses exactly this gesture.
 */

test.describe("the document pane", () => {
  test("renders the document as evidence rows under page markers, with readiness", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/workspace/${contractId}`);

    // The new shell, not the legacy chrome.
    await expect(page.locator(".ws-shell")).toBeVisible();
    await expect(page.locator(".topbar")).toHaveCount(0);

    const doc = page.locator('[data-region="document"]');
    await expect(doc.getByRole("heading", { name: "Document" })).toBeVisible();
    await expect(doc.locator(".ws-row").first()).toBeVisible();
    await expect(doc.locator(".ws-page__marker").first()).toContainText(/Page \d+|Unnumbered/);
    await expect(doc.locator(".ws-readiness")).toHaveAttribute(
      "data-readiness",
      /ready|lexical-only|not-indexed/,
    );
    // Verbatim text is set in the quote voice; nothing here says "confidence".
    await expect(doc.locator(".ws-row__text").first()).toBeVisible();
    expect((await page.content()).toLowerCase()).not.toContain("confidence");
  });

  test("the outline points at a clause: it lights, scrolls and takes focus", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/workspace/${contractId}`);
    const doc = page.locator('[data-region="document"]');
    await expect(doc.locator(".ws-row").first()).toBeVisible();

    const entries = doc.locator(".ws-outline button");
    test.skip((await entries.count()) === 0, "fixture document carries no clause numbering");

    const last = entries.last();
    await last.click();
    const lit = doc.locator(".ws-row--lit");
    await expect(lit).toHaveCount(1);
    await expect(lit).toBeFocused();
    await expect(last).toHaveAttribute("aria-current", "true");
    // The URL now carries the target, so the view can be shared.
    await expect(page).toHaveURL(/[?&]evidence=[0-9a-f-]{36}/);
  });

  test("a shared link lands on the exact row", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/workspace/${contractId}`);
    const doc = page.locator('[data-region="document"]');
    await expect(doc.locator(".ws-row").first()).toBeVisible();
    const targetId = await doc.locator(".ws-row").last().getAttribute("data-evidence-id");

    await page.goto(`/workspace/${contractId}?evidence=${targetId}`);
    const lit = doc.locator(".ws-row--lit");
    await expect(lit).toHaveAttribute("data-evidence-id", targetId!);
    await expect(lit).toBeFocused();
  });

  test("a contract with no upload says so and offers the upload, nothing fake", async ({
    page,
  }) => {
    const created = await apiPost(page, "/contracts", {
      name: `Bare ${Date.now()}`,
      contract_type: "MSA",
    });
    const contract = (await created.json()).data;
    await page.goto(`/workspace/${contract.id}`);
    await expect(page.getByRole("heading", { name: "No document uploaded yet." })).toBeVisible();
    await expect(page.getByRole("link", { name: "Upload a document" })).toBeVisible();
    await expect(page.locator('[data-region="document"]')).toHaveCount(0);
  });

  test("someone else's contract reads exactly like a nonexistent one", async ({
    page,
    browser,
  }) => {
    // Counsel builds a contract the owner cannot see.
    const counsel = await browser.newContext({ storageState: storageStatePath("counsel") });
    const other = await counsel.newPage();
    const created = await apiPost(other, "/contracts", {
      name: `Theirs ${Date.now()}`,
      contract_type: "MSA",
    });
    const theirs = (await created.json()).data.id;
    await counsel.close();

    await page.goto(`/workspace/${theirs}`);
    await expect(page.getByRole("heading", { name: "Not found." })).toBeVisible();
    const stolen = await page.locator(".ws-state").innerText();

    await page.goto(`/workspace/00000000-0000-4000-8000-000000000000`);
    await expect(page.getByRole("heading", { name: "Not found." })).toBeVisible();
    const ghost = await page.locator(".ws-state").innerText();
    expect(stolen).toBe(ghost);
    expect(stolen.toLowerCase()).not.toContain("access");
  });
});

test.describe("collapse behavior", () => {
  test("narrow viewports keep every region reachable as a tab", async ({ page }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.setViewportSize({ width: 800, height: 900 });
    await page.goto(`/workspace/${contractId}`);

    const tabs = page.getByRole("tab");
    await expect(tabs).toHaveCount(3);
    await expect(page.getByRole("tab", { name: "Document" })).toBeVisible();

    await page.getByRole("tab", { name: "Ask" }).click();
    await expect(page.locator('[data-region="ask"]')).toBeVisible();
    await expect(page.locator('[data-region="document"]')).toHaveCount(0);

    // Arrow keys move between tabs — the collapsed state is keyboard-operable.
    await page.getByRole("tab", { name: "Ask" }).focus();
    await page.keyboard.press("ArrowLeft");
    await expect(page.getByRole("tab", { name: "Findings" })).toBeFocused();
    await expect(page.locator('[data-region="findings"]')).toBeVisible();
  });

  test("the skip link is first in the tab order and lands on the content", async ({
    page,
  }) => {
    const { contractId } = await createAnalysedReview(page);
    await page.goto(`/workspace/${contractId}`);
    await expect(page.locator(".ws-shell")).toBeVisible();

    // First tabbable element in DOM order is the skip link — headless Chromium
    // does not move focus off <body> on the very first synthetic Tab, so the tab
    // order is asserted structurally and the link's behavior is exercised directly.
    const first = page.locator('a[href], button, [tabindex]:not([tabindex="-1"])').first();
    await expect(first).toHaveClass(/ws-skip/);

    const skip = page.getByRole("link", { name: "Skip to content" });
    await skip.focus();
    await expect(skip).toBeFocused();
    await skip.press("Enter");
    await expect(page).toHaveURL(/#ws-main$/);
    await expect(page.locator("#ws-main")).toBeFocused();
  });
});
