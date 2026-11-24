/**
 * The presentation-layer vocabulary — one place, 2026-09-04.
 *
 * The API's enums are canonical and unchanged: `LEGAL_REVIEW`, `DECISION_REQUIRED`,
 * `UNABLE_TO_EVALUATE` and the rest are what the server sends, what the audit trail
 * records, and what every test asserts on. This module is the ONLY place they become
 * words for a person, and nothing here may feed a decision, a filter value or a
 * request body — it returns display strings and nothing else.
 *
 * Why it exists. The live audit found raw SCREAMING_SNAKE enums rendered straight to
 * legal professionals across the Reviews queue, the report, the Legal queue and the
 * findings pane. `LEGAL_REVIEW` is not a status a lawyer recognises; "With Legal"
 * is the same fact in their language. Locked Step 30 keeps its state names;
 * only the label changes.
 *
 * TWO DELIBERATE EXCEPTIONS, and they are the product's own vocabulary rather than
 * database leakage: `MATCH`, `DEVIATION` and `MISSING` stay exactly as they are. They
 * are the locked comparison outcomes (Step 20, `REC-02`), they appear verbatim in the
 * specification, the report, the export and every conversation the owner has about
 * this product, and renaming them would be inventing a second vocabulary for the one
 * thing the system exists to say. They are EXPLAINED instead — see `CLASSIFICATION_HELP`
 * and the glossary that renders it.
 */

import type { DealCounts, Finding, Review } from "./types";

/** Review lifecycle — locked Step 30's nine states, in a reviewer's words. */
const REVIEW_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  UPLOADED: "Uploaded",
  PROCESSING: "Being read",           // UI-09: no engine words ("analysis") for a reader
  ANALYSIS_COMPLETE: "Reading finished",   // momentary: LEGAL_REVIEW or RESOLVED follows
  LEGAL_REVIEW: "With Legal",   // PLAIN-LANGUAGE §2.2: one word for one fact
  RESOLVED: "Decided",
  CLOSED: "Closed",
  ANALYSIS_FAILED: "Could not be read",
  CANCELLED: "Cancelled",
};

/** Contract lifecycle — Step 2's Draft / Active / Superseded, DECLARED by the
 *  owner (P-1, 2026-09-06). A document axis: distinct from the Review lifecycle
 *  above and from the Dashboard's derived analysis buckets. */
const CONTRACT_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  ACTIVE: "Active",
  SUPERSEDED: "Superseded",
};

/** Finding workflow position (J-4) — not one of the five legal axes. */
const FINDING_STATUS_LABELS: Record<string, string> = {
  OPEN: "Open",
  DECISION_REQUIRED: "Needs a legal decision",
  AWAITING_CLARIFICATION: "Awaiting clarification",
  RESOLVED: "Resolved",
};

/**
 * Finding classification. The locked trio is untouched; only the engine's
 * "I could not judge this" state is put into words, because `UNABLE_TO_EVALUATE`
 * describes the engine's inability and a reader needs to know what it means FOR THEM:
 * a person has to look.
 *
 * Owner instruction, 2026-09-09: that state reads "Needs Review" (it was "NEEDS A
 * PERSON"). The enum, the audit trail and every evaluator path are untouched —
 * this is the label only. The owner also narrowed what the state should MEAN
 * ("only when the content is genuinely unclear, never a default or fallback"),
 * which is a change to the evaluator's fail-closed routing, NOT to this label,
 * and is deliberately not implemented here: rule 15 currently makes this state
 * the fail-closed destination for insufficient extraction, so narrowing it is a
 * separate, scoped change to those code paths.
 */
const CLASSIFICATION_LABELS: Record<string, string> = {
  MATCH: "MATCH",
  DEVIATION: "DEVIATION",
  MISSING: "MISSING",
  CONFLICT: "CONFLICT",
  UNABLE_TO_EVALUATE: "Needs Review",
};

/**
 * Rule Outcome — what Legal should DO, a separate axis from classification and
 * never merged with it (DECISION_STATE_MODEL). `NOT_APPLICABLE` is the one that
 * misleads on sight: it reads as "this does not apply to you", when locked Step
 * 20 r4 makes it the FAIL-CLOSED state — the engine has no ruling here, so the
 * deviation stands and a person decides. The label says that.
 */
const RULE_OUTCOME_LABELS: Record<string, string> = {
  ACCEPTABLE: "Acceptable",
  UNACCEPTABLE: "Not acceptable",
  APPROVAL_REQUIRED: "Needs approval",
  NOT_APPLICABLE: "No rule covers this",
};

/** A scope key with no label of its own — `EARLY_TERMINATION_RESTRICTION` is an
 *  identifier, not a phrase anyone reads. The raw value stays in `data-scope`,
 *  so tests and exports are unaffected. */
export function scopeLabel(scopeKey: string): string {
  const words = scopeKey.replace(/[_-]+/g, " ").trim().toLowerCase();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** Extraction outcome (45B.7). */
const EXTRACTION_LABELS: Record<string, string> = {
  COMPLETE: "Text extracted",
  PARTIAL: "Partly extracted",
  AMBIGUOUS: "Extraction ambiguous",
  FAILED: "No readable text",
};

/** An unknown value is shown as itself rather than hidden: a state we have no label
 *  for is a gap in THIS file, and silently rendering "Unknown" would hide it. */
function look(map: Record<string, string>, value: string | null | undefined): string {
  if (!value) return "—";
  return map[value] ?? value;
}

export const reviewStatusLabel = (v?: string | null) => look(REVIEW_STATUS_LABELS, v);
export const findingStatusLabel = (v?: string | null) => look(FINDING_STATUS_LABELS, v);
export const classificationLabel = (v?: string | null) => look(CLASSIFICATION_LABELS, v);
export const extractionLabel = (v?: string | null) => look(EXTRACTION_LABELS, v);
export const ruleOutcomeLabel = (v?: string | null) => look(RULE_OUTCOME_LABELS, v);

/**
 * What the comparison outcomes mean — the glossary text, in one place so the
 * findings pane, the report and any future surface cannot drift into three
 * different explanations of the same locked vocabulary.
 *
 * Wording rule (rule 12, DESIGN.md): each line states what the ENGINE found, never
 * what the reader should conclude. "Differs from" is a fact; "is unacceptable" would
 * be a legal position, and only a person holding `legal.decision` makes one.
 */
export const CLASSIFICATION_HELP: { value: string; label: string; help: string }[] = [
  {
    value: "MATCH",
    label: "MATCH",
    help: "The document's provision aligns with the company standard for this requirement.",
  },
  {
    value: "DEVIATION",
    label: "DEVIATION",
    help: "The provision is present but differs from the standard. It is not automatically unacceptable — a person decides.",
  },
  {
    value: "MISSING",
    label: "MISSING",
    help: "The requirement was expected for this document type and no provision covering it was found.",
  },
  {
    value: "CONFLICT",
    label: "CONFLICT",
    help: "Two or more provisions in the document govern the same point and contradict each other.",
  },
  {
    value: "UNABLE_TO_EVALUATE",
    label: "Needs Review",
    help: "Something in the document is not clear enough to compare — for example it states a basis the standard cannot be measured against. The engine never guesses; it hands the question to you.",
  },
];

export function contractStatusLabel(status: string | null | undefined): string {
  return (status && CONTRACT_STATUS_LABELS[status]) ?? status ?? "Status not recorded";
}

/** The three declarable states, in lifecycle order, for a select. */
export const CONTRACT_STATUSES: ReadonlyArray<{ value: string; label: string }> =
  Object.entries(CONTRACT_STATUS_LABELS).map(([value, label]) => ({ value, label }));

/** The five Legal Decisions in a reviewer's words (owner, 2026-10-21). The value sent
 *  stays the locked enum (Step 31); only the words change. */
const DECISION_LABELS: Record<string, string> = {
  // AB-103 (owner, 2026-10-22): each says what it acts on — a point is never confused
  // with the contract ("Do not sign" is the contract's; "Must change" is this clause's)
  ACCEPT_DEVIATION: "Accept as an exception (this contract only)",
  REQUIRE_COMPANY_STANDARD: "Change needed — send our wording",
  APPROVE_CUSTOMIZATION: "Approve a customised clause",
  REJECT: "Not acceptable — this clause must change",
  REQUEST_CLARIFICATION: "Ask the client to clarify",
  NOT_APPLICABLE_TO_CONTRACT: "Not applicable to this contract",
};

/** A recorded decision as the card states it — never "Acceptable" (rule 14): an accepted
 *  difference is an exception a named person allowed, on a date, for a reason. */
const DECIDED_WORDS: Record<string, string> = {
  ACCEPT_DEVIATION: "Accepted as an exception",
  REQUIRE_COMPANY_STANDARD: "Change requested — our wording to send",
  APPROVE_CUSTOMIZATION: "Customised clause approved",
  REJECT: "Must change — not acceptable as written",
  REQUEST_CLARIFICATION: "Awaiting the client's clarification",
  NOT_APPLICABLE_TO_CONTRACT: "Not applicable to this contract",
};

/** AM-174 — the decision on the whole contract, in a reviewer's words. */
export const CONTRACT_OUTCOME_LABELS: Record<string, string> = {
  SIGN_AS_IS: "Sign as is",
  SIGN_WITH_CHANGES: "Sign after our changes",
  DO_NOT_SIGN: "Do not sign",
  ON_HOLD: "On hold — waiting for the client",
};
export const contractOutcomeLabel = (v?: string | null) => look(CONTRACT_OUTCOME_LABELS, v);

/** AB-214: a long step names what it is doing (never a bare "…" for 20 seconds). */
export const CHANGES_COPY = {
  /** a Word comment's label, on a passage, a change and its answer card */
  commentFrom: (author: string) => (author ? `Comment from ${author}` : "Comment"),
  commentsLabel: "Comments on this passage",
  /** the client's comments on clauses they did not change (the list's own details) */
  commentsElsewhere: (n: number) => `Comments not tied to a change (${n})`,
  /** the Summary's detail on a marked-up copy: the tracked edits in the file, never a
   *  headline count (one change can carry many edits) */
  trackedEdits: (c: { changes: number; clauses: number; notes?: number; onto?: number; unmeasured: number }) =>
    `The client's file has ${plural(c.changes, "tracked edit")} in ${plural(c.clauses, "clause")}`
    + (c.notes ? ` and ${plural(c.notes, "comment")}` : "") + ". "
    + (c.onto ? `${c.onto} of the changed clauses ${c.onto === 1 ? "moves" : "move"} risk onto LeapSwitch; the report says how. ` : "")
    + `${c.unmeasured} of those clauses are not checked by our standard terms.`,
  /** the Changes tab's base: which of our versions the client's is compared with */
  comparedWith: (n: number) => `Compared with version ${n} (what we sent).`,
  /** ground rule 1: an answer kept from an earlier reading of the same clause */
  earlierAnswer: "Answered on an earlier reading:",
  earlierAnswerHint: "The clause was paired differently then. Answer it again to confirm.",
  preparingReply: "Preparing our reply. Step 1 of 2: writing the answers into the client's file. Step 2: checking it. About 20 seconds.",
  /** batch 8 R3d-1: the same words, only punctuation differs — still with Legal (Q4) */
  punctuationOnly: "Only punctuation changed",
  unnumbered: "Unnumbered text",
};

/** Batch 8 R2 (`AM-461`): the changes the client made with no tracked change and no
 *  highlight — first in the brief and on the Changes tab. The reply line names clauses
 *  only, never a position (LEGAL-02), and is copied by a person, never sent (Q8). */
export const NOT_MARKED_COPY = {
  title: (n: number, total: number) => `${n} of ${plural(total, "change")} not marked`,
  titleOldFile: (n: number, total: number) => `${n} of ${plural(total, "change")} not marked as tracked changes`,
  body: "The client made these without a tracked change or a highlight. LegalMind found them by comparing with what we sent.",
  bodyOldFile: "The client made these without a tracked change. LegalMind found them by comparing with what we sent. LegalMind read this file before it could see highlights.",
  more: (n: number) => `and ${n} more`,
  copy: "Copy line for the reply",
  copied: "Line copied",
  copyFailed: "The line could not be copied. Select it and copy it.",
  lineLabel: "Line for the reply",
  line: (n: number, clauses: string[]) =>
    `We compared your file with the version we sent. ${plural(n, "change")} ${n === 1 ? "is" : "are"} not marked as a tracked change: ${clauses.join(", ")}. Please mark every change, so both sides can see it.`,
  clause: (number: string | null, title: string | null | undefined, quote: string) => {
    const bare = (text: string) => text.replace(/[\s:]+$/, "");    // "Details of Services:"
    const name = bare(title ?? "");
    // no heading: the clause's own first words, so a bare "Clause 4" never stands alone
    const own = quote.split(" ").length > 6 ? `${quote.split(" ").slice(0, 6).join(" ")}…` : bare(quote);
    return number ? `Clause ${number} (${name || own})` : name || own;
  },
  /** round 2: every untracked change was highlighted — said once on the Changes tab */
  allHighlighted: (n: number, total: number) =>
    `${n} of ${plural(total, "change")} ${n === 1 ? "was" : "were"} made without a tracked change. The client highlighted ${n === 1 ? "it" : "them"}, so each is tagged "highlighted, not tracked".`,
  rowNotMarked: ", not marked",
  rowHighlighted: ", highlighted, not tracked",
} as const;

/** Batch 8 R1 (`AM-464`/`AM-465`): an earlier contract we signed or finalised with this
 *  client, beside a change or a point — information, never a decision. Named and dated. */
const PRIOR_ROW = { SAME: "Same as", CHANGED: "Changed since", NEW: "New since", IN_SIGNED: "Was in" } as const;
const ourPaper = (kind: string) => `our ${kind === "FINAL" ? "final" : "signed"} contract`;
export const PRIOR_COPY = {
  row: (state: keyof typeof PRIOR_ROW, kind: string, date: string) => `${PRIOR_ROW[state]} ${ourPaper(kind)} (${date})`,
  point: (state: string, kind: string, date: string) =>
    `${state === "SAME" ? "Same result as" : "Different from"} ${ourPaper(kind)} (${date})`,
  brief: (n: number, kind: string, name: string, date: string) =>
    // the date is never split across lines
    `${plural(n, "change")} ${n === 1 ? "was" : "were"} already in ${ourPaper(kind)} \u201c${name}\u201d (${date.replace(/ /g, "\u00a0")}).`,
  briefHint: (n: number) => `The client may say we agreed to ${n === 1 ? "this" : "these"} before. Legal still decides ${n === 1 ? "it" : "each one"}.`,
  open: (kind: string) => `Open ${ourPaper(kind).replace("our ", "the ")}`,
  uploadRole: "Signed earlier, for reference",
  uploadHint: "A contract we already signed with this client outside LegalMind. Nothing is negotiated on it.",
  filing: "Filing it as signed…",
  filed: "Filed as signed",
} as const;

/** Batch 8 R5 (`AM-467`, C-34 open): which of our standard sets measured the paper. */
const MEASURED_SET: Record<string, string> = {      // in this order: our MSA first
  OUR_MSA: "our MSA", CONSTITUTION: "our general contract terms", PUBLISHED_POLICY: "our published terms",
  OTHER_DOCUMENT: "our other agreements",
};
const KINDS = Object.keys(MEASURED_SET);
export const MEASURED_COPY = {
  line: (kinds: string[]) => {
    const sets = KINDS.filter((k) => kinds.includes(k)).map((k) => MEASURED_SET[k]!);
    const named = sets.length > 1 ? `${sets.slice(0, -1).join(", ")} and ${sets.at(-1)}` : sets[0] ?? MEASURED_SET.OTHER_DOCUMENT;
    return `Checked against our standards as ${named} ${sets.length > 1 ? "state" : "states"} them.`;
  },
  otherPaper: "Legal has not yet confirmed which of our standards apply to paper that is not an MSA.",
  detailsTitle: "Legal details: where each point's standard comes from",
  detailsRow: (name: string, points: number) => `${name}: ${plural(points, "point")}`,
  conflict: "Open question for Legal (C-34): which of our standards measure paper that is not an MSA.",
} as const;

/** `AM-411`: said on the contract-decision form while a question to the client is open. */
export const CONTRACT_DECISION_COPY = {
  waitingOnClient: "Your question to the client is still open. It goes out in our reply, so you can decide the "
    + "contract now. Sign as is opens once the client has answered.",
};

/** `AM-413`: what "Prepare final contract" makes, by the server's mode. Labels only. */
export function finalPlanText(plan: { mode: string | null; of_version?: number; agreed: unknown[]; entries?: unknown[]; annex?: 2 },
                              nextVersion: number): string {
  const checked = "It is checked like any upload. Then Legal records the decision on the contract.";
  if (plan.mode === "annex") {
    const n = plan.entries?.length ?? 0;
    return `This makes version ${nextVersion}: our contract as approved, word for word, with `
      + `${n === 1 ? "the 1 agreed change" : n ? `the ${n} agreed changes` : "no agreed changes"}`
      + `${n ? ` listed in ${plan.annex === 2 ? "Annexure 2" : "Annexure A"}` : ""}. Nothing in the body is edited. ${checked}`;
  }
  return `This makes version ${nextVersion}: a clean copy of version ${plan.of_version}`
    + `${plan.mode === "reply" ? " with every answer applied" : ""}, every tracked change accepted and every `
    + `comment removed. ${checked}`
    + (plan.mode === "copy" && plan.agreed.length === 0
      ? " Use this when the client accepted the version as it is. If they sent changes, upload their version instead." : "");
}

/** What each choice does, said before it is recorded (owner, 2026-10-22). */
export const DECISION_EFFECTS: Record<string, string> = {
  ACCEPT_DEVIATION: "Closes this point for this contract only. Our standard does not change.",
  REQUIRE_COMPANY_STANDARD: "Adds this point to the changes to send; it is checked again on the revised version.",
  APPROVE_CUSTOMIZATION: "Approves the customised wording for this contract only.",
  REJECT: "Marks this clause as not acceptable; it goes into the changes to send. It does not decide the whole contract.",
  REQUEST_CLARIFICATION: "Keeps this point open until the client answers; the contract cannot be decided meanwhile.",
  NOT_APPLICABLE_TO_CONTRACT: "Closes this point: our standard does not apply to this contract.",
};

/** Where the review stands, in a reader's words (AM-179). */
export const STAGE_LABELS: Record<string, string> = {
  SUPERSEDED: "Superseded — a newer version has been reviewed",
  ANALYSING: "Being analysed",
  ANALYSIS_FAILED: "The analysis could not be completed",
  WAITING_FOR_CLARIFICATION: "Waiting for the client's clarification",
  REOPENED: "Reopened — points need a decision again",
  WITH_LEGAL: "With Legal",
  NOT_SENT: "Not sent to Legal yet",
  CONTRACT_DECISION_PENDING: "Every point is decided — the decision on the contract is next",
  COMPLETE: "Review complete",
  NO_ISSUES: "No point needs a decision",
};

export const decisionLabel = (v?: string | null) => look(DECISION_LABELS, v);
export const decidedWords = (v?: string | null) => look(DECIDED_WORDS, v);

/** QA-037: why a file could not be read, with what to do — the server's ParseError code,
 *  said the same way on the Dashboard and in Ask. An unlisted code keeps the general text. */
export const UNREADABLE_WHY: Record<string, string> = {
  PASSWORD_PROTECTED: "This PDF is password-protected. Remove the password and upload it again.",
  MACRO_ENABLED: "This is a macro-enabled Word file. Save it as an ordinary .docx and upload "
    + "it again.",
  CORRUPT: "This file is damaged and could not be opened. Save or export it again from the "
    + "original and upload the new copy.",
  TOO_MANY_PAGES: "This PDF has more than 1,000 pages. Upload the agreement itself, without "
    + "attachments or appendices that make it this long.",
};

/* ------------------------------------------------------------------------------------
 * S1 — plain language (CLM plan, owner-approved 2026-11-03). One map for the words a
 * person reads on the contract record; every surface reads these rather than spelling
 * its own. Display strings only — nothing here feeds a request, a filter or a decision.
 * ---------------------------------------------------------------------------------- */

/** What a recorded Legal Decision did to a point, in the negotiation's own words — the
 *  second line under a point (who answers / what was answered). Never "Matches": a point
 *  closed by a decision keeps the review's word on its first line (rule 14). */
const ANSWERED_WORDS: Record<string, string> = {
  ACCEPT_DEVIATION: "Accepted theirs",
  REJECT: "Kept ours",
  REQUIRE_COMPANY_STANDARD: "Our standard",
  APPROVE_CUSTOMIZATION: "Our wording",
  REQUEST_CLARIFICATION: "Waiting for the client",
  NOT_APPLICABLE_TO_CONTRACT: "Not applicable here",
};
export const answeredWords = (v?: string | null) => look(ANSWERED_WORDS, v);

/** Who a still-open point is with — the same second line, before anyone answered. */
export const POINT_WHO = {
  yours: "Yours to decide",
  legal: "With Legal",
  /** before the owner has sent the review (AM-291 r1: never "With Legal" until it is) */
  notSent: "Not sent to Legal yet",
  approval: "Waiting for approval",
  client: "Waiting for the client",
} as const;

/** The Legal Decision control's words (`DecisionControl` reads these; its markup, its
 *  no-optimistic-UI rule and its 409 handling are untouched). */
export const DECISION_COPY = {
  reason: "Reason",
  recorded: "Your decision is recorded.",
  recordedFor: (n: number) => `Your decision is recorded for all ${n}.`,
  notEffective: " It takes effect once the client answers or a second person approves it.",
  conflict: "Someone answered this a moment ago — refresh to see it.",
  refresh: "Refresh",
} as const;

/** A server-built sentence for the Summary, with its section references taken out: the
 *  § behind our standard is a Legal detail (S1), shown on the finding's Legal details.
 *  "(Constitution §24.4, §25.1)" and "(§25.1)" go; every other word stays. */
export function withoutSectionRefs(text: string): string {
  return text.replace(/\s*\((?:Constitution\s*)?§[^)]*\)/g, "").replace(/\s+([.,;])/g, "$1");
}

/** Batch 3+4 round 3: quoted words shown to sales say "clause 7.3", never "§7.3" (§6). */
export function plainClauseSigns(text: string): string {
  return withoutSectionRefs(text).replace(/§+\s*/g, "clause ");
}

/** Asking Legal to look at a point — a request, never a decision (`EscalateControl`). */
export const ASK_LEGAL_COPY = {
  open: "Ask Legal",
  submit: "Ask Legal",
  busy: "Asking…",
  asked: "You asked Legal to look at this. Asking is not an approval — Legal decides.",
  why: "What should Legal look at?",
  withdraw: "Withdraw",
} as const;

/** UI-09: the Reviews queue — its filter says the row chips' own words (a Review's state,
 *  never a deal stage or a legal axis; "Decided" is RESOLVED, never "Matches"). */
export const REVIEWS_QUEUE_COPY = {
  filter: "Status",
  filters: [
    { id: "", text: "All" },
    { id: "LEGAL_REVIEW", text: REVIEW_STATUS_LABELS.LEGAL_REVIEW! },
    // U1 r2: no ANALYSIS_COMPLETE option — the state lasts one call
    // (`advance_after_analysis` moves it on), and "Checked" named the date column too
    { id: "RESOLVED", text: REVIEW_STATUS_LABELS.RESOLVED! },
    { id: "CLOSED", text: REVIEW_STATUS_LABELS.CLOSED! },
  ],
  columns: { document: "Contract", status: "Status", checked: "Checked" },
  emptyTitle: "No reviews here",
  emptyFiltered: "No review you can see has this status.",
  emptyAll: "A review appears once a contract is checked. Upload a contract on Contracts to start.",
  /** the row's facts line, as on Contracts: what tells one template's rows apart */
  version: (n: number, role?: string) => `Version ${n}${role ? `, ${role.charAt(0).toLowerCase()}${role.slice(1)}` : ""}`,
  withWhom: (name: string) => `With ${name}`,
} as const;

/** UI-12: the report page's own words — the server's report text is the download's. */
export const REPORT_COPY = {
  backToReviews: "Reviews",
  backToContract: "Contract",
  openContract: "Open the contract",
  /** says what the buttons download before anything downloads */
  exportLine: "The report below, as a file:",
  pdf: "Download PDF",
  word: "Download Word",
  preparing: "Preparing…",
  exportFailed: "The report could not be downloaded. Try again.",
} as const;

/** U1 r2: one name for the deal's end (AM-318) — the brief, the list and the card. */
export const FINAL_READY_WORDS = "Final contract ready";

/** U2 (UI-13): the contract's ⋯ menu — "Compare" said once per item, the file named by its type. */
export const MENU_COPY = {
  compare: "Compare two versions",
  hideCompare: "Hide version comparison",
  compareTemplate: "Compare with our template",
  /** the file is what was uploaded: its type from the file itself, never assumed; "draft"
   *  while a point is open (r4: one short line, the warning one word) */
  download: (n: number, mime: string, draft: boolean) =>
    `Download ${draft ? "draft " : ""}version ${n} (${/pdf/i.test(mime) ? "PDF" : /word|officedocument|msword/i.test(mime) ? "Word" : "file"})`,
  report: "View report",
  colleagues: "Colleagues",
} as const;

/** U2 r4: the Report view's own states (the tab shows once the report is ready). */
export const REPORT_VIEW_COPY = {
  loading: "Loading the report…",
  preparing: "Preparing the report…",
  docFailed: "The report could not be loaded",
  checking: "LegalMind is still checking this version. The report is ready when it finishes.",
  failedTitle: "This version could not be checked",
  failedBody: "There is no report for it. Upload the file again, or ask Legal.",
  noneTitle: "No report yet",
  noneBody: "A report is made once this version is checked.",
} as const;

/** U2 r4: the reply version's notice — one short line that always shows. */
export const REPLY_NOTICE_COPY = {
  label: "Our reply",
  title: (n: number, theirs?: number) => `Version ${n} is our reply to the client’s version${theirs ? ` ${theirs}` : ""}`,
  byHand: (clauses: string[]) => `Restore ${clauses.length} by hand in Word (${clauses.join(", ")}).`,
  next: "Email it to the client, then press Send our reply.",
  notSent: "Not yet sent to the client.",
  sentOn: (date: string) => `Sent to the client on ${date}.`,
} as const;

/** UI-02: taking the contract back from Legal undoes the hand-off, so it asks first. */
export const TAKE_BACK_COPY = {
  // U2 (AM-472/473, owner 2026-11-24): the lawyer gets a notice and the note is kept —
  // so the body no longer warns that they are not told or that the note goes
  open: "Take back from Legal",
  title: "Take this contract back from Legal?",
  body: (who: string) => `It leaves ${who}'s queue. Answers Legal already gave are kept. ${who} gets a notice.`,
  /** a 409: someone else changed who holds it first */
  gone: "Legal no longer has this contract. Refresh to see who has it.",
  cancel: "Cancel",
  confirm: "Take back",
  busy: "Taking back…",
  done: "Taken back from Legal",
} as const;

/** Where a deal stands (`AM-260`). The stage is the server's, and so are its words —
 *  one chip for every reader (AM-398 r2); whose turn it is is said beside the chip.
 *  Its own vocabulary: never a legal axis. */
export type StageViewer = "owner" | "legal";
const STAGE_WORDS: Record<string, string> = {
  DRAFTING: "Drafting",
  INTERNAL_REVIEW: "With Legal",
  WITH_CLIENT: "With client",
  CLIENT_RETURNED: "Client replied",
  READY_TO_SEND: "Ready to send",
  // AM-318: the deal cycle ends at the final copy; a decision on a version that is not
  // final means the final contract is next
  READY_TO_SIGN: "Ready for the final contract",
  SIGNED: "Signed",
  FINAL: "Final",
  ON_HOLD: "On hold",
};
export function stageWords(code: string, _viewer: StageViewer = "owner"): string {
  // AM-398 r2 (UX §1 S1): one chip for every reader — whose turn is said beside it
  return STAGE_WORDS[code] ?? code;
}

/* ------------------------------------------------------------------ AM-291: one vocabulary
 * Two nouns, said the same way on every screen, from the server's one `counts` object:
 * CHANGES are the client's edits in the open round, POINTS the gaps against our standard
 * still undecided. "yours / total" wherever both apply. Nothing here counts anything. */

export const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

/** One label per action, sentence case — every button and link that does the act says it
 *  in these words (home, To-do, the contract header, the Changes tab). */
export const ACTION = {
  decide: (points?: number) => (points ? `Decide ${plural(points, "point")}` : "Decide"),
  answerChanges: "Answer changes",
  /** Legal's one header action while changes wait for them (one queue, batch 1) */
  answerChangesN: (n: number) => `Answer ${plural(n, "change")}`,
  prepareReply: "Prepare our reply",
  preparePackage: "Prepare final contract",
  prepareAmendment: "Prepare amendment",
  sendForSignature: "Download final contract",   // AM-318 (was "Send for signature")
  prepareFinal: "Prepare final contract",
  downloadFinal: "Download final contract",
  recordContractDecision: "Record the decision",
  recordDecision: "Record the decision",
  startAmendment: "Start an amendment",
  sendReply: "Send our reply",
  sendToLegal: "Send to Legal",
  sendToClient: "Send to client",
  createContract: "Create the contract",
  recordSigning: "Record signing",
  uploadVersion: "Upload new version",
  reviewDecision: "Review the decision",
  seeAnswer: "See the answer",
  reviewTemplate: "Review the template",
  open: "Open",
} as const;

/** "19 of 82 changes yours" · "62 of 82 changes need Legal" · "All 82 changes answered";
 *  null when there is no round (the key is absent). `viewer` names who has the rest. */
export function changesWords(c: DealCounts | undefined, viewer: StageViewer = "owner"): string | null {
  if (c?.changes_total === undefined) return null;
  const total = c.changes_total, left = c.changes_left ?? 0, mine = c.changes_left_for_me ?? 0;
  if (!total) return "No changes from the client";
  if (!left) return total === 1 ? "The 1 change answered" : `All ${total} changes answered`;
  if (mine) return `${mine} of ${plural(total, "change")} yours`;
  return `${left} of ${plural(total, "change")} ${viewer === "legal" ? "with the deal owner"
    : left === 1 ? "needs Legal" : "need Legal"}`;
}

/** Batch 1 (c): the ONE rule for "Ready for the final contract" — every change answered,
 *  none of ours to carry back, no point left open and none waiting on the client.
 *  Absent counts fail closed. */
export function finalReady(c: DealCounts | undefined): boolean {
  return c?.changes_total !== undefined && !c.changes_left && !c.changes_ours
    && c.points_open === 0 && c.points_waiting === 0;
}

/** Points, not finding rows (AM-179): findings that share the server's `group_id` are one
 *  point, decided together — the unit the To-do and the Legal queue's header count. */
export function pointCount(rows: { finding: Pick<Finding, "id" | "group_id">; review: Pick<Review, "id"> }[]): number {
  return new Set(rows.map(({ finding, review }) => `${review.id}:${finding.group_id ?? finding.id}`)).size;
}

/** A client's closed deals, said once for both client pages: "1 final · 2 signed". */
export function closedWords(client: { final_documents?: number; signed_documents?: number }): string {
  const parts = [client.final_documents ? `${client.final_documents} final` : null,
                 client.signed_documents ? `${client.signed_documents} signed` : null].filter(Boolean);
  return parts.length ? parts.join(" · ") : "None yet";
}

/** "15 points to decide" (a holder) · "15 open points" (anyone else) · "No open points". */
export function pointsWords(c: DealCounts | undefined, viewer: StageViewer = "owner"): string | null {
  if (c?.points_open === undefined) return null;
  if (!c.points_open) return "No open points";
  return viewer === "legal" && c.points_for_me ? `${plural(c.points_for_me, "point")} to decide`
    : `${plural(c.points_open, "open point")}`;
}

/** "15 waiting for the client" — the points sent back for clarification, said the same
 *  way on the list and the Summary; null when none wait. */
export function waitingWords(n: number | undefined): string | null {
  return n ? `${n} waiting for the client` : null;
}

/** The stage chip, from the stage AND the counts the Summary shows — never contradicting
 *  them. Once every change is answered the stage names what really happens next. */
export function stageLine(code: string, c: DealCounts | undefined, viewer: StageViewer = "owner",
                          final = false): string {
  const points = c?.points_open ?? 0;
  // batch 1 (one queue): while the client's changes wait, the header's one action names
  // them ("Answer N changes"), so the chip names no second count — points stay in Summary
  if (code === "INTERNAL_REVIEW" && points && !c?.changes_left) return `With Legal, ${plural(points, "point")}`;
  // AB-213 D4/D12: the chip names the SERVER's stage — "Client replied" stays that until
  // the server moves it (the main button says what comes next)
  if (code === "INTERNAL_REVIEW" && final) {                                    // AM-318
    // D6: not "with Legal" before anyone in Legal has it
    return c?.sent_to_legal === false ? "Final contract, not sent to Legal" : "Final contract, with Legal";
  }
  return stageWords(code, viewer);
}

/** The shared states and components' own words (UX Batch 2; PLAIN-LANGUAGE.md §2.6, §5):
 *  an error says what failed and the fix, never an apology; a button is a verb. */
export const FEEDBACK_COPY = {
  retry: "Try again",
  dismiss: "Dismiss",
  defaultFix: "Check your connection and try again. If it keeps failing, tell your administrator.",
  reference: (id: string) => `Error reference for support: ${id}`,
  loading: "Loading…",
  chooseFile: "Choose file",
  chooseAnother: "Choose another file",
  dropTitle: "Drag and drop your file here",
  dropOr: "or choose one from your computer",
  fileHint: "PDF, Word, Markdown or text, up to 25 MB",
  preview: "Preview",
  preparingPreview: "Preparing preview…",
  previewFailed: "The preview could not be shown",
  downloadPdf: "Download PDF",
  downloadWord: "Download Word",
  openPdf: "Open the PDF in a new tab",
  noInlinePdf: "This browser can’t show the PDF here",
  noInlinePdfFix: "Open it in a new tab, or download it below. It is the same file.",
  close: "Close",
} as const;

/** The point-status chip's words: exactly these, on every screen (PLAIN-LANGUAGE §2.1).
 *  "Decided" is a second line beside a status, never instead of it (rule 14). */
export const STATUS_CHIP_WORDS = {
  MATCHES: "Matches",
  CHANGE_NEEDED: "Change needed",
  MISSING: "Missing",
  NEEDS_DECISION: "Needs a decision",
  IN_OUR_FAVOUR: "In our favour",
  decided: "Decided",
} as const;

/** B3 page 1: a version read before a formatting fix (`reader_outdated`) — what it means and
 *  the one way out. Nothing in a review changes; the same file comes in as a new version. */
export const READER_OUTDATED = {
  title: "This file was read before a formatting fix",
  body: "Marks such as ** or ## may show in the text. Upload the same file again as a new version to read it cleanly. Nothing in your review changes.",
};

/** S6 (`FINAL-PACKAGE-SPEC` c4): the Final card — the one file a signing tool gets, the
 *  Word copy for records, and a note for whoever sends it. Labels, never contract text. */
export const FINAL_CARD = {
  pdfForSignature: "PDF for signature",
  checking: "Checking the final contract…",
  checkFailed: "The final contract could not be checked",
  checkFailedFix: "Legal cannot record the decision until the check finishes. Try again. If it fails again, tell Legal.",
  wordCopy: "Word copy (not for signing)",
  noteTitle: "Note for whoever sends it to sign",
  copy: "Copy note",
  copied: "Note copied",
  copyFailed: "The note could not be copied. Select it and copy it by hand.",
  noteLoading: "Reading the PDF for the note…",
  noteFailed: "The note could not be made",
  preview: "The final contract, as the signing tool will get it",
} as const;

/** The note's text, from the server's facts only (S6). Exported for the test. */
export function signingNoteText(n: {
  contract_name: string | null; doc_id: string | null; pages: number;
  signature_page: number | null; pdf_sha256: string;
  signers: { party: string; name: string; designation: string; email: string }[];
  filled_since_client_saw?: { label: string; value: string }[];
}): string {
  const where = n.signature_page ? `page ${n.signature_page} of ${n.pages}` : "the signature page";
  const filled = n.filled_since_client_saw ?? [];
  return [
    `Contract: ${n.contract_name ?? "this contract"}`,
    ...(n.doc_id ? [`Document ID: ${n.doc_id}`] : []),
    `Pages: ${n.pages}. Signatures go on ${where}.`,
    ...(n.signers.length ? ["Signers:", ...n.signers.map(
      (s) => `- ${s.party}: ${[s.name, s.designation, s.email].filter(Boolean).join(", ")}`)] : []),
    // B5: what the client has not seen filled in — checked with them before signing
    ...(filled.length ? ["Filled since the client last saw it:", ...filled.map((f) => `- ${f.label}: ${f.value}`)] : []),
    "Sign the PDF, not the Word file.",
    `Leegality: place the signatures on ${where}, not the default bottom-left of every page. That spot holds the document ID.`,
    `PDF SHA-256: ${n.pdf_sha256}`,
  ].join("\n");
}

/** S5 (`FINAL-PACKAGE-SPEC` d3): converting the client's paper to ours. Labels only. */
export const CONVERT_COPY = {
  title: "Convert to our paper",
  carryOver: "Only the points you accepted carry over; the rest of their paper does not.",
  lead: "Fill in our contract for this client. The points you accepted go into Annexure 2 word for word.",
  start: "Fill in our contract",
  checking: "Checking what carries over…",
  failed: "The conversion could not be checked",
  blocked: "It can be converted once these are sorted:",
  carried: (n: number) => `${n === 1 ? "1 point carries" : `${n} points carry`} over:`,
  addAfter: "Add it after clause",
  choose: "Choose a clause",
  convert: "Convert to our paper",
  converting: "Converting…",
  done: "Our paper is ready as a new version",
} as const;

/** Step 0 (owner, 2026-11-16): where a point came from — the client's change first. */
export const ORIGIN_LABELS: Record<string, string> = {
  CLIENT_CHANGED: "The client changed this",
  ALREADY_OURS: "Already in our MSA",
};
export const ORIGIN_RANK: Record<string, number> = { CLIENT_CHANGED: 0, ALREADY_OURS: 2 };

/** R2: a changed clause as a lawyer reads it. */
export const LAWYER_COPY = {
  pointsTitle: "What the client changed, point by point",
  standardsFrom: "Our standards it touches",
  topicFrom: "Topic from the heading",
  notesTitle: "Notes for Legal",
  notesHelp: "Things to check across clauses. They are not points.",
  tableButton: "Open review table",
  tableTitle: "Review table of the client's changes",
  download: "Download Word file",
  tableFailed: "The review table could not be loaded",
  downloadFailed: "The Word file could not be made",
  fromStandard: "From our standard",
  /** U2 (UI-07): said ONCE on the card when no standard applies */
  standardSilent: "No standard covers this clause. Decide from the wording.",
  measuredBy: "Measured against",
  goTo: "Go to",
} as const;

/** R3 step 10 (owner, 2026-11-16): Legal's four verdicts on a client change, each made
 *  with the answers and decision forms that already exist (`verdictsFor`). */
export const VERDICT_LABELS = {
  accept: "Accept",
  accept_changes: "Accept with changes",
  reject: "Reject",
  ask_client: "Ask the client",
} as const;
export const VERDICT_COPY = {
  rejectWith: "Send back",
  condition: "Condition",
  conditionHelp: "Only Legal sees it, unless you share it.",
  share: "Share the condition with sales",
  conditionKept: "Accepted with changes. The condition is with Legal.",
  askHelp: "Our reply keeps their wording and asks your question as a comment on this change.",
  askLabel: "Question to the client",
} as const;

/** R3: the deal owner's words for who has each change, and the deal's one status line. */
export const SALES_LINE = {
  withLegal: "With Legal: nothing for you",
  forLegal: "Legal answers this",
  sendToLegal: "Your turn: send the client's changes to Legal.",
  legalAnswered: "Legal answered",
  yourTurn: "Your turn",
  ready: "Ready to send the reply",
  waitingLegal: "With Legal: nothing for you right now. We will show you when it is your turn.",
  otherTopic: "Other changes",
} as const;
export const POINT_KIND_LABELS: Record<string, string> = {
  CHANGED: "Changed", ADDED: "Added", REMOVED: "Removed",
};
export const PARTY_LABELS: Record<string, string> = {
  LEAPSWITCH: "LeapSwitch", CLIENT: "the client", BOTH: "both sides",
};
export const MUTUALITY_LABELS: Record<string, string> = {
  MADE_MUTUAL: "Now applies to both sides",
  ONE_SIDED_ONTO_LEAPSWITCH: "One-sided: binds LeapSwitch",
  ONE_SIDED_ONTO_CLIENT: "One-sided: binds the client",
  MIXED: "Binds each side in different points",
};

/** Owner's rule of 2026-11-16: Legal reopens a change accepted automatically. */
export const REOPEN_COPY = {
  title: "Accepted automatically — better or no change for us",
  reason: "Why you reopen it",
  button: "Reopen and keep our wording",
} as const;

/** Batch 3+4 (AB-218): ONE label per change row, for this reader. Legal's own
 *  tie ("what we told them") is a label only — never a decision, never "Matches". */
export const ROW_STATUS = {
  beyond: "Goes further than we told them",
  asTold: "As we told them",
  needsYou: "Needs your answer",
  withLegal: "With Legal",
  yours: "Yours to answer",
  waiting: "Waiting for approval",
  answered: (what: string) => `Answered: ${what}`,
} as const;

/** Batch 3+4: the one-minute brief above the contract's tabs. Plain words for sales: no
 *  clause signs, codes or engine words (PLAIN-LANGUAGE §2). */
/** The Summary tab (W1-5). */
export const SUMMARY_COPY = { loading: "Loading the summary…" } as const;
/** The contract text (W1-3 r2): the rest of a long document loads after its first page. */
export const DOCUMENT_COPY = {
  loadingRest: "Loading the rest of the document…",
  restFailed: "The rest of the document could not be loaded",
} as const;

export const BRIEF_COPY = {
  title: "Deal brief",
  showAll: "Show the whole brief",
  showLess: "Show less",
  /** U2 (UI-03/35): the brief opens beside the contract, never above it */
  open: "Open the brief",
  /** U2 r4: the header row says the sentence without the stage words the badge beside it
   *  already says ("With Legal: …" → "55 changes are being answered. …"); the panel keeps it whole */
  withoutStage: (status: string) => {
    const rest = status.replace(/^(With Legal|Your turn|Not sent to Legal yet|With the client|On hold): /, "");
    return rest.charAt(0).toUpperCase() + rest.slice(1);
  },
  ownerLabel: "Owner:",
  assignFailed: "Who has this contract could not be loaded.",
  /** U2 r4: the panel's own name — the word the button says */
  panelTitle: "Brief",
  /** the phone's narrow button; its accessible name stays `open` */
  openShort: "Brief",
  close: "Close the brief",
  whoHasIt: "Who has it",
  withSince: (who: string, date: string) => `With ${who} since ${date}`,
  yourNote: "Your note to Legal",
  yourNoteTaken: (date: string) => `Your note to Legal (taken back ${date})`,
  /** U2 r2: a note someone else sent (a contract transferred since) */
  noteFrom: (who: string) => `Note to Legal from ${who}`,
  noteFromTaken: (who: string, date: string) => `Note to Legal from ${who} (taken back ${date})`,
  earlierNotes: (n: number) => `Earlier notes (${n})`,
  noteSent: (who: string, date: string) => `Sent to ${who} on ${date}`,
  lastNoteFilled: "Your last note is filled in. Change it if you need to.",
  madeFrom: (template: string, version: number, withdrawn: boolean) =>
    `Made from ${template}, version ${version}${withdrawn ? ", a template that has since been withdrawn" : ""}`,
  loading: "Loading the deal brief…",
  failed: "The deal brief could not be loaded",
  asks: "What the client asks for",
  asksMore: (n: number) => `and ${n} more`,
  /** U2 (UI-35): "and N more" opens the Changes tab */
  asksMoreLink: (n: number) => `and ${n} more on the Changes tab`,
  removes: "removes",
  told: "What we told them",
  toldOn: (date: string) => `Told on ${date}`,
  mistake: "Our own mistake",
  startHere: (n: number) => `Start here: ${plural(n, "change")} ${n === 1 ? "goes" : "go"} further than what we told them`,
  asTold: (n: number) => `${plural(n, "change")} as we told them`,
  notDiscussed: (n: number) => `${plural(n, "change")} not discussed`,
  comments: (clauses: string[]) => `Client comments: ${clauses.join(", ")}`,
  wholeContract: "Whole contract",
  /** round 4: Legal's line under a whole-contract point — candidates, never its place */
  possiblyIn: (clauses: string[]) =>
    `Possibly in: clause ${clauses.slice(0, 4).join(", ")}${clauses.length > 4 ? ` and ${clauses.length - 4} more` : ""}`,
  noteFromOwner: "Note to Legal from the owner",
  add: "Add what we told them",
  addFromNote: "Add from this note",
  edit: "Edit",
  withdraw: "Withdraw",
  save: "Save what we told them",
  saving: "Saving…",
  stale: "The brief could not be updated. It may be out of date.",
  retry: "Try again",
  saved: "Saved what we told them",
  withdrawn: "Withdrawn",
  textLabel: "What we told the client (Legal's words, at most 500 characters)",
  dateLabel: "Told on (optional)",
  cancel: "Cancel",
} as const;

/** Batch 3+4: Legal ties a change to what we told the client — the answer card. */
export const TIE_COPY = {
  title: "What we told them",
  position: "Which of what we told them",
  asTold: "As we told them",
  beyond: "Goes further than we told them",
  save: "Save the label",
  remove: "Remove the label",
  saved: "Label saved",
  removed: "Label removed",
  why: "Prepared from what we told them",
} as const;

/** Batch 3+4: the answer card's detail lines (the row says ONE status). */
export const CARD_COPY = {
  standard: "Our standard",
  covers: "Our standard covers this clause",
  forUs: "For us",
  change: "The change",
  moved: ", also moved",
  who: "Who answers",
  loading: "Loading what we told them…",
  noneTold: "Nothing is recorded yet. Add what we told them in the deal brief.",
  choose: "Choose one",
} as const;

/** Batch 3+4 round 2: the brief's status line for each of the server's codes (rule 18:
 *  the server decides who acts next; these are only its words). Arguments: the changes
 *  waiting for Legal, the reader's own, the open points — the one count. */
const are = (n: number) => (n === 1 ? "is" : "are");
/** round 3 (D1): an open point is never hidden from sales — said beside the changes */
const andPoints = (p: number) => (p ? ` ${plural(p, "point")} ${p === 1 ? "needs" : "need"} Legal too.` : "");
export const BRIEF_STATUS: Record<import("@/lib/dealBrief").BriefStatus, (legal: number, mine: number, points: number) => string> = {
  NOT_SENT: (n, _m, p) => `Not sent to Legal yet: ${plural(n, "change")}${p ? ` and ${plural(p, "point")}` : ""} ${n + p === 1 ? "needs" : "need"} Legal. Send it to Legal.`,
  WITH_LEGAL: (n) => `With Legal: ${plural(n, "change")} ${are(n)} being answered. Nothing for you yet.`,
  WITH_LEGAL_AND_YOURS: (n, m) =>
    `With Legal: ${plural(n, "change")} ${are(n)} being answered. Meanwhile, ${plural(m, "change")} ${are(m)} yours to answer.`,
  YOURS_TO_ANSWER: (_n, m, p) => `Your turn: ${plural(m, "change")} to answer.${andPoints(p)}`,
  POINTS_OPEN: (_n, _m, p) => `With Legal: every change is answered. ${plural(p, "point")} ${are(p)} still being decided.`,
  SEND_POINTS_TO_LEGAL: (_n, _m, p) => `${plural(p, "point")} ${p === 1 ? "needs" : "need"} Legal. Send it to Legal.`,
  SEND_REPLY: () => "Your turn: Legal answered every change. Send our reply.",
  /** no change of this round went to Legal: never "Legal answered" */
  ALL_ANSWERED: () => "Your turn: every change is answered. Send our reply.",
  REPLY_READY: () => "Your turn: our reply is ready. Send it to the client.",
  WITH_CLIENT: () => "With the client: we are waiting for their reply.",
  LEGAL_QUEUE: (n, _m, p) => `${plural(n, "change")} to answer, ${plural(p, "point")} to decide.`,
  LEGAL_POINTS: (_n, _m, p) => `${plural(p, "point")} to decide.`,
  LEGAL_NOTHING: () => "Nothing is waiting for Legal on this contract.",
  /** round 5: no analysed review of the client's version yet — nothing is ready */
  CHECKING: () => "LegalMind is still reading the client's version.",
  /** UI-01: stages with no reply to send — the deal's end (AM-318), the final contract
   *  next, or waiting on the client. Never a decision: the stage is the server's. */
  FINAL_READY: () => `${FINAL_READY_WORDS}. Sign it in your signing tool.`,
  PREPARE_FINAL: () => "Your turn: prepare the final contract.",
  ON_HOLD: () => "On hold: waiting for the client.",
};

/** Batch 7 (AB-220): the New contract intake — four steps, the Client details card (Legal's
 *  ten items, certificate first), the side panel. Checklist states are not point statuses:
 *  they never use the StatusChip's words. Presentation only — every state is the server's. */
export const INTAKE_COPY = {
  steps: ["Template and client", "Client details", "This deal", "Review and create"] as const,
  stepOf: (n: number) => `Step ${n} of 4`,
  added: (done: number, of: number) => `${done} of ${of} added`,
  answered: (done: number, of: number) => `${done} of ${of} answered`,
  back: "Back",
  continue: "Continue",
  // step 1
  whatTitle: "What are you making?",
  fromLine: "From Leapswitch Networks Pvt. Ltd., for every brand.",
  whoTitle: "Who is it with?",
  whichCompany: "Which company is it from?",
  whichOne: (docType: string) => `Which ${docType}?`,
  ourTemplate: "Our template",
  linkGone: "That template is not published any more. Choose one below.",
  awaiting: (docType: string) => `A new ${docType} is awaiting approval.`,
  uploadInstead: "Upload a contract",
  starting: "Starting",
  search: "Search your clients",
  recent: "Recent clients",
  detailsMissing: (n: number) => (n ? `${plural(n, "detail")} to add` : "Details on file"),
  addNamed: (name: string) => `Add “${name}” as a new client`,
  addNew: "Add a new client",
  addTitle: "New client",
  addName: "Company name",
  addHelp: "Only the name now. The next step asks the rest, starting with the GST certificate.",
  add: "Add client",
  cancel: "Cancel",
  noClients: "You have no clients yet.",
  clientsFailed: "Your clients could not be loaded. Type to search again.",
  noMatch: (q: string) => `No client named “${q}” among yours.`,
  change: "Change",
  chooseFirst: "Choose the contract and the client first.",
  panelLead: "Legal needs these from the client before the contract is made. You add them in the next step.",
  forUs: (label: string) => (/\bus\b/.test(label) ? label : `${label}, for us`),
  dealComplete: "Every answer for this deal is in.",
  detailsTab: "Details",
  noTemplate: "No contract template is published yet.",
  noTemplateFix: "Upload the client's paper instead, or ask Legal to publish one.",
  approved: (version: number) => `Version ${version}, approved by Legal`,
  // step 2: the card
  title: "Client details",
  lead: (client: string) => `Legal needs these before the contract is made. They are saved on ${client}'s profile for next time.`,
  groups: { certificate: "From the GST certificate", more: "Also needed", signs: "Who signs for them", check: "Check against the government records" },
  upload: "Upload the client's GST certificate",
  uploadHint: "PDF, JPG or PNG, under 25 MB",
  reading: "Reading the certificate",
  filed: (name: string, when: string) => `${name}, added ${when}`,
  replace: "Replace file",
  readResult: (n: number) => (n ? `Read ${plural(n, "detail")} from it. Check them below.` : "Nothing could be read from this file. Type the details below."),
  confirmAll: (n: number) => (n === 1 ? "This detail is correct" : `These ${n} details are correct`),
  marker: "Read from the certificate. Check it.",
  fromDraft: "From this draft. Check it.",
  readState: "Read from the certificate",
  fromCertificate: "From the certificate",
  groupDone: "Complete",
  dealAsks: (labels: string[]) => (labels.length
    ? `This deal asks: ${labels.slice(0, 5).join(", ")}${labels.length > 5 ? `, and ${labels.length - 5} more` : ""}.`
    : "This deal asks nothing more."),
  gstinUnreadable: "The GST number on the certificate could not be read. Type it from the certificate.",
  countryIndia: "India rules apply: the CIN, GST number and certificate are needed.",
  countryChoose: "Choose the country",
  onFileRow: "On file",
  confirm: "Confirm",
  differs: (v: string) => `Certificate says ${v}`,
  useThis: "Use this",
  tradeName: (v: string) => `Trade name on the certificate: ${v}`,
  derived: (pan: string, state: string | undefined) => `PAN ${pan}${state ? `. Registered in ${state}` : ""}.`,
  fields: {
    gstin: { label: "GST number", help: "15 characters, for example 27ABCDE1234F1Z5" },
    legal_name: { label: "Legal name", help: "As on the GST certificate" },
    registered_office: { label: "Registered address", help: "As on the GST certificate" },
    registered_email: { label: "Registered email", help: "As on the GST certificate" },
    cin_or_llpin: { label: "CIN", help: "For Indian companies. 21 characters, for example U72900MH2010PTC123456" },
    line_of_business: { label: "Line of business", help: "What the client does, in the words the contract uses" },
    signatory_name: { label: "Name", help: "The person who signs for the client" },
    signatory_designation: { label: "Designation", help: "For example, Director" },
    signatory_email: { label: "Official email", help: "Where the signing tool sends the contract" },
    authority_reference: { label: "Authority to sign", help: "Optional. For example, a board resolution or letter of authority, with its date" },
    country: { label: "Country", help: "Where the company is registered" },
  } as Record<string, { label: string; help: string }>,
  /** the panel's names for Legal's ten items, in Legal's order */
  items: {
    agreement_date: "Agreement date", registered_email: "Registered email", registered_office: "Registered address",
    cin: "CIN", business: "Line of business", signatory_name: "Signatory's name",
    signatory_designation: "Signatory's designation", signatory_email: "Signatory's official email",
    gstin: "GST number", gst_certificate: "GST certificate",
  } as Record<string, string>,
  status: { done: "Added", missing: "Not filled yet", not_needed: "Not needed", fix: "Check this", refused: "Needed to create" },
  problems: {
    bad_format: "This is not in the right format.",
    pan_mismatch: "The PAN inside this GST number is not the client's PAN.",
    pan_bad_format: "The PAN on file is not in the right format.",
  } as Record<string, string>,
  warnings: {
    state_differs: (g: string, o: string) => `The GST number is registered in ${g}, but the address names ${o}. Check both against the certificate.`,
    state_unreadable: "The address does not name a state. Check it against the certificate.",
    act_wording: (y: number) => `The CIN shows ${y}, but the contract says Companies Act, 2013. Legal to confirm the Act wording.`,
    name_differs: (c: string, p: string) => `The certificate says ${c}, but the profile says ${p}.`,
  },
  abroad: "Not needed for a company outside India.",
  readOnly: "Only someone who can edit this client can change these details.",
  copy: (label: string) => `Copy ${label}`,
  copied: "Copied",
  saving: "Saving",
  saved: "Saved",
  saveFailed: "Not saved. Check this field and try again.",
  gstLink: "Search the taxpayer on the GST portal (opens in a new tab)",
  mcaLink: "View company data on MCA (opens in a new tab)",
  tick: "I checked the legal name, address and email against the GST certificate and the GST and MCA records.",
  markChecked: "Mark as checked",
  checkedBy: (who: string, when: string) => `Checked by ${who}, ${when}.`,
  tickFirst: "Add the legal name, registered email, address, CIN, GST number and certificate first.",
  checkLine: "Checked against the government records",
  notChecked: "Not checked yet",
  addedNotChecked: (done: number, of: number) => `${done} of ${of} added. Not checked yet`,
  clientOpen: (n: number) => `Client details: ${plural(n, "detail")} to add`,
  companyGroup: "The company",
  asRegistered: "As registered",
  certNoInline: "Open it larger to read it and download it.",
  onFile: "Client details on file",
  edit: "Edit",
  // the panel
  tabs: { needed: "Still needed", certificate: "Certificate", contract: "Contract" },
  dealTitle: "This deal",
  checksTitle: "Checks",
  nothingLeft: "Nothing is left to fill in.",
  noCertificate: "No certificate yet. Upload it in Client details.",
  viewLarger: "View larger",
  certFailed: "The certificate could not be shown",
  // step 4
  refusedTitle: "The contract cannot be created yet",
  refusedLead: "Finish these first:",
  goTo: "Go to it",
} as const;

/** Batch 5 (AB-221): "Our contract came back marked up" — the start, its refusals, and the
 *  Changes tab when we compare with the client's tracked changes only. Labels only: the
 *  server decides every refusal and every row. */
export const RETURNED_COPY = {
  choose: "Our contract came back marked up",
  chooseLine: "The client’s Word file with their tracked changes",
  uploadLine: "The client’s own paper, or a draft of ours not yet sent",
  title: "Our contract came back marked up",
  lead: "Upload the client’s Word file. We show each change they made and who answers it.",
  dealTitle: "Which deal is it?",
  newDeal: "It’s not in LegalMind yet",
  newDealLine: "We start a new deal with this client.",
  /** a new deal's name (round 2, UI 4): its type, the client and the day — told apart in every list */
  dealName: (type: string | null, client: string, day: string) => `${type ?? "Contract"} with ${client}, ${day}`,
  noDeals: "No deals with this client yet. We’ll start a new one.",
  dealsFailed: "Deals could not be loaded",
  dealsFailedFix: "Try again, or start a new deal.",
  moreDeals: "Show more deals",
  /** a deal line 2: its type, the stage's own words, whose the latest version is, when it last changed */
  dealLine: (type: string | null, stage: string | null, n: number | null, role: string | null | undefined,
             changed: string) =>
    [type, stage, n === null ? null : `Version ${n}${role === "COMPANY_DRAFT" ? " is ours"
      : role === "CLIENT_MODIFIED" ? " is the client’s" : ""}`, changed ? `Last changed ${changed}` : null]
      .filter(Boolean).join(". ") + ".",
  /** UI 3: the deals that cannot take the file now, in one closed list */
  closedDeals: (n: number) => `${n} ${n === 1 ? "deal" : "deals"} can’t take this file now`,
  dealOpen: "These deals are waiting on an answer first. Open one to see where it stands.",
  openDeal: "Open the deal",
  fileTitle: "The file they sent back",
  fileHint: "A Word file, up to 25 MB",
  pickTitle: "Choose or drop the client’s Word file",
  baseTitle: "Do you have the copy we sent?",
  copyYes: "Yes, I have the copy we sent",
  copyYesLine: "Best: we also find edits the client made without tracking.",
  copyTitle: "The copy we sent",
  copyHint: "The Word file we emailed to the client",
  copyTracked: "This copy still has tracked changes. We read it with every change accepted. If that is not what we sent, fix it in Word first.",
  copyNo: "No, use the client’s tracked changes only",
  copyNoLine: "Edits made without tracking can’t be seen, and every tracked change is read as the client’s. Use this only if the copy we sent had no tracked changes.",
  existingBase: "We compare it with the last version of ours on this deal.",
  whatNext: "What happens next",
  next: ["We read the client’s changes and comments.", "You answer the simple ones.",
         "You send the rest to Legal."] as const,
  nothingSent: "Nothing goes to the client until you send our reply.",
  submit: "Upload and compare",
  busy: "Uploading…",
  busyCheck: "Checking…",
  retry: "Try again",
  resumeCopyIn: "The copy we sent is saved. Try again to add the client’s file.",
  missing: { client: "Choose the client first.", deal: "Choose the deal.", file: "Choose the file the client sent back.",
             copy: "Choose the copy we sent." },
  /** S8: the real step, never a percent */
  step: (n: number, of: number, what: "copy" | "theirs" | "check") =>
    `Step ${n} of ${of}. ${what === "copy" ? "Uploading and reading the copy we sent"
      : what === "theirs" ? "Uploading and reading the client’s file" : "Checking against our standards"}`,
  // refusals
  pdf: "This is a PDF. Ask the client for the Word file. We need it to see their tracked changes and to send our reply.",
  pdfWayOn: "If it is the client’s own paper, not ours, upload it as their paper instead.",
  pdfUpload: "Upload as their paper",
  copyWord: "The copy we sent must be the Word file. Its figures become our starting point.",
  same: "This is the same file as the copy we sent. Choose the file the client sent back.",
  noTracked: "The client’s file has no tracked changes. To see what they changed, choose the copy we sent.",
  gone: "We can’t find this deal any more. Choose another deal or start a new one.",
  closed: "This deal is archived or signed, so it can’t take a new version. Choose another deal or start a new one.",
  duplicate: "This file is already on the deal, so there is nothing new to compare.",
  failed: "The file could not be uploaded",
  // the Changes tab
  banner: "Compared with the client’s tracked changes only. We don’t have the copy we sent, so edits made without tracking can’t be seen. Every tracked change is read as the client’s.",
  oursLabel: "Before the client’s tracked changes",
  legend: "We compare with the text under the client’s tracked changes.",
  /** item 12: Legal's line where Keep our wording is withheld (AM-459, Q2) */
  keepOff: "Keep our wording is off here: Legal is deciding whether we can send back the text from before the client’s changes. Use our standard wording or write new wording instead.",
  noChanges: "The client’s file has no tracked changes to answer.",
  /** S5: under "Our draft" in Upload a contract */
  ourDraftHint: "Did our contract come back with the client’s tracked changes?",
  ourDraftLink: "Use “Our contract came back marked up”",
};
