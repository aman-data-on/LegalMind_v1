/**
 * Batch 1, slice C: points truth and small fixes. Presentation only — every fact is the
 * server's (`in_our_favour`, `measured`, `points_waiting`, `name`); nothing here asserts
 * a legal conclusion (rule 21).
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { StandardForm } from "@/components/configuration/StandardForm";
import { AnswerAnglesView } from "@/components/workspace/Angles";
import { explanation, readerWord as changeWord, type ClientChange } from "@/lib/changes";
import { choicesForLegal } from "@/components/diff-talk/text";
import { ForUs } from "@/components/workspace/ChangesPane";
import { FindingCard, inBucket } from "@/components/workspace/FindingsPane";
import { clauseAndPage, excerpt, figureOf, pointState } from "@/components/workspace/findingLanguage";
import { HighlightProvider } from "@/components/workspace/highlight";
import { contractFacts, type StatusBucket } from "@/components/workspace/model";
import { POINT_STATUS_ORDER } from "@/components/workspace/PointStatus";
import { CountsCell } from "@/components/workspace/StageBadge";
import { nameFromFilename } from "@/lib/documentTypes";
import type { Contract, Evaluation, Finding, RequirementVersion, ReviewAngles } from "@/lib/types";

// the Review's angles, as the server sends them: a counter-proposal for f1 and one
// across-the-document observation on its passage
vi.mock("@/components/workspace/Angles", async (original) => ({
  ...(await original<typeof import("@/components/workspace/Angles")>()),
  useReviewAngles: () => ({
    legal: { actionable: 1, matching: 0, items: [] },
    observations: { structural: [{ kind: "X", clauses: ["4"], evidence_ids: ["ev1"],
                                   text: "Clause 4 and clause 9 state two notice periods." }],
                    additional: [] },
    counter_proposals: {},
  }),
  FindingCounterProposal: () => <aside>Recommended wording to send back</aside>,
}));

function finding(over: Partial<Finding> = {}): Finding {
  const evaluation = {
    id: "e1", finding_id: "f1", scope_key: "GENERAL", scope_label: null,
    evaluation_kind: "PRIMARY", classification: "DEVIATION",
    actual_value: { cap_value: 45, cap_unit: "DAYS" }, evaluated_facts: null,
    evidence_refs: ["ev1"], diagnostics: [], evaluator_type: "NUMERIC_COMPARISON",
    evaluator_version: "v1", requires_decision: false, current_decision: null,
    created_at: null, rule_outcome: "ACCEPTABLE", explanation: [],
  } as unknown as Evaluation;
  return {
    id: "f1", review_id: "r1",
    requirement: { code: "PAYMENT-PERIOD-MSA-001", name: "Payment period", version_id: "v1", version_number: 1 },
    classification: "DEVIATION", status: "OPEN", requires_decision: false, escalated: false,
    evaluations: [evaluation],
    evidence: [{ id: "ev1", relationship_type: "PRIMARY", page_number: 3, section_number: "4",
                 section_title: null, content: "Invoices are paid within 45 days.", source_type: "NATIVE_TEXT" }],
    created_at: null, updated_at: null, user_status: "ACCEPTABLE", in_our_favour: true,
    ...over,
  } as Finding;
}

const render = (f: Finding) => renderToStaticMarkup(
  <HighlightProvider>
    <FindingCard finding={f} onChanged={() => {}} prepared={null} explanation={null} />
  </HighlightProvider>,
).replace(/<[^>]*>/g, " ");

describe("(d) in our favour, from the server's flag", () => {
  it("a favour point says In our favour, never Matches, and offers no wording to send back", () => {
    expect(pointState(finding())).toBe("favour");
    const text = render(finding());
    expect(text).toContain("In our favour");
    expect(text).not.toContain("Matches");
    expect(text).not.toContain("Recommended wording");
  });
  it("a matching point offers no wording either; a change needed still does", () => {
    const match = finding({ classification: "MATCH", in_our_favour: false });
    expect(pointState(match)).toBe("matches");
    expect(render(match)).not.toContain("Recommended wording");
    const change = finding({ user_status: "REQUIRES_MODIFICATION", in_our_favour: false });
    expect(render(change)).toContain("Recommended wording");
  });
  it("says what was noted across the document on the point's clause", () => {
    expect(render(finding())).toContain("Also noted across the document: Clause 4 and clause 9 state two notice periods.");
  });
});

describe("(c) the Points chips add up to All", () => {
  it("puts every point in exactly one mark: 9 matches, 12 open, 2 missing, 1 favour = 24", () => {
    const points = [
      ...Array.from({ length: 9 }, () => finding({ classification: "MATCH", in_our_favour: false })),
      ...Array.from({ length: 12 }, () => finding({ user_status: "NEEDS_DECISION", in_our_favour: false,
                                                     status: "DECISION_REQUIRED" })),
      ...Array.from({ length: 2 }, () => finding({ classification: "MISSING", user_status: "MISSING",
                                                    in_our_favour: false, status: "DECISION_REQUIRED" })),
      finding(),
    ];
    const n = (b: StatusBucket) => points.filter((f) => inBucket(f, b)).length;
    expect(POINT_STATUS_ORDER.map(n)).toEqual([9, 1, 12, 0, 2]);
    for (const f of points) expect(POINT_STATUS_ORDER.filter((b) => inBucket(f, b))).toHaveLength(1);
  });
});

describe("(b) the card's figure and the clause's own name", () => {
  const long = `${"The Customer shall keep records. ".repeat(8)}Invoices are paid within 45 days of receipt. Late sums carry interest.`;
  it("starts the excerpt at the sentence holding the figure", () => {
    const cut = excerpt(long, 160, "45");
    expect(cut).toContain("45 days");
    expect(cut.startsWith("…")).toBe(true);
    expect(excerpt(long, 160)).not.toContain("45");          // no focus: as before
    expect(excerpt("Paid in 145 days. ".repeat(20), 160, "45")).not.toMatch(/^…/);   // never inside 145
    expect(figureOf({ cap_value: 45, cap_unit: "DAYS" })).toBe("45");
    expect(figureOf({ values: ["Mumbai"] })).toBe("Mumbai");
  });
  it("names a repeated clause number by its own words", () => {
    expect(clauseAndPage({ section_number: "2", page_number: 3, name: "Invoicing and Payment" }, 0))
      .toBe("Clause 2 — Invoicing and Payment, page 3");
    expect(clauseAndPage({ section_number: "7.", page_number: null }, 0)).toBe("Clause 7");
  });
});

describe("(f) titles and facts", () => {
  it("takes the stacked extensions and the date stamp off a file name", () => {
    expect(nameFromFilename("26 10 26 - X MSA (G&G).docx.md")).toBe("X MSA (G&G)");
    expect(nameFromFilename("RSA.pdf")).toBe("RSA");
    expect(nameFromFilename("acme_msa-v2 final.docx")).toBe("acme msa v2 final");
    expect(nameFromFilename("no-extension")).toBe("no extension");
  });
  it("never shows a Ref id", () => {
    const facts = contractFacts({ id: "c0ffee12", contract_type: "MSA" } as Contract, "Acme");
    expect(facts.join(" ")).not.toContain("Ref");
  });
});

describe("(g) a list-type standard is edited as JSON", () => {
  it("opens CATEGORICAL in raw mode, with no Value or Unit field", () => {
    const version = {
      id: "v", version_number: 2, name: "Seat", description: null, evaluator_type: "CATEGORICAL",
      created_at: null,
      company_standard: { document_type: "MSA", allowed_values: ["PUNE"], recognised_values: { PUNE: ["Pune"] } },
    } as RequirementVersion;
    const html = renderToStaticMarkup(
      <StandardForm requirementId="r" version={version} onClose={() => {}} onSaved={() => {}} />);
    expect(html).toContain("This kind of standard is edited as JSON for now.");
    expect(html).not.toMatch(/>Value</);
    expect(html).not.toMatch(/>Unit</);
    expect(html).toContain("allowed_values");
    expect(html).not.toMatch(/<textarea[^>]*disabled/);
  });
});

describe("(h) Compare says chosen, never decided", () => {
  it("the copied list and the Review's words", () => {
    const row = { status: "MODIFIED", left: null, right: { number: "4", title: "Fees" } } as never;
    expect(choicesForLegal("A", "B", [row], {})).toContain("not chosen yet");
    const src = readFileSync(path.join(__dirname, "../components/diff-talk/Review.tsx"), "utf8")
      // words only: no comments, class names or `${code}` inside a template
      .replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "")
      .replace(/is-decided/g, "").replace(/\$\{[^}]*\}/g, "");
    expect(src).not.toMatch(/["'`][^"'`\n]*\b(decided|decision)\b[^"'`\n]*["'`]/i);
  });
});

describe("leftovers", () => {
  it("a package entry's effect words follow measured, as the Changes rows do", () => {
    const html = renderToStaticMarkup(<ForUs effect="NEGATIVE" measured="NOT_MEASURED" />);
    expect(html).not.toContain("Worse for us");
    expect(renderToStaticMarkup(<ForUs effect="NEGATIVE" measured="WORSE" />)).toContain("Worse for us");
  });
  it("the list says the points waiting for the client, as the Summary does", () => {
    const contract = { id: "c", counts: { points_open: 3, points_for_me: 0, points_waiting: 15 },
                       latest_analysis: { review_status: "ANALYSIS_COMPLETE" } } as unknown as Contract;
    expect(renderToStaticMarkup(<CountsCell contract={contract} viewer="owner" />))
      .toContain("15 waiting for the client");
  });
});

describe("verify round 1: one word, and no wording to counter a favour point", () => {
  it("Ask's Legal angle sends no wording back on a point in our favour", () => {
    // the server's payload after the fix: the counter-proposal only on the change
    const angles = {
      business: [], top_risks: [], commercial: {}, observations: { structural: [], additional: [] },
      legal: { actionable: 2, matching: 0, items: [
        { finding_id: "fav", requirement_code: "PAYMENT-PERIOD-MSA-001", title: "Payment period",
          classification: "DEVIATION", waived: false, where: "clause 8.5", evidence_ids: ["ev-8"],
          action: "Accept — it differs from our standard in our favour" },
        { finding_id: "chg", requirement_code: "CURE-PERIOD-MSA-001", title: "Cure period",
          classification: "DEVIATION", waived: false, where: "clause 13", evidence_ids: ["ev-13"],
          action: "Send our wording" }] },
      counter_proposals: { chg: { section: "13", kind: "DRAFTING_LANGUAGE", label: "§13", text: "Thirty days to cure." } },
    } as unknown as ReviewAngles;
    const favourOnly = renderToStaticMarkup(<AnswerAnglesView angles={angles} evidenceIds={["ev-8"]} />)
      .split("Also in this contract")[0]!;
    expect(favourOnly).toContain("in our favour");
    expect(favourOnly).not.toContain("Recommended wording");
    expect(favourOnly).not.toContain("Thirty days to cure");
    expect(renderToStaticMarkup(<AnswerAnglesView angles={angles} evidenceIds={["ev-13"]} />))
      .toContain("Recommended wording to send back");
  });
  it("the Changes read and its explanation say In our favour, as the card does", () => {
    const read = { finding_id: "f", requirement_code: "PAYMENT-PERIOD-MSA-001", classification: "DEVIATION",
                   user_status: "ACCEPTABLE" as const, in_our_favour: true, evaluation_ids: [] };
    const change = { review: { after: [read], before: [] }, review_delta: [] } as unknown as ClientChange;
    expect(changeWord(change)).toBe("In our favour");
    expect(explanation(change, { from: 1, to: 2 })[0]).toContain(": In our favour.");
    const match = { ...change, review: { after: [{ ...read, classification: "MATCH", in_our_favour: false }], before: [] } };
    expect(changeWord(match as ClientChange)).toBeNull();
  });
});
