/**
 * The workspace at real laptop and desktop sizes (owner, 2026-09-10).
 *
 * "Do not let panels become extremely narrow… When Document is shown,
 * Summary/Findings must NOT become squeezed into vertically wrapped text…
 * When Document is hidden, Summary/Findings should use the available space."
 * Every claim is geometric, so it is asserted in a browser, at the three
 * viewports a reviewer actually has.
 */
import { expect, test, type Page } from "@playwright/test";

import { askOpener, createAnalysedReview, openFindingsTab, showDocument, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

async function width(page: Page, selector: string): Promise<number> {
  const box = await page.locator(selector).first().boundingBox();
  expect(box, `${selector} should be laid out`).not.toBeNull();
  return box!.width;
}

for (const viewport of [{ width: 1366, height: 768 }, { width: 1536, height: 864 }, { width: 1920, height: 1080 }]) {
  test.describe(`${viewport.width}×${viewport.height}`, () => {
    test.use({ viewport });

    test("document shown: three usable panes, no letter-wrapped tiles", async ({ page }) => {
      const { contractId } = await createAnalysedReview(page);
      await page.goto(`/dashboard?id=${contractId}`);
      await showDocument(page);
      await expect(page.locator(".ws-tiles")).toBeVisible();

      // The side card never drops under its floor, and the document keeps the
      // largest share.
      const side = await width(page, ".ws-pane--side");
      const paper = await width(page, ".ws-doccard");
      const contents = await width(page, "#ws-contents");
      expect(side).toBeGreaterThanOrEqual(398);
      expect(contents).toBeGreaterThanOrEqual(218);
      expect(paper).toBeGreaterThan(side);
      expect(paper).toBeGreaterThanOrEqual(520);

      // Three tiles across, each label at most two lines — never one letter per line.
      const labels = page.locator(".ws-tile__label");
      expect(await labels.count()).toBe(3);
      for (const label of await labels.all()) {
        const box = (await label.boundingBox())!;
        expect(box.height, `"${await label.innerText()}" wrapped too far`).toBeLessThanOrEqual(36);
      }
      const tiles = await page.locator(".ws-tile").all();
      const tops = await Promise.all(tiles.map(async (t) => (await t.boundingBox())!.y));
      expect(new Set(tops.map((y) => Math.round(y))).size).toBe(1);

      // The Contents prints the document's numbers, never an added "§".
      await expect(page.locator(".ws-outline__list")).not.toContainText("§");
      // Clicking an entry lights the passage.
      await page.locator(".ws-outline__list .ws-outline__jump").first().click();
      await expect(page.locator(".ws-row--lit").first()).toBeVisible();
      await expect(page).toHaveURL(/evidence=/);
    });

    test("document hidden: the Summary uses the width; Ask opens from its row", async ({ page }) => {
      // From 1680px Ask is its own column (owner, 2026-10-08); below, the third tab.
      const askColumn = viewport.width >= 1680;
      const { contractId } = await createAnalysedReview(page);
      await page.goto(`/dashboard?id=${contractId}`);
      await showDocument(page);
      await page.locator(".ws-side__doctoggle").click();
      await expect(page.locator(".ws-pane--document")).toBeHidden();
      const analysis = await width(page, ".ws-analysis");
      // At least 70% of what Ask leaves free, up to the 88rem measure — no 1024px
      // strip in the middle of a 1920px screen.
      const free = viewport.width - (askColumn ? await width(page, ".ws-pane--ask") : 0);
      expect(analysis).toBeGreaterThanOrEqual(Math.min(free * 0.7, 1380));
      // Wait for a tile before measuring tiles. `.all()` returns what matches NOW, so
      // without this the next line can measure an empty list and assert a Set size of
      // 0 against 1 — which is what it did at 1536×864 on 2026-09-16 while passing at
      // 1366×768 and 1920×1080 in the same run. The sibling test above already waits
      // on `.ws-tiles`; this waits on the tile itself, which is what is measured.
      await expect(page.locator(".ws-tile").first()).toBeVisible();
      const tops = await Promise.all((await page.locator(".ws-tile").all()).map(async (t) => (await t.boundingBox())!.y));
      expect(new Set(tops.map((y) => Math.round(y))).size).toBe(1);

      const panel = page.locator(".ws-dock__panel");
      if (askColumn) {
        // Its own column: open beside the Summary, covering nothing; "Ask" in the
        // row folds it away and brings it back.
        await expect(panel).toBeVisible();
        await expect(page.locator("#ws-pane-analysis")).toBeVisible();
        await askOpener(page).click();
        await expect(page.locator(".ws-pane--ask")).toBeHidden();
        await askOpener(page).click();
        await expect(panel).toBeVisible();
        return;
      }
      // The third tab: open → the whole column, the tabs still there; a tab click closes it.
      await askOpener(page).click();
      await expect(panel).toBeVisible();
      await expect(page.locator(".ws-side__panel:visible")).toHaveCount(0);
      const panelBox = (await panel.boundingBox())!;
      const sideBox = (await page.locator(".ws-pane--side").boundingBox())!;
      expect(panelBox.height).toBeGreaterThanOrEqual(sideBox.height * 0.7);
      await expect(page.getByRole("button", { name: "Close Ask" })).toBeVisible();
      await openFindingsTab(page);
      await expect(panel).toBeHidden();
      await expect(page.locator("#ws-pane-findings")).toBeVisible();
      // And the Ask tab is the way back in.
      await expect(askOpener(page)).toBeVisible();
    });
  });
}
