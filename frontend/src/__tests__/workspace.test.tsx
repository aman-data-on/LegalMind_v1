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
  activeNavHref,
  pickVersion,
  groupByPage,
  locationLabel,
  navItemsFor,
  outlineOf,
  readiness,
} from "@/components/workspace/model";
import { TranscriptTurn } from "@/components/workspace/TranscriptTurn";
import { ResearchPlaceholder } from "@/components/workspace/ResearchPlaceholder";
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
  it("an ordinary user sees the three built destinations, all in the new UI — never /contracts", () => {
    const user = new Set([P.CONTRACT_VIEW, P.REVIEW_VIEW, P.ASSIST_ASK]);
    const items = navItemsFor((p) => user.has(p));
    expect(items).toEqual([
      { href: "/workspace", label: "Documents" },
      { href: "/workspace/reviews", label: "Reviews" },
      { href: "/workspace/ask", label: "Ask history" },
      { href: "/workspace/research", label: "Research" },
    ]);
  });

  it("the active item is the LONGEST matching href, so Documents never lights on a sibling screen", () => {
    const items = navItemsFor(() => true);
    expect(activeNavHref("/workspace", items)).toBe("/workspace");
    expect(activeNavHref("/workspace/0a1b2c3d-0000-4000-8000-000000000000", items)).toBe("/workspace");
    expect(activeNavHref("/workspace/reviews", items)).toBe("/workspace/reviews");
    expect(activeNavHref("/workspace/reviews/0a1b2c3d", items)).toBe("/workspace/reviews");
    expect(activeNavHref("/workspace/ask/0a1b2c3d", items)).toBe("/workspace/ask");
    expect(activeNavHref("/login", items)).toBeNull();
  });

  it("legal.review adds the Legal queue — and only that permission does", () => {
    const counsel = new Set([P.CONTRACT_VIEW, P.REVIEW_VIEW, P.LEGAL_REVIEW, P.ASSIST_ASK]);
    const items = navItemsFor((p) => counsel.has(p));
    expect(items.map((i) => i.href)).toEqual([
      "/workspace",
      "/workspace/reviews",
      "/workspace/legal",
      "/workspace/ask",
      "/workspace/research",
    ]);
    expect(activeNavHref("/workspace/legal", items)).toBe("/workspace/legal");
  });

  it("a super admin sees Admin — the new-UI control plane — and nothing legacy", () => {
    const admin = new Set([P.AUDIT_VIEW, P.USER_MANAGE]);
    expect(navItemsFor((p) => admin.has(p))).toEqual([
      { href: "/workspace/admin", label: "Admin" },
    ]);
  });

  it("no nav item ever points at a legacy route", () => {
    const everyone = new Set([
      P.CONTRACT_VIEW, P.REVIEW_VIEW, P.LEGAL_REVIEW, P.ASSIST_ASK,
      P.CONFIGURATION_VIEW, P.AUDIT_VIEW, P.USER_MANAGE,
    ]);
    for (const item of navItemsFor((p) => everyone.has(p))) {
      expect(item.href).not.toMatch(/^\/(contracts|reviews|configuration|audit|admin)(\/|$)/);
    }
  });
});

describe("pickVersion (the ?version= lifecycle, 2026-08-31)", () => {
  const versions = [{ id: "v2" }, { id: "v1" }]; // newest first, as the API lists them
  it("opens the requested version when it belongs to this contract", () => {
    expect(pickVersion(versions, "v1")).toEqual({ id: "v1" });
  });
  it("falls back to the latest for no request, a stale id, or a foreign id", () => {
    expect(pickVersion(versions, null)).toEqual({ id: "v2" });
    expect(pickVersion(versions, "gone")).toEqual({ id: "v2" });
    expect(pickVersion([], "v1")).toBeNull();
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

describe("TranscriptTurn (ask history replay)", () => {
  const base = { id: "m1", ordinal: 1, routed_to_evaluator: false, citations: [] as never[] };

  it("a refusal replays on the quiet surface with its state attribute, exactly like the live pane", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn
        contractId="c1"
        turn={{ ...base, role: "ASSISTANT", content: "Information not found in the selected document.", answer_state: "NO_EVIDENCE_RETRIEVED" }}
      />,
    );
    expect(html).toContain("ws-ask__answer--refusal");
    expect(html).toContain('data-state="NO_EVIDENCE_RETRIEVED"');
    expect(html.toLowerCase()).not.toContain("confidence");
  });

  it("an ANSWERED turn's citation is a real link into the workspace highlight, and a null score renders nothing", () => {
    const citation = {
      chunk_id: "ch1", evidence_id: "ev1", page_number: 4, section_ref: "17.2",
      excerpt: "Liability shall not exceed…", retrieval_score: null,
    };
    const html = renderToStaticMarkup(
      <TranscriptTurn
        contractId="c1"
        turn={{ ...base, role: "ASSISTANT", content: "The cap is…", answer_state: "ANSWERED", citations: [citation] }}
      />,
    );
    expect(html).toContain('href="/workspace/c1?evidence=ev1"');
    expect(html).toContain("§17.2");
    // Null score → the score line is absent entirely, never "NaN" or a blank label.
    expect(html).not.toContain("retrieval score");
    // With a score, it renders labeled as exactly that (AI-03 item 16).
    const scored = renderToStaticMarkup(
      <TranscriptTurn
        contractId="c1"
        turn={{ ...base, role: "ASSISTANT", content: "The cap is…", answer_state: "ANSWERED", citations: [{ ...citation, retrieval_score: 0.8123 }] }}
      />,
    );
    expect(scored).toContain("retrieval score 0.812");
  });

  it("a user turn is the question, plainly attributed", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn contractId={null} turn={{ ...base, role: "USER", content: "What is the cap?", answer_state: null }} />,
    );
    expect(html).toContain("What is the cap?");
    expect(html).toContain("ws-turn--user");
  });
});

describe("ResearchPlaceholder (the one disclosed placeholder — C-16)", () => {
  it("discloses without teasing: no link, no button, no input, no fake search", () => {
    const html = renderToStaticMarkup(<ResearchPlaceholder />);
    expect(html).toContain("available yet");
    expect(html).toContain("C-16");
    expect(html).not.toContain("<a ");
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<input");
  });
});
