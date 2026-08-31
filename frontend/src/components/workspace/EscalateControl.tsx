"use client";

/**
 * Escalation — a request for review, never an approval, and it records no
 * decision (locked Step 4, ROLE-04, F-3, AM-23). Visually quiet on purpose
 * (master prompt: "decision authority is visually distinct from decision-
 * adjacent activity") — an underline link, never a button that could be
 * mistaken for the one control that changes the legal record.
 */

import { useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { api } from "@/lib/api";
import type { Finding } from "@/lib/types";

export function EscalateControl({
  finding,
  onChanged,
}: {
  finding: Finding;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function escalate(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.escalate(finding.id, reason);
      setReason("");
      setOpen(false);
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  async function withdraw() {
    setBusy(true);
    setError(null);
    try {
      await api.withdrawEscalation(finding.id);
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="ws-escalate">
      <ErrorBanner error={error} />
      {finding.escalated ? (
        <p>
          Escalated for authorized review — a request, not an approval.{" "}
          <button type="button" className="ws-escalate__link" onClick={() => void withdraw()} disabled={busy}>
            Withdraw
          </button>
        </p>
      ) : open ? (
        <form onSubmit={escalate}>
          <label className="ws-visually-hidden" htmlFor={`escalate-${finding.id}`}>
            Why does this need authorized review?
          </label>
          <input
            id={`escalate-${finding.id}`}
            type="text"
            required
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Why does this need authorized review?"
            disabled={busy}
          />
          <button type="submit" className="ws-btn" disabled={busy}>
            {busy ? "Escalating…" : "Escalate"}
          </button>
          <button type="button" className="ws-escalate__link" onClick={() => setOpen(false)} disabled={busy}>
            Cancel
          </button>
        </form>
      ) : (
        <button type="button" className="ws-escalate__link" onClick={() => setOpen(true)}>
          Escalate for authorized review
        </button>
      )}
    </div>
  );
}
