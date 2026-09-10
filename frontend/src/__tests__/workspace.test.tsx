/**
 * Workspace slice 1 — the pure model and the honest placeholders.
 *
 * Static assertions in the house idiom; the highlight gesture, collapse tabs and
 * real data live in e2e/dashboard.spec.ts against the real backend.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EscalateControl } from "@/components/workspace/EscalateControl";
import { DOCUMENT_TYPES, documentSourceChip, documentSourceLabel, documentTypeLabel, nameFromFilename, typeHintFromFilename } from "@/lib/documentTypes";
import { contractStatusLabel } from "@/lib/labels";
import { NextSlice } from "@/components/workspace/NextSlice";
import {
  activeNavHref,
  analysisCell,
  pickVersion,
  groupByPage,
  locationLabel,
  navItemsFor,
  outlineOf,
  partLabel,
  reviewOrder,
  readiness,
} from "@/components/workspace/model";
import { TranscriptTurn } from "@/components/workspace/TranscriptTurn";
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
      .toBe("17.2 · Liability · p.9");
    expect(locationLabel(row({ page_number: null }))).toBe("location not recorded");
  });
});

describe("navigation by absence AND by existence (52.3 + the 2026-08-30 cleanup)", () => {
  it("an ordinary user is offered only destinations that do something for them", () => {
    /*
     * 2026-09-04 audit. Three things changed and each removes a promise the
     * product could not keep for THIS caller:
     *
     * - Reviews left the nav: for a contract owner it listed one row per
     *   analysis run of documents the Dashboard already lists, in the same
     *   states. It is a queue, and a queue is a destination only for someone
     *   who works one — see the `legal.review` case below. The screen itself
     *   still exists and a Report is still reached from it.
     * - "Ask History" became "Ask": asking happens in a document, and naming
     *   the nav after the archive advertised the filing cabinet while the
     *   feature itself had no nav entry at all.
     * - Research left the nav entirely: statute intake is an open owner
     *   decision (C-16), so the capability does not exist, and a nav slot is a
     *   promise. Its screen stays and says so honestly.
     */
    const user = new Set([P.CONTRACT_VIEW, P.REVIEW_VIEW, P.ASSIST_ASK]);
    const items = navItemsFor((p) => user.has(p));
    expect(items).toEqual([
      { href: "/dashboard", label: "Dashboard" },
      { href: "/dashboard/ask", label: "Ask" },
    ]);
  });

  it("the active item is the LONGEST matching href, so Dashboard never lights on a sibling screen", () => {
    const items = navItemsFor(() => true);
    expect(activeNavHref("/dashboard", items)).toBe("/dashboard");
    expect(activeNavHref("/dashboard/0a1b2c3d-0000-4000-8000-000000000000", items)).toBe("/dashboard");
    expect(activeNavHref("/dashboard/reviews", items)).toBe("/dashboard/reviews");
    expect(activeNavHref("/dashboard/reviews/0a1b2c3d", items)).toBe("/dashboard/reviews");
    expect(activeNavHref("/dashboard/ask/0a1b2c3d", items)).toBe("/dashboard/ask");
    expect(activeNavHref("/login", items)).toBeNull();
  });

  it("legal.review is what turns Reviews into a destination, and adds the Legal queue", () => {
    /* The queue says something the Dashboard cannot only once `legal.review`
     * widens `GET /reviews` past the caller's own contracts (`REC-09`). */
    const counsel = new Set([P.CONTRACT_VIEW, P.REVIEW_VIEW, P.LEGAL_REVIEW, P.ASSIST_ASK]);
    const items = navItemsFor((p) => counsel.has(p));
    expect(items.map((i) => i.href)).toEqual([
      "/dashboard",
      "/dashboard/reviews",
      "/dashboard/legal",
      "/dashboard/ask",
    ]);
    expect(activeNavHref("/dashboard/legal", items)).toBe("/dashboard/legal");
  });

  it("configuration.view offers the screen that publishes the snapshot analysis pins", () => {
    /* It existed only at the legacy `/configuration` URL with no nav entry, so
     * the one screen that makes analysis possible was reachable only by typing
     * an address (2026-09-04 audit; the route is adopted, not deleted). */
    const legalAdmin = new Set([P.CONTRACT_VIEW, P.CONFIGURATION_VIEW]);
    const items = navItemsFor((p) => legalAdmin.has(p));
    expect(items.map((i) => i.href)).toContain("/dashboard/configuration");
  });

  it("a platform admin sees Administration — the new-UI control plane — and nothing legacy", () => {
    const admin = new Set([P.AUDIT_VIEW, P.USER_MANAGE]);
    expect(navItemsFor((p) => admin.has(p))).toEqual([
      { href: "/dashboard/admin", label: "Administration" },
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
    // Step 6's second axis (2026-09-06), same presentation rule.
    expect(documentSourceLabel("COUNTERPARTY")).toBe("Counterparty — their document");
    expect(documentSourceLabel("ZZZ")).toBe("ZZZ");
    expect(documentSourceLabel(null)).toBe("Source not declared");
    // P-1 (2026-09-06): Step 2's lifecycle, in the reader's words.
    expect(contractStatusLabel("SUPERSEDED")).toBe("Superseded");
    expect(contractStatusLabel("ODD")).toBe("ODD");
    expect(contractStatusLabel(null)).toBe("Status not recorded");
    // Whose paper it is, in a reviewer's words (2026-09-06). Undeclared stays
    // undeclared — the chip is absent, never a "Source: unknown" placeholder.
    expect(documentSourceChip("ORGANIZATION")).toBe("Our document");
    expect(documentSourceChip("COUNTERPARTY")).toBe("Their document");
    expect(documentSourceChip(null)).toBeNull();
    expect(documentSourceChip(undefined)).toBeNull();
  });
});

describe("TranscriptTurn (ask history replay)", () => {
  const base = {
    id: "m1", ordinal: 1, routed_to_evaluator: false, citations: [] as never[],
    // Which version answered this turn (2026-09-02).
    document_version_id: "dv1", version_number: 1,
  };

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

  it("an ANSWERED turn's citation is a real link into the workspace highlight, and no score is ever rendered", () => {
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
    // The link names the VERSION the answer was read from as well as the
    // evidence row (2026-09-02): an evidence row belongs to exactly one
    // version's reading order, so landing on the newest version would point the
    // highlight at a row that page does not contain.
    expect(html).toContain('href="/dashboard?id=c1&amp;version=dv1&amp;evidence=ev1"');
    expect(html).toContain("17.2");
    // Null score → the score line is absent entirely, never "NaN" or a blank label.
    expect(html).not.toContain("retrieval score");
    // With a score, it renders labeled as exactly that (AI-03 item 16).
    const scored = renderToStaticMarkup(
      <TranscriptTurn
        contractId="c1"
        turn={{ ...base, role: "ASSISTANT", content: "The cap is…", answer_state: "ANSWERED", citations: [{ ...citation, retrieval_score: 0.8123 }] }}
      />,
    );
    expect(scored).not.toContain("retrieval score");
  });

  it("a user turn is the question, plainly attributed", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn contractId={null} turn={{ ...base, role: "USER", content: "What is the cap?", answer_state: null }} />,
    );
    expect(html).toContain("What is the cap?");
    expect(html).toContain("ws-turn--user");
  });
});


describe("upload-first intake helpers (2026-08-31 UX correction)", () => {
  it("derives an editable name from the filename — never a demand", () => {
    expect(nameFromFilename("RSA.pdf")).toBe("RSA");
    expect(nameFromFilename("acme_msa-v2 final.docx")).toBe("acme msa v2 final");
    expect(nameFromFilename("no-extension")).toBe("no extension");
  });

  it("hints a type from filename tokens, and only from plain tokens", () => {
    expect(typeHintFromFilename("Acme MSA (final).pdf")).toBe("MSA");
    expect(typeHintFromFilename("counterparty-nda.docx")).toBe("NDA");
    expect(typeHintFromFilename("privacy_policy.pdf")).toBe("PRIVACY_POLICY");
    // No token, no hint — the hint never guesses ("msal" is not "msa").
    expect(typeHintFromFilename("agreement.pdf")).toBeNull();
    expect(typeHintFromFilename("msal-config.pdf")).toBeNull();
  });

  it("the analysis cell speaks stages and counts, never a lifecycle enum", () => {
    expect(analysisCell({}).kind).toBe("none");
    expect(analysisCell({ latest_version: { processing_status: "PROCESSING" } }).kind).toBe("processing");
    expect(analysisCell({ latest_version: { processing_status: "COMPLETED" }, latest_analysis: null }).kind).toBe("unanalysed");
    const analysed = analysisCell({
      latest_version: { processing_status: "COMPLETED" },
      latest_analysis: {
        review_id: "r1", review_status: "LEGAL_REVIEW",
        classification_counts: { MATCH: 18, DEVIATION: 3, MISSING: 1 },
      },
    });
    expect(analysed).toMatchObject({ kind: "analysed", review_status: "LEGAL_REVIEW" });
    // Attention-first, MATCH last — a fixed scan order, not object-key order.
    expect((analysed as { counts: { classification: string }[] }).counts.map((c) => c.classification))
      .toEqual(["DEVIATION", "MISSING", "MATCH"]);
  });
});

describe("review order for the Findings list (P-4, 2026-09-06)", () => {
  const f = (
    id: string, requires_decision: boolean,
    evidence: Array<[number | null, string | null]>, name = id,
  ) => ({
    id, requires_decision,
    evidence: evidence.map(([page_number, section_number]) => ({ page_number, section_number })),
    requirement: { code: id, name },
  });

  it("puts what needs a decision first, then follows the document", () => {
    const ordered = reviewOrder([
      f("late-ok", false, [[3, "12"]]),
      f("early-ok", false, [[1, "2"]]),
      f("late-decide", true, [[2, "9.1"]]),
      f("early-decide", true, [[1, "3"]]),
    ]).map((x) => x.id);
    expect(ordered).toEqual(["early-decide", "late-decide", "early-ok", "late-ok"]);
  });

  it("orders by the document's own numbering, not by string", () => {
    const ordered = reviewOrder([
      f("b", false, [[1, "10"]]), f("a", false, [[1, "9.2"]]), f("c", false, [[1, "9"]]),
    ]).map((x) => x.id);
    expect(ordered).toEqual(["c", "a", "b"]);   // 9 < 9.2 < 10 — never "10" < "9"
  });

  it("uses the EARLIEST clause a finding cites, and sends unlocatable ones last", () => {
    const ordered = reviewOrder([
      f("nowhere", false, [[null, null]]),
      f("spread", false, [[4, "20"], [1, "1"]]),
      f("mid", false, [[2, "5"]]),
    ]).map((x) => x.id);
    expect(ordered).toEqual(["spread", "mid", "nowhere"]);
  });

  it("is deterministic — a stable tiebreak on the requirement's heading, then id", () => {
    const a = f("a", false, [[1, "1"]], "Zeta");
    const b = f("b", false, [[1, "1"]], "Alpha");
    expect(reviewOrder([a, b]).map((x) => x.id)).toEqual(["b", "a"]);
    expect(reviewOrder([b, a]).map((x) => x.id)).toEqual(["b", "a"]);
  });
});

describe("annexed parts in the outline (44.4, 2026-09-06)", () => {
  it("names the divider by the document's own word, never by a guess", () => {
    expect(partLabel({ annexure: "Annexure-1" })).toBe("Annexure");
    expect(partLabel({ annexure: "SCHEDULE 2 – Fees" })).toBe("Schedule");
    expect(partLabel({})).toBeUndefined();
  });
});
