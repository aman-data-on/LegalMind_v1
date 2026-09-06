import { readFileSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { csrfToken, fixture, postOk, snapshotId, storageStatePath } from "./support";

/**
 * Two lifecycle facts a document can now carry (2026-09-06).
 *
 * Phase 5, Option C — a version may be RE-READ in place with the current parser
 * while nothing relies on its current reading; the moment a Review exists the
 * server refuses and says what to do instead. P-1 — the contract's own state
 * (Step 2's Draft / Active / Superseded) is DECLARED by the owner and shown in
 * the workspace header in the reader's words.
 */
test.use({ storageState: storageStatePath("owner") });

async function uploadOnly(page: Page): Promise<{ contractId: string; versionId: string }> {
  const f = fixture();
  const contract = await postOk(page, "/contracts", {
    name: `Lifecycle MSA ${Date.now()}`, contract_type: "MSA",
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

test("a version is re-read in place only while nothing relies on it", async ({ page }) => {
  const { contractId, versionId } = await uploadOnly(page);
  const before = (await (await page.request.get(
    `/api/v1/document-versions/${versionId}/evidence?page_size=100`)).json()).data;

  // The workspace offers the re-read while no Review exists, and the pane reloads.
  await page.goto(`/dashboard?id=${contractId}`);
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  await page.getByRole("button", { name: "Re-read with the current parser" }).click();
  await expect(page.getByRole("status").filter({ hasText: /Re-read:/ }))
    .toHaveText(new RegExp(`Re-read: ${before.length} passages`));

  const after = (await (await page.request.get(
    `/api/v1/document-versions/${versionId}/evidence?page_size=100`)).json()).data;
  expect(after.length).toBe(before.length);
  expect(new Set(after.map((r: any) => r.id)).size).toBe(after.length);
  for (const row of after) expect(before.map((r: any) => r.id)).not.toContain(row.id); // the NEW run's rows

  // A Review anchors the reading: refused, with the way forward named.
  await postOk(page, "/reviews", { document_version_id: versionId, configuration_snapshot_id: snapshotId() });
  const refused = await page.request.post(`/api/v1/document-versions/${versionId}/reprocess`, {
    headers: { "X-CSRF-Token": await csrfToken(page) },
  });
  expect(refused.status()).toBe(409);
  expect(await refused.text()).toMatch(/Review/);
  expect(await refused.text()).toMatch(/new version/);
  await page.reload();
  await expect(page.locator('[data-region="document"] .ws-row').first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Re-read with the current parser" })).toHaveCount(0);
});

test("the contract's state is declared by the owner and read back in words", async ({ page }) => {
  const { contractId } = await uploadOnly(page);
  await page.goto(`/dashboard?id=${contractId}`);
  await expect(page.locator(".ws-context__meta .ws-chip", { hasText: "Draft" })).toBeVisible();

  const patched = await page.request.patch(`/api/v1/contracts/${contractId}`, {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrfToken(page) },
    data: { status: "ACTIVE" },
  });
  expect(patched.status()).toBe(200);
  await page.reload();
  await expect(page.locator(".ws-context__meta .ws-chip", { hasText: "Active" })).toBeVisible();
});
