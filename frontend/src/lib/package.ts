/**
 * The final contract (`AM-307`): our template's body exactly as sent, and every agreed
 * change as one entry of Special Conditions (Annexure A). Everything here is the
 * server's — the dry run, its blockers, the entries and the trace; this file only
 * names them in plain words (rule 18: nothing decided here).
 */

import type { Answer, ClientChange, EffectForUs, Measured } from "./changes";

export interface PackageBlocker {
  code: string;
  /** most blockers carry `message`; a template-readiness one carries `detail` */
  message?: string;
  detail?: string;
  /** the change it is about — a link to that change */
  row_key?: string;
}

export interface PackageTarget { key: string; number: string | null; heading: string | null }

export interface PackageEntry {
  n: number;
  op: "replace" | "delete" | "insert";
  target: PackageTarget;
  text: string | null;
  new_number?: string;
  row_key?: string;
  answer?: Answer;
  effect?: EffectForUs;
  /** why a NEGATIVE row goes to Legal — the Changes row's own words (slice A split) */
  measured?: Measured;
}

/** `AM-310`: an amendment is the changes-only instrument unless Legal restates it */
export type PackageForm = "changes_only" | "restated";

export interface PackagePlan {
  available: boolean;
  /** present on an amendment only */
  form?: PackageForm;
  /** why Legal might restate the whole contract: a suggestion, never a choice made here */
  restatement?: string[];
  blockers: PackageBlocker[];
  entries: PackageEntry[];
  precedence: { clause_key: string; number: string | null; approved: boolean } | null;
  entries_sha256: string | null;
}

export interface PreparedPackage {
  document_version: { id: string; version_number: number };
  review_id: string | null;
  entries: PackageEntry[];
  downloads: { docx: string; pdf: string };
  open_points: unknown;
}

/** One entry's record: who answered, when, why — `internal_note` only for a reader the
 *  server sends it to (the key is absent otherwise, never shown as empty). */
export interface TraceEntry {
  n: number;
  op: PackageEntry["op"];
  effect?: EffectForUs | null;
  measured?: Measured;
  row_key: string;
  decision_ids: string[];
  answer?: string;
  decided_by?: string | null;
  decided_at?: string;
  reason?: string | null;
  client_note?: string | null;
  internal_note?: string | null;
}

export interface SpecialConditions {
  document_version_id: string;
  package_of: string | null;
  entries: PackageEntry[];
  trace: TraceEntry[];
}

/** The dry run says this deal does not go out as a final contract at all — the bar is
 *  absent, and "Prepare our reply" stays the step. */
const OTHER_ROUTE = new Set(["NOTHING_TO_ANSWER", "NOT_OUR_TEMPLATE", "REDLINE_ROUND", "ROUND_CLOSED",
                             "AMENDMENT_ROUND", "NO_ANNEXURE"]);

export function packageApplies(plan: PackagePlan | null | undefined): plan is PackagePlan {
  return !!plan && !plan.blockers.some((b) => OTHER_ROUTE.has(b.code));
}

/** The template-readiness codes, said for the person who reads them (the server's own
 *  `detail` is written for Legal's set-up screen). */
const SAID: Record<string, string> = {
  SC_NOT_CONFIGURED: "The template has no Special Conditions (Annexure A) set up.",
  SC_FRAME_MISSING: "The template has no Special Conditions (Annexure A) wording yet.",
  SC_FRAME_NOT_APPROVED: "The Special Conditions (Annexure A) wording is not approved yet.",
  SC_FRAME_INCOMPLETE: "The Special Conditions (Annexure A) wording is incomplete.",
  SC_PRECEDENCE_NOT_PINNED: "The template has no clause saying Annexure A wins over the body.",
  SC_PRECEDENCE_NOT_APPROVED: "The clause saying Annexure A wins over the body is not approved yet.",
  SC_POSITION: "Where Annexure A sits in the contract is not set.",
  NO_AMENDMENT_TEMPLATE: "No approved amendment template yet — Legal needs to approve one first.",
  EFFECTIVE_DATE: "Say the date the amendment takes effect.",
  TEMPLATE_NOT_PUBLISHED: "The template this contract was made from was never published.",
};

export function blockerText(b: PackageBlocker): string {
  const said = SAID[b.code] ?? b.message ?? b.detail ?? "Something stops the final contract.";
  // the bar already says it cannot be prepared yet; keep only the reason
  const reason = said.replace(/^The final contract cannot be prepared yet:\s*/, "");
  return reason.charAt(0).toUpperCase() + reason.slice(1);
}

export function clauseName(t: PackageTarget, newNumber?: string): string {
  const number = newNumber ?? t.number;
  const where = number ? `Clause ${number}` : "A new clause";
  return t.heading ? `${where}, ${sentence(t.heading)}` : where;
}

/** "PAYMENT AND INVOICING" reads as "Payment and invoicing"; a title already in mixed
 *  case keeps its own words. */
function sentence(heading: string): string {
  return heading === heading.toUpperCase() ? heading.charAt(0) + heading.slice(1).toLowerCase() : heading;
}

const WITH: Partial<Record<string, string>> = {
  accept_theirs: "the client’s wording",
  write_wording: "our new wording",
  use_standard: "our standard wording",
};

export function entryAction(e: Pick<PackageEntry, "op" | "answer" | "new_number">): string {
  if (e.op === "delete") return "Removed";
  const said = e.answer ? WITH[e.answer] : undefined;
  if (e.op === "insert") return said ? `Added, with ${said}` : "Added";
  return said ? `Replaced with ${said}` : "Replaced";
}

/** U2: what one answered change becomes in the final contract — from the dry run's
 *  entries and blockers (or, once prepared, its Annexure A), matched by `row_key`.
 *  null while the change is unanswered, or when there is no final contract. */
export function packageLine(
  change: { row_key: string; answer: { answer: Answer } | null },
  entries: PackageEntry[], blockers: PackageBlocker[] = [], place: string = ANNEX,
): string | null {
  const entry = entries.find((e) => e.row_key === change.row_key);
  if (entry) return place === ANNEX ? `Entry ${entry.n} of Annexure A. ${entryAction(entry)}.`
    : `Change ${entry.n}. ${entryAction(entry)}.`;
  const stop = blockers.find((b) => b.row_key === change.row_key);
  if (stop) return `Can’t be written into ${place}. ${blockerText(stop)}`;
  if (!change.answer) return null;
  return change.answer.answer === "keep_ours" ? "No entry. Our wording stays." : "No entry. Our wording does not change.";
}

/** U2, on every change row: what the final contract does to it, from the row's own
 *  `in_package` / `target` (`AM-308`). null where the row carries neither (no final
 *  contract from this pair), or while an unanswered change has nothing in Annexure A. */
/** Where an agreed change is written: Annexure A of a final contract, or (`AM-310`) the
 *  changes-only amendment itself. */
export const ANNEX = "Annexure A";
export const AMENDMENT_PLACE = "the amendment";

export function finalLine(c: Pick<ClientChange, "answer" | "target" | "in_package">,
                          place: string = ANNEX): string | null {
  const n = c.target?.number;
  switch (c.in_package) {
    case "replace": return n ? `Goes into ${place}, replacing clause\u00a0${n}` : `Goes into ${place} as a replacement`;
    case "delete": return n ? `Goes into ${place}, removing clause\u00a0${n}` : `Goes into ${place} as a removal`;
    case "insert": return n ? `Goes into ${place} as a new clause after\u00a0${n}` : `Goes into ${place} as a new clause`;
    case "cannot": return `Can’t be written into ${place} as it is`;
    case "none": return c.answer ? `Not in ${place === ANNEX ? "the final contract" : place}. Our wording stays` : null;
    default: return null;
  }
}
