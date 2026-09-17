"use client";

/**
 * The client directory — every company this caller works with, one row each.
 *
 * A table, deliberately: DESIGN.md requires real table semantics for list data
 * (a screen-reader user needs the row/column relationship for dense rows), and
 * a card grid of companies would carry less information in more space. The
 * owner asked for the same thing — a clean list, because there may be many.
 *
 * **Search, filters and sort are all server-side** (`GET /counterparties`), so
 * the screen behaves the same with four hundred clients as with four. A
 * frontend-only filter was named as the thing to avoid.
 *
 * **No stat tiles.** DESIGN.md's anti-patterns rule out stat cards that are not
 * a real field with a defined meaning, and the numbers here belong to their
 * rows. The one aggregate worth stating — how many clients there are — is a
 * word in the header, and it says "you work with" because the count is scoped
 * to this caller (AB-13 r6).
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import { CLIENT_STATUSES, clientLocation } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Counterparty, DepartmentMembers, Pagination } from "@/lib/types";

import { relativeTime } from "@/components/workspace/model";
import {
  IconBuilding, IconClock, IconFile, IconFileCheck, IconPlus, IconSearch, IconUsers,
} from "@/components/workspace/icons";

import { ClientAvatar, ClientStatus } from "./ClientBits";
import { ClientForm } from "./ClientForm";
import { clientCountLabel, shortDate } from "./model";

const PAGE_SIZE = 25;

const COLUMNS = [
  "Company", "Industry", "Status", "Documents", "Signed", "Last activity",
  "Added", "",
] as const;

/** The header row, in one place — the table renders it and so does the
 *  skeleton, which must reserve its height or the body jumps on arrival. */
function TableHead() {
  return (
    <tr>
      {COLUMNS.map((column, index) => (
        <th key={column || `act-${index}`} scope="col">
          {column || <span className="ws-visually-hidden">Actions</span>}
        </th>
      ))}
    </tr>
  );
}

const SORTS = [
  { value: "name_asc", label: "Name (A–Z)" },
  { value: "name_desc", label: "Name (Z–A)" },
  { value: "recent_desc", label: "Recently active" },
  { value: "documents_desc", label: "Most documents" },
  { value: "added_desc", label: "Recently added" },
] as const;

/**
 * The first-run illustration: one client's file, at the moment it is started.
 *
 * **Decorative in full** — the stage that holds it carries `aria-hidden`, so
 * none of it reaches assistive technology. Everything it depicts is already
 * said in words by the heading, the body copy and the three statements below
 * it; announcing the picture as well would read the screen out three times.
 *
 * Composed from the design system's own parts rather than drawn as an asset:
 * the sheet is `--ws-surface` on `--ws-ink-100`, the letterhead tile and the
 * badge are `--ws-accent-soft`/`--ws-accent`. So it re-tints with the tokens,
 * adds no file to serve, and cannot drift from the product's palette.
 *
 * No gradient, no glow, no sparkle — DESIGN.md's anti-patterns rule out all
 * three, and a sparkle would additionally imply an AI-generated result, which
 * `AI-01` forbids this interface from ever suggesting. The owner's reference
 * also carried a dashed orbit; it was dropped on the owner's instruction
 * (2026-09-15) as decoration that states nothing.
 */
function ClientFileMark() {
  return (
    <span className="ws-cl__zero-sheet">
      <svg className="ws-cl__zero-paper" viewBox="0 0 152 198"
           aria-hidden="true" focusable="false">
        {/* The page, its top-right corner turned back. */}
        <path className="ws-cl__zero-page"
              d="M9 1 H115 L151 37 V189 A8 8 0 0 1 143 197 H9 A8 8 0 0 1 1 189 V9 A8 8 0 0 1 9 1 Z" />
        <path className="ws-cl__zero-fold" d="M115 1 L151 37 H123 A8 8 0 0 1 115 29 Z" />
        {/* Where a letterhead would be, and the lines of the agreement below. */}
        <rect className="ws-cl__zero-tile" x="24" y="30" width="62" height="62" rx="12" />
        <rect className="ws-cl__zero-rule" x="98" y="48" width="34" height="7" rx="3.5" />
        <rect className="ws-cl__zero-rule" x="98" y="65" width="24" height="7" rx="3.5" />
        <rect className="ws-cl__zero-rule" x="24" y="118" width="104" height="9" rx="4.5" />
        <rect className="ws-cl__zero-rule" x="24" y="139" width="86" height="9" rx="4.5" />
        <rect className="ws-cl__zero-rule" x="24" y="160" width="62" height="9" rx="4.5" />
      </svg>
      <span className="ws-cl__zero-glyph"><IconBuilding size={30} /></span>
      <span className="ws-cl__zero-badge"><IconPlus size={22} /></span>
    </span>
  );
}

export function ClientDirectory() {
  const { can } = useSession();
  const [clients, setClients] = useState<Counterparty[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [industries, setIndustries] = useState<string[]>([]);
  const [members, setMembers] = useState<DepartmentMembers | null>(null);
  const [page, setPage] = useState(1);
  const [qInput, setQInput] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [industry, setIndustry] = useState("");
  const [hasDocuments, setHasDocuments] = useState("");
  const [sort, setSort] = useState<string>("name_asc");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<unknown>(null);
  /** Which request is current — the same guard the Dashboard's list uses. Two
   *  requests are routinely in flight while somebody works the toolbar, and
   *  nothing makes them return in order; a slower earlier one landing second
   *  would repaint the table with the previous filter's rows while every
   *  control still read the new one. */
  const [seq, setSeq] = useState(0);

  const load = useCallback(async () => {
    const mine = seq + 1;
    setSeq(mine);
    setError(null);
    try {
      const result = await api.clients(page, PAGE_SIZE, {
        ...(q ? { q } : {}),
        ...(status ? { status } : {}),
        ...(industry ? { industry } : {}),
        ...(hasDocuments ? { has_documents: hasDocuments === "yes" } : {}),
        sort,
      });
      setClients(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
    // `seq` is deliberately absent from the dependency list: including it
    // would make every load schedule another one.
  }, [page, q, status, industry, hasDocuments, sort]);

  useEffect(() => {
    void load();
  }, [load]);

  // The industry filter offers what is actually in use — there is no taxonomy
  // to offer instead (rule 21). Best-effort: the table works without it.
  useEffect(() => {
    let cancelled = false;
    api.clientIndustries()
      .then((result) => { if (!cancelled) setIndustries(result); })
      .catch(() => { if (!cancelled) setIndustries([]); });
    return () => { cancelled = true; };
  }, [clients]);

  useEffect(() => {
    let cancelled = false;
    api.departmentMembers()
      .then((result) => { if (!cancelled) setMembers(result); })
      .catch(() => { if (!cancelled) setMembers(null); });
    return () => { cancelled = true; };
  }, []);

  // Debounced search, one request per pause.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setPage(1);
      setQ(qInput.trim());
    }, 300);
    return () => window.clearTimeout(timer);
  }, [qInput]);

  if (!can(P.CONTRACT_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include document access.</p>
      </div>
    );
  }

  const canAdd = can(P.CONTRACT_UPDATE);
  const filtered = Boolean(q || status || industry || hasDocuments);
  const firstRun = clients !== null && clients.length === 0 && page === 1 && !filtered;
  const stale = Boolean(clients && clients.length > 0);
  const pageCount = pagination
    ? Math.max(1, Math.ceil(pagination.total / pagination.page_size))
    : 1;

  return (
    <>
      {/* `.ws-context` is the shell header EVERY screen uses, and it keeps
          exactly the rules it had: the stacked title block is styled entirely
          through the `ws-cl__*` children below, so no other page moves.

          There was a second marker class here (`ws-cl__context`) carrying no
          rule of its own — the page-local scoping is already in the child
          names, so it did nothing. `styled-classes.test.ts` (new on main, #50)
          catches exactly that, correctly, and it is removed rather than given a
          no-op rule to quiet the guard.

          The count stays — it is a real field, scoped to this caller (AB-13
          r6), and the owner's reference dropping it was a mock simplification
          rather than a decision. */}
      <div className="ws-context">
        <span className="ws-context__icon" aria-hidden="true">
          <IconUsers size={18} />
        </span>
        <div className="ws-cl__titles">
          <div className="ws-cl__titlerow">
            <h1>Client profiles</h1>
            {pagination ? (
              <span className="ws-context__meta ws-mono">
                {clientCountLabel(pagination.total)} you work with
              </span>
            ) : null}
          </div>
          <p className="ws-cl__subtitle">
            Manage your clients and their legal documents in one place.
          </p>
        </div>
        <span className="ws-context__spacer" />
        {/* Hidden on the true first-run screen (owner, 2026-09-17): the
            centered "+ Add client" button in the empty-state card is already
            the page's one call to action there, and closing the form it opens
            is handled by the form's own Cancel button — so this header control
            has nothing left to do until at least one client exists. It returns
            for every other state: populated, loading, and filtered-to-nothing
            (a real client exists somewhere, just not on this view). */}
        {canAdd && !firstRun ? (
          <div className="ws-context__acts">
            <button type="button" className="ws-btn ws-btn--primary"
                    aria-expanded={adding} aria-controls="ws-cl-addpanel"
                    onClick={() => setAdding((was) => !was)}>
              {adding ? "Close" : "+ Add client"}
            </button>
          </div>
        ) : null}
      </div>

      <div className="ws-cl ws-cl--index">
        {adding ? (
          <div id="ws-cl-addpanel">
            <ClientForm knownClients={clients ?? []} members={members}
                        onCancel={() => setAdding(false)}
                        onSaved={(created) => {
                          setAdding(false);
                          window.location.assign(`/dashboard/clients?id=${created.id}`);
                        }} />
          </div>
        ) : null}

        {/* The whole "existing list" section — toolbar, any load error, and the
            table/empty-state ternary below — steps aside while the Add Client
            form is open (owner, 2026-09-17): the list is already one click
            away via Client Profiles, and showing it under the form duplicated
            it for no reason. Wrapped once here rather than adding `!adding` to
            each branch individually, so the three pieces cannot drift apart on
            whether they respect it.

            The underlying data keeps loading regardless — `load()` runs
            unconditionally on mount — so `knownClients` (the duplicate-name
            check inside the form) and the list a Cancel returns to are both
            already current; only the RENDER is withheld. */}
        {!adding ? (
          <>
            {!firstRun ? (
              <div className="ws-cl__toolbar">
                <label className="ws-cl__search">
                  <span className="ws-visually-hidden">Search clients</span>
                  <span className="ws-cl__searchicon" aria-hidden="true">
                    <IconSearch size={14} />
                  </span>
                  <input value={qInput} maxLength={200}
                         placeholder="Search clients…"
                         onChange={(event) => setQInput(event.target.value)} />
                </label>
                <label className="ws-cl__select">
                  <span className="ws-visually-hidden">Filter by status</span>
                  <select value={status}
                          onChange={(event) => { setStatus(event.target.value); setPage(1); }}>
                    <option value="">Any status</option>
                    {CLIENT_STATUSES.map((entry) => (
                      <option key={entry.state} value={entry.state}>{entry.label}</option>
                    ))}
                  </select>
                </label>
                {/* Absent until somebody has recorded an industry — a select whose
                    only option is "Any" is furniture. */}
                {industries.length > 0 ? (
                  <label className="ws-cl__select">
                    <span className="ws-visually-hidden">Filter by industry</span>
                    <select value={industry}
                            onChange={(event) => { setIndustry(event.target.value); setPage(1); }}>
                      <option value="">Any industry</option>
                      {industries.map((name) => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </select>
                  </label>
                ) : null}
                <label className="ws-cl__select">
                  <span className="ws-visually-hidden">Filter by documents</span>
                  <select value={hasDocuments}
                          onChange={(event) => { setHasDocuments(event.target.value); setPage(1); }}>
                    <option value="">With or without documents</option>
                    <option value="yes">Has documents</option>
                    <option value="no">No documents yet</option>
                  </select>
                </label>
                <span className="ws-cl__spacer" />
                <label className="ws-cl__select">
                  <span className="ws-visually-hidden">Sort</span>
                  <select value={sort}
                          onChange={(event) => { setSort(event.target.value); setPage(1); }}>
                    {SORTS.map((entry) => (
                      <option key={entry.value} value={entry.value}>{entry.label}</option>
                    ))}
                  </select>
                </label>
              </div>
            ) : null}

            {error ? (
              <div className={`ws-state ws-state--${stale ? "warn" : "error"}`} role="alert">
                <h2>
                  {stale ? "These results could not be refreshed."
                    : "Client profiles could not be loaded."}
                </h2>
                <p>
                  {describeError(error)}
                  {stale ? " The rows below are the last ones loaded successfully." : ""}
                </p>
                <button type="button" className="ws-btn ws-btn--sm"
                        onClick={() => void load()}>
                  Try again
                </button>
              </div>
            ) : null}

            {clients === null ? (
              /* The column header is part of the loading state, not something that
                 appears afterwards — the 2026-09-08 lesson from the Dashboard:
                 rendering rows without it moved everything down by the header's
                 height the instant data landed, a layout shift on first paint,
                 every visit. Six rows hold roughly a full page's height for the
                 same reason. A bare "Loading clients…" left most of a 1440×900
                 viewport blank, which is what the owner's instruction rules out
                 ("Do not leave users looking at a blank page while data loads"). */
              <div className="ws-cl__table ws-cl__table--skel">
                <p className="ws-visually-hidden" role="status" aria-live="polite">
                  Loading clients…
                </p>
                <table aria-hidden="true"><thead><TableHead /></thead></table>
                {[0, 1, 2, 3, 4, 5].map((row) => (
                  <div key={row} className="ws-cl__skel" aria-hidden="true">
                    <span className="ws-skel ws-skel--line" style={{ width: "30%" }} />
                    <span className="ws-skel ws-skel--line" style={{ width: "14%" }} />
                    <span className="ws-skel ws-skel--line" style={{ width: "10%" }} />
                    <span className="ws-skel ws-skel--line" style={{ width: "8%" }} />
                  </div>
                ))}
              </div>
            ) : firstRun ? (
              /* No `adding` check needed here — the enclosing `!adding` wrapper
                 above already keeps this whole ternary from rendering while the
                 form is open, so this branch is reached only when it should show. */
              <div className="ws-cl__zero">
                {/* Decorative in full — see `ClientFileMark`. Every word here is
                    repeated as real text in the three statements below, so the
                    stage is hidden from assistive technology rather than
                    announced as four more unlabelled graphics. */}
                <div className="ws-cl__zero-stage" aria-hidden="true">
                  <span className="ws-cl__zero-tip ws-cl__zero-tip--a">
                    <IconFile size={18} />
                    <span>Organise all agreements</span>
                  </span>
                  <span className="ws-cl__zero-tip ws-cl__zero-tip--b">
                    <IconUsers size={18} />
                    <span>Keep key contacts handy</span>
                  </span>
                  <span className="ws-cl__zero-tip ws-cl__zero-tip--c">
                    <IconFileCheck size={18} />
                    <span>Track status and documents</span>
                  </span>
                  {/* "Past reviews stay with the client", not the reference's
                      "Save time on future reviews": the second promises an
                      outcome, and DESIGN.md allows this screen to describe what
                      the product does, never to advertise a result. */}
                  <span className="ws-cl__zero-tip ws-cl__zero-tip--d">
                    <IconClock size={18} />
                    <span>Past reviews stay with the client</span>
                  </span>
                  <ClientFileMark />
                </div>

                <h2>No client profiles yet</h2>
                <p>
                  Create a client profile to organise their legal documents — every
                  agreement, its versions and its review, in one place.
                </p>
                {canAdd ? (
                  /* The same handler as the header's button, deliberately: one
                     action, reachable from two places. It is the LARGER of the
                     two so the page still has one primary call to action — the
                     header's keeps the standard 36px height. */
                  <button type="button" className="ws-btn ws-btn--primary ws-btn--lg"
                          onClick={() => setAdding(true)}>
                    <IconPlus size={18} />
                    Add client
                  </button>
                ) : null}

                {/* Three statements of what a client profile already holds. Not
                    links, not filters, not counts — nothing here is a control,
                    and nothing describes a capability the product lacks. */}
                <ul className="ws-cl__zero-benefits">
                  <li>
                    <span className="ws-cl__zero-bmark" aria-hidden="true">
                      <IconFile size={18} />
                    </span>
                    <span className="ws-cl__zero-btext">
                      <span className="ws-cl__zero-btitle">Centralised information</span>
                      <span className="ws-cl__zero-bbody">
                        Store all client details and documents together.
                      </span>
                    </span>
                  </li>
                  <li>
                    <span className="ws-cl__zero-bmark" aria-hidden="true">
                      <IconFileCheck size={18} />
                    </span>
                    <span className="ws-cl__zero-btext">
                      <span className="ws-cl__zero-btitle">Faster reviews</span>
                      <span className="ws-cl__zero-bbody">
                        Quickly access past agreements and versions.
                      </span>
                    </span>
                  </li>
                  <li>
                    <span className="ws-cl__zero-bmark" aria-hidden="true">
                      <IconUsers size={18} />
                    </span>
                    <span className="ws-cl__zero-btext">
                      <span className="ws-cl__zero-btitle">Better collaboration</span>
                      <span className="ws-cl__zero-bbody">
                        Keep your team aligned with updated information.
                      </span>
                    </span>
                  </li>
                </ul>
              </div>
            ) : clients.length === 0 ? (
              <div className="ws-state">
                <h2>No clients match these filters.</h2>
                <p>Try a different search, or clear the filters to see everyone.</p>
                <button type="button" className="ws-btn ws-btn--sm" onClick={() => {
                  setQInput(""); setQ(""); setStatus(""); setIndustry("");
                  setHasDocuments(""); setPage(1);
                }}>
                  Clear filters
                </button>
              </div>
            ) : (
              <>
                <div className="ws-cl__table">
                  <table>
                    <thead><TableHead /></thead>
                    <tbody>
                      {clients.map((client) => {
                        const location = clientLocation(client);
                        return (
                          <tr key={client.id}>
                            <td>
                              <Link className="ws-cl__row"
                                    href={`/dashboard/clients?id=${client.id}`}>
                                <ClientAvatar name={client.name} />
                                <span className="ws-cl__rowtext">
                                  <span className="ws-cl__rowname">{client.name}</span>
                                  {location ? (
                                    <span className="ws-cl__rowloc">{location}</span>
                                  ) : null}
                                </span>
                              </Link>
                            </td>
                            <td>
                              {client.industry ?? (
                                <span className="ws-cl__absent">Not recorded</span>
                              )}
                            </td>
                            <td><ClientStatus status={client.status} /></td>
                            <td className="ws-mono">{client.documents ?? 0}</td>
                            <td className="ws-mono">{client.signed_documents ?? 0}</td>
                            <td className="ws-mono">{relativeTime(client.last_activity)}</td>
                            <td className="ws-mono">{shortDate(client.created_at) ?? "—"}</td>
                            <td className="ws-cl__rowact">
                              {/* A quiet link, not a bordered button. Eleven
                                  outlined buttons down the right edge drew more
                                  attention than the company names beside them,
                                  and the name itself is already the primary way
                                  in — this is the explicit affordance for a
                                  reader who wants a target to aim at, not a
                                  second, louder one. */}
                              <Link href={`/dashboard/clients?id=${client.id}`}>
                                Open
                              </Link>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {pageCount > 1 ? (
                  <div className="ws-pager">
                    <button type="button" className="ws-btn ws-btn--sm" disabled={page <= 1}
                            onClick={() => setPage((p) => Math.max(1, p - 1))}>
                      Previous
                    </button>
                    <span className="ws-pane__note ws-mono">
                      Page {page} of {pageCount}
                    </span>
                    <button type="button" className="ws-btn ws-btn--sm"
                            disabled={page >= pageCount}
                            onClick={() => setPage((p) => p + 1)}>
                      Next
                    </button>
                  </div>
                ) : null}
              </>
            )}
          </>
        ) : null}
      </div>
    </>
  );
}
