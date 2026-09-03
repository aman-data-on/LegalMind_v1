import { expect, test } from "@playwright/test";

import { csrfToken, postOk, storageStatePath } from "./support";

/** Signed in as `owner` — USER and nothing else. */
test.use({ storageState: storageStatePath("owner") });

/**
 * The Original document view (DD-16, 2026-09-03).
 *
 * A legal-document viewer must be able to show the document as it actually
 * looks — the preserved original bytes (34.5), rendered by the browser's own
 * PDF renderer — with the extracted text one click away, because every pointing
 * gesture (citations, outline, find) addresses Evidence rows.
 *
 * Only a browser can prove the composed behaviour: that a PDF opens on the
 * Original tab, that the iframe actually receives the bytes (a blob: URL), that
 * Text is one click away with the extracted content intact, and that a pointing
 * gesture lands the reader in the text view. The DOCX case is the honest
 * absence: no browser renders DOCX, so no toggle is offered at all.
 *
 * The PDF below is STRUCTURAL test data (generated, generic prose, no legal
 * position) — the same tier as the .fixture.json values (rule 21 note in
 * support.ts applies here unchanged).
 */
const STRUCTURAL_PDF = Buffer.from(
  "JVBERi0xLjcKJcK1wrYKJSBXcml0dGVuIGJ5IE11UERGIDEuMjguMgoKMSAwIG9iago8PC9UeXBlL0NhdGFsb2cvUGFnZXMgMiAw" +
  "IFIvSW5mbzw8L1Byb2R1Y2VyKE11UERGIDEuMjguMik+Pj4+CmVuZG9iagoKMiAwIG9iago8PC9UeXBlL1BhZ2VzL0NvdW50IDIv" +
  "S2lkc1s0IDAgUiA4IDAgUl0+PgplbmRvYmoKCjMgMCBvYmoKPDwvRm9udDw8L2hlbHYgNSAwIFI+Pj4+CmVuZG9iagoKNCAwIG9i" +
  "ago8PC9UeXBlL1BhZ2UvTWVkaWFCb3hbMCAwIDU5NSA4NDJdL1JvdGF0ZSAwL1Jlc291cmNlcyAzIDAgUi9QYXJlbnQgMiAwIFIv" +
  "Q29udGVudHNbNiAwIFJdPj4KZW5kb2JqCgo1IDAgb2JqCjw8L1R5cGUvRm9udC9TdWJ0eXBlL1R5cGUxL0Jhc2VGb250L0hlbHZl" +
  "dGljYS9FbmNvZGluZy9XaW5BbnNpRW5jb2Rpbmc+PgplbmRvYmoKCjYgMCBvYmoKPDwvTGVuZ3RoIDQ5MC9GaWx0ZXIvRmxhdGVE" +
  "ZWNvZGU+PgpzdHJlYW0KeNqNVLuO3DAM7P0V/gKfRfFhAcEVAdJcF8BdcE12baRIijT5/hvS9u7a8t0Fi4UskRxyKI6av83XsUlt" +
  "j19qRVsz7pJJO/5pn35Nv/+1KbXj3P74khNN1DOzsHLhiYsw1pknyThPOGGssOBchKQXwsqcNr/n1/Fll0qsK2Rc56o8OXVqpdSe" +
  "KGZQod56TQYsLSqGejSpGamEzX2S8fq1nAis1/CcVVdL2UfqFf8p4rIj6EUvsFMguEfSBXNWA15gG+HEgITdQ76sjiDKJkDZKpyU" +
  "79VVnEk6znTSHY+0sqs8OoCaZlNngS7M8Dlj59Vme+DmfVt7Mm/sED8tPQpU5yZeq5/fMwLDOUwr6+x+ntGW1Tt0wc7wrVhpi6yY" +
  "9qVLAw81U2SPGhCd167tOeeoEZx1taP3Q+yGc2b3LunGibyXd0Rk9Gm6xCTRFn3j7PYcd35d7eL3ePONPh8ZaqGuZKPh9DKP41YJ" +
  "BePV6VDsc6Go9h1kmPREv+T6lRzadAX7V10pQ/6F9T9SEdTL9oEk61Y+yGh/EZ9c6SanEB08MNzAIZdSRPyE9yLOVVSIXS//dhKj" +
  "i51LEcOIrG7JgXAQbEU14fkphU/en5iFSBEJ+d0ZPKpjp6Tj+7CbuvdepWVMvo3N9+YN6a9IbgplbmRzdHJlYW0KZW5kb2JqCgo3" +
  "IDAgb2JqCjw8L0ZvbnQ8PC9oZWx2IDUgMCBSPj4+PgplbmRvYmoKCjggMCBvYmoKPDwvVHlwZS9QYWdlL01lZGlhQm94WzAgMCA1" +
  "OTUgODQyXS9Sb3RhdGUgMC9SZXNvdXJjZXMgNyAwIFIvUGFyZW50IDIgMCBSL0NvbnRlbnRzWzkgMCBSXT4+CmVuZG9iagoKOSAw" +
  "IG9iago8PC9MZW5ndGggMzE2L0ZpbHRlci9GbGF0ZURlY29kZT4+CnN0cmVhbQp42m1RO07FMBDscwqfIPizn6yEKJBo6JDSIaq8" +
  "WBRQ0HB+ZtfwACWyotie2d2Z8fQx3a9TSRmrJJakSnNRTut7unnd3z5TKWnt6fm2tbrXzETMlS53L+vjvzLW2arSse7ApDKLmh2Z" +
  "TLKIaatZiqhWYawLvl2pZm1Ai2yyAW/SgQSGPeOmC9Spd/ATScF+3EvUmii4uIXSGkjB+awvpoG9KwdLpGt1NphZvNbAoWtnUoWK" +
  "TUX44LTyTK2eZALlY87ibtVdbOjdwru525GDe8DEi+sZjmIyY19RYY46173DQ3P9QCi8RS5QZz7nNxvNYHTotUjFdbTgIXvULN5p" +
  "JAScQ0vX8bdrxqg9uM02l4WWE7eEKU3/vKVUtfBhQ1W4+M7zR6WriJfgSCXeF6563Lm3PRQ8rNPT9AUPU6BDCmVuZHN0cmVhbQpl" +
  "bmRvYmoKCnhyZWYKMCAxMAowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAwNDIgMDAwMDAgbiAKMDAwMDAwMDEyMCAwMDAwMCBu" +
  "IAowMDAwMDAwMTc4IDAwMDAwIG4gCjAwMDAwMDAyMTkgMDAwMDAgbiAKMDAwMDAwMDMyNiAwMDAwMCBuIAowMDAwMDAwNDE1IDAw" +
  "MDAwIG4gCjAwMDAwMDA5NzQgMDAwMDAgbiAKMDAwMDAwMTAxNSAwMDAwMCBuIAowMDAwMDAxMTIyIDAwMDAwIG4gCgp0cmFpbGVy" +
  "Cjw8L1NpemUgMTAvUm9vdCAxIDAgUi9JRFs8QzNBQ0MyOURDM0FEMDFDMkI3MTdDM0I0QzJBN0MyODk+PEEyN0Q0QkE1RDhGRTU0" +
  "OTZBOThBQURGNTM5N0U4NUM3Pl0+PgpzdGFydHhyZWYKMTUwNwolJUVPRgo=",
  "base64",
);

async function uploadPdfContract(page: import("@playwright/test").Page) {
  const contract = await postOk(page, "/contracts", {
    name: `Original view PDF ${Date.now()}`,
    contract_type: "MSA",
  });
  const upload = await page.request.post(
    `/api/v1/contracts/${contract.id}/document-versions`,
    {
      headers: {
        "Content-Type": "application/pdf",
        "X-Filename": "structural.pdf",
        "X-CSRF-Token": await csrfToken(page),
      },
      data: STRUCTURAL_PDF,
    },
  );
  expect(upload.ok(), `upload failed: ${await upload.text()}`).toBeTruthy();
  return contract.id as string;
}

test.describe("the Original document view", () => {
  test("a PDF opens on Original — real bytes in the frame — with Text one click away", async ({
    page,
  }) => {
    const contractId = await uploadPdfContract(page);
    await page.goto(`/dashboard?id=${contractId}`);

    // The toggle exists, and Original is the default for a PDF.
    const original = page.getByRole("button", { name: "Original" });
    const text = page.getByRole("button", { name: "Text", exact: true });
    await expect(original).toBeVisible();
    await expect(original).toHaveAttribute("aria-pressed", "true");
    await expect(text).toHaveAttribute("aria-pressed", "false");

    // The frame received the preserved bytes: a blob: URL, not a placeholder.
    const frame = page.locator(".ws-original");
    await expect(frame).toHaveAttribute("src", /^blob:/);

    // Text is one click away and carries the extracted content.
    await text.click();
    await expect(text).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".ws-text")).toContainText("DEFINITIONS AND INTERPRETATION");
    await expect(page.locator(".ws-page__marker").first()).toContainText("Page 1");

    // And back.
    await original.click();
    await expect(page.locator(".ws-original")).toHaveAttribute("src", /^blob:/);
  });

  test("a pointing gesture lands the reader in the text view", async ({ page }) => {
    const contractId = await uploadPdfContract(page);
    await page.goto(`/dashboard?id=${contractId}`);
    await expect(page.locator(".ws-original")).toHaveAttribute("src", /^blob:/);

    // Click a clause in the outline while the Original view is showing: the
    // gesture addresses an Evidence row, so the pane switches itself to Text
    // and lights the row.
    await page.locator(".ws-outline__list button").first().click();
    await expect(page.getByRole("button", { name: "Text", exact: true }))
      .toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".ws-row--lit")).toBeVisible();
  });

  test("a DOCX offers no Original tab — no browser renders one, so none is pretended", async ({
    page,
  }) => {
    const { createAnalysedReview } = await import("./support");
    const { contractId } = await createAnalysedReview(page, { analyse: false });
    await page.goto(`/dashboard?id=${contractId}`);

    await expect(page.locator(".ws-text")).toBeVisible();
    await expect(page.locator(".ws-viewtoggle")).toHaveCount(0);
  });
});
