/**
 * The Ask workspace's two non-trivial rendering rules — static render, house idiom.
 *
 * 1. `AnswerProse` formats without INTERPRETING: paragraphs and bullets, and every
 *    character of the answer survives. A markdown renderer here would put emphasis,
 *    headings and links into a legal answer that nobody wrote.
 * 2. A replayed turn's citation is a real link into the document at the exact
 *    evidence row, on the version the answer was read from (`?version=&evidence=`).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnswerProse, TranscriptTurn } from "@/components/workspace/TranscriptTurn";
import type { ConversationTurn } from "@/lib/types";

function turn(overrides: Partial<ConversationTurn>): ConversationTurn {
  return {
    id: "m-1", ordinal: 1, role: "ASSISTANT", content: "", answer_state: "ANSWERED",
    routed_to_evaluator: false, document_version_id: "dv-2", version_number: 2,
    citations: [], ...overrides,
  };
}

describe("AnswerProse", () => {
  it("splits blank-line blocks into paragraphs and keeps every word", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"The cap is 12 months of fees [1].\n\nIt excludes bodily injury."} />,
    );
    expect(html).toContain("<p class=\"ws-ask__text\">The cap is 12 months of fees [1].</p>");
    expect(html).toContain("It excludes bodily injury.");
  });

  it("renders a run of bulleted lines as a list, marker removed, text intact", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"- Notice: 90 days\n- Governing law: India"} />,
    );
    expect(html).toContain("<ul class=\"ws-ask__bullets\">");
    expect(html).toContain("<li>Notice: 90 days</li>");
    expect(html).toContain("<li>Governing law: India</li>");
  });

  it("invents no markup from prose punctuation — asterisks and hashes stay text", () => {
    const html = renderToStaticMarkup(<AnswerProse text={"# 17.2 applies *only* to fees"} />);
    expect(html).toContain("# 17.2 applies *only* to fees");
    expect(html).not.toContain("<h1");
    expect(html).not.toContain("<em");
  });
});

describe("a replayed turn on the Ask workspace", () => {
  it("links a citation to the evidence row on the version the answer was read from", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn
        contractId="ct-7"
        turn={turn({
          content: "Ninety days written notice is required [1].",
          citations: [{
            chunk_id: "ch-1", evidence_id: "ev-9", page_number: 18, section_ref: "18.1",
            excerpt: "Either party may terminate on ninety days prior written notice.",
            retrieval_score: 0.61,
          }],
        })}
      />,
    );
    expect(html).toContain("/dashboard?id=ct-7&amp;version=dv-2&amp;evidence=ev-9");
    expect(html).toContain("18.1 · p.18");
    // Rule 12 / AI-03 item 16 — a retrieval score is never rendered as legal weight.
    expect(html.toLowerCase()).not.toContain("confidence");
    expect(html).not.toContain("0.61");
  });

  it("keeps a refusal on the quiet surface, with no error styling", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn
        contractId={null}
        turn={turn({ answer_state: "NO_EVIDENCE_RETRIEVED", content: "Information not found." })}
      />,
    );
    expect(html).toContain("ws-ask__answer--refusal");
    expect(html).not.toContain("ws-state--error");
  });
});
