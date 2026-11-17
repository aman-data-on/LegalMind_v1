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
  PROCESSING: "Analysing",
  ANALYSIS_COMPLETE: "Analysis complete",
  LEGAL_REVIEW: "With Legal",   // PLAIN-LANGUAGE §2.2: one word for one fact
  RESOLVED: "Decided",
  CLOSED: "Closed",
  ANALYSIS_FAILED: "Analysis failed",
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

/** Asking Legal to look at a point — a request, never a decision (`EscalateControl`). */
export const ASK_LEGAL_COPY = {
  open: "Ask Legal",
  submit: "Ask Legal",
  busy: "Asking…",
  asked: "You asked Legal to look at this. Asking is not an approval — Legal decides.",
  why: "What should Legal look at?",
  withdraw: "Withdraw",
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
  prepareReply: "Prepare our reply",
  preparePackage: "Prepare final contract",
  prepareAmendment: "Prepare amendment",
  sendForSignature: "Download final contract",   // AM-318 (was "Send for signature")
  prepareFinal: "Prepare final contract",
  downloadFinal: "Download final contract",
  recordContractDecision: "Record the decision",
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
  if (code === "INTERNAL_REVIEW" && points) return `With Legal, ${plural(points, "point")}`;
  if (code === "CLIENT_RETURNED" && c?.changes_total !== undefined && !c.changes_left) {
    // N16: the primary's own words; the final contract waits on open points too
    if (c.changes_ours) return "Client replied";   // UX L12: a stage, never a sentence
    if (finalReady(c)) return "Ready for the final contract";
  }
  if (code === "INTERNAL_REVIEW" && final) return "Final contract, with Legal";   // AM-318
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
  legalDecides: "No standard covers this. Legal decides.",
  notesTitle: "Notes for Legal",
  notesHelp: "Things to check across clauses. They are not points.",
  tableButton: "Review table",
  tableTitle: "Review table of the client's changes",
  download: "Download Word file",
  tableFailed: "The review table could not be loaded",
  downloadFailed: "The Word file could not be made",
  fromStandard: "From our standard",
  standardSilent: "Our standard says nothing on this. Decide from the clause.",
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
