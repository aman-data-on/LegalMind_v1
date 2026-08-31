/**
 * The summary → category drill's pure layer (2026-08-31 v2): counting is
 * presentational grouping of server values — attention-first order, unknown
 * values kept, MATCH-only success detection — and the Documents "needs
 * attention" grouping reads only the server's own counts.
 */

import { describe, expect, it } from "vitest";

import {
  CLASSIFICATION_ORDER,
  clauseStatusByEvidenceId,
  findingsNeedingDecision,
  findingsSummary,
  outlineStatus,
  rowNeedsAttention,
} from "@/components/workspace/model";

const f = (classification: string, requires = false) => ({
  classification,
  requires_decision: requires,
});

describe("findingsSummary", () => {
  it("counts in the fixed attention-first order", () => {
    const summary = findingsSummary([
      f("MATCH"), f("DEVIATION", true), f("MATCH"), f("MISSING", true), f("DEVIATION", true),
    ]);
    expect(summary.counts).toEqual([
      { classification: "DEVIATION", n: 2 },
      { classification: "MISSING", n: 1 },
      { classification: "MATCH", n: 2 },
    ]);
    expect(summary.needsDecision).toBe(3);
    expect(summary.allMatch).toBe(false);
  });

  it("declares the designed success state only when every finding is a MATCH", () => {
    expect(findingsSummary([f("MATCH"), f("MATCH")]).allMatch).toBe(true);
    expect(findingsSummary([]).allMatch).toBe(false);
    expect(findingsSummary([f("MATCH"), f("CONFLICT", true)]).allMatch).toBe(false);
  });

  it("never drops a value outside the known vocabulary", () => {
    const summary = findingsSummary([f("SOMETHING_NEW")]);
    expect(summary.counts).toEqual([{ classification: "SOMETHING_NEW", n: 1 }]);
  });

  it("keeps NOT_APPLICABLE out of the classification vocabulary (it is a Rule Outcome)", () => {
    expect(CLASSIFICATION_ORDER).not.toContain("NOT_APPLICABLE");
  });
});

describe("rowNeedsAttention", () => {
  it("flags any non-MATCH count from the server", () => {
    expect(rowNeedsAttention({
      latest_analysis: { classification_counts: { MATCH: 4, DEVIATION: 1 } },
    })).toBe(true);
  });

  it("stays calm for all-MATCH, unanalysed and empty rows", () => {
    expect(rowNeedsAttention({
      latest_analysis: { classification_counts: { MATCH: 4 } },
    })).toBe(false);
    expect(rowNeedsAttention({ latest_analysis: null })).toBe(false);
    expect(rowNeedsAttention({})).toBe(false);
  });
});

describe("findingsNeedingDecision", () => {
  it("is the server's own requires_decision flag and nothing else", () => {
    const findings = [
      { requires_decision: true, id: "a" },
      { requires_decision: false, id: "b" },
      { requires_decision: true, id: "c" },
    ];
    expect(findingsNeedingDecision(findings).map((x) => x.id)).toEqual(["a", "c"]);
  });
});

describe("clauseStatusByEvidenceId", () => {
  const finding = (classification: string, requires: boolean, evidenceIds: string[]) => ({
    classification,
    requires_decision: requires,
    evidence: evidenceIds.map((id) => ({ id })),
  });

  it("marks non-MATCH or requires_decision evidence as attention", () => {
    const map = clauseStatusByEvidenceId([
      finding("MATCH", false, ["e1"]),
      finding("DEVIATION", true, ["e2"]),
    ]);
    expect(map.get("e1")).toEqual({ covered: true, attention: false });
    expect(map.get("e2")).toEqual({ covered: true, attention: true });
    expect(map.get("e3")).toBeUndefined();
  });

  it("ORs attention across findings citing the same row — attention never downgrades", () => {
    const map = clauseStatusByEvidenceId([
      finding("DEVIATION", true, ["shared"]),
      finding("MATCH", false, ["shared"]),
    ]);
    expect(map.get("shared")).toEqual({ covered: true, attention: true });
  });

  it("treats every non-MATCH classification with the same weight (no severity ranking)", () => {
    const map = clauseStatusByEvidenceId([
      finding("MISSING", false, ["m"]),
      finding("AMBIGUOUS", false, ["a"]),
    ]);
    expect(map.get("m")).toEqual(map.get("a"));
  });
});

describe("outlineStatus", () => {
  it("rolls a body row's status up to its owning outline row", () => {
    const rows = [
      { id: "h1", section_number: "17.2", section_title: "Liability" },
      { id: "b1", section_number: null, section_title: null },
      { id: "h2", section_number: "22", section_title: "Termination" },
      { id: "b2", section_number: null, section_title: null },
    ];
    const status = new Map([
      ["b1", { covered: true, attention: true }],
      ["h2", { covered: true, attention: false }],
    ]);
    const rolled = outlineStatus(rows, status);
    expect(rolled.get("h1")).toEqual({ covered: true, attention: true });
    expect(rolled.get("h2")).toEqual({ covered: true, attention: false });
    expect(rolled.get("b2")).toBeUndefined();
  });
});
