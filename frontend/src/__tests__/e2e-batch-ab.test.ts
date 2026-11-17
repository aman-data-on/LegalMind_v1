/** E2E fix batch A/B (AM-393, AM-398, UX L1/S4): one primary per person per stage. */
import { describe, expect, it } from "vitest";

import { salesLine, salesStatus, type ClientChange } from "@/lib/changes";
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
    expect(salesLine(c, false)).toBe("Legal answers this");
    expect(salesStatus([c], false)).toBe("Your turn: send the client's changes to Legal.");
    expect(salesStatus([c], true)).toMatch(/^With Legal/);
  });
});
