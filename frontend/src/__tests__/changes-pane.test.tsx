/**
 * The Changes tab (CLM Phase 1, AB-150) — static render, house idiom. The server
 * routes every change and says who may answer; these pin that the screen draws only
 * the controls the reader may use (absent, never disabled), says a colleague's newer
 * answer in words, and renders an answer's line across rounds.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const viewer = vi.hoisted(() => ({ seesPosition: true, canUpload: true }));
vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: ["legal.decision"] },
                       can: (p: string) => p !== "document.upload" || viewer.canUpload }),
  useSeesLegalPosition: () => viewer.seesPosition,
}));

// the confirmation dialog's portal needs a DOM; its words are what is pinned here
vi.mock("@/components/Dialog", () => ({ Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

import { AnswerComposer, NO_STANDARD, composerError } from "@/components/workspace/ChangeComposer";
import {
  AcceptTogether, AnswerCard, COLLEAGUE, ChangesPane, EFFECT_FILTERS, ForUs, GateList, Marked, ReplyBar, answerError,
  declareConfirmLine, filtersFor, rowLabel,
} from "@/components/workspace/ChangesPane";
import { ApiError } from "@/lib/api";
import {
  EFFECT_LABEL, acceptable, actionsFor, historyLine, matches, redline, replyBlockers, whoLine, wordDiff,
  type Answer, type ChangeList, type ClientChange,
} from "@/lib/changes";
import type { DocumentVersion } from "@/lib/types";

const change = (over: Partial<ClientChange> = {}): ClientChange => ({
  row_key: "MODIFIED|a|b", kind: "MODIFIED", moved: false,
  clause: { number: "9", heading: "Limitation of Liability" }, page: 3,
  before: { evidence_ids: ["a"], text: "Liability is capped at 12 months of fees." },
  after: { evidence_ids: ["b"], text: "Liability is capped at 3 months of fees." },
  tracked: true, untracked: false,
  review: { before: [], after: [{ finding_id: "f1", requirement_code: "LIAB-1",
    classification: "DEVIATION", user_status: "REQUIRES_MODIFICATION", evaluation_ids: ["e1"] }] },
  review_delta: [{ requirement_code: "LIAB-1", before: "ACCEPTABLE", after: "REQUIRES_MODIFICATION" }],
  triage: null, route: "holder", route_reason: "MEASURED_BY_A_STANDARD", effect_for_us: "NEGATIVE",
  holder_accepted: false, answer: null, history: [], ...over,
});
const list = (over: Partial<ChangeList> = {}): ChangeList => ({
  contract_id: "c", from: { document_version_id: "v1", version_number: 1 },
  to: { document_version_id: "v2", version_number: 2 },
  summary: { total: 1, untracked: 0 }, changes: [], can_answer: true, can_decide: false, ...over,
});
const card = (c: ClientChange, l: ChangeList) => renderToStaticMarkup(
  <AnswerCard change={c} list={l} contractId="c" onAnswered={() => {}} onReload={() => {}} />);
const compose = (c: ClientChange, l: ChangeList, initial: Answer) => renderToStaticMarkup(
  <AnswerComposer change={c} list={l} actions={actionsFor(c, l)} contractId="c" details={[]}
                  onAnswered={() => {}} onReload={() => {}} initial={initial} />);
const LAWYER = { can_answer: true, can_decide: true, can_write_wording: true } as const;
const answered = (answer: Answer, over: Record<string, unknown> = {}) => ({
  round: 2, version_number: 1, answer, reason: "agreed on the call", decided_by: "Counsel",
  decided_at: "2026-11-03T10:00:00Z", ...over });

describe("who may answer (AM-250)", () => {
  it("gives the owner no accept control on a change a holder decides", () => {
    const html = card(change(), list());
    expect(html).toContain(">Keep ours</button>");
    expect(html).toContain("Ask Legal");
    expect(html).not.toContain("Accept theirs");
    expect(html).not.toContain("Your Legal Decision");
    expect(html).not.toContain("disabled=\"\"");
  });

  it("lets the owner accept once a holder's decision accepts it", () => {
    expect(card(change({ holder_accepted: true }), list())).toContain("Accept theirs");
  });

  it("puts the holder's decision in place, and nothing to ask", () => {
    const html = card(change(), list({ can_decide: true }));
    expect(html).toContain('role="radiogroup"');
    expect(html).toContain("Accept theirs");
    expect(html).not.toContain("Ask Legal");
    const panel = compose(change(), list({ can_decide: true }), "accept_theirs");
    expect(panel).toContain("Record your Legal Decision on each point below");
    expect(panel).not.toContain(">Accept theirs</button>");      // the decision, not the answer
  });

  it("never nests the Legal Decision's form inside the answer's (B3)", () => {
    const details = [{ finding: { id: "f1" }, evaluations: [{ id: "e1", current_decision: null }] }] as unknown as
      NonNullable<Parameters<typeof AnswerComposer>[0]["details"]>;
    const html = renderToStaticMarkup(
      <AnswerComposer change={change()} list={list({ can_decide: true })} actions={actionsFor(change(), list(LAWYER))}
                      contractId="c" details={details} onAnswered={() => {}} onReload={() => {}}
                      initial="accept_theirs" />);
    expect(html).toContain("ws-decision");        // the decision is drawn in the panel…
    expect(html).not.toContain("<form");          // …and no form wraps it to swallow its submit
  });

  it("lets a holder answer a change no standard measures, reason required (AM-281)", () => {
    const unmeasured = change({ review: { before: [], after: [] }, unmeasured: true,
                                route_reason: "NO_STANDARD_MEASURES_IT" });
    const html = compose(unmeasured, list({ can_answer: false, can_decide: true }), "accept_theirs");
    expect(html).toContain("recorded as your answer, not a Legal Decision");
    expect(html).toContain(">Accept theirs</button>");
    expect(html).toContain("(required)");
    expect(card(unmeasured, list())).not.toContain("recorded as your answer");   // owner
  });

  it("gives the owner both answers on a formatting-only change", () => {
    const html = card(change({ route: "owner", route_reason: "FORMATTING_ONLY", review: { before: [], after: [] } }), list());
    expect(html).toContain("Keep ours");
    expect(html).toContain("Accept theirs");
  });

  it("shows a reader the change and no control at all", () => {
    const html = card(change({ route: "owner" }), list({ can_answer: false }));
    expect(html).not.toContain("<button");
    expect(html).toContain("Change needed");            // the review's own word, quoted
  });

  it("filters holder rows apart from answered ones", () => {
    const l = list();
    expect(matches(change(), "holder", l)).toBe(true);
    expect(matches(change({ answer: { round: 2, version_number: 1, answer: "keep_ours",
      reason: null, decided_by: "Owner", decided_at: "2026-11-02T10:00:00Z" } }), "holder", l)).toBe(false);
  });
});

describe("the reader's own work (matches the To-do's count)", () => {
  it("puts a holder change under Legal's work, not the owner's", () => {
    expect(matches(change(), "mine", list())).toBe(false);
    expect(matches(change(), "mine", list({ can_answer: false, can_decide: true }))).toBe(true);
    expect(matches(change({ route: "owner" }), "mine", list())).toBe(true);
    expect(matches(change({ holder_accepted: true }), "mine", list())).toBe(true);
  });
});

describe("answers and their history (AM-253)", () => {
  it("says a stale answer is a colleague's, never the server's raw words", () => {
    const conflict = answerError(new ApiError(409, "CONFLICT", "stale", "r1"));
    expect(conflict).toEqual({ conflict: true, message: COLLEAGUE });
    expect(COLLEAGUE).toContain("Changed by a colleague");
    expect(answerError(new ApiError(403, "LEGAL_DECISION_REQUIRED", "x", "r")).conflict).toBe(false);
  });

  it("renders the line across rounds, oldest first", () => {
    const history = [
      { round: 2, version_number: 1, answer: "keep_ours" as const, reason: null,
        decided_by: "Owner", decided_at: "2026-10-24T10:00:00Z" },
      { round: 4, version_number: 1, answer: "accept_theirs" as const, reason: "lower cap agreed",
        decided_by: "Counsel", decided_at: "2026-10-30T10:00:00Z" },
    ];
    expect(historyLine(history)).toBe(
      "R1: kept ours (Owner, 24 Oct 2026) → R2: accepted theirs (Counsel, 30 Oct 2026, lower cap agreed)");
    expect(card(change({ history, answer: history[1]! }), list())).toContain("R1: kept ours (Owner, 24 Oct 2026)");
  });
});

describe("the marks (AM-255)", () => {
  it("underlines what the client added and strikes what it removed, in words too", () => {
    expect(wordDiff("capped at 12 months", "capped at 3 months")).toEqual([
      { op: "eq", text: "capped at " }, { op: "del", text: "12" }, { op: "ins", text: "3" },
      { op: "eq", text: " months" }]);
    const html = renderToStaticMarkup(<Marked change={change()} list={list()} />);
    expect(html).toContain("<del><span class=\"ws-visually-hidden\">client removed: </span>12</del>");
    expect(html).toContain("<ins><span class=\"ws-visually-hidden\">client added: </span>3</ins>");
  });
});

describe("a redline that reads (page 3)", () => {
  it("marks only the colon on a heading, never the word twice", () => {
    expect(wordDiff("SERVICES", "SERVICES:")).toEqual([{ op: "eq", text: "SERVICES" }, { op: "ins", text: ":" }]);
    expect(wordDiff("Interpretation", "INTERPRETATION:")).toEqual([
      { op: "eq", text: "I" }, { op: "case", text: "NTERPRETATION" }, { op: "ins", text: ":" }]);
    const html = renderToStaticMarkup(<Marked change={change({ before: { evidence_ids: [], text: "SERVICES" },
      after: { evidence_ids: [], text: "SERVICES:" } })} list={list()} />);
    expect(html).toContain("cx-marked--heading");
    expect(html).toContain("<span>SERVICES</span><ins>");
  });

  it("draws a rewritten clause as ours struck above and theirs below", () => {
    const ours = "The Indemnifying Party shall defend the other against any third-party claims arising from a breach.";
    const theirs = "Each Party agrees to hold harmless its affiliates, officers and directors from all losses and costs.";
    expect(redline(ours, theirs).replaced).toBe(true);
    expect(redline("capped at 12 months of fees in total", "capped at 3 months of fees in total").replaced).toBe(false);
    const html = renderToStaticMarkup(<Marked change={change({ before: { evidence_ids: [], text: ours },
      after: { evidence_ids: [], text: theirs } })} list={list()} />);
    expect(html).toContain("cx-replaced");
    expect(html).toContain("Ours, version 1");
    expect(html).toContain("The client&#x27;s, version 2");
  });

  it("names a bare-number row by its first words", () => {
    expect(rowLabel(change({ clause: { number: "1.2", heading: null },
      after: { evidence_ids: [], text: "1.2 The headings are for convenience only." } }), "1"))
      .toBe("1.2 The headings are for convenience only.");
  });
});

describe("counted by who answers (page 3)", () => {
  const fmt = change({ route: "owner", route_reason: "FORMATTING_ONLY", review: { before: [], after: [] } });
  it("puts a deal owner's formatting row under the deal owner, never Legal's own work", () => {
    expect(filtersFor(LAWYER).map((f) => f.label)).toEqual(["Yours to answer", "Deal owner's", "Answered", "All"]);
    expect(filtersFor(list()).map((f) => f.label)).toEqual(["Yours to answer", "With Legal", "Answered", "All"]);
    expect(matches(fmt, "mine", list(LAWYER))).toBe(false);
    expect(matches(fmt, "owner", list(LAWYER))).toBe(true);
    expect(matches(change(), "mine", list(LAWYER))).toBe(true);
    expect(whoLine(fmt, list(LAWYER))).toBe("Deal owner answers");
    expect(whoLine(fmt, list())).toBe("Yours to answer");
  });
});

describe("the actions each person has (S2, AM-291 r2)", () => {
  it("gives Sales their own answers only, and Ask Legal on Legal's points", () => {
    expect(actionsFor(change({ route: "owner" }), list())).toEqual(["keep_ours", "accept_theirs"]);
    expect(actionsFor(change(), list())).toEqual(["keep_ours"]);
    const html = card(change(), list());
    expect(html).not.toContain("Write our wording");
    expect(html).not.toContain("Use our standard");
    expect(html).not.toContain("Internal note");
    expect(html).not.toContain('role="radiogroup"');
  });

  it("gives the lawyer all four, as one choice", () => {
    expect(actionsFor(change(), list(LAWYER)))
      .toEqual(["keep_ours", "accept_theirs", "use_standard", "write_wording"]);
    const html = card(change(), list(LAWYER));
    for (const label of ["Keep ours", "Accept theirs", "Use our standard", "Write our wording"]) {
      expect(html).toContain(`<span>${label}</span>`);
    }
  });

  it("on the client's paper: no Keep ours, and our standard only where one is published (AM-294)", () => {
    const theirs = change({ kind: "THEIRS", before: null, anchor: { left_key: null, clause_version_id: null } });
    expect(actionsFor(theirs, list(LAWYER))).toEqual(["accept_theirs", "write_wording"]);
    expect(card(theirs, list({ ...LAWYER, from: null }))).toContain(NO_STANDARD);
    const anchored = { ...theirs, anchor: { left_key: "clause:liab", clause_version_id: "cv1" } };
    expect(actionsFor(anchored, list(LAWYER))).toEqual(["accept_theirs", "use_standard", "write_wording"]);
  });

  it("says a missing standard clause plainly", () => {
    expect(composerError(new ApiError(409, "NO_STANDARD_CLAUSE", "x", "r")).message).toBe(NO_STANDARD);
  });
});

describe("Write our wording (AM-284) and the notes (AM-285)", () => {
  it("opens on their text, previews the redline, and keeps the two notes apart", () => {
    viewer.seesPosition = true;
    const html = compose(change(), list(LAWYER), "write_wording");
    expect(html).toContain("Liability is capped at 3 months of fees.</textarea>");
    expect(html).toContain("How the client will see it");
    expect(html).toContain("Sent to the client");
    expect(html).toContain("a comment on this change in our reply");
    expect(html).toContain("Only Legal sees this");
    expect(html).toContain("never sent");
    expect(html).toContain("(required)");                         // the reason
    expect(html).toContain("Never sent to the client.");          // who reads the reason
    expect(html).toContain("Record our wording");
  });

  it("has no internal note for a reader who could not read it back", () => {
    viewer.seesPosition = false;
    expect(compose(change(), list(LAWYER), "keep_ours")).not.toContain("Only Legal sees this");
    viewer.seesPosition = true;
  });

  it("draws a recorded internal note only when the server sent its key", () => {
    const withNote = change({ answer: answered("keep_ours", { internal_note: "they will push back" }) });
    expect(card(withNote, list(LAWYER))).toContain("they will push back");
    const without = change({ answer: answered("keep_ours", { client_note: "As agreed." }) });
    const html = card(without, list(LAWYER));
    expect(html).toContain("As agreed.");
    expect(html).not.toContain("Internal note · only Legal sees this");
  });

  it("says Waiting for approval after our wording on a measured point", () => {
    const waiting = change({ answer: answered("write_wording", { wording: "Liability is capped at 6 months of fees." }),
                             waiting_for_approval: true });
    expect(whoLine(waiting, list(LAWYER))).toBe("Waiting for approval");
    const html = card(waiting, list(LAWYER));
    expect(html).toContain("<strong>Waiting for approval</strong>");
    expect(html).toContain("second person");
    expect(html).toContain("Our wording, against theirs");
    expect(whoLine({ ...waiting, waiting_for_approval: false }, list(LAWYER))).toBe("Our wording");
  });

  it("keeps line 1 (the review's word) apart from line 2 (who answers)", () => {
    const html = card(change(), list());
    // the one status set's icon, then the review's word (AM-291 r1)
    expect(html).toMatch(/class="cx-line1"><span class="ws-status ws-status--review"[^>]*>.*?<\/span><strong>Change needed<\/strong>/);
    expect(html).toMatch(/class="cx-line2"[^>]*><strong>With Legal<\/strong>/);
    expect(whoLine(change(), list(LAWYER))).toBe("Yours to answer");
  });
});

describe("what still stops our reply (R6, AM-293)", () => {
  const rows = [change({ row_key: "a" }), change({ row_key: "b", answer: answered("accept_theirs") }),
    change({ row_key: "c", answer: answered("write_wording"), waiting_for_approval: true }),
    change({ row_key: "d", route: "owner", answer: answered("keep_ours") })];

  it("lists every open change by why it is open", () => {
    const b = replyBlockers(rows);
    expect(b.open.map((c) => c.row_key)).toEqual(["a"]);
    expect(b.legal.map((c) => c.row_key)).toEqual(["b"]);
    expect(b.approval.map((c) => c.row_key)).toEqual(["c"]);
  });

  it("offers no Prepare while anything is open, and says how many", () => {
    const html = renderToStaticMarkup(<ReplyBar contractId="c" versions={[]} onVersionCreated={() => {}}
      onPick={() => {}} list={list({ changes: rows, summary: { total: 4, untracked: 0 } })} />);
    expect(html).toContain("3 still open before the reply");
    expect(html).not.toContain("Prepare our reply");
  });

  it("names each undecided point of a refused download, linked to it", () => {
    const html = renderToStaticMarkup(<GateList message="This reply cannot leave LegalMind yet."
      gate={{ reason: "UNDECIDED_POINTS", open_points: [{ finding_id: "f9", requirement_code: "LIAB-1" }] }} />);
    expect(html).toContain('href="?finding=f9"');
    expect(html).toContain("needs a decision");
  });
});

describe("what each change does for us (AM-299)", () => {
  const better = change({ row_key: "b", route: "favour", route_reason: "IN_OUR_FAVOUR", effect_for_us: "POSITIVE",
    review: { before: [], after: [{ finding_id: "f2", requirement_code: "LIAB-1", classification: "DEVIATION",
      user_status: "ACCEPTABLE", evaluation_ids: ["e2"] }] } });
  const same = change({ row_key: "s", route: "owner", route_reason: "STILL_MATCHES_OUR_STANDARD", effect_for_us: "NEUTRAL",
    review: { before: [], after: [{ finding_id: "f3", requirement_code: "LIAB-1", classification: "MATCH",
      user_status: "ACCEPTABLE", evaluation_ids: ["e3"] }] } });
  const worse = change({ row_key: "w" });

  it("says it in words and a distinct shape for each — never colour alone", () => {
    const marks = (["POSITIVE", "NEUTRAL", "NEGATIVE"] as const).map((e) => renderToStaticMarkup(<ForUs effect={e} />));
    expect(marks.map((m) => m.replace(/<[^>]+>/g, ""))).toEqual(["Better for us", "No change for us", "Worse for us"]);
    const glyphs = marks.map((m) => m.match(/lucide-[a-z-]+/)?.[0]);
    expect(new Set(glyphs).size).toBe(3);
    expect(marks.join("")).not.toMatch(/style=|#[0-9a-f]{3,6}/i);
  });

  it("filters by effect, apart from who answers", () => {
    expect(EFFECT_FILTERS.map((f) => f.label)).toEqual(Object.values(EFFECT_LABEL));
    const all = [better, same, worse];
    expect(all.filter((c) => matches(c, "POSITIVE", list())).map((c) => c.row_key)).toEqual(["b"]);
    expect(all.filter((c) => matches(c, "NEUTRAL", list())).map((c) => c.row_key)).toEqual(["s"]);
    expect(all.filter((c) => matches(c, "NEGATIVE", list())).map((c) => c.row_key)).toEqual(["w"]);
  });

  it("offers only no-change (formatting) rows to accept together, never a better, worse or a reader's (AM-317 r2)", () => {
    const all = [better, same, worse, change({ row_key: "b2", effect_for_us: "POSITIVE", route: "favour",
      answer: answered("accept_theirs") })];
    expect(acceptable(all, "POSITIVE", list())).toEqual([]);
    expect(acceptable(all, "NEUTRAL", list()).map((c) => c.row_key)).toEqual(["s"]);
    expect(acceptable(all, "NEUTRAL", list({ can_answer: false }))).toEqual([]);
    const pane = renderToStaticMarkup(
      <ChangesPane contractId="c" versions={[]} onVersionCreated={() => {}}
                   changes={{ state: { kind: "ready", list: list({ changes: all }) }, setState: () => {},
                              reload: () => {}, enabled: true }} />);
    expect(pane).toContain("Accept all 1");
    expect(pane).toContain("Only changes worse for us go to Legal.");
  });

  it("lets the owner accept a better or a same change in one click, and asks Legal only on a worse one", () => {
    for (const c of [better, same]) {
      const html = card(c, list());
      expect(html).toContain(">Accept theirs</button>");
      expect(html).not.toContain("Ask Legal");
      expect(html).toContain("The deal owner can accept it without Legal.");
    }
    const html = card(worse, list());
    expect(html).toContain("Worse for us");
    expect(html).toContain("Ask Legal");
    expect(html).not.toContain(">Accept theirs</button>");
  });

  it("confirms a together-acceptance in plain words: who, why, and that Legal can reopen it", () => {
    const html = renderToStaticMarkup(
      <AcceptTogether effect="NEUTRAL" rows={[same]} list={list()} contractId="c"
                      onClose={() => {}} onDone={() => {}} onReload={() => {}} />);
    expect(html).toContain("Accept 1 change with no change for us?");
    expect(html).toContain("Legal can still reopen any of them");
    expect(html).not.toMatch(/NEUTRAL|POSITIVE|AM-/);
  });
});

describe("P1 — a version nobody declared (owner, 2026-11-09)", () => {
  it("asks whose paper it is instead of listing a guessed pair", () => {
    const error = new ApiError(422, "VERSION_ROLE_UNDECLARED",
      "Nobody has said whose paper version 2 is.", "r");
    const versions = [
      { id: "v2", version_number: 2, original_filename: "client-v2.docx" },
      { id: "v1", version_number: 1, version_role: "COMPANY_DRAFT" },
    ] as unknown as DocumentVersion[];
    const html = renderToStaticMarkup(
      <ChangesPane contractId="c" versions={versions} onVersionCreated={() => {}}
                   changes={{ state: { kind: "error", error }, setState: () => {},
                              reload: () => {}, enabled: true }} />);
    expect(html).toContain("Whose paper is this version?");
    expect(html).toContain("Version 2 (client-v2.docx) is");
    expect(html).not.toContain("Version 1");
    expect(html).toContain(">ours</button>");
    expect(html).not.toContain("Try again");
  });

  it("offers the declaration only to those who may make it, and confirms it is final", () => {
    const error = new ApiError(422, "VERSION_ROLE_UNDECLARED", "Nobody has said.", "r");
    const versions = [{ id: "v2", version_number: 2 }] as unknown as DocumentVersion[];
    const render = () => renderToStaticMarkup(
      <ChangesPane contractId="c" versions={versions} onVersionCreated={() => {}}
                   changes={{ state: { kind: "error", error }, setState: () => {},
                              reload: () => {}, enabled: true }} />);
    viewer.canUpload = false;
    const reader = render();
    viewer.canUpload = true;
    expect(reader).not.toContain(">ours</button>");
    expect(reader).toContain("Ask the deal owner to say whose paper it is.");
    expect(render()).toContain(">ours</button>");
    expect(declareConfirmLine(2, "CLIENT_MODIFIED"))
      .toBe("Declare version 2 the client\u2019s? This can\u2019t be changed later.");
    expect(declareConfirmLine(3, "COMPANY_DRAFT")).toContain("version 3 ours?");
  });
});
