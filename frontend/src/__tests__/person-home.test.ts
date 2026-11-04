/**
 * S1 (CLM plan, owner-approved 2026-11-03): each person's home and words are derived from
 * the PERMISSIONS they hold — never a role name (RBAC_MODEL) — and stay presentation only.
 */
import { describe, expect, it } from "vitest";

import {
  contractFacts,
  oneTaskPerContract,
  homeTitle,
  personaFor,
  showsLegalDetails,
  stageViewer,
} from "@/components/workspace/model";
import type { Contract } from "@/lib/types";

const holding = (...perms: string[]) => (p: string) => perms.includes(p);
const USER = ["contract.view", "contract.create", "document.upload", "legal_position.view"];

describe("whose home it is", () => {
  it("opens a contract owner on My contracts", () => {
    expect(personaFor(holding(...USER))).toBe("owner");
    expect(homeTitle("owner")).toBe("My contracts");
  });

  it("opens a Lead on the team's contracts, and on theirs when they switch scope", () => {
    const lead = holding(...USER, "department.view", "contract.transfer");
    expect(personaFor(lead)).toBe("lead");
    expect(homeTitle("lead", "department")).toBe("Team contracts");
    expect(homeTitle("lead", "own")).toBe("My contracts");
  });

  it("opens a legal.decision holder on For my review — whatever else they hold", () => {
    expect(personaFor(holding("contract.view", "legal.review", "legal.decision"))).toBe("legal");
    expect(personaFor(holding(...USER, "department.view", "legal.decision"))).toBe("legal");
    expect(homeTitle("legal")).toBe("For my review");
  });

  it("does not read a Legal Reviewer without the decision right as the lawyer", () => {
    expect(personaFor(holding("contract.view", "legal.review", "legal_position.view"))).toBe("owner");
  });
});

describe("the home queue and the To-do: one task per contract", () => {
  const at = (h: number) => `2026-11-03T${String(h).padStart(2, "0")}:00:00Z`;
  const items = [
    { kind: "changes_to_answer", contract_id: "A", since: at(9) },
    { kind: "client_returned", contract_id: "A", since: at(8) },
    { kind: "second_approval", contract_id: "B", since: at(7) },
    { kind: "decide", contract_id: "B", since: at(10) },
    { kind: "answered", contract_id: "C", since: at(6) },
  ];

  it("keeps the most pressing task of each contract, oldest first", () => {
    expect(oneTaskPerContract(items).map((i) => `${i.contract_id}:${i.kind}`))
      .toEqual(["C:answered", "A:changes_to_answer", "B:decide"]);
  });
});

describe("who sees what", () => {
  it("gives Legal details only to a holder of the position AND Legal's review", () => {
    expect(showsLegalDetails(holding("legal_position.view", "legal.review"))).toBe(true);
    expect(showsLegalDetails(holding("legal_position.view"))).toBe(false);   // the deal owner
    expect(showsLegalDetails(holding("legal.review"))).toBe(false);
  });

  it("words a stage for the lawyer only on a contract they do not own", () => {
    const lawyer = holding("legal.decision");
    expect(stageViewer(lawyer, false)).toBe("legal");
    expect(stageViewer(lawyer, true)).toBe("owner");
    expect(stageViewer(holding(...USER), false)).toBe("owner");
  });
});

describe("the contracts home rows (critic round)", () => {
  const row = (over: Partial<Contract>) => ({
    id: "c", owner_id: "u", name: "MSA", contract_type: "MSA", status: "ACTIVE",
    archived_at: null, created_at: null, updated_at: null, ...over,
  }) as Contract;
  const analysed = {
    latest_version: { id: "v", version_number: 2, processing_status: "COMPLETED", created_at: "2026-11-02T10:00:00Z" },
    latest_analysis: { review_id: "r", review_status: "ANALYSIS_COMPLETE", created_at: null, completed_at: null,
      user_status_counts: { ACCEPTABLE: 8, REQUIRES_MODIFICATION: 4, MISSING: 2, NEEDS_DECISION: 11 } },
  } as Partial<Contract>;

  it("tells two contracts apart by client, type, version and upload date", () => {
    const facts = contractFacts(row(analysed), "Acme");
    expect(facts.slice(0, 2)).toEqual(["Acme", "MSA"]);
    expect(facts[2]).toMatch(/^Version 2, uploaded 2 Nov 2026, \d\d:\d\d$/);
    expect(facts[3]).toBe("Ref C");
    expect(facts.join(" ")).not.toContain("·");            // parts, never a middot string
    expect(contractFacts(row({ contract_type: null }))).toEqual(["Ref C"]);
  });
});
