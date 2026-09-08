/**
 * The workspace Ask pane's three message shapes — static render, house idiom.
 * `WsAnswerView` needs the highlight context, so it is rendered inside the provider.
 * Interaction (the real refusal path, byte-identical wording) lives in the browser
 * suite, where the real backend refuses under the real AM-31 posture.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { WsAnswerView } from "@/components/workspace/AskDock";
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
    expect(html).toContain("§22");
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

  it("an evaluator-routed reply is a third type — labelled as not answered here, not a refusal", () => {
    const html = render(result({ routed_to_evaluator: true, text: "This asks whether the document meets the standard — see Findings." }));
    expect(html).toContain("ws-ask__answer--routed");
    expect(html).toContain("Compared by the evaluator, not the assistant");
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
        source_clause: "9.9 Widget Handling", content: "Widgets shall be handled with care.", retrieval_score: 0.5 }],
    }));
    expect(html).toContain("Approved position");
    expect(html).toContain("TESTPOS-MSA-001");
    expect(html).toContain("9.9 Widget Handling");
    expect(html).toContain("Widgets shall be handled with care.");
    expect(html).not.toContain("confidence");
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

  it("with no Review yet, the handoff offers to open the document rather than a sentence of prose", () => {
    const html = renderWithContract(result({ routed_to_evaluator: true, text: "No analysis yet.", comparison: null }));
    expect(html).toContain("Open the document to run analysis");
  });
});
