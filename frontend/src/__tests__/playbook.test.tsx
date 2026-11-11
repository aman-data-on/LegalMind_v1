import { describe, expect, it } from "vitest";

import type { ClientChange } from "@/lib/changes";
import { grouped, offerFor, OFFER_WORDS, type PlaybookPoint } from "@/lib/playbook";

const CAP: PlaybookPoint = {
  requirement_code: "LIABILITY-MSA-001", kind: "RANGE",
  opening: { value: 6, unit: "MONTHS", basis: "FEES_PAID_FOR_AFFECTED_SERVICES" },
  line: "We start at 6 months of fees for the affected services. You can agree up to 12 months of total fees, the same for both sides. Anything more goes to Legal.",
  room: true,
};
const LAW: PlaybookPoint = { requirement_code: "GOVLAW-MSA-001", kind: "LEGAL_ONLY", opening: null, line: "Legal decides any change.", room: false };

const change = (code: string, effect: ClientChange["effect_for_us"]) => ({
  effect_for_us: effect, ...(effect === "NEGATIVE" ? { measured: "WORSE" } : {}), after: { evidence_ids: ["e"], text: "t" },
  review: { before: [], after: [{ finding_id: "f", requirement_code: code, classification: "MATCH",
                                  user_status: "ACCEPTABLE", evaluation_ids: [] }] },
}) as unknown as ClientChange;

describe("what we can offer (AM-305)", () => {
  it("reads within from the server's effect_for_us, never from the figures", () => {
    expect(offerFor(change(CAP.requirement_code, "NEUTRAL"), [CAP])).toEqual({ point: CAP, within: true, fallback: false });
    expect(offerFor(change(CAP.requirement_code, "FALLBACK"), [CAP])).toEqual({ point: CAP, within: true, fallback: true });
    expect(offerFor(change(CAP.requirement_code, "POSITIVE"), [CAP])?.within).toBe(true);
    expect(offerFor(change(CAP.requirement_code, "NEGATIVE"), [CAP])?.within).toBe(false);
  });
  it("says nothing for a point Legal alone decides, or one the playbook does not hold", () => {
    expect(offerFor(change(LAW.requirement_code, "NEGATIVE"), [CAP, LAW])).toBeNull();
    expect(offerFor(change("OTHER-001", "POSITIVE"), [CAP])).toBeNull();
    expect(offerFor(change(CAP.requirement_code, "POSITIVE"), null)).toBeNull();
  });
  it("orders room to agree before fixed figures and Legal-only points", () => {
    const fixed = { ...CAP, requirement_code: "CURE", kind: "EXACT" as const, room: false };
    expect(grouped([LAW, fixed, CAP])).toEqual({ room: [CAP], fixed: [fixed], legal: [LAW] });
    expect(OFFER_WORDS.within).toBe("Within what we can offer — you can accept");
    expect(OFFER_WORDS.fallback).toBe("Fallback — you can accept");
    expect(OFFER_WORDS.beyond).toBe("Beyond what we can offer — Legal decides");
  });
});

describe("the Fallback effect (AM-306)", () => {
  it("has its own filter, label and bulk-accept slot, ordered Better / No change / Fallback", async () => {
    const { ACCEPTABLE_EFFECTS, EFFECT_LABEL, matches } = await import("@/lib/changes");
    const { EFFECT_FILTERS } = await import("@/components/workspace/ChangesPane");
    expect(ACCEPTABLE_EFFECTS).toEqual(["POSITIVE", "NEUTRAL", "FALLBACK"]);
    expect(EFFECT_FILTERS.map((f) => f.id)).toEqual(["POSITIVE", "NEUTRAL", "FALLBACK", "NEGATIVE"]);
    expect(EFFECT_LABEL.FALLBACK).toBe("Fallback");
    const list = { can_answer: true, can_decide: false };
    expect(matches(change("X", "FALLBACK"), "FALLBACK", list)).toBe(true);
    expect(matches(change("X", "NEUTRAL"), "FALLBACK", list)).toBe(false);
  });
});
