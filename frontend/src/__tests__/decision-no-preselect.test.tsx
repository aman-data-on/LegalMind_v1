/**
 * LA-1 (owner, 2026-11-09): the decision form opens with NO decision type chosen, and
 * "Record decision" stays disabled until the decider picks one. Static markup cannot
 * press "Decide", so every `useState(false)` starts `true` here — the form renders open.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("react", async (importOriginal) => {
  const react = await importOriginal<typeof import("react")>();
  return { ...react, useState: (init: unknown) => react.useState(init === false ? true : init) };
});
vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: ["legal.decision"] } }),
}));

import { DecisionControl } from "@/components/workspace/DecisionControl";
import type { Evaluation } from "@/lib/types";

const EVALUATION = {
  id: "ev-1", finding_id: "f-1", scope_key: "GENERAL", classification: "DEVIATION",
  evidence_refs: [], requires_decision: true, current_decision: null,
} as unknown as Evaluation;

describe("LA-1 — no decision is preselected", () => {
  const html = renderToStaticMarkup(
    <DecisionControl evaluation={EVALUATION} onRecorded={() => {}} />);

  it("opens on the empty choice, never on Accept as an exception", () => {
    expect(html).toContain("ws-decision__form");
    expect(html).toMatch(/<option value="" disabled="" selected="">Choose a decision<\/option>/);
    expect(html.match(/selected=""/g)).toHaveLength(1);
  });

  it("keeps Record disabled until a type is chosen", () => {
    expect(html).toMatch(/<button type="submit"[^>]*disabled=""[^>]*>Record decision<\/button>/);
  });
});
