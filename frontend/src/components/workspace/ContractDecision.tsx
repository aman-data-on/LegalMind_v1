"use client";

/**
 * The decision on the whole contract — AM-174 (owner, 2026-10-22).
 *
 * Opens once every point is decided. The code SUGGESTS an outcome from the point
 * decisions and pre-selects it; only a `legal.decision` holder records one, with a
 * reason (rule 13). No optimistic UI: the line changes only when the server says so,
 * and a version clash reloads what was recorded meanwhile.
 */
import { useCallback, useEffect, useId, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import { CONTRACT_OUTCOME_LABELS, contractOutcomeLabel } from "@/lib/labels";
import { LEGAL_DECISION } from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ContractOutcome, ContractOutcomeState } from "@/lib/types";

const ORDER: ContractOutcome[] = ["SIGN_AS_IS", "SIGN_WITH_CHANGES", "DO_NOT_SIGN", "ON_HOLD"];

const day = (iso: string | null) => iso
  ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
  : "";

export function ContractDecision({ reviewId, reviewStatus, refreshKey, onRecorded }: {
  reviewId: string;
  reviewStatus: string;
  /** changes whenever a point decision changes, so readiness is re-read */
  refreshKey: string;
  onRecorded?: () => void;
}) {
  const { identity } = useSession();
  const canDecide = (identity?.permissions ?? []).includes(LEGAL_DECISION);
  const [state, setState] = useState<ContractOutcomeState | null>(null);
  const [editing, setEditing] = useState(false);
  const [choice, setChoice] = useState<ContractOutcome | null>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = useId();

  // nothing to show is safer than a guess, so a failure reads as null
  const fetchState = useCallback(
    () => api.reviewOutcome(reviewId).catch(() => null), [reviewId]);

  useEffect(() => {
    let cancelled = false;
    void fetchState().then((value) => { if (!cancelled) setState(value); });
    return () => { cancelled = true; };
  }, [fetchState, refreshKey, reviewStatus]);

  if (!state || (!state.ready && state.history.length === 0 && !error)) return null;
  const current = state.history.at(-1) ?? null;
  const closed = reviewStatus === "CLOSED";
  const options = closed ? ORDER.filter((o) => o !== "ON_HOLD") : ORDER;
  const showForm = canDecide && state.ready && (editing || current === null);
  const selected = choice ?? (current?.outcome !== "ON_HOLD" && current ? current.outcome : state.suggested);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!reason.trim()) { setError("Give the reason for this decision."); return; }
    setBusy(true);
    setError(null);
    try {
      setState(await api.recordOutcome(reviewId, {
        outcome: selected, justification: reason.trim(),
        expected_version: state?.history.length ?? 0 }));
      setEditing(false);
      setChoice(null);
      setReason("");
      onRecorded?.();
    } catch (err) {
      if (err instanceof ApiError && err.code === "REVIEW_READ_ONLY") {
        // QA-022: archived, or a newer version analysed — the server says which
        setError(`No decision can be recorded here: ${err.message}.`);
        setState((await fetchState()) ?? state);
      } else if (err instanceof ApiError && err.status === 409) {
        // QA-022: never leave the reader one click from overwriting what they have not seen
        setEditing(false);
        setChoice(null);
        setReason("");
        setError("Another reviewer recorded a decision on this contract meanwhile — it is "
                 + "shown above. Read it before you change it.");
        setState((await fetchState()) ?? state);
      } else {
        setError(describeError(err));
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ws-contract" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} className="ws-contract__title">Decision on this contract</h3>
      {current ? (
        <p className="ws-decision__done">
          <strong>{contractOutcomeLabel(current.outcome)}</strong>
          {" — "}{current.decided_by_name ?? "a reviewer"}, {day(current.decided_at)}
          {": “"}{current.justification}{"”"}
        </p>
      ) : canDecide ? null : (
        <p className="ws-pane__note">Every point is decided. A reviewer records what to do with
          the contract.</p>
      )}
      {state.read_only && !error ? (
        <p className="ws-pane__note">No decision can be recorded here: {state.read_only}.</p>
      ) : null}
      {current && canDecide && state.ready && !editing ? (
        <button type="button" className="ws-btn" onClick={() => setEditing(true)}>
          Change the decision on the contract
        </button>
      ) : null}
      {showForm ? (
        <form className="ws-decision__form" onSubmit={submit} noValidate>
          <fieldset className="ws-contract__options">
            <legend>What should we do with this contract?</legend>
            {options.map((o) => (
              <label key={o} className="ws-contract__option">
                <input type="radio" name={`${id}-outcome`} value={o}
                       checked={selected === o} onChange={() => setChoice(o)} />
                <span>{CONTRACT_OUTCOME_LABELS[o]}</span>
                {o === state.suggested ? (
                  <span className="ws-contract__hint">Suggested from the point decisions</span>
                ) : null}
              </label>
            ))}
          </fieldset>
          <label>
            <span>Reason (required)</span>
            <textarea value={reason} rows={3} required aria-invalid={error !== null && !reason.trim()}
                      aria-describedby={error ? `${id}-err` : undefined}
                      onChange={(e) => setReason(e.target.value)} />
          </label>
          <div className="ws-contract__actions">
            <button type="submit" className="ws-btn ws-btn--primary" disabled={busy}>
              {busy ? "Recording…" : "Record the decision"}
            </button>
            {editing ? (
              <button type="button" className="ws-btn" disabled={busy}
                      onClick={() => { setEditing(false); setChoice(null); setError(null); }}>
                Cancel
              </button>
            ) : null}
          </div>
        </form>
      ) : null}
      {error ? <p id={`${id}-err`} className="ws-pane__note" role="alert">{error}</p> : null}
    </section>
  );
}
