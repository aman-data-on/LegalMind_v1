/**
 * Batch 5 (AB-221): the steps behind "Our contract came back marked up", apart from the
 * page so each one is checked on its own. Presentation and request order only: the server
 * decides every refusal, every base and every row (rule 18).
 */

import { chainAnalysis } from "./analysisChain";
import { api, ApiError } from "./api";
import { formatDate } from "./dates";
import { documentTypeChip } from "./documentTypes";
import { RETURNED_COPY as C } from "./labels";
import type { Contract } from "./types";
import { preflightProblem, startContract } from "./upload";

/** the deal choice for a contract that is not in LegalMind yet */
export const NEW_DEAL = "new";
const WORD = [".docx"];
/** S1: a returned copy lands on a deal whose latest version is ours, or nothing yet */
const OPEN_FOR_RETURN = new Set(["DRAFTING", "READY_TO_SEND", "WITH_CLIENT"]);
/** a closed deal is not listed: presentation only, the list is the server's (SEC-07) */
const HIDDEN = new Set(["FINAL", "SIGNED"]);

export type Missing = keyof typeof C.missing;

/** What the person still has to choose, first first — the bar says it (S7) — or null. */
export function missingOf(s: { client: unknown; deal: string | null; file: File | null; haveCopy: boolean;
                               copy: File | null }): Missing | null {
  return !s.client ? "client" : !s.deal ? "deal" : !s.file ? "file"
    : s.deal === NEW_DEAL && s.haveCopy && !s.copy ? "copy" : null;
}

/** Why the file the client sent back cannot be sent, or null — a PDF never (Q5). */
export function fileRefusal(file: File): string | null {
  return file.name.toLowerCase().endsWith(".pdf") ? C.pdf : preflightProblem(file, WORD);
}

/** Why the copy we sent cannot be used, or null: it supplies our opening figures, so only
 *  the Word file we emailed (S3). */
export function copyRefusal(file: File): string | null {
  return file.name.toLowerCase().endsWith(".pdf") ? C.copyWord : preflightProblem(file, WORD);
}

/** This client's deals as listed: FINAL and SIGNED left out. */
export function dealsShown(rows: Contract[]): Contract[] {
  return rows.filter((c) => !HIDDEN.has(c.negotiation_stage?.stage ?? ""));
}

/** Whether a listed deal takes the returned copy now (others say "Open the deal"). */
export function openForReturn(c: Contract): boolean {
  const stage = c.negotiation_stage?.stage;
  return !stage || OPEN_FOR_RETURN.has(stage);
}

export type Refusal = "no_tracked" | "word" | "gone" | "closed" | "other";

/** What a failed send means for the page. */
export function refusalOf(cause: unknown, existingDeal: boolean): Refusal {
  if (!(cause instanceof ApiError)) return "other";
  if (cause.code === "NO_TRACKED_CHANGES") return "no_tracked";
  if (cause.code === "WORD_FILE_NEEDED") return "word";
  // M8: a 404 is the same whether the deal went or was never the reader's (49.5, 52.4)
  if (existingDeal && cause.isNotFound) return "gone";
  return existingDeal && cause.status === 409 ? "closed" : "other";
}

/** What a refusal changes on the page (round 2, D2). Never the client or the file the
 *  person chose (R6): a clean Word file under "tracked changes only" switches to "I have the
 *  copy we sent" and keeps both; ``focus`` is the element that says why. */
export function afterRefusal(why: Refusal): {
  focus: string; haveCopy?: true; noTracked?: true; dropFile?: true; fileError?: string; deal?: null;
  dealProblem?: string; failure?: true; forgetDeal?: true;
} {
  switch (why) {
    case "no_tracked": return { focus: "rm-notracked", haveCopy: true, noTracked: true, forgetDeal: true };
    case "word": return { focus: "rm-file-err", dropFile: true, fileError: C.pdf };
    case "gone": return { focus: "rm-deal-h", deal: null, dealProblem: C.gone };
    case "closed": return { focus: "rm-deal-h", deal: null, dealProblem: C.closed };
    default: return { focus: "rm-fail", failure: true };
  }
}

/** A new deal's name: its type once read (MSA), the client and today (round 2, UI 4). */
export function newDealName(client: string, today = new Date()): (type: string | null) => string {
  return (type) => C.dealName(documentTypeChip(type), client, formatDate(today));
}

export type SendStep = { n: number; of: number; what: "copy" | "theirs" | "check" };
/** what is already in: a retry resumes after it (review M7) */
export type Made = { contractId: string | null; copyIn: boolean };

/**
 * Send the returned file, in the one order the server can compare (before < after,
 * `negotiation.py:1006`): (a) an existing deal — the file as its next version; (b) a new
 * deal with the copy we sent — that copy as our draft, then the file; (c) a new deal with
 * no copy — the file alone, declared "tracked changes only" (`AM-456`). Resolves with the
 * deal to land on, or the deal already holding this very file (`duplicate`).
 */
export async function sendReturned(o: {
  deal: string; clientId: string; clientName: string; file: File; copy: File | null; haveCopy: boolean; review: boolean;
  made: Made; onStep: (step: SendStep) => void;
}): Promise<{ contractId: string; duplicate: boolean }> {
  const isNew = o.deal === NEW_DEAL;
  if (isNew && !o.haveCopy) {
    o.onStep({ n: 1, of: 2, what: "theirs" });
    const started = await startContract(o.file, "CLIENT_MODIFIED", {
      nameFor: newDealName(o.clientName), counterpartyId: o.clientId, compareWith: "TRACKED_ORIGINAL", canReview: o.review,
      onStep: (s) => { if (s === "analyzing") o.onStep({ n: 2, of: 2, what: "check" }); } });
    return { contractId: started.contractId, duplicate: false };
  }
  const of = isNew ? 3 : 2;
  let contractId = o.deal;
  if (isNew) {
    if (!o.made.copyIn || !o.made.contractId) {
      o.onStep({ n: 1, of, what: "copy" });
      // ponytail: a failure before the copy is in starts a new deal on retry; a refusal
      // archived the first one, a dropped connection may leave it (as Upload a contract does)
      const started = await startContract(o.copy!, "COMPANY_DRAFT", { nameFor: newDealName(o.clientName),
                                                                      counterpartyId: o.clientId, canReview: o.review });
      Object.assign(o.made, { contractId: started.contractId, copyIn: true });
    }
    contractId = o.made.contractId!;
  }
  o.onStep({ n: of - 1, of, what: "theirs" });
  const up = await api.uploadDocument(contractId, o.file, "CLIENT_MODIFIED");
  if (up.duplicate_of) return { contractId, duplicate: true };   // M7: never a false "no changes"
  o.onStep({ n: of, of, what: "check" });
  await chainAnalysis(contractId, o.review);
  return { contractId, duplicate: false };
}

/** One run at a time (R7): a second call while the first is in flight does nothing. */
export function singleFlight<A extends unknown[]>(run: (...args: A) => Promise<void>): (...args: A) => Promise<void> {
  let busy = false;
  return async (...args: A) => {
    if (busy) return;
    busy = true;
    try { await run(...args); } finally { busy = false; }
  };
}
