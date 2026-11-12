import { describe, expect, it } from "vitest";

import { actionWords } from "@/components/admin/AdminShell";

describe("actionWords — an audit action in plain words (B3 p2)", () => {
  it("says the known ones plainly and every other code as words, never the raw code", () => {
    expect(actionWords("auth.login_succeeded")).toBe("Signed in");
    expect(actionWords("admin.role_granted")).toBe("Role granted");
    expect(actionWords("contract.read_via_department_scope")).toBe("Opened a contract");
    expect(actionWords("assist.generation_called")).toBe("Ask: generation called");
    expect(actionWords("review.reopened")).toBe("Review: reopened");
    for (const code of ["auth.logout", "config.published", "authz.permission_denied"]) {
      expect(actionWords(code)).not.toMatch(/[a-z]\.[a-z]|_/);
    }
  });
});
