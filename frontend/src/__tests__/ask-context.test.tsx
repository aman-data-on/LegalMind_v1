/**
 * The context that makes Ask one product rather than two chats (2026-09-11).
 *
 * Two properties, each of which was a real gap before this change:
 *
 *   1. A Finding's "Ask about this" carries the Finding's id, so the server can
 *      seed retrieval with the clause the reader is looking at. It is a retrieval
 *      hint and nothing more — no classification, Rule Outcome or Company Standard
 *      value travels (the backend asserts that end; here we assert the id is
 *      carried and that the question itself is still what the user sees).
 *   2. An obligation is no longer a dead end: it can be asked about without
 *      retyping it.
 */
import { describe, expect, it } from "vitest";

import { nextDraft } from "@/components/workspace/askIntent";

describe("the Finding → Ask handoff", () => {
  it("carries the finding id alongside the editable question", () => {
    const draft = nextDraft(null, "What does this document say about Termination?",
                            "finding-7");
    expect(draft.findingId).toBe("finding-7");
    // The user still sees exactly the question that is asked — the id steers
    // retrieval, it does not add words to the question.
    expect(draft.text).toBe("What does this document say about Termination?");
  });

  it("omits the finding id entirely when there is none, rather than sending null", () => {
    // An obligation is a descriptive fact about the document's text, not a Finding.
    // `JSON.stringify` drops undefined keys, so an ABSENT key never reaches the wire
    // while an explicit null would — and the API forbids unknown/none fields.
    const draft = nextDraft(null, "What does this document say about X?");
    expect("findingId" in draft).toBe(false);
    expect(JSON.stringify(draft)).not.toContain("findingId");
  });

  it("advances the sequence so the same question can be asked twice", () => {
    const first = nextDraft(null, "Why is this a deviation?", "f-1");
    const second = nextDraft(first, "Why is this a deviation?", "f-1");
    expect(second.seq).toBe(first.seq + 1);
  });
});
