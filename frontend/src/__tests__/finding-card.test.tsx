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
      // The canonical word survives — inside "How this was determined", never
      // on the card face (owner, 2026-09-08: three user-facing statuses).
      // UNABLE_TO_EVALUATE renders as its locked label "NEEDS A PERSON".
      const { before, inside } = splitAtDetails(html);
      const word = classification === "UNABLE_TO_EVALUATE" ? /NEEDS A PERSON/ : new RegExp(classification);
      expect(inside).toMatch(word);
      expect(before).not.toMatch(word);
      // The title is words, never the identifier repeated as one.
      expect(html).toContain("Residuals");
      expect(html).not.toMatch(/Residuals nda 001/i);
      // No empty reasoning step, which is what the old explainer produced.
      expect(html).not.toMatch(/<li><\/li>/);
    });
  }

  it("keeps the requirement code available, but not as the heading or on the visible card", () => {
    // Relocated 2026-09-08 (third pass): a raw identifier is an "internal ID"
    // by the manager's own definition, so it moved from the card face into
    // "How this was determined" alongside the rest of the technical facts.
    const html = card();
    expect(html).toMatch(/ws-finding__title[^>]*>Residuals</);
    const { before, inside } = splitAtDetails(html);
    expect(before).not.toContain("RESIDUALS-NDA-001");
    expect(inside).toContain("RESIDUALS-NDA-001");
  });
});

/**
 * Splits a rendered card's HTML at its `<details>…</details>` boundary.
 * `renderToStaticMarkup` emits a closed `<details>`'s content in the markup
 * regardless — the browser hides it, not the server — so a plain substring
 * search cannot tell "on the visible card" from "behind the disclosure".
 * This can, and is what the tests below actually need: the manager's report
 * was specifically that certain facts sat OUTSIDE the disclosure, on the
 * always-visible part of the card.
 */
function splitAtDetails(html: string): { before: string; inside: string; after: string } {
  const open = html.indexOf("<details");
  const closeTag = "</details>";
  const close = html.lastIndexOf(closeTag);
  if (open === -1 || close === -1) return { before: html, inside: "", after: "" };
  return {
    before: html.slice(0, open),
    inside: html.slice(open, close + closeTag.length),
    after: html.slice(close + closeTag.length),
  };
}

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

describe("technical/engineering facts stay off the default-visible card (owner, 2026-09-08)", () => {
  it("keeps the raw rule outcome out of the visible card and inside the disclosure", () => {
    const html = card({}, {
      rule_outcome: "NOT_APPLICABLE", expected_value: { presence: "PRESENT" },
    });
    const { before, inside } = splitAtDetails(html);
    // The label the manager's screenshot flagged: not on the visible card.
    expect(before).not.toMatch(/No rule covers this/);
    // Not deleted — inside the disclosure, still reachable.
    expect(inside).toMatch(/No rule covers this/);
    expect(inside).toContain("ws-evaluation__outcome");
  });

  it("keeps the evaluator/evidence-count provenance out of the visible card", () => {
    const html = card(
      { classification: "MATCH", evidence: [evidence()] },
      { classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["ev1"] },
    );
    const { before, inside } = splitAtDetails(html);
    expect(before).not.toMatch(/PRESENCE-v1/);
    expect(inside).toMatch(/PRESENCE-v1/);
    expect(inside).toContain("ws-evaluation__provenance");
  });

  it("still proves the LEGAL-02 hooks by count, wherever they now live", () => {
    // The two tests above prove POSITION changed; this proves the property the
    // browser suite actually checks — presence/absence — is untouched. Both
    // `.ws-evaluation__outcome` and `.ws-evaluation__provenance` must appear
    // exactly once when the data is present.
    const html = card({}, { rule_outcome: "UNACCEPTABLE", expected_value: { presence: "PRESENT" } });
    expect((html.match(/ws-evaluation__outcome/g) ?? []).length).toBe(1);
    expect((html.match(/ws-evaluation__provenance/g) ?? []).length).toBe(1);
  });

  it("what a reader sees WITHOUT expanding anything still answers all four questions", () => {
    // What was checked / what the document says / what the standard expects /
    // what to do next — the manager's own four questions — must all be in the
    // `before` segment, i.e. visible with zero clicks.
    // Finding-level `requires_decision: true` (never the evaluation's — that
    // would also render `DecisionControl`, which needs a live session and has
    // its own browser coverage in `decision.spec.ts`) matches what a real
    // UNACCEPTABLE produces: D-3.5(a)'s zero-tolerance routing.
    const html = card(
      { classification: "DEVIATION", requires_decision: true },
      {
        classification: "DEVIATION", rule_outcome: "UNACCEPTABLE",
        actual_value: { cap_value: 24, cap_unit: "MONTHS" },
        expected_value: { preferred: 6, unit: "MONTHS" },
      },
    );
    const { before } = splitAtDetails(html);
    expect(before).toMatch(/Residuals/);                        // what was checked
    expect(before).toMatch(/24 MONTHS/);                          // what the document says
    expect(before).toMatch(/6 MONTHS/);                           // what the standard expects
    expect(before).toMatch(/NEXT STEP/i);                         // what to do next
    // And NOT the raw outcome label that used to sit right beside it.
    expect(before).not.toMatch(/Not acceptable/);
  });

  it("drops a scope label that only repeats the title, on every classification", () => {
    for (const classification of ["MATCH", "DEVIATION", "MISSING"]) {
      const html = card(
        { classification },
        { classification, scope_key: "RESIDUALS" },   // scopeLabel("RESIDUALS") === "Residuals" === the title
      );
      const { before } = splitAtDetails(html);
      expect(before, classification).not.toMatch(/ws-evaluation__scope/);
    }
  });

  it("keeps a scope label that says something the title did not", () => {
    const html = card(
      { requirement: { code: "X-MSA-001", name: "Liability cap", version_id: "v1", version_number: 1 } },
      { scope_key: "AGGREGATE" },
    );
    expect(html).toMatch(/ws-evaluation__scope[^>]*>Aggregate</);
  });
});

/**
 * The five real cases the manager named explicitly, with EXACT values pulled
 * (read-only) from the live database's own analysed NDA/MSA reviews — not
 * approximated, not invented. Every actual_value/expected_value/operator/
 * evaluator_version/explanation below is what the evaluator actually
 * produced for these requirements, so a wording bug here is a wording bug a
 * real Sales user would actually see.
 */
describe("the five required real-world cases (owner, 2026-09-08, third pass)", () => {
  it("RESIDUALS-NDA-001 — MISSING: absent from the contract, required by the standard", () => {
    const html = card(
      { requirement: { code: "RESIDUALS-NDA-001", name: "RESIDUALS-NDA-001", version_id: "v1", version_number: 1 },
        classification: "MISSING", status: "DECISION_REQUIRED", requires_decision: true },
      {
        classification: "MISSING", scope_key: "RESIDUALS", rule_outcome: "NOT_APPLICABLE",
        actual_value: { presence: "ABSENT" }, expected_value: { presence: "PRESENT" },
        operator: "presence", evaluator_version: "PRESENCE-v1",
        explanation: ["mapping layer completed and mapped no provision",
                      "absence established by mapping, not by evaluator inspection"],
      },
    );
    const { before, inside } = splitAtDetails(html);
    expect(before).toMatch(/Residuals/);
    expect(before).toMatch(/was not found in the document/i);
    expect(before).toMatch(/Not found/);
    // "Required", not "Found" — a presence-shaped Company Standard value
    // states what the standard requires, not that the standard was "found".
    expect(before).toMatch(/Required/);
    expect(before).toMatch(/legal authority needs to review/i);
    // Nothing technical on the visible surface: no evaluator name, no raw
    // "presence" operator word, no scope key, no raw outcome label.
    expect(before).not.toMatch(/PRESENCE-v1/);
    expect(before).not.toMatch(/>presence</);
    expect(before).not.toMatch(/RESIDUALS-NDA-001/);
    expect(before).not.toMatch(/No rule covers this/);
    // All of it is still reachable inside the disclosure.
    expect(inside).toContain("PRESENCE-v1");
    expect(inside).toMatch(/No rule covers this/);
    expect(inside).toContain("RESIDUALS-NDA-001");
  });

  it("CONF-SURVIVAL-NDA-001 — UNABLE_TO_EVALUATE (\"NEEDS A PERSON\"): nothing extracted on either side", () => {
    const html = card(
      { requirement: { code: "CONF-SURVIVAL-NDA-001", name: "CONF-SURVIVAL-NDA-001", version_id: "v1", version_number: 1 },
        classification: "UNABLE_TO_EVALUATE", status: "DECISION_REQUIRED", requires_decision: true,
        evidence: [evidence({ id: "ev1", section_number: null, section_title: null, page_number: 3 })] },
      {
        classification: "UNABLE_TO_EVALUATE", scope_key: "GENERAL", rule_outcome: "NOT_APPLICABLE",
        actual_value: null, expected_value: null, operator: null,
        evaluator_version: "NUMERIC-COMPARISON-v1", evidence_refs: ["ev1"],
        explanation: ["no extracted facts were supplied", "failing closed rather than guessing (ENG-09)"],
      },
    );
    const { before, inside } = splitAtDetails(html);
    expect(before).toMatch(/not enough reliable information/i);
    // The locked word lives in the disclosure now; the face says "Needs review".
    expect(before).toMatch(/Needs review/);
    expect(inside).toMatch(/NEEDS A PERSON/);
    expect(before).toMatch(/legal authority needs to review/i);
    // Honest about having nothing to compare — never a guess, never silence.
    expect(before).toMatch(/Not recorded/);
    expect(before).not.toMatch(/NUMERIC-COMPARISON-v1/);
    expect(before).not.toMatch(/CONF-SURVIVAL-NDA-001/);
    expect(before).not.toMatch(/No rule covers this/);
    expect(inside).toContain("NUMERIC-COMPARISON-v1");
    expect(inside).toContain("CONF-SURVIVAL-NDA-001");
  });

  it("GOVLAW-NDA-001 — MATCH: present in the contract, and the standard requires it", () => {
    const html = card(
      { requirement: { code: "GOVLAW-NDA-001", name: "GOVLAW-NDA-001", version_id: "v1", version_number: 1 },
        classification: "MATCH", status: "OPEN", requires_decision: false,
        evidence: [evidence({ id: "ev1", section_number: null, section_title: null, page_number: 6 })] },
      {
        classification: "MATCH", scope_key: "GOVERNING_LAW", rule_outcome: "ACCEPTABLE",
        actual_value: { presence: "PRESENT" }, expected_value: { presence: "PRESENT" },
        operator: "presence", evaluator_version: "PRESENCE-v1", evidence_refs: ["ev1"],
        explanation: ["mapping CONFIRMED for GOVLAW-NDA-001", "expected PRESENT; a qualifying provision is present"],
      },
    );
    const { before, inside } = splitAtDetails(html);
    expect(before).toMatch(/matches what the company standard expects/i);
    expect(before).toMatch(/Found/);
    expect(before).toMatch(/Required/);
    // A MATCH still answers "does someone need to act?" explicitly — saying
    // "No action is needed" is more useful to a Sales reader than silently
    // omitting the row, and it is a fact about the workflow state, not an
    // invented legal conclusion.
    expect(before).toMatch(/NEXT STEP.*No action is needed/is);
    expect(before).not.toMatch(/PRESENCE-v1/);
    expect(before).not.toMatch(/GOVLAW-NDA-001/);
    expect(inside).toContain("PRESENCE-v1");
    expect(inside).toContain("GOVLAW-NDA-001");
  });

  it("FORCE-MAJEURE-MSA-001 — DEVIATION: a real numeric mismatch, both sides in plain units", () => {
    const html = card(
      { requirement: { code: "FORCE-MAJEURE-MSA-001", name: "FORCE-MAJEURE-MSA-001", version_id: "v1", version_number: 1 },
        classification: "DEVIATION", status: "DECISION_REQUIRED", requires_decision: true },
      {
        classification: "DEVIATION", scope_key: "GENERAL", rule_outcome: "UNACCEPTABLE", operator: "!=",
        actual_value: { scope: "GENERAL", cap_unit: "DAYS", cap_basis: "FORCE_MAJEURE_TERMINATION_TRIGGER", cap_value: 30.0 },
        expected_value: { unit: "DAYS", basis: "FORCE_MAJEURE_TERMINATION_TRIGGER", preferred: 60, scope_key: "GENERAL" },
        evaluator_version: "NUMERIC-COMPARISON-v1",
      },
    );
    const { before, inside } = splitAtDetails(html);
    expect(before).toMatch(/not in the way the company standard expects/i);
    expect(before).toMatch(/30 DAYS/);
    expect(before).toMatch(/60 DAYS/);
    expect(before).toMatch(/legal authority needs to review/i);
    expect(before).not.toMatch(/Not acceptable/);
    expect(before).not.toMatch(/>!=</);
    expect(before).not.toMatch(/NUMERIC-COMPARISON-v1/);
    expect(inside).toMatch(/Not acceptable/);
    expect(inside).toContain("NUMERIC-COMPARISON-v1");
  });
});

describe("the status mark and the merged three-part comparison (owner, 2026-09-08, fourth pass)", () => {
  it("gives every classification a status mark with the right tone, before any click", () => {
    // One tone per user-facing status: Accepted ok, Needs review warn, and
    // "bad" reserved for Not accepted — so MISSING is no longer red on sight.
    const cases: Array<[string, string]> = [
      ["MATCH", "ws-finding__mark--ok"],
      ["DEVIATION", "ws-finding__mark--warn"],
      ["CONFLICT", "ws-finding__mark--warn"],
      ["MISSING", "ws-finding__mark--warn"],
      ["UNABLE_TO_EVALUATE", "ws-finding__mark--warn"],
    ];
    for (const [classification, markClass] of cases) {
      const html = card({ classification }, { classification });
      const { before } = splitAtDetails(html);
      expect(before, classification).toContain(markClass);
      // aria-hidden: the chip right beside it already carries the word.
      expect(before).toMatch(/ws-finding__mark[^>]*aria-hidden="true"/);
    }
  });

  it("puts \"Next step\" inside the SAME comparison as a third fact, not a separate paragraph", () => {
    // Finding-level requires_decision only (not the evaluation's, which would
    // also render DecisionControl — that needs a live session and has its own
    // browser coverage in decision.spec.ts).
    const html = card(
      { classification: "DEVIATION", requires_decision: true },
      { classification: "DEVIATION", expected_value: { presence: "PRESENT" } },
    );
    const { before } = splitAtDetails(html);
    // One `.ws-facts--compare` block; "Next step" is a dt/dd pair inside it,
    // not a second, separately-styled element after it.
    expect((before.match(/ws-facts--compare/g) ?? []).length).toBe(1);
    expect(before).toMatch(/<dt>Next step<\/dt><dd class="ws-facts__next">/);
    // The old standalone paragraph class is gone.
    expect(before).not.toContain("ws-eval__next");
  });

  it("omits the Next Step column entirely when there is nothing to act on — never an empty cell", () => {
    // MATCH with no legal_position.view: rule_outcome is omitted, finding
    // does not require a decision -> nextStep() returns null.
    const html = card(
      { classification: "MATCH" },
      {
        classification: "MATCH", actual_value: { presence: "PRESENT" },
        rule_outcome: undefined, expected_value: undefined,
      } as unknown as Partial<Evaluation>,
    );
    const { before } = splitAtDetails(html);
    expect(before).not.toContain("Next step");
  });
});

/**
 * The three user-facing statuses (owner, 2026-09-08, fifth pass). The four
 * engine classifications are untouched in the data; the card FACE says one of
 * three words, and NOT ACCEPTED fires only on an explicit Constitution citation.
 */
describe("the three-word status on the card face", () => {
  const face = (over: Partial<Finding>, evalOver: Partial<Evaluation> = {}) =>
    splitAtDetails(card(over, evalOver)).before;

  it("maps MATCH to Accepted and every other classification to Needs review", () => {
    expect(face({ classification: "MATCH" }, { classification: "MATCH" })).toMatch(/data-status="ACCEPTED"[^>]*>Accepted</);
    for (const classification of ["DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE"]) {
      const html = face({ classification }, { classification });
      expect(html, classification).toMatch(/data-status="NEEDS_REVIEW"[^>]*>Needs review</);
      expect(html, classification).not.toMatch(/Not accepted/);
    }
  });

  it("never infers Not accepted from a DEVIATION, a MISSING or an UNACCEPTABLE rule outcome", () => {
    for (const classification of ["DEVIATION", "MISSING"]) {
      const html = face(
        { classification, requires_decision: true },
        { classification, rule_outcome: "UNACCEPTABLE" },
      );
      expect(html, classification).toMatch(/Needs review/);
      expect(html, classification).not.toMatch(/Not accepted/);
      // And it does not tell the reader the contract must be modified.
      expect(html, classification).not.toMatch(/must be (modified|changed|amended)/i);
    }
  });

  it("shows Not accepted, with the Constitution citation, only when the server sends one", () => {
    const html = card(
      { classification: "DEVIATION", requires_decision: true },
      {
        classification: "DEVIATION", rule_outcome: "UNACCEPTABLE",
        actual_value: { cap_status: "UNLIMITED" }, expected_value: { preferred: 12, unit: "MONTHS" },
        constitution_prohibition: { section: "9", quote: "Unlimited liability is Unacceptable." },
      },
    );
    const { before, inside } = splitAtDetails(html);
    expect(before).toMatch(/data-status="NOT_ACCEPTED"[^>]*>Not accepted</);
    expect(before).toContain("ws-finding__mark--bad");
    expect(before).toMatch(/Legal Constitution §9: “Unlimited liability is Unacceptable\.”/);
    // The engine's own words are still there, one click away.
    expect(inside).toMatch(/DEVIATION/);
    expect(inside).toMatch(/Not acceptable/);
  });

  it("ignores an empty or null prohibition — an incomplete citation is no citation", () => {
    const cases: Array<{ section: string; quote: string } | null> =
      [null, { section: "", quote: "x" }, { section: "9", quote: "" }];
    for (const prohibition of cases) {
      const html = face(
        { classification: "DEVIATION" },
        { classification: "DEVIATION", constitution_prohibition: prohibition },
      );
      expect(html).toMatch(/Needs review/);
      expect(html).not.toMatch(/Not accepted|Legal Constitution/);
    }
  });

  it("keeps every technical field inside the disclosure and off the face", () => {
    const html = card(
      { classification: "DEVIATION", requires_decision: true },
      { classification: "DEVIATION", rule_outcome: "UNACCEPTABLE", operator: "!=",
        actual_value: { cap_value: 24, cap_unit: "MONTHS" }, expected_value: { preferred: 12, unit: "MONTHS" } },
    );
    const { before, inside } = splitAtDetails(html);
    for (const tech of ["DEVIATION", "RESIDUALS-NDA-001", "PRESENCE-v1", ">!=<", "Not acceptable", "Classification"]) {
      expect(before, tech).not.toContain(tech);
      expect(inside, tech).toContain(tech);
    }
    // The four reader questions stay on the face.
    expect(before).toMatch(/Residuals/);
    expect(before).toMatch(/24 MONTHS/);
    expect(before).toMatch(/12 MONTHS/);
    expect(before).toMatch(/Next step/i);
  });
});
