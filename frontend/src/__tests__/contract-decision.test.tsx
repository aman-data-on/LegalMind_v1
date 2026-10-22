/**
 * AM-173/AM-174 (owner, 2026-10-22): a point can be marked not applicable to this
 * contract, a decided point is no longer open, and the decision on the whole contract
 * is said in a reviewer's words — never "Acceptable" (rule 14).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { LegalAngleView } from "@/components/workspace/Angles";
import { CONTRACT_OUTCOME_LABELS, decidedWords, decisionLabel } from "@/lib/labels";
import { DECISION_TYPES, submittableDecisionTypes } from "@/lib/permissions";
import type { ReviewAngles } from "@/lib/types";

describe("not applicable to this contract (AM-173)", () => {
  it("is offered to a decider and said in words, never as Acceptable", () => {
    expect(submittableDecisionTypes(["legal.decision"])).toContain("NOT_APPLICABLE_TO_CONTRACT");
    expect(DECISION_TYPES).toContain("NOT_APPLICABLE_TO_CONTRACT");
    expect(decisionLabel("NOT_APPLICABLE_TO_CONTRACT")).toBe("Not applicable to this contract");
    expect(decidedWords("NOT_APPLICABLE_TO_CONTRACT")).not.toMatch(/acceptable/i);
  });
});

describe("the decision on the contract (AM-174)", () => {
  it("has the four answers in a reviewer's words", () => {
    expect(Object.values(CONTRACT_OUTCOME_LABELS)).toEqual([
      "Sign as is", "Sign after our changes", "Do not sign", "On hold — waiting for the client"]);
  });

  it("keeps a decided point out of Open points", () => {
    const item = (id: string) => ({
      finding_id: id, requirement_code: `R-${id}`, title: `Point ${id}`,
      classification: "DEVIATION", waived: false, where: `§${id} · page 1`,
      evidence_ids: [] });
    const angles = { legal: { actionable: 2, matching: 0,
      items: [item("a"), item("b")] } } as unknown as ReviewAngles;
    const html = renderToStaticMarkup(<LegalAngleView angles={angles} decided={new Set(["a"])} />);
    expect(html).toContain("Open points (1)");
    expect(html).toContain("§b · page 1");
    expect(html).not.toContain("§a · page 1");
  });
});
