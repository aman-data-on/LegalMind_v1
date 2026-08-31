"use client";

/**
 * Admin — the audit trail (slice 7; PRODUCT_UX_ROADMAP §E screen 12). Read-only
 * by construction (AUD-01: the table is append-only at the database level;
 * the API has no write verb) — so reading is all this screen can do, densely.
 *
 * Filters are the API's allow-list (49.6): action and entity type, exact
 * values, never free-text search — a filter must not become a probe. The
 * before/after state payloads are gated behind `legal_position.view` and
 * arrive OMITTED otherwise (Step 24 r8); this table does not render them at
 * all, so an omitted field never shows as a suspicious blank.
 */

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AuditEvent, Pagination } from "@/lib/types";

const PAGE_SIZE = 50;

export default function AuditPage() {
  const { can } = useSession();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  // The submitted filter (drives the query) and the draft being typed.
  const [filter, setFilter] = useState<{ action: string; entity_type: string }>({ action: "", entity_type: "" });
  const [draft, setDraft] = useState(filter);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.auditEvents({
        page,
        page_size: PAGE_SIZE,
        ...(filter.action ? { action: filter.action } : {}),
        ...(filter.entity_type ? { entity_type: filter.entity_type } : {}),
      });
      setEvents(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page, filter]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.AUDIT_VIEW)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include audit access.</p>
      </div>
    );
  }

  return (
    <>
      <div className="ws-context">
        <h1>Audit trail</h1>
        <div className="ws-context__meta">
          {pagination ? <span className="ws-mono">{pagination.total} events</span> : null}
          <Link href="/workspace/admin">Users &amp; roles</Link>
        </div>
      </div>
      <div className="ws-docs">
        <form
          className="ws-auditfilter"
          onSubmit={(event) => {
            event.preventDefault();
            setPage(1);
            setEvents(null);
            setFilter({ action: draft.action.trim(), entity_type: draft.entity_type.trim() });
          }}
          aria-label="Filter events"
        >
          <label className="ws-field">
            <span className="ws-field__label">Action</span>
            <input
              value={draft.action}
              onChange={(event) => setDraft((d) => ({ ...d, action: event.target.value }))}
              placeholder="e.g. admin.user_created"
            />
          </label>
          <label className="ws-field">
            <span className="ws-field__label">Entity type</span>
            <input
              value={draft.entity_type}
              onChange={(event) => setDraft((d) => ({ ...d, entity_type: event.target.value }))}
              placeholder="e.g. user"
            />
          </label>
          <button type="submit" className="ws-btn">
            Apply
          </button>
        </form>
        <p className="ws-pane__note">
          Append-only — reading is all this screen can do. Filters match exact values.
        </p>

        {error ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>The audit trail could not be loaded.</h2>
            <p>{describeError(error)}</p>
          </div>
        ) : null}

        {events === null && !error ? (
          <div className="ws-docs__table" aria-busy="true">
            <p className="ws-visually-hidden" role="status" aria-live="polite">
              Loading events…
            </p>
            {[0, 1, 2, 3].map((row) => (
              <div key={row} className="ws-docs__skel" aria-hidden="true">
                <span className="ws-skel ws-skel--line" style={{ width: "18%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "30%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "22%" }} />
              </div>
            ))}
          </div>
        ) : null}

        {events !== null && events.length === 0 ? (
          <div className="ws-state">
            <h2>No events match.</h2>
            <p>Filters match exact values — a partial action name matches nothing.</p>
          </div>
        ) : null}

        {events !== null && events.length > 0 ? (
          <div className="ws-docs__table">
            <table>
              <thead>
                <tr>
                  <th scope="col">When</th>
                  <th scope="col">Action</th>
                  <th scope="col">Entity</th>
                  <th scope="col">Actor</th>
                  <th scope="col">Request</th>
                </tr>
              </thead>
              <tbody>
                {events.map((event) => (
                  <tr key={event.id}>
                    <td className="ws-mono">{event.timestamp ? event.timestamp.slice(0, 19).replace("T", " ") : "—"}</td>
                    <td className="ws-mono">{event.action}</td>
                    <td>
                      {event.entity_type}
                      {event.entity_id ? <span className="ws-mono"> {event.entity_id.slice(0, 8)}</span> : null}
                    </td>
                    <td className="ws-mono">{event.actor_id ? event.actor_id.slice(0, 8) : "system"}</td>
                    <td className="ws-mono">{event.request_id ? event.request_id.slice(0, 8) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {pagination && pagination.total > pagination.page_size ? (
          <nav className="ws-pager" aria-label="Pagination">
            <button type="button" className="ws-btn" disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="ws-mono">
              Page {pagination.page} of {Math.ceil(pagination.total / pagination.page_size)}
            </span>
            <button
              type="button"
              className="ws-btn"
              disabled={pagination.page * pagination.page_size >= pagination.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </nav>
        ) : null}
      </div>
    </>
  );
}
