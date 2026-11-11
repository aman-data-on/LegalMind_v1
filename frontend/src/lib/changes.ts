/**
 * The client's changes, as the server lists them (CLM Phase 1, AB-150) — the wire
 * types and the few pure helpers the Changes tab renders with. Nothing here decides
 * a route, a status word or who may answer: every one of those is the server's
 * (`GET /contracts/{id}/changes`), and the screen only shows it (rule 18).
 */

import { USER_STATUS_LABELS, requirementTitle, type UserStatus } from "@/components/workspace/findingLanguage";
import { sectionRef } from "@/lib/documentTypes";
import { formatDate } from "@/lib/dates";

/** THEIRS: the client's paper came first (`AM-290`) — one row per point the review
 *  found, with no wording of ours before it. */
export type ChangeKind = "MODIFIED" | "ADDED" | "DELETED" | "MOVED" | "NEW_ANNEXURE" | "THEIRS";
export type ChangeRoute = "owner" | "holder" | "favour";
/** What a change does for us (`AM-299`) — the server's own field, never a classification
 *  or a decision (the five axes). Anything unmeasured or unclear arrives as NEGATIVE. */
/** `AM-306`: FALLBACK — inside our standard, but a step back from our own paper's figure. */
export type EffectForUs = "POSITIVE" | "NEUTRAL" | "FALLBACK" | "NEGATIVE";
/** Accepted together, without Legal: every effect but NEGATIVE. */
export type AcceptableEffect = Exclude<EffectForUs, "NEGATIVE">;
export const ACCEPTABLE_EFFECTS: AcceptableEffect[] = ["POSITIVE", "NEUTRAL", "FALLBACK"];
export type Answer = "keep_ours" | "accept_theirs" | "use_standard" | "write_wording";

export interface ChangeFinding {
  finding_id: string;
  requirement_code: string;
  classification: string;
  user_status: UserStatus;
  evaluation_ids: string[];
}

export interface AnswerEntry {
  round: number;
  version_number: number;
  answer: Answer;
  reason: string | null;
  decided_by: string;
  decided_at: string;
  /** `AM-284`: the lawyer's own wording, and the hash its Legal Decision carries */
  wording?: string | null;
  wording_sha256?: string | null;
  /** `AM-284` r5: the published clause "Use our standard" inserted */
  clause_version_id?: string | null;
  /** `AM-284` r6: goes into the reply as a Word comment the client reads */
  client_note?: string | null;
  /** `AM-285` r3: the KEY is absent for a reader without `legal_position.view` */
  internal_note?: string | null;
}

export interface ClientChange {
  row_key: string;
  kind: ChangeKind;
  moved: boolean;
  clause: { number: string | null; heading: string | null };
  page: number | null;
  before: { evidence_ids: string[]; text: string } | null;
  after: { evidence_ids: string[]; text: string } | null;
  tracked: boolean;
  untracked: boolean;
  review: { before: ChangeFinding[]; after: ChangeFinding[] };
  review_delta: { requirement_code: string; before: UserStatus | null; after: UserStatus | null }[];
  triage: {
    effect: string | null;
    reasons: { reason: string; quote: string }[];
    reading?: { label: string; quote: string };
    /** `position` is OMITTED for a reader who may not see positions (LEGAL-02). */
    topics: { section: string; title: string; position?: string }[];
  } | null;
  route: ChangeRoute;
  route_reason: string;
  effect_for_us: EffectForUs;
  favour_reason?: string;
  /** holder route only: an EFFECTIVE Legal Decision accepts every Evaluation — or, where
   *  none exists, a holder recorded "accept theirs" as their answer (`AM-281`) */
  holder_accepted?: boolean;
  /** holder route only: no Evaluation on either side — nothing a decision is recorded on */
  unmeasured?: boolean;
  answer: AnswerEntry | null;
  history: AnswerEntry[];
  /** our wording on a measured point, its Legal Decision not effective yet (`AM-291` r1) */
  waiting_for_approval?: boolean;
  /** client paper first (`AM-290`): our published clause for this point, if one exists */
  anchor?: { left_key: string | null; clause_version_id: string | null };
  /** `AM-308`: the clause of ours this row is about and what the final contract does to
   *  it — both keys absent where no final contract can be made from this pair */
  target?: { key: string; number: string | null; heading: string | null } | null;
  in_package?: "replace" | "delete" | "insert" | "none" | "cannot";
}

export interface TemplateLink {
  template_key: string;
  version: number;
  title: string | null;
  /** found by the template ID in its footer, or by its structure */
  how: "id" | "structure";
  current_version: number | null;
  older: boolean;
  /** "Made from an older template (v2); the current one is v3." — the server's words */
  message: string | null;
}

/** What the left side of a change is called: our version, or the template it came from */
export function oursLabel(list: Pick<ChangeList, "from" | "template">): string {
  return list.template ? `Our template, version ${list.template.version}`
    : `Ours, version ${list.from?.version_number ?? ""}`;
}

export interface ChangeList {
  contract_id: string;
  /** null: the client's paper came first — no version of ours before it (`AM-290`) */
  from: { document_version_id: string; version_number: number } | null;
  to: { document_version_id: string; version_number: number };
  /** `AM-302`: the returned copy was made from our blank template — compared with it */
  template?: TemplateLink;
  /** `AM-307`: why a side's Special Conditions (Annexure A) could not be applied — the
   *  list then compares the raw text and every change goes to Legal; absent otherwise */
  special_conditions_not_applied?: string[];
  summary: { total: number; untracked: number } & Record<string, number>;
  changes: ClientChange[];
  can_answer: boolean;
  /** May record our version as sent — outlives the round, unlike `can_answer`. */
  can_send?: boolean;
  can_decide: boolean;
  /** holds `legal.approve_customization` and may answer: "Write our wording" (`AM-284` r1) */
  can_write_wording?: boolean;
}

/** Why a reply may not leave LegalMind yet (`AM-293` r1) — the points, never a position. */
export interface ReplyGate {
  reason: "ANALYSIS_NOT_FINISHED" | "UNDECIDED_POINTS";
  open_points: { finding_id: string; requirement_code: string }[];
}

/** A change the reply cannot write into the client's file by itself (AB-151). */
export interface ManualRow {
  row_key: string;
  clause: string;
  reason: string;
  /** on a prepared reply: whether a Word comment marks the place */
  commented?: boolean;
}

export interface PreparedReply {
  document_version: { id: string; version_number: number };
  kept_ours: number;
  accepted_theirs: number;
  our_wording?: number;
  our_standard?: number;
  manual_rows: ManualRow[];
  downloads: { docx: string; pdf: string };
  /** null once the reply's own review has nothing undecided — then it may be downloaded */
  open_points?: ReplyGate | null;
}

export const KIND_LABEL: Record<ChangeKind, string> = {
  MODIFIED: "Wording changed",
  ADDED: "Added by the client",
  DELETED: "Removed by the client",
  MOVED: "Moved",
  NEW_ANNEXURE: "New annexure",
  THEIRS: "Their clause",
};

export const ANSWER_LABEL: Record<Answer, string> = {
  keep_ours: "kept ours",
  accept_theirs: "accepted theirs",
  use_standard: "our standard",
  write_wording: "our wording",
};

/** Why the server routed a change where it did — its codes, in plain words. "Legal" is
 *  whoever holds the decision right; "the deal owner" is the contract's owner or a
 *  colleague on it. Never a verdict: who answers, not whether it is acceptable. */
export const ROUTE_REASON: Record<string, string> = {
  FORMATTING_ONLY: "Only formatting changed, so the deal owner answers.",
  IN_OUR_FAVOUR: "It differs from our position in our favour, so the deal owner may accept it.",
  STILL_MATCHES_OUR_STANDARD: "It still says what our standard says, so the deal owner may accept it.",
  MEASURED_BY_A_STANDARD: "One of our approved positions covers this clause, so Legal decides.",
  NO_STANDARD_MEASURES_IT: "None of our standards covers this clause, so Legal decides.",
  MOVED: "The clause moved, so Legal decides.",
};

/** What a change does for us, in words: the row's short form and the card's sentence.
 *  "Worse" also covers what could not be measured — it is the one that needs review. */
export const EFFECT_LABEL: Record<EffectForUs, string> = {
  POSITIVE: "Better for us",
  NEUTRAL: "No change for us",
  FALLBACK: "Fallback",
  NEGATIVE: "Worse for us",
};
export const EFFECT_SENTENCE: Record<EffectForUs, string> = {
  POSITIVE: "The deal owner can accept it without Legal.",
  NEUTRAL: "The deal owner can accept it without Legal.",
  FALLBACK: "The deal owner can accept it without Legal. It gives up some of our opening position.",
  NEGATIVE: "Legal reviews it. A change our standards cannot measure counts here too.",
};

/** The open changes this reader may accept together: only "No change for us" — the
 *  same words, formatting only (`AM-317` r2; `POST …/changes/accept` checks the same).
 *  A better-for-us or fallback figure is answered one by one. */
export function acceptable(changes: ClientChange[], effect: AcceptableEffect,
                           list: Pick<ChangeList, "can_answer">): ClientChange[] {
  return list.can_answer && effect === "NEUTRAL"
    ? changes.filter((c) => c.effect_for_us === effect && c.answer === null) : [];
}

/** Who answers a change, in two words — the server's route, never re-derived. */
export const ROUTE_LABEL: Record<ChangeRoute, string> = {
  owner: "Deal owner answers",
  holder: "With Legal",
  favour: "In our favour",
};

export function where(change: ClientChange): string {
  const { number, heading } = change.clause;
  const head = [sectionRef(number), heading].filter(Boolean).join(" ");
  if (head) return head;
  // a point on the client's paper the review found nowhere in the text (MISSING)
  const point = change.kind === "THEIRS" ? change.review.after[0]?.requirement_code : undefined;
  return point ? requirementTitle({ code: point }) : change.page ? `Page ${change.page}` : "Opening text";
}

/** The four actions, by their `AM-291` r2 names. */
export const ACTION_LABEL: Record<Answer, string> = {
  keep_ours: "Keep ours",
  accept_theirs: "Accept theirs",
  use_standard: "Use our standard",
  write_wording: "Write our wording",
};

type Reader = Pick<ChangeList, "can_answer" | "can_decide" | "can_write_wording">;

/** Whether this reader answers as Legal: the four actions, the notes, the decisions. */
export const answersAsLegal = (list: Reader) => list.can_decide || !!list.can_write_wording;

/** The actions this reader may take on a change, in their fixed order — from the
 *  server's own flags only (presentation: every write checks again). An action the
 *  reader may not take is not in the list, so it is never drawn (52.4). */
export function actionsFor(change: ClientChange, list: Reader): Answer[] {
  const theirs = change.kind === "THEIRS";
  const legal = answersAsLegal(list);
  const holder = change.route === "holder";
  const out: Answer[] = [];
  // AM-294 r2: on the client's paper there is no wording of ours to keep
  if (list.can_answer && !theirs) out.push("keep_ours");
  // accepting a point Legal decides: the decision itself for a holder, nothing for Sales
  if (holder ? (change.holder_accepted ? list.can_answer : list.can_decide) : list.can_answer) {
    out.push("accept_theirs");
  }
  // our published clause: Legal's answer; on their paper only where one is anchored
  if (legal && list.can_answer && (!theirs || change.anchor?.clause_version_id)) out.push("use_standard");
  if (list.can_write_wording) out.push("write_wording");
  return out;
}

/** Line 1 of a point (`AM-291` r1): the review's word against our standard, when the
 *  clause is not simply a match. Never merged with line 2. */
export function readerWord(change: ClientChange): string | null {
  const status = readerStatus(change);
  return status ? USER_STATUS_LABELS[status] : null;
}

/** The server's reader status behind `readerWord` — what the one StatusChip shows. */
export function readerStatus(change: ClientChange): UserStatus | null {
  return change.review.after.find((x) => x.user_status !== "ACCEPTABLE")?.user_status ?? null;
}

/** Which of the four marks a change carries (the one status set, `PointStatus`): the
 *  review's word on the client's clause, "Decided" once answered or accepted by Legal;
 *  null when no standard measures it. */
export function changeBucket(change: ClientChange): "match" | "review" | "decided" | "missing" | null {
  const after = change.review.after;
  if (!after.length) return null;
  if (change.answer || change.holder_accepted) return "decided";
  if (after.every((f) => f.user_status === "ACCEPTABLE")) return "match";
  return after.some((f) => f.user_status === "MISSING") ? "missing" : "review";
}

/** Line 2 of a point: what was answered, or who answers it — the server's route and
 *  flags, worded for this reader. */
export function whoLine(change: ClientChange, list: Reader): string {
  const a = change.answer;
  if (a) {
    if (a.answer === "write_wording" && change.waiting_for_approval) return "Waiting for approval";
    return ANSWER_LABEL[a.answer].replace(/^./, (c) => c.toUpperCase());
  }
  if (change.route === "holder" && !change.holder_accepted) {
    return list.can_decide ? "Yours to answer" : "With Legal";
  }
  // a Legal reader may answer a deal owner's row, but it is not theirs to answer
  return list.can_answer && !list.can_decide ? "Yours to answer" : ROUTE_LABEL.owner;
}

/** What still stops our reply, from the list (the server refuses the same, `REPLY_NOT_READY`). */
export function replyBlockers(changes: ClientChange[]) {
  const legalFirst = (c: ClientChange) => c.route === "holder" && !c.holder_accepted;
  return {
    /** unanswered, by who acts: Legal decides, or the deal owner answers */
    withLegal: changes.filter((c) => c.answer === null && legalFirst(c)),
    withOwner: changes.filter((c) => c.answer === null && !legalFirst(c)),
    open: changes.filter((c) => c.answer === null),
    legal: changes.filter((c) => c.answer?.answer === "accept_theirs" && c.route === "holder"
      && !c.holder_accepted),
    approval: changes.filter((c) => !!c.waiting_for_approval),
  };
}

export type Filter = "holder" | "owner" | "mine" | "answered" | "all" | EffectForUs;

/** Presentation only: which rows each filter shows, from the server's own fields. */
export function matches(change: ClientChange, filter: Filter, list: Pick<ChangeList, "can_answer" | "can_decide">): boolean {
  switch (filter) {
    case "holder":
      return change.route === "holder" && !change.holder_accepted && change.answer === null;
    case "owner":
      // a Legal reader's view of the deal owner's rows: open, not a holder's
      return change.answer === null && change.route !== "holder";
    case "mine":
      // Legal (`legal.decision`): the holder's rows — what only Legal settles, counted
      // by who answers, so a deal owner's formatting row is never "yours". Anyone
      // else: the deal owner's own routes, and a holder change Legal has accepted.
      if (list.can_decide) return change.answer === null && change.route === "holder";
      return change.answer === null && list.can_answer
        && (change.route !== "holder" || !!change.holder_accepted);
    case "answered":
      return change.answer !== null;
    case "POSITIVE":
    case "NEUTRAL":
    case "FALLBACK":
    case "NEGATIVE":
      return change.effect_for_us === filter;
    default:
      return true;
  }
}


/** "R1: kept ours (Owner, 24 Oct) → R2: accepted theirs (Counsel, 30 Oct, reason)" —
 *  one round number per client version, oldest first. */
export function historyLine(history: AnswerEntry[]): string {
  const rounds = [...new Set(history.map((h) => h.round))];
  return history
    .map((h) => {
      const who = [h.decided_by, formatDate(h.decided_at), h.reason].filter(Boolean).join(", ");
      return `R${rounds.indexOf(h.round) + 1}: ${ANSWER_LABEL[h.answer]} (${who})`;
    })
    .join(" → ");
}

/** "Explain this" — assembled from what the review recorded and what code read; no
 *  sentence is written here that the server did not give. */
export function explanation(change: ClientChange, versions: { from: number; to: number }): string[] {
  const out: string[] = [];
  for (const f of change.review.after) {
    out.push(`The review of version ${versions.to} reads ${requirementTitle({ code: f.requirement_code })}: ${USER_STATUS_LABELS[f.user_status]}.`);
  }
  for (const d of change.review_delta) {
    if (d.before && d.after) {
      out.push(`${requirementTitle({ code: d.requirement_code })} was "${USER_STATUS_LABELS[d.before]}" on version ${versions.from}.`);
    } else if (d.before) {
      out.push(`${requirementTitle({ code: d.requirement_code })} was measured on version ${versions.from} ("${USER_STATUS_LABELS[d.before]}") and is not on this clause now.`);
    }
  }
  for (const r of change.triage?.reasons ?? []) out.push(`${r.reason}: “${r.quote}”`);
  if (change.triage?.reading) out.push(`${change.triage.reading.label} “${change.triage.reading.quote}”`);
  for (const t of change.triage?.topics ?? []) {
    if (t.position) out.push(`Our position (${t.title}): ${t.position}`);
  }
  return out;   // who answers and why is the card's own line (ROUTE_REASON), not repeated here
}

export type Mark = { op: "eq" | "ins" | "del" | "case"; text: string };

/** LCS over tokens (33.15's deterministic method — no model). `same` decides a match;
 *  a match that is not identical is a `case` mark (theirs' characters, capitals changed).
 *  ponytail: O(n·m); a clause is a few hundred words — swap for Myers if a whole
 *  annexure ever arrives as one row and this shows in a profile. */
function lcsMarks(a: string[], b: string[], same: (x: string, y: string) => boolean): Mark[] {
  const n = a.length, m = b.length;
  const lcs: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      lcs[i]![j] = same(a[i]!, b[j]!) ? lcs[i + 1]![j + 1]! + 1 : Math.max(lcs[i + 1]![j]!, lcs[i]![j + 1]!);
    }
  }
  const out: Mark[] = [];
  const push = (op: Mark["op"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.op === op) last.text += text;
    else out.push({ op, text });
  };
  let i = 0, j = 0;
  while (i < n && j < m) {
    if (same(a[i]!, b[j]!)) { push(a[i] === b[j] ? "eq" : "case", b[j]!); i++; j++; }
    else if (lcs[i + 1]![j]! >= lcs[i]![j + 1]!) push("del", a[i++]!);
    else push("ins", b[j++]!);
  }
  while (i < n) push("del", a[i++]!);
  while (j < m) push("ins", b[j++]!);
  return out;
}

/** The letters and digits of a text, lower case: two spellings that differ only in
 *  punctuation, quotes or capitals read the same. */
const bare = (text: string) => text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");

/** A word-level diff of two texts: our wording → the client's. Where a removed run and
 *  the added run beside it differ only in punctuation or capitals ("SERVICES" →
 *  "SERVICES:"), the pair is diffed by character, so only ":" is marked — never the
 *  word struck and written again. */
export function wordDiff(ours: string, theirs: string): Mark[] {
  const words = (t: string) => t.match(/\s+|[^\s]+/g) ?? [];
  const coarse = lcsMarks(words(ours), words(theirs), (x, y) => x === y);
  const out: Mark[] = [];
  const push = (m: Mark) => {
    const last = out[out.length - 1];
    if (last && last.op === m.op) last.text += m.text;
    else out.push({ ...m });
  };
  for (let k = 0; k < coarse.length; k++) {
    const m = coarse[k]!, next = coarse[k + 1];
    const pair = next && ((m.op === "del" && next.op === "ins") || (m.op === "ins" && next.op === "del"));
    if (pair && bare(m.text) && bare(m.text) === bare(next.text) && m.text.length + next.text.length < 400) {
      const [del, ins] = m.op === "del" ? [m.text, next.text] : [next.text, m.text];
      lcsMarks([...del], [...ins], (x, y) => x.toLowerCase() === y.toLowerCase()).forEach(push);
      k++;
    } else push(m);
  }
  return out;
}

/** A rewritten clause reads as two blocks, not as interleaved words: at or above this
 *  share of changed words (and a clause, not a phrase), ours above, theirs below. */
export const REWRITE_SHARE = 0.4;
const REWRITE_MIN_WORDS = 8;

/** How a change is drawn: word marks in place, or — rewritten — a replaced block. */
export function redline(ours: string, theirs: string): { replaced: boolean; marks: Mark[] } {
  const marks = wordDiff(ours, theirs);
  const count = (t: string) => t.match(/\S+/g)?.length ?? 0;
  const total = Math.max(count(ours), count(theirs));
  const kept = marks.reduce((n, m) => n + (m.op === "eq" || m.op === "case" ? count(m.text) : 0), 0);
  const replaced = !!ours.trim() && !!theirs.trim() && total >= REWRITE_MIN_WORDS
    && 1 - kept / total >= REWRITE_SHARE;
  return { replaced, marks };
}

/** Only punctuation or capitals changed — the server's own route reason, never re-read. */
export const formattingOnly = (change: ClientChange) => change.route_reason === "FORMATTING_ONLY";

/** One short line with no full stop inside: drawn as the heading it is, like the reading view. */
export const isHeading = (text: string) => !text.trim().includes("\n") && (text.match(/\S+/g)?.length ?? 0) <= 8;
