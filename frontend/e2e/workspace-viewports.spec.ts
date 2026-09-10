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

import { createAnalysedReview, openFindingsTab, showDocument, storageStatePath } from "./support";

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

    test("document hidden: the Summary uses the width; Ask takes the column while open", async ({ page }) => {
      const { contractId } = await createAnalysedReview(page);
      await page.goto(`/dashboard?id=${contractId}`);
      await showDocument(page);
      await page.locator(".ws-side__doctoggle").click();
      await expect(page.locator(".ws-pane--document")).toBeHidden();
      const analysis = await width(page, ".ws-analysis");
      // At least 70% of the viewport up to the 88rem measure — no 1024px strip
      // in the middle of a 1920px screen.
      expect(analysis).toBeGreaterThanOrEqual(Math.min(viewport.width * 0.7, 1380));
      const tops = await Promise.all((await page.locator(".ws-tile").all()).map(async (t) => (await t.boundingBox())!.y));
      expect(new Set(tops.map((y) => Math.round(y))).size).toBe(1);

      // Ask: open → the whole column, the tabs still there; a tab click closes it.
      await page.getByRole("button", { name: /Ask about this document/i }).click();
      const panel = page.locator(".ws-dock__panel");
      await expect(panel).toBeVisible();
      await expect(page.locator(".ws-side__panel:visible")).toHaveCount(0);
      const panelBox = (await panel.boundingBox())!;
      const sideBox = (await page.locator(".ws-pane--side").boundingBox())!;
      expect(panelBox.height).toBeGreaterThanOrEqual(sideBox.height * 0.7);
      await expect(page.getByRole("button", { name: "Close Ask" })).toBeVisible();
      await openFindingsTab(page);
      await expect(panel).toBeHidden();
      await expect(page.locator("#ws-pane-findings")).toBeVisible();
      // And the launcher is the way back in.
      await expect(page.getByRole("button", { name: /Ask about this document/i })).toBeVisible();
    });
  });
}
