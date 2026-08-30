/**
 * The three rendering rules of the assist surface (AB-3/AB-4):
 *   a refusal renders quietly, never with the error treatment;
 *   a score is labeled a retrieval score, and "confidence" appears nowhere
 *   (AI-03 item 16, rule 12);
 *   an evaluator-routed reply points at Reviews rather than answering (AM-25 r4).
 *
 * Static render assertions, the house idiom — interaction flows belong to the
 * Playwright suite.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnswerView } from "@/components/AskPanel";
import type { AskResult } from "@/lib/types";

function result(overrides: Partial<AskResult>): AskResult {
  return {
    conversation_id: "c-1",
    message_id: "m-1",
    answer_state: "ANSWERED",
    text: "",
    routed_to_evaluator: false,
    citations: [],
    ...overrides,
  };
}

describe("AnswerView", () => {
  it("renders an answer with its citation and a labeled retrieval score", () => {
    const html = renderToStaticMarkup(
      <AnswerView
        result={result({
          text: "Ninety days written notice is required [1].",
          citations: [
            {
              chunk_id: "ch-1",
              page_number: 7,
              section_ref: "22",
              excerpt: "Either party may terminate on ninety days prior written notice.",
              retrieval_score: 0.6213,
            },
          ],
        })}
      />,
    );
    expect(html).toContain("Ninety days written notice");
    expect(html).toContain("§22");
    expect(html).toContain("p.7");
    expect(html).toContain("retrieval score 0.621");
    // AI-03 item 16 / rule 12: no confidence figure anywhere on this surface.
    expect(html.toLowerCase()).not.toContain("confidence");
  });

  it("renders a refusal quietly, never with the error treatment", () => {
    const html = renderToStaticMarkup(
      <AnswerView
        result={result({
          answer_state: "NO_EVIDENCE_RETRIEVED",
          text: "Information not found in the selected document. The available material does not answer this question.",
        })}
      />,
    );
    expect(html).toContain("Information not found");
    expect(html).toContain("ask-answer--refusal");
    expect(html.toLowerCase()).not.toContain("error");
    expect(html).not.toContain("role=\"alert\"");
  });

  it("keeps the two refusal causes visually identical in markup shape", () => {
    // AM-29 r4's UI corollary: nothing rendered may distinguish "empty corpus"
    // from "authorization exclusion" — the server sends one wording, and the
    // component adds no state-specific decoration beyond the shared refusal class.
    const wordings = (["NO_EVIDENCE_RETRIEVED", "EVIDENCE_INSUFFICIENT"] as const).map(
      (state) =>
        renderToStaticMarkup(
          <AnswerView result={result({ answer_state: state, text: "Same words." })} />,
        ).replace(state, "STATE"),
    );
    expect(wordings[0]).toBe(wordings[1]);
  });

  it("shows the evaluator pointer for a compliance-shaped question", () => {
    const html = renderToStaticMarkup(
      <AnswerView
        result={result({
          answer_state: "EVIDENCE_INSUFFICIENT",
          routed_to_evaluator: true,
          text: "That determination is made by the deterministic evaluator — run or open a Review.",
        })}
      />,
    );
    expect(html).toContain("deterministic evaluator");
    expect(html).toContain("ask-answer--routed");
  });
});
