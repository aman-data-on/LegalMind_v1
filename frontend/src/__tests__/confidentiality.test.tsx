/**
 * LEGAL-02 confidentiality rendering — locked 49.7 r4/r5, 52.4.
 *
 * Locked 52.4 is the rule under test: "The UI must render an omitted field as
 * simply absent — no placeholder, no 'hidden', no greyed-out row, no lock icon. A
 * visible marker would disclose that an internal legal position exists, which is
 * exactly what LEGAL-02 prevents."
 *
 * These assertions are made against the real rendered markup rather than against a
 * helper, because the failure mode is visual: a component could pass every logical
 * test and still emit a dash where a threshold was withheld.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EvaluationRow, evaluationNeedsAttention } from "@/components/EvaluationRow";
import { FindingCard } from "@/components/FindingCard";
import type { Evaluation, Finding } from "@/lib/types";

/** What a caller WITHOUT `legal_position.view` receives — fields simply absent. */
const withheld: Evaluation = {
  id: "e1",
  finding_id: "f1",
  scope_key: "CATEGORY",
  scope_label: "confidentiality breach",
  evaluation_kind: "EXCEPTION",
  classification: "DEVIATION",
  actual_value: { months: 3 },
  evaluated_facts: { caps: 2 },
  evidence_refs: ["ev1"],
  diagnostics: [],
  evaluator_type: "NUMERIC_COMPARISON",
  evaluator_version: "LIABILITY-EVALUATOR-v1",
  requires_decision: true,
  current_decision: null,
  created_at: "2026-08-17T10:00:00+00:00",
};

/** The same Evaluation as an authorized Legal caller receives it. */
const permitted: Evaluation = {
  ...withheld,
  rule_outcome: "UNACCEPTABLE",
  expected_value: { months: 6 },
  operator: ">=",
  comparison: "3 < 6",
  explanation: ["Company Standard requires at least 6 months", "Contract gives 3"],
  legal_rule_version_id: "lr1",
};

describe("omitted legal position", () => {
  it("renders no marker of any kind where a field was withheld", () => {
    const html = renderToStaticMarkup(<EvaluationRow evaluation={withheld} />);

    // The values themselves must not appear.
    expect(html).not.toContain("UNACCEPTABLE");
    expect(html).not.toContain("6 months");
    expect(html).not.toContain("3 < 6");
    expect(html).not.toContain("Company Standard requires");

    // Nor may anything hint that a value exists and was withheld (52.4).
    //
    // The list is phrases, not bare words: "confidential" and "lock" would collide
    // with legitimate contract content — this fixture's own scope_label is
    // "confidentiality breach", which is the counterparty's clause text and must be
    // shown. A test that forbade the substring would forbid displaying the
    // contract.
    for (const marker of [
      "Hidden",
      "hidden field",
      "Restricted",
      "redacted",
      "Redacted",
      "Confidential —",
      "not permitted to view",
      "no access",
      "requires legal_position",
      "🔒",
      "&#128274;",
    ]) {
      expect(html).not.toContain(marker);
    }
    // And no marker-bearing class may be emitted at all.
    expect(html).not.toMatch(/class="[^"]*(withheld|masked|redact|locked)/);
  });

  it("emits no empty element where the withheld field would have been", () => {
    const html = renderToStaticMarkup(<EvaluationRow evaluation={withheld} />);
    // An empty span or a bare dash is still a marker: it shows the reader that
    // something belongs there.
    expect(html).not.toMatch(/<span[^>]*class="outcome[^"]*"[^>]*>\s*<\/span>/);
    expect(html).not.toContain("<dt>Company Standard</dt>");
    expect(html).not.toContain("—</dd>");
  });

  it("shows the full position to a permitted caller", () => {
    const html = renderToStaticMarkup(<EvaluationRow evaluation={permitted} />);
    expect(html).toContain("UNACCEPTABLE");
    expect(html).toContain("Company Standard");
    expect(html).toContain("Company Standard requires at least 6 months");
    expect(html).toContain("&gt;=");
  });

  it("gives the two callers structurally different views, not one masked view", () => {
    // Step 52.4: "structurally different views, not the same view with fields
    // masked." If they differed only in text content, a reader could infer the
    // withheld field from the shape.
    const restricted = renderToStaticMarkup(<EvaluationRow evaluation={withheld} />);
    const full = renderToStaticMarkup(<EvaluationRow evaluation={permitted} />);
    expect(restricted.length).toBeLessThan(full.length);
    expect(restricted).not.toContain("evaluation__explanation");
    expect(full).toContain("evaluation__explanation");
  });

  it("never leaks a legal position through the Finding view either", () => {
    const finding: Finding = {
      id: "f1",
      review_id: "r1",
      requirement: { code: "LIABILITY-001", name: "Liability", version_id: "rv1", version_number: 1 },
      classification: "DEVIATION",
      status: "DECISION_REQUIRED",
      requires_decision: true,
      escalated: false,
      evaluations: [withheld],
      evidence: [],
      created_at: null,
      updated_at: null,
    };
    const html = renderToStaticMarkup(<FindingCard finding={finding} />);
    expect(html).not.toContain("UNACCEPTABLE");
    expect(html).not.toContain("rule_outcome");
  });
});

describe("attention styling without a legal position", () => {
  it("marks an Evaluation needing a decision even when rule_outcome is withheld", () => {
    // 52.5 requires the visual distinction. For a caller who cannot see rule
    // outcomes it has to come from `requires_decision`, which is not a legal
    // position and which 49.7's own example returns to everyone.
    expect(evaluationNeedsAttention(withheld)).toBe(true);
    const html = renderToStaticMarkup(<EvaluationRow evaluation={withheld} />);
    expect(html).toContain("evaluation--attention");
  });

  it("marks an UNACCEPTABLE Evaluation for a permitted caller", () => {
    expect(evaluationNeedsAttention(permitted)).toBe(true);
  });

  it("leaves a conforming Evaluation unmarked", () => {
    const calm: Evaluation = {
      ...withheld,
      classification: "MATCH",
      requires_decision: false,
      rule_outcome: "ACCEPTABLE",
    };
    expect(evaluationNeedsAttention(calm)).toBe(false);
    const html = renderToStaticMarkup(<EvaluationRow evaluation={calm} />);
    expect(html).not.toContain("evaluation--attention");
  });
});
