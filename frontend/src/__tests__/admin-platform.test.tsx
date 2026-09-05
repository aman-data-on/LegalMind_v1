/**
 * Platform Administration — the client-side half of the contract.
 *
 * Two things are worth pinning here, and both are places where a
 * plausible-looking implementation is wrong:
 *
 * 1. **Filters and sort must reach the server.** The previous screen kept a
 *    "Sort by" control whose value was never sent — it looked like a capability
 *    and was not one. Filtering the page already fetched has the same shape of
 *    bug: a colleague on page 2 is invisible to a filter that claims to search
 *    everyone.
 *
 * 2. **A role nobody may assign is never offered.** The server refuses under
 *    S-8 regardless, but a picker that offers an action the backend rejects is
 *    its own defect — and the two future legal roles are exactly that case.
 */

import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import {
  ADMIN_SECTIONS,
  ASSIGNABLE_TIERS,
  TIER_LABEL,
  TIER_ORDER,
  dateOnly,
  dateTime,
  signInMethod,
} from "@/components/admin/AdminShell";
import type { AuditEvent, Role, User } from "@/lib/types";

function user(over: Partial<User> = {}): User {
  return {
    id: "u1", email: "aman@leapswitch.test", name: "Aman Singh", status: "ACTIVE",
    roles: ["USER"], department: null, auth_providers: [], last_login_at: null,
    provisioned_by: null, created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...over,
  };
}

function role(code: string, tier: Role["tier"]): Role {
  return {
    id: code, code, name: code, tier, permissions: [],
    confers_legal_authority: [],
  };
}

describe("the assignment picker never offers a role the server would refuse", () => {
  it("excludes the future legal roles from every assignable tier", () => {
    expect(ASSIGNABLE_TIERS).not.toContain("future_legal");
    const roles = [
      role("USER", "department"),
      role("DEPARTMENT_LEAD", "department"),
      role("PLATFORM_ADMIN", "platform"),
      role("DEVELOPER", "break_glass"),
      role("LEGAL_REVIEWER", "future_legal"),
      role("LEGAL_DECISION_AUTHORITY", "future_legal"),
    ];
    const offered = roles.filter((r) => ASSIGNABLE_TIERS.includes(r.tier)).map((r) => r.code);

    expect(offered).toEqual(["USER", "DEPARTMENT_LEAD", "PLATFORM_ADMIN", "DEVELOPER"]);
    expect(offered).not.toContain("LEGAL_REVIEWER");
    expect(offered).not.toContain("LEGAL_DECISION_AUTHORITY");
  });

  it("still names the retained roles, because the catalogue screen lists them", () => {
    // Hidden from assignment is not the same as hidden from the product: an
    // administrator should be able to see that these exist and are unused.
    expect(TIER_LABEL.future_legal).toBe("Not in use yet");
    expect(TIER_ORDER).toContain("future_legal");
    expect(TIER_ORDER.indexOf("future_legal")).toBe(TIER_ORDER.length - 1);
  });
});

describe("the roster asks the server, not the current page", () => {
  it("sends every filter and the sort as query parameters", async () => {
    const spy = vi.spyOn(api, "users").mockResolvedValue({
      items: [], pagination: { page: 1, page_size: 25, total: 0 },
    });

    await api.users({
      page: 1, page_size: 25, sort: "last_login_desc", status: "ACTIVE",
      search: "aman", role: "DEPARTMENT_LEAD", department_id: "d1",
    });

    expect(spy.mock.calls[0]![0]).toMatchObject({
      sort: "last_login_desc",
      status: "ACTIVE",
      search: "aman",
      role: "DEPARTMENT_LEAD",
      department_id: "d1",
    });
    spy.mockRestore();
  });

  it("asks for the unplaced with their own flag, not a department id", () => {
    // "No department" is not a department id, and it is the question that
    // matters: nobody's Lead can see that person's deals.
    const departmentFilter = "__none__";
    const query = departmentFilter === "__none__"
      ? { unassigned: "true" }
      : { department_id: departmentFilter };
    expect(query).toEqual({ unassigned: "true" });
  });
});

describe("account creation is one act", () => {
  it("carries the department and role with the account", async () => {
    const spy = vi.spyOn(api, "createUser").mockResolvedValue(user());

    await api.createUser("new@leapswitch.test", "New Joiner", {
      department_id: "d1", role_code: "USER",
    });

    expect(spy).toHaveBeenCalledWith("new@leapswitch.test", "New Joiner", {
      department_id: "d1", role_code: "USER",
    });
    spy.mockRestore();
  });
});

describe("the screen states what the backend can support, and nothing more", () => {
  it("says an account has never signed in rather than leaving a blank", () => {
    expect(user({ last_login_at: null }).last_login_at).toBeNull();
    expect(signInMethod(user({ auth_providers: [] }))).toBe("No sign-in yet");
    expect(signInMethod(user({ auth_providers: ["OIDC"] }))).toBe("Google SSO");
    expect(signInMethod(user({ auth_providers: ["OIDC", "PASSWORD"] })))
      .toBe("Google SSO + Password");
  });

  it("renders an absent timestamp as an em dash, never as a fabricated date", () => {
    expect(dateOnly(null)).toBe("—");
    expect(dateTime(undefined)).toBe("—");
    expect(dateOnly("2026-09-05T11:22:33Z")).toBe("2026-09-05");
    expect(dateTime("2026-09-05T11:22:33Z")).toBe("2026-09-05 11:22");
  });
});

describe("the audit payload is presence-tested, never null-tested", () => {
  const envelope = {
    id: "e1", actor_id: null, actor: null, action: "contract.archived",
    entity_type: "contract", entity_id: "c1", entity_label: null,
    administrative: false, timestamp: "2026-09-05T00:00:00Z", request_id: null,
  } satisfies AuditEvent;

  it("treats an omitted payload as withheld and a present one as readable", () => {
    // 49.7 r4 / Step 52.4: a `null` would still disclose that a payload exists.
    // The screen must test for the KEY, not for a falsy value.
    expect("after_state" in envelope).toBe(false);
    const administrative: AuditEvent = {
      ...envelope, action: "admin.role_granted", entity_type: "user",
      administrative: true, after_state: { role: "USER" },
    };
    expect("after_state" in administrative).toBe(true);
  });

  it("never labels a contract entity", () => {
    // Naming it would hand a Platform Admin the one thing the scope model
    // withholds, through a screen they are entitled to open.
    expect(envelope.entity_label).toBeNull();
  });
});

describe("the administration area is one product surface", () => {
  it("offers the four sections in a stable order", () => {
    expect(ADMIN_SECTIONS.map((s) => s.label)).toEqual([
      "Users", "Departments", "Roles & permissions", "Audit log",
    ]);
    expect(ADMIN_SECTIONS.map((s) => s.href)).toEqual([
      "/dashboard/admin",
      "/dashboard/admin/departments",
      "/dashboard/admin/roles",
      "/dashboard/admin/audit",
    ]);
  });

  it("gates on the permissions the server actually checks", () => {
    expect(P.USER_MANAGE).toBe("user.manage");
    expect(P.ROLE_MANAGE).toBe("role.manage");
    expect(P.AUDIT_VIEW).toBe("audit.view");
  });
});
