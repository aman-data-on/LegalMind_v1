"use client";

import { useCallback, useState } from "react";

import { api, describeError } from "@/lib/api";
import { useStep } from "@/lib/nextStep";
import { BRIEF_COPY } from "@/lib/labels";
import type { ReviewAssignments } from "@/lib/types";

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
  return (
    <span className="lm-sendlegal"
          onKeyDown={(event) => { if (event.key === "Escape" && open) { event.stopPropagation(); setOpen(false); } }}>
      <button type="button" className={`ws-btn ws-btn--sm${primary ? " ws-btn--primary" : ""}`}
              aria-expanded={open} aria-controls="lm-sendlegal" onClick={() => setOpen((v) => !v)}>
        {label}
      </button>
      {open ? (
        <div className="lm-sendlegal__pop" id="lm-sendlegal" role="dialog" aria-label={label}>
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
        </div>
      ) : null}
    </span>
  );
}
