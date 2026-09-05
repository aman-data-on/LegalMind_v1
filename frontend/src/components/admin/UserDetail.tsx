"use client";

/**
 * One account, in full — identity, access, and what has happened to it.
 *
 * Everything mutable here goes through the authoritative path and nothing is
 * decided locally: role grants run S-8 server-side, department changes and
 * status changes run S-9 plus the SEC-05 / administrative-lockout guards, and
 * every refusal is rendered verbatim beside the control that caused it rather
 * than being pre-empted by a disabled button. A pre-check would eventually
 * disagree with the server, and the server is the one that matters (43.23).
 *
 * The history panel is the existing audit endpoint filtered by `entity_id` — no
 * second store, no per-user event table.
 */

import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import type { AuditEvent, Department, Role, User } from "@/lib/types";

import { ASSIGNABLE_TIERS, AccountStatus, TIER_LABEL, TIER_ORDER, dateTime, signInMethod } from "./AdminShell";

export function UserDetail({
  user, roles, departments, canGrant, onChanged, onClose,
}: {
  user: User;
  roles: Role[] | null;
  departments: Department[] | null;
  canGrant: boolean;
  onChanged: (user: User) => void;
  onClose: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [grantCode, setGrantCode] = useState("");
  const [history, setHistory] = useState<AuditEvent[] | null>(null);

  const loadHistory = useCallback(async () => {
    try {
      // The same audit endpoint every other screen reads, narrowed to this
      // account. `audit.view` gates it; an administrator without it simply
      // gets no panel rather than an error about a screen they did not ask for.
      const result = await api.auditEvents({ entity_id: user.id, page_size: 25 });
      setHistory(result.items);
    } catch {
      setHistory([]);
    }
  }, [user.id]);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  async function act(operation: () => Promise<User>) {
    setBusy(true);
    setError(null);
    try {
      onChanged(await operation());
      await loadHistory();
    } catch (cause) {
      // SEC-05's last-authority refusal and every S-8/S-9 result land here,
      // worded by the server.
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  const roleName = (code: string) => roles?.find((r) => r.code === code)?.name ?? code;
  const grantable = (roles ?? [])
    .filter((role) => !user.roles.includes(role.code))
    .filter((role) => ASSIGNABLE_TIERS.includes(role.tier))
    .sort((a, b) => TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier)
      || a.name.localeCompare(b.name));
  const active = user.status === "ACTIVE";

  return (
    <aside className="ws-detail" aria-label={`Account ${user.email}`}>
      <header className="ws-detail__head">
        <div>
          <h2 className="ws-detail__title">{user.name}</h2>
          <p className="ws-detail__sub ws-mono">{user.email}</p>
        </div>
        <button type="button" className="ws-btn ws-btn--sm" onClick={onClose}>
          Close
        </button>
      </header>

      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}

      <dl className="ws-deflist">
        <div><dt>Status</dt><dd><AccountStatus status={user.status} /></dd></div>
        <div><dt>Department</dt><dd>{user.department?.name ?? "None"}</dd></div>
        <div><dt>Sign-in</dt><dd>{signInMethod(user)}</dd></div>
        <div><dt>Last sign-in</dt><dd>{user.last_login_at ? dateTime(user.last_login_at) : "Never"}</dd></div>
        <div><dt>Created</dt><dd>{dateTime(user.created_at)}</dd></div>
        <div><dt>Updated</dt><dd>{dateTime(user.updated_at)}</dd></div>
        <div>
          <dt>Provisioned by</dt>
          <dd>{user.provisioned_by
            ? `${user.provisioned_by.name} (${user.provisioned_by.email})`
            : "Not recorded"}</dd>
        </div>
      </dl>

      <section className="ws-detail__section">
        <h3>Access</h3>
        {user.roles.length === 0 ? (
          <p className="ws-pane__note">No roles — this account cannot act yet.</p>
        ) : null}
        <div className="ws-detail__roles">
          {user.roles.map((code) => (
            <span key={code} className="ws-rolechip">
              <span className="ws-chip" title={code}>{roleName(code)}</span>
              {canGrant ? (
                <button
                  type="button"
                  className="ws-rolechip__revoke ws-rolechip__revoke--icon"
                  aria-label={`Revoke ${code} from ${user.email}`}
                  disabled={busy}
                  onClick={() => void act(() => api.revokeRole(user.id, code))}
                  title={`Revoke ${code}`}
                >
                  <span aria-hidden="true">×</span>
                </button>
              ) : null}
            </span>
          ))}
        </div>
        {canGrant && grantable.length > 0 ? (
          <div className="ws-grant">
            <label className="ws-visually-hidden" htmlFor={`grant-${user.id}`}>
              Role to grant to {user.email}
            </label>
            <select
              id={`grant-${user.id}`}
              value={grantCode}
              disabled={busy}
              onChange={(event) => setGrantCode(event.target.value)}
            >
              <option value="">Grant a role…</option>
              {TIER_ORDER.filter((tier) => grantable.some((r) => r.tier === tier)).map((tier) => (
                <optgroup key={tier} label={TIER_LABEL[tier]}>
                  {grantable.filter((r) => r.tier === tier).map((role) => (
                    <option key={role.code} value={role.code}>{role.name}</option>
                  ))}
                </optgroup>
              ))}
            </select>
            <button
              type="button"
              className="ws-btn"
              disabled={busy || !grantCode}
              onClick={() => void act(async () => {
                const next = await api.grantRole(user.id, grantCode);
                setGrantCode("");
                return next;
              })}
            >
              Grant
            </button>
          </div>
        ) : null}
        {!canGrant ? (
          <p className="ws-pane__note">
            Granting roles needs role administration, which this account does not include.
          </p>
        ) : null}
      </section>

      <section className="ws-detail__section">
        <h3>Department</h3>
        <label className="ws-field">
          <span className="ws-visually-hidden">Department for {user.email}</span>
          <select
            value={user.department?.id ?? ""}
            disabled={busy || departments === null}
            onChange={(event) => void act(() =>
              api.updateUser(user.id, { department_id: event.target.value || null }))}
          >
            <option value="">No department</option>
            {(departments ?? []).map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </label>
        <p className="ws-pane__note">
          A Department Lead sees every deal owned by someone in their department. Moving this account
          moves what its Lead can see; it does not move the deals themselves.
        </p>
      </section>

      <section className="ws-detail__section">
        <h3>Account</h3>
        <div className="ws-detail__acts">
          <button
            type="button"
            className="ws-btn"
            disabled={busy}
            onClick={() => void act(() =>
              api.updateUser(user.id, { status: active ? "DISABLED" : "ACTIVE" }))}
          >
            {active ? "Disable account" : "Re-enable account"}
          </button>
        </div>
        <p className="ws-pane__note">
          Disabling signs the account out immediately and refuses every future sign-in. The
          server refuses a change that would leave nobody able to administer the platform.
        </p>
      </section>

      <section className="ws-detail__section">
        <h3>History</h3>
        {history === null ? (
          <p className="ws-pane__note" role="status">Loading history…</p>
        ) : history.length === 0 ? (
          <p className="ws-pane__note">Nothing recorded against this account yet.</p>
        ) : (
          <ul className="ws-timeline">
            {history.map((event) => (
              <li key={event.id}>
                <span className="ws-mono ws-timeline__when">{dateTime(event.timestamp)}</span>
                <span className="ws-timeline__what">{event.action}</span>
                <span className="ws-pane__note">
                  {event.actor ? `by ${event.actor.name}` : "by the system"}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}
