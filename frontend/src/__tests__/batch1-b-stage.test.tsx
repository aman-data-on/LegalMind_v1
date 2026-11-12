/**
 * Batch 1, slice B: one stage truth (c) and Legal's queue (e). Presentation only — the
 * facts are the server's counts; nothing here asserts a legal conclusion.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { summaryCount } from "@/components/workspace/AnalysisPanel";
import { StageBadge } from "@/components/workspace/StageBadge";
import { changesWords, closedWords, finalReady, stageLine } from "@/lib/labels";
import { nextStep, taskAction } from "@/lib/nextStep";

const answered = { changes_total: 4, changes_left: 0, changes_ours: 0, changes_left_for_me: 0 };
const owner = { viewer: "owner" as const, canAnswer: true, stage: "CLIENT_RETURNED" as const };

describe("the final contract waits on open points", () => {
  it("says Ready only with no point open, and fails closed when points are unknown", () => {
    expect(stageLine("CLIENT_RETURNED", { ...answered, points_open: 3 })).not.toContain("Ready");
    expect(stageLine("CLIENT_RETURNED", { ...answered, points_open: 0, points_waiting: 0 })).toContain("Ready");
    expect(finalReady(answered)).toBe(false);                       // absent: closed
    // keep-ours answers still lead to our reply, whatever the points
    expect(stageLine("CLIENT_RETURNED", { ...answered, changes_ours: 1, points_open: 3 }))
      .toBe("Changes answered, reply next");
  });
  it("makes Send to Legal the step, never Prepare final contract", () => {
    const counts = { ...answered, points_open: 3 };
    expect(nextStep({ ...owner, counts, canSendToLegal: true })?.kind).toBe("sendToLegal");
    expect(nextStep({ ...owner, counts, packageReady: true })).toBeNull();   // with Legal already
    expect(nextStep({ ...owner, counts: { ...answered, points_open: 0, points_waiting: 0 } })?.kind).toBe("prepareFinal");
    expect(taskAction({ kind: "client_returned", counts })).not.toBe("Prepare final contract");
  });
});

describe("one turn marker", () => {
  it("is drawn only when the caller says it is this reader's turn", () => {
    const stage = { stage: "CLIENT_RETURNED" as const, since: new Date().toISOString(), days: 0 };
    expect(renderToStaticMarkup(<StageBadge stage={stage} />)).not.toContain("Your turn");
    const marked = renderToStaticMarkup(<StageBadge stage={stage} ourTurn />);
    expect(marked).toContain(">Your turn<");
    expect(marked).toContain("ws-dealstage--turn");
  });
});

describe("who answers, not who may", () => {
  it("gives the Answer changes primary only to whoever the changes belong to (LA-18)", () => {
    const counts = { changes_total: 81, changes_left: 2, changes_left_for_me: 2 };
    expect(nextStep({ ...owner, counts })?.kind).toBe("answerChanges");
    expect(nextStep({ ...owner, counts, answersChanges: false })).toBeNull();
  });
  it("names the holder for a lawyer who does not hold the review", () => {
    const base = { points: "3 open points", open: 3, canDecide: true, notSent: false, waiting: 0, decided: 0,
                   required: 3 };
    expect(summaryCount({ ...base, assignee: "Counsel" }))
      .toBe("3 open points are with Counsel. You can also decide them.");
    expect(summaryCount({ ...base, mine: true, points: "3 points to decide" })).toBe("3 points to decide.");
  });
  it("says the owner's remaining changes need Legal", () => {
    expect(changesWords({ changes_total: 4, changes_left: 3, changes_left_for_me: 0 })).toBe("3 of 4 changes need Legal");
    expect(changesWords({ changes_total: 4, changes_left: 1, changes_left_for_me: 0 })).toBe("1 of 4 changes needs Legal");
  });
});

describe("a client's closed deals, said once", () => {
  it("reads the same on both client pages", () => {
    expect(closedWords({ final_documents: 1, signed_documents: 2 })).toBe("1 final · 2 signed");
    expect(closedWords({ final_documents: 0, signed_documents: 1 })).toBe("1 signed");
    expect(closedWords({})).toBe("None yet");
  });
});
