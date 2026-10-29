/** Ask audit, Phase A (2026-10-29): the e-mail Ask drafts is one card with its own Copy;
 *  a reply that is not an answer offers one way forward; the brand question is answered
 *  with a tap. Synthetic text. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AnswerNextStep, BRAND_QUESTION_START, isDeadEnd } from "@/components/workspace/AnswerNextStep";
import { AnswerProse } from "@/components/workspace/AnswerProse";
import type { ConversationTurn } from "@/lib/types";

const DRAFT = "Here is a holding reply.\n\nDraft for review — not approved company wording:\n\n"
  + "```draft\nSubject: Re: Your points\n\nDear [Name],\n\nThank you.\n```\n\nBefore sending, confirm with Legal.";

const turn = (over: Partial<ConversationTurn>): ConversationTurn => ({
  id: "t", ordinal: 1, role: "ASSISTANT", content: "x", answer_state: "ANSWERED",
  routed_to_evaluator: false, citations: [], document_version_id: null, version_number: null,
  ...over } as ConversationTurn);
const noop = () => {};

describe("the drafted e-mail", () => {
  it("is one card with its own Copy, and its label is not said twice", () => {
    const html = renderToStaticMarkup(<AnswerProse text={DRAFT} />);
    expect(html).toContain('aria-label="Draft email"');
    expect(html).toContain("Copy email");
    expect(html).toContain('class="ws-draft__subject">Subject: Re: Your points');
    expect(html).not.toContain("Draft for review — not approved company wording:");
    expect(html).not.toContain("```");
    expect(html).toContain("Before sending, confirm with Legal.");   // outside the card
  });
});

describe("a reply that is not an answer", () => {
  it("is told apart from answers, fixed replies and reviews", () => {
    expect(isDeadEnd(turn({ answer_state: "EVIDENCE_INSUFFICIENT", answered_by: null, latency_ms: 56000 }))).toBe(true);
    expect(isDeadEnd(turn({ answer_state: "ANSWERED", answered_by: null, latency_ms: 56000 }))).toBe(false);
    expect(isDeadEnd(turn({ answer_state: "NO_EVIDENCE_RETRIEVED", answered_by: null, latency_ms: null }))).toBe(false);
    expect(isDeadEnd(turn({ answer_state: "EVIDENCE_INSUFFICIENT", latency_ms: 900, routed_to_evaluator: true }))).toBe(false);
  });

  it("offers Ask again, or the working model when the chosen one is paused", () => {
    const dead = turn({ answer_state: "EVIDENCE_INSUFFICIENT", answered_by: null, latency_ms: 900 });
    expect(renderToStaticMarkup(<AnswerNextStep turn={dead} question="Q?" switchTo={null}
                                                onAsk={noop} onSwitchAndAsk={noop} />)).toContain("Ask again");
    expect(renderToStaticMarkup(<AnswerNextStep turn={dead} question="Q?" switchTo={{ id: "deepseek", label: "DeepSeek" }}
                                                onAsk={noop} onSwitchAndAsk={noop} />)).toContain("Ask with DeepSeek");
    expect(renderToStaticMarkup(<AnswerNextStep turn={turn({})} question="Q?" switchTo={null}
                                                onAsk={noop} onSwitchAndAsk={noop} />)).toBe("");
  });

  it("answers the brand question with a tap", () => {
    const html = renderToStaticMarkup(<AnswerNextStep
      turn={turn({ content: `${BRAND_QUESTION_START} CloudPe is the cloud platform.` })}
      question="Q?" switchTo={null} onAsk={noop} onSwitchAndAsk={noop} />);
    expect(html).toContain(">Leapswitch</button>");
    expect(html).toContain(">CloudPe</button>");
  });
});

describe("Phase B", () => {
  it("names a Constitution source once", async () => {
    const { legendWhere } = await import("@/components/workspace/AnswerProse");
    expect(legendWhere({ key: "C6", kind: "constitution", location: "", text: "" } as never,
      "§13, Legal Constitution L1.14 · 13. Termination & Suspension")).toBe("§13 · Termination & Suspension");
  });

  it("offers the document or other words after a plain not-found, never a retry", async () => {
    const { isNotFound } = await import("@/components/workspace/AnswerNextStep");
    const nf = turn({ answer_state: "NO_EVIDENCE_RETRIEVED", answered_by: null, latency_ms: null });
    expect(isNotFound(nf)).toBe(true);
    const html = renderToStaticMarkup(<AnswerNextStep turn={nf} question="Q?" switchTo={null}
      onAsk={noop} onSwitchAndAsk={noop} onAttach={noop} onEdit={noop} />);
    expect(html).toContain("Attach the document");
    expect(html).toContain("Reword the question");
    expect(html).not.toContain("Ask again");
  });

  it("starts a chat on a model that can answer", async () => {
    const { startingModel } = await import("@/components/workspace/ModelPicker");
    const m = (id: string, extra = {}) => ({ id, label: id, default: false, configured: true, paused: false, ...extra });
    expect(startingModel([m("gemini", { default: true, paused: true }), m("deepseek")])).toBe("deepseek");
    expect(startingModel([m("gemini", { default: true }), m("deepseek")])).toBe("gemini");
    expect(startingModel([m("gemini", { default: true, paused: true })])).toBe("gemini");   // none can: the default
  });
});
