"use client";

/**
 * Add a client, and edit one — the same form, because the fields are the same
 * and two forms would drift.
 *
 * **A disclosure, not a modal** (DD-11): DESIGN.md reserves modals for a
 * genuine interruption — a destructive confirmation or a truly blocking choice
 * — and recording a company is neither. It opens in place, above the list it
 * adds to, and closes back to it.
 *
 * **Only the name is required.** Everything else is optional and stays empty
 * unless somebody types it: rule 21 forbids inventing company information, and
 * a form that demands an industry gets an invented industry. The server applies
 * the same rule — a blank field is stored as nothing, not as "".
 *
 * **The duplicate warning is a warning.** When the name being typed already
 * names a client this caller can see, the form says so and offers to open it —
 * and still lets them continue, because only the person typing knows whether
 * "Acme Ltd" and "Acme Limited" are one company or two. AB-13 deliberately put
 * no unique constraint on the name for that reason; refusing here would make
 * the genuine second company unrecordable.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { api, describeError } from "@/lib/api";
import { CLIENT_STATUSES } from "@/lib/documentTypes";
import type { Counterparty, DepartmentMembers } from "@/lib/types";

/** The editable shape, flat, so one `<input>` per key and no nesting. */
interface Draft {
  name: string;
  legal_name: string;
  status: string;
  industry: string;
  website: string;
  city: string;
  state_region: string;
  country: string;
  primary_contact_name: string;
  primary_contact_email: string;
  primary_contact_phone: string;
  legal_contact_name: string;
  legal_contact_email: string;
  account_owner_id: string;
  relationship_notes: string;
}

const EMPTY: Draft = {
  name: "", legal_name: "", status: "ACTIVE", industry: "", website: "",
  city: "", state_region: "", country: "",
  primary_contact_name: "", primary_contact_email: "", primary_contact_phone: "",
  legal_contact_name: "", legal_contact_email: "",
  account_owner_id: "", relationship_notes: "",
};

function draftFrom(client: Counterparty): Draft {
  return {
    ...EMPTY,
    name: client.name,
    legal_name: client.legal_name ?? "",
    status: client.status,
    industry: client.industry ?? "",
    website: client.website ?? "",
    city: client.city ?? "",
    state_region: client.state_region ?? "",
    country: client.country ?? "",
    primary_contact_name: client.primary_contact_name ?? "",
    primary_contact_email: client.primary_contact_email ?? "",
    primary_contact_phone: client.primary_contact_phone ?? "",
    legal_contact_name: client.legal_contact_name ?? "",
    legal_contact_email: client.legal_contact_email ?? "",
    account_owner_id: client.account_owner_id ?? "",
    relationship_notes: client.relationship_notes ?? "",
  };
}

/** A trimmed value, or null to mean "nothing" — the shape the API's
 *  "omitted, never nulled" contract expects on the way in. */
function orNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

/** Comparable form of a company name, for the duplicate warning only.
 *  Case and punctuation folded, and the legal suffix left ALONE: "Acme
 *  Technologies" and "Acme Technologies Pvt. Ltd." are plausibly one company,
 *  but so are they plausibly two, and this only decides whether to ASK. */
export function nameKey(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export function ClientForm({
  existing, knownClients, members, onSaved, onCancel,
}: {
  /** Absent for Add, present for Edit. */
  existing?: Counterparty;
  /** The clients this caller already sees, for the duplicate warning. */
  knownClients: readonly Counterparty[];
  /** Colleagues who may hold the relationship. Empty when the caller is in no
   *  department, in which case the field is simply absent — the server refuses
   *  a target outside the caller's department anyway. */
  members: DepartmentMembers | null;
  onSaved: (client: Counterparty) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<Draft>(
    existing ? draftFrom(existing) : EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const nameInput = useRef<HTMLInputElement>(null);

  // Focus lands on the one required field, so the form is usable by the
  // keyboard that opened it. `preventScroll`, for the reason the Dashboard's
  // row menu records: the scroll a plain focus() requests arrives a frame
  // later and can move the page out from under the reader.
  useEffect(() => {
    nameInput.current?.focus({ preventScroll: true });
  }, []);

  const set = <K extends keyof Draft>(key: K) =>
    (event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setDraft((current) => ({ ...current, [key]: event.target.value }));

  const trimmedName = draft.name.trim();
  const duplicate = trimmedName.length > 1
    ? knownClients.find((c) =>
      c.id !== existing?.id && nameKey(c.name) === nameKey(trimmedName))
    : undefined;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!trimmedName) return;
    setBusy(true);
    setError(null);
    const body: Record<string, string | null> = {
      name: trimmedName,
      status: draft.status,
      legal_name: orNull(draft.legal_name),
      industry: orNull(draft.industry),
      website: orNull(draft.website),
      city: orNull(draft.city),
      state_region: orNull(draft.state_region),
      country: orNull(draft.country),
      primary_contact_name: orNull(draft.primary_contact_name),
      primary_contact_email: orNull(draft.primary_contact_email),
      primary_contact_phone: orNull(draft.primary_contact_phone),
      legal_contact_name: orNull(draft.legal_contact_name),
      legal_contact_email: orNull(draft.legal_contact_email),
      relationship_notes: orNull(draft.relationship_notes),
      account_owner_id: orNull(draft.account_owner_id),
    };
    try {
      const saved = existing
        ? await api.updateCounterparty(existing.id, body)
        : await api.createCounterparty(body);
      onSaved(saved);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  const heading = existing ? "Edit client profile" : "Add a client";
  return (
    <form className="ws-cl__form" onSubmit={submit}
          aria-labelledby="ws-cl-form-title">
      <div className="ws-cl__form-head">
        <h2 id="ws-cl-form-title">{heading}</h2>
        <p className="ws-pane__note">
          Only the company name is required. Anything you leave empty stays
          empty — nothing here is filled in for you.
        </p>
      </div>

      <div className="ws-cl__form-grid">
        <label className="ws-field ws-cl__form-name">
          <span className="ws-field__label">
            Company name <span className="ws-field__req">(required)</span>
          </span>
          <input ref={nameInput} value={draft.name} onChange={set("name")}
                 maxLength={500} required disabled={busy}
                 aria-describedby={duplicate ? "ws-cl-dupe" : undefined} />
        </label>

        {duplicate ? (
          <p className="ws-cl__dupe" id="ws-cl-dupe" role="status">
            <strong>{duplicate.name}</strong> is already a client.{" "}
            <Link href={`/dashboard/clients?id=${duplicate.id}`}>
              Open that profile
            </Link>{" "}
            instead, or continue if this is a different company.
          </p>
        ) : null}

        <label className="ws-field">
          <span className="ws-field__label">Registered name</span>
          <input value={draft.legal_name} onChange={set("legal_name")}
                 maxLength={500} disabled={busy}
                 placeholder="If it differs from the name above" />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Status</span>
          <select value={draft.status} onChange={set("status")} disabled={busy}>
            {CLIENT_STATUSES.map((s) => (
              <option key={s.state} value={s.state}>{s.label}</option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Industry</span>
          <input value={draft.industry} onChange={set("industry")}
                 maxLength={200} disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Website</span>
          <input value={draft.website} onChange={set("website")} type="url"
                 maxLength={500} disabled={busy} placeholder="https://" />
        </label>

        <label className="ws-field">
          <span className="ws-field__label">City</span>
          <input value={draft.city} onChange={set("city")} maxLength={200}
                 disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">State or region</span>
          <input value={draft.state_region} onChange={set("state_region")}
                 maxLength={200} disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Country</span>
          <input value={draft.country} onChange={set("country")} maxLength={200}
                 disabled={busy} />
        </label>

        <label className="ws-field">
          <span className="ws-field__label">Primary contact</span>
          <input value={draft.primary_contact_name}
                 onChange={set("primary_contact_name")} maxLength={200}
                 disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Primary contact email</span>
          <input value={draft.primary_contact_email} type="email"
                 onChange={set("primary_contact_email")} maxLength={320}
                 disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Phone</span>
          <input value={draft.primary_contact_phone}
                 onChange={set("primary_contact_phone")} maxLength={60}
                 disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Legal contact</span>
          <input value={draft.legal_contact_name}
                 onChange={set("legal_contact_name")} maxLength={200}
                 disabled={busy} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Legal contact email</span>
          <input value={draft.legal_contact_email} type="email"
                 onChange={set("legal_contact_email")} maxLength={320}
                 disabled={busy} />
        </label>

        {/* Absent when the caller is in no department — there is nobody to
            offer, and the server refuses a target outside it regardless. */}
        {members && members.members.length > 0 ? (
          <label className="ws-field">
            <span className="ws-field__label">Account owner</span>
            <select value={draft.account_owner_id}
                    onChange={set("account_owner_id")} disabled={busy}>
              <option value="">Nobody yet</option>
              {members.members.map((m) => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
          </label>
        ) : null}

        <label className="ws-field ws-cl__form-wide">
          <span className="ws-field__label">Notes</span>
          <textarea value={draft.relationship_notes}
                    onChange={set("relationship_notes")} rows={3}
                    maxLength={5000} disabled={busy}
                    placeholder="Anything worth knowing about this relationship" />
          <span className="ws-field__help">
            Notes are context for your colleagues. They are not a legal record —
            a Company Standard, a published rule and a Legal Decision are.
          </span>
        </label>
      </div>

      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}

      <div className="ws-cl__form-acts">
        <button type="button" className="ws-btn" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="ws-btn ws-btn--primary"
                disabled={busy || !trimmedName}>
          {busy
            ? (existing ? "Saving…" : "Adding…")
            : (existing ? "Save changes" : "Add client")}
        </button>
      </div>
    </form>
  );
}
