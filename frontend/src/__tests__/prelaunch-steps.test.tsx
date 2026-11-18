/** Prelaunch walk 2026-11-18: the next step where the deal waited on nobody. */
import { describe, expect, it } from "vitest";

import { nextStep } from "@/lib/nextStep";

const owner = { viewer: "owner" as const, canAnswer: true };

describe("prelaunch steps", () => {
  it("U1: changes only Legal answers, not yet sent — Send to Legal is the owner's step", () => {
    const counts = { changes_total: 3, changes_left: 3, changes_left_for_me: 0, points_open: 3 };
    expect(nextStep({ ...owner, stage: "CLIENT_RETURNED", counts, canSendToLegal: true })?.kind).toBe("sendToLegal");
    expect(nextStep({ ...owner, stage: "CLIENT_RETURNED", counts, canSendToLegal: false })).toBeNull();
    expect(nextStep({ ...owner, stage: "CLIENT_RETURNED", counts: { ...counts, changes_left_for_me: 2 },
                      canSendToLegal: true })?.kind).toBe("answerChanges");
  });
});
