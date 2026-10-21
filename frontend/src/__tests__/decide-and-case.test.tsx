/**
 * Step 5 (owner, 2026-10-21): one small "Decide" per open point, the decision in plain
 * words, a recorded decision said as who/when/why — and the finding's case on the card:
 * the contract's words first, what it is read with, the money, the standard's source.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: ["legal.decision"] } }),
}));

import { DecisionControl } from "@/components/workspace/DecisionControl";
import { CaseContext, CaseContract } from "@/components/workspace/FindingsPane";
import type { Evaluation, FindingCase } from "@/lib/types";

const EVALUATION = {
  id: "ev-1", finding_id: "f-1", scope_key: "GENERAL", classification: "DEVIATION",
  evidence_refs: [], requires_decision: true, current_decision: null,
} as unknown as Evaluation;

describe("Decide (owner, 2026-10-21)", () => {
  it("shows one Decide button and no open form until it is pressed", () => {
    const html = renderToStaticMarkup(
      <DecisionControl evaluation={EVALUATION} onRecorded={() => {}} />);
    expect(html).toContain(">Decide</button>");
    expect(html).not.toContain("ws-decision__form");
    expect(html).not.toMatch(/ACCEPT_DEVIATION|REQUIRE_COMPANY_STANDARD/);
  });

  it("says a recorded acceptance as an exception a named person allowed, never Acceptable", () => {
    const decided = { ...EVALUATION, current_decision: {
      id: "d", evaluation_id: "ev-1", finding_id: "f-1", decision_type: "ACCEPT_DEVIATION",
      justification: "small deal", decided_by: "u-1", decided_by_name: "Legal Lead",
      version_number: 1, is_current: true, created_at: "2026-10-21T10:00:00Z" },
    } as unknown as Evaluation;
    const html = renderToStaticMarkup(
      <DecisionControl evaluation={decided} onRecorded={() => {}} />);
    expect(html).toContain("<strong>Accepted as an exception</strong> — Legal Lead, 21 Oct 2026");
    expect(html).toContain("“small deal”");
    expect(html).toContain(">Change the decision</button>");
    expect(html).not.toContain("Acceptable");
  });
});

const CASE: FindingCase = {
  contract: { quote: "13.1 Either party may terminate for convenience on 15 days' notice.",
              clause: "13.1", page: 2 },
  standard: { section: "13", topic: "Termination", value: "30 days",
              source: { label: "Constitution §13 — Company Position",
                        quote: "Either party may terminate for convenience with 30 days' written notice." } },
  gap: "15 days in the contract vs our 30 days",
  business: { headline: "The customer can end the contract on 15 days' notice",
              body: "That is the time LeapSwitch has to plan.", money: null },
  related: [{ evidence_id: "e-2", clause: "13.2", page: 2, relation: "early exit and what it costs",
              text: "There is no lock-in and no early termination charges shall apply." }],
  recommendation: "Request revised wording",
};

describe("the finding's case on the card (owner, 2026-10-21)", () => {
  it("leads with the contract's own words, clause and page", () => {
    const html = renderToStaticMarkup(<CaseContract kase={CASE} />);
    expect(html).toContain("The contract says (Clause 13.1 · page 2)");
    expect(html).toContain("15 days&#x27; notice");
  });

  it("quotes nothing for a missing clause — never the standard's words as the contract's", () => {
    expect(renderToStaticMarkup(<CaseContract kase={{ ...CASE, contract: null }} />)).toBe("");
  });

  it("shows what the point is read with, the money, and the standard's source", () => {
    const html = renderToStaticMarkup(<CaseContext kase={CASE} />);
    expect(html).toContain("Read with");
    expect(html).toContain("early exit and what it costs · clause 13.2 · page 2");
    expect(html).toContain("What it means for the business");
    expect(html).toContain("Where our standard comes from");
  });

  it("omits the standard's source for a reader without positions (SEC-07)", () => {
    const { source, value, ...open } = CASE.standard;
    void source; void value;
    const html = renderToStaticMarkup(<CaseContext kase={{ ...CASE, standard: open }} />);
    expect(html).not.toContain("Where our standard comes from");
  });
});
