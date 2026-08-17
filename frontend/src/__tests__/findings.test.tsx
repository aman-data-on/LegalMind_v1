/**
 * The Review surface — locked 52.5, 49.7 r1/r2/r3, rule 14, Step 30 r8.
 *
 * 52.5 is the section these defend: a Finding shows its derived classification
 * **and** its Evaluations, is never presented as a single verdict, and cannot be
 * resolved while a scoped Evaluation still lacks a decision.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EvidenceList, formatLocation } from "@/components/EvidenceList";
import { FindingCard } from "@/components/FindingCard";
import type { Evaluation, Evidence, Finding } from "@/lib/types";

function evaluation(overrides: Partial<Evaluation> = {}): Evaluation {
  return {
    id: "e1",
    finding_id: "f1",
    scope_key: "AGGREGATE",
    scope_label: null,
    evaluation_kind: "PRIMARY",
    classification: "MATCH",
    actual_value: { months: 12 },
    evaluated_facts: null,
    evidence_refs: ["ev1"],
    diagnostics: [],
    evaluator_type: "NUMERIC_COMPARISON",
    evaluator_version: "LIABILITY-EVALUATOR-v1",
    requires_decision: false,
    current_decision: null,
    created_at: null,
    ...overrides,
  };
}

function finding(overrides: Partial<Finding> = {}): Finding {
  return {
    id: "f1",
    review_id: "r1",
    requirement: {
      code: "LIABILITY-001",
      name: "Limitation of Liability",
      version_id: "rv1",
      version_number: 1,
    },
    classification: "DEVIATION",
    status: "DECISION_REQUIRED",
    requires_decision: true,
    escalated: false,
    evaluations: [evaluation()],
    evidence: [],
    created_at: null,
    updated_at: null,
    ...overrides,
  };
}

describe("49.7 r1 — classification never appears without its Evaluations", () => {
  it("renders both together", () => {
    const html = renderToStaticMarkup(<FindingCard finding={finding()} />);
    expect(html).toContain("DEVIATION");
    expect(html).toContain("AGGREGATE");
    expect(html).toContain("evaluations");
  });

  it("labels the classification as a derived summary", () => {
    // D-1.1 — the scoped Evaluations are authoritative; the Finding value is a
    // summary. If the UI presented it as the verdict, the whole AB-1 model would be
    // invisible to the person deciding.
    const html = renderToStaticMarkup(<FindingCard finding={finding()} />);
    expect(html).toContain("derived summary");
  });

  it("shows every scoped Evaluation, including the exception", () => {
    // The locked 45C shape: an aggregate cap that conforms plus a category
    // exception that does not. This is the "hidden carve-out" case — if only the
    // aggregate were shown, a reviewer would approve a contract whose exception is
    // unacceptable.
    const html = renderToStaticMarkup(
      <FindingCard
        finding={finding({
          evaluations: [
            evaluation({ id: "agg", scope_key: "AGGREGATE", classification: "MATCH" }),
            evaluation({
              id: "cat",
              scope_key: "CATEGORY",
              scope_label: "confidentiality breach",
              evaluation_kind: "EXCEPTION",
              classification: "DEVIATION",
              requires_decision: true,
            }),
          ],
        })}
      />,
    );
    expect(html).toContain("AGGREGATE");
    expect(html).toContain("CATEGORY");
    expect(html).toContain("confidentiality breach");
    expect(html).toContain("evaluation--attention");
  });

  it("reports a Finding with no Evaluations as a defect, not an empty state", () => {
    // EV-MIN (AB-1.6) makes this unreachable; if it ever renders, showing the
    // classification alone would be the exact thing r1 forbids.
    const html = renderToStaticMarkup(<FindingCard finding={finding({ evaluations: [] })} />);
    expect(html).toContain("should not be possible");
  });
});

describe("49.7 r2 — no Finding-level rule outcome", () => {
  it("renders no rule outcome for the Finding itself", () => {
    const html = renderToStaticMarkup(
      <FindingCard finding={finding({ evaluations: [evaluation({ rule_outcome: "ACCEPTABLE" })] })} />,
    );
    // The outcome appears once, on the Evaluation — not on the Finding header.
    const header = html.slice(0, html.indexOf("evaluations"));
    expect(header).not.toContain("ACCEPTABLE");
  });
});

describe("rule 14 / Step 30 r8 — RESOLVED is not MATCH", () => {
  it("a resolved Finding still displays its original classification", () => {
    const html = renderToStaticMarkup(
      <FindingCard finding={finding({ status: "RESOLVED", classification: "DEVIATION" })} />,
    );
    expect(html).toContain("RESOLVED");
    expect(html).toContain("DEVIATION");
    // The two are separate axes (REC-06) and must never be collapsed into one, so
    // the Finding header carries both and neither is rewritten into the other.
    const header = html.slice(0, html.indexOf("finding__note"));
    expect(header).toContain("RESOLVED");
    expect(header).toContain("DEVIATION");
    expect(header).not.toContain("MATCH");
  });
});

describe("49.7 r3 / 45C.15 — evidence may legitimately be empty", () => {
  it("states absence rather than rendering a gap", () => {
    const html = renderToStaticMarkup(<EvidenceList evidence={[]} />);
    expect(html).toContain("No supporting text was found");
    // Never an error, and never a fabricated extract (45C.25).
    expect(html).not.toContain("error");
  });

  it("shows the document location with each extract", () => {
    // 52.6 — "Evidence viewer with document location". "The clause says six months"
    // is not evidence; "clause 11.2, page 14 says six months" is.
    const item: Evidence = {
      id: "ev1",
      relationship_type: "PRIMARY",
      page_number: 14,
      section_number: "11.2",
      section_title: "Limitation of Liability",
      content: "Aggregate liability shall not exceed fees paid in the prior 12 months.",
      source_type: "NATIVE_TEXT",
    };
    expect(formatLocation(item)).toBe("Clause 11.2 · Limitation of Liability · page 14");
    const html = renderToStaticMarkup(<EvidenceList evidence={[item]} />);
    expect(html).toContain("Clause 11.2");
    expect(html).toContain("page 14");
  });

  it("labels OCR-derived evidence", () => {
    // 34.8 — provenance is visible, so a reader knows the text was recovered rather
    // than read directly.
    const html = renderToStaticMarkup(
      <EvidenceList
        evidence={[
          {
            id: "ev2",
            relationship_type: "PRIMARY",
            page_number: 2,
            section_number: null,
            section_title: null,
            content: "scanned text",
            source_type: "OCR",
          },
        ]}
      />,
    );
    expect(html).toContain("OCR");
  });

  it("does not invent a location it does not have", () => {
    expect(
      formatLocation({
        id: "ev3",
        relationship_type: "PRIMARY",
        page_number: null,
        section_number: null,
        section_title: null,
        content: "x",
        source_type: "NATIVE_TEXT",
      }),
    ).toBe("Location not recorded");
  });
});

describe("escalation is not approval", () => {
  it("shows an escalated Finding as requiring review, with no decision implied", () => {
    // Locked Step 4 / ROLE-04: escalation means "this requires authorized review",
    // never "I approve this deviation".
    const html = renderToStaticMarkup(
      <FindingCard finding={finding({ escalated: true, status: "DECISION_REQUIRED" })} />,
    );
    expect(html).toContain("Escalated");
    expect(html).toContain("Requires authorized review");
    expect(html).not.toContain("approv");
  });
});
