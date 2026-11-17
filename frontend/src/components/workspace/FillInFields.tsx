"use client";

/**
 * Fill-in fields (`AM-394`): the blanks Legal made into fields on the template, with the
 * deal's values. The deal owner may change them while our latest version is still with
 * us — saving makes a new version of ours. Presentation only: the server says who may
 * edit (`can_edit`) and checks again on save.
 */
import { useCallback, useEffect, useId, useState } from "react";

import { api, describeError, type BlankValues } from "@/lib/api";

export function FillInFields({ contractId, onSaved }: { contractId: string; onSaved: () => void }) {
  const [got, setGot] = useState<BlankValues | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const id = useId();
  const load = useCallback(() => api.blankValues(contractId).then(setGot).catch(() => setGot(null)), [contractId]);
  useEffect(() => { void load(); }, [load]);
  if (!got?.fields.length) return null;
  const shown = (f: BlankValues["fields"][number]) => f.value ?? (f.default ? `${f.default} (template default)` : "Not filled");

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const changed = Object.fromEntries(Object.entries(draft).filter(([k, v]) =>
      v.trim() && v.trim() !== (got!.fields.find((f) => f.key === k)?.value ?? "")));
    if (!Object.keys(changed).length) { setEditing(false); return; }
    setBusy(true);
    setError(null);
    try {
      await api.fillBlankValues(contractId, { values: changed, expected_version: got!.version_number! });
      setEditing(false);
      await load();
      onSaved();
    } catch (cause) {
      setError(describeError(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="ws-contract" aria-labelledby={`${id}-h`}>
      <h3 id={`${id}-h`} className="ws-contract__title">Fill-in fields</h3>
      {editing ? (
        <form className="ws-decision__form" onSubmit={save} noValidate>
          {got.fields.map((f) => (
            <label key={f.key}>
              <span>{f.label}{f.required ? "" : " (optional)"}</span>
              <input type="text" maxLength={300} defaultValue={f.value ?? ""}
                     placeholder={f.default ?? undefined}
                     onChange={(e) => setDraft((d) => ({ ...d, [f.key]: e.target.value }))} />
            </label>
          ))}
          <p className="ws-pane__note">Saving makes a new version of our contract with these words.</p>
          {error ? <p className="cx-error" role="alert">{error}</p> : null}
          <div className="ws-contract__actions">
            <button type="button" className="ws-btn" disabled={busy} onClick={() => setEditing(false)}>Cancel</button>
            <button type="submit" className="ws-btn ws-btn--primary" disabled={busy}>{busy ? "Saving…" : "Save fields"}</button>
          </div>
        </form>
      ) : (
        <>
          <dl className="lm-fields">
            {got.fields.map((f) => (
              <div key={f.key}><dt>{f.label}</dt><dd>{shown(f)}</dd></div>
            ))}
          </dl>
          {got.can_edit ? (
            <button type="button" className="ws-btn" onClick={() => { setDraft({}); setEditing(true); }}>Edit fill-in fields</button>
          ) : null}
        </>
      )}
    </section>
  );
}
