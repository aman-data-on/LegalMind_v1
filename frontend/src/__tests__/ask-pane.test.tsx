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
  it("an answer's citation is a button that points at its EVIDENCE row, with a labelled retrieval score", () => {
    const html = render(result({
      text: "Ninety days written notice is required [1].",
      citations: [{ chunk_id: "ch-1", evidence_id: "ev-9", page_number: 7, section_ref: "22",
                    excerpt: "Either party may terminate on ninety days prior written notice.", retrieval_score: 0.6213 }],
    }));
    expect(html).toContain('data-evidence-id="ev-9"');
    expect(html).toContain("§22");
    expect(html).toContain("p.7");
    expect(html).toContain("retrieval score 0.621");
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
    expect(html).toContain("Not answered here");
    expect(html).not.toContain("ws-ask__answer--refusal");
  });
});
