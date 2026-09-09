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
 * findings pane. `LEGAL_REVIEW` is not a status a lawyer recognises; "Awaiting legal
 * decision" is the same fact in their language. Locked Step 30 keeps its state names;
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

/** Review lifecycle — locked Step 30's nine states, in a reviewer's words. */
const REVIEW_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  UPLOADED: "Uploaded",
  PROCESSING: "Analysing",
  ANALYSIS_COMPLETE: "Analysis complete",
  LEGAL_REVIEW: "Awaiting legal decision",
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

/** Document processing (34.15) — a document concern, separate from the Review. */
const PROCESSING_LABELS: Record<string, string> = {
  PENDING: "Queued",
  PROCESSING: "Reading the document",
  COMPLETED: "Ready",
  FAILED: "Could not be read",
};

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
export const processingLabel = (v?: string | null) => look(PROCESSING_LABELS, v);
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
