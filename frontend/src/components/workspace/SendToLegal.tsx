"use client";

import { useCallback, useId, useRef, useState } from "react";

import { api, describeError } from "@/lib/api";
import { useStep } from "@/lib/nextStep";
import { BRIEF_COPY } from "@/lib/labels";
import type { ReviewAssignments } from "@/lib/types";
import { Dialog } from "@/components/Dialog";

import { useMinWidth } from "./WorkspaceLayout";

/** Send to Legal (AB-100): a button that opens a picker of the people who may review —
 *  never a styled native select (MED 8). The list is the server's (only people holding
 *  both legal roles, never the owner); the server checks the send again. */
export function SendToLegal({ reviewId, data, onChange, label, primary = false }: {
  reviewId: string; data: ReviewAssignments; onChange: (next: ReviewAssignments) => void;
  label: string; primary?: boolean;
}) {
  const [open, setOpen] = useState(false);
  // AB-213 D3: nobody preselected — the owner picks the lawyer
  const [pick, setPick] = useState("");
  // AM-473: a re-send starts from the last note — never an empty field that drops it
  const last = data.notes?.[0]?.note ?? "";
  const [note, setNote] = useState(last);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useStep("sendToLegal", useCallback(() => setOpen(true), []));
  // W1 r2 (M2): on the phone workspace the picker is a modal sheet (focus kept in it, Esc,
  // focus back on the button); on a wide screen it stays the popover under the button
  const sheet = useMinWidth(900) === false;
  const titleId = useId();
  const opener = useRef<HTMLButtonElement>(null);
  const send = async () => {
    setBusy(true);
    setError(null);
    try {
      const got = await api.sendForReview(reviewId, pick, note);
      onChange({ ...data, ...got });
      setOpen(false);
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  };
  const form = (
    <>
      <fieldset>
        <legend>Who reviews it</legend>
        {data.eligible.map((person, i) => (
          <label key={person.user_id}>
            <input type="radio" name="lm-sendlegal" value={person.user_id} checked={pick === person.user_id}
                   autoFocus={i === 0} onChange={() => setPick(person.user_id)} />
            <span className="lm-sendlegal__who">
              {person.name || person.email}
              {person.name ? <small>{person.email}</small> : null}
            </span>
          </label>
        ))}
      </fieldset>
      <label className="lm-sendlegal__note">
        <span>Note for Legal (optional)</span>
        <textarea rows={3} maxLength={2000} value={note} aria-describedby={last ? "lm-sendlegal-last" : undefined}
                  onChange={(e) => setNote(e.target.value)} />
        {last ? <span id="lm-sendlegal-last">{BRIEF_COPY.lastNoteFilled}</span> : null}
      </label>
      {error ? <p className="cx-error" role="alert">{error}</p> : null}
      <div className="lm-sendlegal__foot">
        <button type="button" className="ws-btn ws-btn--sm" onClick={() => setOpen(false)}>Cancel</button>
        <button type="button" className="ws-btn ws-btn--sm ws-btn--primary" disabled={busy || !pick}
                onClick={() => void send()}>
          {busy ? "Sending…" : label}
        </button>
      </div>
    </>
  );
  return (
    <span className="lm-sendlegal"
          onKeyDown={(event) => {
            // M2-3 (M-18): Escape closes the picker and hands focus back to its button
            if (event.key === "Escape" && open) { event.stopPropagation(); setOpen(false); opener.current?.focus(); }
          }}>
      <button ref={opener} type="button" className={`ws-btn ws-btn--sm${primary ? " ws-btn--primary" : ""}`}
              aria-expanded={open} aria-controls="lm-sendlegal" onClick={() => setOpen((v) => !v)}>
        {label}
      </button>
      {open && sheet ? (
        <Dialog onClose={() => setOpen(false)} titleId={titleId} overlayClassName="lm-sendsheet"
                dismissOnScrimClick={false} returnFocus={() => opener.current}>
          <h2 id={titleId} className="lm-sendsheet__title">{label}</h2>
          <div className="lm-sendlegal__pop" data-sheet="">{form}</div>
        </Dialog>
      ) : open ? (
        <div className="lm-sendlegal__pop" id="lm-sendlegal" role="dialog" aria-label={label}>{form}</div>
      ) : null}
    </span>
  );
}
