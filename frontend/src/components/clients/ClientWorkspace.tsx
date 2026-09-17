"use client";

/**
 * One client's workspace — the dedicated client file.
 *
 * **Layout**: a compact client rail on the left (the same 264px token the
 * workspace's clause index uses, so the two screens share one measure) and the
 * client itself taking the rest of the width. The rail is for SWITCHING; every
 * pixel beyond it belongs to the client, which is why the header, the
 * information row and the document table all run its full width rather than
 * sitting in cards inside it.
 *
 * **Deliberately not the Dashboard.** The Dashboard is a working queue with
 * status tiles above a table of everything. This is a file: identity first,
 * what we know about them second, then their documents. No stat tiles — the
 * counts that matter here ("4 documents, 2 signed") are two words in the
 * header, and DESIGN.md's anti-patterns rule out stat cards that exist to fill
 * space.
 *
 * Nothing here decides anything legal. Every status on a document row is the
 * server's own (52.7), and the only writes are the client's own fields, a
 * version's declared role, and the counterparty link.
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { api, describeError } from "@/lib/api";
import { clientLocation } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Counterparty, DepartmentMembers } from "@/lib/types";

import { Dialog } from "@/components/Dialog";
import { IconChevronRight } from "@/components/workspace/icons";

import { ClientAvatar, ClientStatus, Fact, websiteHref } from "./ClientBits";
import { ClientDocuments } from "./ClientDocuments";
import { ClientForm } from "./ClientForm";
import { ClientActivityFeed, ClientDetails, ClientNotes } from "./ClientTabs";
import {
  documentCountLabel,
  hasProfileDetail,
  mergeProfile,
} from "./model";

const TABS = [
  { key: "documents", label: "Documents" },
  { key: "details", label: "Details" },
  { key: "notes", label: "Notes" },
  { key: "activity", label: "Activity" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

/**
 * The client header's overflow menu — the same `.ws-menu` vocabulary the
 * Dashboard's row actions use (`⋯` toggle, `role="menu"`, `--bad` for the
 * destructive item), and the same reason for existing: DESIGN.md keeps
 * destructive actions out of the standing control row, so "Delete client" is
 * never a permanent red button beside "Edit profile".
 *
 * No portal here, unlike the Dashboard's copy. That one escapes the table's
 * `overflow` by rendering into `document.body` with inline viewport
 * coordinates; this header has no clipping ancestor (`.ws-cl__head` and
 * `.ws-cl__main` set no `overflow`), so the plain absolutely-positioned list is
 * correct and carries none of that machinery.
 */
function ClientMenu({ children, label }: { children: ReactNode; label: string }) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const toggleRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onPointer(event: PointerEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      // Stop the shell's single-key shortcuts seeing it, and return focus to
      // the control the reader opened — the same courtesy `Dialog` gives.
      event.stopPropagation();
      setOpen(false);
      toggleRef.current?.focus();
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="ws-menu ws-cl__headmenu" ref={wrapRef}>
      <button ref={toggleRef} type="button"
              className="ws-btn ws-btn--sm ws-menu__toggle"
              aria-haspopup="menu" aria-expanded={open} aria-label={label}
              onClick={() => setOpen((was) => !was)}>
        ⋯
      </button>
      {open ? (
        <div className="ws-menu__list" role="menu" aria-orientation="vertical"
             onClick={() => setOpen(false)}>
          {children}
        </div>
      ) : null}
    </div>
  );
}

/**
 * Delete confirmation — the same shape as `DeleteContractDialog`, deliberately:
 * one interruption pattern for one kind of act. The consequence is different
 * and the copy says so. This destroys a profile with nothing filed under it, so
 * unlike a contract deletion no document, version, finding or legal decision
 * goes with it, and rule 17 is not in play.
 *
 * **No optimistic UI** (52.7): the client is removed from the screen only after
 * the server returns 204. A failure leaves the profile exactly where it was and
 * says why.
 */
function DeleteClientDialog({
  client, onClose, onDeleted,
}: { client: Counterparty; onClose: () => void; onDeleted: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteClient(client.id);
      onDeleted();
    } catch (cause) {
      setError(cause);
      setBusy(false);
    }
  }

  return (
    <Dialog onClose={onClose} titleId="ws-cl-del-title">
      <h2 id="ws-cl-del-title">Delete this client profile?</h2>
      <p className="ws-modal__body"><strong>{client.name}</strong></p>
      <p className="ws-modal__body">
        This removes the client profile only — its details, contacts and notes.
        No documents are filed under it, so nothing else is affected. This
        cannot be undone.
      </p>
      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}
      <div className="ws-modal__acts">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
        <button type="button" className="ws-btn ws-btn--bad"
                disabled={busy} onClick={() => void confirm()}>
          {busy ? "Deleting…" : "Delete permanently"}
        </button>
      </div>
    </Dialog>
  );
}

/** The rail: search, and every client this caller works with. */
function ClientRail({
  clients, activeId, total, q, onSearch, onAdd, canAdd,
}: {
  /** `null` means NOT YET LOADED, which is not the same fact as "none".
   *
   *  It started as `[]` and the rail said "No clients yet." to an account with
   *  eleven of them, for the ~300ms before the list landed — the exact failure
   *  DESIGN.md names ("never rendered as visually identical to still
   *  loading"). Absence is information here, so it must not be printed until
   *  it is actually known. */
  clients: readonly Counterparty[] | null;
  activeId: string;
  total: number | null;
  q: string;
  onSearch: (value: string) => void;
  onAdd: () => void;
  canAdd: boolean;
}) {
  return (
    <aside className="ws-cl__rail" aria-label="Clients">
      <div className="ws-cl__rail-head">
        <Link className="ws-cl__rail-back" href="/dashboard/clients">
          All clients
        </Link>
        {total !== null ? (
          <span className="ws-cl__rail-total ws-mono">{total}</span>
        ) : null}
      </div>
      <div className="ws-cl__rail-tools">
        <label className="ws-cl__rail-search">
          <span className="ws-visually-hidden">Search clients</span>
          <input value={q} onChange={(event) => onSearch(event.target.value)}
                 placeholder="Search clients…" maxLength={200} />
        </label>
        {canAdd ? (
          <button type="button" className="ws-btn ws-btn--sm ws-cl__rail-add"
                  onClick={onAdd}>
            + Add
          </button>
        ) : null}
      </div>
      {clients === null ? (
        <p className="ws-pane__note ws-cl__rail-empty" role="status"
           aria-live="polite">
          Loading…
        </p>
      ) : clients.length === 0 ? (
        <p className="ws-pane__note ws-cl__rail-empty">
          {q ? "No clients match that." : "No clients yet."}
        </p>
      ) : (
        <ul className="ws-cl__raillist">
          {clients.map((client) => (
            <li key={client.id}>
              <Link href={`/dashboard/clients?id=${client.id}`}
                    aria-current={client.id === activeId ? "true" : undefined}
                    className={client.id === activeId
                      ? "ws-cl__railitem ws-cl__railitem--active"
                      : "ws-cl__railitem"}>
                <span className="ws-cl__railname">{client.name}</span>
                <ClientStatus status={client.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
}

export function ClientWorkspace({ clientId }: { clientId: string }) {
  const { can } = useSession();
  const [client, setClient] = useState<Counterparty | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [tab, setTab] = useState<TabKey>("documents");
  const [editing, setEditing] = useState(false);
  const [adding, setAdding] = useState(false);
  /** `null` until the first load returns — see `ClientRail`. */
  const [rail, setRail] = useState<Counterparty[] | null>(null);
  const [railTotal, setRailTotal] = useState<number | null>(null);
  const [railQ, setRailQ] = useState("");
  const [members, setMembers] = useState<DepartmentMembers | null>(null);
  /** The client awaiting a delete confirmation, or `null`. Never a boolean:
   *  the dialog needs the name it is about to destroy. */
  const [deleting, setDeleting] = useState<Counterparty | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setClient(await api.counterparty(clientId));
    } catch (cause) {
      setError(cause);
    }
  }, [clientId]);

  useEffect(() => {
    setTab("documents");
    setEditing(false);
    void load();
  }, [clientId, load]);

  // The rail. Debounced, and best-effort: failing to load the list of other
  // clients must not take THIS client's page down — it is navigation, not
  // content.
  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      api.clients(1, 100, { sort: "name_asc", ...(railQ.trim() ? { q: railQ.trim() } : {}) })
        .then((result) => {
          if (cancelled) return;
          setRail(result.items);
          setRailTotal(result.pagination.total);
        })
        // A failed rail is an empty rail, not a permanent "Loading…": it is
        // navigation, and the client itself has loaded regardless.
        .catch(() => { if (!cancelled) { setRail([]); setRailTotal(0); } });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [railQ]);

  // Colleagues who may hold the relationship — only needed by the form, and
  // absent (not an error) for an account in no department.
  useEffect(() => {
    let cancelled = false;
    api.departmentMembers()
      .then((result) => { if (!cancelled) setMembers(result); })
      .catch(() => { if (!cancelled) setMembers(null); });
    return () => { cancelled = true; };
  }, []);

  if (!can(P.CONTRACT_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include document access.</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="ws-state ws-state--error" role="alert">
        <h2>This client could not be opened.</h2>
        <p>{describeError(error)}</p>
        <Link className="ws-btn" href="/dashboard/clients">All clients</Link>
      </div>
    );
  }

  if (!client) {
    return (
      <div className="ws-cl">
        <p className="ws-pane__note" role="status" aria-live="polite">Loading…</p>
      </div>
    );
  }

  const location = clientLocation(client);
  const documents = client.documents ?? 0;
  const signed = client.signed_documents ?? 0;

  return (
    <div className="ws-cl ws-cl--work">
      <ClientRail clients={rail} activeId={client.id} total={railTotal}
                  q={railQ} onSearch={setRailQ} canAdd={can(P.CONTRACT_UPDATE)}
                  onAdd={() => { setAdding(true); setEditing(false); }} />

      <div className="ws-cl__main">
        {/* Breadcrumb, so a reader arriving from a document knows where they
            are and can get back to the list in one click. */}
        <nav className="ws-cl__crumbs" aria-label="Breadcrumb">
          <Link href="/dashboard/clients">Client profiles</Link>
          <span aria-hidden="true"><IconChevronRight size={12} /></span>
          <span aria-current="page">{adding ? "Add client" : client.name}</span>
        </nav>

        {/* The open client's header, info strip, tabs and panel all step aside
            while the Add Client form is open (same fix as `ClientDirectory`,
            owner, 2026-09-17): the form used to render ABOVE this content
            rather than instead of it, so the client being viewed stayed fully
            visible — its header, tabs and documents — underneath a form for a
            DIFFERENT, not-yet-created client. Wrapped once here, as there,
            rather than adding an `adding` check to each piece individually. */}
        {adding ? (
          <ClientForm knownClients={rail ?? []} members={members}
                      onCancel={() => setAdding(false)}
                      onSaved={(created) => {
                        setAdding(false);
                        window.location.assign(`/dashboard/clients?id=${created.id}`);
                      }} />
        ) : (
          <>
            <header className="ws-cl__head">
              <ClientAvatar name={client.name} size="lg" />
              <div className="ws-cl__headtext">
                <div className="ws-cl__headline">
                  <h1>{client.name}</h1>
                  <ClientStatus status={client.status} />
                </div>
                <p className="ws-cl__headmeta">
                  {client.industry ? <span>{client.industry}</span> : null}
                  {location ? <span>{location}</span> : null}
                  {client.legal_name && client.legal_name !== client.name ? (
                    <span>Registered as {client.legal_name}</span>
                  ) : null}
                  {!client.industry && !location && !client.legal_name ? (
                    <span className="ws-cl__absent">
                      No company details recorded yet
                    </span>
                  ) : null}
                </p>
              </div>
              <span className="ws-cl__spacer" />
              <div className="ws-cl__headcounts">
                <span>{documentCountLabel(documents)}</span>
                {documents > 0 ? (
                  <span className="ws-cl__signed">{signed} signed</span>
                ) : null}
              </div>
              {can(P.CONTRACT_UPDATE) ? (
                <button type="button" className="ws-btn ws-btn--sm"
                        aria-expanded={editing}
                        onClick={() => { setEditing((was) => !was); setAdding(false); }}>
                  {editing ? "Cancel" : "Edit profile"}
                </button>
              ) : null}
              {/*
                Delete is offered ONLY for a profile with nothing filed under it,
                and that is a statement about the database rather than a UI
                preference: `contracts.counterparty_id` is `ON DELETE RESTRICT`
                (migration c8e4a1b7d2f6), so with documents present the server can
                only ever refuse. Offering it anyway would be a button whose whole
                purpose is to fail.

                The action does not vanish in that case — it becomes "Mark
                inactive", which is the specified way to retire a live client
                (`CLIENT_STATUSES`: "dormant or ended — documents stay, profile
                stops being current"). Two states, both of which do something.

                `documents` is the caller's own scoped count, so it can read 0 while
                another department's contract still points here. That is fine: this
                gate decides what to OFFER, and the server decides what happens —
                it re-checks unscoped and answers 409. Presentation only (47.6).
              */}
              {can(P.CONTRACT_ARCHIVE) && !editing ? (
                <ClientMenu label={`More actions for ${client.name}`}>
                  {documents === 0 ? (
                    <button type="button" role="menuitem"
                            className="ws-menu__item ws-menu__item--bad"
                            onClick={() => setDeleting(client)}>
                      Delete client
                    </button>
                  ) : (
                    <button type="button" role="menuitem" className="ws-menu__item"
                            onClick={() => { setEditing(true); setAdding(false); }}>
                      Mark inactive…
                    </button>
                  )}
                </ClientMenu>
              ) : null}
            </header>

            {editing ? (
              <ClientForm existing={client} knownClients={rail ?? []} members={members}
                          onCancel={() => setEditing(false)}
                          onSaved={(saved) => {
                            setEditing(false);
                            // Show the saved profile at once, then refetch: the
                            // detail endpoint owns the document list and the
                            // derived counts, which a PATCH never returns.
                            setClient(mergeProfile(client, saved));
                            void load();
                          }} />
            ) : null}

            {/* The compact information row — a horizontal strip, never five cards.
                Rendered only when there is something in it: a strip of five
                "Not available" cells is worse than none, and the Details tab is
                where the full picture (including what is missing) belongs. */}
            {!editing && hasProfileDetail(client) ? (
              <dl className="ws-cl__strip">
                <Fact label="Website" value={client.website}
                      href={websiteHref(client.website)} />
                <Fact label="Primary contact" value={client.primary_contact_name} />
                <Fact label="Legal contact" value={client.legal_contact_name} />
                <Fact label="Phone" value={client.primary_contact_phone} />
                <Fact label="Account owner" value={client.account_owner_name} />
              </dl>
            ) : null}

            {/* Real tabs: each one owns a panel, so `role="tab"` is honest here in
                a way the Dashboard's scope buttons were not (2026-09-08). */}
            <div className="ws-cl__tabs" role="tablist" aria-label="Client sections">
              {TABS.map((entry) => (
                <button key={entry.key} type="button" role="tab"
                        id={`ws-cl-tab-${entry.key}`}
                        aria-selected={tab === entry.key}
                        aria-controls={`ws-cl-panel-${entry.key}`}
                        tabIndex={tab === entry.key ? 0 : -1}
                        className={`ws-cl__tab${tab === entry.key ? " ws-cl__tab--active" : ""}`}
                        onClick={() => setTab(entry.key)}
                        onKeyDown={(event) => {
                          const at = TABS.findIndex((t) => t.key === tab);
                          const to = event.key === "ArrowRight" ? (at + 1) % TABS.length
                            : event.key === "ArrowLeft" ? (at - 1 + TABS.length) % TABS.length
                            : -1;
                          if (to < 0) return;
                          event.preventDefault();
                          const next = TABS[to]!.key;
                          setTab(next);
                          document.getElementById(`ws-cl-tab-${next}`)?.focus();
                        }}>
                  {entry.label}
                </button>
              ))}
            </div>

            <div id={`ws-cl-panel-${tab}`} role="tabpanel"
                 aria-labelledby={`ws-cl-tab-${tab}`} tabIndex={0}
                 className="ws-cl__panel">
              {tab === "documents" ? (
                <ClientDocuments client={client} onChanged={load} />
              ) : null}
              {tab === "details" ? <ClientDetails client={client} /> : null}
              {tab === "notes" ? (
                <ClientNotes client={client}
                             onSaved={(saved) => setClient(mergeProfile(client, saved))} />
              ) : null}
              {tab === "activity" ? <ClientActivityFeed clientId={client.id} /> : null}
            </div>
          </>
        )}
      </div>

      {deleting ? (
        <DeleteClientDialog
          client={deleting}
          onClose={() => setDeleting(null)}
          onDeleted={() => {
            // Back to the directory, which re-reads the list on mount — the
            // same full navigation `ClientForm` performs after a save, rather
            // than a router push that would leave this now-deleted client's
            // component mounted behind the transition.
            window.location.assign("/dashboard/clients");
          }}
        />
      ) : null}
    </div>
  );
}
