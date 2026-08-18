/**
 * Queued analysis in the UI — locked 55.1, 52.7, Step 30.
 *
 * Locked 55.1 makes analysis a worker job, so the screen has to cope with a Review
 * that has been submitted and has no Findings yet. Locked 52.7 constrains how:
 * "the Review lifecycle state (Step 30) is the single source of progress."
 *
 * These defend the two ways that could go wrong — inventing a client-side progress
 * state, and waiting for ever on a worker that is not running.
 */

import { describe, expect, it } from "vitest";

import {
  PRE_ANALYSIS_STATUSES,
  QUEUE_POLL_ATTEMPTS,
  isAnalysable,
  isPreAnalysis,
  shouldPollForAnalysis,
} from "@/lib/analysis";

describe("52.7 — progress comes from the lifecycle, not from the client", () => {
  it("only recognises Step 30's own pre-analysis states", () => {
    // Locked Step 30's states, and no invented one. A `QUEUED` here would be exactly
    // the second source of progress 52.7 forbids.
    expect([...PRE_ANALYSIS_STATUSES]).toEqual(["DRAFT", "UPLOADED", "PROCESSING"]);
    expect(PRE_ANALYSIS_STATUSES).not.toContain("QUEUED");
  });

  it("treats an unknown status as pre-analysis so the control stays available", () => {
    // The Review may not have loaded yet. Offering the control and letting the server
    // refuse is safer than hiding it and stranding the user (52.3: gating is
    // presentation only).
    expect(isPreAnalysis(null)).toBe(true);
  });

  it("stops offering analysis once the Review has moved on", () => {
    for (const status of ["ANALYSIS_COMPLETE", "LEGAL_REVIEW", "RESOLVED", "CLOSED",
                          "ANALYSIS_FAILED", "CANCELLED"]) {
      expect(isAnalysable(status)).toBe(false);
    }
    for (const status of PRE_ANALYSIS_STATUSES) {
      expect(isAnalysable(status)).toBe(true);
    }
  });
});

describe("55.1 — watching a queued job", () => {
  const base = { mode: "queued", reviewStatus: "DRAFT", attempts: 0 };

  it("looks again while the job is queued and the lifecycle has not moved", () => {
    expect(shouldPollForAnalysis(base)).toBe(true);
  });

  it("stops as soon as the lifecycle moves", () => {
    // The lifecycle moving IS the completion signal — there is nothing else to check,
    // and checking a job-state resource instead would be a second answer (52.7).
    expect(shouldPollForAnalysis({ ...base, reviewStatus: "LEGAL_REVIEW" })).toBe(false);
    expect(shouldPollForAnalysis({ ...base, reviewStatus: "ANALYSIS_FAILED" })).toBe(false);
  });

  it("does not poll after an inline run, which has already finished", () => {
    expect(shouldPollForAnalysis({ ...base, mode: "inline" })).toBe(false);
    expect(shouldPollForAnalysis({ ...base, mode: undefined })).toBe(false);
  });

  it("gives up after a bounded number of looks", () => {
    // A stopped worker must be reported, not animated. An indefinite spinner would
    // imply progress the system cannot observe.
    expect(shouldPollForAnalysis({ ...base, attempts: QUEUE_POLL_ATTEMPTS })).toBe(false);
    expect(shouldPollForAnalysis({ ...base, attempts: QUEUE_POLL_ATTEMPTS - 1 })).toBe(true);
  });
});
