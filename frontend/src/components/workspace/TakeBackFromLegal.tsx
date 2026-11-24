"use client";

import { useId, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { toast } from "@/components/Toast";
import { ApiError, api, describeError } from "@/lib/api";
import { TAKE_BACK_COPY as COPY } from "@/lib/labels";
import type { ReviewAssignments } from "@/lib/types";

/** UI-02: "Take back" (withdraw the review from its Legal holder) asks first — it undoes
 *  the hand-off. Cancel, then the verb; the error stays in the dialog; a toast confirms.
 *  U2 (UI-13): its trigger is an item of the header's ⋯ menu, which closes on a click — so
 *  the dialog is held by the header, open while `open`, and focus goes back to ⋯.
 *  Presentation only: the server checks the withdrawal again (rule 18). */
export function TakeBackFromLegal({ reviewId, holder, onClose, onDone, returnFocus }: {
  reviewId: string; holder: { user_id: string; name?: string | null; email: string };
  onClose: () => void;
  /** resolves once the page has re-read the contract (its stage, so the brief) */
  onDone: (got: Pick<ReviewAssignments, "assigned" | "notes">) => Promise<void>;
  returnFocus: () => HTMLElement | null;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();
  const close = () => { if (!busy) onClose(); };
  const takeBack = async () => {
    setBusy(true);
    setError(null);
    try {
      const got = await api.withdrawReview(reviewId, holder.user_id);
      onClose();
      toast(COPY.done);
      await onDone(got);              // the re-read keeps the last counts on a failure
    } catch (cause) {
      setError(cause instanceof ApiError && cause.code === "CONFLICT" ? COPY.gone : describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog onClose={close} titleId={titleId} returnFocus={returnFocus}>
      <h2 id={titleId}>{COPY.title}</h2>
      <p className="ws-modal__body">{COPY.body(holder.name || holder.email)}</p>
      {error ? <p className="cx-error" role="alert">{error}</p> : null}
      <div className="ws-modal__acts">
        <button type="button" className="ws-btn" disabled={busy} onClick={close}>{COPY.cancel}</button>
        <button type="button" className="ws-btn ws-btn--primary" disabled={busy} aria-busy={busy}
                onClick={() => void takeBack()}>{busy ? COPY.busy : COPY.confirm}</button>
      </div>
    </Dialog>
  );
}
