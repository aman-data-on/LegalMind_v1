"use client";

/**
 * Administration → Users. The roster, and the one place accounts are created.
 *
 * Three server rules this screen surfaces rather than re-implements:
 *
 *   47.1.3   an account exists only because an administrator made it; roles are
 *            assigned deliberately and never inferred from a login
 *   SEC-05   disabling or de-granting the last ACTIVE holder of an authority is
 *            refused server-side — the refusal renders beside the control
 *   S-8/S-9  who may administer whom, and who may grant what, are server checks;
 *            a 403 here is a result, not a pre-check (43.23)
 *
 * Every filter and the sort go to the server and apply to the WHOLE roster. The
 * previous version kept a "Sort by" control whose value was never sent — it
 * looked like a capability and was not one — and filtering a page client-side
 * would have the same shape of bug: a colleague on page 2 invisible to a filter
 * that claims to search everyone.
 *
 * A record id never appears in a path segment (AB-11 r2), so the detail panel is
 * `?user=<id>` on this screen rather than a dynamic route.
 */

import { Suspense, useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";

import { useSearchParams } from "next/navigation";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Department, Pagination, Role, User } from "@/lib/types";

import {
  ASSIGNABLE_TIERS,
  AccountStatus,
  AdminNav,
  TIER_ORDER,
  dateOnly,
  dateTime,
} from "@/components/admin/AdminShell";
import { UserDetail } from "@/components/admin/UserDetail";

const PAGE_SIZE = 25;

const SORTS = [
  { value: "name_asc", label: "Name (A–Z)" },
  { value: "name_desc", label: "Name (Z–A)" },
  { value: "email_asc", label: "Email (A–Z)" },
  { value: "created_desc", label: "Newest first" },
  { value: "created_asc", label: "Oldest first" },
  { value: "last_login_desc", label: "Recently signed in" },
] as const;

function UsersScreen() {
  const { can } = useSession();
  /*
   * Selection is React state, and the URL is read ONCE to open it.
   *
   * Both ways of writing it back were tried and both are wrong here.
   * `router.replace` on a query change is a soft navigation: it re-renders the
   * route, remounts this client component and sends `users` back to `null`, so
   * opening a row wiped the table it came from and refetched the page.
   * `history.replaceState` is no escape either — Next patches it and re-syncs
   * the router, which resets the state in the same gesture that set it.
   *
   * So an incoming `?user=<id>` link still opens that account (AB-11 r2 — a
   * record id never appears in a path segment), and clicking a row afterwards
   * simply does not rewrite the address bar. That costs a shareable link for a
   * panel nobody links to, and buys a table that does not reload under the
   * pointer.
   */
  const [selectedId, setSelectedId] = useState<string | null>(
    useSearchParams().get("user"));

  const [users, setUsers] = useState<User[] | null>(null);
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [departments, setDepartments] = useState<Department[] | null>(null);
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);

  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [sort, setSort] = useState<string>("name_asc");

  const [createOpen, setCreateOpen] = useState(false);
  const canGrant = can(P.ROLE_MANAGE);
  const canManageUsers = can(P.USER_MANAGE);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.users({
        page,
        page_size: PAGE_SIZE,
        sort,
        ...(statusFilter && { status: statusFilter }),
        ...(search && { search }),
        ...(roleFilter && { role: roleFilter }),
        ...(departmentFilter === "__none__"
          ? { unassigned: "true" }
          : departmentFilter && { department_id: departmentFilter }),
      });
      setUsers(result.items);
      setPagination(result.pagination);
    } catch (cause) {
      setError(cause);
    }
  }, [page, sort, statusFilter, search, roleFilter, departmentFilter]);

  useEffect(() => { void load(); }, [load]);

  // Reference data, loaded once: the department list feeds two filters and the
  // create form; the role list names the chips. `GET /roles` needs
  // `role.manage`, so an account holding only `user.manage` sees codes and a
  // note instead of a grant control — the server would refuse the grant anyway.
  useEffect(() => {
    api.departments({ page_size: 100 }).then((r) => setDepartments(r.items)).catch(() => {});
    if (canGrant) {
      api.roles({ page_size: 100 }).then((r) => setRoles(r.items)).catch(() => {});
    }
  }, [canGrant]);

  // Reset to page 1 whenever the question changes — landing on page 3 of a
  // filter you just applied shows an empty table.
  useEffect(() => { setPage(1); }, [search, statusFilter, roleFilter, departmentFilter, sort]);

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  if (!canManageUsers) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include user administration.</p>
      </div>
    );
  }

  const selected = users?.find((u) => u.id === selectedId) ?? null;
  const replaceUser = (next: User) =>
    setUsers((current) => current?.map((u) => (u.id === next.id ? next : u)) ?? null);
  const select = (id: string | null) => setSelectedId(id);
  const pageCount = pagination
    ? Math.max(1, Math.ceil(pagination.total / pagination.page_size)) : 1;
  const filtered = Boolean(search || statusFilter || roleFilter || departmentFilter);
  const roleName = (code: string) => roles?.find((r) => r.code === code)?.name ?? code;

  return (
    <div className="ws-admin">
      <header className="ws-admin__head">
        <div>
          <h1>Administration</h1>
          <p className="ws-pane__note">
            Accounts, access and departments. Contract content is never administered here.
          </p>
        </div>
        <button
          type="button"
          className="ws-btn ws-btn--primary ws-btn--icon"
          aria-expanded={createOpen}
          onClick={() => setCreateOpen((open) => !open)}
        >
          <Plus size={16} />
          Add account
        </button>
      </header>

      <AdminNav />

      {createOpen ? (
        <CreateAccount
          departments={departments}
          roles={roles}
          onCreated={async (created) => {
            setCreateOpen(false);
            await load();
            select(created.id);
          }}
          onCancel={() => setCreateOpen(false)}
        />
      ) : null}

      <div className="ws-filter-bar">
        {/* The filter controls and the create form both talk about a role and a
            department. Two controls with the same accessible name on one screen
            is a real defect, not just an ambiguous selector: a screen reader
            announces "Role, combo box" twice and neither one says which. The
            visible text stays short and is a substring of the accessible name,
            so WCAG 2.5.3 is satisfied rather than traded away. */}
        <label className="ws-field">
          <span className="ws-field__label">Search</span>
          <input
            type="search"
            aria-label="Search accounts"
            placeholder="Name or email"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Role</span>
          <select aria-label="Filter by role" value={roleFilter}
                  onChange={(event) => setRoleFilter(event.target.value)}>
            <option value="">All roles</option>
            {(roles ?? [])
              .filter((role) => ASSIGNABLE_TIERS.includes(role.tier))
              .map((role) => (
                <option key={role.code} value={role.code}>{role.name}</option>
              ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Department</span>
          <select
            aria-label="Filter by department"
            value={departmentFilter}
            onChange={(event) => setDepartmentFilter(event.target.value)}
          >
            <option value="">All departments</option>
            {(departments ?? []).map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
            <option value="__none__">No department</option>
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Status</span>
          <select aria-label="Filter by status" value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="SUSPENDED">Suspended</option>
            <option value="DISABLED">Disabled</option>
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Sort by</span>
          <select aria-label="Sort accounts by" value={sort}
                  onChange={(event) => setSort(event.target.value)}>
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>

      <div className="ws-admin__body">
        <div className="ws-admin__main">
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
              {[0, 1, 2, 3].map((row) => (
                <div key={row} className="ws-docs__skel" aria-hidden="true">
                  <span className="ws-skel ws-skel--line" style={{ width: "26%" }} />
                  <span className="ws-skel ws-skel--line" style={{ width: "18%" }} />
                  <span className="ws-skel ws-skel--line" style={{ width: "14%" }} />
                </div>
              ))}
            </div>
          ) : null}

          {users !== null && users.length === 0 && !error ? (
            <div className="ws-state">
              <h2>{filtered ? "No accounts match." : "No accounts yet."}</h2>
              <p>
                {filtered
                  ? "Try a broader filter — search matches name and email."
                  : "Add the first account to get started. A new account holds no roles until you grant one."}
              </p>
            </div>
          ) : null}

          {users !== null && users.length > 0 ? (
            <div className="ws-docs__table">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Email</th>
                    <th scope="col">Role</th>
                    <th scope="col">Department</th>
                    <th scope="col">Status</th>
                    <th scope="col">Last sign-in</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr
                      key={user.id}
                      data-user-email={user.email}
                      className={user.id === selectedId ? "ws-tr--selected" : undefined}
                    >
                      <td>
                        <button
                          type="button"
                          className="ws-link ws-admin__name"
                          onClick={() => select(user.id === selectedId ? null : user.id)}
                        >
                          {user.name}
                        </button>
                      </td>
                      <td className="ws-mono">{user.email}</td>
                      <td>
                        {user.roles.length === 0 ? (
                          <span className="ws-pane__note">no roles</span>
                        ) : (
                          user.roles.map((code) => (
                            <span key={code} className="ws-chip" title={code}>
                              {roleName(code)}
                            </span>
                          ))
                        )}
                      </td>
                      <td>{user.department?.name ?? <span className="ws-pane__note">—</span>}</td>
                      <td><AccountStatus status={user.status} /></td>
                      <td className="ws-mono">
                        {user.last_login_at ? dateTime(user.last_login_at) : "Never"}
                      </td>
                      <td className="ws-mono">{dateOnly(user.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {pagination && pagination.total > pagination.page_size ? (
            <nav className="ws-pager" aria-label="Pagination">
              <button
                type="button"
                className="ws-btn"
                disabled={pagination.page <= 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span className="ws-mono">
                Page {pagination.page} of {pageCount} · {pagination.total} accounts
              </span>
              <button
                type="button"
                className="ws-btn"
                disabled={pagination.page >= pageCount}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </nav>
          ) : null}
        </div>

        {selected ? (
          <UserDetail
            key={selected.id}
            user={selected}
            roles={roles}
            departments={departments}
            canGrant={canGrant}
            onChanged={replaceUser}
            onClose={() => select(null)}
          />
        ) : null}
      </div>
    </div>
  );
}

/**
 * Create an account — and, optionally, place and empower it in the same act.
 *
 * The three-step version (create, then place, then grant) left the account in a
 * state nobody chose for as long as it took to finish. The server does all
 * three in one transaction and still runs S-8 on the role, so a refusal leaves
 * no account behind.
 */
function CreateAccount({
  departments, roles, onCreated, onCancel,
}: {
  departments: Department[] | null;
  roles: Role[] | null;
  onCreated: (user: User) => Promise<void>;
  onCancel: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [departmentId, setDepartmentId] = useState("");
  const [roleCode, setRoleCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const assignable = (roles ?? [])
    .filter((role) => ASSIGNABLE_TIERS.includes(role.tier))
    .sort((a, b) => TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier)
      || a.name.localeCompare(b.name));

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await api.createUser(email.trim(), name.trim(), {
        ...(departmentId && { department_id: departmentId }),
        ...(roleCode && { role_code: roleCode }),
      });
      await onCreated(created);
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="ws-intake" onSubmit={submit} aria-labelledby="ws-admin-create">
      <h2 id="ws-admin-create" className="ws-intake__title">Add an account</h2>
      <div className="ws-intake__fields">
        <label className="ws-field">
          <span className="ws-field__label">
            Full name <span className="ws-field__req">(required)</span>
          </span>
          <input required value={name} disabled={busy}
                 onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">
            Work email <span className="ws-field__req">(required)</span>
          </span>
          <input type="email" required value={email} disabled={busy}
                 onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Department</span>
          <select aria-label="Department for the new account" value={departmentId}
                  disabled={busy}
                  onChange={(event) => setDepartmentId(event.target.value)}>
            <option value="">No department</option>
            {(departments ?? []).map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Role</span>
          <select aria-label="Role for the new account" value={roleCode} disabled={busy}
                  onChange={(event) => setRoleCode(event.target.value)}>
            <option value="">No role yet</option>
            {assignable.map((role) => (
              <option key={role.code} value={role.code}>{role.name}</option>
            ))}
          </select>
        </label>
      </div>
      <p className="ws-field__help">
        Credentials are provisioned outside this screen: the account can sign in once an
        identity is linked to it. Leaving the role empty is fine — the account simply cannot
        act until you grant one.
      </p>
      {error ? (
        <p className="ws-field__error" role="alert">{describeError(error)}</p>
      ) : null}
      <div className="ws-detail__acts">
        <button type="button" className="ws-btn" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="submit" className="ws-btn ws-btn--primary"
                disabled={busy || !email.trim() || !name.trim()}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </div>
    </form>
  );
}

export default function AdminUsersPage() {
  return (
    <Suspense fallback={<div className="ws-state" aria-busy="true" />}>
      <UsersScreen />
    </Suspense>
  );
}
