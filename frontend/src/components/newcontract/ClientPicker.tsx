"use client";

/**
 * Who the contract is with (S5): search this person's own Client Profiles (AB-13 r6 — there
 * is no global company list), or add a new one here with its legal details (`AM-286`).
 * Every detail is typed by a person; the API checks only the shape of a CIN/LLPIN, PAN
 * and GSTIN and names the field it refuses.
 */

import { useEffect, useState } from "react";

import { api, ApiError, describeError } from "@/lib/api";
import { CLIENT_FIELDS, clientFieldError } from "@/lib/newContract";
import type { Counterparty } from "@/lib/types";

/** Line 2 of a client: where it is registered, and its CIN, when anyone typed them. */
export function clientLine(c: Counterparty): string {
  const legal = c as Counterparty & { registered_office?: string; cin_or_llpin?: string };
  return [legal.registered_office ?? c.city, legal.cin_or_llpin].filter(Boolean).join(", ") || "No legal details yet";
}

function NewClient({ onAdded, onCancel }: { onAdded: (c: Counterparty) => void; onCancel: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [failure, setFailure] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [more, setMore] = useState(false);

  function field(f: (typeof CLIENT_FIELDS)[number]) {
    const id = `nc-client-${f.key}`;
    const err = errors[f.key];
    const props = {
      id, value: values[f.key] ?? "",
      onChange: (e: { target: { value: string } }) => setValues((v) => ({ ...v, [f.key]: e.target.value })),
      "aria-describedby": [f.help ? `${id}-help` : "", err ? `${id}-err` : ""].join(" ").trim() || undefined,
      ...(err ? { "aria-invalid": true as const } : {}),
      ...(f.key === "name" ? { "aria-required": true as const } : {}),
    };
    return (
      <div key={f.key} className="nc-q" data-wide={f.wide || undefined}>
        <label className="nc-q__label" htmlFor={id}>
          {f.label}{f.key === "name" ? null : <span className="nc-q__req">Optional</span>}
        </label>
        {f.help ? <p id={`${id}-help`} className="nc-q__help">{f.help}</p> : null}
        {f.area ? <textarea rows={2} {...props} /> : <input type={f.key === "notice_email" ? "email" : "text"} {...props} />}
        {err ? <p id={`${id}-err`} className="nc-q__error">{err}</p> : null}
      </div>
    );
  }

  async function add() {
    if (!values.name?.trim()) { setErrors({ name: clientFieldError("name") }); return; }
    setBusy(true); setErrors({}); setFailure(null);
    const body = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()));
    try {
      onAdded(await api.createCounterparty(body));
    } catch (e) {
      if (e instanceof ApiError && e.fields?.length) {
        setErrors(Object.fromEntries(e.fields.map((f) => [f.field, clientFieldError(f.field)])));
        if (e.fields.some((f) => !CLIENT_FIELDS.find((c) => c.key === f.field)?.first)) setMore(true);
        requestAnimationFrame(() => document.getElementById(`nc-client-${e.fields![0]!.field}`)?.focus());
      } else {
        setFailure(describeError(e));
      }
    } finally { setBusy(false); }
  }

  return (
    <div className="nc-newclient" role="group" aria-labelledby="nc-newclient-title">
      <h3 id="nc-newclient-title" className="nc-sub">New client</h3>
      <div className="nc-newclient__grid">{CLIENT_FIELDS.filter((f) => f.first).map(field)}</div>
      <details className="nc-more" open={more} onToggle={(e) => setMore((e.target as HTMLDetailsElement).open)}>
        <summary>More details<span className="nc-q__req">Registered office, PAN, GSTIN, who signs and more</span></summary>
        <div className="nc-newclient__grid">{CLIENT_FIELDS.filter((f) => !f.first).map(field)}</div>
      </details>
      <p className="nc-quiet">Typed by you. LegalMind never fills these in.</p>
      {failure ? <p className="nc-error" role="alert">{failure}</p> : null}
      <div className="nc-actions">
        <button type="button" className="ws-btn" onClick={onCancel}>Cancel</button>
        <button type="button" className="ws-btn" onClick={() => void add()} disabled={busy}>
          {busy ? "Adding…" : "Add client"}
        </button>
      </div>
    </div>
  );
}

export function ClientPicker({ value, onChange }: {
  value: Counterparty | null;
  onChange: (c: Counterparty | null) => void;
}) {
  const [q, setQ] = useState("");
  const [found, setFound] = useState<Counterparty[] | null>(null);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    if (value || adding) return;
    let live = true;
    const t = setTimeout(() => {
      api.clients(1, 8, q.trim() ? { q: q.trim() } : {})
        .then((r) => { if (live) setFound(r.items); })
        .catch(() => { if (live) setFound([]); });
    }, 250);
    return () => { live = false; clearTimeout(t); };
  }, [q, value, adding]);

  if (value) {
    return (
      <div className="nc-chosen">
        <div>
          <p className="nc-item__l1">{value.name}</p>
          <p className="nc-item__l2">{clientLine(value)}</p>
        </div>
        <button type="button" className="ws-btn ws-btn--sm" onClick={() => onChange(null)}>Change</button>
      </div>
    );
  }
  if (adding) return <NewClient onAdded={(c) => { setAdding(false); onChange(c); }} onCancel={() => setAdding(false)} />;
  return (
    <div className="nc-clients">
      <label className="ws-visually-hidden" htmlFor="nc-client-search">Search your clients</label>
      <input id="nc-client-search" className="nc-search" type="search" placeholder="Search your clients by name"
             value={q} onChange={(e) => setQ(e.target.value)} />
      <ul className="nc-results" aria-label="Your clients">
        {(found ?? []).map((c) => (
          <li key={c.id}>
            <button type="button" className="nc-item" onClick={() => onChange(c)}>
              <span className="nc-item__l1">{c.name}</span>
              <span className="nc-item__l2">{clientLine(c)}</span>
            </button>
          </li>
        ))}
        {found && !found.length ? (
          <li className="nc-quiet nc-results__none">{q.trim() ? `No client named “${q.trim()}” among yours.` : "You have no clients yet."}</li>
        ) : null}
        <li>
          <button type="button" className="nc-item nc-item--add" onClick={() => setAdding(true)}>
            <span className="nc-item__l1">Add a new client</span>
            <span className="nc-item__l2">With their registered name, CIN and who signs</span>
          </button>
        </li>
      </ul>
    </div>
  );
}
