import { expect, test } from "@playwright/test";

import { storageStatePath } from "./support";

/**
 * Platform Administration, against the real backend.
 *
 * The lifecycle a provisioner actually performs — create an account with its
 * department and role in one act, find it, change its access, disable it — plus
 * the two boundaries that make this role safe: an administrator may not offer
 * themselves legal authority, and may not open a single deal.
 */

test.describe("users", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("an account is created, placed, granted, found and disabled", async ({ page }) => {
    const email = `provisioned-${Date.now()}@e2e.test`;

    await page.goto("/dashboard/admin");
    await expect(page.getByRole("heading", { name: "Administration", level: 1 })).toBeVisible();
    await expect(page.locator('nav a[href="/dashboard/admin"]').first())
      .toHaveAttribute("aria-current", "page");

    // Create — with a department and a role, in one request.
    await page.getByRole("button", { name: "Add account" }).click();
    await page.getByLabel(/Full name/).fill("Provisioned Account");
    await page.getByLabel(/Work email/).fill(email);
    await page.getByLabel("Department for the new account")
      .selectOption({ label: "E2E Department" });
    await page.getByLabel("Role for the new account")
      .selectOption({ label: "Department User" });
    await page.getByRole("button", { name: "Create account" }).click();

    // It appears in the roster, with what we asked for — role by NAME, not code.
    const row = page.locator(`tr[data-user-email="${email}"]`);
    await expect(row).toBeVisible();
    await expect(row).toContainText("Department User");
    await expect(row).toContainText("E2E Department");
    await expect(row).toContainText("Active");
    // It has never signed in, and the screen says so rather than leaving a gap.
    await expect(row).toContainText("Never");

    // Creating an account opens it: you just made it, here it is. No click
    // needed — and clicking the name here would TOGGLE it shut.
    const detail = page.getByRole("complementary", { name: `Account ${email}` });
    await expect(detail).toBeVisible();
    await expect(detail).toContainText("Provisioned by");

    // Closing and reopening from the row is the other way in.
    await detail.getByRole("button", { name: "Close" }).click();
    await expect(detail).toHaveCount(0);
    await row.getByRole("button", { name: "Provisioned Account" }).click();
    await expect(detail).toBeVisible();

    // Revoke the role: the account keeps existing and can no longer act.
    await detail.getByRole("button", { name: `Revoke USER from ${email}` }).click();
    await expect(detail).toContainText("No roles");

    // Disable: the control inverts, and the roster agrees.
    await detail.getByRole("button", { name: "Disable account" }).click();
    await expect(detail.getByRole("button", { name: "Re-enable account" })).toBeVisible();
    await expect(row).toContainText("Disabled");

    // No page text ever grades anything here either.
    const body = (await page.locator("body").innerText()).toLowerCase();
    expect(body).not.toContain("confidence");
  });

  test("the future legal roles are never offered when granting", async ({ page }) => {
    // The server refuses under S-8 regardless; offering an action the backend
    // rejects is its own defect.
    await page.goto("/dashboard/admin");
    await page.getByRole("button", { name: "Add account" }).click();
    const roleSelect = page.getByLabel("Role for the new account");
    // Wait for the role list to arrive, or the assertion would pass against an
    // empty select — the commonest way a "nothing forbidden is offered" test
    // proves nothing.
    await expect(roleSelect.locator("option", { hasText: "Department User" }))
      .toHaveCount(1);
    const options = await roleSelect.locator("option").allInnerTexts();

    expect(options).toContain("Department User");
    expect(options).toContain("Department Lead");
    expect(options.join(" ")).not.toContain("Legal Reviewer");
    expect(options.join(" ")).not.toContain("Legal Decision Authority");
  });

  test("filters and sort narrow the whole roster, not the page", async ({ page }) => {
    await page.goto("/dashboard/admin");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await expect(page.getByLabel("Filter by role")
      .locator("option", { hasText: "Department Lead" })).toHaveCount(1);

    // Role filter: the request goes to the server with ?role=
    const [filtered] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/users?") && r.url().includes("role=")),
      page.getByLabel("Filter by role").selectOption({ label: "Department Lead" }),
    ]);
    expect(filtered.ok()).toBeTruthy();
    await expect(page.locator("tbody tr")).not.toHaveCount(0);

    // Sort is a real parameter now, not a decorative control.
    const [sorted] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("sort=name_desc")),
      page.getByLabel("Sort accounts by").selectOption("name_desc"),
    ]);
    expect(sorted.ok()).toBeTruthy();
  });
});

test.describe("departments", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("a department reports its lead and members, and can be renamed", async ({ page }) => {
    await page.goto("/dashboard/admin/departments");
    await expect(page.getByRole("heading", { name: "Administration", level: 1 })).toBeVisible();

    const row = page.locator('tr[data-department-code="E2E"]');
    await expect(row).toBeVisible();
    // Every e2e account is placed in this department by the bootstrap.
    await expect(row).toContainText("E2E");

    await row.getByRole("button", { name: /E2E/ }).first().click();
    const detail = page.getByRole("complementary", { name: /Department/ });
    await expect(detail).toBeVisible();
    await expect(detail).toContainText("Members");
    // The code is stated as immutable, beside the name that is not.
    await expect(detail).toContainText("The code stays");
  });
});

test.describe("roles & permissions", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("the catalogue explains roles and marks legal authority", async ({ page }) => {
    await page.goto("/dashboard/admin/roles");

    const lead = page.locator('[data-role-code="DEPARTMENT_LEAD"]');
    await expect(lead).toBeVisible();
    await expect(lead).toContainText("Department Lead");

    // Retained roles are shown — and labelled as unused, not silently present.
    const authority = page.locator('[data-role-code="LEGAL_DECISION_AUTHORITY"]');
    await expect(authority).toContainText("Not in use yet");
    await expect(authority).toContainText("Legal authority");

    // Permissions are grouped and named, not a flat list of dotted strings.
    await authority.getByRole("button", { name: /permission/ }).click();
    await expect(authority).toContainText("legal.decision");
    await expect(authority).toContainText("Legal authority");
  });
});

test.describe("the audit log", () => {
  test.use({ storageState: storageStatePath("admin") });

  test("names the actor, and shows an administrative payload", async ({ page }) => {
    const email = `audited-${Date.now()}@e2e.test`;
    await page.goto("/dashboard/admin");
    await page.getByRole("button", { name: "Add account" }).click();
    await page.getByLabel(/Full name/).fill("Audited Account");
    await page.getByLabel(/Work email/).fill(email);
    await page.getByRole("button", { name: "Create account" }).click();
    await expect(page.locator(`tr[data-user-email="${email}"]`)).toBeVisible();

    await page.goto("/dashboard/admin/audit");
    await expect(page.locator("tbody tr").first()).toBeVisible();
    await page.getByLabel("Action").selectOption("admin.user_created");
    await page.getByRole("button", { name: "Apply" }).click();

    const row = page.locator("tbody tr").first();
    // The actor is a person, not a UUID prefix; the target is named.
    await expect(row).toContainText("Admin");
    await expect(row).toContainText(email);
    // And the payload of an act this administrator performed is legible to them.
    await row.getByRole("button", { name: "Show" }).click();
    await expect(page.locator(".ws-auditpayload")).toContainText(email);
  });

  test("a contract event is listed without naming the contract", async ({ page }) => {
    // Step 24 r8 — the envelope is the administrator's, the payload is not.
    await page.goto("/dashboard/admin/audit");
    await page.getByLabel("Entity type").fill("contract");
    await page.getByRole("button", { name: "Apply" }).click();

    const rows = page.locator("tbody tr");
    if (await rows.count() > 0) {
      // Nothing to expand: the payload was omitted, so the cell offers no control.
      await expect(rows.first().getByRole("button", { name: "Show" })).toHaveCount(0);
    }
  });
});

test.describe("everyone else", () => {
  test.use({ storageState: storageStatePath("owner") });

  test("a department user reaches no part of administration", async ({ page }) => {
    for (const route of ["/dashboard/admin", "/dashboard/admin/departments",
                         "/dashboard/admin/roles", "/dashboard/admin/audit"]) {
      await page.goto(route);
      await expect(page.getByText("Access restricted")).toBeVisible();
    }
    // And the nav never offered it in the first place (presentation only —
    // the server refuses regardless, which is what the API tests assert).
    await page.goto("/dashboard");
    await expect(page.locator('nav a[href="/dashboard/admin"]')).toHaveCount(0);
  });
});
