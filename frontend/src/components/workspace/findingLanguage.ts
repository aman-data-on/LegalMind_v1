/**
 * The Finding, in a reader's language — owner request, 2026-09-08.
 *
 * A Sales or Customer Success reader opens a review and has to answer four
 * questions in seconds: what was checked, what does the document say, what does
 * our standard expect, and does someone need to act. The card they were given
 * answered none of them in words they use. It said `RESIDUALS-NDA-001`,
 * `MISSING`, `No rule covers this`, `Found in contract: ABSENT`,
 * `Comparison: presence`, `PRESENCE-v1 · 0 evidence references` — every one of
 * which is either an identifier, an enum or an evaluator's internal note.
 *
 * ── THE RULE THIS MODULE OBEYS ────────────────────────────────────────────
 * Every string it returns is built from a field the server actually sent. It
 * invents no legal content, no explanation of what a clause MEANS, no severity
 * and no recommendation (rules 7, 12, 21). Where the data does not support a
 * statement, the statement is omitted — never guessed and never softened into a
 * vague one. `null` is a valid, useful answer here.
 *
 * The canonical vocabulary is untouched: `MATCH`, `DEVIATION`, `MISSING`,
 * `CONFLICT`, `UNABLE_TO_EVALUATE`, the four Rule Outcomes and the Finding
 * statuses remain exactly what the API sends, what the audit trail records and
 * what `lib/labels.ts` renders as chips. This module adds a SENTENCE beside the
 * chip; it never replaces the chip and never feeds a filter, a request body or
 * a decision.
 */

import { DOCUMENT_TYPES } from "@/lib/documentTypes";
import { classificationLabel } from "@/lib/labels";
import type { Evaluation, Evidence, Finding } from "@/lib/types";

/** The ten declared document-type codes, as a set — so the title parser below
 *  strips `NDA` from a requirement code without a second hard-coded list. */
const TYPE_CODES = new Set(DOCUMENT_TYPES.map((t) => t.code));

/**
 * A requirement's title in words.
 *
 * The ratified standards carry no `name` of their own — `tools/import_ratified_
 * standards.py` falls back to `name = code`, so every requirement in the live
 * database is named after its own identifier. The old heading noticed the two
 * were equal and ran the code through a generic label helper, which produced
 * "Residuals nda 001": the document-type token and the sequence number rendered
 * as if they were words.
 *
 * So the code is parsed rather than prettified. `RESIDUALS-NDA-001` →
 * "Residuals"; `CONF-SURVIVAL-NDA-001` → "Conf survival";
 * `EARLY-TERM-RESTRICTION-MSA-001` → "Early term restriction". A real `name`,
 * whenever configuration starts carrying one, wins outright — this is the
 * fallback, not the preference.
 */
/** The abbreviations our own requirement codes use, spelt out. These name the
 *  clause type the way `CLAUSE_CATALOGUE.md` does ("GOVLAW" is the governing-law
 *  clause); they carry no legal position, so this is presentation, not
 *  configuration. A code that uses none of them is unaffected. */
const CODE_WORDS: Record<string, string> = {
  GOVLAW: "governing law",
  CONF: "confidentiality",
  LIAB: "liability",
  TERM: "termination",
  AUTORENEW: "auto-renewal",
  IP: "IP",
  KYC: "KYC",
  CARVEOUTS: "carve-outs",
  CARVEOUT: "carve-out",
  NON: "Non",
};

export function requirementTitle(
  requirement: { code?: string | null; name?: string | null } | null | undefined,
): string {
  const name = requirement?.name?.trim();
  const code = requirement?.code?.trim();
  if (name && name !== code) return name;
  if (!code) return "Requirement";
  const words = code
    .split(/[-_\s]+/)
    .filter((part) => part.length > 0)
    // A trailing sequence number and the document-type token are addressing,
    // not meaning. Everything else is the requirement's own words.
    .filter((part) => !/^\d+$/.test(part))
    .filter((part) => !TYPE_CODES.has(part.toUpperCase()))
    .map((part) => CODE_WORDS[part.toUpperCase()] ?? part.toLowerCase());
  if (words.length === 0) return code;
  // "Non" joins its neighbour with a hyphen ("Non-solicit"); everything else
  // with a space. Acronyms in CODE_WORDS keep their case.
  const sentence = words.join(" ").replace(/\bNon /g, "Non-");
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

/**
 * The document-type family a requirement's code declares — "MSA", "TOS", "NDA".
 *
 * `requirementTitle` strips this token deliberately: it is addressing, not
 * meaning, and a reader does not want "Auto renewal MSA" on every card. But two
 * standards in DIFFERENT families reduce to the SAME title, and since `AM-51`
 * (applicability by CONTENT) both are measured against one document — so the
 * MSA in the owner's screenshot carried two cards both headed "Auto-renewal":
 * `AUTORENEW-MSA-001`, a 6-month renewal-term comparison, and
 * `AUTORENEW-TOS-001`, a presence check. Two real requirements, one title,
 * which reads as a duplicate.
 *
 * This is the honest distinguisher, used ONLY where titles actually collide
 * (see `collidingTitles`), so the 2026-09-08 decision to keep requirement codes
 * out of the card header stands everywhere else.
 */
export function requirementFamily(
  requirement: { code?: string | null } | null | undefined,
): string | null {
  const parts = requirement?.code?.trim().split(/[-_\s]+/) ?? [];
  return parts.map((part) => part.toUpperCase()).find((part) => TYPE_CODES.has(part)) ?? null;
}

/**
 * Titles carried by more than one of the findings on screen. A card qualifies
 * its heading only when it is in this set — a distinction is worth showing
 * exactly when there is something to distinguish it from.
 */
export function collidingTitles(
  findings: Array<{ requirement: { code?: string | null; name?: string | null } }>,
): Set<string> {
  const seen = new Set<string>();
  const twice = new Set<string>();
  for (const finding of findings) {
    const title = requirementTitle(finding.requirement);
    if (seen.has(title)) twice.add(title);
    seen.add(title);
  }
  return twice;
}

/** What the outcome means for the reader, in one sentence. The chip beside it
 *  still carries the canonical word. */
const CLASSIFICATION_SENTENCES: Record<string, string> = {
  MATCH: "The document matches what the company standard expects.",
  DEVIATION:
    "The document covers this, but not in the way the company standard expects.",
  MISSING: "The expected requirement was not found in the document.",
  CONFLICT:
    "Two or more provisions in the document contradict each other on this point.",
  UNABLE_TO_EVALUATE:
    "There is not enough reliable information to tell whether this requirement is met.",
};

export function classificationSentence(classification: string): string | null {
  return CLASSIFICATION_SENTENCES[classification] ?? null;
}


/**
 * The status a reader sees — owner instruction, 2026-09-08 (fifth pass): three
 * words, for a Sales user who has to know in one glance whether anything is
 * expected of them.
 *
 *   ACCEPTED      MATCH — matches the company standard.
 *   NOT ACCEPTED  a clear, evidence-supported conflict: the approved rule's
 *                 own UNACCEPTABLE on a DEVIATION or MISSING, or an explicit
 *                 Constitution citation (owner's FINAL decision, 2026-09-09).
 *   NEEDS REVIEW  everything a person must judge — an unruled deviation or
 *                 absence, CONFLICT, UNABLE_TO_EVALUATE. Never a rejection.
 *
 * Presentation only. The four classifications, the Rule Outcomes and the
 * Finding statuses stay exactly what the API sends; they render inside "How
 * this was determined". Every surface that shows a Finding's status goes
 * through this function — one vocabulary (rule 12), never a second one.
 */
export type UserStatus = "ACCEPTABLE" | "NEEDS_DECISION" | "REQUIRES_MODIFICATION";

export const USER_STATUS_LABELS: Record<UserStatus, string> = {
  ACCEPTABLE: "Acceptable",
  REQUIRES_MODIFICATION: "Requires modification",
  NEEDS_DECISION: "Needs a decision",
};

/**
 * The fixed order the three words are shown in, everywhere they appear as a
 * sequence, and the tone each one wears — owner instruction, 2026-09-09:
 *
 *   Acceptable             green   the clause matches the company standard
 *   Requires modification  amber   it deviates, or a required clause is absent
 *   Needs a decision       red     acceptance cannot be determined at all, so
 *                                  a person with legal authority must rule
 *
 * ONE place, because it was five: the Summary tiles, the ring, the Dashboard
 * badges, the filter row and the report each spelled the order and the colour
 * out for themselves, and two of them disagreed — which is how "Requires
 * modification" ended up wearing the red that belongs to "Needs a decision".
 * Every surface reads these two, and the tone names are the stylesheet's own
 * `--ws-ok` / `--ws-warn` / `--ws-bad` channels (`ws-*--ok|warn|bad`).
 *
 * Presentation only, and no new colour: the three hues are DD-12's audited
 * ones, reassigned. Never colour alone — every surface that carries a tone
 * carries the word from `USER_STATUS_LABELS` and an icon beside it.
 */
export const USER_STATUS_ORDER: readonly UserStatus[] = [
  "ACCEPTABLE",
  "REQUIRES_MODIFICATION",
  "NEEDS_DECISION",
];

export type StatusTone = "ok" | "warn" | "bad";

export const USER_STATUS_TONE: Record<UserStatus, StatusTone> = {
  ACCEPTABLE: "ok",
  REQUIRES_MODIFICATION: "warn",
  NEEDS_DECISION: "bad",
};

/** The engine's determination, as the short phrase under a card's title (owner's
 *  reference, 2026-09-09) — the five answers in plain words, never the enum. */
const DETERMINATION_LABELS: Record<string, string> = {
  MATCH: "Constitution match",
  DEVIATION: "Deviates from the Constitution",
  MISSING: "Required clause missing",
  CONFLICT: "Conflicting provisions",
  UNABLE_TO_EVALUATE: "Unclear",
};

export function determinationLabel(classification: string): string | null {
  return DETERMINATION_LABELS[classification] ?? null;
}

export function userStatus(finding: Pick<Finding, "user_status">): UserStatus {
  // Server-derived (owner's FINAL decision, 2026-09-09): the backend maps the
  // authoritative result — classification, the approved rule's own outcome,
  // the Constitution citation — onto the three words in ONE place
  // (`legalmind/evaluation/user_status.py`), so a USER without the legal
  // position still gets the word and no screen re-derives it. Absent (an
  // older payload) it fails closed to "a person must look".
  return finding.user_status ?? "NEEDS_DECISION";
}

/** The three-word counts for a whole review — the Summary's tiles (AM-50 r4). */
export function statusCounts(
  findings: Array<Pick<Finding, "user_status" | "requires_decision">>,
): { ACCEPTABLE: number; REQUIRES_MODIFICATION: number; NEEDS_DECISION: number; needsDecision: number } {
  const out = { ACCEPTABLE: 0, REQUIRES_MODIFICATION: 0, NEEDS_DECISION: 0, needsDecision: 0 };
  for (const f of findings) {
    out[userStatus(f)] += 1;
    if (f.requires_decision) out.needsDecision += 1;
  }
  return out;
}

/** The Constitution citation behind a NOT ACCEPTED, or null.
 *  ponytail: finding-level — the first cited evaluation colours the whole card
 *  and the citation renders under the lede. Findings carry one evaluation
 *  today; attach it per evaluation if multi-scope findings start citing. */
export function constitutionProhibition(
  finding: Pick<Finding, "evaluations">,
): { section: string; quote: string } | null {
  for (const evaluation of finding.evaluations) {
    const p = evaluation.constitution_prohibition;
    if (p && p.section && p.quote) return p;
  }
  return null;
}

/**
 * Whether a scope label just repeats the requirement's own title in different
 * words the caller already read — "Residuals" beside a card already titled
 * "Residuals". Case- and whitespace-insensitive: `scopeLabel("RESIDUALS")` and
 * `requirementTitle({code: "RESIDUALS-NDA-001"})` both produce "Residuals" by
 * two independent paths, and a byte-exact compare would miss that.
 */
export function sameAsTitle(scope: string, title: string): boolean {
  return scope.trim().toLowerCase() === title.trim().toLowerCase();
}

/**
 * What the reader does next — one sentence, by what the engine found and
 * where the Finding sits in the workflow (owner, 2026-09-08, seventh pass).
 *
 * The engine never produces a Legal Decision (rule 13) and under the
 * zero-tolerance rule essentially every non-MATCH routes to a person, so
 * every non-MATCH step names that person and stops there. It never says what
 * the outcome would be — owner ruling 2026-09-09, withdrawing the sixth pass's
 * "adding it would make this Accepted": a lawyer may decide the missing clause
 * is acceptable as-is or require a different provision, and the card must not
 * pre-decide that (rule 13). Not accepted routes to a person and says why.
 * Never null for a real classification: "Next step" is one of the four
 * questions the card exists to answer.
 */
export function nextStep(
  finding: Finding,
  evaluation?: Evaluation,
  status: UserStatus = userStatus(finding),
): string | null {
  if (evaluation?.current_decision) {
    return "A decision has been recorded for this. No further action is needed.";
  }
  const escalated = finding.requires_decision || evaluation?.requires_decision;
  switch (status) {
    case "REQUIRES_MODIFICATION":
      // The owner's own words (2026-09-09): a clear, rule-backed conflict is
      // the one status where the card may say the contract needs changing.
      return "This does not match the company standard. The clause needs to be modified, or someone with legal authority must decide.";
    case "ACCEPTABLE":
      // An escalated MATCH still needs a person (workflow.py clause (d)): the
      // server's flag wins over the status's default.
      return escalated
        ? "This has been escalated. Someone with legal authority needs to review it and record a decision."
        : "No action is needed.";
    default:
      // One sentence for every Needs review, whatever the engine recorded: it
      // never pre-decides the outcome (owner, 2026-09-09).
      return "Someone with legal authority needs to decide this.";
  }
}

function classificationOf(finding: Finding, evaluation?: Evaluation): string {
  return evaluation?.classification ?? finding.classification;
}

/**
 * The one sentence a Sales reader gets — what was found, in the words of the
 * data (owner, 2026-09-08, seventh pass). Built from the requirement's title
 * and the two values only; it never explains what a clause MEANS in law and
 * never names a consequence (rules 7, 12, 21). Residuals is nothing special
 * here: every requirement type flows through the same five shapes.
 *
 *   MATCH      "The document's liability is 12 months, which matches the
 *               company standard."
 *   DEVIATION  "The document sets late fee at 8 percent per month, while the
 *               company standard expects 5 percent per month."
 *   MISSING    "The document does not include residuals, which the company
 *               standard requires."
 *   CONFLICT   "The document contains provisions on … that contradict each
 *               other."
 *   UNABLE     "There is no approved company standard recorded for …, so
 *               LegalMind cannot tell whether it is acceptable." — or, when
 *               the standard exists but the document is unreadable on the
 *               point, "The document does not say enough about … to tell
 *               whether it meets the company standard."
 *
 * `expected_value` is OMITTED for a caller without `legal_position.view`;
 * those sentences then simply do not mention the standard's value.
 */
export function findingSentence(finding: Finding, evaluation?: Evaluation): string | null {
  const classification = evaluation?.classification ?? finding.classification;
  const subject = subjectOf(requirementTitle(finding.requirement));
  const contract = evaluation ? sideOf(evaluation.actual_value) : null;
  const hasStandard = evaluation !== undefined && evaluation.expected_value !== undefined;
  const standard = hasStandard ? standardSideOf(evaluation.expected_value) : null;
  const standardValue = standard && standard.tone === "value" ? standard.text : null;
  const contractValue = contract && contract.tone === "value" ? contract.text : null;

  switch (classification) {
    case "MATCH":
      return contractValue
        ? `The document's ${subject} is ${contractValue}, which matches the company standard.`
        : `The document includes ${subject}, as the company standard requires.`;
    case "DEVIATION":
      if (contract?.text === "No limit stated") {
        return standardValue
          ? `The document sets no limit on ${subject}, while the company standard expects ${standardValue}.`
          : `The document sets no limit on ${subject}, which differs from the company standard.`;
      }
      if (contractValue && standardValue) {
        return `The document sets ${subject} at ${contractValue}, while the company standard expects ${standardValue}.`;
      }
      if (contractValue) {
        return `The document sets ${subject} at ${contractValue}, which differs from the company standard.`;
      }
      return `The document covers ${subject}, but not in the way the company standard expects.`;
    case "MISSING":
      return hasStandard
        ? `The document does not include ${subject}, which the company standard requires.`
        : `The document does not include ${subject}.`;
    case "CONFLICT":
      return `The document contains provisions on ${subject} that contradict each other.`;
    case "UNABLE_TO_EVALUATE":
      if (hasStandard && standard && standard.tone === "unknown") {
        return `There is no approved company standard recorded for ${subject}, so LegalMind cannot tell whether it is acceptable.`;
      }
      return `The document does not say enough about ${subject} to tell whether it meets the company standard.`;
    default:
      return classificationSentence(classification);
  }
}

/** A title, ready to sit mid-sentence: "Residuals" → "residuals", but an
 *  acronym or a name that is already mid-sentence-shaped is left alone
 *  ("NDA term", "IP assignment"). */
function subjectOf(title: string): string {
  if (title.length > 1 && title[1] === title[1]!.toUpperCase() && /[A-Z]/.test(title[1]!)) return title;
  return title.charAt(0).toLowerCase() + title.slice(1);
}

/**
 * One side of the comparison, ready to render.
 *
 * `tone` drives a mark and never colour alone. `value` earns NO mark: a tick
 * beside "6 MONTHS" would read as "satisfied" when it is simply the number the
 * standard states — the first draft of this did exactly that and the screenshot
 * showed a green tick against the company's own expected value.
 *
 * `detail` carries a controlled-vocabulary token verbatim — `FEES_PAID` is not
 * the same basis as `FEES_PAID_FOR_AFFECTED_SERVICES` (45B.4 forbids assuming
 * otherwise), so it is never reworded into friendlier prose. It renders small
 * and monospaced beside the phrase a reader can act on.
 */
export interface Side {
  tone: "present" | "absent" | "unknown" | "value";
  text: string;
  detail?: string;
}

const PRESENCE_WORDS: Record<string, Side> = {
  PRESENT: { tone: "present", text: "Found" },
  ABSENT: { tone: "absent", text: "Not found" },
  INDETERMINATE: { tone: "unknown", text: "Unclear" },
  FINITE: { tone: "present", text: "Found" },
  UNLIMITED: { tone: "value", text: "No limit stated" },
  UNKNOWN: { tone: "unknown", text: "Unclear" },
};

/** The keys the evaluators actually use, measured against the live database
 *  rather than guessed: the PRESENCE evaluator writes `{presence}`, the numeric
 *  one `{cap_value, cap_unit, cap_basis, scope}` on the contract side and
 *  `{preferred, unit, basis, scope_key}` on the standard side, `{cap_status}`
 *  when nothing was extracted, and `{caps: [...]}` when several provisions
 *  govern one scope. A first version looked for `amount`/`value` alone and so
 *  fell through to printing "scope, cap_unit, cap_basis, cap_value" — the KEYS
 *  — at the reader. */
const NUMBER_KEYS = ["cap_value", "value", "amount", "preferred"];
const UNIT_KEYS = ["cap_unit", "unit"];
const BASIS_KEYS = ["cap_basis", "basis"];

/** A unit enum in the reader's words — "12 months", "1 year", "8 percent per
 *  month". Units are measurement, not legal position, so this is presentation;
 *  the `basis` token beside it stays verbatim (45B.4). Unknown units fall back
 *  to lower-case words — unreachable on the 32 ratified standards (DAYS, MONTHS,
 *  YEARS, PERCENT_PER_MONTH only); add a monetary unit here explicitly before
 *  configuring one, or "USD" would render as "usd". */
const UNIT_WORDS: Record<string, string> = {
  MONTHS: "months", YEARS: "years", DAYS: "days", WEEKS: "weeks", HOURS: "hours",
  PERCENT_PER_MONTH: "percent per month", PERCENT_PER_ANNUM: "percent per year",
  PERCENT: "percent",
};

function unitWords(unit: unknown, n: number): string {
  const raw = String(unit);
  const words = UNIT_WORDS[raw.toUpperCase()] ?? raw.toLowerCase().replace(/_/g, " ");
  return n === 1 && /s$/.test(words) && !/percent/.test(words) ? words.slice(0, -1) : words;
}

function firstOf(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    const found = record[key];
    if (found !== undefined && found !== null) return found;
  }
  return undefined;
}

/** `String(30.0)` is already "30" — the evaluator stores a float and the
 *  document says "30 DAYS". Named for the intent, not for the arithmetic. */
function plain(value: unknown): string {
  return String(value);
}

export function sideOf(value: unknown): Side {
  if (value === null || value === undefined) {
    return { tone: "unknown", text: "Not recorded" };
  }
  if (typeof value === "string") {
    return PRESENCE_WORDS[value] ?? { tone: "value", text: value };
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return { tone: "value", text: plain(value) };
  }
  if (typeof value !== "object" || Array.isArray(value)) {
    return { tone: "unknown", text: "Not recorded" };
  }

  const record = value as Record<string, unknown>;

  // Several provisions govern one scope — the CONFLICT shape. Stated as a
  // count, because which one prevails is exactly what the engine could not
  // decide and is not ours to assert.
  if (Array.isArray(record.caps)) {
    const n = record.caps.length;
    return { tone: "unknown", text: `${n} separate ${n === 1 ? "limit" : "limits"} stated` };
  }

  const state = record.presence ?? record.cap_status;
  const number = firstOf(record, NUMBER_KEYS);
  if (typeof state === "string" && (number === undefined || state !== "FINITE")) {
    return PRESENCE_WORDS[state] ?? { tone: "unknown", text: state };
  }

  if (number !== undefined) {
    const unit = firstOf(record, UNIT_KEYS);
    const basis = firstOf(record, BASIS_KEYS);
    return {
      tone: "value",
      text: [plain(number), unit === undefined ? undefined : unitWords(unit, Number(number))]
        .filter((part) => part !== undefined).join(" "),
      ...(basis !== undefined ? { detail: String(basis) } : {}),
    };
  }

  // Nothing recognised. Naming the keys is honest — it says the shape was not
  // understood rather than inventing a reading of it — but it is a last resort.
  const keys = Object.keys(record).filter((key) => key !== "scope" && key !== "scope_key");
  return keys.length > 0
    ? { tone: "unknown", text: "Recorded, but not in a form this view can summarise" }
    : { tone: "unknown", text: "Not recorded" };
}

/**
 * The SAME value, worded for the Company Standard column rather than the
 * "Found in contract" one — owner request, 2026-09-08 (third pass): "Company
 * Standard: Found" reads as if the standard document itself turned up
 * somewhere, when what a presence-shaped standard value actually states is
 * REQUIRED or NOT REQUIRED (the ratified configuration's own field is
 * `expected_presence: PRESENT`, alongside `applicability: REQUIRED` — this is
 * a direct reading of that pair, not an invented distinction). Every other
 * shape (a numeric cap, a controlled-vocabulary basis) is unaffected: this
 * only reworks the two presence tokens.
 *
 * "Not required" gets no mark — `sideOf`'s plain absence reads as a defect
 * (✗), and a standard that simply does not require something is not one.
 */
export function standardSideOf(value: unknown): Side {
  const side = sideOf(value);
  if (side.tone === "present" && side.text === "Found") {
    return { tone: "present", text: "Required" };
  }
  if (side.tone === "absent" && side.text === "Not found") {
    return { tone: "unknown", text: "Not required" };
  }
  return side;
}

/** One step of the reasoning chain. `detail` is the engine's own note, kept for
 *  the reader who wants it and never required to make the step make sense. */
export interface Step {
  label: string;
  text: string;
}

/**
 * Why this was flagged — the Evidence → Fact → Standard → Rule → Result chain
 * of rule 12, in the reader's language and built ONLY from present fields.
 *
 * The engine's own `explanation` lines stay available verbatim beside this (the
 * card renders them under "The engine's own record"); they are accurate and
 * they are the audit trail, but "mapping CONFIRMED for RESIDUALS-NDA-001" and
 * "absence established by mapping, not by evaluator inspection" are notes to an
 * engineer, which is exactly the complaint this answers.
 *
 * `expected_value` and `rule_outcome` are OMITTED for a caller without
 * `legal_position.view` (LEGAL-02, SEC-07). Their steps are then absent rather
 * than nulled — the chain simply reads Requirement → Contract → Result.
 */
export function reasoningSteps(
  finding: Finding,
  evaluation: Evaluation,
  evidenceCount: number,
): Step[] {
  const steps: Step[] = [];
  const title = requirementTitle(finding.requirement);
  steps.push({
    label: "Requirement",
    text: `${title} was checked against the company standard.`,
  });

  const contract = sideOf(evaluation.actual_value);
  steps.push({
    label: "This document",
    text: contract.tone === "absent"
      ? "No matching provision was found."
      : evidenceCount === 0
        ? `Recorded as ${contract.text.toLowerCase()}; no supporting passage was cited.`
        : `${contract.text} in ${evidenceCount === 1 ? "1 passage" : `${evidenceCount} passages`}, quoted below.`,
  });

  if (evaluation.expected_value !== undefined) {
    const standard = sideOf(evaluation.expected_value);
    steps.push({
      label: "Company standard",
      text: standard.tone === "present" && standard.text === "Found"
        ? "The standard expects this to be present."
        : standard.tone === "absent"
          ? "The standard expects this to be absent."
          : `The standard expects ${standard.text}.`,
    });
  }

  // The engine's own word — MATCH / DEVIATION / MISSING / CONFLICT / NEEDS A
  // PERSON — kept verbatim for audit (rules 11, 12). The card face says
  // Accepted / Needs review / Not accepted; this is the only place the
  // classification appears, so nothing is said twice.
  steps.push({
    label: "Result",
    text: `Recorded as ${classificationLabel(evaluation.classification)}.`,
  });
  return steps;
}

/**
 * How a passage was READ, where that changes how much it can be trusted.
 *
 * `source_type` was at first taken to distinguish a contract passage from a
 * company-standard passage, and it does not: measured against the live
 * database its values are `NATIVE_TEXT`, `OCR` and `TABLE`. A Finding's
 * evidence comes from `finding_evidence` and is therefore always from the
 * document under review, so there is no grouping to do — but a passage
 * recovered by OCR or lifted out of a table is worth flagging, because that is
 * where a misread comes from. Native text says nothing, because there is
 * nothing to say.
 */
export function evidenceNote(sourceType: string): string | null {
  if (/OCR/i.test(sourceType)) return "read by OCR";
  if (/TABLE/i.test(sourceType)) return "from a table";
  return null;
}

/** Where a passage sits, as one line. Every part is optional in the data, so
 *  every part is optional here; a row with no location at all says so rather
 *  than rendering an empty button. */
export function evidenceLocation(row: Evidence, index: number): string {
  const parts = [
    row.section_number ? `§${row.section_number}` : null,
    row.section_title,
    row.page_number != null ? `page ${row.page_number}` : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : `Passage ${index + 1}`;
}

/** A long excerpt, cut at a sentence or word boundary rather than mid-word.
 *  Returns the whole string when it is already short enough, so a caller can
 *  compare the two to decide whether a "show all" control is needed. */
export function excerpt(content: string, limit = 320): string {
  const text = content.trim();
  if (text.length <= limit) return text;
  const window = text.slice(0, limit);
  const stop = Math.max(window.lastIndexOf(". "), window.lastIndexOf("; "));
  if (stop > limit * 0.5) return `${window.slice(0, stop + 1)}…`;
  const space = window.lastIndexOf(" ");
  return `${(space > 0 ? window.slice(0, space) : window).trimEnd()}…`;
}

/**
 * The report's headline, in plain language.
 *
 * Counts only — no score, no grade, no severity ranking (rule 12, DESIGN.md).
 * The sentence states what the counts mean for the reader and stops there.
 */
export function reviewHeadline(counts: {
  total: number;
  needsDecision: number;
  missing: number;
  match: number;
}): string {
  if (counts.total === 0) {
    return "No ratified requirement for this document type produced a finding.";
  }
  if (counts.needsDecision > 0) {
    return counts.needsDecision === 1
      ? "1 point needs a person to decide before this contract is settled."
      : `${counts.needsDecision} points need a person to decide before this contract is settled.`;
  }
  if (counts.match === counts.total) {
    return counts.total === 1
      ? "The one requirement checked matches the company standard."
      : `All ${counts.total} requirements checked match the company standard.`;
  }
  return "Nothing is waiting on a decision. The findings below record what was checked.";
}
