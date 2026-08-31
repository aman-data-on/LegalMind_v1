"use client";

/**
 * Admin — Users & roles (slice 7; PRODUCT_UX_ROADMAP §E screen 11, §H). The
 * control plane, deliberately separate from the legal workflow: SUPER_ADMIN
 * provisions accounts and composes authority here, and holds no legal
 * authority of its own (Step 23; SEC-02).
 *
 * Three server rules this screen surfaces rather than re-implements:
 *
 *   47.1.3   a new account holds NO roles — authority is a later, deliberate
 *            grant, never a side effect of creation; credentials are
 *            provisioned outside this screen entirely
 *   SEC-05   disabling or de-granting the last ACTIVE Legal Decision
 *            Authority is refused server-side — the refusal renders beside
 *            the row that caused it, unaltered
 *   S-8/S-9  who may administer whom, and who may grant what, are server
 *            checks; a 403 here is a result, not a pre-check (43.23)
 *
 * The grant control needs the role list, which `GET /roles` gates on
 * `role.manage` — an account holding only `user.manage` sees the roles a user
 * already has (revocable) and a plain note instead of a grant form.
 */

import { useCallback, useEffect, useState } from "react";

import Link from "next/link";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Pagination, Role, User } from "@/lib/types";

const PAGE_SIZE = 25;

export default function AdminUsersPage() {
  const { can } = useSession();
  const [users, setUsers] = useState<User[] | null>(null);
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);
  const canGrant = can(P.ROLE_MANAGE);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.users({ page, page_size: PAGE_SIZE });
      setUsers(result.items);
      setPagination(result.pagination);
      if (canGrant) {
        // Five canonical roles; one page is the whole vocabulary.
        setRoles((await api.roles({ page_size: 100 })).items);
      }
    } catch (cause) {
      setError(cause);
    }
  }, [page, canGrant]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.USER_MANAGE)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include user administration.</p>
      </div>
    );
  }

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setCreating(true);
    setCreateError(null);
    try {
      await api.createUser(email.trim(), name.trim());
      setEmail("");
      setName("");
      await load();
    } catch (cause) {
      setCreateError(cause);
    } finally {
      setCreating(false);
    }
  }

  const replaceUser = (next: User) =>
    setUsers((current) => current?.map((u) => (u.id === next.id ? next : u)) ?? null);

  return (
    <>
      <div className="ws-context">
        <h1>Admin</h1>
        <div className="ws-context__meta">
          {pagination ? <span className="ws-mono">{pagination.total} account{pagination.total === 1 ? "" : "s"}</span> : null}
          {can(P.AUDIT_VIEW) ? <Link href="/workspace/admin/audit">Audit trail</Link> : null}
        </div>
      </div>
      <div className="ws-docs">
        <form className="ws-intake" onSubmit={create} aria-labelledby="ws-admin-create">
          <h2 id="ws-admin-create" className="ws-intake__title">
            Add an account
          </h2>
          <div className="ws-intake__fields">
            <label className="ws-field">
              <span className="ws-field__label">
                Work email <span className="ws-field__req">(required)</span>
              </span>
              <input
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={creating}
              />
            </label>
            <label className="ws-field ws-field--type">
              <span className="ws-field__label">
                Name <span className="ws-field__req">(required)</span>
              </span>
              <input required value={name} onChange={(event) => setName(event.target.value)} disabled={creating} />
              <span className="ws-field__help">
                A new account holds no roles — authority is a separate, deliberate grant.
                Credentials are provisioned outside this screen.
              </span>
            </label>
            <button type="submit" className="ws-btn ws-btn--primary" disabled={creating || !email.trim() || !name.trim()}>
              {creating ? "Adding…" : "Add account"}
            </button>
          </div>
          {createError ? (
            <p className="ws-field__error" role="alert">
              {createError instanceof ApiError ? describeError(createError) : "The account could not be added."}
            </p>
          ) : null}
        </form>

        {error ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>Accounts could not be loaded.</h2>
            <p>{describeError(error)}</p>
          </div>
        ) : null}

        {users === null && !error ? (
          <div className="ws-docs__table" aria-busy="true">
            <p className="ws-visually-hidden" role="status" aria-live="polite">
              Loading accounts…
            </p>
            {[0, 1, 2].map((row) => (
              <div key={row} className="ws-docs__skel" aria-hidden="true">
                <span className="ws-skel ws-skel--line" style={{ width: "35%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "20%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "25%" }} />
              </div>
            ))}
          </div>
        ) : null}

        {users !== null && users.length > 0 ? (
          <div className="ws-docs__table">
            <table>
              <thead>
                <tr>
                  <th scope="col">Account</th>
                  <th scope="col">Status</th>
                  <th scope="col">Roles</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <UserRow
                    key={user.id}
                    user={user}
                    roles={roles}
                    canGrant={canGrant}
                    onChanged={replaceUser}
                  />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {!canGrant ? (
          <p className="ws-pane__note">
            Granting roles needs role administration, which this account does not include.
          </p>
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

function UserRow({
  user,
  roles,
  canGrant,
  onChanged,
}: {
  user: User;
  roles: Role[] | null;
  canGrant: boolean;
  onChanged: (user: User) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [rowError, setRowError] = useState<unknown>(null);
  const [grantCode, setGrantCode] = useState("");

  async function act(operation: () => Promise<User>) {
    setBusy(true);
    setRowError(null);
    try {
      onChanged(await operation());
    } catch (cause) {
      // SEC-05's last-authority refusal (and every S-8/S-9 result) lands here,
      // worded by the server — beside the row that caused it.
      setRowError(cause);
    } finally {
      setBusy(false);
    }
  }

  const active = user.status === "ACTIVE";
  const grantable = (roles ?? []).filter((role) => !user.roles.includes(role.code));

  return (
    <tr data-user-email={user.email}>
      <td>
        <div>{user.email}</div>
        <div className="ws-pane__note">{user.name}</div>
        {rowError ? (
          <p className="ws-field__error" role="alert">
            {describeError(rowError)}
          </p>
        ) : null}
      </td>
      <td>
        <span className={`ws-chip${active ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}>{user.status}</span>{" "}
        <button
          type="button"
          className="ws-escalate__link"
          disabled={busy}
          onClick={() => void act(() => api.updateUser(user.id, { status: active ? "DISABLED" : "ACTIVE" }))}
        >
          {active ? "Disable" : "Restore"}
        </button>
      </td>
      <td>
        {user.roles.length === 0 ? <span className="ws-pane__note">no roles — cannot act yet</span> : null}
        {user.roles.map((code) => (
          <span key={code} className="ws-rolechip">
            <span className="ws-chip">{code}</span>
            <button
              type="button"
              className="ws-rolechip__revoke"
              aria-label={`Revoke ${code} from ${user.email}`}
              disabled={busy}
              onClick={() => void act(() => api.revokeRole(user.id, code))}
            >
              ×
            </button>
          </span>
        ))}
        {canGrant && grantable.length > 0 ? (
          <span className="ws-grant">
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
              {grantable.map((role) => (
                <option key={role.code} value={role.code}>
                  {role.name} ({role.code})
                </option>
              ))}
            </select>
            <button
              type="button"
              className="ws-btn"
              disabled={busy || !grantCode}
              onClick={() =>
                void act(async () => {
                  const next = await api.grantRole(user.id, grantCode);
                  setGrantCode("");
                  return next;
                })
              }
            >
              Grant
            </button>
          </span>
        ) : null}
      </td>
    </tr>
  );
}
