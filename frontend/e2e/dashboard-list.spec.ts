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
  // Forced to an EXACT scroll position (2026-09-24, dashboard hero redesign):
  // the page above the table is taller now — hero banner, toolbar, stat
  // cards — so row 1's toggle is no longer guaranteed to already sit near
  // the top of a 720px viewport the way it did on the old, one-line header.
  // `scrollIntoView({block:"start"})` was tried here first and did not hold:
  // if the browser judges the element already "in view" (even hard against
  // the bottom edge), it can decide no scroll is needed at all — then
  // `.click()`'s own actionability scroll (nearest edge) leaves the toggle
  // exactly where there is too little room below it, and the menu correctly
  // (per `openMenu`'s own rules) flips upward instead of covering row 2,
  // which is not the case this test means to exercise. Computing the target
  // `scrollTop` directly and setting it leaves no such judgment call.
  const absoluteTop = await toggles.first().evaluate(
    (el) => el.getBoundingClientRect().top + window.scrollY,
  );
  await page.evaluate((y) => window.scrollTo(0, Math.max(0, y - 40)), absoluteTop);
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

/**
 * The search box, typed the way a person types it.
 *
 * A 2026-09-16 UX review reported it dead: `xyz-nomatch` was entered and the table did
 * not change. The input is in fact fully wired — controlled value, 300 ms debounce, `q`
 * sent to the server and in the loader's dependency list — and the unit tests pin that
 * `q` reaches the request. What none of that proves is the bit the review was actually
 * exercising: a real keystroke reaching React's onChange. Setting `input.value` from
 * devtools does NOT fire it, which is the likeliest reason the box looked dead.
 *
 * So this types with the keyboard, through the real component, against the real server,
 * and asserts the whole chain: keystroke → debounce → request → rendered rows. It is
 * deliberately an e2e test; the house has no DOM testing library, and adding one would
 * be a rule 19 dependency decision.
 */
test("typing in the search box filters the table, and clearing it brings the rows back", async ({
  page,
}) => {
  const { contractId } = await createAnalysedReview(page);
  const contract = await (await page.request.get(`/api/v1/contracts/${contractId}`)).json();
  const name: string = contract.data.name;

  await page.goto("/dashboard");
  const search = page.getByRole("textbox", { name: "Search contracts" });
  const rows = page.locator("tbody tr");
  await expect(rows.filter({ hasText: name })).toHaveCount(1);

  // A string no contract can carry. `pressSequentially` raises real key events —
  // `fill()` would set the value in one shot and prove less about the wiring.
  await search.pressSequentially("xyz-nomatch", { delay: 20 });
  // Past the 300 ms debounce, the server answers with nothing and the table says so
  // rather than silently keeping the rows it had.
  await expect(rows.filter({ hasText: name })).toHaveCount(0, { timeout: 5000 });

  // The term survives as the reader typed it — a debounce that reset the input would
  // look identical to a filter that worked and then undid itself.
  await expect(search).toHaveValue("xyz-nomatch");

  // And it is a filter, not a one-way trip: clearing restores the row.
  await search.fill("");
  await expect(rows.filter({ hasText: name })).toHaveCount(1, { timeout: 5000 });

  // Finally the positive direction: typing part of the real name keeps it on screen,
  // so the assertion above is about the query and not about an empty table.
  await search.pressSequentially(name.slice(0, 10), { delay: 20 });
  await expect(rows.filter({ hasText: name })).toHaveCount(1, { timeout: 5000 });
});
