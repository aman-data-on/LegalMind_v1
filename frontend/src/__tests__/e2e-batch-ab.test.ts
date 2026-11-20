/** E2E fix batch A/B (AM-393, AM-398, UX L1/S4): one primary per person per stage. */
import { describe, expect, it } from "vitest";

import { rowStatus, type ClientChange } from "@/lib/changes";
import { nextStep } from "@/lib/nextStep";

describe("whose turn", () => {
  it("never gives Legal a sales act at Ready to send", () => {
    expect(nextStep({ stage: "READY_TO_SEND", viewer: "legal", canAnswer: true, replyReady: true })).toBeNull();
    expect(nextStep({ stage: "READY_TO_SEND", viewer: "owner", canAnswer: true, replyReady: true })?.kind).toBe("sendReply");
  });
  it("offers Prepare our reply when Legal decided on the client's version", () => {
    expect(nextStep({ stage: "READY_TO_SEND", viewer: "owner", canAnswer: true })?.kind).toBe("prepareReply");
  });
  it("says With Legal only once the changes were sent to Legal", () => {
    const c = { route: "holder", holder_accepted: false, answer: null } as unknown as ClientChange;
    // batch 3+4: the row's one label (the deal's status line is the server's code)
    const reader = { can_answer: true, can_decide: false } as const;
    expect(rowStatus(c, { ...reader, sent_to_legal: false })).toBe("Legal answers this");
    expect(rowStatus(c, { ...reader, sent_to_legal: true })).toBe("With Legal");
  });
});
