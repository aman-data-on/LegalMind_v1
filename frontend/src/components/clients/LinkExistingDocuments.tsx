"use client";

/**
 * Link a document that is ALREADY in LegalMind to this client.
 *
 * This is the answer to the owner's requirement that "existing documents should
 * continue to work" and that nobody should have to upload the same document a
 * second time because Client Profiles arrived. It creates nothing: the one
 * write is `PATCH /contracts/{id}` setting `counterparty_id`, which is the same
 * call the Dashboard's edit dialog has made since AB-13.
 *
 * **Deterministic, never inferred.** The list offered is exactly the caller's
 * own unlinked documents (`?counterparty_id=none`), in their own words, and
 * nothing is matched for them by name, party extraction or any model. The owner
 * was explicit: explicit user selection takes priority, and a document must
 * never be silently associated with the wrong company. So this screen asks, and
 * a document nobody links stays unlinked — which is an honest state, not a gap.
 */

import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import type { Contract, Counterparty } from "@/lib/types";

import { shortDate } from "./model";

export function LinkExistingDocuments({ client, onClose, onLinked }: {
  client: Counterparty;
  onClose: () => void;
  onLinked: () => void | Promise<void>;
}) {
  const [candidates, setCandidates] = useState<Contract[] | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [linking, setLinking] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.contracts(1, 100, {
        counterparty_id: "none",
        ...(q.trim() ? { q: q.trim() } : {}),
      });
      setCandidates(result.items);
    } catch (cause) {
      setError(cause);
    }
  }, [q]);

  // Debounced, like every other search box in the app: one request per pause,
  // not one per keystroke.
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 250);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function link(contract: Contract) {
    setLinking(contract.id);
    setError(null);
    try {
      await api.updateContract(contract.id, { counterparty_id: client.id });
      await onLinked();
      await load();
    } catch (cause) {
      setError(cause);
    } finally {
      setLinking(null);
    }
  }

  return (
    <section className="ws-cl__link" aria-labelledby="ws-cl-link-title">
      <header className="ws-cl__link-head">
        <h3 id="ws-cl-link-title">Link an existing document</h3>
        <span className="ws-cl__spacer" />
        <button type="button" className="ws-btn ws-btn--sm" onClick={onClose}>
          Close
        </button>
      </header>
      <p className="ws-pane__note">
        Documents already in LegalMind that are not yet filed under a client.
        Linking one moves nothing and copies nothing — it records who the
        document is with.
      </p>

      <label className="ws-field">
        <span className="ws-visually-hidden">Search your unlinked documents</span>
        <input value={q} onChange={(event) => setQ(event.target.value)}
               placeholder="Search documents…" maxLength={200} />
      </label>

      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}

      {candidates === null ? (
        <p className="ws-pane__note" role="status" aria-live="polite">Loading…</p>
      ) : candidates.length === 0 ? (
        <p className="ws-pane__note">
          {q.trim()
            ? "No unlinked documents match that."
            : "Every document you can see is already filed under a client."}
        </p>
      ) : (
        <ul className="ws-cl__linklist">
          {candidates.map((contract) => (
            <li key={contract.id}>
              <span className="ws-cl__linkname">{contract.name}</span>
              {contract.contract_type ? (
                <span className="ws-chip ws-chip--type">{contract.contract_type}</span>
              ) : null}
              <span className="ws-cl__linkwhen">
                {shortDate(contract.created_at) ?? ""}
              </span>
              <button type="button" className="ws-btn ws-btn--sm"
                      disabled={linking === contract.id}
                      onClick={() => void link(contract)}>
                {linking === contract.id ? "Linking…" : "Link"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
