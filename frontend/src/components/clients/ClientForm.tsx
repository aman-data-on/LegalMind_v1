"use client";

/**
 * Add a client, and edit one — the same form, because the fields are the same
 * and two forms would drift.
 *
 * **A disclosure, not a modal** (DD-11): DESIGN.md reserves modals for a
 * genuine interruption — a destructive confirmation or a truly blocking choice
 * — and recording a company is neither. It opens in place, above the list it
 * adds to, and closes back to it. The owner's 2026-09-16 reference drew Add as
 * its own page with a breadcrumb and a "Back to clients" button; asked which
 * they wanted, they chose to keep it in place and take the visual design, so
 * DD-11 and DD-18 §4 stand and those two page controls are not built.
 *
 * **Two arrangements, one set of fields.** ADD renders the reference's layout —
 * a marked header, three numbered sections, a companion panel. EDIT renders the
 * flat grid it always had, because it lives on the client detail page and this
 * redesign was scoped to Add. Every field is declared ONCE and both branches
 * compose the same nodes, so the grouping is visual only and the two cannot
 * drift apart on a limit, a placeholder or a handler.
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

import {
  IconBuilding, IconLightbulb, IconUsers,
} from "@/components/workspace/icons";

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

  /*
   * EVERY FIELD IS DEFINED ONCE, HERE, and the two layouts below compose these
   * same nodes. The file's own rule — "the same form, because the fields are
   * the same and two forms would drift" — applied to the arrangement as well:
   * writing the inputs out twice is how a maxLength, a placeholder or a
   * `disabled` ends up correct in one layout and stale in the other.
   *
   * Nothing below changes what any field IS. Same names, same limits, same
   * types, same handlers, same `draft` keys, same submit body.
   */
  const fName = (
    <label className="ws-field ws-cl__form-name">
      <span className="ws-field__label">
        Company name <span className="ws-field__req">(required)</span>
      </span>
      <input ref={nameInput} value={draft.name} onChange={set("name")}
             maxLength={500} required disabled={busy}
             aria-describedby={duplicate ? "ws-cl-dupe" : undefined} />
    </label>
  );

  const fDuplicate = duplicate ? (
    <p className="ws-cl__dupe" id="ws-cl-dupe" role="status">
      <strong>{duplicate.name}</strong> is already a client.{" "}
      <Link href={`/dashboard/clients?id=${duplicate.id}`}>
        Open that profile
      </Link>{" "}
      instead, or continue if this is a different company.
    </p>
  ) : null;

  const fRegistered = (
    <label className="ws-field">
      <span className="ws-field__label">Registered name</span>
      <input value={draft.legal_name} onChange={set("legal_name")}
             maxLength={500} disabled={busy}
             placeholder="If it differs from the name above" />
    </label>
  );

  const fStatus = (
    <label className="ws-field">
      <span className="ws-field__label">Status</span>
      <select value={draft.status} onChange={set("status")} disabled={busy}>
        {CLIENT_STATUSES.map((s) => (
          <option key={s.state} value={s.state}>{s.label}</option>
        ))}
      </select>
    </label>
  );

  const fIndustry = (
    <label className="ws-field">
      <span className="ws-field__label">Industry</span>
      <input value={draft.industry} onChange={set("industry")}
             maxLength={200} disabled={busy} />
    </label>
  );

  const fWebsite = (
    <label className="ws-field">
      <span className="ws-field__label">Website</span>
      <input value={draft.website} onChange={set("website")} type="url"
             maxLength={500} disabled={busy} placeholder="https://" />
    </label>
  );

  const fCity = (
    <label className="ws-field">
      <span className="ws-field__label">City</span>
      <input value={draft.city} onChange={set("city")} maxLength={200}
             disabled={busy} />
    </label>
  );

  const fStateRegion = (
    <label className="ws-field">
      <span className="ws-field__label">State or region</span>
      <input value={draft.state_region} onChange={set("state_region")}
             maxLength={200} disabled={busy} />
    </label>
  );

  const fCountry = (
    <label className="ws-field">
      <span className="ws-field__label">Country</span>
      <input value={draft.country} onChange={set("country")} maxLength={200}
             disabled={busy} />
    </label>
  );

  const fPrimary = (
    <label className="ws-field">
      <span className="ws-field__label">Primary contact</span>
      <input value={draft.primary_contact_name}
             onChange={set("primary_contact_name")} maxLength={200}
             disabled={busy} />
    </label>
  );

  const fPrimaryEmail = (
    <label className="ws-field">
      <span className="ws-field__label">Primary contact email</span>
      <input value={draft.primary_contact_email} type="email"
             onChange={set("primary_contact_email")} maxLength={320}
             disabled={busy} />
    </label>
  );

  const fPhone = (
    <label className="ws-field">
      <span className="ws-field__label">Phone</span>
      <input value={draft.primary_contact_phone}
             onChange={set("primary_contact_phone")} maxLength={60}
             disabled={busy} />
    </label>
  );

  const fLegalContact = (
    <label className="ws-field">
      <span className="ws-field__label">Legal contact</span>
      <input value={draft.legal_contact_name}
             onChange={set("legal_contact_name")} maxLength={200}
             disabled={busy} />
    </label>
  );

  const fLegalEmail = (
    <label className="ws-field">
      <span className="ws-field__label">Legal contact email</span>
      <input value={draft.legal_contact_email} type="email"
             onChange={set("legal_contact_email")} maxLength={320}
             disabled={busy} />
    </label>
  );

  /* Absent when the caller is in no department — there is nobody to offer, and
     the server refuses a target outside it regardless. Not in the reference
     image, which predates it; kept because removing a field is not a redesign. */
  const fAccountOwner = members && members.members.length > 0 ? (
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
  ) : null;

  const fNotes = (
    <label className="ws-field ws-cl__form-wide">
      <span className="ws-field__label">Notes</span>
      {/* Two rows in ADD, where the compact layout is fighting for viewport;
          three in EDIT, which must stay exactly as it was. `maxLength` is
          untouched at 5000 in both — this is the box's height, not its limit. */}
      <textarea value={draft.relationship_notes}
                onChange={set("relationship_notes")} rows={existing ? 3 : 2}
                maxLength={5000} disabled={busy}
                placeholder="Anything worth knowing about this relationship" />
      <span className="ws-field__help">
        Notes are context for your colleagues. They are not a legal record —
        a Company Standard, a published rule and a Legal Decision are.
      </span>
    </label>
  );

  const errorNode = error ? (
    <p className="ws-field__error" role="alert">{describeError(error)}</p>
  ) : null;

  const actions = (
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
  );

  /* EDIT PROFILE — unchanged, deliberately. It renders on the client detail
     page, which this redesign was told to leave alone (owner, 2026-09-16), so
     it keeps the flat grid it has always had. Only the arrangement differs
     between the two branches; every field above is the same object. */
  if (existing) {
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
          {fName}
          {fDuplicate}
          {fRegistered}
          {fStatus}
          {fIndustry}
          {fWebsite}
          {fCity}
          {fStateRegion}
          {fCountry}
          {fPrimary}
          {fPrimaryEmail}
          {fPhone}
          {fLegalContact}
          {fLegalEmail}
          {fAccountOwner}
          {fNotes}
        </div>

        {errorNode}
        {actions}
      </form>
    );
  }

  /*
   * ADD A CLIENT — the owner's reference layout (2026-09-16): a marked header,
   * the fields grouped into three numbered sections, and a companion panel on
   * the right.
   *
   * It stays a DISCLOSURE inside `/dashboard/clients` rather than becoming its
   * own route (owner's choice when the tradeoff was put to them). DD-11 and
   * DD-18 §4 both record that Add client, Edit profile, Upload document and
   * Link existing open in place; the reference's breadcrumb and "Back to
   * clients" belong to a page and are deliberately not built, because inside a
   * panel they would point at the screen the reader is already on.
   *
   * The sections are VISUAL ONLY. No field is duplicated, moved between
   * `draft` keys, or given a different name — the submit body below is byte
   * for byte what it was.
   */
  const section = (n: number, title: string, note: string, children: React.ReactNode) => (
    <section className="ws-cl__sect">
      <div className="ws-cl__sect-head">
        <span className="ws-cl__sect-num" aria-hidden="true">{n}</span>
        <div className="ws-cl__sect-titles">
          <h3>{title}</h3>
          <p className="ws-pane__note">{note}</p>
        </div>
      </div>
      <div className="ws-cl__sect-grid">{children}</div>
    </section>
  );

  return (
    <form className="ws-cl__form ws-cl__form--add" onSubmit={submit}
          aria-labelledby="ws-cl-form-title">
      <div className="ws-cl__addhead">
        <span className="ws-cl__addmark" aria-hidden="true">
          <IconBuilding size={22} />
        </span>
        <div className="ws-cl__form-head">
          <h2 id="ws-cl-form-title">{heading}</h2>
          <p className="ws-pane__note">
            Only the company name is required. Anything you leave empty stays
            empty — nothing here is filled in for you.
          </p>
        </div>
      </div>

      <div className="ws-cl__addcols">
        <div className="ws-cl__addmain">
          {section(1, "Basic information",
            "Start with the essential details about the company.",
            <>
              {fName}
              {fDuplicate}
              {fRegistered}
              {fStatus}
              {fIndustry}
              {fWebsite}
              {fCity}
              {fStateRegion}
              {fCountry}
            </>)}

          {section(2, "Contact information",
            "Add primary and legal contacts for this client.",
            <>
              {fPrimary}
              {fPrimaryEmail}
              {fPhone}
              {fLegalContact}
              {fLegalEmail}
              {fAccountOwner}
            </>)}

          {section(3, "Additional information",
            "Add any relevant notes about this client.",
            fNotes)}

          {errorNode}
          {actions}
        </div>

        {/* Companion panel. Descriptive only — no control, nothing focusable,
            so the form's tab order runs straight from the last field to Cancel
            and Add client. The illustration reuses the empty state's sheet
            vocabulary rather than introducing a second drawing style. */}
        <aside className="ws-cl__aside" aria-labelledby="ws-cl-aside-title">
          <span className="ws-cl__aside-art" aria-hidden="true">
            <span className="ws-cl__aside-card">
              <span className="ws-cl__aside-avatar"><IconUsers size={18} /></span>
              <span className="ws-cl__aside-lines">
                <span /><span />
              </span>
            </span>
          </span>
          <h3 id="ws-cl-aside-title">Keep client information organised</h3>
          <p className="ws-pane__note">
            A client profile helps you manage all their legal documents,
            versions and reviews in one place.
          </p>
          <div className="ws-cl__tips">
            <p className="ws-cl__tips-head">
              <IconLightbulb size={14} />
              Tips
            </p>
            <ul>
              <li>Only the company name is required.</li>
              <li>Add as much information as you have.</li>
              <li>You can always update these details later.</li>
              <li>Notes are for internal use only.</li>
            </ul>
          </div>
        </aside>
      </div>
    </form>
  );
}
