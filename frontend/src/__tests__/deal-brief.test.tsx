/**
 * Batch 3+4 "deal brief" (AB-218) — static render, house idiom.
 *  - check 8: every change row renders exactly ONE status label and no more than one
 *    primary action, for the deal owner and for Legal, in every state a row can be in;
 *  - check 6: the deal owner's brief says no clause sign, no code and no engine word;
 *  - the label comes only from Legal's own tie, and never reaches the deal owner.
 * The words of "what we told them" here are TEST text, never a position (rule 21).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const reader = vi.hoisted(() => ({ legal: true }));
vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: [] }, can: () => true }),
  useSeesLegalPosition: () => true,
  useCanQuietly: () => reader.legal,
}));
vi.mock("@/components/Dialog", () => ({ Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

import { ChangeIndex } from "@/components/workspace/ChangesPane";
import { AnswerCard } from "@/components/workspace/AnswerCard";
import { BriefView } from "@/components/workspace/DealBrief";
import { rowStatus, type ChangeList, type ClientChange } from "@/lib/changes";
import { statusWords, type DealBrief } from "@/lib/dealBrief";
import { BRIEF_COPY, ROW_STATUS } from "@/lib/labels";
import { WholeContractPlace } from "@/components/workspace/Angles";

const base = (key: string, over: Partial<ClientChange> = {}): ClientChange => ({
  row_key: key, kind: "MODIFIED", moved: false, clause: { number: key.slice(-1), heading: "Fees" }, page: 1,
  before: { evidence_ids: [`a${key}`], text: "Fees are payable within 30 days." },
  after: { evidence_ids: [`b${key}`], text: "Fees are payable within 60 days." },
  tracked: true, untracked: false, review: { before: [], after: [] }, review_delta: [], triage: null,
  route: "holder", route_reason: "NO_STANDARD_MEASURES_IT", effect_for_us: "NEGATIVE", measured: "NOT_MEASURED",
  holder_accepted: false, answer: null, history: [], ...over,
});
const answered = (answer: "keep_ours" | "accept_theirs" | "write_wording") => ({
  round: 2, version_number: 1, answer, reason: null, decided_by: "Counsel", decided_at: "2026-11-19T10:00:00Z" });
const TOLD = { position_key: "p1", text: "Test note: a mutual cap was offered" };
const ROWS: ClientChange[] = [
  base("N|M|1"),                                                             // waiting for Legal
  base("N|M|2", { told: { tie: "AS_TOLD", ...TOLD } }),
  base("N|M|3", { told: { tie: "BEYOND", ...TOLD } }),
  base("N|M|4", { answer: answered("keep_ours") }),
  base("N|M|5", { answer: answered("write_wording"), waiting_for_approval: true }),
  base("N|M|6", { route: "owner", route_reason: "FORMATTING_ONLY", effect_for_us: "NEUTRAL" }),
  base("N|M|7", { holder_accepted: true }),
  base("N|D|8", { kind: "DELETED", after: null, untracked: true }),
  base("N|M|9", { answer: answered("accept_theirs"), route: "favour", effect_for_us: "POSITIVE" }),
];
const list = (over: Partial<ChangeList>): ChangeList => ({
  contract_id: "c", from: { document_version_id: "v1", version_number: 1 },
  to: { document_version_id: "v2", version_number: 2 }, summary: { total: ROWS.length, untracked: 1 },
  changes: ROWS, can_answer: true, can_decide: false, sent_to_legal: true, ...over,
});
const SALES = list({});
const LAWYER = list({ can_decide: true, can_write_wording: true });

const pane = (l: ChangeList) => renderToStaticMarkup(
  <ChangeIndex rows={l.changes} current={null} onPick={() => {}} allUntracked={false} reader={l}
               formatting={[]} onKeepAllFormatting={() => {}} />);

/** Each row button of the index, by its row key. */
function rows(html: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const m of html.matchAll(/<button type="button" id="cx-row-([^"]+)" class="cx-row"[\s\S]*?<\/button>/g)) {
    out.set(m[1]!, m[0]);
  }
  return out;
}

describe("one label and one action per change row (check 8)", () => {
  for (const [who, l] of [["the deal owner", SALES], ["Legal", LAWYER]] as const) {
    it(`gives ${who} exactly one status label on every row, and no primary action`, () => {
      const html = pane({ ...l, changes: ROWS });
      const found = rows(html);
      // the formatting row sits in its own (closed) group; every other row is drawn
      expect(found.size).toBeGreaterThanOrEqual(ROWS.length - 1);
      for (const [key, row] of found) {
        expect(row.match(/data-status=""/g) ?? [], key).toHaveLength(1);
        expect(row.match(/ws-btn--primary/g) ?? [], key).toHaveLength(0);
        // the review's chip and the effect are the card's now, never the row's
        expect(row, key).not.toContain("lm-chip");
        expect(row, key).not.toContain("cx-forus");
      }
    });
  }

  it("says the deal owner's words and Legal's words, from Legal's own tie only", () => {
    const say = (l: ChangeList) => ROWS.map((c) => rowStatus(c, l));
    expect(say(SALES)).toEqual([
      ROW_STATUS.withLegal, ROW_STATUS.withLegal, ROW_STATUS.withLegal, "Answered: Kept ours",
      ROW_STATUS.waiting, ROW_STATUS.yours, ROW_STATUS.yours, ROW_STATUS.withLegal, "Answered: Accepted theirs"]);
    expect(say(LAWYER)).toEqual([
      ROW_STATUS.needsYou, ROW_STATUS.asTold, ROW_STATUS.beyond, "Answered: Kept ours",
      ROW_STATUS.waiting, "Deal owner answers", "Deal owner answers", ROW_STATUS.needsYou, "Answered: Accepted theirs"]);
    // N2: a lawyer who cannot answer the row reads "With Legal", never "Needs your answer"
    expect(rowStatus(ROWS[0]!, { ...LAWYER, can_answer: false })).toBe(ROW_STATUS.withLegal);
    expect(rowStatus(ROWS[2]!, { ...LAWYER, can_answer: false })).toBe(ROW_STATUS.withLegal);
    // never sent to Legal: the deal owner reads who answers it, never "With Legal"
    expect(rowStatus(ROWS[0]!, { ...SALES, sent_to_legal: false })).toBe("Legal answers this");
  });

  it("puts ONE label on the answer card too, with the review's word as a detail", () => {
    const card = (c: ClientChange, l: ChangeList) => renderToStaticMarkup(
      <AnswerCard change={c} list={l} contractId="c" onAnswered={() => {}} onReload={() => {}} />);
    for (const c of ROWS) {
      for (const l of [SALES, LAWYER]) expect(card(c, l).match(/data-status=""/g) ?? []).toHaveLength(1);
    }
  });

  it("prepares the answer from the tie, and the lawyer still submits it", () => {
    const card = (c: ClientChange) => renderToStaticMarkup(
      <AnswerCard change={c} list={LAWYER} contractId="c" onAnswered={() => {}} onReload={() => {}} />);
    const asTold = card(ROWS[1]!);
    expect(asTold).toMatch(/checked="" value="accept"/);           // Accept theirs preselected
    expect(asTold).toContain("Prepared from what we told them");
    expect(asTold).toContain(TOLD.text);
    // N1 (rule 13): the action only — the reason box starts empty, the lawyer's own words
    expect(asTold).not.toContain("As we told the client");
    expect(asTold).not.toMatch(/<input type="text"[^>]*value="[^"]+"/);
    const beyond = card(ROWS[2]!);
    expect(beyond).toMatch(/checked="" value="reject"/);           // Keep ours preselected
    expect(card(ROWS[0]!)).not.toMatch(/checked=""/);               // nothing prepared
    // round 5: a measured row (its answer writes a Legal Decision) — nothing preselected,
    // what we told them still shown
    const measured = card(base("N|M|m", { told: { tie: "AS_TOLD", ...TOLD }, review: { before: [], after: [{
      finding_id: "f", requirement_code: "LIAB-1", classification: "DEVIATION", user_status: "REQUIRES_MODIFICATION",
      evaluation_ids: ["e1"] }] } }));
    expect(measured).not.toMatch(/checked=""/);
    expect(measured).toContain(TOLD.text);
  });
});

const BRIEF: DealBrief = {
  status: "WITH_LEGAL",
  counts: { changes_total: 55, changes_left: 55, changes_left_legal: 55, changes_left_for_me: 0,
            points_open: 11, sent_to_legal: true },
  asks: [
    { title: "Limitation of Liability", clause: "17", quote: "each party's total liability is capped at twelve months of fees", removed: false, row_key: "r1" },
    { title: "Termination", clause: "7", quote: "either party may end it on thirty days' notice", removed: false, row_key: "r2" },
    { title: "Indemnities", clause: "16", quote: "the Customer indemnifies the Provider", removed: true, row_key: "r3" },
  ],
  asks_more: 4,
  told: [{ text: "Test note: we offered a mutual cap and a thirty day exit", told_on: "2026-11-18" }],
  our_mistake: "Our company is named “Example Services Private Limited” in the version we sent, which is not the contracting entity.",
};
const view = (b: DealBrief, expanded = true) => renderToStaticMarkup(
  <BriefView brief={b} contractId="c"
             expanded={expanded} onToggle={() => {}} onOpen={() => {}} onChanged={() => {}} />);
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ");

describe("the deal brief (checks 5 and 6)", () => {
  it("tells the deal owner the status, who acts next and what the client asks, in plain words", () => {
    const said = text(view(BRIEF));
    expect(said).toContain("With Legal: 55 changes are being answered. Nothing for you yet.");
    expect(said).toContain("Limitation of Liability");
    expect(said).toContain("and 4 more");
    expect(said).toContain("What we told them");
    expect(said).toContain("Our own mistake");
    // check 6: the §7 grep, as sales
    expect(said).not.toMatch(/[A-Z]{2,}[-_][A-Z0-9_]|AM-[0-9]|§|Constitution|requirement|evaluat|deviation|classification|\*\*|##|\.docx|Ref [A-Z0-9]{6}/);
    expect(said).not.toMatch(/\bfinding|\bfallback|\bescalat|\blikely|\bprobably|\bAI\b|%/i);
    // no Legal part for the deal owner: no add, withdraw or label controls
    expect(said).not.toMatch(/Add what we told them|Withdraw|Start here|not discussed/);
  });

  it("collapses to three lines: the status, the top asks, the toggle", () => {
    const html = view(BRIEF, false);
    expect(text(html)).toContain("What the client asks for: Limitation of Liability, Termination, Indemnities and 4 more.");
    expect(html).not.toContain("lm-brief__body");
    expect(html.match(/<p /g) ?? []).toHaveLength(2);
  });

  it("offers no toggle when there is nothing more to show", () => {
    const html = view({ counts: { points_open: 3 } }, false);
    expect(html).not.toContain("Show the whole brief");
  });

  it("words the server's status code, and decides nothing itself (rule 18)", () => {
    const counts = { changes_total: 3, changes_left: 3, changes_left_legal: 2, changes_left_for_me: 1, points_open: 2 };
    expect(statusWords({ status: "SEND_REPLY", counts })).toBe("Your turn: Legal answered every change. Send our reply.");
    expect(statusWords({ status: "NOT_SENT", counts })).toBe("Not sent to Legal yet: 2 changes and 2 points need Legal. Send it to Legal.");
    expect(statusWords({ status: "WITH_LEGAL_AND_YOURS", counts }))
      .toBe("With Legal: 2 changes are being answered. Meanwhile, 1 change is yours to answer.");
    expect(statusWords({ status: "POINTS_OPEN", counts }))
      .toBe("With Legal: every change is answered. 2 points are still being decided.");
    expect(statusWords({ status: "LEGAL_QUEUE", counts })).toBe("2 changes to answer, 2 points to decide.");
    expect(statusWords({ counts })).toBeNull();                   // no code: no line
    expect(statusWords({ status: "CHECKING", counts })).toBe("LegalMind is still reading the client's version.");
    // round 3 (D1): an open point never sent to Legal, and a round no change went to Legal in
    expect(statusWords({ status: "SEND_POINTS_TO_LEGAL", counts })).toBe("2 points need Legal. Send it to Legal.");
    expect(statusWords({ status: "ALL_ANSWERED", counts })).not.toContain("Legal answered");
    expect(statusWords({ status: "YOURS_TO_ANSWER", counts })).toBe("Your turn: 1 change to answer. 2 points need Legal too.");
    // the same counts with another code say another thing: the words follow the code only
    expect(statusWords({ status: "WITH_LEGAL", counts: {} })).toBe("With Legal: 0 changes are being answered. Nothing for you yet.");
  });

  it("gives Legal the queue by Legal's own tie, the note and the add control", () => {
    const said = text(view({ ...BRIEF, status: "LEGAL_QUEUE", legal: {
      beyond: [{ row_key: "r1", clause: "17 Limitation of Liability" }], as_told: 30, not_discussed: 24,
      comments: ["10.5", "11.9"], whole_contract: [{ finding_id: "f", title: "Notice to end for convenience" }],
      note: "Test email pasted by sales", can_record: true } }));
    expect(said).toContain("55 changes to answer, 11 points to decide.");
    expect(said).toContain("Start here: 1 change goes further than what we told them");
    expect(said).toContain("30 changes as we told them. 24 changes not discussed");
    expect(said).toContain("Client comments: 10.5, 11.9");
    expect(said).toContain("Whole contract");
    expect(said).toContain("Test email pasted by sales");
    expect(said).toContain("Add what we told them");
  });
});

describe("a point no confirmed clause holds (round 4)", () => {
  it("is placed on the whole contract, with the candidate clauses for Legal only", () => {
    const html = renderToStaticMarkup(<WholeContractPlace candidates={["7.6.6", "17.6"]} />);
    expect(html).toContain(BRIEF_COPY.wholeContract);
    expect(html).toContain("Possibly in: clause 7.6.6, 17.6");       // can() is true here
    expect(renderToStaticMarkup(<WholeContractPlace />)).not.toContain("Possibly in");
    expect(renderToStaticMarkup(<WholeContractPlace candidates={["7", "7.1", "7.2", "7.3", "7.6.6", "11.4"]} />))
      .toContain("Possibly in: clause 7, 7.1, 7.2, 7.3 and 2 more");
    reader.legal = false;                                              // sales: the place only
    try {
      const sales = renderToStaticMarkup(<WholeContractPlace candidates={["7.6.6"]} />);
      expect(sales).toContain(BRIEF_COPY.wholeContract);
      expect(sales).not.toContain("Possibly in");
    } finally { reader.legal = true; }
  });
});
