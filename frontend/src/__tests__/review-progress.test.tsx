/**
 * AB-103 (owner, 2026-10-22): the Summary leads with where the review stands — the
 * server's stage in words, the progress in words beside the bar, who acts next — and
 * what was decided, never "Acceptable" for a decided point (rule 14).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/workspace/WorkspaceLayout", () => ({ useSideTabs: () => null }));

import { DecidedRow, StageLine } from "@/components/workspace/AnalysisPanel";
import type { ReviewProgress } from "@/lib/types";

const BASE: ReviewProgress = {
  stage: "WITH_LEGAL", outcome: null, superseded_by: null, reopened_at: null,
  total: 17, required: 11, to_decide: 6, clarification: 0, decided: 5, no_action: 0,
  matches: 6, decided_by_type: {}, next: { who: "reviewer", name: "Nikhil" },
  assignee: { name: "Nikhil", email: "n@example.test" },
};

describe("where the review stands", () => {
  it("names the stage, the reviewer, the progress in words and who acts next", () => {
    const html = renderToStaticMarkup(<StageLine progress={BASE} />);
    expect(html).toContain("With Legal — Nikhil");
    expect(html).toContain("5 of 11 points decided");
    expect(html).toContain('aria-label="5 of 11 points decided"');
    expect(html).toContain("Next: Nikhil decides.");
  });

  it("says a complete review with changes is not approval to sign", () => {
    const html = renderToStaticMarkup(<StageLine progress={{
      ...BASE, stage: "COMPLETE", outcome: "SIGN_WITH_CHANGES", to_decide: 0, decided: 11,
      next: { who: "owner", name: "Saba" } }} />);
    expect(html).toContain("Review complete: Sign after our changes");
    expect(html).toContain("not approval to sign");
    expect(html).toContain("Next: Saba acts on it.");
  });

  it("asks the owner to send an unsent review", () => {
    const html = renderToStaticMarkup(<StageLine progress={{
      ...BASE, stage: "NOT_SENT", assignee: null, next: { who: "owner", name: "Saba" } }} />);
    expect(html).toContain("Not yet sent for review");
    expect(html).toContain("Next: Saba sends it to a reviewer.");
  });

  it("lists what was decided in words, never Acceptable", () => {
    const html = renderToStaticMarkup(<DecidedRow progress={{ ...BASE, decided_by_type: {
      ACCEPT_DEVIATION: 3, REQUIRE_COMPANY_STANDARD: 1, NOT_APPLICABLE_TO_CONTRACT: 1 } }} />);
    expect(html).toContain("Accepted as an exception");
    expect(html).toContain("Change requested — our wording to send");
    expect(html).toContain("Not applicable to this contract");
    expect(html).not.toMatch(/>Acceptable</);
  });

  it("shows nothing when the server could not say", () => {
    expect(renderToStaticMarkup(<StageLine progress={null} />)).toBe("");
  });
});

describe("the document marks follow the decisions (AB-103)", () => {
  it("marks a decided passage decided — not open, not a match — unless another point on it is open", async () => {
    const { clauseStatusByEvidenceId } = await import("@/components/workspace/model");
    const decided = { classification: "DEVIATION", requires_decision: false, status: "RESOLVED",
                      evidence: [{ id: "e1" }] };
    const open = { classification: "DEVIATION", requires_decision: true, status: "DECISION_REQUIRED",
                   evidence: [{ id: "e2" }] };
    const marks = clauseStatusByEvidenceId([decided, open, { ...open, evidence: [{ id: "e1" }] }]);
    expect(clauseStatusByEvidenceId([decided]).get("e1"))
      .toEqual({ covered: true, attention: false, bucket: "decided" });
    expect(marks.get("e2")?.bucket).toBe("review");
    expect(marks.get("e1")).toEqual({ covered: true, attention: true, bucket: "review" });
  });
});

describe("a point awaiting the client is never said to be finished", () => {
  it("says what happens next after a clarification request", async () => {
    const { nextStep } = await import("@/components/workspace/findingLanguage");
    const finding = { requires_decision: true, classification: "DEVIATION" } as never;
    const asking = { current_decision: { decision_type: "REQUEST_CLARIFICATION" } } as never;
    const decided = { current_decision: { decision_type: "ACCEPT_DEVIATION" } } as never;
    expect(nextStep(finding, asking)).toBe("Waiting for the client's answer; then a reviewer decides.");
    expect(nextStep(finding, decided)).toMatch(/No further action is needed/);
  });
});
