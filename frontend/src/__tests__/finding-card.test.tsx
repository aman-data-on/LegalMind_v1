/**
 * One finding card per classification and per evidence shape — the edge-case
 * matrix the owner asked for on 2026-09-08, rendered rather than reasoned
 * about.
 *
 * `renderToStaticMarkup` is the harness this project already uses for
 * components (see `ask-dock.test.tsx`): no DOM, no testing-library, and it
 * fails on a render-time throw, which is exactly the failure a new value shape
 * would cause. Fixtures carry `requires_decision: false` and no recorded
 * decision so the card renders without the decision control, which needs a
 * session — the decision path has its own browser coverage in `decision.spec.ts`.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { FindingCard } from "@/components/workspace/FindingsPane";
import { HighlightProvider } from "@/components/workspace/highlight";
import type { Evaluation, Evidence, Finding } from "@/lib/types";

function evidence(over: Partial<Evidence> = {}): Evidence {
  return {
    id: "ev1", relationship_type: "PRIMARY", page_number: 4,
    section_number: "11", section_title: "Residuals",
    content: "The Receiving Party may use Residuals.", source_type: "NATIVE_TEXT",
    ...over,
  };
}

function card(over: Partial<Finding> = {}, evalOver: Partial<Evaluation> = {}): string {
  const evaluation = {
    id: "e1", finding_id: "f1", scope_key: "GENERAL", scope_label: null,
    evaluation_kind: "PRIMARY", classification: over.classification ?? "MISSING",
    actual_value: { presence: "ABSENT" }, evaluated_facts: null,
    evidence_refs: [], diagnostics: [], evaluator_type: "PRESENCE",
    evaluator_version: "PRESENCE-v1", requires_decision: false,
    current_decision: null, created_at: null,
    expected_value: { presence: "PRESENT" }, rule_outcome: "NOT_APPLICABLE",
    explanation: ["mapping layer completed and mapped no provision"],
    ...evalOver,
  } as Evaluation;
  const finding = {
    id: "f1", review_id: "r1",
    requirement: { code: "RESIDUALS-NDA-001", name: "RESIDUALS-NDA-001", version_id: "v1", version_number: 1 },
    classification: "MISSING", status: "OPEN", requires_decision: false,
    escalated: false, evaluations: [evaluation], evidence: [],
    created_at: null, updated_at: null,
    ...over,
  } as Finding;
  return renderToStaticMarkup(
    <HighlightProvider>
      <FindingCard finding={finding} onChanged={() => {}} prepared={null} />
    </HighlightProvider>,
  );
}

describe("every classification renders a card a reader can act on", () => {
  const cases: Array<[string, RegExp]> = [
    ["MATCH", /matches what the company standard expects/i],
    ["DEVIATION", /not in the way the company standard expects/i],
    ["MISSING", /was not found in the document/i],
    ["CONFLICT", /contradict each other/i],
    ["UNABLE_TO_EVALUATE", /not enough reliable information/i],
  ];

  for (const [classification, sentence] of cases) {
    it(`${classification} carries the plain sentence and the canonical word`, () => {
      const html = card({ classification }, { classification });
      expect(html).toMatch(sentence);
      // The chip keeps the canonical vocabulary beside the sentence —
      // UNABLE_TO_EVALUATE renders as its locked label "NEEDS A PERSON".
      expect(html).toMatch(classification === "UNABLE_TO_EVALUATE" ? /NEEDS A PERSON/ : new RegExp(classification));
      // The title is words, never the identifier repeated as one.
      expect(html).toContain("Residuals");
      expect(html).not.toMatch(/Residuals nda 001/i);
      // No empty reasoning step, which is what the old explainer produced.
      expect(html).not.toMatch(/<li><\/li>/);
    });
  }

  it("keeps the requirement code available, but not as the heading", () => {
    const html = card();
    expect(html).toContain("RESIDUALS-NDA-001");
    expect(html).toMatch(/ws-finding__title[^>]*>Residuals</);
  });
});

describe("evidence shapes", () => {
  it("says plainly when nothing was cited", () => {
    expect(card()).toMatch(/No supporting text was found in the document/i);
  });

  it("quotes one passage with its location", () => {
    const html = card(
      { classification: "MATCH", evidence: [evidence()] },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["ev1"] },
    );
    expect(html).toMatch(/§11 · Residuals · page 4/);
    expect(html).toContain("The Receiving Party may use Residuals.");
    expect(html).toMatch(/Quoted from this document/i);
  });

  it("counts many passages rather than listing a number nobody can hold", () => {
    const rows = [1, 2, 3, 4, 5].map((n) => evidence({ id: `ev${n}`, section_number: `${n}` }));
    const html = card(
      { classification: "MATCH", evidence: rows },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: rows.map((r) => r.id) },
    );
    expect(html).toMatch(/5 passages/);
  });

  it("offers the full text of a long passage instead of truncating it silently", () => {
    const long = evidence({ content: `${"The Receiving Party shall not disclose it. ".repeat(20)}Final sentence.` });
    const html = card(
      { classification: "MATCH", evidence: [long] },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["ev1"] },
    );
    expect(html).toMatch(/Show the full passage/);
    expect(html).toMatch(/…/);
  });

  it("flags a passage recovered by OCR, and says nothing about native text", () => {
    const ocr = card(
      { classification: "MATCH", evidence: [evidence({ source_type: "OCR" })] },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["ev1"] },
    );
    expect(ocr).toMatch(/read by OCR/);
    const native = card(
      { classification: "MATCH", evidence: [evidence()] },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["ev1"] },
    );
    expect(native).not.toMatch(/read by/);
  });

  it("renders a passage with no location at all without an empty control", () => {
    const bare = evidence({ section_number: null, section_title: null, page_number: null });
    const html = card(
      { classification: "MATCH", evidence: [bare] },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["ev1"] },
    );
    expect(html).toMatch(/Passage 1/);
  });
});

describe("LEGAL-02 — an omitted legal position leaves no trace", () => {
  it("renders without expected_value, rule_outcome or explanation", () => {
    // The shape the server sends a caller without `legal_position.view`:
    // omitted, never nulled (SEC-07). The card must not print a placeholder
    // where the company's position would go, and must not crash.
    // The omitted fields are `?:` on the type, so the cast is through
    // `unknown`: TypeScript will not narrow `string | undefined` down from an
    // object literal that only carries `undefined`.
    const html = card({}, {
      expected_value: undefined, rule_outcome: undefined, explanation: undefined,
    } as unknown as Partial<Evaluation>);
    expect(html).not.toMatch(/Company Standard/);
    expect(html).not.toMatch(/ws-evaluation__outcome/);
    expect(html).not.toMatch(/ws-explain/);
    // What survives: the contract's own value and the audit provenance.
    expect(html).toMatch(/Found in contract/);
    expect(html).toMatch(/PRESENCE-v1/);
  });
});

describe("odd value shapes never reach the reader as JSON", () => {
  it("renders an unrecognised actual_value without printing its keys", () => {
    const html = card({}, { actual_value: { wibble: 1, wobble: { deep: true } } });
    expect(html).not.toContain("wibble");
    expect(html).not.toContain("{&quot;");
  });

  it("renders the conflict shape as a count of provisions", () => {
    const html = card(
      { classification: "CONFLICT" },
      { classification: "CONFLICT", actual_value: { caps: [{ cap_value: 6 }, { cap_value: 12 }] } },
    );
    expect(html).toMatch(/2 separate limits stated/);
  });
});
