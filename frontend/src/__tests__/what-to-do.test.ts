import { describe, expect, it } from "vitest";

import { whatToDo } from "@/components/workspace/findingLanguage";
import type { Evaluation, Finding } from "@/lib/types";

const f = (over: Partial<Finding>): Finding => ({
  id: "f", review_id: "r", requirement: { code: null, name: "X" }, classification: "DEVIATION",
  status: "OPEN", requires_decision: false, escalated: false, evaluations: [], evidence: [],
  user_status: "REQUIRES_MODIFICATION", in_our_favour: false, ...over,
} as unknown as Finding);
const e = (over: Partial<Evaluation> = {}) => ({ current_decision: null, ...over } as unknown as Evaluation);

describe("whatToDo — one action per card, agreeing with the status (PLAIN-LANGUAGE §4)", () => {
  it("offers our wording only when the server holds it", () => {
    expect(whatToDo(f({}), e(), "REQUIRES_MODIFICATION", true)).toBe("Send our standard wording, or Legal decides.");
    expect(whatToDo(f({}), e(), "REQUIRES_MODIFICATION", false)).toBe("Legal decides this one.");
    const missing = f({ classification: "MISSING", user_status: "MISSING" });
    expect(whatToDo(missing, e(), "MISSING", true)).toBe("Ask the client to add our clause.");
    expect(whatToDo(missing, e(), "MISSING", false)).toBe("Legal decides this one.");
  });
  it("matches, in our favour, needs a decision, and the lawyer's own words", () => {
    const match = f({ classification: "MATCH", user_status: "ACCEPTABLE" });
    expect(whatToDo(match, e(), "ACCEPTABLE", true)).toBe("Nothing to do.");
    expect(whatToDo(f({ in_our_favour: true, user_status: "ACCEPTABLE" }), e(), "ACCEPTABLE", true))
      .toBe("You can accept this.");
    const decide = f({ classification: "CONFLICT", user_status: "NEEDS_DECISION", status: "DECISION_REQUIRED" });
    expect(whatToDo(decide, e(), "NEEDS_DECISION", true)).toBe("Legal decides this one.");
    expect(whatToDo(decide, e(), "NEEDS_DECISION", false, true)).toBe("Read it and decide.");
  });
});
