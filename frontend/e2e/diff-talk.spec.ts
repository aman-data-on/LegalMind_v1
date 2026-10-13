import { type Page, expect, test } from "@playwright/test";

import { csrfToken, postOk, storageStatePath } from "./support";

/**
 * Diff-Talk — our document beside a client contract (owner, 2026-10-12/13). The
 * QA plan of 2026-10-13, kept in CI (it lived only in a session scratchpad).
 *
 * The two documents are SYNTHETIC plain text built here — no real contract enters
 * the repository (54.6), and nothing asserts a legal conclusion: these tests pin
 * the WORDING comparison only. Between them: one clause reworded (fees), one
 * missing (termination), one added (audit), one renumbered word for word
 * (notices, 4 → 3) — three differences, the rest the same.
 */
const OURS = [
  "SERVICES AGREEMENT",
  "1. Definitions",
  "\"Services\" means the services described in an order form.",
  "2. Fees",
  "Fees are billed monthly in advance and are payable within fifteen days of invoice.",
  "3. Termination",
  "Either party may end this agreement by giving thirty days written notice.",
  "4. Notices",
  "Notices are sent by email to the addresses given in the order form.",
].join("\n\n");
const THEIRS = [
  "SERVICES AGREEMENT",
  "1. Definitions",
  "\"Services\" means the services described in an order form.",
  "2. Fees",
  "Fees are billed monthly in advance and are payable within forty-five days of invoice.",
  "3. Notices",
  "Notices are sent by email to the addresses given in the order form.",
  "4. Audit",
  "The customer may audit the records of the provider once a year.",
].join("\n\n");

test.use({ storageState: storageStatePath("owner"), permissions: ["clipboard-read", "clipboard-write"] });

/** One document through the real endpoints, declared ours or theirs (Step 6). */
async function uploadText(page: Page, name: string, text: string,
                          source: "ORGANIZATION" | "COUNTERPARTY"): Promise<string> {
  const contract = await postOk(page, "/contracts", { name: `${name} ${Date.now()}` });
  const upload = await page.request.post(`/api/v1/contracts/${contract.id}/document-versions`, {
    headers: { "Content-Type": "text/plain", "X-Filename": `${name}.txt`,
               "X-CSRF-Token": await csrfToken(page) },
    data: Buffer.from(text),
  });
  expect(upload.ok(), await upload.text()).toBeTruthy();
  const versionId: string = (await upload.json()).data.document_version.id;
  const declared = await page.request.patch(`/api/v1/document-versions/${versionId}`, {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrfToken(page) },
    data: { source },
  });
  expect(declared.ok(), await declared.text()).toBeTruthy();
  return versionId;
}

async function openPair(page: Page) {
  await page.goto("/dashboard");
  const ours = await uploadText(page, "Diff ours", OURS, "ORGANIZATION");
  const theirs = await uploadText(page, "Diff theirs", THEIRS, "COUNTERPARTY");
  await page.goto(`/dashboard/diff?left=${ours}&right=${theirs}`);
  await expect(page.locator(".ws-dt__card").first()).toBeVisible({ timeout: 20_000 });
  return { ours, theirs };
}

test("setup: each side lists only its own documents, and uploads land on their side", async ({ page }) => {
  await page.goto("/dashboard/diff");
  await expect(page.locator(".ws-dt__slot")).toHaveCount(2);
  await page.locator(".ws-dt__slot").nth(0).locator('input[type="file"]')
    .setInputFiles({ name: "Setup ours.txt", mimeType: "text/plain", buffer: Buffer.from(OURS) });
  await expect(page.locator(".ws-dt__slot.is-filled")).toHaveCount(1, { timeout: 20_000 });
  await expect(page).toHaveURL(/left=/);
  // Our upload is offered on our side only.
  await expect(page.locator("#dt-pick-1 option", { hasText: "Setup ours" })).toHaveCount(1);
  await expect(page.locator("#dt-pick-2 option", { hasText: "Setup ours" })).toHaveCount(0);
  await page.locator(".ws-dt__slot").nth(1).locator('input[type="file"]')
    .setInputFiles({ name: "Setup theirs.txt", mimeType: "text/plain", buffer: Buffer.from(THEIRS) });
  await expect(page.locator(".ws-dt--review")).toBeVisible({ timeout: 20_000 });
});

test("review: differences first, counts agree, wording only — never a verdict", async ({ page }) => {
  await openPair(page);
  const all = page.locator('.ws-dt__filters button[aria-pressed="true"] span');
  await expect(all).toHaveText("3");
  await expect(page.locator(".ws-dt__change-item")).toHaveCount(3);
  await expect(page.locator(".ws-dt__card")).toHaveCount(3);
  await expect(page.locator(".ws-dt__kind", { hasText: "Wording changed" })).toHaveCount(1);
  await expect(page.locator(".ws-dt__kind", { hasText: "Missing from the client's" })).toHaveCount(1);
  await expect(page.locator(".ws-dt__kind", { hasText: "Added by the client" })).toHaveCount(1);
  // The renumbered clause and the rest read the same: hidden in Changes only, and
  // on BOTH sides in Full documents (one column read as the client having none).
  await expect(page.locator(".ws-dt__card.is-unchanged")).toHaveCount(0);
  await page.getByRole("button", { name: "Full documents", exact: true }).click();
  const same = page.locator(".ws-dt__card.is-unchanged");
  await expect(same.first()).toBeVisible();
  await expect(same.first().locator(".ws-dt__sidetext.is-client .ws-dt__text")).toBeVisible();
  // Same-wording clauses are read, not counted: still three differences listed.
  await expect(page.locator(".ws-dt__change-item")).toHaveCount(3);
  // 33.16: a comparison never says whether a difference is acceptable.
  await expect(page.locator(".ws-dt--review")).not.toContainText(/acceptable|approved|rejected|compliant/i);
});

test("choices: a click folds and moves on, a key stays, they persist, and Copy for Legal lists them", async ({ page }) => {
  await openPair(page);
  const progress = page.locator(".ws-dt__progress span");
  await expect(progress).toHaveText("0 of 3 decided");
  await page.locator(".ws-dt__card").nth(0).locator(".ws-dt__opt").nth(0).click();
  await expect(progress).toHaveText("1 of 3 decided");
  await expect(page.locator(".ws-dt__card").nth(0)).toHaveClass(/is-folded/);
  await expect(page.locator(".ws-dt__card.is-current .ws-dt__num")).toHaveText("2");
  const second = page.locator(".ws-dt__card").nth(1);
  await second.locator("input").first().focus();
  await page.keyboard.press("ArrowRight");
  await expect(progress).toHaveText("2 of 3 decided");
  await expect(second.locator("input:checked")).toBeFocused();
  await expect(second).not.toHaveClass(/is-folded/);
  await page.reload();
  await expect(progress).toHaveText("2 of 3 decided", { timeout: 20_000 });
  await expect(page.locator(".ws-dt__card.is-folded")).toHaveCount(2);
  // Change reopens a decided difference with its choice in focus.
  await page.locator(".ws-dt__card.is-folded").first().getByRole("button", { name: /Change your choice/ }).click();
  await expect(page.locator(".ws-dt__card").nth(0).locator("input:checked")).toBeFocused();
  await page.getByRole("button", { name: "Copy for Legal" }).click();
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  expect(copied).toContain("(ours) vs");
  expect(copied.match(/not decided yet/g)).toHaveLength(1);
});

test("navigation: J/K stay inside a filter, 1/2 choose; Change, Back and Forward", async ({ page }) => {
  const { ours, theirs } = await openPair(page);
  await page.locator(".ws-dt__filters button", { hasText: "Added" }).click();
  await expect(page.locator(".ws-dt__card")).toHaveCount(1);
  await page.locator("body").click({ position: { x: 5, y: 5 } });
  await page.keyboard.press("j");
  await expect(page.locator(".ws-dt__pos")).toContainText("1 of 1");
  // 2 chooses the client's side for the current difference, and folds it.
  await page.keyboard.press("2");
  await expect(page.locator(".ws-dt__card").first()).toHaveClass(/is-folded/);
  await expect(page.locator(".ws-dt__pickword")).toHaveText("Add it");
  await page.locator(".ws-dt__doc").nth(1).getByRole("button", { name: "Change" }).click();
  await expect(page.locator(".ws-dt--setup")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`left=${ours}$`));
  await page.goBack();
  await expect(page).toHaveURL(new RegExp(`right=${theirs}`));
  await expect(page.locator(".ws-dt__card").first()).toBeVisible({ timeout: 20_000 });
  await page.goForward();
  await expect(page.locator(".ws-dt--setup")).toBeVisible();
});

test("errors: the same document twice, an unknown reference, an unreadable upload", async ({ page }) => {
  const { ours } = await openPair(page);
  await page.goto(`/dashboard/diff?left=${ours}&right=${ours}`);
  await expect(page.locator(".ws-dt__fail")).toContainText("two different");
  await page.goto(`/dashboard/diff?left=${ours}&right=not-a-document`);
  await expect(page.locator(".ws-dt__fail p")).toHaveText("Not found.");
  await page.goto(`/dashboard/diff?left=${ours}`);
  await page.locator(".ws-dt__slot").nth(1).locator('input[type="file"]')
    .setInputFiles({ name: "broken.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-garbage") });
  await expect(page.locator(".ws-dt__slot").nth(1).locator(".ws-dt__msg.is-error")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".ws-dt--setup")).toBeVisible();
});

test("another user cannot open the owner's documents by URL (SEC-07)", async ({ page, browser }) => {
  const { ours, theirs } = await openPair(page);
  const other = await browser.newContext({ storageState: storageStatePath("reader") });
  const peek = await other.newPage();
  await peek.goto(`/dashboard/diff?left=${ours}&right=${theirs}`);
  await expect(peek.locator(".ws-dt__fail p")).toHaveText("Not found.", { timeout: 20_000 });
  await expect(peek.locator(".ws-dt__card")).toHaveCount(0);
  await other.close();
});

test("phone width: one column, a thumb bar, the list in a sheet, no sideways scroll", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openPair(page);
  await expect(page.locator(".ws-dt__key")).toBeVisible();
  await page.locator(".ws-dt__dockmid").click();
  await expect(page.locator(".ws-dt__sheet")).toBeVisible();
  await page.locator(".ws-dt__sheet .ws-dt__change-item").nth(2).click();
  await expect(page.locator(".ws-dt__sheet")).toBeHidden();
  await expect(page.locator(".ws-dt__dockmid .ws-dt__pos")).toContainText("3 of 3");
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBe(0);
});
