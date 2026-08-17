"use client";

/**
 * Audit view — locked 52.6 (Step 25), 42.18, AUD-01, 47.9.
 *
 * Read-only, because the trail is append-only at the database level (AUD-01). There
 * is no edit or delete control, and there is no endpoint for one.
 *
 * The `before_state` / `after_state` payloads are gated by the API behind
 * `legal_position.view`, not by `audit.view`: locked Step 24 r8 says a Super Admin
 * "does not automatically have access to confidential contract or Legal content", and
 * a decision type is Legal content. They are therefore rendered by testing whether
 * the property is **present**, exactly as in `EvaluationRow` — never by asking what
 * the caller may see, and with no marker where they were withheld (52.4).
 */

import { useCallback, useEffect, useState } from "react";

import { AccessRestricted } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading, Pager } from "@/components/Feedback";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AuditEvent, Pagination } from "@/lib/types";

export default function AuditPage() {
  const { can } = useSession();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [action, setAction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.auditEvents({
        page,
        ...(action ? { action } : {}),
        ...(entityType ? { entity_type: entityType } : {}),
      });
      setEvents(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page, action, entityType]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.AUDIT_VIEW)) return <AccessRestricted what="the audit trail" />;

  return (
    <>
      <h1>Audit trail</h1>
      <p className="hint">
        Append-only. Entries are never edited or removed, and this view cannot change
        them.
      </p>
      <ErrorBanner error={error} />

      <form className="card inline" onSubmit={(event) => event.preventDefault()}>
        <label>
          Action
          <input
            value={action}
            onChange={(event) => {
              setPage(1);
              setAction(event.target.value);
            }}
            placeholder="e.g. legal.decision_recorded"
          />
        </label>
        <label>
          Entity type
          <input
            value={entityType}
            onChange={(event) => {
              setPage(1);
              setEntityType(event.target.value);
            }}
            placeholder="e.g. evaluation"
          />
        </label>
      </form>

      {events === null ? (
        <Loading what="audit events" />
      ) : events.length === 0 ? (
        <EmptyState>No audit events match.</EmptyState>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Entity</th>
                <th>Actor</th>
                <th>Request</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id}>
                  <td>{event.timestamp ?? "—"}</td>
                  <td>{event.action}</td>
                  <td>
                    {event.entity_type}
                    {event.entity_id ? ` ${event.entity_id.slice(0, 8)}` : ""}
                    {/*
                      Presence-tested. Where the API omitted the payload there is no
                      cell content and no marker — its absence conveys nothing.
                    */}
                    {event.after_state !== undefined || event.before_state !== undefined ? (
                      <details>
                        <summary>state</summary>
                        <pre>
                          {JSON.stringify(
                            { before: event.before_state, after: event.after_state },
                            null,
                            2,
                          )}
                        </pre>
                      </details>
                    ) : null}
                  </td>
                  <td>{event.actor_id ? event.actor_id.slice(0, 8) : "—"}</td>
                  <td>{event.request_id ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {pagination ? (
            <Pager
              page={pagination.page}
              pageSize={pagination.page_size}
              total={pagination.total}
              onPage={setPage}
            />
          ) : null}
        </>
      )}
    </>
  );
}
