/**
 * The final contract (`AM-307`, design 11 §8 U3–U5) — static render, house idiom. The
 * server decides everything; these pin the words, that a blocker links to its change,
 * that the step picks "Prepare final contract" / "Send for signature", and that an
 * internal note shows only when the server sent it (absent otherwise).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: [] }, can: () => true }),
  useSeesLegalPosition: () => true,
}));
vi.mock("@/components/Dialog", () => ({ Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

import { PackageBar, PackageCard, TraceList } from "@/components/workspace/Package";
import { nextStep } from "@/lib/nextStep";
import { blockerText, clauseName, entryAction, packageApplies, packageLine, type PackagePlan, type SpecialConditions } from "@/lib/package";
import type { DocumentVersion } from "@/lib/types";

const entry = { n: 1, op: "replace" as const, text: "The cap is twelve months.", answer: "accept_theirs" as const,
  effect: "NEGATIVE" as const, row_key: "r1",
  target: { key: "K.CAP", number: "17.2", heading: "Monetary Cap on Liability" } };
const plan = (over: Partial<PackagePlan> = {}): PackagePlan => ({
  available: true, blockers: [], entries: [entry],
  precedence: { clause_key: "K.PREC", number: "22", approved: true }, entries_sha256: "abc", ...over });
const bar = (p: PackagePlan, canPrepare = true) => renderToStaticMarkup(
  <PackageBar contractId="c" plan={p} canPrepare={canPrepare} nextVersion={3} onReload={() => {}} onPrepared={() => {}} onPick={() => {}} />);

describe("the dry run (PackageBar)", () => {
  it("lists Annexure A's entries in plain words and names the precedence clause", () => {
    const html = bar(plan());
    expect(html).toContain("Final contract");
    expect(html).toContain("the 1 agreed change");
    expect(html).toContain("Special Conditions (Annexure A)");
    expect(html).toContain("Clause 22 says Annexure A wins");
    expect(html).toContain("Clause 17.2, Monetary Cap on Liability");
    expect(html).toContain("Replaced with the client’s wording");
    expect(html).toContain("Worse for us");
    expect(html.replace(/<[^>]+>/g, " ")).not.toMatch(/accept_theirs|NEGATIVE|K\.CAP/);
  });
  it("names the precedence clause from the server, never a fixed number", () => {
    expect(bar(plan({ precedence: { clause_key: "K", number: "21.3", approved: true } }))).toContain("Clause 21.3 says Annexure A wins");
    expect(bar(plan({ precedence: null }))).toContain("The order-of-precedence clause says Annexure A wins");
  });
  it("offers the tracked-changes reply only to someone who may prepare", () => {
    expect(bar(plan())).toContain("Prepare a reply with tracked changes instead");
    expect(bar(plan(), false)).not.toContain("tracked changes instead");
  });
  it("blocked: each reason in words, a change's reason a link to it", () => {
    const html = bar(plan({ available: false, entries: [], blockers: [
      { code: "SC_FRAME_NOT_APPROVED", detail: "the Special Conditions wording is not approved by Legal" },
      { code: "CANNOT_EXPRESS", message: "Two answers vary clause 8.5 — answer it once.", row_key: "r9" },
    ] }));
    expect(html).toContain("can be prepared once these are sorted");
    expect(html).toContain("The Special Conditions (Annexure A) wording is not approved yet.");
    expect(html).toContain("Two answers vary clause 8.5");
    expect(html.match(/Open the change/g)).toHaveLength(1);
    expect(html).not.toContain("SC_FRAME");
  });
  it("is absent when the deal goes out another way", () => {
    expect(packageApplies(plan({ available: false, blockers: [{ code: "NOT_OUR_TEMPLATE", message: "x" }] }))).toBe(false);
    // AM-316 r7: a template kept without Annexure A — the reply goes back as tracked changes
    expect(packageApplies(plan({ available: false, blockers: [{ code: "NO_ANNEXURE", message: "x" }] }))).toBe(false);
    expect(packageApplies(plan({ available: false, blockers: [{ code: "SC_NOT_CONFIGURED", detail: "x" }] }))).toBe(true);
    expect(packageApplies(null)).toBe(false);
  });
});

describe("words", () => {
  it("names a clause and what happens to it", () => {
    expect(clauseName({ key: "k", number: "8.5", heading: "PAYMENT AND INVOICING" })).toBe("Clause 8.5, Payment and invoicing");
    expect(clauseName({ key: "k", number: null, heading: null }, "17.2A")).toBe("Clause 17.2A");
    expect(entryAction({ op: "delete" })).toBe("Removed");
    expect(entryAction({ op: "insert", answer: "write_wording" })).toBe("Added, with our new wording");
    expect(blockerText({ code: "UNKNOWN", message: "Said by the server." })).toBe("Said by the server.");
  });
});

describe("the step (nextStep)", () => {
  const counts = { changes_total: 3, changes_left: 0, changes_left_for_me: 0 };
  const base = { viewer: "owner" as const, canAnswer: true, counts };
  it("prepares the final contract when its dry run is clear, our reply otherwise", () => {
    expect(nextStep({ ...base, stage: "CLIENT_RETURNED", packageReady: true })?.label).toBe("Prepare final contract");
    expect(nextStep({ ...base, stage: "CLIENT_RETURNED" })?.label).toBe("Prepare our reply");
  });
  it("sends the final contract for signature before it is marked signed", () => {
    expect(nextStep({ ...base, stage: "READY_TO_SIGN", packageUnsent: true })?.label).toBe("Send for signature");
    expect(nextStep({ ...base, stage: "READY_TO_SEND", packageUnsent: true })?.kind).toBe("sendForSignature");
    expect(nextStep({ ...base, stage: "READY_TO_SIGN" })?.kind).toBe("recordSigning");
  });
});

const version = (over: Partial<DocumentVersion> = {}) => ({
  id: "v3", version_number: 3, package: { of_version_id: "v2", special_conditions: 3 }, ...over,
}) as DocumentVersion;

describe("the final contract (PackageCard)", () => {
  const versions = [version(), { id: "v2", version_number: 2 } as DocumentVersion];
  it("says what it is and holds the files while a point is open", () => {
    const held = renderToStaticMarkup(<PackageCard version={version()} versions={versions} filesOpen={false} />);
    expect(held).toContain("Version 3 is the final contract");
    expect(held).toContain("3 Special Conditions (Annexure A), answering the client’s version 2");
    expect(held).toContain("the files are held");
    expect(held).not.toContain("Download");
    const open = renderToStaticMarkup(<PackageCard version={version()} versions={versions} filesOpen />);
    expect(open).toContain("Not sent yet.");
    expect(open).toContain("PDF");
    expect(open).toContain("What is in Annexure A (3)");
  });
  it("says when it went out", () => {
    const sent = renderToStaticMarkup(<PackageCard version={version({ sent_at: "2026-11-04T10:00:00Z" })}
                                                   versions={versions} filesOpen={false} />);
    expect(sent).toContain("Sent for signature on 4 Nov 2026");
    expect(sent).toContain("PDF");
  });
});

describe("Annexure A's record (SpecialConditionsTrace)", () => {
  const sc = (note?: Record<string, string | null>): SpecialConditions => ({
    document_version_id: "v3", package_of: "v2", entries: [entry],
    trace: [{ n: 1, op: "replace", effect: "NEGATIVE", row_key: "r1", decision_ids: ["d1"], answer: "accept_theirs",
      decided_by: "Counsel", decided_at: "2026-11-04T10:00:00Z", reason: "agreed on the call", client_note: null, ...note }],
  });
  it("says who agreed each entry, when and why", () => {
    const html = renderToStaticMarkup(<TraceList sc={sc()} />);
    expect(html).toContain("Replaced with the client’s wording, answered by Counsel on 4 Nov 2026.");
    expect(html).toContain("Agreed by a Legal Decision.");
    expect(html).toContain("agreed on the call");
    expect(html).not.toContain("Sent to the client");
  });
  it("shows the internal note only when the server sent one", () => {
    expect(renderToStaticMarkup(<TraceList sc={sc()} />)).not.toContain("Internal note");
    expect(renderToStaticMarkup(<TraceList sc={sc({ internal_note: null })} />)).not.toContain("Internal note");
    expect(renderToStaticMarkup(<TraceList sc={sc({ internal_note: "keep this in" })} />)).toContain("keep this in");
  });
});

describe("In the final contract (U2, by row_key)", () => {
  it("names the entry, the reason it can't be written, or that our wording stays", () => {
    const answered = (row_key: string, answer: "keep_ours" | "accept_theirs") => ({ row_key, answer: { answer } });
    expect(packageLine(answered("r1", "accept_theirs"), [entry])).toBe("Entry 1 of Annexure A. Replaced with the client’s wording.");
    expect(packageLine(answered("r9", "accept_theirs"), [entry],
      [{ code: "CANNOT_EXPRESS", message: "A clause with sub-clauses cannot be replaced.", row_key: "r9" }]))
      .toBe("Can’t be written into Annexure A. A clause with sub-clauses cannot be replaced.");
    expect(packageLine(answered("r2", "keep_ours"), [entry])).toBe("No entry. Our wording stays.");
    expect(packageLine({ row_key: "r3", answer: null }, [entry])).toBeNull();
  });
});

describe("blocker words", () => {
  it("drops the bar's own lead from the server's reason", () => {
    expect(blockerText({ code: "PACKAGE_NOT_READY", message: "The final contract cannot be prepared yet: 3 changes not answered yet (clause 8.5)." }))
      .toBe("3 changes not answered yet (clause 8.5).");
  });
});

import { SpecialConditionsSetup } from "@/components/templates/TemplateApproval";

describe("Special Conditions set-up on the template (U1)", () => {
  it("says it is set up, or what is missing in words — and that publishing is not stopped", () => {
    expect(renderToStaticMarkup(<SpecialConditionsSetup readiness={{ ready: true, missing: [] }} />)).toContain("Set up.</strong>");
    const only = renderToStaticMarkup(<SpecialConditionsSetup readiness={{ ready: false, missing: [{ code: "NOT_CONFIGURED", detail: "x" }] }} />);
    expect(only).toContain("cannot be set up from this page yet");
    expect(only).not.toContain("<ul>");
    const html = renderToStaticMarkup(<SpecialConditionsSetup readiness={{ ready: false, missing: [
      { code: "PRECEDENCE_NOT_APPROVED", detail: "the order-of-precedence clause is not approved by Legal" }] }} />);
    expect(html).toContain("It does not stop publishing.");
    expect(html).toContain("The clause saying Annexure A wins over the body is not approved yet.");
    expect(html).not.toContain("PRECEDENCE_NOT_APPROVED");
    expect(renderToStaticMarkup(<SpecialConditionsSetup />)).toBe("");
  });
});

import { ChangesPane } from "@/components/workspace/ChangesPane";

describe("Annexure A not applied (U6 banner)", () => {
  it("says the copy is compared as written and every change goes to Legal, with the server's reason", () => {
    const list = { contract_id: "c", from: { document_version_id: "v1", version_number: 1 },
      to: { document_version_id: "v2", version_number: 2 }, summary: { total: 0, untracked: 0 }, changes: [],
      can_answer: true, can_decide: false, special_conditions_not_applied: ["special Conditions not found in this copy"] };
    const html = renderToStaticMarkup(<ChangesPane contractId="c" versions={[]} onVersionCreated={() => {}}
      changes={{ state: { kind: "ready", list }, setState: () => {}, reload: () => {}, enabled: true }} />);
    expect(html).toContain("Annexure A could not be read on this copy");
    expect(html).toContain("every change goes to Legal");
    expect(html).toContain("Special Conditions not found in this copy.");
  });
});

import { CopySection } from "@/components/workspace/SigningSheet";

describe("signing a final contract (U6 note)", () => {
  const state = { execution: null, agreed: { document_version_id: "v3", version_number: 3 }, comparison: null,
    blockers: [], signed: false };
  it("names the agreed final contract and its Annexure A only when it is one", () => {
    const copy = (annexure?: number) => renderToStaticMarkup(<CopySection state={state} busy={null} onUpload={() => {}}
      onRefresh={() => {}} onAccept={() => {}} annexure={annexure} />);
    expect(copy(3)).toContain("including Annexure A with its 3 Special Conditions");
    expect(copy()).not.toContain("Annexure A");
  });
});
