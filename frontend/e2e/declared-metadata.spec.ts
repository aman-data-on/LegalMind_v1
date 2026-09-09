import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { csrfToken, fixture, postOk, snapshotId, storageStatePath } from "./support";

/**
 * Declared version metadata — source · counterparty · effective date (2026-09-06).
 *
 * Stored in locked 42.4's `document_versions.metadata` JSONB, declared by the
 * uploader and never read out of the document. Two properties the backend suite
 * cannot show from the browser's side: the keys are ABSENT until declared (never
 * null), and the same Dashboard list that feeds the counterparty datalist carries
 * them — through the proxy the real page uses. And the owner's ruling: once a
 * Review exists the declaration is fixed (locked 33.7), which the edit dialog
 * shows before the server refuses it.
 */
test.use({ storageState: storageStatePath("owner") });

const DECLARED = {
  source: "COUNTERPARTY",
  // A placeholder, never a real counterparty (locked 54.6).
  counterparty: "Placeholder Counterparty Ltd",
  effective_date: "2026-07-28",
};

async function declare(page: Page, versionId: string, body: Record<string, string | null>) {
  return page.request.patch(`/api/v1/document-versions/${versionId}`, {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrfToken(page) },
    data: body,
  });
}

/** The newest row's action menu — the same gesture `dashboard-list.spec.ts` uses:
 *  the menu renders through a portal, so wait for it rather than for the click. */
async function openFirstRowMenu(page: Page) {
  const toggle = page.getByRole("button", { name: /More actions for/ }).first();
  await toggle.scrollIntoViewIfNeeded();
  // A click that lands before hydration attaches the handler focuses the button
  // and opens nothing; retry until the menu is actually there.
  await expect(async () => {
    await toggle.click();
    await expect(page.locator(".ws-menu__list")).toBeVisible({ timeout: 1_000 });
  }).toPass();
}

/** Contract + uploaded version, NO Review — so the declaration is still open. */
async function uploadOnly(page: Page): Promise<{ contractId: string; versionId: string }> {
  const f = fixture();
  const contract = await postOk(page, "/contracts", {
    name: `Declared MSA ${Date.now()}`, contract_type: "MSA",
  });
  const upload = await page.request.post(`/api/v1/contracts/${contract.id}/document-versions`, {
    headers: {
      "Content-Type": f.document.mime,
      "X-Filename": f.document.filename,
      "X-CSRF-Token": await csrfToken(page),
    },
    data: readFileSync(f.document.path),
  });
  expect(upload.ok(), `upload failed: ${upload.status()}`).toBeTruthy();
  return { contractId: contract.id, versionId: (await upload.json()).data.document_version.id };
}

test("the keys are absent until declared, round-trip, reach the list, and freeze once reviewed", async ({ page }) => {
  const { contractId, versionId } = await uploadOnly(page);

  const bare = (await (await page.request.get(`/api/v1/document-versions/${versionId}`)).json()).data;
  for (const key of Object.keys(DECLARED)) expect(bare, `${key} omitted, not nulled`).not.toHaveProperty(key);

  const declared = await declare(page, versionId, DECLARED);
  expect(declared.status()).toBe(200);
  expect((await declared.json()).data).toMatchObject(DECLARED);

  // The Dashboard's own list — the datalist's only source of names.
  const listed = (await (await page.request.get(
    "/api/v1/contracts?page=1&page_size=25&sort=created_desc&scope=own")).json()).data;
  expect(listed.find((c: any) => c.id === contractId).latest_version).toMatchObject(DECLARED);

  // A Review — even one never analysed — fixes the declaration (owner, 2026-09-06).
  await postOk(page, "/reviews", { document_version_id: versionId, configuration_snapshot_id: snapshotId() });
  expect((await declare(page, versionId, { source: "ORGANIZATION" })).status()).toBe(409);
});

test("the edit dialog shows the declaration, and disables it once the version is analysed", async ({ page }) => {
  const { versionId } = await uploadOnly(page);
  expect((await declare(page, versionId, DECLARED)).status()).toBe(200);

  // Newest first, so the contract just created is row 1.
  await page.goto("/dashboard");
  await openFirstRowMenu(page);
  await page.getByRole("menuitem", { name: "Edit details" }).click();
  await expect(page.getByRole("heading", { name: "Edit contract details" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: /^Source/ })).toHaveValue("COUNTERPARTY");
  await expect(page.getByRole("combobox", { name: "Counterparty", exact: true })).toHaveValue(DECLARED.counterparty);
  await expect(page.getByRole("combobox", { name: "Counterparty", exact: true })).toBeEnabled();
  await expect(page.getByLabel(/^Effective date/)).toHaveValue("2026-07-28");
  await page.keyboard.press("Escape");

  // Analysed → the dialog says so and disables the fields BEFORE the server's 409
  // (presentation only, rule 18: the refusal is the server's either way).
  const review = await postOk(page, "/reviews", {
    document_version_id: versionId, configuration_snapshot_id: snapshotId(),
  });
  await postOk(page, `/reviews/${review.id}/analyze`);
  await page.goto("/dashboard");
  await openFirstRowMenu(page);
  await page.getByRole("menuitem", { name: "Edit details" }).click();
  await expect(page.getByRole("combobox", { name: "Counterparty", exact: true })).toBeDisabled();
  await expect(page.getByText(/has been analysed, so they are fixed/)).toBeVisible();
});

test("the workspace says whose paper it is, who it is with, and when it took effect", async ({ page }) => {
  const { contractId, versionId } = await uploadOnly(page);
  expect((await declare(page, versionId, DECLARED)).status()).toBe(200);

  // The manager's question — "LeapSwitch ne banaya hai ya counterparty ne
  // bheja hai" — answered where the reviewer reads, not only in the dialog
  // that records it. Declared facts render; undeclared ones stay absent.
  await page.goto(`/dashboard?id=${contractId}`);
  const meta = page.locator(".ws-context__meta");
  await expect(meta.getByText("Their document")).toBeVisible();
  await expect(meta.getByText(DECLARED.counterparty)).toBeVisible();
  await expect(meta.getByText("Effective 2026-07-28")).toBeVisible();

  // Cleared → the chip goes, rather than becoming an empty or "unknown" one.
  expect((await declare(page, versionId, { counterparty: null })).status()).toBe(200);
  await page.reload();
  await expect(page.locator(".ws-context__meta")).toBeVisible();
  await expect(meta.getByText(DECLARED.counterparty)).toHaveCount(0);
  await expect(meta.getByText("Their document")).toBeVisible();
});
