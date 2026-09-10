/**
 * Two requirements, one title.
 *
 * The owner's screenshot (2026-09-09) showed a real MSA with two cards both
 * headed "Auto renewal". They are not a duplicate: `AUTORENEW-MSA-001` compares
 * the renewal TERM (6 months, NUMERIC_COMPARISON) and `AUTORENEW-TOS-001`
 * checks the clause is PRESENT, and since `AM-51` measures applicability by
 * content both apply to one document. `requirementTitle` strips the
 * document-type token as addressing rather than meaning, which is what collapses
 * the two headings into one.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FindingCard } from "@/components/workspace/FindingsPane";
import { HighlightProvider } from "@/components/workspace/highlight";
import {
  collidingTitles,
  requirementFamily,
  requirementTitle,
} from "@/components/workspace/findingLanguage";
import type { Evaluation, Finding, FindingExplanation } from "@/lib/types";

const AUTORENEW_MSA = { code: "AUTORENEW-MSA-001", name: "AUTORENEW-MSA-001", version_id: "v1", version_number: 1,
  description: "The agreement renews automatically for a set period each time, on the same terms." };
const AUTORENEW_TOS = { code: "AUTORENEW-TOS-001", name: "AUTORENEW-TOS-001", version_id: "v2", version_number: 1,
  description: "Services renew automatically for the same billing period unless cancelled before the renewal date." };
const LIABILITY_MSA = { code: "LIABILITY-MSA-001", name: "LIABILITY-MSA-001", version_id: "v3", version_number: 1 };

function finding(requirement: typeof AUTORENEW_MSA | typeof LIABILITY_MSA, id: string): Finding {
  const evaluation = {
    id: `e-${id}`, finding_id: id, scope_key: "GENERAL", scope_label: null,
    evaluation_kind: "PRIMARY", classification: "MATCH",
    actual_value: { presence: "PRESENT" }, evaluated_facts: null,
    expected_value: { presence: "PRESENT" }, rule_outcome: "ACCEPTABLE",
    evidence_refs: [], diagnostics: [], evaluator_type: "PRESENCE",
    evaluator_version: "PRESENCE-v1", requires_decision: false,
    current_decision: null, created_at: null, explanation: [],
  } as unknown as Evaluation;
  return {
    id, review_id: "r1", requirement, classification: "MATCH",
    status: "OPEN", requires_decision: false, escalated: false,
    evidence: [], evaluations: [evaluation], created_at: null,
  } as unknown as Finding;
}

describe("the two auto-renewal requirements", () => {
  it("really do reduce to the same title", () => {
    expect(requirementTitle(AUTORENEW_MSA)).toBe(requirementTitle(AUTORENEW_TOS));
  });

  it("names each standard's own family", () => {
    expect(requirementFamily(AUTORENEW_MSA)).toBe("MSA");
    expect(requirementFamily(AUTORENEW_TOS)).toBe("TOS");
  });
});

describe("collidingTitles", () => {
  it("reports only titles more than one finding carries", () => {
    const titles = collidingTitles([
      finding(AUTORENEW_MSA, "f1"),
      finding(AUTORENEW_TOS, "f2"),
      finding(LIABILITY_MSA, "f3"),
    ]);
    expect([...titles]).toEqual([requirementTitle(AUTORENEW_MSA)]);
    expect(titles.has(requirementTitle(LIABILITY_MSA))).toBe(false);
  });

  it("is empty when every title is distinct", () => {
    expect(collidingTitles([finding(AUTORENEW_MSA, "f1"), finding(LIABILITY_MSA, "f3")]).size).toBe(0);
  });
});

function render(f: Finding, qualify: boolean, explanation: FindingExplanation | null = null): string {
  return renderToStaticMarkup(
    <HighlightProvider>
      <FindingCard finding={f} qualify={qualify} onChanged={() => {}} prepared={null} explanation={explanation} />
    </HighlightProvider>,
  );
}

describe("the card heading", () => {
  it("names the family when another card shares the title", () => {
    expect(render(finding(AUTORENEW_MSA, "f1"), true)).toContain("MSA standard");
    expect(render(finding(AUTORENEW_TOS, "f2"), true)).toContain("TOS standard");
  });

  it("says nothing extra when the title stands alone", () => {
    // The 2026-09-08 decision to keep requirement codes out of the header holds
    // for every card that is not ambiguous.
    const markup = render(finding(LIABILITY_MSA, "f3"), false);
    expect(markup).not.toContain("MSA standard");
  });
});

describe("what each colliding standard asks (owner, 2026-09-10)", () => {
  const grounded = { status: "ACCEPTED", text: "The clause renews the agreement for six months." } as unknown as FindingExplanation;

  it("puts the requirement's own description under a colliding title", () => {
    const msa = render(finding(AUTORENEW_MSA, "f1"), true, grounded);
    const tos = render(finding(AUTORENEW_TOS, "f2"), true, grounded);
    expect(msa).toContain("ws-finding__asks");
    expect(msa).toContain("renews automatically for a set period");
    expect(tos).toContain("for the same billing period");
  });

  it("does not repeat a description the lede already shows, and shows nothing on a lone title", () => {
    // No grounded sentence: the lede IS the description, once.
    const msa = render(finding(AUTORENEW_MSA, "f1"), true, null);
    expect(msa.match(/renews automatically for a set period/g)).toHaveLength(1);
    expect(render(finding(LIABILITY_MSA, "f3"), false, grounded)).not.toContain("ws-finding__asks");
  });
});
