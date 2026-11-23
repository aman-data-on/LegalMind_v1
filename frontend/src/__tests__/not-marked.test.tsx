/**
 * Batch 8 R2.6 (`AM-461`): the changes the client made with no tracked change and no
 * highlight come first — in the deal brief and on the Changes tab — with a line sales
 * may copy into the reply (Q8: copied, never sent). Static render, house idiom.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: [] }, can: () => true }),
  useSeesLegalPosition: () => true,
  useCanQuietly: () => false,
}));

import { BriefView } from "@/components/workspace/DealBrief";
import { ChangesBanners } from "@/components/workspace/ChangesBanners";
import { rowMeta, type ChangeList, type ClientChange } from "@/lib/changes";
import type { DealBrief } from "@/lib/dealBrief";
import { NOT_MARKED_COPY } from "@/lib/labels";

const ROW = (n: string, title: string) => ({ title, clause: n, quote: `the client's words in ${title}`,
                                             removed: false, row_key: `N|MODIFIED|a${n}|b${n}` });
const brief = (over: Partial<DealBrief["not_marked"]> = {}): DealBrief => ({
  counts: { changes_total: 22, changes_left_legal: 22 } as DealBrief["counts"],
  status: "WITH_LEGAL",
  asks: [ROW("4", "Payment Terms")], asks_more: 0,
  not_marked: { count: 17, total: 22, highlights_read: true, more: 15,
                rows: [ROW("4", "Payment Terms"), ROW("15", "Service Termination")], ...over },
});
const view = (b: DealBrief, expanded = true) => renderToStaticMarkup(
  <BriefView brief={b} contractId="c" expanded={expanded} onToggle={() => {}} onOpen={() => {}} onChanged={() => {}} />);
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

describe("not marked (batch 8 R2)", () => {
  it("is the brief's first block, above what the client asks for", () => {
    const html = view(brief());
    const body = html.slice(html.indexOf("lm-brief__body"));
    expect(body.indexOf("data-testid=\"not-marked\"")).toBeGreaterThan(-1);
    expect(body.indexOf("data-testid=\"not-marked\"")).toBeLessThan(body.indexOf("What the client asks for"));
    expect(text(html)).toContain("17 of 22 changes not marked");
    expect(text(html)).toContain("Clause 4 (Payment Terms)");
    expect(text(html)).toContain("and 15 more");
    expect(text(html)).toContain(NOT_MARKED_COPY.copy);
  });

  it("leads the collapsed brief", () => {
    expect(text(view(brief(), false))).toContain("17 of 22 changes not marked.");
  });

  it("never claims highlights were read on an older file", () => {
    const said = text(view(brief({ highlights_read: false })));
    expect(said).toContain("17 of 22 changes not marked as tracked changes");
    expect(said).toContain("before it could see highlights");
    expect(said).not.toContain("or a highlight");
  });

  it("counts one and many in words, and the reply line names clauses only", () => {
    expect(NOT_MARKED_COPY.title(1, 3)).toBe("1 of 3 changes not marked");
    expect(NOT_MARKED_COPY.title(1, 1)).toBe("1 of 1 change not marked");
    expect(NOT_MARKED_COPY.line(1, ["Clause 4 (Payment Terms)"])).toBe(
      "We compared your file with the version we sent. 1 change is not marked as a tracked change: "
      + "Clause 4 (Payment Terms). Please mark every change, so both sides can see it.");
    expect(NOT_MARKED_COPY.line(2, ["A", "B"])).toContain("2 changes are not marked");
  });

  it("is absent when every change is marked", () => {
    const { not_marked: _gone, ...rest } = brief();
    expect(view(rest)).not.toContain("not-marked");
  });

  const change = (over: Partial<ClientChange>): ClientChange => ({
    row_key: "k", kind: "MODIFIED", moved: false, clause: { number: "11", heading: null }, page: 1,
    before: null, after: null, tracked: false, untracked: true, unmarked: true,
    review: { before: [], after: [] }, review_delta: [], triage: null, route: "holder",
    route_reason: "NO_STANDARD_MEASURES_IT", effect_for_us: "NEGATIVE", answer: null, history: [], ...over,
  } as ClientChange);

  it("tags each row: not marked, highlighted not tracked, only punctuation", () => {
    expect(rowMeta(change({}), false)).toBe("Wording changed, not marked");
    expect(rowMeta(change({ unmarked: false }), false)).toBe("Wording changed, highlighted, not tracked");
    expect(rowMeta(change({ untracked: false, unmarked: false, tracked: true }), false)).toBe("Wording changed");
    expect(rowMeta(change({ punctuation_only: true }), false)).toBe("Wording changed, not marked. Only punctuation changed");
  });

  it("comes first on the Changes tab, every not-marked row a link, formatting aside", () => {
    const list = {
      contract_id: "c", from: { document_version_id: "v1", version_number: 1 },
      to: { document_version_id: "v2", version_number: 2 },
      summary: { total: 3, untracked: 3, unmarked: 1, highlights_read: true },
      changes: [change({ row_key: "a" }), change({ row_key: "b", unmarked: false }),
                change({ row_key: "c", route: "owner", route_reason: "FORMATTING_ONLY", clause: { number: "12", heading: null } })],
      can_answer: true, can_decide: false,
    } as unknown as ChangeList;
    const html = renderToStaticMarkup(<ChangesBanners data={list} />);
    expect(html.indexOf("not-marked")).toBeLessThan(html.indexOf("Compared with version 1"));
    expect(text(html)).toContain("1 of 3 changes not marked");
    expect((html.match(/lm-notmarked__open/g) ?? []).length).toBe(1);
  });
});

describe("not-marked names", () => {
  it("names a clause by its number and heading, else its own first words, never a trailing colon", () => {
    expect(NOT_MARKED_COPY.clause("4", "Payment Terms", "x")).toBe("Clause 4 (Payment Terms)");
    expect(NOT_MARKED_COPY.clause("4", undefined, "First two months in advance.")).toBe("Clause 4 (First two months in advance.)");
    expect(NOT_MARKED_COPY.clause(null, undefined, "Invoicing:")).toBe("Invoicing");
    expect(NOT_MARKED_COPY.clause(null, "Details of Services:", "x")).toBe("Details of Services");
    expect(NOT_MARKED_COPY.clause(null, undefined, "one two three four five six seven")).toBe("one two three four five six…");
  });
});

describe("round 2", () => {
  const row = (over: Partial<ClientChange>): ClientChange => ({
    row_key: Math.random().toString(), kind: "MODIFIED", moved: false, clause: { number: "2", heading: null }, page: 1,
    before: null, after: null, tracked: false, untracked: true, unmarked: true,
    review: { before: [], after: [] }, review_delta: [], triage: null, route: "holder",
    route_reason: "MEASURED_BY_A_STANDARD", effect_for_us: "NEGATIVE", answer: null, history: [], ...over,
  } as ClientChange);
  const list = (changes: ClientChange[]) => ({
    contract_id: "c", from: { document_version_id: "v1", version_number: 1 },
    to: { document_version_id: "v2", version_number: 2 },
    summary: { total: changes.length, untracked: changes.filter((c) => c.untracked).length, highlights_read: true },
    changes, can_answer: true, can_decide: false,
  } as unknown as ChangeList);

  it("leaves a typography-only change out of the not-marked list", () => {
    const html = renderToStaticMarkup(<ChangesBanners data={list([row({ typography_only: true })])} />);
    expect(html).not.toContain("not-marked");
  });

  it("says once that every untracked change was highlighted", () => {
    const said = text(renderToStaticMarkup(<ChangesBanners data={list([row({ unmarked: false }), row({ untracked: false, unmarked: false, tracked: true })])} />));
    expect(said).toContain("1 of 2 changes was made without a tracked change. The client highlighted it");
    expect(said).not.toContain("not marked");
  });
});
