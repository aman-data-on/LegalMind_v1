/**
 * The workspace Ask pane's three message shapes — static render, house idiom.
 * `WsAnswerView` needs the highlight context, so it is rendered inside the provider.
 * Interaction (the real refusal path, byte-identical wording) lives in the browser
 * suite, where the real backend refuses under the real AM-31 posture.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

// The comparison table reads the caller's permissions (the standard column needs
// `legal_position.view`); a static render has no session provider.
vi.mock("@/lib/session", () => ({ useSession: () => ({ can: () => true }) }));

import { WsAnswerView } from "@/components/workspace/AskDock";
import { clauseRef } from "@/components/workspace/ComparisonTable";
import { TranscriptTurn } from "@/components/workspace/TranscriptTurn";
import { HighlightProvider } from "@/components/workspace/highlight";
import type { AskResult } from "@/lib/types";

function result(overrides: Partial<AskResult>): AskResult {
  return {
    conversation_id: "c-1", message_id: "m-1", answer_state: "ANSWERED", text: "",
    routed_to_evaluator: false,
    // The version the answer was read from — always present on a real reply.
    document_version_id: "dv-1", version_number: 1,
    citations: [], ...overrides,
  };
}
const render = (r: AskResult) =>
  renderToStaticMarkup(<HighlightProvider><WsAnswerView result={r} /></HighlightProvider>);

describe("WsAnswerView", () => {
  it("an answer's citation is a button that points at its EVIDENCE row, and shows no retrieval score", () => {
    const html = render(result({
      text: "Ninety days written notice is required [1].",
      citations: [{ chunk_id: "ch-1", evidence_id: "ev-9", page_number: 7, section_ref: "22",
                    excerpt: "Either party may terminate on ninety days prior written notice.", retrieval_score: 0.6213 }],
    }));
    expect(html).toContain('data-evidence-id="ev-9"');
    expect(html).toContain("22 · p.7");
    expect(html).not.toContain("§");
    expect(html).toContain("p.7");
    expect(html).not.toContain("retrieval score");
    expect(html.toLowerCase()).not.toContain("confidence");
  });

  it("a refusal renders on the same quiet surface — no error role, no error class", () => {
    const html = render(result({ answer_state: "NO_EVIDENCE_RETRIEVED",
      text: "Information not found in the selected document. The available material does not answer this question." }));
    expect(html).toContain("ws-ask__answer--refusal");
    expect(html).toContain('data-state="NO_EVIDENCE_RETRIEVED"');
    expect(html).not.toContain('role="alert"');
    expect(html).not.toContain("ws-state--error");
  });

  it("the two refusal causes render identically apart from the state attribute", () => {
    const text = "Information not found in the selected document. The available material does not answer this question.";
    const a = render(result({ answer_state: "NO_EVIDENCE_RETRIEVED", text }));
    const b = render(result({ answer_state: "EVIDENCE_INSUFFICIENT", text }));
    expect(a.replace("NO_EVIDENCE_RETRIEVED", "X")).toBe(b.replace("EVIDENCE_INSUFFICIENT", "X"));
  });

  it("an outage reply keeps its quoted passages' Sources as interactive entries", () => {
    // Demo audit 2026-10-14: a model outage is EVIDENCE_INSUFFICIENT now (D6), and the
    // passages its floor quotes must stay inspectable, as in an answer.
    const text = "Gemini could not be reached just now.\n\nSources\n\n- D14: 6 · Data Loss";
    const source = { key: "D14", kind: "document" as const, location: "6 · Data Loss",
                     text: "Provider shall have no liability for any loss of Customer Data." };
    const withSources = render(result({ answer_state: "EVIDENCE_INSUFFICIENT", text,
                                        sources: [source] }));
    const without = render(result({ answer_state: "EVIDENCE_INSUFFICIENT", text }));
    expect(withSources).toContain("ws-ask__answer--refusal");
    expect(withSources).toContain('class="ws-ask__srcbtn"');   // opens the passage
    expect(without).not.toContain('class="ws-ask__srcbtn"');
  });

  it("an evaluator-routed reply is a third type — labelled as not answered here, not a refusal", () => {
    const html = render(result({ routed_to_evaluator: true, text: "This asks whether the document meets the standard — see Findings." }));
    expect(html).toContain("ws-ask__answer--routed");
    expect(html).toContain("From the contract review — the same check as the Dashboard");
    expect(html).not.toContain("ws-ask__answer--refusal");
  });
});


const renderWithContract = (r: AskResult) =>
  renderToStaticMarkup(
    <HighlightProvider>
      <WsAnswerView result={r} contractId="c-1" />
    </HighlightProvider>,
  );

describe("multi-source answers (2026-09-08)", () => {
  it("quotes an approved position in its own labelled section with its own citation grammar", () => {
    const html = render(result({
      text: "The document says ninety days [1].",
      positions: [{ position_chunk_id: "p-1", standard_code: "TESTPOS-MSA-001", document_type: "MSA",
        source_clause: "9.9 Widget Handling", content: "Widgets shall be handled with care.", standard_version: 1, ratification_status: "ACTIVE", retrieval_score: 0.5 }],
    }));
    expect(html).toContain("Company standard");
    expect(html).toContain("TESTPOS-MSA-001");
    expect(html).toContain("9.9 Widget Handling");
    expect(html).toContain("Widgets shall be handled with care.");
    expect(html).not.toContain("confidence");
  });

  it("names the standard's version, because a citation without one does not say WHICH position", () => {
    const html = render(result({
      positions: [{ position_chunk_id: "p-1", standard_code: "TESTPOS-MSA-001", document_type: "MSA",
        source_clause: "9.9 Widget Handling", content: "Widgets shall be handled with care.",
        standard_version: 3, ratification_status: "ACTIVE", retrieval_score: 0.5 }],
    }));
    expect(html).toContain("v3");
    // ACTIVE is the common case: stamping it on every citation is noise that trains
    // the eye to skip the field, which is precisely when a DRAFT needs to be seen.
    expect(html).not.toContain("ACTIVE");
    expect(html).not.toContain("Superseded");
  });

  it("marks a position that is NOT the active one, so a reader is never quoted a superseded standard silently", () => {
    for (const [status, word] of [["DRAFT", "Draft"], ["DEPRECATED", "Superseded"]] as const) {
      const html = render(result({
        positions: [{ position_chunk_id: "p-1", standard_code: "TESTPOS-MSA-001", document_type: "MSA",
          source_clause: "9.9", content: "Widgets shall be handled with care.",
          standard_version: 2, ratification_status: status, retrieval_score: 0.5 }],
      }));
      expect(html).toContain(word);
      expect(html).toContain("ws-ask__standard-state");
    }
  });

  it("an older record with no version recorded degrades quietly rather than rendering a hole", () => {
    const html = render(result({
      positions: [{ position_chunk_id: "p-1", standard_code: "TESTPOS-MSA-001", document_type: "MSA",
        source_clause: "9.9", content: "Widgets shall be handled with care.",
        standard_version: null, ratification_status: null, retrieval_score: null }],
    }));
    expect(html).toContain("TESTPOS-MSA-001");
    expect(html).not.toContain("vnull");
    expect(html).not.toContain("· v");
  });

  it("a comparison handoff shows the Findings by classification in words and links to them — no dead end", () => {
    const html = renderWithContract(result({
      routed_to_evaluator: true, text: "Compared by the evaluator.",
      comparison: { review_id: "r-1", review_status: "ANALYSIS_COMPLETE",
        findings_by_classification: { MATCH: 3, DEVIATION: 1, MISSING: 2 } },
    }));
    expect(html).toContain("ws-ask__answer--routed");
    expect(html).toContain("Open the Findings");
    expect(html).toContain("DEVIATION");
    expect(html).toContain("MISSING");
  });

  it("with no Review yet, the reply says to run the analysis — and offers no link back to the page the reader is on", () => {
    // 2026-10-15: the dock IS the document's page, so "Open the document to run
    // analysis" went nowhere — and it showed on an analysed document whose replayed
    // turn had lost its comparison. The routed text says what to do.
    const html = renderWithContract(result({ routed_to_evaluator: true, text: "No analysis yet.", comparison: null }));
    expect(html).toContain("No analysis yet.");
    expect(html).not.toContain("Open the document to run analysis");
  });

  it("with a Review, the reply is the evaluator's side-by-side table, not counts and a link", () => {
    // The panel passes the Review — a live answer's own, or the newest of a replayed
    // turn's version (2026-10-15). The table loads the Findings itself.
    const html = renderToStaticMarkup(
      <HighlightProvider>
        <WsAnswerView result={result({ routed_to_evaluator: true, text: "Compared.", comparison: null })}
                      contractId="c-1" reviewId="r-1" />
      </HighlightProvider>,
    );
    expect(html).toContain("ws-ask__answer--routed");
    expect(html).toContain("Reading the evaluator");
    expect(html).not.toContain("Open the Findings");
    expect(html).not.toContain("Open the document to run analysis");
  });
});

describe("the comparison table's clause reference (2026-10-15)", () => {
  const row = (over: object) => ({ id: "e", relationship_type: "PRIMARY", page_number: null,
    section_number: null, section_title: null, content: "", source_type: "PARAGRAPH", ...over });

  it("uses the parser's number, else the number the row's own text states, else its passage", () => {
    expect(clauseRef(row({ section_number: "12.1", section_title: "Termination" })))
      .toBe("§12.1 · Termination");
    expect(clauseRef(row({ content: "1.1 This Addendum amends the MSA." }))).toBe("1.1");
    expect(clauseRef(row({ content: "Each Party shall keep it confidential." }))).toBe("Passage 1");
    expect(clauseRef(undefined)).toBe("No clause found");
  });
});

describe("a chat file's temporary contract review (AM-143, 2026-10-15)", () => {
  it("renders the engine's Findings that came with the answer — no Review to fetch, no link to a Contract", () => {
    const finding = {
      id: "f-1", review_id: "temporary", classification: "DEVIATION", status: "OPEN",
      requires_decision: true, escalated: false, user_status: "REQUIRES_MODIFICATION",
      requirement: { code: "LIABILITY-001", name: "Liability", version_id: "rv",
                     version_number: 1 },
      evaluations: [{ id: "e-1", finding_id: "f-1", scope_key: "GENERAL", scope_label: null,
        evaluation_kind: "PRIMARY", classification: "DEVIATION",
        actual_value: { cap_value: 3, cap_unit: "MONTHS" }, evaluated_facts: {},
        evidence_refs: [], diagnostics: [], evaluator_type: "NUMERIC_COMPARISON",
        evaluator_version: "v1", requires_decision: true, current_decision: null,
        created_at: null, expected_value: { preferred: 6, unit: "MONTHS" } }],
      evidence: [{ id: "ev", relationship_type: "PRIMARY", page_number: null,
        section_number: "1", section_title: "Limitation of Liability",
        content: "Liability shall not exceed 3 months of fees paid.", source_type: "PARAGRAPH" }],
      created_at: null, updated_at: null,
    };
    const html = renderToStaticMarkup(
      <TranscriptTurn contractId={null} turn={{
        id: "m-2", ordinal: 1, role: "ASSISTANT", content: "Compared by the contract review.",
        answer_state: "EVIDENCE_INSUFFICIENT", routed_to_evaluator: true, citations: [],
        document_version_id: null, version_number: null,
        comparison: { review_id: null, review_status: "TEMPORARY", temporary: true,
          filename: "msa.docx", findings_by_classification: { DEVIATION: 1 },
          findings: [finding] as never },
      }} />,
    );
    expect(html).toContain("ws-chat__table");
    expect(html).toContain("Liability");
    expect(html).toContain("1 · Limitation of Liability");     // the clause it read
    expect(html).not.toContain("Reading the evaluator");        // nothing fetched
    expect(html).not.toContain("/dashboard?id=");               // no Contract to open
    expect(html).toContain("File reviewed: msa.docx");          // a chat may hold several
  });

  it("says so when no approved standard applied to the file", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn contractId={null} turn={{
        id: "m-3", ordinal: 1, role: "ASSISTANT", content: "Compared by the contract review.",
        answer_state: "EVIDENCE_INSUFFICIENT", routed_to_evaluator: true, citations: [],
        document_version_id: null, version_number: null,
        comparison: { review_id: null, review_status: "TEMPORARY", temporary: true,
          filename: "law.docx", findings_by_classification: {}, findings: [] },
      }} />,
    );
    expect(html).toContain("None of the approved standards applied to this file.");
    expect(html).not.toContain("This Review holds no Findings");
  });
});

describe("a routed question that quotes a clause (AM-149, 2026-10-16)", () => {
  const finding = (id: string, evidenceId: string, name: string) => ({
    id, review_id: "r", classification: "DEVIATION", status: "OPEN",
    requires_decision: true, escalated: false, user_status: "REQUIRES_MODIFICATION",
    requirement: { code: `${name.toUpperCase()}-MSA-001`, name, version_id: "rv", version_number: 1 },
    evaluations: [{ id: `e-${id}`, finding_id: id, scope_key: "GENERAL", scope_label: null,
      evaluation_kind: "PRIMARY", classification: "DEVIATION",
      actual_value: { cap_value: 15, cap_unit: "DAYS" }, evaluated_facts: {},
      evidence_refs: [], diagnostics: [], evaluator_type: "NUMERIC_COMPARISON",
      evaluator_version: "v1", requires_decision: true, current_decision: null,
      created_at: null, expected_value: { preferred: 30, unit: "DAYS" } }],
    evidence: [{ id: evidenceId, relationship_type: "PRIMARY", page_number: 2,
      section_number: "13", section_title: "Service Termination", content: "…",
      source_type: "NATIVE_TEXT" }],
    created_at: null, updated_at: null,
  });
  const clause = { evidence_ids: ["ev-13"], location: "§13 · Service Termination · page 2",
    changes: [{ deleted: "A 30-day prior notice period is applicable.",
                inserted: "The Customer may terminate on 15 days notice." }] };

  it("shows that clause's Findings and what the markup changes — not the whole document", async () => {
    const { ComparisonTable } = await import("@/components/workspace/ComparisonTable");
    const html = renderToStaticMarkup(
      <ComparisonTable contractId={null} clause={clause}
        findings={[finding("f-13", "ev-13", "Cure period"),
                   finding("f-9", "ev-9", "Liability")] as never} />);
    expect(html).toContain("The clause you quoted: <strong>§13 · Service Termination · page 2</strong>");
    expect(html).toContain("Removed: <del>A 30-day prior notice period is applicable.</del>");
    expect(html).toContain("Added: <ins>The Customer may terminate on 15 days notice.</ins>");
    expect(html).toContain("Cure period");
    expect(html).not.toContain("Liability");                       // another clause's
    expect(html).toContain("Show all 2 findings for this document"); // never hidden
  });

  it("says so when no approved standard measured the quoted clause", async () => {
    const { ComparisonTable } = await import("@/components/workspace/ComparisonTable");
    const html = renderToStaticMarkup(
      <ComparisonTable contractId={null} clause={clause}
        findings={[finding("f-9", "ev-9", "Liability")] as never} />);
    expect(html).toContain("No approved standard measured this clause");
    expect(html).not.toContain("ws-chat__table");
  });
});
