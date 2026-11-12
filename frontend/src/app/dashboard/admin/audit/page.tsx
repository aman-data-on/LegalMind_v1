"use client";

/**
 * Administration → Audit log. Who did what, to what, when.
 *
 * Read-only by construction (AUD-01: append-only at the database level; the API
 * has no write verb), so reading is all this screen can do — densely.
 *
 * Two confidentiality rules are visible in what it renders:
 *
 *   the payload    `before_state`/`after_state` arrive for identity-and-access
 *                  events and are OMITTED for everything else unless the caller
 *                  holds `legal_position.view` (Step 24 r8). An omitted field is
 *                  never rendered as a blank, so absence says nothing.
 *   the label      an entity is named only when it is a user, department, role
 *                  or session. A contract is deliberately never named here —
 *                  the administrator can see that one changed and not which.
 *
 * Filters are the API's allow-list (49.6): exact action, exact entity type, a
 * date range, and the administrative narrowing. Never free text — a filter must
 * not become a probe.
 */

import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AuditEvent, Pagination } from "@/lib/types";

import { AdminNav, COMMON_ACTIONS, actionWords, dateTime } from "@/components/admin/AdminShell";
import { ErrorState } from "@/components/Feedback";
import { AccessRestricted } from "@/components/AccessRestricted";
import { PageHeader } from "@/components/page/PageHeader";
import { StackTable } from "@/components/StackTable";
import { FilterPanel } from "@/components/FilterPanel";

const PAGE_SIZE = 50;

export default function AuditPage() {
  const { can } = useSession();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [filter, setFilter] = useState({
    action: "", entity_type: "", since: "", administrative: false,
  });
  const [draft, setDraft] = useState(filter);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Only for an account that may see it — no refused request before "Access
  // restricted" (review, 2026-10-14).
  const allowed = can(P.AUDIT_VIEW);
  const load = useCallback(async () => {
    if (!allowed) return;
    setError(null);
    try {
      const result = await api.auditEvents({
        page,
        page_size: PAGE_SIZE,
        ...(filter.action ? { action: filter.action } : {}),
        ...(filter.entity_type ? { entity_type: filter.entity_type } : {}),
        // A date input gives `YYYY-MM-DD`; the server takes it as midnight UTC.
        ...(filter.since ? { since: `${filter.since}T00:00:00+00:00` } : {}),
        ...(filter.administrative ? { administrative: "true" } : {}),
      });
      setEvents(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [allowed, page, filter]);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setPage(1); }, [filter]);

  if (!allowed) {
    return (
      // one restricted state everywhere (GP-23): the page keeps its h1, the note is AccessRestricted
      <div className="lm-page">
        <PageHeader title="Administration" />
        <AccessRestricted what="the audit trail" />
      </div>
    );
  }

  const pageCount = pagination
    ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;

  return (
    <div className="ws-admin">
      <header className="ws-admin__head">
        <div>
          <h1>Administration</h1>
          <p className="ws-pane__note">
            Entries are permanent. Nothing here can be changed.
          </p>
        </div>
      </header>

      <AdminNav />

      <form onSubmit={(event) => { event.preventDefault(); setFilter(draft); }}>
        <FilterPanel active={[filter.action, filter.entity_type, filter.since].filter(Boolean).length
          + (filter.administrative ? 1 : 0)}>
        <label className="ws-field">
          <span className="ws-field__label">Action</span>
          <select
            value={COMMON_ACTIONS.some((a) => a.value === draft.action) ? draft.action : ""}
            onChange={(event) => setDraft({ ...draft, action: event.target.value })}
          >
            {COMMON_ACTIONS.map((action) => (
              <option key={action.value} value={action.value}>{action.label}</option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Record type</span>
          <input
            value={draft.entity_type}
            placeholder="user, department, role…"
            onChange={(event) => setDraft({ ...draft, entity_type: event.target.value })}
          />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Since</span>
          <input
            type="date"
            value={draft.since}
            onChange={(event) => setDraft({ ...draft, since: event.target.value })}
          />
        </label>
        <label className="ws-field ws-field--check">
          <input
            type="checkbox"
            checked={draft.administrative}
            onChange={(event) =>
              setDraft({ ...draft, administrative: event.target.checked })}
          />
          <span className="ws-field__label">Account &amp; access only</span>
        </label>
        <button type="submit" className="ws-btn">Apply</button>
        </FilterPanel>
      </form>

      {error ? (
        <ErrorState title="The audit trail could not be loaded" error={error} onRetry={() => void load()} />
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

      {events !== null && events.length === 0 && !error ? (
        <div className="ws-state">
          <h2>No events match.</h2>
          <p>Action and entity type match exact values — a partial name matches nothing.</p>
        </div>
      ) : null}

      {events !== null && events.length > 0 ? (
        <StackTable columns={[{ label: "When" }, { label: "Who" }, { label: "Did what" }, { label: "To what" }, { label: "Details" }]}>
              {events.map((event) => {
                // Presence-tested, never null-tested: the field is omitted when
                // the caller may not read it (49.7 r4 / Step 52.4).
                const payload = "after_state" in event || "before_state" in event;
                const open = expanded === event.id;
                return (
                  <tr key={event.id}>
                    <td className="ws-num">{dateTime(event.timestamp)}</td>
                    <td>
                      {event.actor
                        ? <span title={event.actor.email}>{event.actor.name}</span>
                        : <span className="ws-pane__note">system</span>}
                    </td>
                    <td>{actionWords(event.action)}</td>
                    <td>
                      {event.entity_label
                        ? <span>{event.entity_label}</span>
                        : <span className="ws-pane__note">{(event.entity_type ?? "").replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()) || "—"}</span>}
                    </td>
                    <td>
                      {/* B3 p2: codes and ids only here, on request */}
                      <button type="button" className="ws-link ws-auditshow" aria-expanded={open}
                              onClick={() => setExpanded(open ? null : event.id)}>
                        {open ? "Hide" : "Show"}
                      </button>
                      {open ? (
                        <pre className="ws-auditpayload">
                          {JSON.stringify({
                            action: event.action, record: event.entity_type, id: event.entity_id,
                            ...(payload ? { before: event.before_state, after: event.after_state } : {}),
                          }, null, 2)}
                        </pre>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
        </StackTable>
      ) : null}

      {pagination && pagination.total > pagination.page_size ? (
        <nav className="ws-pager" aria-label="Pagination">
          <button type="button" className="ws-btn" disabled={pagination.page <= 1}
                  onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span className="ws-num">
            Page {pagination.page} of {pageCount} · {pagination.total} events
          </span>
          <button type="button" className="ws-btn" disabled={pagination.page >= pageCount}
                  onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </nav>
      ) : null}
    </div>
  );
}
