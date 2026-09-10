/**
 * The three-pane workspace — owner instruction, 2026-09-09.
 *
 * "LEFT = collapsible Document Contents / Index, CENTER = Document Viewer,
 * RIGHT = Findings / Ask panel. The document is the primary reference surface."
 * That amends `AM-50` r5 (findings-primary) and supersedes DD-15 (a floating
 * Ask dock), both owner-approved after the ids were named.
 *
 * Asserted in a browser because every claim here is geometric — which pane is
 * left of which, and whether an open panel covers something. The static suite
 * can see the markup but not the layout, and the two defects this replaces were
 * both invisible in markup: a container query stacked the index and squeezed its
 * list to ~200px, and the Ask panel floated over the findings.
 */

import { expect, test } from "@playwright/test";

import {
  createAnalysedReview,
  fixture,
  openFindingsTab,
  openUploadPanel,
  showDocument,
  storageStatePath,
} from "./support";

test.use({ storageState: storageStatePath("owner") });

/** Left edge of a locator, for ordering assertions. */
async function left(page: import("@playwright/test").Page, selector: string): Promise<number> {
  const box = await page.locator(selector).first().boundingBox();
  expect(box, `${selector} should be laid out`).not.toBeNull();
  return box!.x;
}

test.describe("the three panes", () => {
  test.use({
    storageState: storageStatePath("owner"),
    viewport: { width: 1600, height: 900 },
  });

  test("read left to right: contents, document, findings — and Ask docks without covering them", async ({
    page,
  }) => {
    const f = fixture();
    await page.goto("/dashboard");
    await openUploadPanel(page);
    await page.setInputFiles('input[type="file"]', f.document.path);
    await page.waitForURL(/\/dashboard\?id=[0-9a-f-]{36}$/, { timeout: 45_000 });

    /* The document opens WITH the workspace now — it is the primary reference
       surface, not a disclosure. `showDocument` is idempotent and returns early
       when the toggle already reads pressed, so this asserts the default rather
       than creating it. */
    const toggle = page.locator(".ws-side__doctoggle");
    await expect(toggle).toHaveAttribute("aria-pressed", "true");
    await showDocument(page);

    // ---- order --------------------------------------------------------
    await expect(page.locator("#ws-contents")).toBeVisible();
    const contentsX = await left(page, "#ws-contents");
    const paperX = await left(page, ".ws-doccard");
    const findingsX = await left(page, ".ws-pane--side");
    expect(contentsX).toBeLessThan(paperX);
    expect(paperX).toBeLessThan(findingsX);

    // ---- the index is a real index, not an empty box ------------------
    /* The fixture's own two headings. Nothing here is placeholder content: if
       the parser records no numbering and the text states none, the panel says
       so instead of inventing entries. */
    const entries = page.locator(".ws-outline__list .ws-outline__jump");
    await expect(entries.first()).toBeVisible();
    expect(await entries.count()).toBeGreaterThan(1);
    await expect(page.locator(".ws-outline__list")).toContainText("Limitation of Liability");

    /* The list must have real height — the defect was a 200px card whose list
       got ~55px of it. */
    const listBox = await page.locator(".ws-outline__list").boundingBox();
    expect(listBox!.height).toBeGreaterThan(120);

    // ---- clicking an entry moves the document ------------------------
    const entry = entries.filter({ hasText: "Limitation of Liability" }).first();
    await entry.click();
    // The clicked entry marks itself current, and the row it addresses lights up
    // in the paper — the same pointing gesture every citation uses.
    await expect(entry).toHaveAttribute("aria-current", "true");
    await expect(page.locator(".ws-row--lit").first()).toBeVisible();
    await expect(page.locator(".ws-row--lit").first()).toContainText("Limitation of Liability");

    // ---- collapse and reopen -----------------------------------------
    await page.getByRole("button", { name: "Hide contents" }).click();
    await expect(page.locator("#ws-contents")).toBeHidden();
    const rail = page.getByRole("button", { name: "Show contents" });
    await expect(rail).toBeVisible();
    // The paper gains the space the index gave up.
    expect(await left(page, ".ws-doccard")).toBeLessThan(paperX);
    await rail.click();
    await expect(page.locator("#ws-contents")).toBeVisible();

    // ---- Ask is DOCKED, and covers nothing ---------------------------
    await openFindingsTab(page);
    const finding = page.locator("article[data-finding-id]").first();
    await expect(finding).toBeVisible();

    await page.getByRole("button", { name: /Ask about this document/i }).click();
    const panel = page.locator(".ws-dock__panel");
    await expect(panel).toBeVisible();
    // Its own header carries the collapse control, visibly.
    await expect(page.getByRole("button", { name: "Close Ask" })).toBeVisible();

    /* THE POINT OF THIS SPEC. A docked panel shares the column; a floating one
       sits on top of it. So the panel's box must not intersect the document's —
       which is also WCAG 2.2 AA 2.4.11, the criterion that names chat widgets. */
    const panelBox = (await panel.boundingBox())!;
    const paperBox = (await page.locator(".ws-doccard").boundingBox())!;
    expect(panelBox.x).toBeGreaterThanOrEqual(paperBox.x + paperBox.width - 1);

    /* Open, Ask IS the column (owner, 2026-09-10): the findings panel steps
       aside rather than sharing a squeezed strip with it, the tab strip stays
       above, and choosing a tab brings the findings back and closes Ask. */
    await expect(page.locator(".ws-side__panel:visible")).toHaveCount(0);
    const sideBox = (await page.locator(".ws-pane--side").boundingBox())!;
    expect(panelBox.height).toBeGreaterThan(sideBox.height * 0.7);
    await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();

    /* Both icon-only controls must actually be visible at their stated size.
       The owner's screenshot showed the Ask close control as a barely-there
       dot, and "There is no obvious close/collapse icon" was the first item on
       the list this work answers. */
    for (const name of ["Close Ask", "Hide contents"]) {
      const icon = page.getByRole("button", { name }).locator("svg");
      const box = (await icon.boundingBox())!;
      expect(box.width, `${name} icon width`).toBeGreaterThanOrEqual(14);
      expect(box.height, `${name} icon height`).toBeGreaterThanOrEqual(14);
    }

    // Closing returns the persistent launcher, so it can be reopened.
    await page.getByRole("button", { name: "Close Ask" }).click();
    await expect(panel).toBeHidden();
    await expect(page.getByRole("button", { name: /Ask about this document/i })).toBeVisible();
  });
});

/**
 * "The layout must adapt cleanly to laptop, desktop and smaller screens.
 * Panels should collapse/dock intelligently rather than overlap content."
 *
 * Three real widths rather than a sweep: a large desktop where all three panes
 * fit side by side, a 13" laptop, and a width below the 900px point where the
 * workspace becomes one region at a time. The invariant at every one of them is
 * that the page itself never scrolls sideways — the panes own their scrolling,
 * and a horizontal page scrollbar is the signature of a pane that refused to
 * give ground.
 */
for (const { label, width, height, threePane } of [
  { label: "desktop", width: 1920, height: 1080, threePane: true },
  { label: "laptop", width: 1280, height: 800, threePane: true },
  { label: "small", width: 820, height: 900, threePane: false },
]) {
  test.describe(`${label} — ${width}×${height}`, () => {
    test.use({ storageState: storageStatePath("owner"), viewport: { width, height } });

    test("adapts without overlapping or scrolling the page sideways", async ({ page }) => {
      const { contractId } = await createAnalysedReview(page, { analyse: false });
      await page.goto(`/dashboard?id=${contractId}`);
      await showDocument(page);
      await expect(page.locator('[data-region="document"]').first()).toBeVisible();

      const scrolled = await page.evaluate(() => ({
        x: document.documentElement.scrollWidth > window.innerWidth + 1,
        y: document.documentElement.scrollHeight > window.innerHeight + 1,
      }));
      expect(scrolled.x, "the page must never scroll sideways").toBeFalsy();
      expect(scrolled.y, "the panes own the scrolling, not the page").toBeFalsy();

      if (threePane) {
        /* Both columns are on screen together, and the document is the wider of
           the two — it is the primary reference surface. */
        const doc = (await page.locator(".ws-pane--document").boundingBox())!;
        const side = (await page.locator(".ws-pane--side").boundingBox())!;
        expect(doc.x + doc.width).toBeLessThanOrEqual(side.x + 1);
        expect(doc.width).toBeGreaterThan(side.width);
      } else {
        /* Below 900px there is one region at a time as top tabs, so nothing can
           overlap: the side card is not laid out beside anything. */
        await expect(page.locator(".ws-workspace--one")).toBeVisible();
        await expect(page.getByRole("tab", { name: "Findings" })).toBeVisible();
      }

      await page.screenshot({
        path: `test-results/panes-${label}.png`,
        fullPage: false,
      });
    });
  });
}
