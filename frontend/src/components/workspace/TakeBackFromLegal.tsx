"use client";

import { useId, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { toast } from "@/components/Toast";
import { ApiError, api, describeError } from "@/lib/api";
import { TAKE_BACK_COPY as COPY } from "@/lib/labels";
import type { ReviewAssignments } from "@/lib/types";

/** UI-02: "Take back" (withdraw the review from its Legal holder) asks first — it undoes
 *  the hand-off. Cancel, then the verb; the error stays in the dialog; a toast confirms.
 *  Presentation only: the server checks the withdrawal again (rule 18). */
export function TakeBackFromLegal({ reviewId, holder, onDone }: {
  reviewId: string; holder: { user_id: string; name?: string | null; email: string };
  /** resolves once the page has re-read the contract (its stage, so the brief) */
  onDone: (assigned: ReviewAssignments["assigned"]) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const titleId = useId();
  const trigger = useRef<HTMLButtonElement>(null);     // focus comes back here on close
  const close = () => { if (!busy) { setOpen(false); setError(null); } };
  const takeBack = async () => {
    setBusy(true);
    setError(null);
    try {
      const { assigned } = await api.withdrawReview(reviewId, holder.user_id);
      setOpen(false);
      toast(COPY.done);
      // the trigger is gone with the holder: focus the page's heading, never the body (D3)
      await onDone(assigned);              // the re-read keeps the last counts on a failure
      const heading = document.querySelector<HTMLElement>("h1");
      if (heading) { heading.tabIndex = -1; heading.focus(); }
    } catch (cause) {
      setError(cause instanceof ApiError && cause.code === "CONFLICT" ? COPY.gone : describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <button ref={trigger} type="button" className="ws-linkbtn" onClick={() => setOpen(true)}>{COPY.open}</button>
      {open ? (
        <Dialog onClose={close} titleId={titleId} returnFocus={() => trigger.current}>
          <h2 id={titleId}>{COPY.title}</h2>
          <p className="ws-modal__body">{COPY.body(holder.name || holder.email)}</p>
          {error ? <p className="cx-error" role="alert">{error}</p> : null}
          <div className="ws-modal__acts">
            <button type="button" className="ws-btn" disabled={busy} onClick={close}>{COPY.cancel}</button>
            <button type="button" className="ws-btn ws-btn--primary" disabled={busy} aria-busy={busy}
                    onClick={() => void takeBack()}>{busy ? COPY.busy : COPY.confirm}</button>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}
