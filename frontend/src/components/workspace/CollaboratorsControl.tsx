"use client";

/**
 * Who works on this contract — `AM-259` (AB-150, R10). Collaborators answer the
 * client's changes and upload returned versions beside the owner; they never decide,
 * transfer, archive or delete. Only the owner or their Department Lead changes the
 * list, and only colleagues in the owner's department are offered — the server decides
 * all of it (`can_manage`, `candidates`); this screen only shows what it was given.
 */
import { useEffect, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { api, describeError, type Collaborators } from "@/lib/api";

import { IconUsers } from "./icons";

export function CollaboratorsControl({ contractId }: { contractId: string }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState<Collaborators | null>(null);
  const [pick, setPick] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.collaborators(contractId).then(setState).catch(() => setState(null));
  }, [contractId]);

  const count = state?.collaborators.length ?? 0;
  if (!state || (!count && !state.can_manage)) return null;

  async function change(run: () => Promise<Collaborators>) {
    setBusy(true);
    setError(null);
    try {
      setState(await run());
      setPick("");
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button type="button" className="ws-btn ws-collab__toggle" onClick={() => setOpen(true)}
              aria-label={count ? `${count} colleague${count > 1 ? "s" : ""} on this contract` : "Add a colleague"}>
        <IconUsers size={15} />
        {count ? `${count} colleague${count > 1 ? "s" : ""}` : "Add colleague"}
      </button>
      {open ? (
        <Dialog onClose={() => setOpen(false)} titleId="ws-collab-title">
          <h2 id="ws-collab-title">Colleagues on this contract</h2>
          <p className="ws-pane__note ws-collab__intro">
            Colleagues can answer the client&apos;s changes and upload returned versions. Only the owner can decide, transfer, archive or delete.
          </p>
          {count === 0 ? (
            <p className="ws-collab__empty">Only the owner is working on this contract.</p>
          ) : (
            <ul className="ws-collab__list">
              {state.collaborators.map((p) => (
                <li key={p.id}>
                  <span>{p.name}<span className="ws-collab__email">{p.email}</span></span>
                  {state.can_manage ? (
                    <button type="button" className="ws-escalate__link" disabled={busy}
                            onClick={() => void change(() => api.removeCollaborator(contractId, p.id))}>
                      Remove
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          {state.can_manage ? (
            state.candidates.length ? (
              <form className="ws-collab__add" onSubmit={(e) => {
                e.preventDefault();
                if (pick) void change(() => api.addCollaborator(contractId, pick));
              }}>
                <label htmlFor="ws-collab-pick">Add a colleague from the owner&apos;s department</label>
                <div>
                  <select id="ws-collab-pick" value={pick} onChange={(e) => setPick(e.target.value)}>
                    <option value="">Choose a colleague</option>
                    {state.candidates.map((p) => (
                      <option key={p.id} value={p.id}>{p.name} — {p.email}</option>
                    ))}
                  </select>
                  <button type="submit" className="ws-btn ws-btn--primary" disabled={!pick || busy}>
                    Add
                  </button>
                </div>
              </form>
            ) : (
              <p className="ws-pane__note">Everyone in the owner&apos;s department is already on it.</p>
            )
          ) : null}
          {error ? <p className="ws-pane__note" role="alert">{error}</p> : null}
          <div className="ws-collab__foot">
            <button type="button" className="ws-btn" onClick={() => setOpen(false)}>Done</button>
          </div>
        </Dialog>
      ) : null}
    </>
  );
}
