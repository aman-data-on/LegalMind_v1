"use client";

/**
 * The three quieter tabs — Details, Notes, Activity.
 *
 * Each one exists because it has something real to show. There is no Analysis
 * tab: analysis belongs to a document, the document rows already lead to it,
 * and a client-level "Analysis" tab would either duplicate the Documents tab or
 * invent a client-level legal conclusion, which no locked decision defines
 * (rule 7). The owner's instruction says the same thing — "Do not create empty
 * tabs just for appearance."
 */

import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import { clientStatusLabel } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ClientActivity, Counterparty } from "@/lib/types";

import { Fact, websiteHref } from "./ClientBits";
import { activityWords, shortDate } from "./model";

/**
 * Everything recorded about the client, in one plain list.
 *
 * Every field is shown whether or not it has a value, and an empty one says
 * "Not available" — on THIS tab, unlike the compact header row, because the
 * Details tab's job is precisely to say what is and is not known. Absence is
 * information (DESIGN.md), and here it is the information the reader came for.
 */
export function ClientDetails({ client }: { client: Counterparty }) {
  return (
    <section className="ws-cl__details" aria-labelledby="ws-cl-details-title">
      <h2 id="ws-cl-details-title" className="ws-visually-hidden">
        Client details
      </h2>
      <dl className="ws-cl__factgrid">
        <Fact label="Company name" value={client.name} />
        <Fact label="Registered name" value={client.legal_name} />
        <Fact label="Status" value={clientStatusLabel(client.status)} />
        <Fact label="Industry" value={client.industry} />
        <Fact label="Website" value={client.website}
              href={websiteHref(client.website)} />
        <Fact label="City" value={client.city} />
        <Fact label="State or region" value={client.state_region} />
        <Fact label="Country" value={client.country} />
        <Fact label="Primary contact" value={client.primary_contact_name} />
        <Fact label="Primary contact email" value={client.primary_contact_email}
              href={client.primary_contact_email
                ? `mailto:${client.primary_contact_email}` : null} />
        <Fact label="Phone" value={client.primary_contact_phone} />
        <Fact label="Legal contact" value={client.legal_contact_name} />
        <Fact label="Legal contact email" value={client.legal_contact_email}
              href={client.legal_contact_email
                ? `mailto:${client.legal_contact_email}` : null} />
        <Fact label="Account owner" value={client.account_owner_name} />
        <Fact label="Added" value={shortDate(client.created_at)} />
      </dl>
    </section>
  );
}

/**
 * The relationship note — one text field, saved deliberately.
 *
 * It reuses `counterparties.relationship_notes`, which AB-13 r1 already
 * created, so no note table was added. The help text below is not decoration:
 * a free-text note that reads as an organisational legal position is exactly
 * what `LEGAL-02` and rule 13 keep apart from a ratified Company Standard, and
 * the reader is told which of the two they are writing.
 */
export function ClientNotes({ client, onSaved }: {
  client: Counterparty;
  onSaved: (client: Counterparty) => void;
}) {
  const { can } = useSession();
  const [text, setText] = useState(client.relationship_notes ?? "");
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const editable = can(P.CONTRACT_UPDATE);

  // A different client arriving under the same mounted tab must not keep the
  // previous one's text in the box.
  useEffect(() => {
    setText(client.relationship_notes ?? "");
    setSaved(false);
  }, [client.id, client.relationship_notes]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.updateCounterparty(client.id, {
        relationship_notes: text.trim() || null,
      });
      onSaved(updated);
      setSaved(true);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  if (!editable) {
    return (
      <section className="ws-cl__notes" aria-labelledby="ws-cl-notes-title">
        <h2 id="ws-cl-notes-title">Notes</h2>
        {client.relationship_notes ? (
          <p className="ws-cl__notetext">{client.relationship_notes}</p>
        ) : (
          <p className="ws-pane__note">No notes for this client yet.</p>
        )}
      </section>
    );
  }

  const dirty = text.trim() !== (client.relationship_notes ?? "").trim();
  return (
    <section className="ws-cl__notes" aria-labelledby="ws-cl-notes-title">
      <h2 id="ws-cl-notes-title">Notes</h2>
      <label className="ws-field">
        <span className="ws-visually-hidden">Notes about this client</span>
        <textarea value={text} rows={8} maxLength={5000} disabled={busy}
                  placeholder="Anything worth knowing about this relationship"
                  onChange={(event) => { setText(event.target.value); setSaved(false); }} />
        <span className="ws-field__help">
          Context for your colleagues, and visible to everyone who can see this
          client. A note is not a legal record — the organisation&rsquo;s position
          lives in an approved Company Standard, and a ruling on a document is a
          Legal Decision.
        </span>
      </label>
      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}
      <div className="ws-cl__form-acts">
        {saved && !dirty ? (
          <span className="ws-pane__note" role="status" aria-live="polite">Saved</span>
        ) : null}
        <span className="ws-cl__spacer" />
        <button type="button" className="ws-btn ws-btn--primary"
                disabled={busy || !dirty} onClick={() => void save()}>
          {busy ? "Saving…" : "Save notes"}
        </button>
      </div>
    </section>
  );
}

/**
 * This client's history, from the audit trail that already recorded it.
 *
 * No second history was built for this screen: `audit_events` (42.18, AUD-01)
 * already carried every one of these acts, and the endpoint simply reads the
 * rows whose entity is this client or one of its documents. Payloads are not
 * returned — a before/after can hold an internal legal position (`LEGAL-02`) —
 * so the feed answers when, what and who, which is what the owner asked for.
 */
export function ClientActivityFeed({ clientId }: { clientId: string }) {
  const [rows, setRows] = useState<ClientActivity[] | null>(null);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    setRows(null);
    setError(null);
    api.clientActivity(clientId)
      .then((result) => { if (!cancelled) setRows(result); })
      .catch((cause) => { if (!cancelled) setError(cause); });
    return () => { cancelled = true; };
  }, [clientId]);

  if (error) {
    return (
      <div className="ws-state ws-state--error" role="alert">
        <h2>This client&rsquo;s history could not be loaded.</h2>
        <p>{describeError(error)}</p>
      </div>
    );
  }
  if (rows === null) {
    return (
      <p className="ws-pane__note" role="status" aria-live="polite">Loading…</p>
    );
  }
  if (rows.length === 0) {
    return (
      <p className="ws-pane__note">
        Nothing has happened to this client yet. Activity appears here as
        documents are uploaded, analyzed and decided.
      </p>
    );
  }

  return (
    <section className="ws-cl__activity" aria-labelledby="ws-cl-activity-title">
      <h2 id="ws-cl-activity-title" className="ws-visually-hidden">Activity</h2>
      <ol className="ws-cl__timeline">
        {rows.map((row) => (
          <li key={row.id}>
            <span className="ws-cl__when ws-mono">
              {shortDate(row.timestamp) ?? "—"}
            </span>
            <span className="ws-cl__what">
              {activityWords(row.action)}
              {row.subject ? (
                <span className="ws-cl__subject"> · {row.subject}</span>
              ) : null}
            </span>
            <span className="ws-cl__who">
              {row.actor_name ?? "System"}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
