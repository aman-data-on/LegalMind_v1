import { readFileSync } from "node:fs";

import { expect, test } from "@playwright/test";

import { fixture, openUploadPanel, storageStatePath } from "./support";

test.use({ storageState: storageStatePath("owner") });

/**
 * A filename with a non-ASCII character must still upload.
 *
 * Regression, 2026-09-03 — reported against the live site with a real NDA
 * filename containing an en dash ("NON – DISCLOSURE"). HTTP header values are
 * restricted to ISO-8859-1 bytes, and `api.ts` set the filename directly as
 * the `X-Filename` header — so the browser's `fetch` threw synchronously,
 * before the request ever left the tab. No request reached the server (the
 * contract record was already created by that point, so the visible symptom
 * was a contract with no document and a generic "request could not be
 * completed" banner). The fix percent-encodes the header on the client and
 * decodes it on the server (`upload_document_version` in contracts.py); this
 * drives the real upload UI exactly as a user would, through the real `fetch`
 * call, rather than Playwright's `page.request` API context, which bypasses
 * the browser's header validation entirely and would not have caught this.
 */
test("a filename containing a non-ASCII character uploads without error", async ({ page }) => {
  const f = fixture();
  await page.goto("/dashboard");
  await openUploadPanel(page);

  await page.setInputFiles('input[type="file"]', {
    name: "MUTUAL NON – DISCLOSURE AGREEMENT.docx", // en dash, U+2013
    mimeType: f.document.mime,
    buffer: readFileSync(f.document.path),
  });

  // The defect's exact symptom: a generic client-side error banner, with the
  // panel dropped back to its empty "Upload a contract" state.
  await expect(page.locator(".ws-field__error")).toHaveCount(0);

  // The upload succeeded and the flow reached the type-confirmation step —
  // proof the request actually reached the server and came back.
  const typeSelect = page.getByLabel(/^Document type/);
  await expect(typeSelect).toBeVisible({ timeout: 15_000 });
});
