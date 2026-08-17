/**
 * Permission-driven rendering and the error taxonomy — locked 52.1 r3, 52.3, 49.5,
 * 47.5, Step 23.
 *
 * Everything here is about *presentation*. Locked 52.1 r3: "Permission gating in
 * the UI is presentation only. Hiding a control is a usability affordance, never a
 * security control; the server authorizes every operation regardless."
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { ApiError, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";

describe("47.5 / Step 23 — legal authority is a separate, explicit grant", () => {
  it("offers no decision at all without legal.decision", () => {
    expect(P.submittableDecisionTypes([])).toEqual([]);
    // Holding legal.review does NOT confer it (Step 23: "when explicitly
    // permitted").
    expect(P.submittableDecisionTypes([P.LEGAL_REVIEW])).toEqual([]);
    // Nor does any administrative permission — Super Admin's whole grant set.
    expect(
      P.submittableDecisionTypes([P.USER_MANAGE, P.ROLE_MANAGE, P.AUDIT_VIEW]),
    ).toEqual([]);
  });

  it("withholds APPROVE_CUSTOMIZATION without the additional grant", () => {
    // 49.3 / 47.5 — required *in addition to* legal.decision.
    const types = P.submittableDecisionTypes([P.LEGAL_DECISION]);
    expect(types).toContain("ACCEPT_DEVIATION");
    expect(types).not.toContain("APPROVE_CUSTOMIZATION");
  });

  it("offers it with both grants", () => {
    const types = P.submittableDecisionTypes([
      P.LEGAL_DECISION,
      P.LEGAL_APPROVE_CUSTOMIZATION,
    ]);
    expect(types).toContain("APPROVE_CUSTOMIZATION");
  });

  it("offers exactly the five locked decision types and nothing else", () => {
    expect([...P.DECISION_TYPES]).toEqual([
      "ACCEPT_DEVIATION",
      "REQUIRE_COMPANY_STANDARD",
      "APPROVE_CUSTOMIZATION",
      "REJECT",
      "REQUEST_CLARIFICATION",
    ]);
  });
});

describe("52.3 — restricted sections and hidden controls", () => {
  it("renders an explicit restricted state, not an empty view", () => {
    const html = renderToStaticMarkup(<AccessRestricted what="the audit trail" />);
    expect(html).toContain("Access restricted");
    expect(html).toContain("the audit trail");
  });

  it("says nothing about the objects behind the section", () => {
    // Naming what is inside would be a disclosure, and for an out-of-scope object
    // there is nothing to name — the server returned a byte-identical 404.
    const html = renderToStaticMarkup(<AccessRestricted />);
    expect(html).not.toMatch(/\d+ (contract|review|finding)/i);
    expect(html).toContain("checked on the server");
  });

  it("renders nothing for a control the user cannot invoke", () => {
    const hidden = renderToStaticMarkup(
      <PermissionGate granted={false}>
        <button type="button">Record decision</button>
      </PermissionGate>,
    );
    expect(hidden).toBe("");
    const shown = renderToStaticMarkup(
      <PermissionGate granted>
        <button type="button">Record decision</button>
      </PermissionGate>,
    );
    expect(shown).toContain("Record decision");
  });
});

describe("49.5 / 52.4 — the error taxonomy as the user sees it", () => {
  const error = (status: number, code: string, message: string) =>
    new ApiError(status, code, message, "req-1");

  it("phrases a 404 so it cannot be read as out-of-scope", () => {
    // 49.5 r1 makes the two byte-identical on the wire. Wording such as "you do not
    // have access to this Review" would hand the disclosure back at the last step.
    const text = describeError(error(404, "NOT_FOUND", "The requested resource was not found."));
    expect(text).toBe("Not found.");
    expect(text).not.toMatch(/access|permission|yours|scope/i);
  });

  it("distinguishes 401 from 403", () => {
    expect(error(401, "UNAUTHENTICATED", "x").isUnauthenticated).toBe(true);
    expect(error(403, "FORBIDDEN", "x").isForbidden).toBe(true);
    expect(describeError(error(401, "UNAUTHENTICATED", "x"))).toMatch(/sign in/i);
  });

  it("treats 409 as a real outcome, not a retryable glitch", () => {
    // 52.7 — a version collision is meaningful, which is why optimistic UI is
    // forbidden for decisions.
    expect(error(409, "DECISION_VERSION_CONFLICT", "x").isConflict).toBe(true);
  });

  it("surfaces a 429 without describing the limit", () => {
    // 49.10 — no detail about the limit's shape.
    const text = describeError(error(429, "RATE_LIMITED", "Too many requests."));
    expect(text).toMatch(/try again/i);
    expect(text).not.toMatch(/\d+\s*(per|\/)\s*(second|minute|hour)/i);
  });

  it("never surfaces a raw failure as a legal statement", () => {
    expect(describeError(new TypeError("network down"))).toBe(
      "The request could not be completed.",
    );
  });
});

describe("permission names match the locked Step 47 catalogue", () => {
  it("carries the three Step 23 names verbatim", () => {
    expect(P.LEGAL_REVIEW).toBe("legal.review");
    expect(P.LEGAL_DECISION).toBe("legal.decision");
    expect(P.LEGAL_APPROVE_CUSTOMIZATION).toBe("legal.approve_customization");
  });

  it("keeps legal_position.view distinct from legal.review", () => {
    // LEGAL-02 gates internal legal position; legal.review is workflow authority.
    // Conflating them would show thresholds to a reviewer who may not see them.
    expect(P.LEGAL_POSITION_VIEW).toBe("legal_position.view");
    expect(P.LEGAL_POSITION_VIEW).not.toBe(P.LEGAL_REVIEW);
  });
});
