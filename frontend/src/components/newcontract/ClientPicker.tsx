"use client";

/**
 * Who the contract is with (S5; batch 7 review change 12): a combobox over this person's own
 * clients (AB-13 r6 — there is no global company list). Recent clients first; as they type,
 * the names that match come first, and "Add" carries the typed name. A new client is only
 * its name here: the next step asks the rest, certificate first, onto the client record.
 */

import { useEffect, useId, useState } from "react";

import { api, ApiError, describeError } from "@/lib/api";
import { INTAKE_COPY as C } from "@/lib/labels";
import { clientFieldError } from "@/lib/newContract";
import type { Counterparty } from "@/lib/types";

/** Line 2 of a client: where it is registered, and how many of Legal's details are missing. */
export function clientLine(c: Counterparty, gaps = true): string {
  return [c.registered_office ?? c.city, c.gstin, gaps && C.detailsMissing(c.details_missing ?? 0)].filter(Boolean).join(". ");
}

function NewClient({ named, onAdded, onCancel }: { named: string; onAdded: (c: Counterparty) => void; onCancel: () => void }) {
  const [name, setName] = useState(named);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function add() {
    if (!name.trim()) { setError(clientFieldError("name")); return; }
    setBusy(true); setError(null);
    try { onAdded(await api.createCounterparty({ name: name.trim() })); }
    catch (e) { setError(e instanceof ApiError && e.fields?.length ? clientFieldError("name") : describeError(e)); }
    finally { setBusy(false); }
  }
  return (
    <div className="nc-newclient" role="group" aria-labelledby="nc-newclient-title">
      <h3 id="nc-newclient-title" className="nc-sub">{C.addTitle}</h3>
      <div className="nc-q">
        <label className="nc-q__label" htmlFor="nc-client-name">{C.addName}</label>
        <p id="nc-client-name-help" className="nc-q__help">{C.addHelp}</p>
        <input id="nc-client-name" type="text" value={name} autoFocus aria-required
               aria-describedby={`nc-client-name-help${error ? " nc-client-name-err" : ""}`} aria-invalid={error ? true : undefined}
               onChange={(e) => setName(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") void add(); }} />
        {error ? <p id="nc-client-name-err" className="nc-q__error">{error}</p> : null}
      </div>
      <div className="nc-actions">
        <button type="button" className="ws-btn" onClick={onCancel}>{C.cancel}</button>
        <button type="button" className="ws-btn" onClick={() => void add()} disabled={busy}>{C.add}</button>
      </div>
    </div>
  );
}

export function ClientPicker({ value, onChange, disabled = false, showGaps = true }: {
  value: Counterparty | null;
  onChange: (c: Counterparty | null) => void;
  /** batch 5: locked while a file is being sent */
  disabled?: boolean;
  /** batch 5: "N details to add" belongs to the New-contract intake, not to every picker */
  showGaps?: boolean;
}) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Counterparty[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [adding, setAdding] = useState(false);
  const list = useId();

  useEffect(() => {
    if (value || adding) return;
    let live = true;
    const t = setTimeout(() => {
      api.clients(1, 8, q.trim() ? { q: q.trim() } : { sort: "recent_desc" })
        .then((r) => { if (live) { setFound(r.items); setFailed(false); } })
        .catch(() => { if (live) { setFound([]); setFailed(true); } });
    }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [q, value, adding]);

  if (value) {
    return (
      <div className="nc-chosen">
        <div>
          <p className="nc-item__l1">{value.name}</p>
          <p className="nc-item__l2">{clientLine(value, showGaps)}</p>
        </div>
        <button type="button" className="ws-btn ws-btn--sm" disabled={disabled} onClick={() => onChange(null)}>{C.change}</button>
      </div>
    );
  }
  if (adding) return <NewClient named={q.trim()} onAdded={(c) => { setAdding(false); onChange(c); }} onCancel={() => setAdding(false)} />;
  const rows = found ?? [];
  /** arrows move between the results (buttons, so Tab and Enter work as everywhere) */
  function arrows(e: React.KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    const all = [...document.querySelectorAll<HTMLButtonElement>(`[id="${list}"] button`)];
    const at = all.indexOf(document.activeElement as HTMLButtonElement);
    const next = e.key === "ArrowDown" ? Math.min(at + 1, all.length - 1) : at - 1;
    (next < 0 ? document.getElementById("nc-client-search") : all[next])?.focus();
  }
  return (
    <div className="nc-clients" onKeyDown={arrows}>
      <label className="ic-field__label" htmlFor="nc-client-search">{C.search}</label>
      <input id="nc-client-search" className="nc-search" type="search" autoComplete="off" aria-controls={list}
             value={q} onChange={(e) => setQ(e.target.value)} />
      {!q.trim() && rows.length ? <p className="ic-quiet">{C.recent}</p> : null}
      {found === null ? <div className="lm-skel" aria-hidden="true"><span className="lm-skel__row" /><span className="lm-skel__row" /></div> : (
        <ul className="nc-results" id={list} aria-label={C.search} aria-live="polite">
          {rows.map((c) => (
            <li key={c.id}>
              <button type="button" className="nc-item" onClick={() => onChange(c)}>
                <span className="nc-item__l1">{c.name}</span>
                <span className="nc-item__l2">{clientLine(c, showGaps)}</span>
              </button>
            </li>
          ))}
          {!rows.length ? (
            <li className="nc-quiet nc-results__none">
              {failed ? C.clientsFailed : q.trim() ? C.noMatch(q.trim()) : C.noClients}
            </li>
          ) : null}
          <li>
            <button type="button" className="nc-item nc-item--add" onClick={() => setAdding(true)}>
              <span className="nc-item__l1">{q.trim() ? C.addNamed(q.trim()) : C.addNew}</span>
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}
