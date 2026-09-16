/**
 * One obligation, one finding — and never one finding for two obligations.
 *
 * Found in a UX review of the live site, 2026-09-16: an NDA showed two
 * "Confidentiality survival" cards, one measured against the MSA standard and one
 * against the NDA standard, both quoting §9, both reading "2 years" against "3 years",
 * both "Requires modification". Under `AM-51` both evaluations are correct — content
 * decides applicability and one document may span families — but the reader met one
 * clause as two problems, and every Summary count was inflated by the repeat.
 *
 * The fold is presentation only: nothing is re-classified, nothing is dropped, and the
 * folded finding is carried on the survivor so the card can still name every standard
 * that was measured.
 *
 * The dangerous direction is the other one. These pin the cases that must NOT fold —
 * above all two MISSING findings, which cite no evidence and otherwise look identical to
 * each other: fold those and a requirement the document never satisfied disappears from
 * the reader's list entirely.
 */

import { describe, expect, it } from "vitest";

import { mergeEquivalentFindings } from "@/components/workspace/findingLanguage";
import type { Evaluation, Finding } from "@/lib/types";

function finding(over: {
  id: string;
  code: string;
  classification?: string;
  user_status?: string;
  evidence?: string[];
  actual?: Record<string, unknown>;
  expected?: Record<string, unknown>;
  requires_decision?: boolean;
}): Finding {
  const classification = over.classification ?? "DEVIATION";
  const evaluation = {
    id: `e-${over.id}`, finding_id: over.id, scope_key: "GENERAL", scope_label: null,
    evaluation_kind: "PRIMARY", classification,
    actual_value: over.actual ?? { cap_value: 2, cap_unit: "YEARS" },
    evaluated_facts: null,
    evidence_refs: over.evidence ?? ["ev-9"],
    diagnostics: [], evaluator_type: "NUMERIC_COMPARISON",
    evaluator_version: "NUMERIC-v1", requires_decision: false,
    current_decision: null, created_at: null,
    expected_value: over.expected ?? { preferred: 3, unit: "YEARS" },
    rule_outcome: "UNACCEPTABLE", explanation: [],
  } as Evaluation;
  return {
    id: over.id, review_id: "r1",
    requirement: { code: over.code, name: over.code, version_id: `v-${over.id}`, version_number: 1 },
    classification, status: "OPEN",
    requires_decision: over.requires_decision ?? false,
    escalated: false,
    user_status: over.user_status ?? "REQUIRES_MODIFICATION",
    evaluations: [evaluation], evidence: [],
    created_at: null, updated_at: null,
  } as Finding;
}

/** The reported pair: one clause, one value, two standards for one obligation. */
const CONFIDENTIALITY_MSA = finding({
  id: "f-msa", code: "CONF-SURVIVAL-MSA-001", evidence: ["ev-9"],
  actual: { cap_value: 2, cap_unit: "YEARS", cap_basis: "CONFIDENTIALITY_SURVIVAL_POST_TERMINATION" },
  expected: { preferred: 3, unit: "YEARS", basis: "CONFIDENTIALITY_SURVIVAL_POST_TERMINATION" },
});
const CONFIDENTIALITY_NDA = finding({
  id: "f-nda", code: "CONF-SURVIVAL-NDA-001", evidence: ["ev-9"],
  actual: { cap_value: 2, cap_unit: "YEARS", cap_basis: "CONFIDENTIALITY_SURVIVAL_POST_TERMINATION" },
  // The bases differ deliberately in the ratified config, and differ here.
  expected: { preferred: 3, unit: "YEARS", basis: "CONFIDENTIALITY_SURVIVAL_POST_TERMINATION_OR_RELATIONSHIP_END" },
});

describe("two statements of one obligation become one finding", () => {
  it("folds the reported MSA/NDA confidentiality pair into a single card", () => {
    const merged = mergeEquivalentFindings([CONFIDENTIALITY_MSA, CONFIDENTIALITY_NDA]);
    expect(merged).toHaveLength(1);
    expect(merged[0]!.id).toBe("f-msa");
  });

  it("carries the folded standard rather than discarding it", () => {
    // Rule 11/12: the chain stays reconstructible. The card names what it stands for.
    const [kept] = mergeEquivalentFindings([CONFIDENTIALITY_MSA, CONFIDENTIALITY_NDA]);
    expect(kept!.alsoMeasuredAgainst?.map((f) => f.requirement.code))
      .toEqual(["CONF-SURVIVAL-NDA-001"]);
  });

  it("does not mutate the findings it was given", () => {
    const input = [CONFIDENTIALITY_MSA, CONFIDENTIALITY_NDA];
    mergeEquivalentFindings(input);
    expect((CONFIDENTIALITY_MSA as Finding & { alsoMeasuredAgainst?: unknown })
      .alsoMeasuredAgainst).toBeUndefined();
    expect(input).toHaveLength(2);
  });

  it("keeps the order the server sent", () => {
    const other = finding({ id: "f-other", code: "GOVLAW-MSA-001", evidence: ["ev-2"] });
    const merged = mergeEquivalentFindings([other, CONFIDENTIALITY_MSA, CONFIDENTIALITY_NDA]);
    expect(merged.map((f) => f.id)).toEqual(["f-other", "f-msa"]);
  });
});

describe("what must never fold", () => {
  it("never folds two MISSING findings, which cite nothing and look alike", () => {
    /* THE DANGEROUS CASE. Two requirements the document does not satisfy produce two
       findings with no evidence, the same "not found" value, the same status and the
       same next step. Folding them would delete a missing obligation from the reader's
       list — which is why a finding citing no evidence is never folded at all. */
    const arbitration = finding({
      id: "f-arb", code: "ARBITRATION-MSA-001", classification: "MISSING",
      evidence: [], actual: { presence: "ABSENT" }, expected: { presence: "PRESENT" },
    });
    const indemnity = finding({
      id: "f-ind", code: "INDEMNITY-MSA-001", classification: "MISSING",
      evidence: [], actual: { presence: "ABSENT" }, expected: { presence: "PRESENT" },
    });
    expect(mergeEquivalentFindings([arbitration, indemnity])).toHaveLength(2);
  });

  it("never folds two different obligations measured on the same clause", () => {
    const survival = finding({ id: "f-1", code: "CONF-SURVIVAL-MSA-001", evidence: ["ev-9"] });
    const retention = finding({ id: "f-2", code: "RECORD-RETENTION-MSA-001", evidence: ["ev-9"] });
    expect(mergeEquivalentFindings([survival, retention])).toHaveLength(2);
  });

  it("never folds when the required value differs", () => {
    const three = finding({ id: "f-1", code: "CONF-SURVIVAL-MSA-001", evidence: ["ev-9"] });
    const five = finding({
      id: "f-2", code: "CONF-SURVIVAL-NDA-001", evidence: ["ev-9"],
      expected: { preferred: 5, unit: "YEARS" },
    });
    expect(mergeEquivalentFindings([three, five])).toHaveLength(2);
  });

  it("never folds when the clause differs", () => {
    const nine = finding({ id: "f-1", code: "CONF-SURVIVAL-MSA-001", evidence: ["ev-9"] });
    const twelve = finding({ id: "f-2", code: "CONF-SURVIVAL-NDA-001", evidence: ["ev-12"] });
    expect(mergeEquivalentFindings([nine, twelve])).toHaveLength(2);
  });

  it("never folds an accepted finding into one that needs work", () => {
    const ok = finding({
      id: "f-1", code: "CONF-SURVIVAL-MSA-001", evidence: ["ev-9"],
      classification: "MATCH", user_status: "ACCEPTABLE",
    });
    const not = finding({ id: "f-2", code: "CONF-SURVIVAL-NDA-001", evidence: ["ev-9"] });
    expect(mergeEquivalentFindings([ok, not])).toHaveLength(2);
  });

  it("never folds when one of them needs a decision and the other does not", () => {
    const decide = finding({
      id: "f-1", code: "CONF-SURVIVAL-MSA-001", evidence: ["ev-9"], requires_decision: true,
    });
    const plain = finding({ id: "f-2", code: "CONF-SURVIVAL-NDA-001", evidence: ["ev-9"] });
    expect(mergeEquivalentFindings([decide, plain])).toHaveLength(2);
  });

  it("leaves a list with nothing to fold exactly as it was", () => {
    const list = [
      finding({ id: "f-1", code: "GOVLAW-MSA-001", evidence: ["ev-1"] }),
      finding({ id: "f-2", code: "LIABILITY-MSA-001", evidence: ["ev-2"] }),
    ];
    expect(mergeEquivalentFindings(list).map((f) => f.id)).toEqual(["f-1", "f-2"]);
    expect(mergeEquivalentFindings(list).every((f) => f.alsoMeasuredAgainst === undefined))
      .toBe(true);
  });
});

describe("the counts a reader is shown follow the fold", () => {
  it("counts the folded pair once, so the Summary and the list agree", () => {
    // The pane, the Summary tiles and the outline all read one merged list — the
    // point of folding at the load rather than in the pane.
    const merged = mergeEquivalentFindings([
      CONFIDENTIALITY_MSA,
      CONFIDENTIALITY_NDA,
      finding({ id: "f-3", code: "GOVLAW-MSA-001", evidence: ["ev-2"] }),
    ]);
    expect(merged.filter((f) => f.user_status === "REQUIRES_MODIFICATION")).toHaveLength(2);
  });
});
