import { expect, test } from "@playwright/test";

import { storageStatePath } from "./support";

// The control plane's own account: SUPER_ADMIN + LEGAL_ADMIN + USER — and,
// deliberately, no legal authority (Step 23; SEC-02).
test.use({ storageState: storageStatePath("admin") });

/**
 * Slice 7 — the admin plane in the new UI, against the real backend.
 *
 * The lifecycle a provisioner actually performs, in one pass: create an
 * account (born with NO roles — 47.1.3), grant one, revoke it, disable the
 * account — and then find the creation in the audit trail through the
 * allow-listed action filter.
 */

test.describe("users & roles", () => {
  test("an account is born with no roles; grant, revoke and disable all round-trip", async ({
    page,
  }) => {
    const email = `provisioned-${Date.now()}@e2e.test`;

    await page.goto("/workspace/admin");
    await expect(page.getByRole("heading", { name: "Admin" })).toBeVisible();
    await expect(page.locator('nav a[href="/workspace/admin"]')).toHaveAttribute(
      "aria-current",
      "page",
    );

    // Create — and the new row states its powerlessness plainly.
    await page.getByLabel(/Work email/).fill(email);
    await page.getByLabel(/^Name/).fill("Provisioned Account");
    await page.getByRole("button", { name: "Add account" }).click();
    const row = page.locator(`tr[data-user-email="${email}"]`);
    await expect(row).toBeVisible();
    await expect(row).toContainText("no roles — cannot act yet");

    // Grant USER: the chip appears and the empty-roles note goes.
    await row.getByLabel(`Role to grant to ${email}`).selectOption("USER");
    await row.getByRole("button", { name: "Grant" }).click();
    await expect(row.locator(".ws-rolechip")).toContainText("USER");
    await expect(row).not.toContainText("no roles — cannot act yet");

    // Revoke it again — the accessible name carries exactly what the × does.
    await row.getByRole("button", { name: `Revoke USER from ${email}` }).click();
    await expect(row).toContainText("no roles — cannot act yet");

    // Disable: the status chip flips and the action inverts to Restore.
    await row.getByRole("button", { name: "Disable" }).click();
    await expect(row).toContainText("DISABLED");
    await expect(row.getByRole("button", { name: "Restore" })).toBeVisible();

    // No page text ever grades anything here either.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
  });
});

test.describe("the audit trail", () => {
  test("events list newest first and the exact-value action filter narrows to them", async ({
    page,
  }) => {
    await page.goto("/workspace/admin/audit");
    await expect(page.getByRole("heading", { name: "Audit trail" })).toBeVisible();
    await expect(page.locator("tbody tr").first()).toBeVisible();

    // Exact-value filter (49.6): the user-creation events from this suite.
    await page.getByLabel("Action").fill("admin.user_created");
    await page.getByRole("button", { name: "Apply" }).click();
    const rows = page.locator("tbody tr");
    await expect(rows.first()).toBeVisible();
    for (const cell of await rows.locator("td:nth-child(2)").allInnerTexts()) {
      expect(cell).toBe("admin.user_created");
    }

    // A partial value matches nothing — stated, not erroring.
    await page.getByLabel("Action").fill("admin.user_");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByText("No events match.")).toBeVisible();
  });

  test("no admin plane for an account without the permissions", async ({ browser }) => {
    const context = await browser.newContext({ storageState: storageStatePath("owner") });
    const page = await context.newPage();
    await page.goto("/workspace/admin");
    await expect(page.getByText("Access restricted")).toBeVisible();
    await expect(page.locator('nav a[href="/workspace/admin"]')).toHaveCount(0);
    await context.close();
  });
});
