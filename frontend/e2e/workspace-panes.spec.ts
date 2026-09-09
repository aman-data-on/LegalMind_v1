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
    const entries = page.locator(".ws-outline__list button");
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

    /* And the findings keep a real share of the column. Measured on the
       SCROLLER, not on a card: a card's own box extends past its scroll clip,
       so a card assertion here would only measure how long the card is. */
    const findingsBox = (await page.locator(".ws-side__panel:not([hidden])").boundingBox())!;
    expect(findingsBox.y + findingsBox.height).toBeLessThanOrEqual(panelBox.y + 1);
    expect(findingsBox.height).toBeGreaterThan(panelBox.height * 0.6);

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
