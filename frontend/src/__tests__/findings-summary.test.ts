/**
 * The summary → category drill's pure layer (2026-08-31 v2): counting is
 * presentational grouping of server values — attention-first order, unknown
 * values kept, MATCH-only success detection — and the Documents "needs
 * attention" grouping reads only the server's own counts.
 */

import { describe, expect, it } from "vitest";

import {
  CLASSIFICATION_ORDER,
  findingsSummary,
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
