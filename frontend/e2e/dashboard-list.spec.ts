import { expect, test } from "@playwright/test";

import { createAnalysedReview, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * Dashboard list view — the row action menu (⋯).
 *
 * Two regressions, both from the owner reporting the live site, both fixed
 * the same day (2026-09-03) and both pinned here because the second one was
 * only visible once the first was fixed.
 *
 * 1. CLIPPED. The menu originally rendered as an absolutely positioned child
 *    of `.ws-menu`, itself inside `.ws-docs__table` — which clips overflow
 *    for its own reasons (the horizontal scroller; `overflow: hidden` on the
 *    index card variant). A menu opened on any row was cut off at the
 *    table's edge instead of floating above the page.
 *
 * 2. SEE-THROUGH. Fixed by portaling the menu out of the table — but the
 *    first fix portaled into `document.body`, which sits OUTSIDE `.ws`, the
 *    class every design token in this app is scoped to (`--ws-surface`,
 *    `--ws-z-dialog`, `--ws-radius`, all of it — deliberately, so this
 *    stylesheet and the legacy one never fight over `:root`). Outside `.ws`,
 *    `z-index: var(--ws-z-dialog)` fell back to `auto` and `background:
 *    var(--ws-surface)` fell back to transparent. The menu still correctly
 *    OCCLUDED clicks (DOM order alone put it last, so hit-testing found it
 *    first) — but with no opaque background behind that, the row underneath
 *    visually painted straight through it. The owner's second screenshot,
 *    still showing the row below bleeding through the menu, was this.
 *
 * The real fix portals into the `.ws` element itself (see `menuPortalTarget`
 * in dashboard/page.tsx) — escaping the table's clipping ancestor while
 * keeping every design token, and widens the menu to the row's own Action
 * `<td>` width so it fully covers whatever it ends up floating over.
 */
test("the row action menu escapes the table's clipping ancestor and is fully usable", async ({
  page,
}) => {
  await createAnalysedReview(page);
  await page.goto("/dashboard");

  const toggle = page.getByRole("button", { name: /More actions for/ }).first();
  await toggle.scrollIntoViewIfNeeded();
  await toggle.click();

  const menu = page.locator(".ws-menu__list");
  await expect(menu).toBeVisible();

  // Regression 1: before the fix, this node's parent was `.ws-menu` (inside
  // the clipped table). Now it is a child of the `.ws` shell root — outside
  // any container that could clip it, but still inside the element every
  // design token is scoped to (see the next test).
  const parentIsWsRoot = await menu.evaluate((el) => el.parentElement?.classList.contains("ws"));
  expect(parentIsWsRoot).toBe(true);

  // Not just present in the DOM — actually clickable, which a clipped node
  // (zero-height overflow box, or z-index buried under the table) would fail.
  const edit = page.getByRole("menuitem", { name: "Edit details" });
  await expect(edit).toBeVisible();
  await edit.click();
  await expect(page.getByRole("heading", { name: "Edit contract details" })).toBeVisible();
});

test("the menu keeps its design tokens and fully covers the row it floats over", async ({
  page,
}) => {
  await createAnalysedReview(page);
  await createAnalysedReview(page);
  await page.goto("/dashboard");

  // The dashboard's default sort is "Recently Added", so the two contracts
  // just created (via createAnalysedReview) are rows 1 and 2 regardless of
  // how many other contracts this database already holds.
  const toggles = page.getByRole("button", { name: /More actions for/ });
  await toggles.first().click();

  const menu = page.locator(".ws-menu__list");
  const style = await menu.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { zIndex: cs.zIndex, backgroundColor: cs.backgroundColor, borderRadius: cs.borderRadius };
  });
  // Regression 2's exact signature: outside `.ws`, both of these silently
  // fall back to their CSS-initial values (`auto`, transparent) instead of
  // erroring — so pin the resolved values, not just "no crash".
  expect(style.zIndex).not.toBe("auto");
  expect(Number(style.zIndex)).toBeGreaterThan(0);
  expect(style.backgroundColor).not.toBe("rgba(0, 0, 0, 0)");
  expect(style.backgroundColor).not.toBe("transparent");
  expect(style.borderRadius).not.toBe("0px");

  // The menu, opening below row 1, lands over row 2's Action cell. Hit-testing
  // at the exact centre of row 2's own link must resolve to the menu, not the
  // link underneath it — proving the coverage (width fix) actually reaches
  // that point, on top of the token fix making it opaque there.
  const row2Link = page.locator("tbody tr").nth(1).locator(".ws-rowact a");
  const linkBox = await row2Link.boundingBox();
  const topElement = await page.evaluate(([x, y]) => {
    const el = document.elementFromPoint(x, y);
    return el?.closest(".ws-menu__list") != null;
  }, [linkBox!.x + linkBox!.width / 2, linkBox!.y + linkBox!.height / 2] as const);
  expect(topElement).toBe(true);
});
