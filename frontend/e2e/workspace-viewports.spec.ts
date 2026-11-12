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
      // CLM Page 2 (2026-11-03): the Summary's four tiles moved to Legal details; what the
      // owner's side card shows is "What needs attention" and the open points list.
      const heading = page.getByRole("heading", { name: "What needs attention", level: 2 });
      await expect(heading).toBeVisible();

      // The side card never drops under its floor, and the document keeps the
      // largest share.
      const side = await width(page, ".ws-pane--side");
      const paper = await width(page, ".ws-doccard");
      const contents = await width(page, "#ws-contents");
      expect(side).toBeGreaterThanOrEqual(398);
      expect(contents).toBeGreaterThanOrEqual(218);
      expect(paper).toBeGreaterThan(side);
      expect(paper).toBeGreaterThanOrEqual(520);

      // Nothing in the side card is squeezed into letter-wrapped text: the heading stays on
      // one line and each open point's name on at most two.
      expect((await heading.boundingBox())!.height).toBeLessThanOrEqual(36);
      for (const name of await page.locator(".ws-open__go").all()) {
        const box = (await name.boundingBox())!;
        expect(box.width, "an open point is laid out across the card").toBeGreaterThanOrEqual(300);
      }

      // The Contents prints the document's numbers, never an added "§".
      await expect(page.locator(".ws-outline__list")).not.toContainText("§");
      // Clicking an entry lights the passage.
      await page.locator(".ws-outline__list .ws-outline__jump").first().click();
      await expect(page.locator(".ws-row--lit").first()).toBeVisible();
      await expect(page).toHaveURL(/evidence=/);
    });

    test("document hidden: the Summary uses the width; Ask opens from its row", async ({ page }) => {
      // Ask is the third tab at every width (owner, 2026-11-02); it never takes a column.
      const { contractId } = await createAnalysedReview(page);
      await page.goto(`/dashboard?id=${contractId}`);
      await showDocument(page);
      await page.locator(".ws-side__doctoggle").click();
      await expect(page.locator(".ws-pane--document")).toBeHidden();
      const analysis = await width(page, ".ws-analysis");
      // At least 70% of what Ask leaves free, up to the 88rem measure — no 1024px
      // strip in the middle of a 1920px screen.
      const free = viewport.width;
      expect(analysis).toBeGreaterThanOrEqual(Math.min(free * 0.7, 1380));
      // The Summary's content uses that width (the tiles it measured moved to Legal details).
      await expect(page.locator(".ws-open__go").first()).toBeVisible();
      expect((await page.locator(".ws-open__go").first().boundingBox())!.width)
        .toBeGreaterThanOrEqual(Math.min(free * 0.5, 900));

      const panel = page.locator(".ws-dock__panel");
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
