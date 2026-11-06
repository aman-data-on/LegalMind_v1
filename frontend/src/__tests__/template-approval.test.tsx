/**
 * Template approval (S4): absent for a non-holder, the clause list's order, a reason
 * before a replacement, and the publish gate's refusals in plain words.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const session = { can: (_p: string) => false };
vi.mock("@/lib/session", () => ({ useSession: () => session }));
vi.mock("next/navigation", () => ({ useParams: () => ({ id: "t-1" }) }));

import TemplatesPage from "@/app/templates/page";
import TemplatePage from "@/app/templates/[id]/page";
import { CheckStatus, TemplatesToApprove } from "@/components/templates/TemplateList";
import { ClauseSheet } from "@/components/templates/TemplateClause";
import { navItemsFor } from "@/components/workspace/model";
import * as P from "@/lib/permissions";
import {
  actionProblem, blockers, CHECK_TIMEOUT_MS, DEMO_WORDS, isDemo, changedSincePublished, clauseLine, clauseNumbers, fromEditor, groupClauses, outlineDiff, plainText,
  problemLines, listOrder, problemWords, runs, statusWords, stopCount, structureChanges, toEditor, within,
  type OutlineLine, type TemplateCheck, type TemplateClause, type TemplateSummary,
} from "@/lib/templates";

const clause = (key: string, over: Partial<TemplateClause> = {}): TemplateClause => ({
  clause_key: key, version: 1, title: key, body: [{ kind: "p", text: `${key} text` }], status: "DRAFT",
  variables: [], label: "Reference text — not approved by Legal", flags: [], approval: null, ...over,
});
const summary = (over: Partial<TemplateSummary> = {}): TemplateSummary => ({
  id: "t-1", template_key: "NDA.LEAPSWITCH", version: 1, status: "DRAFT", doc_type: "NDA", brand: "LEAPSWITCH",
  title: "NON-DISCLOSURE AGREEMENT", label: "Reference text — not approved by Legal",
  clauses_approved: 0, clauses_total: 3, progress: "0 of 3 clauses approved", published_at: null, ...over,
});
const check: TemplateCheck = {
  publishable: false,
  problems: ["PREFLIGHT UNDEFINED_TERM: “Partner” is used in quotes and never defined"],
  standards: [
    { code: "VENUE", description: "Disputes are heard at Pune.", classification: "DEVIATION", clause_keys: ["C"],
      topic: "Governing Law & Dispute Resolution" },
    { code: "KYC", description: "KYC records are kept.", classification: "UNABLE_TO_EVALUATE", clause_keys: ["E"] },
    { code: "MUTUAL", description: "Obligations are mutual.", classification: "DEVIATION", clause_keys: ["A", "B", "C", "D"] },
    { code: "LATE", description: "Late payments accrue interest.", classification: "MISSING", clause_keys: [] },
  ],
};

describe("absent, not disabled, for a reader without legal.approve_customization", () => {
  it("has no nav item, no home section, and both pages read as an unknown address", () => {
    session.can = () => false;
    expect(navItemsFor(session.can).map((i) => i.label)).not.toContain("Templates");
    expect(renderToStaticMarkup(<TemplatesToApprove />)).toBe("");
    for (const page of [<TemplatesPage key="l" />, <TemplatePage key="d" />]) {
      const html = renderToStaticMarkup(page);
      expect(html).toContain("Page not found");
      expect(html).not.toMatch(/Templates|Approve|Publish|Reference text/);
    }
  });

  it("is present for a holder", () => {
    session.can = (p) => p === P.LEGAL_APPROVE_CUSTOMIZATION;
    expect(navItemsFor(session.can).map((i) => i.label)).toContain("Templates");
    expect(renderToStaticMarkup(<TemplatesPage />)).toMatch(/<h1[^>]*>Templates<\/h1>/);
  });
});

describe("the clause list", () => {
  const clauses = [clause("A"), clause("B", { flags: ["has a blank to fill — Check this clause"] }),
                   clause("C"), clause("D", { status: "APPROVED", approval: {
                     decision: "APPROVE", approved_by: "u", approved_by_name: "Priya Shah",
                     approved_at: "2026-11-03T10:00:00Z", reason: "" } }), clause("E")];

  it("groups what differs first, then what could not be checked, the import's notes, what is left, what is approved — a standard read across the whole template pins none", () => {
    const groups = groupClauses(clauses, check);
    expect(groups.map((g) => [g.title, g.clauses.map((c) => c.clause_key)])).toEqual([
      ["Differs from our standard", ["C"]], ["Couldn\u2019t be checked, read it yourself", ["E"]],
      ["Check this clause", ["B"]], ["Nothing to fix", ["A"]], ["Approved", ["D"]]]);
    expect(groups.every((g) => g.id === "approved" || g.why)).toBe(true);
    expect(listOrder(groups).map((c) => c.clause_key)).toEqual(["C", "E", "B", "A", "D"]);
  });

  it("says on line 2 why, in a few words, or who approved it", () => {
    expect(clauseLine(clauses[2]!, check)).toBe("Differs: Governing law & dispute resolution");
    expect(clauseLine(clauses[4]!, check)).toBe("Couldn\u2019t be checked: KYC records are kept.");
    expect(clauseLine({ ...clauses[2]!, status: "APPROVED" }, check)).toBe("Approved, still differs: Governing law & dispute resolution");
    expect(clauseLine(clauses[1]!, check)).toBe("Check this clause: Has a blank to fill");
    expect(clauseLine(clauses[0]!, check)).toBe("Not approved yet");
    expect(clauseLine(clauses[3]!, check)).toBe("Approved by Priya Shah, 3 Nov 2026");
  });

  it("sets a fill-in field as a named chip and ends the sheet on the reference label until approved", () => {
    expect(runs("between {party_two_name} and us")).toEqual(
      [{ text: "between " }, { field: "party_two_name" }, { text: " and us" }]);
    const html = renderToStaticMarkup(<ClauseSheet clause={clause("A", { body: [{ kind: "p", text: "Signed by {party_two_name}." }] })}
                                                   number="1" numbers={new Map()} label="x" />);
    expect(html).toContain('<span class="tpl-field">Party two name</span>');
    expect(html).toContain("Reference text — not approved by Legal");
    const done = renderToStaticMarkup(<ClauseSheet clause={clauses[3]!} number="4" numbers={new Map()} label="x" />);
    expect(done).toContain("Approved by Priya Shah, 3 Nov 2026");
    expect(done).not.toContain("not approved by Legal");
  });
});

describe("recording a clause", () => {
  it("a replacement or a no-position needs a reason; a replacement needs wording", () => {
    expect(actionProblem("replace", "Our words.", " ")).toMatch(/Give a reason/);
    expect(actionProblem("no-position", "", "")).toMatch(/Give a reason/);
    expect(actionProblem("replace", "  ", "because")).toMatch(/wording/);
    expect(actionProblem("replace", "Our words.", "Lawyer's wording")).toBeNull();
  });
});

describe("the clause's words", () => {
  it("numbers keyed sub-clauses for a cross-reference, and keeps a defined term in the editor's text", () => {
    const c = clause("A", { body: [{ kind: "sub", text: "x", body: [{ kind: "sub", key: "A_2_1", text: "y" }] }] });
    expect(clauseNumbers([clause("Z"), c]).get("A_2_1")).toBe("2.1.1");
    expect(plainText([{ kind: "definition", term: "Services", text: "means the services." }]))
      .toBe("\u201cServices\u201d means the services.");
  });
});

describe("publishing", () => {
  const clauses = [clause("A", { title: "Exclusions" }), clause("C", { title: "Governing law" })];

  it("lists a refusal's problems in plain words, each linked to its clause where it has one", () => {
    expect(problemWords("CLAUSE_NOT_APPROVED: A@1 is DRAFT", clauses, check))
      .toEqual({ text: "Exclusions: not approved yet", clauseKey: "A" });
    expect(problemWords("NOT_MATCH: VENUE is DEVIATION", clauses, check))
      .toEqual({ text: "Differs from our standard: Disputes are heard at Pune.", clauseKey: "C" });
    expect(problemWords("NOT_MATCH: MUTUAL is DEVIATION", clauses, check).clauseKey).toBeUndefined();
    expect(problemLines(["MODEL: A@2: uses the term \u201cX\u201d, which is never defined; C@2: uses \u201cY\u201d"], clauses, check))
      .toEqual([{ text: "Exclusions: uses the term \u201cX\u201d, which is never defined", clauseKey: "A" },
                { text: "Governing law: uses \u201cY\u201d", clauseKey: "C" }]);
    expect(problemWords("PREFLIGHT UNDEFINED_TERM: “Partner” is used in quotes and never defined", clauses, check))
      .toEqual({ text: "“Partner” is used in quotes and never defined" });
    const uses = [clause("DEF", { body: [{ kind: "p", text: "A \u201cPartner\u201d is one of us." }] })];
    expect(problemWords("PREFLIGHT UNDEFINED_TERM: “Partner” is used in quotes and never defined", uses, check).clauseKey)
      .toBe("DEF");
  });

  it("names what blocks publishing, and calls a template ready only when the gate can pass", () => {
    // one count everywhere: every standard not met and every file problem, as listed
    expect(stopCount(check)).toBe(5);
    expect(blockers(summary(), check)).toBe("3 clauses to approve. 5 problems stop publishing.");
    // HIGH 4: ONE status word for a draft; what blocks it is the `blockers` sentence
    expect(statusWords(summary(), check)).toBe("Draft");
    const done = summary({ clauses_approved: 3 });
    expect(statusWords(done, check)).toBe("Draft");
    expect(blockers(done, check)).toBe("5 problems stop publishing.");
    expect(statusWords(done, { publishable: true, problems: [], standards: [] })).toBe("Ready to publish");
    expect(statusWords(summary({ status: "PUBLISHED" }), null)).toBe("Published, version 1");
  });
});

describe("replacing with our wording", () => {
  const line = (kind: string, text: string, number: string | null = null, level = 1): OutlineLine => ({ number, level, kind, text });

  it("shows a cross-reference as a clause number in the editor and sends it back as the key", () => {
    const numbers = new Map([["A_2", "4.2"]]);
    const shown = toEditor("See {xref:A_2} and {xref:GONE}.", numbers);
    expect(shown).toBe("See {clause 4.2} and {xref:GONE}.");
    expect(fromEditor(shown, numbers)).toBe("See {xref:A_2} and {xref:GONE}.");
  });

  it("says what the wording would change in the clause's form, and which lines are new or gone", () => {
    const before = [line("sub", "One.", "4.1", 2), line("sub", "Two.", "4.2", 2), line("sub", "Three.", "4.3", 2)];
    const after = [line("p", "One."), line("p", "Two, changed."), line("p", "Three.")];
    expect(structureChanges(before, after)).toEqual(["3 numbered sub-clauses will become plain paragraphs"]);
    expect(structureChanges(before, before)).toEqual([]);
    const diff = outlineDiff(before, after);
    expect([...diff.changed]).toEqual([1]);
    expect(diff.removed).toEqual(["Two."]);
  });

  it("lists the clauses whose version differs from the published template's", () => {
    const cs = [clause("A", { version: 3, published_version: 2 }), clause("B", { version: 2, published_version: 2 }),
                clause("C", { version: 1, published_version: null }), clause("D")];
    expect(changedSincePublished(cs).map((c) => c.clause_key)).toEqual(["A", "C"]);
  });
});

describe("the check always finishes (HIGH 4)", () => {
  it("rejects past its limit, so the screen offers Run again instead of waiting for ever", async () => {
    vi.useFakeTimers();
    const never = new Promise<never>(() => {});
    const raced = within(never, 1000);
    vi.advanceTimersByTime(1001);
    await expect(raced).rejects.toThrow("took too long");
    vi.useRealTimers();
    await expect(within(Promise.resolve(3), 1000)).resolves.toBe(3);
  });
  it("says checking, or failed with try again", () => {
    expect(renderToStaticMarkup(<CheckStatus state="checking" onRetry={() => {}} />)).toContain("Checking against our standards");
    const failed = renderToStaticMarkup(<CheckStatus state="failed" onRetry={() => {}} />);
    expect(failed).toContain("Couldn’t check right now —");
    expect(failed).toContain(">try again</button>");
  });
  it("a playbook read that never answers ends in failed, and the next attempt asks again", async () => {
    const { api } = await import("@/lib/api");
    const { loadPlaybook } = await import("@/components/workspace/OfferPlaybook");
    vi.useFakeTimers();
    const asked = vi.spyOn(api, "templatePlaybook").mockReturnValue(new Promise(() => {}));
    const first = loadPlaybook("template", "t-hang");
    vi.advanceTimersByTime(CHECK_TIMEOUT_MS + 1);
    await expect(first).resolves.toBe("failed");
    vi.useRealTimers();
    asked.mockResolvedValue({ points: [] } as never);
    await expect(loadPlaybook("template", "t-hang")).resolves.toEqual([]);
    expect(asked).toHaveBeenCalledTimes(2);
    asked.mockRestore();
  });
});

describe("a hand-published demo copy", () => {
  it("says it is not approved by Legal instead of its clause count", () => {
    expect(isDemo(summary({ status: "PUBLISHED", label: "DEMO — not approved by Legal" }))).toBe(true);
    expect(isDemo(summary({ status: "PUBLISHED", label: null }))).toBe(false);
    expect(isDemo(summary())).toBe(false);
    expect(DEMO_WORDS).toBe("Demo — not approved by Legal");
  });
});
