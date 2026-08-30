/**
 * Workspace slice 1 — the pure model and the honest placeholders.
 *
 * Static assertions in the house idiom; the highlight gesture, collapse tabs and
 * real data live in e2e/workspace.spec.ts against the real backend.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EscalateControl } from "@/components/workspace/EscalateControl";
import { DOCUMENT_TYPES, documentTypeLabel } from "@/lib/documentTypes";
import { NextSlice } from "@/components/workspace/NextSlice";
import {
  groupByPage,
  locationLabel,
  navItemsFor,
  outlineOf,
  readiness,
} from "@/components/workspace/model";
import * as P from "@/lib/permissions";
import type { EvidenceRow } from "@/lib/types";

function row(overrides: Partial<EvidenceRow>): EvidenceRow {
  return {
    id: "e",
    document_version_id: "v",
    page_number: 1,
    section_number: null,
    section_title: null,
    content: "text",
    source_type: "NATIVE",
    start_offset: 0,
    end_offset: 4,
    ...overrides,
  };
}

describe("readiness from counts", () => {
  it("derives the three plain states and never invents a fourth", () => {
    expect(readiness(undefined)).toBe("not-indexed");
    expect(readiness({ chunks: 0, embedded_chunks: 0 })).toBe("not-indexed");
    expect(readiness({ chunks: 12, embedded_chunks: 0 })).toBe("lexical-only");
    expect(readiness({ chunks: 12, embedded_chunks: 12 })).toBe("ready");
  });
});

describe("reading order", () => {
  it("groups consecutive rows by page and keeps unnumbered rows as their own group", () => {
    const groups = groupByPage([
      row({ id: "a", page_number: 1 }),
      row({ id: "b", page_number: 1 }),
      row({ id: "c", page_number: 2 }),
      row({ id: "d", page_number: null }),
    ]);
    expect(groups.map((g) => [g.page, g.rows.length])).toEqual([[1, 2], [2, 1], [null, 1]]);
  });

  it("the outline is exactly the rows that carry a clause reference", () => {
    const rows = [
      row({ id: "a", section_number: "17.2" }),
      row({ id: "b" }),
      row({ id: "c", section_title: "Definitions" }),
    ];
    expect(outlineOf(rows).map((r) => r.id)).toEqual(["a", "c"]);
  });

  it("labels a location from whatever the parser recorded", () => {
    expect(locationLabel(row({ section_number: "17.2", section_title: "Liability", page_number: 9 })))
      .toBe("§17.2 · Liability · p.9");
    expect(locationLabel(row({ page_number: null }))).toBe("location not recorded");
  });
});

describe("navigation by absence AND by existence (52.3 + the 2026-08-30 cleanup)", () => {
  it("an ordinary user sees Documents, pointed at the new UI — never /contracts", () => {
    const user = new Set([P.CONTRACT_VIEW, P.REVIEW_VIEW, P.ASSIST_ASK]);
    const items = navItemsFor((p) => user.has(p));
    expect(items).toEqual([{ href: "/workspace", label: "Documents" }]);
  });

  it("a super admin sees an empty nav — Audit/Admin have no new-UI screen yet, so no legacy link is offered", () => {
    const admin = new Set([P.AUDIT_VIEW, P.USER_MANAGE]);
    expect(navItemsFor((p) => admin.has(p))).toEqual([]);
  });

  it("no nav item ever points at a legacy route", () => {
    const everyone = new Set([
      P.CONTRACT_VIEW, P.REVIEW_VIEW, P.CONFIGURATION_VIEW, P.AUDIT_VIEW, P.USER_MANAGE,
    ]);
    for (const item of navItemsFor((p) => everyone.has(p))) {
      expect(item.href).not.toMatch(/^\/(contracts|reviews|configuration|audit|admin)(\/|$)/);
    }
  });
});

describe("NextSlice", () => {
  it("names the pane, says it is not built, and carries no link anywhere — including into the legacy app", () => {
    const html = renderToStaticMarkup(
      <NextSlice title="Findings" note="Findings still work in the current application while this pane is built." />,
    );
    expect(html).toContain("Findings");
    expect(html).toContain("later build slice");
    expect(html).toContain("still work in the current application");
    // The 2026-08-30 cleanup rule, pinned structurally: no anchor, no button, no input.
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<input");
  });

  it("the note is optional", () => {
    const html = renderToStaticMarkup(<NextSlice title="Ask" />);
    expect(html).toContain("Ask");
    expect(html).not.toContain("<a ");
  });
});

describe("EscalateControl", () => {
  it("is a real <button> for keyboard/AT operability, but never styled like a decision control", () => {
    const html = renderToStaticMarkup(
      <EscalateControl
        finding={{ id: "f1", review_id: "r1", requirement: { code: "LIABILITY-001", name: null, version_id: "v", version_number: 1 }, classification: "DEVIATION", status: "OPEN", requires_decision: true, escalated: false, evaluations: [], evidence: [], created_at: null, updated_at: null }}
        onChanged={() => {}}
      />,
    );
    expect(html).toContain("Escalate for authorized review");
    expect(html).toContain("<button");
    // Quiet register (master prompt: escalation is visually distinct from a
    // decision) — never the primary-button class the decision control uses.
    expect(html).not.toContain("ws-btn--primary");
    expect(html).not.toContain('class="ws-btn"');
  });

  it("shows the withdraw option once escalated, worded as a request not an approval", () => {
    const html = renderToStaticMarkup(
      <EscalateControl
        finding={{ id: "f1", review_id: "r1", requirement: { code: "LIABILITY-001", name: null, version_id: "v", version_number: 1 }, classification: "DEVIATION", status: "LEGAL_REVIEW", requires_decision: true, escalated: true, evaluations: [], evidence: [], created_at: null, updated_at: null }}
        onChanged={() => {}}
      />,
    );
    expect(html).toContain("a request, not an approval");
    expect(html).toContain("Withdraw");
  });
});

describe("Step 6 document types (presentation copy)", () => {
  it("carries exactly the ten locked codes, in the backend's order", () => {
    expect(DOCUMENT_TYPES.map((t) => t.code)).toEqual([
      "MSA", "NDA", "TOS", "SLA", "DPA", "AUP", "PRIVACY_POLICY", "ORDER_FORM", "AMENDMENT", "OTHER",
    ]);
  });
  it("labels a known code and never invents one for an unknown or missing value", () => {
    expect(documentTypeLabel("SLA")).toBe("Service Level Agreement");
    expect(documentTypeLabel("ZZZ")).toBe("ZZZ");
    expect(documentTypeLabel(null)).toBe("Type not declared");
  });
});
