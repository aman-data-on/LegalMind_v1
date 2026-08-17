# Step 47 — Security / Authentication / Authorization

**Status: 🔒 LOCKED (2026-08-17).** Lock record in [`all_lock.md`](../../all_lock.md) under "Step 47 — LOCK RECORD". No locked decision amended.

Prepared 2026-08-17. External MoS material used as **reference architecture only**, per its audited classification — adapted, never copied. See [EXTERNAL_REFERENCE_AUDIT.md](../00-project/EXTERNAL_REFERENCE_AUDIT.md).

Related: [AUTHENTICATION.md](AUTHENTICATION.md) · [AUTHORIZATION.md](AUTHORIZATION.md) · [OWNERSHIP.md](OWNERSHIP.md) · [SECURITY_MODEL.md](SECURITY_MODEL.md) · [USER_ROLES.md](../01-product/USER_ROLES.md)

---

# 47.0 What was already locked

Step 47 turned out to be **substantially pre-determined**. The locked corpus answers more than expected:

| Locked | Provides |
|---|---|
| **Step 23** role summary | The four roles, their capability boundaries, three permission names (`legal.review`, `legal.decision`, `legal.approve_customization`), the resource-scope concept, and **"Super Admin — No automatic Legal Decision authority"** |
| **Step 4 / ROLE-05** | Admin is a system role; legal approval authority is **separately assignable**; two Admins may differ |
| **Step 24 / ROLE-07** | Review visibility and ownership |
| **41.24 / 43.23** | Object-level authorization traversal; the IDOR prohibition |
| **38.21 / 38.22** | Server-side security boundary; no direct UI→database access |
| **42.3** | `user_roles` many-to-many — "keeps role assignment flexible" |
| **42.18 / AUD-01** | Append-only audit events, entity-shaped |
| **LEGAL-02** | Internal legal positions are permission-controlled |
| **Step 39** | V1 security checklist: TLS, authentication, server-side RBAC, object-level authorization, encrypted storage, secrets outside source, upload validation, safe parsing, malware scanning, audit trail, rate limiting, session security, backups |

---

# 47.1 · OD-9 — Authentication

## 47.1.1 Resolved by engineering: the identity contract

What the rest of LegalMind depends on is **not** the authentication mechanism — it is the identity contract. That is fully derivable and is specified here:

```text
AUTHENTICATED PRINCIPAL

{
    user_id          UUID     the only identity authorization trusts
    session_id       UUID     server-side session record
    authenticated_at TIMESTAMPTZ
}
```

**Locked-derived rules:**

1. **Only `user_id` is trusted from the session.** Roles, permissions and legal authority are resolved **fresh from the database on every request** — never carried in a token. *(Adapted from external U-1; required by 38.21 and by Step 29's rule that configuration changes take effect without stale caching.)*
2. A revoked or expired session is indistinguishable from being signed out. Never an error that discloses account state.
3. Identical responses for unknown account, wrong credential, and disabled account — no account enumeration. *(External U-5.)*
4. Every authentication outcome emits an audit event (47.9).
5. The session establishes **identity only**. It never carries authority.

This contract holds regardless of which mechanism is chosen, which is why the mechanism does not block the rest of Step 47.

## 47.1.2 Session model — resolved

**Server-side session records, not stateless tokens.**

The external reference uses a stateless JWT and is explicit that "nothing is revoked server-side because nothing is stored server-side." **Rejected for LegalMind.** A system holding confidential legal strategy (LEGAL-02) and bound by append-only auditability (AUD-01) must be able to terminate a session on demand — after a role change, a departure, or a suspected compromise.

```text
sessions
--------
id                UUID PK
user_id           UUID FK → users.id      NOT NULL
created_at        TIMESTAMPTZ             NOT NULL
last_seen_at      TIMESTAMPTZ             NOT NULL
expires_at        TIMESTAMPTZ             NOT NULL
revoked_at        TIMESTAMPTZ             NULL
revoked_reason    VARCHAR                 NULL
INDEX(user_id), INDEX(expires_at)
```

A session is valid when `revoked_at IS NULL AND expires_at > now()`. Logout sets `revoked_at`. Revocation is immediate because authority is resolved per request anyway.

New table; **no locked decision amended.**

## 47.1.3 · OD-9 — Authentication mechanism · **DECIDED 2026-08-17**

**Owner decision:**

```text
Primary authentication      Corporate SSO via OIDC
Fallback authentication     Password-based login, as a controlled fallback
Session model               Server-side sessions (47.1.2)
Session contents            identity (user_id) ONLY
Authority resolution        fresh from the database on every request
Revocation                  immediate, server-side
Rejected                    stateless JWT model
Hard rule                   the authentication mechanism NEVER confers
                            Legal Decision authority
```

Legal authority remains permission/role based and subject to §47.2, §47.4 and §47.5 without exception. **Which mechanism authenticated a user has no bearing whatsoever on what that user may do** — the two concerns meet only at `user_id`.

### Identity linkage — new table, no amendment

Locked `users` (42.2) carries `id`, `email`, `name`, `status` and timestamps — no credential or provider columns. Rather than amend it, identities are held separately, which also lets the primary and fallback mechanisms coexist without nullable-column sprawl:

```text
user_identities
---------------
id                 UUID PK
user_id            UUID FK → users.id        NOT NULL
provider           IDENTITY_PROVIDER         NOT NULL     OIDC | PASSWORD
provider_subject   VARCHAR                   NULL         OIDC `sub`; NULL for PASSWORD
credential_hash    VARCHAR                   NULL         PASSWORD only; NULL for OIDC
created_at         TIMESTAMPTZ               NOT NULL
last_used_at       TIMESTAMPTZ               NULL

UNIQUE(provider, provider_subject)
UNIQUE(user_id, provider)
INDEX(user_id)
```

`credential_hash` is selected by exactly one repository method and is excluded from every other query (S-4). **No locked table is amended.**

### OIDC flow

Authorization-code flow with **PKCE**, `state` and `nonce`; the ID token verified against the provider's JWKS; the resolved subject matched to a `user_identities` row. The provider's token is **never** used as a LegalMind session — it is exchanged for a server-side session (47.1.2) and discarded.

### Account resolution

1. Known `(OIDC, sub)` → sign in as that user.
2. Unknown `sub`, verified email matching an existing user → link a new `user_identities` row to that user. Requires a **verified** email claim; an unverified claim is refused.
3. Unknown `sub`, no matching user → **refused.** LegalMind does not self-provision accounts; a user must be created by an authorized administrator (`user.manage`). This preserves the locked authorization model — an account's roles must be assigned deliberately, never inferred from a successful login.

### Fallback password mechanism

Available only when explicitly enabled. Subject to S-5 (rate limiting), S-7 (no enumeration) and the same session contract. `status` gating (42.2 `ACTIVE` / `SUSPENDED` / `DISABLED`) applies to **both** mechanisms — a disabled account cannot authenticate by any route.

**Deferred, not invented:** password policy specifics, reset-token flow and mail transport are implementation-phase items for the fallback path only; MFA is deferred to the identity provider, which is a principal reason SSO is primary.

---

# 47.2 · OD-2 — Super-role authority · **RESOLVED from locked text**

Step 23's locked role summary states, of Super Admin:

> **No automatic Legal Decision authority**

and:

> A Super Admin without that Legal permission **cannot approve the customization merely because they are a Super Admin.**

**Resolution:**

1. A super-role bypass **may** exist for administrative permissions (user, role, platform, audit administration).
2. It **must explicitly exclude** `legal.decision` and `legal.approve_customization`. These are never reachable by bypass, inheritance, or implication.
3. The exclusion is enforced **server-side in the permission resolver**, not by convention.

```text
resolve(user, permission):
    if permission in LEGAL_AUTHORITY_PERMISSIONS:
        return has_explicit_grant(user, permission)      # bypass never applies
    if user_holds_super_role(user):
        return true
    return has_explicit_grant(user, permission)
```

This is the single most important control in Step 47. The external reference's `is_super` pattern — "returns true immediately without consulting grants at all" — would silently violate locked ROLE-05 if adopted unmodified. **Adapted, not copied** (conflict C-EXT-4).

---

# 47.3 · OD-3 — Single vs multi-role · **RESOLVED from locked text**

Locked 42.3 defines `user_roles` with `PRIMARY KEY(user_id, role_id)` and the comment "This keeps role assignment flexible." The locked schema is many-to-many.

**Resolution: multi-role, with union semantics.** A user's effective permissions are the union of their roles' grants.

**This also resolves a puzzle in Step 4.** Its locked example shows two users, both Admins, one with legal approval authority and one without. Under single-role that is impossible. Under the locked multi-role schema it is natural: the second Admin *additionally holds* a Legal Decision Authority role.

```text
Admin A   roles: { Admin }                            → no legal authority
Admin B   roles: { Admin, Legal Decision Authority }  → legal authority
```

**No new table.** Legal authority is carried by an additional role assignment, using locked 42.3 exactly as its comment intends. The external reference's single-role model is **rejected** — it would foreclose the mechanism the locked schema provides (conflict C-EXT-3).

---

# 47.4 · OD-4 — Permission catalogue

Built from LegalMind's locked domain objects. Dotted naming convention adapted from the external reference (A-2); contents entirely LegalMind's. Three names are already locked in Step 23 and are carried verbatim.

| Group | Permissions |
|---|---|
| Contracts | `contract.view` · `contract.create` · `contract.update` · `contract.delete` |
| Documents | `document.upload` · `document.view` · `document.download` |
| Reviews | `review.create` · `review.view` |
| Findings | `finding.view` · `finding.comment` |
| Evaluations | `evaluation.view` |
| **Legal authority** | **`legal.review`** · **`legal.decision`** · **`legal.approve_customization`** *(locked names, Step 23)* |
| Legal configuration | `configuration.view` · `configuration.draft` · `configuration.publish` · `configuration.deprecate` |
| Internal legal position | `legal_position.view` *(gates rule outcomes and thresholds — LEGAL-02)* |
| Reporting | `report.view` · `report.generate` · `export.generate` |
| Audit | `audit.view` |
| Administration | `user.manage` · `role.manage` · `platform.manage` |

## Default grants, mapped onto Step 23's locked role summary

| | User | Legal Reviewer | Legal Admin | Super Admin |
|---|---|---|---|---|
| Contracts / Documents / Reviews | ✅ own | ✅ scoped | ✅ scoped | ✅ |
| `finding.view`, `evaluation.view` | ✅ | ✅ | ✅ | ✅ |
| `legal_position.view` | ❌ | ✅ | ✅ | ❌ |
| `legal.review` | ❌ | ✅ | ✅ | ❌ |
| **`legal.decision`, `legal.approve_customization`** | ❌ | **only when explicitly granted** | **only when explicitly granted** | **❌ never automatic** |
| Legal configuration | ❌ | ❌ | ✅ | ❌ |
| `audit.view` | ❌ | ❌ | ❌ | ✅ |
| Administration | ❌ | ❌ | ❌ | ✅ |

Every cell traces to Step 23's locked summary — including Legal Admin having no automatic platform administration, and Super Admin having no `legal_position.view` (internal legal strategy is not a platform-administration concern; LEGAL-02).

**Catalogue changes** follow the additive pattern adapted from the external reference (U-8): new permissions are inserted idempotently and are **never auto-granted to non-super roles**, so an administrator's deliberate trimming is never silently undone.

---

# 47.5 · Legal Decision authority — the separation

Locked Step 23 and Step 4 make this a distinct capability, not an ordinary permission:

```text
Platform Administration  ≠  Legal Configuration  ≠  Legal Review  ≠  Legal Decision
```

**Rules:**

1. `legal.decision` and `legal.approve_customization` require an **explicit** grant. Never inherited, never implied by any role, never reachable by super-role bypass.
2. Holding `legal.review` does **not** confer `legal.decision` (Step 23: "Make Legal Decisions **when explicitly permitted**").
3. Legal Configuration authority does not confer Legal Decision authority, and vice versa.
4. A decision is checked at the **Evaluation** level (AB-1: `legal_decisions.evaluation_id`), traversing to the owning Contract.
5. **Second-person approval** (Step 31 r15) is evaluated at Evaluation level and requires a *different* user holding the same authority.
6. **Never zero authorities:** a configuration change must not leave the system with no user holding `legal.decision`. Adapted from the external lockout guard (A-6); protects Step 31 r18 and Step 30 r7 from an unresolvable Review.

**NOT YET SPECIFIED — deferred by locked Step 4:** granular approval limits ("Later we may introduce granular approval limits, but those are not finalized yet"). V1 grants are unscoped. Do not invent thresholds.

---

# 47.6 · Object-level authorization

Locked 41.24 and 43.23 define the traversal. Extended for the AB-1 Evaluation layer:

```text
Legal Decision → Evaluation → Finding → Review → Contract → owner / scope → User → Roles → Permissions
```

**Rules:**

1. Every object access resolves ownership/scope server-side. **Knowing an ID is never sufficient** (41.24, Step 39).
2. Authorization occurs at the API/service boundary before any domain operation (43.23).
3. The UI performs **presentation-only** gating. It never talks to the database (38.22) and never implements evaluation logic (38.23). Adopting the external reference's page-level direct-database pattern is **prohibited** (conflict C-EXT-1).
4. Ownership and Review visibility follow locked Step 24 / ROLE-07.
5. `legal_position.view` gates rule outcomes, thresholds and `rule_configuration` in every response (LEGAL-02).

---

# 47.7 · Denial semantics

Derived from 41.24 (IDOR) and LEGAL-02 (confidentiality). Extends locked 43.22 without contradicting it.

| Situation | Response |
|---|---|
| No valid session | **401** |
| Valid session; object exists but is outside the user's ownership/visibility scope | **404** — existence is not disclosed |
| Valid session; object is visible; user lacks the operation permission | **403** |
| Valid session; permission held; business rule rejects | **409 / 422** per 43.22 |

**Rationale for 404 over 403 on out-of-scope objects:** for contracts, reviews and findings, confirming that an object with a given ID exists is itself a disclosure — a counterparty name or an ongoing negotiation can be inferred from existence alone. The external reference does not address this; LegalMind's confidentiality posture requires it.

Error bodies never disclose internal legal position, and never differ in a way that allows probing.

---

# 47.8 · Session and security invariants

| # | Invariant | Basis |
|---|---|---|
| S-1 | Authority is resolved fresh per request; nothing about *what a user may do* is trusted from the session | 38.21; external U-1 |
| S-2 | Sessions are revocable server-side and revocation is immediate | 47.1.2 |
| S-3 | Session cookies are `HttpOnly`, `Secure`, `SameSite`; CSRF protection on all state-changing requests | Step 39 "Session security" |
| S-4 | Credential material is never returned by any endpoint; excluded at the repository layer, not by response filtering | External U-3 |
| S-5 | Rate limiting on authentication and on expensive analysis endpoints; thresholds are deployment configuration | Step 39 "Rate limiting" |
| S-6 | Secrets outside source control; signing/encryption keys rotatable | Step 39 |
| S-7 | No account enumeration on any identity-related response | External U-5 |
| S-8 | Authority-escalation guard: **a user may not grant an authority they do not themselves hold** — applied to `legal.decision`, `legal.approve_customization`, `role.manage` and `platform.manage` | Adapted from external A-1 |
| S-9 | The escalation guard covers **granting, editing and deleting** a more-privileged account — not only granting | External's own admitted gap (C-EXT-9); LegalMind does not inherit it |
| S-10 | Role–permission changes are transactional | Locked 43.26; external's non-transactional approach rejected (C-EXT-7) |

---

# 47.9 · Audit and security events

**Resolved without a new table.** Locked `audit_events` (42.18) is entity-shaped — `actor_id`, `action`, `entity_type`, `entity_id`, `before_state`, `after_state`, `metadata` — and accommodates authentication events directly:

| Event | `entity_type` | `actor_id` |
|---|---|---|
| `auth.login_succeeded` | `session` | user |
| `auth.login_failed` | `authentication` | NULL when the account is unknown |
| `auth.logout` | `session` | user |
| `auth.session_revoked` | `session` | revoking actor |
| `authz.permission_denied` | target entity | user |
| `admin.role_granted` / `admin.role_revoked` | `user` | actor |
| `admin.legal_authority_granted` / `revoked` | `user` | actor |
| `admin.permission_changed` | `role` | actor |

Rules: append-only (AUD-01); `actor_id` nullable for pre-authentication events; **no credential material, session token or password ever recorded**; failed-login records must not become an enumeration oracle in any surfaced view.

This closes the gap the external reference names in its own documentation — it has no auth-event logging at all.

---

# 47.10 · Rejected external patterns

Recorded so they are not reintroduced.

| Pattern | Why rejected |
|---|---|
| `is_super` blanket bypass | Would confer Legal Decision authority, violating locked ROLE-05 and Step 23 (C-EXT-4) |
| Pages reading the database directly | Prohibited by locked 38.22 (C-EXT-1) |
| Business/auth logic in frontend route handlers | Locked stack is Next.js → FastAPI → Services → Repositories (C-EXT-2) |
| Single role per user | Forecloses the locked 42.3 mechanism that Step 4 depends on (C-EXT-3) |
| Stateless session with no revocation | Incompatible with legal-document custody (47.1.2) |
| Non-transactional permission replacement | Locked 43.26 (C-EXT-7) |
| MySQL idioms | Locked PostgreSQL (C-EXT-3) |

---

# 47.11 · Escalated

**OD-9 is decided (§47.1.3). No decision remains escalated in Step 47.**

**Deferred, recorded, not invented:** granular legal-approval limits (locked Step 4 defers them); multi-tenancy (OD-11 — no locked requirement); MFA (depends on OD-9).

---

# 47.12 · Security implementation readiness

| Area | State |
|---|---|
| Identity contract | ✅ Specified |
| Session model & revocation | ✅ Specified (one new table) |
| Authentication mechanism | ✅ **OD-9 decided** — OIDC primary, password fallback |
| Super-role boundary | ✅ Resolved from Step 23 |
| Multi-role model | ✅ Resolved from 42.3 |
| Permission catalogue | ✅ Specified; mapped to Step 23's locked matrix |
| Legal Decision authority separation | ✅ Specified |
| Object-level authorization | ✅ Specified |
| Denial semantics | ✅ Specified |
| Session/security invariants | ✅ S-1 – S-10 |
| Audit/security events | ✅ Specified; no new table |
| Rate limiting | ✅ Control specified; thresholds are deployment config |

**Schema impact:** two new tables (`sessions`, `user_identities`). **No locked decision amended.**

## What remains before API finalization

1. Permission-to-endpoint mapping — every endpoint declares its required permission (Step 49).
2. Error envelope shape consistent with 47.7's denial semantics (Step 49).
3. Correlation identifiers linking request → audit event (Step 53).
