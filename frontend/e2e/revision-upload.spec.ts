import { expect, test } from "@playwright/test";

import { createAnalysedReview, fixture, openAsk, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * The workspace's own "Upload a revised version" control, exercised AFTER an Ask
 * interaction — the exact sequence that hung on 2026-09-02's live run: the dock
 * was opened, Escape closed it, the reupload disclosure was opened, a file was
 * set, Upload was clicked — and no POST ever reached the API. journey.spec.ts
 * exercises the same control WITHOUT the dock interaction and passes, so if the
 * dock sequence is the difference, this spec is where it shows.
 */
test("revised-version upload works after opening and closing Ask", async ({ page }) => {
  const { contractId } = await createAnalysedReview(page, { analyse: false });
  await page.goto(`/dashboard?id=${contractId}`);

  // The live sequence, verbatim: dock open, then Escape.
  const input = await openAsk(page);
  await expect(input).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.locator(".ws-dock__panel")).toBeHidden();

  // Now the reupload, watching the wire the whole way.
  const posts: string[] = [];
  page.on("request", (r) => {
    if (r.method() === "POST") posts.push(r.url());
  });
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.getByRole("button", { name: "Upload a revised version" }).click();
  const file = page.locator('.ws-reupload input[type="file"]');
  await expect(file).toBeVisible();
  await file.setInputFiles(fixture().document.path);
  await page.locator(".ws-reupload").getByRole("button", { name: /^Upload$/ }).click();

  // The POST must leave the page promptly — the 2026-09-02 hang was its absence.
  await expect
    .poll(() => posts.some((u) => u.includes("/document-versions")), { timeout: 15_000 })
    .toBeTruthy();

  // And the flow completes: a second version exists and the picker appears.
  await expect(page.locator(".ws-version select")).toBeVisible({ timeout: 120_000 });
  await expect(page.locator(".ws-version select option")).toHaveCount(2);

  expect(errors, `console/page errors: ${errors.join(" | ")}`).toEqual([]);
});
