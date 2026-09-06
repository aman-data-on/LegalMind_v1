import { expect, test } from "@playwright/test";

import { csrfToken, postOk, storageStatePath } from "./support";

/**
 * The counterparty as an ENTITY — AB-13 (2026-09-06).
 *
 * Management asked for two things Phase 3's free text could not give: a company
 * PROFILE, and the NDA → MSA → revisions of one company stopping being isolated
 * documents. Both rest on identity, which is what the entity adds.
 *
 * Also pinned here: the disclosure boundary (r6). "We have a deal with X" is
 * exactly the class of fact SEC-07/LEGAL-02 keep inside scope, so a company must
 * never appear to an account that shares no contract with it.
 */
test.use({ storageState: storageStatePath("owner") });

async function patchOk(page: import("@playwright/test").Page, path: string, body: unknown) {
  const response = await page.request.patch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrfToken(page) },
    data: body as Record<string, unknown>,
  });
  expect(response.ok(), `PATCH ${path} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()).data;
}

test("one company gathers its own documents, and the profile is editable", async ({ page }) => {
  const stamp = Date.now();
  const company = await postOk(page, "/counterparties", { name: `Placeholder Co ${stamp}` });
  expect(company.industry).toBeUndefined();          // nothing invented (rule 21)

  const nda = await postOk(page, "/contracts", { name: `NDA ${stamp}`, contract_type: "NDA" });
  const msa = await postOk(page, "/contracts", { name: `MSA ${stamp}`, contract_type: "MSA" });
  for (const c of [nda, msa]) {
    await patchOk(page, `/contracts/${c.id}`, { counterparty_id: company.id });
  }

  // The manager's "related documents": one query, no relationship table.
  const profile = (await (await page.request.get(
    `/api/v1/counterparties/${company.id}`)).json()).data;
  expect(new Set(profile.contracts.map((c: any) => c.id))).toEqual(new Set([nda.id, msa.id]));
  expect(new Set(profile.contracts.map((c: any) => c.contract_type))).toEqual(new Set(["NDA", "MSA"]));

  // The profile is real: an industry can be recorded later, and cleared again.
  const filled = await patchOk(page, `/counterparties/${company.id}`, { industry: "Cloud hosting" });
  expect(filled.industry).toBe("Cloud hosting");
  const cleared = await patchOk(page, `/counterparties/${company.id}`, { industry: null });
  expect(cleared.industry).toBeUndefined();
});

test("the edit dialog links a deal to a company, and the link survives a reload", async ({ page }) => {
  const stamp = Date.now();
  const company = await postOk(page, "/counterparties", { name: `Linkable Co ${stamp}` });
  const contract = await postOk(page, "/contracts", { name: `Deal ${stamp}`, contract_type: "MSA" });

  await page.goto("/dashboard");
  const toggle = page.getByRole("button", { name: `More actions for ${contract.name}` });
  await toggle.scrollIntoViewIfNeeded();
  await expect(async () => {
    await toggle.click();
    await expect(page.locator(".ws-menu__list")).toBeVisible({ timeout: 1_000 });
  }).toPass();
  await page.getByRole("menuitem", { name: "Edit details" }).click();

  const picker = page.getByLabel(/^Company \(counterparty\)/);
  await expect(picker).toBeVisible();
  await picker.selectOption(company.id);
  await page.getByRole("button", { name: "Save changes" }).click();

  await expect(async () => {
    const fresh = (await (await page.request.get(`/api/v1/contracts/${contract.id}`)).json()).data;
    expect(fresh.counterparty_id).toBe(company.id);
  }).toPass();
});

test("a company is invisible to an account that shares no contract with it", async ({ page, browser }) => {
  const stamp = Date.now();
  const company = await postOk(page, "/counterparties", { name: `Private Co ${stamp}` });
  const contract = await postOk(page, "/contracts", { name: `Private ${stamp}`, contract_type: "MSA" });
  await patchOk(page, `/contracts/${contract.id}`, { counterparty_id: company.id });

  // A different account: no shared contract, so no sight of the company at all —
  // and by id the answer is 404, never a 403 that would confirm it exists (r6).
  const other = await browser.newContext({ storageState: storageStatePath("reader") });
  const otherPage = await other.newPage();
  const listed = (await (await otherPage.request.get("/api/v1/counterparties")).json()).data;
  expect(listed.map((c: any) => c.id)).not.toContain(company.id);
  expect((await otherPage.request.get(`/api/v1/counterparties/${company.id}`)).status()).toBe(404);
  await other.close();
});

test("the workspace names the company and opens every document for it", async ({ page }) => {
  const stamp = Date.now();
  const company = await postOk(page, "/counterparties", { name: `Grouped Co ${stamp}` });
  const nda = await postOk(page, "/contracts", { name: `Their NDA ${stamp}`, contract_type: "NDA" });
  const msa = await postOk(page, "/contracts", { name: `Their MSA ${stamp}`, contract_type: "MSA" });
  for (const c of [nda, msa]) {
    await patchOk(page, `/contracts/${c.id}`, { counterparty_id: company.id });
  }

  // The header names the LINKED company (AB-13 r7) and it is a real control.
  await page.goto(`/dashboard?id=${msa.id}`);
  const chip = page.getByRole("button", { name: company.name });
  await expect(chip).toBeVisible();
  await chip.click();

  // ...which opens every document for that company — the manager's ask.
  const dialog = page.getByRole("dialog", { name: company.name });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("link", { name: `Their NDA ${stamp}` })).toBeVisible();
  await expect(dialog.getByText("open now")).toBeVisible();

  // And it navigates: the NDA is one click from the MSA.
  await dialog.getByRole("link", { name: `Their NDA ${stamp}` }).click();
  await expect(page).toHaveURL(new RegExp(`id=${nda.id}`));
});
