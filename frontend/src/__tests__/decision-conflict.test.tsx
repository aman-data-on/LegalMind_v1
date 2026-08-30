/**
 * The 409 conflict surface — Phase 4 hardening of the locked 52.7 posture.
 *
 * `ConflictNotice` is exported from DecisionPanel for exactly this test, the
 * `AnswerView` precedent. The full conflict flow — a real second decision, a
 * real 409, the frozen form, the explicit refresh — is proven end-to-end in
 * e2e/decision.spec.ts against the real backend; this pins the rendered shape.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ConflictNotice } from "@/components/DecisionPanel";

describe("ConflictNotice", () => {
  it("says plainly that nothing was recorded, and why", () => {
    const html = renderToStaticMarkup(
      <ConflictNotice requestId="req-123" refreshing={false} onRefresh={() => {}} />,
    );
    expect(html).toContain("Not recorded");
    expect(html).toContain("already updated by another user");
    expect(html).toContain('role="alert"');
    expect(html).toContain("Reference req-123");
  });

  it("offers an explicit refresh — the user loads the latest state deliberately", () => {
    const html = renderToStaticMarkup(
      <ConflictNotice requestId="req-123" refreshing={false} onRefresh={() => {}} />,
    );
    expect(html).toContain("Refresh to see the latest decision");
  });

  it("the refresh control reports its own busy state", () => {
    const html = renderToStaticMarkup(
      <ConflictNotice requestId="req-123" refreshing onRefresh={() => {}} />,
    );
    expect(html).toContain("Refreshing…");
    expect(html).toContain("disabled");
  });
});
