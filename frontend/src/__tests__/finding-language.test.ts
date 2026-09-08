/**
 * The Finding, in a reader's language (owner request, 2026-09-08).
 *
 * Every case here is one the screenshots or the live database actually produced,
 * and the module's whole job is to be honest about data it did not get. So the
 * two properties worth pinning are: it says something a non-lawyer can act on
 * when the data supports it, and it says NOTHING — `null`, or a plain statement
 * that the value was not recorded — when the data does not. A helper that
 * guesses a sentence is worse than one that returns null, because the guess
 * looks authoritative.
 */

import { describe, expect, it } from "vitest";

import {
  classificationSentence,
  evidenceLocation,
  evidenceNote,
  excerpt,
  nextStep,
  reasoningSteps,
  requirementTitle,
  userStatus,
  constitutionProhibition,
  findingSentence,
  reviewHeadline,
  sameAsTitle,
  sideOf,
  standardSideOf,
} from "@/components/workspace/findingLanguage";
import type { Evaluation, Evidence, Finding } from "@/lib/types";

function finding(over: Partial<Finding> = {}): Finding {
  return {
    id: "f1",
    review_id: "r1",
    requirement: { code: "RESIDUALS-NDA-001", name: "RESIDUALS-NDA-001", version_id: "v1", version_number: 1 },
    classification: "MISSING",
    status: "DECISION_REQUIRED",
    requires_decision: true,
    escalated: false,
    evaluations: [],
    evidence: [],
    created_at: null,
    updated_at: null,
    ...over,
  } as Finding;
}

function evaluation(over: Partial<Evaluation> = {}): Evaluation {
  return {
    id: "e1",
    finding_id: "f1",
    scope_key: "GENERAL",
    scope_label: null,
    evaluation_kind: "PRIMARY",
    classification: "MISSING",
    actual_value: { presence: "ABSENT" },
    evaluated_facts: null,
    evidence_refs: [],
    diagnostics: [],
    evaluator_type: "PRESENCE",
    evaluator_version: "PRESENCE-v1",
    requires_decision: true,
    current_decision: null,
    created_at: null,
    ...over,
  } as Evaluation;
}

describe("the requirement's title", () => {
  it("spells out the abbreviations our own codes use", () => {
    expect(requirementTitle({ code: "GOVLAW-NDA-001" })).toBe("Governing law");
    expect(requirementTitle({ code: "CONF-SURVIVAL-MSA-001" })).toBe("Confidentiality survival");
    expect(requirementTitle({ code: "LIAB-CARVEOUTS-MSA-001" })).toBe("Liability carve-outs");
    expect(requirementTitle({ code: "IP-OWNERSHIP-MSA-001" })).toBe("Ip ownership");
  });

  it("parses the code when configuration names the requirement after itself", () => {
    // The live database: every ratified standard has `name = code`, because
    // `import_ratified_standards.py` falls back to the code. The old heading
    // ran that through a generic label helper and produced "Residuals nda 001"
    // — the document-type token and the sequence number rendered as words.
    expect(requirementTitle({ code: "RESIDUALS-NDA-001", name: "RESIDUALS-NDA-001" }))
      .toBe("Residuals");
    expect(requirementTitle({ code: "CONF-SURVIVAL-NDA-001", name: "CONF-SURVIVAL-NDA-001" }))
      .toBe("Confidentiality survival");
    expect(requirementTitle({ code: "EARLY-TERM-RESTRICTION-MSA-001", name: null }))
      .toBe("Early termination restriction");
  });

  it("prefers a real name whenever configuration carries one", () => {
    expect(requirementTitle({ code: "X-MSA-001", name: "Liability cap" })).toBe("Liability cap");
  });

  it("never returns an empty heading", () => {
    expect(requirementTitle({ code: null, name: null })).toBe("Requirement");
    expect(requirementTitle(null)).toBe("Requirement");
    // A code made only of stripped tokens still has to render as something.
    expect(requirementTitle({ code: "NDA-001", name: "NDA-001" })).toBe("NDA-001");
  });
});

describe("what the outcome means, in one sentence", () => {
  it("puts every classification the engine can produce into words", () => {
    for (const classification of ["MATCH", "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE"]) {
      const sentence = classificationSentence(classification);
      expect(sentence, classification).toBeTruthy();
      // The sentence explains; it never restates the enum at the reader.
      expect(sentence).not.toContain(classification);
    }
  });

  it("returns null rather than inventing a sentence for a value it does not know", () => {
    expect(classificationSentence("SOMETHING_NEW")).toBeNull();
  });
});

describe("what happens next", () => {
  it("names the person when the server flagged that one is needed", () => {
    expect(nextStep(finding(), evaluation())).toMatch(/legal authority/i);
  });

  it("states a recorded decision as settled", () => {
    const decided = evaluation({
      requires_decision: false,
      current_decision: { decision_type: "ACCEPT_DEVIATION" } as never,
    });
    expect(nextStep(finding({ requires_decision: false }), decided)).toMatch(/recorded/i);
  });

  it("answers by what was found, never by the rule outcome — so it reads the same with or without legal_position.view", () => {
    // The rule outcome ("No rule covers this") is a legal position and lives in
    // the disclosure; the next step is workflow guidance a Sales reader needs
    // on every card, so it is never null for a real classification.
    const withOutcome = nextStep(finding(), evaluation({ rule_outcome: "NOT_APPLICABLE" }));
    const without = nextStep(finding(), evaluation());
    expect(withOutcome).toBe(without);
    expect(without).toMatch(/legal authority/i);
    expect(without).not.toMatch(/rule|applicable/i);
  });

  it("gives every classification its own step, and only a MATCH needs nothing", () => {
    const step = (c: string) => nextStep(finding({ classification: c }), evaluation({ classification: c }));
    expect(step("MATCH")).toBe("No action is needed.");
    expect(step("DEVIATION")).toMatch(/review this difference/);
    expect(step("MISSING")).toMatch(/decide whether this must be added/);
    expect(step("CONFLICT")).toMatch(/which of the contradicting provisions applies/);
    expect(step("UNABLE_TO_EVALUATE")).toMatch(/legal or business decision may be required/i);
  });

  it("says what WOULD make a deviation or an absence Accepted — conditionally, never as an instruction to amend", () => {
    for (const c of ["DEVIATION", "MISSING"]) {
      const step = nextStep(finding({ classification: c }), evaluation({ classification: c }))!;
      expect(step).toMatch(/would make (it|this) Accepted/);
      expect(step).not.toMatch(/must be (modified|changed|amended)/i);
    }
    expect(nextStep(finding({ classification: "UNABLE_TO_EVALUATE" }), evaluation({ classification: "UNABLE_TO_EVALUATE" })))
      .not.toMatch(/would make/);
  });

  it("routes Not accepted to a person and never suggests a self-service edit", () => {
    const step = nextStep(finding({ classification: "DEVIATION" }), evaluation({ classification: "DEVIATION" }), "NOT_ACCEPTED");
    expect(step).toMatch(/goes against an approved company position/);
    expect(step).toMatch(/legal authority/i);
    expect(step).not.toMatch(/would make/);
  });
});

describe("the one sentence a Sales reader gets — built from the data, for every requirement", () => {
  const cap = { code: "LIABILITY-MSA-001", name: "LIABILITY-MSA-001", version_id: "v1", version_number: 1 };

  it("MATCH names the value when there is one", () => {
    expect(findingSentence(
      finding({ requirement: cap, classification: "MATCH" }),
      evaluation({ classification: "MATCH", actual_value: { cap_value: 12, cap_unit: "MONTHS" }, expected_value: { preferred: 12, unit: "MONTHS" } }),
    )).toBe("The document's liability is 12 MONTHS, which matches the company standard.");
    expect(findingSentence(
      finding({ classification: "MATCH" }),
      evaluation({ classification: "MATCH", actual_value: { presence: "PRESENT" }, expected_value: { presence: "PRESENT" } }),
    )).toBe("The document includes residuals, as the company standard requires.");
  });

  it("DEVIATION states both values when it has them, and only the contract's when the standard is omitted", () => {
    const both = evaluation({ classification: "DEVIATION", actual_value: { cap_value: 8, cap_unit: "PERCENT_PER_MONTH" }, expected_value: { preferred: 5, unit: "PERCENT_PER_MONTH" } });
    expect(findingSentence(finding({ requirement: { ...cap, code: "LATE-FEE-TOS-001", name: "LATE-FEE-TOS-001" }, classification: "DEVIATION" }), both))
      .toBe("The document sets late fee at 8 PERCENT_PER_MONTH, while the company standard expects 5 PERCENT_PER_MONTH.");
    const omitted = evaluation({ classification: "DEVIATION", actual_value: { cap_value: 24, cap_unit: "MONTHS" } });
    delete (omitted as { expected_value?: unknown }).expected_value;
    expect(findingSentence(finding({ requirement: cap, classification: "DEVIATION" }), omitted))
      .toBe("The document sets liability at 24 MONTHS, which differs from the company standard.");
  });

  it("DEVIATION reads an unlimited cap as 'no limit'", () => {
    expect(findingSentence(
      finding({ requirement: cap, classification: "DEVIATION" }),
      evaluation({ classification: "DEVIATION", actual_value: { cap_status: "UNLIMITED" }, expected_value: { preferred: 12, unit: "MONTHS" } }),
    )).toBe("The document sets no limit on liability, while the company standard expects 12 MONTHS.");
  });

  it("MISSING says the standard requires it only when the standard was sent", () => {
    expect(findingSentence(finding(), evaluation({ expected_value: { presence: "PRESENT" } })))
      .toBe("The document does not include residuals, which the company standard requires.");
    expect(findingSentence(finding(), evaluation()))
      .toBe("The document does not include residuals.");
  });

  it("UNABLE_TO_EVALUATE distinguishes 'no standard recorded' from 'document unreadable on this point'", () => {
    const noStandard = evaluation({ classification: "UNABLE_TO_EVALUATE", actual_value: null, expected_value: null });
    expect(findingSentence(finding({ classification: "UNABLE_TO_EVALUATE" }), noStandard))
      .toMatch(/no approved company standard recorded for residuals/);
    const unreadable = evaluation({ classification: "UNABLE_TO_EVALUATE", actual_value: { cap_status: "UNKNOWN" }, expected_value: { preferred: 3, unit: "YEARS" } });
    expect(findingSentence(finding({ classification: "UNABLE_TO_EVALUATE" }), unreadable))
      .toMatch(/does not say enough about residuals/);
  });

  it("CONFLICT and an unknown classification still produce a sentence, never null for the five real ones", () => {
    expect(findingSentence(finding({ classification: "CONFLICT" }), evaluation({ classification: "CONFLICT", actual_value: { caps: [{}, {}] } })))
      .toBe("The document contains provisions on residuals that contradict each other.");
    for (const c of ["MATCH", "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE"]) {
      expect(findingSentence(finding({ classification: c }), evaluation({ classification: c })), c).toBeTruthy();
    }
  });

  it("never prints a requirement code, an enum or JSON at the reader", () => {
    for (const c of ["MATCH", "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE"]) {
      const text = findingSentence(finding({ classification: c }), evaluation({ classification: c, actual_value: { wibble: 1 } }))!;
      expect(text).not.toMatch(/RESIDUALS-NDA-001|ABSENT|PRESENT|\{|MISSING|DEVIATION/);
    }
  });
});


describe("a recorded value as one phrase", () => {
  it("reads the PRESENCE evaluator's shape", () => {
    expect(sideOf({ presence: "ABSENT" })).toEqual({ tone: "absent", text: "Not found" });
    expect(sideOf({ presence: "PRESENT" })).toEqual({ tone: "present", text: "Found" });
    expect(sideOf({ presence: "INDETERMINATE" })).toEqual({ tone: "unknown", text: "Unclear" });
  });

  it("reads the numeric evaluator's shape on both sides, keeping the basis verbatim", () => {
    // Measured shapes. `FEES_PAID` and `FEES_PAID_FOR_AFFECTED_SERVICES` are
    // NOT interchangeable (45B.4), so the token is never reworded.
    expect(sideOf({ scope: "GENERAL", cap_unit: "DAYS", cap_basis: "FORCE_MAJEURE", cap_value: 30.0 }))
      .toEqual({ tone: "value", text: "30 DAYS", detail: "FORCE_MAJEURE" });
    expect(sideOf({ unit: "YEARS", preferred: 3 }))
      .toEqual({ tone: "value", text: "3 YEARS" });
  });

  it("gives a concrete value NO tick — a tick beside a number reads as 'satisfied'", () => {
    expect(sideOf({ unit: "YEARS", preferred: 3 }).tone).toBe("value");
  });

  it("reads an unextracted cap as absent, not as zero", () => {
    expect(sideOf({ cap_status: "ABSENT" })).toEqual({ tone: "absent", text: "Not found" });
  });

  it("counts conflicting provisions instead of picking one", () => {
    // Which provision prevails is exactly what the engine could not decide.
    const side = sideOf({ caps: [{ cap_value: 6 }, { cap_value: null }] });
    expect(side.text).toBe("2 separate limits stated");
    expect(side.tone).toBe("unknown");
  });

  it("says 'not recorded' for null, and never prints JSON at the reader", () => {
    expect(sideOf(null)).toEqual({ tone: "unknown", text: "Not recorded" });
    expect(sideOf(undefined)).toEqual({ tone: "unknown", text: "Not recorded" });
    const odd = sideOf({ something: "unexpected", nested: { a: 1 } });
    expect(odd.text).not.toContain("{");
    expect(odd.text).not.toContain("something");
  });
});

describe("why this was flagged — the reasoning chain", () => {
  it("runs Requirement → This document → Company standard → Result", () => {
    const steps = reasoningSteps(finding(), evaluation({ rule_outcome: "NOT_APPLICABLE", expected_value: { presence: "PRESENT" } }), 0);
    expect(steps.map((s) => s.label))
      .toEqual(["Requirement", "This document", "Company standard", "Result"]);
    expect(steps[1]!.text).toBe("No matching provision was found.");
    expect(steps[2]!.text).toMatch(/expects this to be present/i);
    expect(steps[3]!.text).toBe("Recorded as MISSING.");
  });

  it("drops the standard step entirely when it is omitted for this caller", () => {
    // LEGAL-02 omits `expected_value`; SEC-07 says omit, never null. So the
    // chain reads Requirement → This document → Result, with no empty row and
    // no "not available" placeholder standing in for a legal position.
    const steps = reasoningSteps(finding(), evaluation(), 0);
    expect(steps.map((s) => s.label)).toEqual(["Requirement", "This document", "Result"]);
  });

  it("counts the passages it actually has, and says so when it has none", () => {
    const one = reasoningSteps(finding({ classification: "MATCH" }), evaluation({
      classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["a"],
    }), 1);
    expect(one[1]!.text).toMatch(/1 passage/);
    const many = reasoningSteps(finding({ classification: "MATCH" }), evaluation({
      classification: "MATCH", actual_value: { presence: "PRESENT" }, evidence_refs: ["a", "b", "c"],
    }), 3);
    expect(many[1]!.text).toMatch(/3 passages/);
    // Present, but nothing cited — stated plainly rather than implied.
    const bare = reasoningSteps(finding({ classification: "MATCH" }), evaluation({
      classification: "MATCH", actual_value: { presence: "PRESENT" },
    }), 0);
    expect(bare[1]!.text).toMatch(/no supporting passage/i);
  });

  it("never renders an empty step, which is what the old explainer did", () => {
    // The defect this replaces: "How this result was reached" over a bare
    // numbered list whose items were engine notes — or nothing at all.
    for (const c of ["MATCH", "DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE"]) {
      const steps = reasoningSteps(finding({ classification: c }), evaluation({ classification: c }), 0);
      for (const step of steps) {
        expect(step.label.length, c).toBeGreaterThan(0);
        expect(step.text.trim().length, `${c}/${step.label}`).toBeGreaterThan(0);
      }
    }
  });
});

describe("evidence", () => {
  function row(over: Partial<Evidence> = {}): Evidence {
    return {
      id: "ev1", relationship_type: "PRIMARY", page_number: 3,
      section_number: "11.2", section_title: "Residuals",
      content: "The Receiving Party may use Residuals.", source_type: "NATIVE_TEXT",
      ...over,
    };
  }

  it("names where a passage sits, using only the parts that exist", () => {
    expect(evidenceLocation(row(), 0)).toBe("§11.2 · Residuals · page 3");
    expect(evidenceLocation(row({ section_number: null, section_title: null }), 0))
      .toBe("page 3");
    // Nothing at all still gives the reader a handle, never an empty control.
    expect(evidenceLocation(row({ section_number: null, section_title: null, page_number: null }), 4))
      .toBe("Passage 5");
  });

  it("flags only the reads that affect trust", () => {
    // `source_type` says HOW the passage was read. Native text says nothing
    // because there is nothing to say.
    expect(evidenceNote("NATIVE_TEXT")).toBeNull();
    expect(evidenceNote("OCR")).toBe("read by OCR");
    expect(evidenceNote("TABLE")).toBe("from a table");
  });

  it("cuts a long passage at a boundary, never mid-word", () => {
    const long = `${"The Receiving Party shall not disclose. ".repeat(20)}End.`;
    const cut = excerpt(long);
    expect(cut.length).toBeLessThan(long.length);
    expect(cut.endsWith("…")).toBe(true);
    expect(cut).not.toMatch(/\w…$/);        // never a severed word
    // A short passage is returned whole, so a caller can compare and decide
    // whether a "show the full passage" control is needed at all.
    expect(excerpt("Short.")).toBe("Short.");
  });
});

describe("the report headline", () => {
  it("leads with what needs a person, because that is the only actionable count", () => {
    expect(reviewHeadline({ total: 7, needsDecision: 4, missing: 1, match: 3 }))
      .toMatch(/^4 points need a person/);
    expect(reviewHeadline({ total: 7, needsDecision: 1, missing: 1, match: 3 }))
      .toMatch(/^1 point needs a person/);
  });

  it("states a clean review as a fact, not as praise or a score", () => {
    const line = reviewHeadline({ total: 5, needsDecision: 0, missing: 0, match: 5 });
    expect(line).toMatch(/All 5 requirements checked match/);
    expect(line).not.toMatch(/\d+%|score|excellent|risk/i);
  });

  it("does not call an empty analysis an approval", () => {
    expect(reviewHeadline({ total: 0, needsDecision: 0, missing: 0, match: 0 }))
      .toMatch(/no ratified requirement/i);
  });
});

describe("a scope that just repeats the title", () => {
  it("is recognised regardless of case or stray whitespace", () => {
    expect(sameAsTitle("Residuals", "Residuals")).toBe(true);
    expect(sameAsTitle("RESIDUALS", "residuals")).toBe(true);
    expect(sameAsTitle("  Residuals  ", "Residuals")).toBe(true);
  });

  it("is false when the scope actually adds information", () => {
    expect(sameAsTitle("Aggregate", "Liability cap")).toBe(false);
  });
});

describe("the Company Standard column reads as an expectation, not a search result", () => {
  it("reads a presence-shaped standard as Required / Not required", () => {
    // `expected_presence: PRESENT` in the ratified config is paired with
    // `applicability: REQUIRED` — this is a direct reading of that pair, not
    // an invented distinction.
    expect(standardSideOf({ presence: "PRESENT" })).toEqual({ tone: "present", text: "Required" });
    expect(standardSideOf({ presence: "ABSENT" })).toEqual({ tone: "unknown", text: "Not required" });
  });

  it("gives 'Not required' no mark — it is not a defect, just a fact about the standard", () => {
    expect(standardSideOf({ presence: "ABSENT" }).tone).not.toBe("absent");
  });

  it("leaves every other shape exactly as sideOf renders it", () => {
    expect(standardSideOf({ unit: "YEARS", preferred: 3 })).toEqual(sideOf({ unit: "YEARS", preferred: 3 }));
    expect(standardSideOf(null)).toEqual(sideOf(null));
    expect(standardSideOf({ presence: "INDETERMINATE" })).toEqual(sideOf({ presence: "INDETERMINATE" }));
  });
});

describe("the three-word user-facing status (owner, 2026-09-08)", () => {
  const f = (classification: string, evaluations: Array<Partial<Evaluation>> = [{}]) =>
    ({ classification, evaluations: evaluations as Evaluation[] });

  it("maps the four engine classifications onto exactly two of the three words", () => {
    expect(userStatus(f("MATCH"))).toBe("ACCEPTED");
    expect(userStatus(f("DEVIATION"))).toBe("NEEDS_REVIEW");
    expect(userStatus(f("MISSING"))).toBe("NEEDS_REVIEW");
    expect(userStatus(f("UNABLE_TO_EVALUATE"))).toBe("NEEDS_REVIEW");
    expect(userStatus(f("CONFLICT"))).toBe("NEEDS_REVIEW");
  });

  it("treats an unknown classification as needing review — the honest default", () => {
    expect(userStatus(f("SOMETHING_NEW"))).toBe("NEEDS_REVIEW");
  });

  it("never reads an UNACCEPTABLE rule outcome as Not accepted", () => {
    expect(userStatus(f("DEVIATION", [{ rule_outcome: "UNACCEPTABLE" }]))).toBe("NEEDS_REVIEW");
    expect(userStatus(f("MISSING", [{ rule_outcome: "UNACCEPTABLE" }]))).toBe("NEEDS_REVIEW");
  });

  it("is Not accepted only on an explicit, complete Constitution citation", () => {
    const cited = { section: "9", quote: "Unlimited liability is Unacceptable." };
    expect(userStatus(f("DEVIATION", [{ constitution_prohibition: cited }]))).toBe("NOT_ACCEPTED");
    expect(constitutionProhibition(f("DEVIATION", [{}, { constitution_prohibition: cited }]))).toEqual(cited);
    expect(userStatus(f("DEVIATION", [{ constitution_prohibition: null }]))).toBe("NEEDS_REVIEW");
    expect(userStatus(f("DEVIATION", [{ constitution_prohibition: { section: "9", quote: "" } }]))).toBe("NEEDS_REVIEW");
    expect(constitutionProhibition(f("MATCH"))).toBeNull();
  });
});

