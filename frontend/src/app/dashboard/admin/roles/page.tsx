"use client";

/**
 * Administration → Roles & permissions. A catalogue, deliberately not a control.
 *
 * The screen answers "what does this role let someone do?" in the words of the
 * permission catalogue (SEC-04's groups), so an administrator granting a role
 * elsewhere knows what they are granting. Two things it makes visible that a
 * list of dotted strings cannot:
 *
 *   dangerous permissions   `legal.decision` and `legal.approve_customization`
 *                           are the two no bypass may ever reach (SEC-02,
 *                           ROLE-05). They are marked, and the marking comes
 *                           from the server rather than a hardcoded list here.
 *   roles nobody holds      `LEGAL_REVIEWER` and `LEGAL_DECISION_AUTHORITY` are
 *                           retained for a workflow that does not exist yet
 *                           (AB-12 r10). They are shown, labelled "Not in use
 *                           yet", and are absent from every assignment picker.
 *
 * Editing a role's permission set stays on `PATCH /roles/{id}` (S-10,
 * transactional) and is not exposed here: it is a rare, high-consequence act,
 * and putting a checkbox grid in front of it would invite the routine use it
 * should never have. The screen says so plainly rather than pretending the
 * capability is absent.
 */

import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { PermissionCatalogue, Role } from "@/lib/types";

import { AdminNav, TIER_LABEL, TIER_ORDER } from "@/components/admin/AdminShell";

export default function AdminRolesPage() {
  const { can } = useSession();
  const [roles, setRoles] = useState<Role[] | null>(null);
  const [catalogue, setCatalogue] = useState<PermissionCatalogue | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (!can(P.ROLE_MANAGE)) return;
    Promise.all([api.roles({ page_size: 100 }), api.permissionCatalogue()])
      .then(([rolePage, cat]) => { setRoles(rolePage.items); setCatalogue(cat); })
      .catch(setError);
  }, [can]);

  if (!can(P.ROLE_MANAGE)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include role administration.</p>
      </div>
    );
  }

  // Group name for each permission, so a role's grants can be shown the way the
  // catalogue organises them rather than as one flat list.
  const groupOf = new Map<string, string>();
  const describe = new Map<string, string | null>();
  const dangerous = new Set<string>();
  for (const group of catalogue?.groups ?? []) {
    for (const permission of group.permissions) {
      groupOf.set(permission.name, group.group);
      describe.set(permission.name, permission.description);
      if (permission.confers_legal_authority) dangerous.add(permission.name);
    }
  }

  const ordered = (roles ?? []).slice().sort(
    (a, b) => TIER_ORDER.indexOf(a.tier) - TIER_ORDER.indexOf(b.tier)
      || a.name.localeCompare(b.name));

  return (
    <div className="ws-admin">
      <header className="ws-admin__head">
        <div>
          <h1>Administration</h1>
          <p className="ws-pane__note">
            What each role lets someone do. Roles are granted from an account, under Users.
          </p>
        </div>
      </header>

      <AdminNav />

      {error ? (
        <div className="ws-state ws-state--error" role="alert">
          <h2>Roles could not be loaded.</h2>
          <p>{describeError(error)}</p>
        </div>
      ) : null}

      {roles === null && !error ? (
        <div className="ws-docs__table" aria-busy="true">
          <p className="ws-visually-hidden" role="status">Loading roles…</p>
          {[0, 1, 2].map((row) => (
            <div key={row} className="ws-docs__skel" aria-hidden="true">
              <span className="ws-skel ws-skel--line" style={{ width: "24%" }} />
              <span className="ws-skel ws-skel--line" style={{ width: "40%" }} />
            </div>
          ))}
        </div>
      ) : null}

      {roles !== null ? (
        <div className="ws-rolecards">
          {ordered.map((role) => {
            const open = expanded === role.code;
            const byGroup = new Map<string, string[]>();
            for (const permission of role.permissions) {
              const group = groupOf.get(permission) ?? "Other";
              byGroup.set(group, [...(byGroup.get(group) ?? []), permission]);
            }
            return (
              <article key={role.id} className="ws-rolecard" data-role-code={role.code}>
                <header className="ws-rolecard__head">
                  <div>
                    <h2 className="ws-rolecard__name">{role.name}</h2>
                    <p className="ws-pane__note ws-mono">{role.code}</p>
                  </div>
                  <div className="ws-rolecard__tags">
                    <span className="ws-chip">{TIER_LABEL[role.tier] ?? role.tier}</span>
                    {role.confers_legal_authority.length > 0 ? (
                      <span className="ws-chip ws-chip--fill ws-chip--outcome-fill">
                        Legal authority
                      </span>
                    ) : null}
                  </div>
                </header>

                {role.tier === "future_legal" ? (
                  <p className="ws-pane__note">
                    Kept for a legal-review workflow that is not in use. It is not offered when
                    granting a role, and nobody holds it.
                  </p>
                ) : null}

                <button
                  type="button"
                  className="ws-link"
                  aria-expanded={open}
                  onClick={() => setExpanded(open ? null : role.code)}
                >
                  {role.permissions.length} permission{role.permissions.length === 1 ? "" : "s"}
                </button>

                {open ? (
                  <div className="ws-rolecard__perms">
                    {role.permissions.length === 0 ? (
                      <p className="ws-pane__note">No permissions assigned.</p>
                    ) : (
                      [...byGroup.entries()].map(([group, permissions]) => (
                        <div key={group}>
                          <h3>{group}</h3>
                          <ul>
                            {permissions.map((permission) => (
                              <li key={permission}>
                                <span className="ws-mono">{permission}</span>
                                {dangerous.has(permission) ? (
                                  <span className="ws-chip ws-chip--fill ws-chip--outcome-fill">
                                    legal authority
                                  </span>
                                ) : null}
                                {describe.get(permission) ? (
                                  <span className="ws-pane__note">
                                    {describe.get(permission)}
                                  </span>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        </div>
                      ))
                    )}
                  </div>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}

      <p className="ws-pane__note ws-admin__footnote">
        A role&rsquo;s permission set is changed through <span className="ws-mono">PATCH /api/v1/roles/&#123;id&#125;</span>,
        which replaces the whole set in one transaction. It is deliberately not a routine screen
        action: an administrator can never construct a role granting an authority they do not
        hold themselves, and the server refuses the attempt.
      </p>
    </div>
  );
}
