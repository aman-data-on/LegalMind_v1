"use client";

/**
 * S5 (`FINAL-PACKAGE-SPEC` d3): the client's paper converts to ours. The person fills in
 * our contract (New contract, `?convert=`), comes back here with the draft, and the
 * server's dry run says what carries over: each accepted point, word for word, as an
 * entry of Annexure 2. A point with no clause of ours to go with asks where it is added.
 * Everything that decides is the server's (rule 18).
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "@/components/Feedback";
import { toast } from "@/components/Toast";
import { ApiError, api, describeError } from "@/lib/api";
import { CONVERT_COPY } from "@/lib/labels";
import { type ConvertPlan, blockerText, clauseName, entryAction } from "@/lib/package";

type Load = { kind: "loading" } | { kind: "ready"; plan: ConvertPlan } | { kind: "error"; error: unknown };

export function ConvertPaper({ contractId, draftId, onPick, onConverted }: {
  contractId: string;
  /** the person's New-contract draft, back from `?convert=` */
  draftId: string | null;
  onPick: (rowKey: string) => void;
  onConverted: () => void;
}) {
  const [addAfter, setAddAfter] = useState<Record<string, string>>({});
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  useEffect(() => {
    if (!draftId) return;
    let live = true;
    setLoad({ kind: "loading" });
    api.convertPreview(contractId, draftId, addAfter).then(
      (plan) => { if (live) setLoad({ kind: "ready", plan }); },
      (error: unknown) => { if (live) setLoad({ kind: "error", error }); });
    return () => { live = false; };
  }, [contractId, draftId, addAfter, attempt]);

  async function convert(plan: ConvertPlan) {
    if (!draftId || !plan.entries_sha256) return;
    setBusy(true);
    setRefused(null);
    try {
      await api.convert(contractId, draftId, addAfter, plan.entries_sha256);
      toast(CONVERT_COPY.done);
      onConverted();
    } catch (cause) {
      setRefused(describeError(cause));
      if (cause instanceof ApiError && cause.isConflict) setAttempt((n) => n + 1);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="lm-pkg" aria-labelledby="lm-convert-title">
      <h2 id="lm-convert-title" className="lm-pkg__title">{CONVERT_COPY.title}</h2>
      <p className="lm-pkg__lead"><strong>{CONVERT_COPY.carryOver}</strong></p>
      {!draftId ? (
        <>
          <p className="lm-pkg__lead">{CONVERT_COPY.lead}</p>
          <p><Link className="ws-btn" href={`/contracts/new?convert=${encodeURIComponent(contractId)}`}>{CONVERT_COPY.start}</Link></p>
        </>
      ) : null}
      {draftId && load.kind === "loading" ? <LoadingState label={CONVERT_COPY.checking} /> : null}
      {draftId && load.kind === "error" ? (
        <ErrorState title={CONVERT_COPY.failed} error={load.error} onRetry={() => setAttempt((n) => n + 1)} />
      ) : null}
      {draftId && load.kind === "ready" ? (
        <ConvertBody plan={load.plan} addAfter={addAfter} busy={busy} onPick={onPick}
                     setAnchor={(row, key) => setAddAfter((was) => ({ ...was, [row]: key }))}
                     onConvert={() => void convert(load.plan)} />
      ) : null}
      {refused ? <p className="cx-error" role="alert">{refused}</p> : null}
    </section>
  );
}

/** The dry run said in plain words — exported for the test. */
export function ConvertBody({ plan, addAfter, busy, onPick, setAnchor, onConvert }: {
  plan: ConvertPlan; addAfter: Record<string, string>; busy: boolean;
  onPick: (rowKey: string) => void; setAnchor: (row: string, key: string) => void; onConvert: () => void;
}) {
  return (
    <>
      {plan.entries.length ? (
        <>
          <p className="lm-pkg__lead">{CONVERT_COPY.carried(plan.entries.length)}</p>
          <ol className="lm-convert__entries">
            {plan.entries.map((e) => (
              <li key={e.n}><strong>{clauseName(e.target, e.new_number)}</strong>. {entryAction(e)}.</li>
            ))}
          </ol>
        </>
      ) : null}
      {plan.blockers.length ? (
        <>
          <p className="lm-pkg__lead">{CONVERT_COPY.blocked}</p>
          <ul className="lm-pkg__blockers">
            {plan.blockers.map((b, i) => (
              <li key={i}>
                {b.row_key ? <button type="button" className="ws-escalate__link" onClick={() => onPick(b.row_key!)}>
                  {blockerText(b)}</button> : blockerText(b)}
                {b.code === "ANCHOR_REQUIRED" && b.row_key ? (
                  <label className="lm-convert__anchor">
                    <span>{CONVERT_COPY.addAfter}</span>
                    <select value={addAfter[b.row_key] ?? ""} onChange={(ev) => setAnchor(b.row_key!, ev.target.value)}>
                      <option value="" disabled>{CONVERT_COPY.choose}</option>
                      {plan.choices.map((c) => (
                        <option key={c.key} value={c.key}>{clauseName(c)}</option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </li>
            ))}
          </ul>
        </>
      ) : null}
      {plan.available ? (
        <p>
          <button type="button" className="ws-btn ws-btn--primary" disabled={busy} aria-busy={busy || undefined} onClick={onConvert}>
            {busy ? CONVERT_COPY.converting : CONVERT_COPY.convert}
          </button>
        </p>
      ) : null}
    </>
  );
}
