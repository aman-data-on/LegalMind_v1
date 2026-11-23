/**
 * Batch 8 sub-batch B: "already agreed before" (R1, `AM-464`/`AM-465`) and which of our
 * standard sets measured the paper (R5, `AM-467`). Every word is the server's field put
 * in labels.ts words; nothing renders without it. Static render, house idiom.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: [] }, can: () => true }),
  useSeesLegalPosition: () => true,
  useCanQuietly: () => false,
}));
vi.mock("next/link", () => ({
  default: ({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) =>
    <a href={href} className={className}>{children}</a>,
}));

import { BriefView } from "@/components/workspace/DealBrief";
import { CheckedAgainst } from "@/components/workspace/PriorAndStandards";
import { UploadToClient } from "@/components/clients/UploadToClient";
import { rowMeta, type ClientChange } from "@/lib/changes";
import type { DealBrief } from "@/lib/dealBrief";
import { MEASURED_COPY, PRIOR_COPY } from "@/lib/labels";
import type { Counterparty, Prior } from "@/lib/types";

const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");
const PAPER = { contract_id: "x1", name: "MoU 2 nodes", agreed_on: "2026-10-23", kind: "SIGNED" as const };
const prior = (state: Prior["state"], kind: "SIGNED" | "FINAL" = "SIGNED"): Prior => ({ ...PAPER, kind, state });
const change = (over: Partial<ClientChange>): ClientChange => ({
  row_key: "k", kind: "MODIFIED", moved: false, clause: { number: "11", heading: null }, page: 1,
  before: null, after: null, tracked: true, untracked: false, unmarked: false,
  review: { before: [], after: [] }, review_delta: [], triage: null, route: "holder",
  route_reason: "NO_STANDARD_MEASURES_IT", effect_for_us: "NEGATIVE", answer: null, history: [], ...over,
} as ClientChange);
const base: DealBrief = { counts: { changes_total: 3, changes_left_legal: 3 } as DealBrief["counts"],
                          status: "WITH_LEGAL" };
const view = (b: DealBrief, legal = false) => renderToStaticMarkup(
  <BriefView brief={legal ? { ...b, legal: { beyond: [], as_told: 0, not_discussed: 0, comments: [],
                                             whole_contract: [], can_record: false } } : b}
             contractId="c" expanded onToggle={() => {}} onOpen={() => {}} onChanged={() => {}} />);

describe("already agreed before (batch 8 R1)", () => {
  it("tags a row with the earlier contract, named by its date", () => {
    expect(rowMeta(change({ prior: prior("SAME") }), false)).toBe("Wording changed. Same as our signed contract (23 Oct 2026)");
    expect(rowMeta(change({ prior: prior("CHANGED", "FINAL") }), false)).toBe(
      "Wording changed. Changed since our final contract (23 Oct 2026)");
    expect(rowMeta(change({ prior: prior("NEW") }), false)).toContain("New since our signed contract");
    expect(rowMeta(change({ kind: "DELETED", prior: prior("IN_SIGNED") }), false)).toContain("Was in our signed contract");
  });

  it("says nothing without an earlier contract", () => {
    expect(rowMeta(change({}), false)).toBe("Wording changed");
    expect(view(base)).not.toContain("already-agreed");
  });

  it("puts the count, the contract and its link in the brief", () => {
    const html = view({ ...base, already_agreed: { count: 5, rows: [], contract: PAPER } });
    expect(text(html)).toContain("5 changes were already in our signed contract “MoU 2 nodes” (23 Oct 2026).");
    expect(text(html)).toContain(PRIOR_COPY.briefHint(5));
    expect(html).toContain("(23\u00a0Oct\u00a02026)");                    // the date never splits
    expect(PRIOR_COPY.briefHint(1)).toBe("The client may say we agreed to this before. Legal still decides it.");
    expect(html).toContain('href="/contracts/x1"');
    expect(PRIOR_COPY.brief(1, "FINAL", "A", "1 Nov 2026")).toBe("1 change was already in our final contract “A” (1\u00a0Nov\u00a02026).");
  });

  it("offers a signed-earlier reference filing on a new document only", () => {
    const client = { id: "cp", name: "Client Co", contracts: [] } as unknown as Counterparty;
    const html = renderToStaticMarkup(<UploadToClient client={client} onDone={() => {}} />);
    expect(text(html)).toContain(PRIOR_COPY.uploadRole);
    expect(text(html)).not.toContain("Mark signed");
    const into = renderToStaticMarkup(<UploadToClient client={{ ...client, contracts: [{ id: "k1", name: "Deal" }] } as unknown as Counterparty}
                                                      onDone={() => {}} initialContractId="k1" />);
    expect(text(into)).not.toContain(PRIOR_COPY.uploadRole);
  });
});

describe("checked against (batch 8 R5)", () => {
  const sets = [{ kind: "OUR_MSA", name: "Leapswitch Master Services Agreement, Version 2 (July 2025)", points: 9 },
                { kind: "CONSTITUTION", name: "Legal Constitution, Lawyer Review Version L1.10", points: 14 }];
  it("names the sets in plain words for sales, never the source documents", () => {
    const said = text(renderToStaticMarkup(<CheckedAgainst brief={{ measured_against: sets,
      measured_against_note: "MSA_TERMS_ON_OTHER_PAPER" }} legal={false} />));
    expect(said).toContain("Checked against our standards as our MSA and our general contract terms state them.");
    expect(MEASURED_COPY.line(["OTHER_DOCUMENT", "CONSTITUTION", "OUR_MSA", "CONSTITUTION"])).toBe(
      "Checked against our standards as our MSA, our general contract terms and our other agreements state them.");
    expect(said).toContain(MEASURED_COPY.otherPaper);
    expect(said).not.toMatch(/Constitution|C-34|§|MSA\.pdf/);
  });

  it("reads the kinds alone, as the server sends them to sales (D5: no names, no counts)", () => {
    const said = text(renderToStaticMarkup(<CheckedAgainst brief={{ measured_against: [{ kind: "CONSTITUTION" }, { kind: "OUR_MSA" }],
      measured_against_note: "MSA_TERMS_ON_OTHER_PAPER" }} legal={false} />));
    expect(said).toContain("Checked against our standards as our MSA and our general contract terms state them.");
    expect(said).toContain("Legal has not yet confirmed which of our standards apply to paper that is not an MSA.");
  });

  it("lists each source with its points for Legal, and the open question", () => {
    const said = text(renderToStaticMarkup(<CheckedAgainst brief={{ measured_against: sets,
      measured_against_note: "MSA_TERMS_ON_OTHER_PAPER" }} legal />));
    expect(said).toContain("Leapswitch Master Services Agreement, Version 2 (July 2025): 9 points");
    expect(said).toContain(MEASURED_COPY.conflict);
  });

  it("says one set alone, no note on an MSA, nothing for an older snapshot", () => {
    expect(MEASURED_COPY.line(["OUR_MSA"])).toBe("Checked against our standards as our MSA states them.");
    const msa = text(renderToStaticMarkup(<CheckedAgainst brief={{ measured_against: [sets[0]!] }} legal={false} />));
    expect(msa).not.toContain(MEASURED_COPY.otherPaper);
    expect(renderToStaticMarkup(<CheckedAgainst brief={{}} legal />)).toBe("");
    expect(view({ ...base, measured_against: sets })).toContain("checked-against");
  });
});
