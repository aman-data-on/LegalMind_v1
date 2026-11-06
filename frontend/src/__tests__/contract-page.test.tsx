/**
 * Page 2 — the contract page's one vocabulary (AM-291): before the owner sends a review a
 * point never reads "With Legal"; the Summary repeats the header's stage word and counts
 * the open points once; the place is said as a reader says it.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/workspace/WorkspaceLayout", () => ({ useSideTabs: () => ({ openFindings: () => {} }) }));

import { AttentionLine, summaryCount } from "@/components/workspace/AnalysisPanel";
import { clauseAndPage, pointAnswer } from "@/components/workspace/findingLanguage";
import type { Finding, ReviewProgress } from "@/lib/types";

const open = { status: "DECISION_REQUIRED", requires_decision: true, classification: "DEVIATION",
               evaluations: [{ current_decision: null }] } as unknown as Finding;
const progress = (stage: ReviewProgress["stage"]): ReviewProgress => ({
  stage, outcome: null, superseded_by: null, reopened_at: null, total: 20, required: 15,
  to_decide: 15, clarification: 0, decided: 0, no_action: 0, matches: 5, decided_by_type: {},
  next: { who: "owner", name: "Owner" }, assignee: null });
const stage = { stage: "CLIENT_RETURNED", since: "2026-11-02", days: 0 } as const;

describe("who has an open point (page 2)", () => {
  it("says not sent before the owner sends it, With Legal after, the act to a holder", () => {
    expect(pointAnswer(open, false, false)).toBe("Not sent to Legal yet");   // "Needs" once: the status says it
    expect(pointAnswer(open, false, true)).toBe("With Legal");
    expect(pointAnswer(open, true, false)).toBe("Yours to decide");
  });

  it("says the place once, as a reader says it", () => {
    expect(clauseAndPage({ section_number: "5.3", page_number: 5 }, 0)).toBe("Clause 5.3, page 5");
    expect(clauseAndPage({ section_number: null, page_number: 18 }, 0)).toBe("Page 18");
  });
});

describe("the Summary's first lines (page 2)", () => {
  it("says both nouns from the server's counts, the stage left to the header (AM-291)", () => {
    const counts = { changes_total: 82, changes_left: 81, changes_left_for_me: 19, points_open: 15, points_for_me: 0 };
    const owner = renderToStaticMarkup(<AttentionLine progress={progress("NOT_SENT")} stage={stage}
      viewer="owner" canDecide={false} counts={counts} />);
    expect(owner).not.toContain("Client replied");           // the header's word, said once there
    expect(owner).toContain("15 open points need Legal. Not sent yet.");
    expect(owner).toContain("19 of 82 changes yours");
    expect(owner).not.toContain("Not sent to Legal yet");     // the review stage: Legal details
    expect(owner).not.toContain("Decide");                    // the act is the header's
    // HIGH 2: every change answered, the reply with Legal — the chip and the line agree
    const answered = { changes_total: 82, changes_left: 0, changes_left_for_me: 0, points_open: 17, points_for_me: 17 };
    const holder = renderToStaticMarkup(<AttentionLine progress={progress("WITH_LEGAL")}
      stage={{ ...stage, stage: "INTERNAL_REVIEW" }} viewer="legal" canDecide counts={answered} />);
    expect(holder).toContain("17 points to decide");
    expect(holder).toContain("All 82 changes answered");
    expect(holder).not.toContain("to answer");
  });
});

describe("a signed contract tells one story (owner item (b))", () => {
  it("says Signed and the review is for reference — no open-point counter, no progress bar", () => {
    const counts = { changes_total: 4, changes_left: 2, changes_left_for_me: 1, points_open: 21, points_for_me: 0 };
    const html = renderToStaticMarkup(<AttentionLine progress={{ ...progress("WITH_LEGAL"), assignee: { name: "Counsel" } } as ReviewProgress}
      stage={{ ...stage, stage: "SIGNED" }} viewer="owner" canDecide={false} counts={counts} />);
    expect(html).toContain("The review is kept for reference.");
    expect(html).not.toContain("open point");
    expect(html).not.toContain("Counsel");
    expect(html).not.toContain("<progress");
    expect(html).not.toContain("changes");
  });
});

describe("the Summary's count agrees with its number", () => {
  const base = { points: "", canDecide: false, notSent: true, waiting: 0, decided: 0, required: 3 };
  it("singular and plural, before and after it is sent", () => {
    expect(summaryCount({ ...base, points: "1 open point", open: 1 })).toBe("1 open point needs Legal. Not sent yet.");
    expect(summaryCount({ ...base, points: "3 open points", open: 3 })).toBe("3 open points need Legal. Not sent yet.");
    expect(summaryCount({ ...base, notSent: false, points: "1 open point", open: 1 })).toBe("1 open point is with Legal.");
    expect(summaryCount({ ...base, notSent: false, assignee: "Counsel", points: "2 open points", open: 2, decided: 1 }))
      .toBe("2 open points are with Counsel. 1 of 3 decided.");
  });
  it("draws no meter until a point is decided", () => {
    const counts = { changes_total: 0, changes_left: 0, changes_left_for_me: 0, points_open: 1, points_for_me: 0 };
    const html = renderToStaticMarkup(<AttentionLine progress={{ ...progress("NOT_SENT"), required: 1 }} stage={null}
      viewer="owner" canDecide={false} counts={counts} />);
    expect(html).not.toContain("<progress");
  });
});
