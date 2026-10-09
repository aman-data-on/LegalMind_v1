/**
 * The Ask workspace's two non-trivial rendering rules — static render, house idiom.
 *
 * 1. `AnswerProse` renders a closed markdown subset and every character of the
 *    answer survives: paragraphs, lists, `**…**`, and since `AM-116` headings, code
 *    and fenced blocks — each guarded so legal prose ("# 17.2 applies", a stray
 *    asterisk) is never turned into markup nobody wrote.
 * 2. A replayed turn's citation is a real link into the document at the exact
 *    evidence row, on the version the answer was read from (`?version=&evidence=`).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnswerMeta, sourceKind } from "@/components/workspace/AnswerProse";
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

  it("bolds the answer's marked key phrase, references still live inside it", () => {
    const html = renderToStaticMarkup(
      <AnswerProse
        text={"**The cap does not cover statutory duties** [1].\n\n- Notice: **90 days**\n- Governing law: India"}
        citeCount={1}
        citeTargetId={(n) => `src-${n}`}
      />,
    );
    expect(html).toContain("<strong>The cap does not cover statutory duties</strong>");
    expect(html).toContain("<li>Notice: <strong>90 days</strong></li>");
    expect(html).toContain("Go to source 1");
    // a lone pair of asterisks is not emphasis, and nothing is lost
    expect(renderToStaticMarkup(<AnswerProse text={"Fees ** are due."} />)).toContain(
      "Fees ** are due.");
  });

  it("renders a run of bulleted lines as a list, marker removed, text intact", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"- Notice: 90 days\n- Governing law: India"} />,
    );
    expect(html).toContain("<ul class=\"ws-ask__bullets\">");
    expect(html).toContain("<li>Notice: 90 days</li>");
    expect(html).toContain("<li>Governing law: India</li>");
  });

  it("renders the multi-source answer's Sources legend as its own list", () => {
    // The exact shape `service._multi_source_text` returns (2026-09-27).
    const html = renderToStaticMarkup(
      <AnswerProse text={"The cap is 12 months [1].\n\nSources\n\n- [1] Legal Constitution L1.10 §9\n- [2] Company Standard LIABILITY-MSA-001"} />,
    );
    expect(html).toContain("<h3 class=\"ws-ask__section\">Sources</h3>");
    expect(html).toContain("<li>[1] Legal Constitution L1.10 §9</li>");
    expect(html).toContain("<li>[2] Company Standard LIABILITY-MSA-001</li>");
  });

  it("heads each layer of a verified answer with the server's own label (AM-107)", () => {
    // The shape `service._layered` returns: the direct answer, then each layer apart.
    const html = renderToStaticMarkup(
      <AnswerProse text={"No early exit is permitted [1].\n\nAlso relevant\n\nEither party may terminate on notice [2].\n\nHistorical context — past negotiated deals, not current policy\n\nTwo past deals differed [1]."} />,
    );
    expect(html).toContain("<p class=\"ws-ask__text\">No early exit is permitted [1].</p>");
    expect(html).toContain("<h3 class=\"ws-ask__section\">Also relevant</h3>");
    expect(html).toContain(
      "<h3 class=\"ws-ask__section\">Historical context — past negotiated deals, not current policy</h3>");
    expect(html.indexOf("No early exit")).toBeLessThan(html.indexOf("Also relevant"));
  });

  it("heads the four parts of a whole-situation answer (2026-10-06)", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"The cap may not cover it all.\n\nWhat we know\n\nAn engineer deleted the data.\n\nWhat needs legal review\n\nThe notification duty."} />,
    );
    expect(html).toContain("<h3 class=\"ws-ask__section\">What we know</h3>");
    expect(html).toContain("<h3 class=\"ws-ask__section\">What needs legal review</h3>");
  });

  it("never makes a heading of model prose that merely contains a label", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"Also relevant is the notice period [2].\n\nSources vary."} />,
    );
    expect(html).not.toContain("<h3");
    expect(html).toContain("Also relevant is the notice period [2].");
  });

  it("renders a server-shaped pipe table as a table, markers as references (AM-108)", () => {
    const html = renderToStaticMarkup(
      <AnswerProse
        text={"Two clauses govern exit [1].\n\n| Clause | What the agreement says |\n|---|---|\n| Term | It runs for the committed term [1] |\n| Exit | An early exit fee is payable [2] |"}
        citeCount={2}
        citeTargetId={(n) => `c-${n}`}
      />,
    );
    expect(html).toContain("<table class=\"ws-ask__table\">");
    expect(html).toContain("<th scope=\"col\">What the agreement says</th>");
    expect(html).toContain("<th scope=\"row\">Term</th>");
    expect(html).toContain("aria-label=\"Go to source 2\"");
    expect(html).not.toContain("|---|");
  });

  it("renders a structured comparison as a diff, each source's marker on its own line", () => {
    const html = renderToStaticMarkup(
      <AnswerProse
        text={"Agreement (cl. 14.3): at least 90 days advance written notice [D63]\nStandard (MSA agreements only): 30 days' written notice [P7]\nDelta: 90 days against 30 days: the agreement is 60 days longer\nLonger than ours.\n\nSources\n\n- D63: 14.3, the selected document\n- P7: §13, MSA agreements only"}
      />,
    );
    expect(html).toContain("<dl class=\"ws-ask__compare\">");
    expect(html).toContain("<dt>Agreement<span class=\"ws-ask__compare-qual\"> (cl. 14.3)</span></dt>");
    expect(html).toContain("<dt>Standard<span class=\"ws-ask__compare-qual\"> (MSA agreements only)</span></dt>");
    expect(html).toContain("ws-ask__compare-row ws-ask__compare-row--delta");
    expect(html).toContain("the agreement is 60 days longer");
    expect(html).toContain("<p class=\"ws-ask__text\">Longer than ours.</p>");
    expect(html).not.toContain("<p class=\"ws-ask__text\">Agreement");
  });

  it("keeps a comparison whose clause number has its own parenthesis, 7.2(b)", () => {
    const html = renderToStaticMarkup(
      <AnswerProse
        text={"Agreement (cl. 7.2(b)): payable within 30 days [D3]\nStandard (MSA agreements only): payable within 45 days [P2]\nDelta: 30 days against 45 days: the agreement is 15 days shorter\n\nSources\n\n- D3: 7.2(b), the selected document\n- P2: §4, MSA agreements only"}
      />,
    );
    expect(html).toContain("<dl class=\"ws-ask__compare\">");
    expect(html).toContain("<span class=\"ws-ask__compare-qual\"> (cl. 7.2(b))</span>");
  });

  it("does not take an ordinary paragraph that starts with a label for a comparison", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"Agreement is needed from both sides.\nStandard terms apply.\nDelta: none."} />,
    );
    expect(html).not.toContain("ws-ask__compare");
  });

  it("leaves a lone pipe line as text — a table needs a header and a row", () => {
    const html = renderToStaticMarkup(<AnswerProse text={"| just | one |"} />);
    expect(html).not.toContain("<table");
    expect(html).toContain("| just | one |");
  });

  it("renders a markdown heading, never a clause reference (AM-116)", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"## Termination rights\n\nEither party may exit.\n\n### What **remains**"} />,
    );
    expect(html).toContain("<h3 class=\"ws-ask__heading\">Termination rights</h3>");
    expect(html).toContain("<h4 class=\"ws-ask__heading\">What <strong>remains</strong></h4>");
  });

  it("keeps a numbered list numbered, from the number it starts at", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"Do these first:\n1. Notify the customer\n2. Preserve the logs\n\n3. Brief counsel"} />,
    );
    expect(html).toContain("<p class=\"ws-ask__text\">Do these first:</p>");
    expect(html).toContain(
      "<ol class=\"ws-ask__bullets\"><li>Notify the customer</li><li>Preserve the logs</li></ol>");
    expect(html).toContain("<ol class=\"ws-ask__bullets\" start=\"3\"><li>Brief counsel</li></ol>");
  });

  it("splits a lead-in, a list and a closing line instead of running them together", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"Two carve-outs apply:\n- bodily injury\n- fraud\nNeither is capped."} />,
    );
    expect(html).toContain("<ul class=\"ws-ask__bullets\"><li>bodily injury</li><li>fraud</li></ul>");
    expect(html).toContain("<p class=\"ws-ask__text\">Neither is capped.</p>");
  });

  it("shows inline code and a fenced block exactly as written", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"Set `**not bold**` [1] here.\n\n```json\n{\"cap\": 12}\n\n- not a list\n```\n\nAfter."}
                   citeCount={1} citeTargetId={(n) => `s-${n}`} />,
    );
    expect(html).toContain("<code class=\"ws-ask__code\">**not bold**</code>");
    expect(html).toContain("aria-label=\"Go to source 1\"");
    expect(html).toContain(
      "<pre class=\"ws-ask__pre\"><code>{&quot;cap&quot;: 12}\n\n- not a list</code></pre>");
    expect(html).toContain("<p class=\"ws-ask__text\">After.</p>");
  });

  it("lets bold wrap a code value, and code keep its text unread", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"Report it **within `6 hours`** under `s. 70B(7)`."} />,
    );
    expect(html).toContain(
      "<strong>within <code class=\"ws-ask__code\">6 hours</code></strong>");
    expect(html).toContain("<code class=\"ws-ask__code\">s. 70B(7)</code>");
    expect(html).not.toContain("**");
  });

  it("sets the agent's ledger keys apart and links each to its Sources entry", () => {
    const html = renderToStaticMarkup(
      <AnswerProse text={"The cap is 12 months. [P8, C2]\n\nSources\n\n- P8: MSA standard\n- C2: §9"} />,
    );
    expect(html).toContain("class=\"ws-ask__keys ws-mono\"");
    expect(html).toContain("aria-label=\"Go to source P8\"");
    expect(html).toContain("aria-label=\"Go to source C2\"");
    // the legend entry the key lands on: its own id, focusable by script only
    const id = /aria-label="Go to source P8"/.test(html)
      && /<li id="([^"]+)" tabindex="-1"><span class="ws-ask__srckey ws-mono">P8 <\/span>/.exec(html);
    expect(html).toContain("class=\"ws-ask__bullets ws-ask__legend\"");
    // the key group keeps to the word before it
    expect(html).toContain("12 months.\u00A0<span class=\"ws-ask__keys");
    expect(id).toBeTruthy();
    // a key with no legend entry stays quiet text, never a dead link
    expect(renderToStaticMarkup(<AnswerProse text={"Capped. [S1]"} />)).not.toContain("<button");
  });

  it("leaves an unclosed fence and a lone backtick as text", () => {
    const html = renderToStaticMarkup(<AnswerProse text={"```\nhalf a block\n\nThe ` mark stays."} />);
    expect(html).not.toContain("<pre");
    expect(html).not.toContain("<code");
    expect(html).toContain("The ` mark stays.");
  });

  it("invents no markup from prose punctuation — asterisks and hashes stay text", () => {
    const html = renderToStaticMarkup(<AnswerProse text={"# 17.2 applies *only* to fees"} />);
    expect(html).toContain("# 17.2 applies *only* to fees");
    expect(html).not.toContain("<h1");
    expect(html).not.toContain("<em");
  });
});

describe("the two speakers (AM-108)", () => {
  it("names the answer's voice and keeps the reader's label for screen readers only", () => {
    const user = renderToStaticMarkup(
      <TranscriptTurn contractId={null} turn={turn({ id: "u", role: "USER", content: "What is the cap?" })} />,
    );
    expect(user).toContain("ws-turn--user");
    expect(user).toContain("<span class=\"ws-ask__role ws-visually-hidden\">You</span>");
    const ai = renderToStaticMarkup(
      <TranscriptTurn contractId={null} turn={turn({ content: "Twelve months of fees [1]." })} />,
    );
    expect(ai).toContain("ws-turn--ai");
    expect(ai).toContain("<p class=\"ws-ask__voice\" aria-hidden=\"true\">");
    expect(ai).toContain("LegalMind");
    expect(ai).not.toContain("sparkle");
  });

  it("keeps a cited passage behind its clause reference", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn
        contractId="ct-7"
        turn={turn({
          content: "Ninety days [1].",
          citations: [{ chunk_id: "ch-1", evidence_id: "ev-9", page_number: 18, section_ref: "18.1",
                        excerpt: "Either party may terminate on ninety days notice.", retrieval_score: 0.6 }],
        })}
      />,
    );
    expect(html).toContain("<details class=\"ws-ask__passage\">");
    expect(html).toContain("<summary>Show the passage</summary>");
    expect(html).toContain("Either party may terminate on ninety days notice.");
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

  it("formats a turn recorded without an answer state — no raw ** on the page", () => {
    const html = renderToStaticMarkup(
      <TranscriptTurn turn={turn({ answer_state: null, content: "A contract **cannot override** the law." })}
                      contractId={null} />,
    );
    expect(html).toContain("<strong>cannot override</strong>");
    expect(html).not.toContain("**");
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

describe("an exact-wording request (AM-109)", () => {
  it("opens the quoted position on a live turn, as the dock does", () => {
    const position = {
      standard_code: "LIABILITY-MSA-001", version_number: 1, status: "ACTIVE",
      title: "Liability", document_type: "MSA", source_clause: "§9", text: "The cap is 12 months.",
    } as unknown as NonNullable<ConversationTurn["positions"]>[number];
    const open = renderToStaticMarkup(
      <TranscriptTurn turn={turn({ content: "Quoted below [1].", positions: [position],
                                   exact_text_requested: true })} contractId={null} />);
    const closed = renderToStaticMarkup(
      <TranscriptTurn turn={turn({ content: "Quoted below [1].", positions: [position] })}
                      contractId={null} />);
    expect(open).toMatch(/<details class="ws-ask__exact" open/);
    expect(closed).not.toMatch(/<details class="ws-ask__exact" open/);
  });
});


describe("the chat page's own rules (2026-10-06)", () => {
  it("dates a chat by the reader's local day, not the UTC day", async () => {
    const { dayGroup } = await import("@/components/workspace/AskWorkspace");
    const tz = process.env.TZ;
    process.env.TZ = "Asia/Kolkata";
    try {
      const now = new Date("2026-10-06T12:00:00+05:30");
      // 01:30 IST on 4 October is 20:00 UTC on the 3rd — it belongs to the 4th.
      expect(dayGroup("2026-10-03T20:00:00Z", now)).toBe("2026-10-04");
      expect(dayGroup("2026-10-06T00:10:00+05:30", now)).toBe("Today");
      expect(dayGroup("2026-10-05T23:50:00+05:30", now)).toBe("Yesterday");
      expect(dayGroup(null, now)).toBe("Earlier");
    } finally {
      process.env.TZ = tz;
    }
  });

  it("treats Enter that commits an IME composition as choosing a word, not sending", async () => {
    const { isImeEnter } = await import("@/components/workspace/AskWorkspace");
    const key = (isComposing: boolean, keyCode: number) =>
      ({ nativeEvent: { isComposing } as KeyboardEvent, keyCode });
    expect(isImeEnter(key(true, 13))).toBe(true);
    expect(isImeEnter(key(false, 229))).toBe(true);   // Safari reports only this
    expect(isImeEnter(key(false, 13))).toBe(false);
  });
});

describe("Sources you can open, and who answered (owner, 2026-10-07)", () => {
  const cap = {
    key: "D58", kind: "document" as const, location: "13.1", scope: "the selected document",
    text: "13.1 The total liability of Leapswitch … shall in no case exceed …",
    evidence_id: "ev-58", document_version_id: "dv-2",
  };
  const text = "The cap is an average of three months' fees. [D58, P4]\n\nSources\n\n" +
    "- D58: 13.1, the selected document\n- P4: §9, MSA agreements only";

  it("turns a legend key with its record into a button that opens it", () => {
    const html = renderToStaticMarkup(<AnswerProse text={text} sources={[cap]} contractId="k-1" />);
    expect(html).toMatch(/<button[^>]*class="ws-ask__srcbtn"[^>]*aria-haspopup="dialog"/);
    expect(html).toContain("This agreement");
    // a key with no record behind it stays a plain entry, as before
    expect(html).toMatch(/<li id="[^"]*-source-P4" tabindex="-1">/);
    // the marker in the prose still lands on the entry: the button carries its id
    expect(html).toMatch(/<button id="[^"]*-source-D58"/);
  });

  it("names each kind of source in the reader's words", () => {
    expect(sourceKind(cap)).toBe("This agreement");
    expect(sourceKind({ ...cap, scope: 'another document: "SLA"' })).toBe("Another document");
    expect(sourceKind({ ...cap, kind: "position" })).toBe("Company standard");
    expect(sourceKind({ ...cap, kind: "statute" })).toBe("Statute");
    expect(sourceKind({ ...cap, kind: "material" })).toBe("Your material");
  });

  it("says which model answered and how long it took — never a score", () => {
    const meta = (t: Parameters<typeof AnswerMeta>[0]["turn"]) =>
      renderToStaticMarkup(<AnswerMeta turn={t} />);
    expect(meta({ answered_by: { label: "DeepSeek", model: "deepseek-v4.1-flash" },
                  latency_ms: 27514 }))
      .toContain("Answered by DeepSeek (deepseek-v4.1-flash) · 27.5 s");
    // a floor: a model ran (there is a time) but code wrote the reply (`AM-122`)
    expect(meta({ answered_by: null, latency_ms: 41200 })).toContain("Model draft not used · 41.2 s");
    // a fixed reply: nothing ran, nothing was timed
    expect(meta({ answered_by: null, latency_ms: null })).toContain("Instant reply · no model used");
    expect(meta({ answered_by: { label: "DeepSeek", model: "deepseek-v4.1-flash" },
                  latency_ms: 1000 })).not.toMatch(/confidence|score/i);
  });
});
