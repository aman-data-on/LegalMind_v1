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
import type { AssistStatuteAnswer, ConversationTurn } from "@/lib/types";

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

/**
 * Citation markers as references (Ask target architecture Phase 3, 2026-09-17).
 *
 * The server already renumbers prose markers and the source list into one sequence
 * after verification (PR #68); this is the half that lets a reader follow one. The
 * rules worth pinning are the conservative ones: a marker links ONLY when it has a
 * source to land on, and nothing else in the prose becomes markup.
 */
describe("citation markers in an answer", () => {
  const targetId = (n: number) => `cite-m-9-${n}`;

  it("turns an in-range marker into a reference to its own source", () => {
    const html = renderToStaticMarkup(
      <AnswerProse
        text="The cap is 12 months of total fees [1], and carve-outs are listed [2]."
        citeCount={2}
        citeTargetId={targetId}
      />,
    );
    expect(html).toContain("aria-label=\"Go to source 1\"");
    expect(html).toContain("aria-label=\"Go to source 2\"");
    expect(html).toContain("class=\"ws-ask__ref ws-mono\"");
    // Every word of the answer still survives the round trip.
    expect(html).toContain("The cap is 12 months of total fees ");
    expect(html).toContain(", and carve-outs are listed ");
  });

  it("leaves a marker with no source behind it as plain text", () => {
    // One citation, but the model wrote [2]. A reference that goes nowhere is worse
    // than a number, so it stays a number.
    const html = renderToStaticMarkup(
      <AnswerProse text="Clause 7 governs notice [2]." citeCount={1} citeTargetId={targetId} />,
    );
    expect(html).toContain("[2]");
    expect(html).not.toContain("ws-ask__ref");
  });

  it("links nothing when the turn carries no source list", () => {
    const html = renderToStaticMarkup(<AnswerProse text="The cap is 12 months [1]." />);
    expect(html).toContain("[1]");
    expect(html).not.toContain("ws-ask__ref");
    expect(html).not.toContain("<button");
  });

  it("does not treat a bracketed aside as a citation", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text="Notice is 90 days [see §7.2]." citeCount={3} citeTargetId={targetId} />,
    );
    expect(html).toContain("[see §7.2]");
    expect(html).not.toContain("ws-ask__ref");
  });

  it("links markers inside bullets too, marker stripped only from the bullet itself", () => {
    const html = renderToStaticMarkup(
      <AnswerProse
        text={"- Cap: 12 months of total fees [1]\n- Carve-outs: bodily injury [2]"}
        citeCount={2}
        citeTargetId={targetId}
      />,
    );
    expect(html).toContain("<ul class=\"ws-ask__bullets\">");
    expect(html).toContain("aria-label=\"Go to source 1\"");
    expect(html).toContain("Cap: 12 months of total fees ");
  });

  it("gives every source an id the markers of that turn can reach", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn
        turn={turn({
          id: "m-9",
          content: "The cap is 12 months of total fees [1].",
          citations: [{
            chunk_id: "c-1", evidence_id: "e-1", section_ref: "13", page_number: 4,
            excerpt: "Liability is limited to 12 months of total fees.",
          }] as ConversationTurn["citations"],
        })}
        contractId="k-1"
      />,
    );
    // The marker's target and the source's id are the same string, built by one
    // function — this is the assertion that catches them drifting apart.
    expect(html).toContain("id=\"cite-m-9-1\"");
    expect(html).toContain("aria-label=\"Go to source 1\"");
  });
});

/**
 * A statute answer's markers point at the STATUTE list — never at the document's
 * sources of the same number. The server generates and renumbers Domain C against its
 * own citation order (`service._statute_views` indexes the same `cited` list
 * `_renumber_markers` uses), so the two namespaces must stay apart in the markup too.
 */
describe("a statute answer's citation markers", () => {
  const statuteTurn = turn({
    id: "m-4",
    content: "The organisation's own material does not address this.",
    citations: [],
    statutes: {
      answer_state: "ANSWERED",
      text: "A contract without consideration is void [1].",
      citations: [{
        statute_chunk_id: "s-1",
        citation: "Indian Contract Act, 1872 — s. 25",
        official_title: "Indian Contract Act, 1872",
        section_number: "25", sub_section: null,
        marginal_note: "Agreement without consideration, void",
        excerpt: "An agreement made without consideration is void…",
        retrieval_score: 0.71,
      }],
    } satisfies AssistStatuteAnswer,
  });

  it("links the marker to its own statute source", () => {
    const html = renderToStaticMarkup(<TranscriptTurn turn={statuteTurn} contractId="k-1" />);
    expect(html).toContain("id=\"statute-m-4-1\"");
    expect(html).toContain("aria-label=\"Go to source 1\"");
    // The statute namespace is distinct from the document one, so a statute marker
    // can never land on `cite-m-4-1`.
    expect(html).not.toContain("id=\"cite-m-4-1\"");
  });

  it("gives the statute answer the same paragraph handling as any other answer", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn
        turn={turn({
          ...statuteTurn,
          statutes: {
            ...statuteTurn.statutes!,
            text: "Consideration is required [1].\n\nThere are exceptions.",
          } satisfies AssistStatuteAnswer,
        })}
        contractId="k-1"
      />,
    );
    // Two paragraphs, not one wall — this was a flat <p> before. Counted INSIDE the
    // statute section: the turn's own answer paragraph carries the same class.
    const section = html.slice(html.indexOf("ws-ask__statutes"));
    expect(section.match(/class="ws-ask__text"/g)?.length).toBe(2);
  });
});
