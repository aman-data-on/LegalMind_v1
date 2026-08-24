"use client";

/**
 * Users and roles — locked 52.6 (Step 23, Step 47), 49.3, S-8, S-9, SEC-05.
 *
 * The screen where authority is granted, so it says out loud what locked Step 23
 * establishes: **legal authority is a separate, explicit grant.** Granting
 * `SUPER_ADMIN` confers no `legal.*` permission, and a role that does carry legal
 * authority is labelled, so an administrator does not have to know which permission
 * names are special.
 *
 * The escalation guards (S-8: you may not grant an authority you do not hold; S-9:
 * the same applies to editing a more-privileged account) and SEC-05 (never zero
 * legal authorities) are enforced **server-side**. This screen surfaces their
 * refusals verbatim rather than pre-empting them — a client-side prediction of an
 * authority rule would be a second, drift-prone copy of it.
 */

import { useCallback, useEffect, useState } from "react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading } from "@/components/Feedback";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Role, User } from "@/lib/types";

export default function AdminPage() {
  const { can } = useSession();
  const [users, setUsers] = useState<User[] | null>(null);
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      if (can(P.USER_MANAGE)) setUsers((await api.users({ page_size: 100 })).items);
      if (can(P.ROLE_MANAGE)) setRoles((await api.roles({ page_size: 100 })).items);
    } catch (cause) {
      setError(cause);
    }
  }, [can]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.USER_MANAGE) && !can(P.ROLE_MANAGE)) {
    return <AccessRestricted what="user and role administration" />;
  }

  async function createUser(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.createUser(email, name);
      setEmail("");
      setName("");
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  async function grant(userId: string, roleCode: string) {
    setError(null);
    try {
      await api.grantRole(userId, roleCode);
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  async function revoke(userId: string, roleCode: string) {
    setError(null);
    try {
      await api.revokeRole(userId, roleCode);
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  async function setStatus(userId: string, status: string) {
    setError(null);
    try {
      await api.updateUser(userId, { status });
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  return (
    <>
      <h1>Users &amp; roles</h1>
      <p className="hint">
        Legal Decision authority is a separate, explicit grant. No role confers it
        automatically, including Super Admin.
      </p>
      <ErrorBanner error={error} />

      <PermissionGate granted={can(P.USER_MANAGE)}>
        <form className="card form-row" onSubmit={createUser}>
          <div className="field">
            <label className="field__label" htmlFor="new-user-email">
              Work email
            </label>
            <input
              id="new-user-email"
              type="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <div className="field">
            <label className="field__label" htmlFor="new-user-name">
              Name
            </label>
            <input
              id="new-user-name"
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
          </div>
          <button type="submit" className="btn btn--primary">
            Create user
          </button>
        </form>
        <p className="hint">
          A new account holds no roles. Authority is always a later, deliberate grant.
        </p>

        <h2>Users</h2>
        {users === null ? (
          <Loading what="users" />
        ) : users.length === 0 ? (
          <EmptyState>No users.</EmptyState>
        ) : (
          <div className="table-card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Email</th>
                <th>Name</th>
                <th>Status</th>
                <th>Roles</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.name}</td>
                  <td>
                    <span className={`status status--${user.status.toLowerCase()}`}>
                      {user.status}
                    </span>
                  </td>
                  <td>
                    {user.roles.length === 0 ? (
                      <span className="hint">none</span>
                    ) : (
                      user.roles.map((code) => (
                        <span key={code}>
                          {code}{" "}
                          <button
                            type="button"
                            className="link"
                            onClick={() => void revoke(user.id, code)}
                          >
                            revoke
                          </button>{" "}
                        </span>
                      ))
                    )}
                  </td>
                  <td>
                    <form
                      className="inline"
                      onSubmit={(event) => {
                        event.preventDefault();
                        const code = new FormData(event.currentTarget).get("role");
                        if (typeof code === "string" && code) void grant(user.id, code);
                      }}
                    >
                      <label>
                        <select name="role" defaultValue="">
                          <option value="" disabled>
                            Grant role…
                          </option>
                          {(roles ?? []).map((role) => (
                            <option key={role.id} value={role.code}>
                              {role.code}
                              {role.confers_legal_authority.length > 0
                                ? " (legal authority)"
                                : ""}
                            </option>
                          ))}
                        </select>
                      </label>
                      <button type="submit" className="btn btn--secondary btn--sm">
                        Grant
                      </button>
                    </form>
                    {/* Disabling access is the destructive direction (DD-5 button tiers). */}
                    <button
                      type="button"
                      className={
                        user.status === "ACTIVE"
                          ? "btn btn--danger btn--sm"
                          : "btn btn--secondary btn--sm"
                      }
                      onClick={() =>
                        void setStatus(
                          user.id,
                          user.status === "ACTIVE" ? "DISABLED" : "ACTIVE",
                        )
                      }
                    >
                      {user.status === "ACTIVE" ? "Disable" : "Re-enable"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </PermissionGate>

      <PermissionGate granted={can(P.ROLE_MANAGE)}>
        <h2>Roles</h2>
        {roles === null ? (
          <Loading what="roles" />
        ) : (
          <div className="table-card table-wrap">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Permissions</th>
                <th>Legal authority</th>
              </tr>
            </thead>
            <tbody>
              {roles.map((role) => (
                <tr key={role.id}>
                  <td>{role.code}</td>
                  <td>{role.name}</td>
                  <td className="hint">{role.permissions.join(", ") || "none"}</td>
                  <td>
                    {role.confers_legal_authority.length > 0 ? (
                      <span className="status status--escalated">
                        {role.confers_legal_authority.join(", ")}
                      </span>
                    ) : (
                      <span className="hint">none</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </PermissionGate>
    </>
  );
}
