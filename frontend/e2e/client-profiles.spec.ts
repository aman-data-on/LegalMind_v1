import { readFileSync } from "node:fs";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

import { expect, test } from "@playwright/test";

import { csrfToken, fixture, postOk, snapshotId, storageStatePath } from "./support";

/**
 * Client Profiles in a real browser — owner instruction, 2026-09-10.
 *
 * What only a browser can prove, and therefore what this spec is for:
 *
 *  * the six document types render in ONE table with one `<tbody>`, which is
 *    the owner's "do not create MSA/NDA/SLA sections" as a DOM fact rather than
 *    a promise in a comment;
 *  * three versions of one document are all still reachable after the third
 *    upload, each wearing its own declared role;
 *  * the rail and the workspace actually lay out as two columns, with the
 *    workspace taking the majority of the width;
 *  * "Analyze" on a client's document reaches the EXISTING engine and comes
 *    back with the existing reader statuses.
 *
 * Every value here is synthetic fixture data in the dedicated e2e database
 * (rule 21 / locked 54.6): the company names are stamped placeholders, and no
 * real counterparty, contact or legal position appears anywhere.
 */
test.use({ storageState: storageStatePath("owner") });

/**
 * Where the review screenshots land. `LEGALMIND_SHOTS_DIR` overrides it, which
 * is what a session without write access to the repo's `test-results/` uses —
 * the images are a review aid, not an artefact the repository keeps.
 */
const SHOTS = process.env.LEGALMIND_SHOTS_DIR
  ?? join(__dirname, "..", "..", "test-results", "client-profiles");

async function patchOk(page: import("@playwright/test").Page, path: string, body: unknown) {
  const response = await page.request.patch(`/api/v1${path}`, {
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrfToken(page) },
    data: body as Record<string, unknown>,
  });
  expect(response.ok(),
         `PATCH ${path} → ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()).data;
}

/** Upload the fixture document to a contract and return the new version. */
async function upload(page: import("@playwright/test").Page, contractId: string) {
  const f = fixture();
  const response = await page.request.post(
    `/api/v1/contracts/${contractId}/document-versions`,
    {
      headers: {
        "Content-Type": f.document.mime,
        "X-Filename": f.document.filename,
        "X-CSRF-Token": await csrfToken(page),
      },
      data: readFileSync(f.document.path),
    },
  );
  expect(response.ok(), `upload → ${response.status()} ${await response.text()}`)
    .toBeTruthy();
  return (await response.json()).data.document_version;
}

/** One client carrying six document types and a three-version negotiation. */
async function buildClient(page: import("@playwright/test").Page, stamp: number) {
  const client = await postOk(page, "/counterparties", {
    name: `Northwind Systems ${stamp}`,
    legal_name: `Northwind Systems Placeholder Ltd ${stamp}`,
    industry: "Information technology",
    city: "Pune", state_region: "Maharashtra", country: "India",
    website: "https://northwind.invalid",
    primary_contact_name: "Placeholder Contact",
    primary_contact_email: "contact@northwind.invalid",
    primary_contact_phone: "+91 00000 00000",
    legal_contact_name: "Placeholder Counsel",
    legal_contact_email: "legal@northwind.invalid",
    status: "ACTIVE",
    relationship_notes: "Synthetic fixture client. Carries no legal position.",
  });

  // Six types, ONE list. The MSA is the one that carries a negotiation.
  const msa = await postOk(page, "/contracts", {
    name: "Master Services Agreement", contract_type: "MSA",
    counterparty_id: client.id,
  });
  const roles = ["COMPANY_DRAFT", "CLIENT_MODIFIED", "FINAL_SIGNED"] as const;
  for (const role of roles) {
    const version = await upload(page, msa.id);
    await patchOk(page, `/document-versions/${version.id}`, { version_role: role });
  }

  for (const [name, type, role] of [
    ["Mutual Non-Disclosure Agreement", "NDA", "COMPANY_DRAFT"],
    ["Service Level Agreement", "SLA", "CLIENT_MODIFIED"],
    ["Amendment 1", "AMENDMENT", "FINAL_SIGNED"],
    ["Order Form", "ORDER_FORM", null],
    ["Partner Agreement", "OTHER", null],
  ] as const) {
    const contract = await postOk(page, "/contracts", {
      name, contract_type: type, counterparty_id: client.id,
    });
    const version = await upload(page, contract.id);
    if (role) {
      await patchOk(page, `/document-versions/${version.id}`, { version_role: role });
    }
  }
  return client;
}

test("a client's six document types are ONE list, not six sections", async ({ page }) => {
  const client = await buildClient(page, Date.now());
  await page.goto(`/dashboard/clients?id=${client.id}`);

  const table = page.locator(".ws-cl__docs .ws-cl__table table");
  await expect(table).toHaveCount(1);
  await expect(table.locator("tbody")).toHaveCount(1);

  // Every document, by name, in that one table.
  for (const name of [
    "Master Services Agreement", "Mutual Non-Disclosure Agreement",
    "Service Level Agreement", "Amendment 1", "Order Form", "Partner Agreement",
  ]) {
    await expect(table.getByRole("link", { name })).toBeVisible();
  }

  // Type travels as a chip in its own column — six of them, one per row.
  await expect(table.locator(".ws-chip--type")).toHaveCount(6);

  // And there is no per-type heading anywhere on the page: a section per type
  // is the structure the owner ruled out, so its absence is asserted, not
  // assumed.
  for (const heading of ["MSA", "NDA", "SLA"]) {
    await expect(page.getByRole("heading", { name: heading, exact: true }))
      .toHaveCount(0);
  }
  await expect(page.getByRole("heading", { name: "Legal documents" })).toBeVisible();
});

test("three versions of one document all survive, each with its own role",
     async ({ page }) => {
  const client = await buildClient(page, Date.now());
  await page.goto(`/dashboard/clients?id=${client.id}`);

  const row = page.locator("tr", { hasText: "Master Services Agreement" }).first();
  const toggle = row.getByRole("button", { name: /3 versions/ });
  await expect(toggle).toBeVisible();
  await toggle.click();

  const versions = page.locator(".ws-cl__verlist .ws-cl__ver");
  await expect(versions).toHaveCount(3);
  // Newest first, and every one still there — the third upload replaced nothing.
  await expect(versions.nth(0)).toContainText("v3");
  await expect(versions.nth(0)).toContainText("Final signed");
  await expect(versions.nth(1)).toContainText("v2");
  await expect(versions.nth(1)).toContainText("Client modified");
  await expect(versions.nth(2)).toContainText("v1");
  await expect(versions.nth(2)).toContainText("Company draft");
  // The current version is the highest number, and it is said so.
  await expect(versions.nth(0)).toContainText("current");
});

test("an unclassified version says so rather than being guessed at",
     async ({ page }) => {
  const client = await buildClient(page, Date.now());
  await page.goto(`/dashboard/clients?id=${client.id}`);
  const row = page.locator("tr", { hasText: "Order Form" }).first();
  await row.getByRole("button", { name: /1 version/ }).click();
  await expect(page.locator(".ws-cl__verlist .ws-cl__ver").first())
    .toContainText("Not classified");
});

test("a document already in LegalMind is linked, never re-uploaded",
     async ({ page }) => {
  const stamp = Date.now();
  const client = await postOk(page, "/counterparties", { name: `Linkable Co ${stamp}` });
  const orphan = await postOk(page, "/contracts", {
    name: `Historical NDA ${stamp}`, contract_type: "NDA",
  });
  await upload(page, orphan.id);

  await page.goto(`/dashboard/clients?id=${client.id}`);
  await expect(page.getByText("No legal documents for this client yet")).toBeVisible();

  await page.getByRole("button", { name: "Link existing" }).click();
  const list = page.locator(".ws-cl__linklist");
  await expect(list).toBeVisible();
  const entry = list.locator("li", { hasText: `Historical NDA ${stamp}` });
  await entry.getByRole("button", { name: "Link" }).click();

  // It appears in the client's list — and there is still exactly ONE contract
  // with that name, so nothing was copied.
  await expect(page.locator(".ws-cl__docs")
    .getByRole("link", { name: `Historical NDA ${stamp}` })).toBeVisible();
  const all = await (await page.request.get(
    `/api/v1/contracts?page_size=100&q=Historical NDA ${stamp}`)).json();
  expect(all.data).toHaveLength(1);
  expect(all.data[0].counterparty_id).toBe(client.id);
});

test("the existing analysis engine is what a client's document is analyzed by",
     async ({ page }) => {
  const stamp = Date.now();
  const client = await postOk(page, "/counterparties", { name: `Analysed Co ${stamp}` });
  const contract = await postOk(page, "/contracts", {
    name: `Analysed MSA ${stamp}`, contract_type: "MSA", counterparty_id: client.id,
  });
  const version = await upload(page, contract.id);
  // The existing endpoints, exactly as the workspace calls them.
  const review = await postOk(page, "/reviews", {
    document_version_id: version.id, configuration_snapshot_id: snapshotId(),
  });
  await postOk(page, `/reviews/${review.id}/analyze`);

  await page.goto(`/dashboard/clients?id=${client.id}`);
  const row = page.locator("tr", { hasText: `Analysed MSA ${stamp}` }).first();
  // The row shows the server's own bucket and the three reader statuses — the
  // same vocabulary the Dashboard and the workspace use (`AM-56`).
  await expect(row.locator(".ws-status-pill")).toBeVisible();
  await expect(row.locator(".ws-findings-badge")).toHaveCount(3);
  // ...and leads to the existing workspace rather than a second reader.
  await expect(row.getByRole("link", { name: "Review" })).toBeVisible();
});

test("a client this caller shares no contract with is not on their screen",
     async ({ page, browser }) => {
  const stamp = Date.now();
  const client = await postOk(page, "/counterparties", { name: `Private Co ${stamp}` });
  const contract = await postOk(page, "/contracts", {
    name: `Private MSA ${stamp}`, counterparty_id: client.id,
  });
  expect(contract.counterparty_id).toBe(client.id);

  // A different account: AB-13 r6 — "we have a deal with X" stays in scope, and
  // a nicer screen over the same set does not widen it.
  const other = await browser.newContext({ storageState: storageStatePath("reader") });
  const otherPage = await other.newPage();
  await otherPage.goto(`/dashboard/clients`);
  await expect(otherPage.getByText(`Private Co ${stamp}`)).toHaveCount(0);
  const listed = await (await otherPage.request.get("/api/v1/counterparties")).json();
  expect(listed.data.map((c: { id: string }) => c.id)).not.toContain(client.id);
  await other.close();
});

/**
 * The visual review. Not an assertion suite — a reproducible way to LOOK at the
 * screens with real data in them, which is the only way to judge whether the
 * layout uses the width, whether the rail is compact, and whether the page
 * reads as a client file rather than another dashboard.
 */
test("capture the screens for visual review", async ({ page }) => {
  mkdirSync(SHOTS, { recursive: true });
  const stamp = Date.now();
  const client = await buildClient(page, stamp);
  // A few more clients, so the directory and the rail are not one row.
  for (const [name, extra] of [
    ["Zatpat Technologies", { industry: "Cloud hosting", city: "Pune",
                              status: "ACTIVE" }],
    ["Contoso Placeholder", { industry: "Manufacturing", city: "Chennai",
                              status: "PROSPECTIVE" }],
    ["Fabrikam Placeholder", { industry: "Logistics", city: "Nagpur",
                               status: "INACTIVE" }],
    ["Adventure Placeholder", { industry: "Information technology",
                                city: "Mumbai", status: "ACTIVE" }],
  ] as const) {
    const made = await postOk(page, "/counterparties",
                              { name: `${name} ${stamp}`, ...extra });
    if (name === "Zatpat Technologies") {
      const c = await postOk(page, "/contracts", {
        name: "Terms of Service", contract_type: "TOS", counterparty_id: made.id,
      });
      const v = await upload(page, c.id);
      await patchOk(page, `/document-versions/${v.id}`,
                    { version_role: "FINAL_SIGNED" });
    }
  }

  // 1440×900 — a realistic laptop, which DESIGN.md's responsive principle makes
  // the primary target.
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/dashboard/clients");
  // Wait for ROWS, not just the heading: the first pass caught the skeleton and
  // the review had to be redone. A screenshot of a loading state proves nothing
  // about the layout it is standing in for.
  await expect(page.locator(".ws-cl__table tbody tr").first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "01-directory-1440.png"), fullPage: true });

  await page.goto(`/dashboard/clients?id=${client.id}`);
  await expect(page.getByRole("heading", { name: "Legal documents" })).toBeVisible();
  // ...and for the rail, which loads on its own debounce.
  await expect(page.locator(".ws-cl__raillist li").first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "02-workspace-1440.png"), fullPage: true });

  // The rail must stay compact and the workspace must get the rest.
  const railBox = await page.locator(".ws-cl__rail").boundingBox();
  const mainBox = await page.locator(".ws-cl__main").boundingBox();
  expect(railBox!.width).toBeLessThan(260);
  expect(mainBox!.width).toBeGreaterThan(railBox!.width * 3.5);

  // Versions open.
  await page.locator("tr", { hasText: "Master Services Agreement" }).first()
    .getByRole("button", { name: /3 versions/ }).click();
  await page.screenshot({ path: join(SHOTS, "03-versions-1440.png"), fullPage: true });

  for (const [tab, file] of [["Details", "04-details"], ["Notes", "05-notes"],
                             ["Activity", "06-activity"]] as const) {
    await page.getByRole("tab", { name: tab }).click();
    await page.screenshot({ path: join(SHOTS, `${file}-1440.png`), fullPage: true });
  }

  // The two disclosures.
  await page.getByRole("tab", { name: "Documents" }).click();
  await page.getByRole("button", { name: "+ Upload document" }).click();
  await page.screenshot({ path: join(SHOTS, "07-upload-1440.png"), fullPage: true });

  await page.goto("/dashboard/clients");
  await page.getByRole("button", { name: "+ Add client" }).click();
  await page.screenshot({ path: join(SHOTS, "08-addclient-1440.png"), fullPage: true });

  // A 1366×768 laptop — the short viewport the Dashboard audit called out.
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto(`/dashboard/clients?id=${client.id}`);
  await expect(page.locator(".ws-cl__raillist li").first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "09-workspace-1366.png") });

  // Tablet width: the rail becomes a strip, and nothing is dropped.
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.reload();
  await expect(page.locator(".ws-cl__raillist li").first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "10-workspace-1024.png"), fullPage: true });

  // The loading state, on purpose: it is what every visit begins with, and the
  // first review pass found it was a bare line of text in an empty viewport.
  await page.route("**/api/v1/counterparties?**", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.continue();
  });
  await page.goto("/dashboard/clients");
  await expect(page.locator(".ws-cl__table--skel")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "12-loading-1440.png") });
  await page.unroute("**/api/v1/counterparties?**");

  // An empty client — the state a reader meets most often on day one.
  const empty = await postOk(page, "/counterparties",
                             { name: `Empty Placeholder ${stamp}` });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/dashboard/clients?id=${empty.id}`);
  await expect(page.getByText("No legal documents for this client yet")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "11-empty-1440.png"), fullPage: true });
});
