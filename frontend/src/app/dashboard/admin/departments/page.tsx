"use client";

/**
 * Administration → Departments.
 *
 * A department is the boundary a Department Lead's oversight is scoped to
 * (AB-12 r3), so this screen answers two questions and refuses a third:
 *
 *   who is in it        member and active-member counts, and the accounts
 *   who oversees it     the leads, DERIVED from who holds DEPARTMENT_LEAD —
 *                       there is no `lead_id` column, because the role
 *                       assignment is what grants the scope, and a second
 *                       place to record it would eventually disagree
 *   what are they working on        ← not here, and not anywhere for this role
 *
 * Membership is not edited here. It is a property of each account and changes
 * one audited act at a time from that account's own row (Users → the account →
 * Department), so every placement has an actor and a reason to look at.
 */

import { Suspense, useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";

import { useSearchParams } from "next/navigation";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Department } from "@/lib/types";

import { AccountStatus, AdminNav, dateOnly } from "@/components/admin/AdminShell";

function DepartmentsScreen() {
  const { can } = useSession();
  // State only; the URL is read once to open a department. See the note on the
  // Users screen for why writing it back remounts and refetches the list.
  const [selectedId, setSelectedId] = useState<string | null>(
    useSearchParams().get("department"));

  const [departments, setDepartments] = useState<Department[] | null>(null);
  const [detail, setDetail] = useState<Department | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setDepartments((await api.departments({ page_size: 100 })).items);
    } catch (cause) {
      setError(cause);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    let cancelled = false;
    api.department(selectedId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch(() => { if (!cancelled) setDetail(null); });
    return () => { cancelled = true; };
  }, [selectedId]);

  if (!can(P.USER_MANAGE)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include user administration.</p>
      </div>
    );
  }

  const select = (id: string | null) => setSelectedId(id);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setCreateError(null);
    try {
      await api.createDepartment(code.trim(), name.trim());
      setCode("");
      setName("");
      setCreateOpen(false);
      await load();
    } catch (cause) {
      setCreateError(cause);
    } finally {
      setBusy(false);
    }
  }

  async function rename(department: Department, next: string) {
    await api.renameDepartment(department.id, next);
    await load();
    if (selectedId === department.id) setDetail(await api.department(department.id));
  }

  return (
    <div className="ws-admin">
      <header className="ws-admin__head">
        <div>
          <h1>Administration</h1>
          <p className="ws-pane__note">
            Departments bound what a Department Lead can see. They never grant sight of a deal.
          </p>
        </div>
        <button type="button" className="ws-btn ws-btn--primary ws-btn--icon"
                aria-expanded={createOpen} onClick={() => setCreateOpen((o) => !o)}>
          <Plus size={16} />
          Add department
        </button>
      </header>

      <AdminNav />

      {createOpen ? (
        <form className="ws-intake" onSubmit={create} aria-labelledby="ws-dept-create">
          <h2 id="ws-dept-create" className="ws-intake__title">Add a department</h2>
          <div className="ws-intake__fields">
            <label className="ws-field">
              <span className="ws-field__label">
                Department code <span className="ws-field__req">(required)</span>
              </span>
              <input required value={code} placeholder="SALES" disabled={busy}
                     onChange={(event) => setCode(event.target.value)} />
            </label>
            <label className="ws-field ws-field--type">
              <span className="ws-field__label">
                Department name <span className="ws-field__req">(required)</span>
              </span>
              <input required value={name} placeholder="Sales" disabled={busy}
                     onChange={(event) => setName(event.target.value)} />
            </label>
          </div>
          <p className="ws-field__help">
            The code identifies this department in the audit trail and cannot be changed later.
            The name can.
          </p>
          {createError ? (
            <p className="ws-field__error" role="alert">{describeError(createError)}</p>
          ) : null}
          <div className="ws-detail__acts">
            <button type="button" className="ws-btn" onClick={() => setCreateOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="ws-btn ws-btn--primary"
                    disabled={busy || !code.trim() || !name.trim()}>
              {busy ? "Adding…" : "Add department"}
            </button>
          </div>
        </form>
      ) : null}

      {error ? (
        <div className="ws-state ws-state--error" role="alert">
          <h2>Departments could not be loaded.</h2>
          <p>{describeError(error)}</p>
        </div>
      ) : null}

      <div className="ws-admin__body">
        <div className="ws-admin__main">
          {departments === null && !error ? (
            <div className="ws-docs__table" aria-busy="true">
              <p className="ws-visually-hidden" role="status">Loading departments…</p>
              {[0, 1].map((row) => (
                <div key={row} className="ws-docs__skel" aria-hidden="true">
                  <span className="ws-skel ws-skel--line" style={{ width: "30%" }} />
                  <span className="ws-skel ws-skel--line" style={{ width: "20%" }} />
                </div>
              ))}
            </div>
          ) : null}

          {departments !== null && departments.length === 0 ? (
            <div className="ws-state">
              <h2>No departments yet.</h2>
              <p>
                Until a department exists, every account sees only its own deals — including a
                Department Lead. Add one, then place people in it from their account.
              </p>
            </div>
          ) : null}

          {departments !== null && departments.length > 0 ? (
            <div className="ws-docs__table">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Department</th>
                    <th scope="col">Code</th>
                    <th scope="col">Lead</th>
                    <th scope="col">Members</th>
                    <th scope="col">Active</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {departments.map((department) => (
                    <tr key={department.id} data-department-code={department.code}
                        className={department.id === selectedId ? "ws-tr--selected" : undefined}>
                      <td>
                        <button type="button" className="ws-link ws-admin__name"
                                onClick={() => select(department.id === selectedId
                                  ? null : department.id)}>
                          {department.name}
                        </button>
                      </td>
                      <td className="ws-mono">{department.code}</td>
                      <td>
                        {department.leads && department.leads.length > 0
                          ? department.leads.map((lead) => lead.name).join(", ")
                          : <span className="ws-pane__note">No lead appointed</span>}
                      </td>
                      <td className="ws-mono">{department.members ?? 0}</td>
                      <td className="ws-mono">{department.active_members ?? 0}</td>
                      <td className="ws-mono">{dateOnly(department.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>

        {detail ? (
          <DepartmentDetail department={detail} onClose={() => select(null)}
                            onRename={rename} />
        ) : null}
      </div>
    </div>
  );
}

function DepartmentDetail({
  department, onClose, onRename,
}: {
  department: Department;
  onClose: () => void;
  onRename: (department: Department, name: string) => Promise<void>;
}) {
  const [name, setName] = useState(department.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => { setName(department.name); }, [department.id, department.name]);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onRename(department, name.trim());
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="ws-detail" aria-label={`Department ${department.name}`}>
      <header className="ws-detail__head">
        <div>
          <h2 className="ws-detail__title">{department.name}</h2>
          <p className="ws-detail__sub ws-mono">{department.code}</p>
        </div>
        <button type="button" className="ws-btn ws-btn--sm" onClick={onClose}>Close</button>
      </header>

      <form className="ws-detail__section" onSubmit={save}>
        <h3>Name</h3>
        <label className="ws-field">
          <span className="ws-visually-hidden">Department name</span>
          <input value={name} disabled={busy}
                 onChange={(event) => setName(event.target.value)} />
        </label>
        {error ? (
          <p className="ws-field__error" role="alert">{describeError(error)}</p>
        ) : null}
        <div className="ws-detail__acts">
          <button type="submit" className="ws-btn"
                  disabled={busy || !name.trim() || name.trim() === department.name}>
            {busy ? "Saving…" : "Save name"}
          </button>
        </div>
        <p className="ws-pane__note">
          The code stays <span className="ws-mono">{department.code}</span> — it identifies this
          department in an append-only audit trail.
        </p>
      </form>

      <section className="ws-detail__section">
        <h3>Members ({department.members ?? 0})</h3>
        {(department.member_accounts ?? []).length === 0 ? (
          <p className="ws-pane__note">
            Nobody is in this department yet. Place people from their own account under Users.
          </p>
        ) : (
          <ul className="ws-memberlist">
            {(department.member_accounts ?? []).map((member) => (
              <li key={member.id}>
                <span>{member.name}</span>
                <span className="ws-mono ws-pane__note">{member.email}</span>
                <AccountStatus status={member.status} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </aside>
  );
}

export default function AdminDepartmentsPage() {
  return (
    <Suspense fallback={<div className="ws-state" aria-busy="true" />}>
      <DepartmentsScreen />
    </Suspense>
  );
}
