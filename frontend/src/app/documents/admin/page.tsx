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
import { Plus, ChevronLeft, ChevronRight, Power, Trash2, Key } from "lucide-react";

import Link from "next/link";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Pagination, Role, User } from "@/lib/types";

const PAGE_SIZE = 25;
type Tab = "users" | "roles";
type SortBy = "email" | "created_at";
type StatusFilter = "all" | "ACTIVE" | "SUSPENDED" | "DISABLED";

export default function AdminPage() {
  const { can } = useSession();
  const [tab, setTab] = useState<Tab>("users");
  const [users, setUsers] = useState<User[] | null>(null);
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortBy, setSortBy] = useState<SortBy>("created_at");
  const canGrant = can(P.ROLE_MANAGE);
  const canManageUsers = can(P.USER_MANAGE);

  const load = useCallback(async () => {
    setError(null);
    try {
      if (tab === "users") {
        const result = await api.users({
          page,
          page_size: PAGE_SIZE,
          ...(statusFilter !== "all" && { status: statusFilter }),
          ...(search && { search }),
        });
        setUsers(result.items);
        setPagination(result.pagination);
      }
      if (canGrant && (tab === "roles" || tab === "users")) {
        // Five canonical roles; one page is the whole vocabulary.
        setRoles((await api.roles({ page_size: 100 })).items);
      }
    } catch (cause) {
      setError(cause);
    }
  }, [page, canGrant, tab, statusFilter, search]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, search]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!canManageUsers) {
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

  const replaceRole = (next: Role) =>
    setRoles((current) => current?.map((r) => (r.id === next.id ? next : r)) ?? null);

  return (
    <>
      <div className="ws-context">
        <h1>Admin</h1>
        <div className="ws-context__meta">
          {tab === "users" && pagination ? (
            <span className="ws-mono">{pagination.total} account{pagination.total === 1 ? "" : "s"}</span>
          ) : null}
          {can(P.AUDIT_VIEW) ? <Link href="/documents/admin/audit">Audit trail</Link> : null}
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="ws-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "users"}
          className={`ws-tab ${tab === "users" ? "ws-tab--active" : ""}`}
          onClick={() => setTab("users")}
        >
          Users
        </button>
        {canGrant ? (
          <button
            role="tab"
            aria-selected={tab === "roles"}
            className={`ws-tab ${tab === "roles" ? "ws-tab--active" : ""}`}
            onClick={() => setTab("roles")}
          >
            Roles
          </button>
        ) : null}
      </div>

      <div className="ws-docs">
        {/* USERS TAB */}
        {tab === "users" ? (
          <>
            {/* Create User Form */}
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
                  <input
                    required
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    disabled={creating}
                  />
                  <span className="ws-field__help">
                    A new account holds no roles — authority is a separate, deliberate grant. Credentials are provisioned
                    outside this screen.
                  </span>
                </label>
                <button
                  type="submit"
                  className="ws-btn ws-btn--primary ws-btn--icon"
                  disabled={creating || !email.trim() || !name.trim()}
                >
                  <Plus size={18} />
                  {creating ? "Adding…" : "Add account"}
                </button>
              </div>
              {createError ? (
                <p className="ws-field__error" role="alert">
                  {createError instanceof ApiError ? describeError(createError) : "The account could not be added."}
                </p>
              ) : null}
            </form>

            {/* Search & Filter */}
            <div className="ws-filter-bar">
              <label className="ws-field">
                <span className="ws-field__label">Search</span>
                <input
                  type="text"
                  placeholder="Email or name"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </label>
              <label className="ws-field">
                <span className="ws-field__label">Status</span>
                <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
                  <option value="all">All statuses</option>
                  <option value="ACTIVE">Active</option>
                  <option value="SUSPENDED">Suspended</option>
                  <option value="DISABLED">Disabled</option>
                </select>
              </label>
              <label className="ws-field">
                <span className="ws-field__label">Sort by</span>
                <select value={sortBy} onChange={(event) => setSortBy(event.target.value as SortBy)}>
                  <option value="created_at">Newest first</option>
                  <option value="email">Email (A–Z)</option>
                </select>
              </label>
            </div>

            {/* Error State */}
            {error ? (
              <div className="ws-state ws-state--error" role="alert">
                <h2>Accounts could not be loaded.</h2>
                <p>{describeError(error)}</p>
              </div>
            ) : null}

            {/* Loading State */}
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

            {/* Users Table */}
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

            {/* Empty State */}
            {users !== null && users.length === 0 && !error ? (
              <div className="ws-state">
                <h2>No accounts found</h2>
                <p>Try adjusting your search or filters.</p>
              </div>
            ) : null}

            {!canGrant ? (
              <p className="ws-pane__note">Granting roles needs role administration, which this account does not include.</p>
            ) : null}

            {/* Pagination */}
            {pagination && pagination.total > pagination.page_size ? (
              <nav className="ws-pager" aria-label="Pagination">
                <button
                  type="button"
                  className="ws-btn ws-btn--icon"
                  disabled={pagination.page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  title="Previous page"
                >
                  <ChevronLeft size={18} />
                  Previous
                </button>
                <span className="ws-mono">
                  Page {pagination.page} of {Math.ceil(pagination.total / pagination.page_size)}
                </span>
                <button
                  type="button"
                  className="ws-btn ws-btn--icon"
                  disabled={pagination.page * pagination.page_size >= pagination.total}
                  onClick={() => setPage((p) => p + 1)}
                  title="Next page"
                >
                  Next
                  <ChevronRight size={18} />
                </button>
              </nav>
            ) : null}
          </>
        ) : null}

        {/* ROLES TAB */}
        {tab === "roles" && canGrant ? (
          <>
            <div className="ws-state">
              <h2>Role Management</h2>
              <p>Manage roles and their permissions. Five canonical roles cannot be deleted (User, Legal Reviewer, Legal Admin, Super Admin, Legal Decision Authority).</p>
            </div>

            {roles !== null && roles.length > 0 ? (
              <div className="ws-docs__table">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Role</th>
                      <th scope="col">Code</th>
                      <th scope="col">Permissions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {roles.map((role) => (
                      <RoleRow key={role.id} role={role} onChanged={replaceRole} />
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {roles === null ? (
              <div className="ws-state" aria-busy="true">
                <p className="ws-visually-hidden" role="status" aria-live="polite">
                  Loading roles…
                </p>
              </div>
            ) : null}

            {/* `{id}` is literal text here, not a JSX expression — braces in prose
                have to be escaped or React reads them as a reference. */}
            <p className="ws-pane__note">
              Role creation and permission management is available via the API. Use{" "}
              <code>POST /api/v1/roles</code> and{" "}
              <code>PATCH /api/v1/roles/{"{id}"}</code>.
            </p>
          </>
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
  const [deleting, setDeleting] = useState(false);

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

  async function deleteUser() {
    if (!window.confirm(`Are you sure you want to delete ${user.email}? This cannot be undone.`)) {
      return;
    }
    setDeleting(true);
    setRowError(null);
    try {
      await api.deleteUser(user.id);
      // Note: in a real implementation, the parent would remove this row.
      // For now, the error will show if the delete fails.
    } catch (cause) {
      setRowError(cause);
    } finally {
      setDeleting(false);
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
          className="ws-escalate__link ws-escalate__link--icon"
          disabled={busy}
          onClick={() => void act(() => api.updateUser(user.id, { status: active ? "DISABLED" : "ACTIVE" }))}
          title={active ? "Disable account" : "Re-enable account"}
        >
          <Power size={16} />
          {active ? "Disable" : "Restore"}
        </button>
        {user.status === "DISABLED" ? (
          <>
            {" "}
            <button type="button" className="ws-escalate__link ws-escalate__link--danger ws-escalate__link--icon" disabled={deleting} onClick={deleteUser} title="Delete account">
              <Trash2 size={16} />
              {deleting ? "Deleting…" : "Delete"}
            </button>
          </>
        ) : null}
      </td>
      <td>
        {user.roles.length === 0 ? <span className="ws-pane__note">no roles — cannot act yet</span> : null}
        {user.roles.map((code) => (
          <span key={code} className="ws-rolechip">
            <span className="ws-chip">{code}</span>
            <button
              type="button"
              className="ws-rolechip__revoke ws-rolechip__revoke--icon"
              aria-label={`Revoke ${code} from ${user.email}`}
              disabled={busy}
              onClick={() => void act(() => api.revokeRole(user.id, code))}
              title={`Revoke ${code}`}
            >
              <span className="ws-visually-hidden">Revoke</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
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
              className="ws-btn ws-btn--icon"
              disabled={busy || !grantCode}
              onClick={() =>
                void act(async () => {
                  const next = await api.grantRole(user.id, grantCode);
                  setGrantCode("");
                  return next;
                })
              }
              title="Grant role"
            >
              <Key size={16} />
              Grant
            </button>
          </span>
        ) : null}
      </td>
    </tr>
  );
}

function RoleRow({ role, onChanged }: { role: Role; onChanged: (role: Role) => void }) {
  const [expanding, setExpanding] = useState(false);

  return (
    <tr data-role-code={role.code}>
      <td>
        <div className="ws-role-name">{role.name}</div>
      </td>
      <td>
        <code>{role.code}</code>
      </td>
      <td>
        <button
          type="button"
          className="ws-link"
          onClick={() => setExpanding(!expanding)}
          aria-expanded={expanding}
        >
          {role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}
        </button>
        {expanding ? (
          <div className="ws-role-perms">
            {role.permissions.length === 0 ? (
              <p className="ws-pane__note">No permissions assigned</p>
            ) : (
              <ul>
                {role.permissions.map((perm) => (
                  <li key={perm}>
                    <code>{perm}</code>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </td>
    </tr>
  );
}
