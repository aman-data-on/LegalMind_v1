"use client";

/**
 * The end of the deal cycle — `AM-318` (owner, 2026-11-06): the deal ends at the final
 * clean copy; stamping and signing happen in another tool.
 *
 *   PrepareFinal  "Prepare final contract" where no Annexure package applies (client
 *                 paper, a client who accepted our version unchanged, a template without
 *                 Annexure A, a tracked-changes round): the server's dry run, then the copy
 *   FinalCard     Document tab once Legal recorded Sign as is on the final contract
 *   ClosedPanel   the Changes and Points tabs of a Final deal: one closed state
 *
 * Everything that decides is the server's; these only show it (rule 18).
 */

import { useCallback, useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { ApiError, api, describeError } from "@/lib/api";
import { ANSWER_LABEL, type Answer } from "@/lib/changes";
import { formatDate } from "@/lib/dates";
import { ACTION, contractOutcomeLabel } from "@/lib/labels";
import { useStep } from "@/lib/nextStep";
import type { ContractOutcomeState, DocumentVersion, FinalCopyPlan } from "@/lib/types";

import { ReplyDownloads } from "./ChangesPane";
import { useFindingsStateOptional } from "./findingsState";
import { SpecialConditionsTrace } from "./Package";
import "./final.css";

const NEXT = "Sign it in your signing tool. Nothing more is needed here. If the client asks "
  + "for another change, upload their version and the negotiation reopens.";

export function PrepareFinal({ contractId, nextVersion, onPrepared }: {
  contractId: string; nextVersion: number; onPrepared: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [plan, setPlan] = useState<FinalCopyPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [blockers, setBlockers] = useState<{ message?: string }[]>([]);
  useStep("prepareFinal", useCallback(() => {
    setPlan(null);
    setError(null);
    setBlockers([]);
    setOpen(true);
  }, []));
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api.finalCopyPlan(contractId).then((got) => { if (!cancelled) setPlan(got); },
                                       (cause: unknown) => { if (!cancelled) setError(describeError(cause)); });
    return () => { cancelled = true; };
  }, [open, contractId]);
  if (!open) return null;
  const close = () => { if (!busy) setOpen(false); };
  async function prepare() {
    setBusy(true);
    setError(null);
    try {
      await api.prepareFinalCopy(contractId);
      setOpen(false);
      onPrepared();
    } catch (cause) {
      setError(describeError(cause));
      if (cause instanceof ApiError && cause.blockers) setBlockers(cause.blockers);
    } finally {
      setBusy(false);
    }
  }
  const shown = blockers.length ? blockers : plan?.blockers ?? [];
  return (
    <Dialog onClose={close} titleId="lm-final-title">
      <h2 id="lm-final-title">{ACTION.prepareFinal}</h2>
      {plan === null && !error ? <p className="ws-pane__note" role="status">Checking…</p> : null}
      {plan?.available && !blockers.length ? (
        <p className="lm-pkg__body">
          This makes version {nextVersion}: a clean copy of version {plan.of_version}
          {plan.mode === "reply" ? " with every answer applied" : ""}, every tracked change accepted and every
          comment removed. It is reviewed like any upload; then Legal records the decision on the contract.
          {plan.mode === "copy" && plan.agreed.length === 0
            ? " Use this when the client accepted the version as it is. If they sent changes, upload their version instead."
            : ""}
        </p>
      ) : null}
      {shown.length ? (
        <div className="cx-blocked" role="alert">
          <p className="cx-blocked__title">The final contract cannot be prepared yet.</p>
          <ul className="lm-pkg__blockers">{shown.map((b, i) => <li key={i}>{b.message}</li>)}</ul>
        </div>
      ) : error ? <p className="cx-error" role="alert">{error}</p> : null}
      <div className="cx-dialog__foot">
        <button type="button" className="ws-btn" disabled={busy} onClick={close}>Cancel</button>
        {plan?.available && !blockers.length ? (
          <button type="button" className="ws-btn ws-btn--primary" disabled={busy} aria-busy={busy}
                  onClick={() => void prepare()}>
            {busy ? "Preparing…" : ACTION.prepareFinal}
          </button>
        ) : null}
      </div>
    </Dialog>
  );
}

/** "Final contract ready for signature" — the version, Legal's decision, the files, what
 *  was agreed, and the one next step (GOV.UK confirmation-page pattern). */
export function FinalCard({ version, versions, since }: {
  version: DocumentVersion; versions: DocumentVersion[]; since: string;
}) {
  const findings = useFindingsStateOptional();
  const reviewId = findings && findings.state.kind === "ready" ? findings.state.review.id : null;
  const [outcome, setOutcome] = useState<ContractOutcomeState | null>(null);
  useEffect(() => {
    if (!reviewId) return;
    let cancelled = false;
    api.reviewOutcome(reviewId).then((got) => { if (!cancelled) setOutcome(got); }, () => undefined);
    return () => { cancelled = true; };
  }, [reviewId]);
  const decided = outcome?.history.at(-1);
  const of = version.final_copy?.of_version_id ?? version.package?.of_version_id;
  const from = versions.find((v) => v.id === of);
  const agreed = version.final_copy?.agreed ?? [];
  return (
    <section className="ws-replynote lm-final" aria-labelledby="lm-final-card">
      <div className="ws-replynote__text">
        <h2 id="lm-final-card" className="ws-replynote__title">Final contract ready for signature</h2>
        <p className="ws-replynote__sub">
          Version {version.version_number}
          {from ? `, made from version ${from.version_number}` : ""}.{" "}
          {decided ? <>Legal recorded <strong>{contractOutcomeLabel(decided.outcome)}</strong>
            {decided.decided_by_name ? ` (${decided.decided_by_name})` : ""} on {formatDate(decided.decided_at ?? since)}.</>
            : <>Final since {formatDate(since)}.</>}
        </p>
        <p className="ws-replynote__sub">{NEXT}</p>
      </div>
      <div className="ws-replynote__acts">
        <ReplyDownloads version={version} pdf="pdf" word={version.mime_type !== "application/pdf"} />
      </div>
      {version.package ? (
        <SpecialConditionsTrace versionId={version.id} count={version.package.special_conditions}
                                instrument={version.package.form === "changes_only"}
                                summary={`What was agreed (${version.package.special_conditions})`} />
      ) : agreed.length ? (
        <details className="lm-pkgtrace">
          <summary>What was agreed ({agreed.length})</summary>
          <ul className="lm-final__agreed">
            {agreed.map((a, i) => (
              <li key={i}><span>{a.where.charAt(0).toUpperCase() + a.where.slice(1)}</span>
                {" — "}{ANSWER_LABEL[a.answer as Answer] ?? a.answer}</li>
            ))}
          </ul>
        </details>
      ) : (
        <p className="ws-replynote__sub">What was agreed (0): the client accepted
          {from ? ` version ${from.version_number}` : " our version"} as it was.</p>
      )}
    </section>
  );
}

/** One closed state for a Final deal's Changes and Points tabs — never a row of zero chips.
 *  The points stay one click away for anyone who wants the record. */
export function ClosedPanel({ what, children }: { what: "changes" | "points"; children?: React.ReactNode }) {
  const [show, setShow] = useState(false);
  if (show && children) return <>{children}</>;
  return (
    <section className="ws-state lm-closed" aria-label={what === "changes" ? "Changes" : "Points"}>
      <h2>Nothing left to do</h2>
      <p>
        {what === "changes"
          ? "Every change was answered and the final contract is ready. If the client asks for another change, upload their version and the negotiation reopens."
          : "Every point was decided and Legal recorded the decision on the final contract."}
      </p>
      {children ? (
        <button type="button" className="ws-btn ws-btn--sm" onClick={() => setShow(true)}>Show the points</button>
      ) : null}
    </section>
  );
}
