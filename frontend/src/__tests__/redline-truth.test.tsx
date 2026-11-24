/**
 * Batch 1 "redline truth" (client case 2026-11-19): one lawyer queue with ONE primary,
 * the client's Word comments on the change they belong to, the base the changes are
 * compared with, and the tracked edits as a detail — never a headline count.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ChangesBanners, EarlierAnswers } from "@/components/workspace/ChangesBanners";
import { WordComments } from "@/components/workspace/WordComments";
import type { ChangeList, ClientChange } from "@/lib/changes";
import { ACTION, CHANGES_COPY, stageLine } from "@/lib/labels";
import { nextStep, taskAction } from "@/lib/nextStep";

const list = (over: Partial<ChangeList> = {}): ChangeList => ({
  contract_id: "c", from: { document_version_id: "v1", version_number: 1 },
  to: { document_version_id: "v2", version_number: 2 }, summary: { total: 55, untracked: 0 },
  changes: [], can_answer: false, can_decide: true, ...over,
});

describe("one lawyer queue", () => {
  it("leads with the changes Legal holds: one primary, never Decide beside it", () => {
    const legal = { viewer: "legal" as const, canAnswer: false, stage: "INTERNAL_REVIEW" as const };
    const both = nextStep({ ...legal, counts: { changes_left_for_me: 55, points_for_me: 11, points_open: 11 } });
    expect(both).toEqual({ kind: "answerChanges", label: "Answer 55 changes" });
    expect(nextStep({ ...legal, counts: { changes_left_for_me: 0, points_for_me: 11 } })?.label).toBe("Decide 11 points");
    expect(ACTION.answerChangesN(1)).toBe("Answer 1 change");
  });
  it("names no second count beside the one action while changes wait", () => {
    expect(stageLine("INTERNAL_REVIEW", { changes_total: 55, changes_left: 55, points_open: 10 }, "legal")).toBe("With Legal");
    expect(stageLine("INTERNAL_REVIEW", { changes_total: 55, changes_left: 0, points_open: 10 }, "legal")).toBe("With Legal, 10 points");
  });
  it("labels the To-do task with the header's own words", () => {
    expect(taskAction({ kind: "decide", count: 11, changes: 55 })).toBe("Answer 55 changes");
    expect(taskAction({ kind: "decide", count: 11 })).toBe("Decide 11 points");
  });
});

describe("the client's comments and the base", () => {
  it("says who commented, on the change", () => {
    const html = renderToStaticMarkup(<WordComments comments={[{ author: "Counsel", text: "Please confirm." }]} />);
    expect(html).toContain("Comment from Counsel");
    expect(html).toContain("Please confirm.");
    expect(renderToStaticMarkup(<WordComments comments={[]} />)).toBe("");
  });
  it("names the version compared with and lists comments not tied to a change", () => {
    const html = renderToStaticMarkup(<ChangesBanners allUntracked={false} data={list({
      comments_elsewhere: [{ author: "Counsel", text: "A note.", clause: { number: "3", heading: null } }],
    })} />);
    // U2 r4: "Compared with version 1" moved to the Changes bar's row (ChangesPane)
    expect(html).not.toContain("Compared with version 1");
    expect(html).toContain(CHANGES_COPY.commentsElsewhere(1));
    expect(html).toContain("Comment from Counsel");
    expect(html).not.toContain("not marked");                 // no false untracked line
  });
  it("keeps an answer given on an earlier reading, never drops it", () => {
    const change = { earlier_answers: [{ row_key: "N|MODIFIED|a|b", answer: "keep_ours", round: 2, version_number: 1,
      reason: "kept", decided_by: "Counsel", decided_at: "2026-11-19T10:00:00Z" }] } as unknown as ClientChange;
    const html = renderToStaticMarkup(<EarlierAnswers change={change} />);
    expect(html).toContain(CHANGES_COPY.earlierAnswer);
    expect(html).toContain("Counsel");
  });
});

describe("tracked edits are a detail", () => {
  it("never says N changes to M clauses", () => {
    const line = CHANGES_COPY.trackedEdits({ changes: 239, clauses: 47, notes: 3, onto: 0, unmeasured: 21 });
    expect(line).toMatch(/^The client's file has 239 tracked edits in 47 clauses and 3 comments\./);
    expect(line).not.toMatch(/changes to \d+ clauses/);
  });
});
