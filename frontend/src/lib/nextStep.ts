/**
 * The ONE primary action per person per stage (cross-page pass, `AM-291`). Presentation
 * only (rule 18): it reads the server's stage, the server's `counts` and what the server
 * says this reader may do, and picks a label from the one action map. Every write checks
 * again server-side; nothing here decides a legal outcome.
 *
 * The header renders the step; the page that owns the act listens for it (`onStep`), so
 * the button can live in the header on every tab without the header owning the act.
 */

import { useEffect } from "react";

import { ACTION, finalReady, type StageViewer } from "./labels";
import type { DealCounts, NegotiationStageCode, ReviewAssignments, TodoItem } from "./types";

export type StepKind =
  | "decide" | "recordDecision" | "answerChanges" | "prepareReply" | "sendReply" | "sendToLegal" | "sendToClient"
  | "preparePackage" | "prepareFinal" | "downloadFinal" | "startAmendment";

export interface Step { kind: StepKind; label: string }

export interface StepFacts {
  stage?: NegotiationStageCode | undefined;
  counts?: DealCounts | undefined;
  /** "legal" = holds `legal.decision` and is not the deal's owner (`stageViewer`) */
  viewer: StageViewer;
  /** may answer and send on this deal — the server's own `can_answer`/ownership */
  canAnswer: boolean;
  /** the owner may send the review to a Legal reviewer, and has not yet */
  canSendToLegal?: boolean;
  /** our prepared reply is the latest version, not sent, and this reader may record it */
  replyReady?: boolean;
  /** our own draft (not a reply) is the latest version and has not been sent */
  draftUnsent?: boolean;
  /** `AM-307`: the final contract's dry run is clear — prepare it instead of a tracked reply */
  packageReady?: boolean;
  /** `AM-307`: our final contract is the latest version and has not been sent */
  packageUnsent?: boolean;
  /** `AM-310`: the deal is an amendment — its package is the amendment itself */
  amendment?: boolean;
  /** `AM-318`: the latest version is the final contract (a package or a final copy) */
  finalLatest?: boolean;
  /** LA-18: this reader answers the client's changes (owner or collaborator — whoever the
   *  To-do gives them to); someone who only MAY answer gets no "Answer changes" primary */
  answersChanges?: boolean;
}

export function nextStep(f: StepFacts): Step | null {
  const c = f.counts ?? {};
  const step = (kind: StepKind, label: string = ACTION[kind] as string): Step => ({ kind, label });
  // batch 1 (one lawyer queue): the client's changes Legal holds lead — ONE primary,
  // "Answer N changes"; the points stay one tab away, never a second primary beside it
  if (f.viewer === "legal" && c.changes_left_for_me) return step("answerChanges", ACTION.answerChangesN(c.changes_left_for_me));
  if (f.viewer === "legal" && c.points_for_me) return step("decide", ACTION.decide(c.points_for_me));
  // AM-413: every point is answered (or waits only on the client) — the contract decision
  // is this lawyer's to record now (the server's `decision_for_me`)
  if (f.viewer === "legal" && c.decision_for_me && f.stage !== "FINAL" && f.stage !== "SIGNED") {
    return step("recordDecision");
  }
  // UX L1/S4: Legal's only primary is deciding — sending, preparing and signing are sales acts
  if (!f.canAnswer || f.viewer === "legal") return null;
  switch (f.stage) {
    case "FINAL":
      // AM-318: the end. AB-213 D5: the final card's "PDF for signature" is the one main
      // button (the owner's); the header adds none
      return null;
    case "ON_HOLD":
      // AB-213 D1 (AM-405): never stuck — our reply (with the question) goes to the client
      if (f.finalLatest) return null;
      return f.replyReady ? step("sendReply") : step("prepareReply");
    case "READY_TO_SIGN":
      // AM-318: Legal's decision is on a version that is not final — make the final copy
      return f.finalLatest ? null : step("prepareFinal");
    case "READY_TO_SEND":
      // our reply, or our own draft once Legal decided every point of it
      // AM-393: "Sign after our changes" decided on the client's version — reply next
      return f.replyReady ? step("sendReply") : f.draftUnsent ? step("sendToClient") : step("prepareReply");
    case "CLIENT_RETURNED":
      if (c.changes_left_for_me && f.answersChanges !== false) return step("answerChanges");
      if (c.changes_total === undefined) return null;
      // prelaunch U1: changes only Legal may answer, not yet sent — sending them is the step
      if (c.changes_left) return f.canSendToLegal ? step("sendToLegal") : null;
      // Batch 1 (c): open points go to Legal before the final contract
      if (!c.changes_ours && !finalReady(c)) return f.canSendToLegal ? step("sendToLegal") : null;
      if (f.packageReady) return step("preparePackage", f.amendment ? ACTION.prepareAmendment : undefined);
      // our answers go back to the client as our reply first; nothing to send back
      // (every change accepted) — the client's version is agreed: its final copy
      return c.changes_ours ? step("prepareReply") : step("prepareFinal");
    case "INTERNAL_REVIEW":
      // AM-398 r2: the client's version with Legal may still hold changes left to us
      if (c.changes_left_for_me && f.answersChanges !== false) return step("answerChanges");
      // our reply (or draft) holds open points, or the final copy waits on Legal's
      // decision on the contract, and nobody in Legal has it yet
      return (c.points_open || f.finalLatest) && f.canSendToLegal ? step("sendToLegal") : null;
    case "DRAFTING":
      if (c.points_open && f.canSendToLegal) return step("sendToLegal");
      return c.points_open === 0 && f.draftUnsent ? step("sendToClient") : null;
    default:
      return null;
  }
}

/** Whether the contract header offers "Send to Legal": there is something for Legal to
 *  decide, the paper is not with the client or done, this reader may send, and the review
 *  is NOT already with Legal — at any stage (the server's `sent_to_legal`, or a reviewer
 *  just picked here). Presentation only; the send checks again. */
export function canSendToLegalFor({ stage, counts, finalLatest, assign }: {
  stage?: NegotiationStageCode | undefined; counts?: DealCounts | undefined;
  finalLatest: boolean; assign: ReviewAssignments | null;
}): boolean {
  return stage !== "SIGNED" && stage !== "WITH_CLIENT" && stage !== "FINAL"
    && ((counts?.points_open ?? 0) > 0 || (finalLatest && stage === "INTERNAL_REVIEW"))
    && !counts?.sent_to_legal && !!assign?.can_send && !assign.assigned.length
    && assign.eligible.length > 0;
}

/** A To-do item's action, in the same words as the header's step. */
export function taskAction(item: Pick<TodoItem, "kind" | "count" | "counts" | "changes">): string {
  switch (item.kind) {
    // one lawyer queue: the changes lead, as the contract header's one primary does
    case "decide": return item.changes ? ACTION.answerChangesN(item.changes) : ACTION.decide(item.count);
    case "second_approval": return ACTION.reviewDecision;
    case "answered": return ACTION.seeAnswer;
    case "reply_ready": return ACTION.sendReply;
    case "contract_decision": return ACTION.recordContractDecision;
    case "prepare_final": return ACTION.prepareFinal;
    case "client_returned":
      return item.counts?.changes_total !== undefined && !item.counts.changes_left
        ? (item.counts.changes_ours ? ACTION.prepareReply
          : finalReady(item.counts) ? ACTION.prepareFinal : ACTION.sendToLegal)
        : ACTION.answerChanges;
    default: return ACTION.answerChanges;
  }
}

const EVENT = "legalmind:step";

/** The header's button: ask whichever pane owns the act to do it. */
export function runStep(kind: StepKind): void {
  window.dispatchEvent(new CustomEvent<StepKind>(EVENT, { detail: kind }));
}

/** A pane that owns an act listens for it. */
export function useStep(kind: StepKind, handler: () => void): void {
  useEffect(() => {
    const listen = (event: Event) => { if ((event as CustomEvent<StepKind>).detail === kind) handler(); };
    window.addEventListener(EVENT, listen);
    return () => window.removeEventListener(EVENT, listen);
  }, [kind, handler]);
}
