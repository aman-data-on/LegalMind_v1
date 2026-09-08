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
    .filter((part) => !TYPE_CODES.has(part.toUpperCase()));
  if (words.length === 0) return code;
  const sentence = words.join(" ").toLowerCase();
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
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
 * What happens next — from the Finding's own workflow position and the
 * Evaluation's Rule Outcome, never from an opinion about severity.
 *
 * A recorded decision is stated as a fact and nothing further is asked for; a
 * Finding the server flagged `requires_decision` says a person must act. The
 * fail-closed outcome (`NOT_APPLICABLE`, locked Step 20 r4) is the one that
 * misleads on sight, so it says what it actually means: no rule disposes of
 * this, so a person decides.
 */
export function nextStep(finding: Finding, evaluation?: Evaluation): string | null {
  if (evaluation?.current_decision) {
    return "A decision has been recorded for this. No further action is needed.";
  }
  if (finding.requires_decision || evaluation?.requires_decision) {
    return "Someone with legal authority needs to review this and record a decision.";
  }
  const outcome = evaluation?.rule_outcome;
  if (outcome === "ACCEPTABLE") return "No action is needed.";
  if (outcome === "APPROVAL_REQUIRED") {
    return "This needs approval before the contract can proceed on these terms.";
  }
  if (outcome === "NOT_APPLICABLE") {
    return "No published rule covers this result, so a person decides what to do.";
  }
  return null;
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
      text: [plain(number), unit].filter((part) => part !== undefined).join(" "),
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

  const result = classificationSentence(evaluation.classification);
  const action = nextStep(finding, evaluation);
  steps.push({
    label: "Result",
    text: [result, action].filter(Boolean).join(" "),
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
