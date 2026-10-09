/**
 * The Summary appeared only after a manual refresh (owner, 2026-10-09): an analysis
 * submitted at 11:51:04 left its Review "UPLOADED" until the worker picked it up, the
 * page read it in that instant, saw "not started" and never asked again. A just-queued
 * Review must keep being asked about; a finished or failed one must not.
 */
import { describe, expect, it } from "vitest";

import { pollBudget } from "@/components/workspace/findingsState";

describe("which findings states are asked about again", () => {
  it("keeps asking about a Review that has not started yet — it may have just been queued", () => {
    expect(pollBudget("not-started")).toBeGreaterThanOrEqual(40);       // ≥ 100 s at 2.5 s
  });
  it("keeps asking about an analysis in flight, longer", () => {
    expect(pollBudget("in-flight")).toBeGreaterThan(pollBudget("not-started"));
  });
  it.each(["ready", "failed", "no-review", "error", "loading"] as const)("stops for %s", (kind) => {
    expect(pollBudget(kind)).toBe(0);
  });
});
