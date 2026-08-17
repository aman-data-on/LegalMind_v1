# External Reference Audit — MoS documentation

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a conclusion was reached, and its status lines describe the state **at the time of writing**, which has since changed. A conclusion is authoritative only where it appears in [LOCKED_DECISIONS.md](LOCKED_DECISIONS.md) and `all_lock.md`. Do not implement from this file.

**Status: ⏳ ANALYSIS ONLY — NOTHING LOCKED, NOTHING ADOPTED.**

Prepared 2026-08-16. `all_lock.md` unmodified (13,941 lines, md5 `66591e62`). No locked decision changed. No LegalMind requirement created.

## Source-of-truth hierarchy applied throughout

```text
1. all_lock.md                        authoritative
2. LegalMind docs/                    derived implementation reference
3. Approved reconciliation decisions  REC-01 – REC-07, J-series
4. External MoS documents             REFERENCE MATERIAL ONLY
```

**Where the external material conflicts with LegalMind, LegalMind wins.** Conflicts are recorded in §9, never resolved here.

---

# 1. External documents reviewed

| Document | Purpose | Primary relevance |
|---|---|---|
| `AUTHENTICATION (1).md` | MoS sign-in: password + Google OAuth, JWT session cookie, route guards, user status, forgot-password stub | Step 47, Step 55 |
| `AUTHORIZATION (2).md` | MoS RBAC: `roles`/`permissions`/`role_permissions`, `is_super` bypass, `requirePermission()`, privilege-escalation guard, activity log | **Step 47 (primary)** |
| `USERS (3).md` | MoS user management: paginated list, add/edit dialog, validation, per-route permission gating, known gaps | Step 47, Step 49, Step 52 |
| `PLATFORM_API.md` | MoS machine identities: API consumers, bearer tokens (one-time reveal, SHA-256 + prefix), ability catalogue | Reference / future |

All four describe **MoS**, a Next.js 16 + React 19 + **MySQL** admin application. They are internally consistent, unusually candid about their own gaps, and written to the same standard LegalMind aims for.

---

# 2. Executive conclusion

The external material is **strongest as a security-control checklist and weakest as an architecture**. Its stack and layering are incompatible with LegalMind's locked architecture; several of its individual mechanisms are excellent and portable.

**Three patterns are worth adopting almost as-is** (translated to LegalMind's stack):

1. **Fresh permission resolution on every request**, never trusted from the session token.
2. **The privilege-escalation guard** (`canAssignRole`) — LegalMind currently specifies no equivalent.
3. **Defensive data-access habits** — the password hash excluded from the default column set; duplicate-key handling instead of check-then-insert.

**Three patterns must be rejected outright**, because LegalMind's locked architecture forbids them:

1. Pages reading the database directly (MoS's page guards are load-bearing *because* of this) — prohibited by locked **38.22**.
2. Business/auth logic in Next.js API routes — LegalMind locks **Next.js → FastAPI → Services → Repositories** (Step 39, 43.x).
3. Non-transactional permission replacement — prohibited by locked **43.26**.

**One pattern is a genuine danger to LegalMind's legal model:** the `is_super` bypass. Adopting it unmodified would grant Legal Decision authority implicitly, contradicting locked **ROLE-05** and Step 4. See conflict **C-EXT-4**.

**The most valuable single contribution** is not a pattern at all — it is MoS's *Known Gaps* discipline. Its enumerated gaps (no rate limiting, inert status value, no session revocation, no protection against an admin editing a more-privileged account) form a ready-made threat checklist for Step 47.

---

# 3. USE — adoptable substantially as-is

| # | Concept | Why it fits LegalMind unchanged | Destination |
|---|---|---|---|
| U-1 | **Permissions resolved fresh per request from the grant table, never from the session token.** "A permission revoked mid-session takes effect on the very next request." | Directly serves locked **38.21** (server-side authorization) and **41.24** (object-level checks). Also matches LegalMind's configuration-versioning instinct: authority is looked up, not carried. | Step 47 |
| U-2 | **Only the role identifier is trusted from the session; role *name* is display-only.** | Prevents a stale token from conferring authority. Consistent with **ARCH-02**. | Step 47 |
| U-3 | **Password hash never in the default column set** — one dedicated function is the only place it is selected. | A repository-layer discipline that composes with locked **43.25**. Prevents accidental exposure in any response. | Step 47 / Step 49 |
| U-4 | **Duplicate-key error handling instead of check-then-insert**, to avoid a race between check and write. | Correctness pattern, stack-neutral, consistent with locked transaction boundaries (**43.26**). | Step 49 |
| U-5 | **Identical response for unknown account, wrong password, and credential-less account** (no account enumeration). | Standard control; nothing in LegalMind contradicts it. | Step 47 |
| U-6 | **Server-side clamping of pagination parameters** regardless of client input (page size capped). | Clean convention for Step 49; no locked decision governs pagination yet. | Step 49 |
| U-7 | **Explicit "Access restricted" state rather than a broken/empty screen** when a viewer lacks a permission. | UX convention that respects **LEGAL-02** (do not leak what the viewer may not see). | Step 52 |
| U-8 | **Idempotent, additive permission-catalogue seeding** that never silently restores grants an administrator has trimmed. | Operationally sound; aligns with LegalMind's "no silent configuration change" posture (Step 29, AUD-03). | Step 47 / Step 55 |

---

# 4. ADAPT — useful, but must be redesigned for LegalMind

### A-1 — Privilege-escalation guard → **authority-escalation guard**

**External:** `canAssignRole(actorRoleId, targetRoleId)` — only an `is_super` role may grant an `is_super` role.

**Why LegalMind needs it:** LegalMind currently specifies **no** escalation guard anywhere. Locked **ROLE-05** says approval authority is separately assignable — but nothing prevents a Legal Admin from assigning legal-decision authority to themselves or another account.

**How to adapt:** the guard must key on **Legal Decision authority**, not on a "super" flag. LegalMind's dangerous grant is not "a more powerful role" in the abstract — it is *the authority to make binding Legal Decisions* (Step 31). The rule becomes: **a user may not grant an authority they do not themselves hold**, applied specifically to legal-decision authority, and enforced server-side in the service layer.

Note the external project's own admission: its guard covers *granting* a role but not *editing or deleting* a more-privileged account. LegalMind should not inherit that hole — see OD-12.

### A-2 — Dotted permission naming → LegalMind's domain vocabulary

**External:** `user.view`, `role.manage_permissions`, `platform_api.manage_tokens`.

**How to adapt:** the *convention* is good; the *catalogue* must be LegalMind's own — built from locked concepts: Contract, Document Version, Review, Finding, Evaluation, Legal Decision, Configuration, Audit, Export. Do not import MoS's groups.

⚠ **Do not model Legal Decision authority as an ordinary permission string without an explicit decision.** Locked ROLE-05 and Step 4 treat it as a distinct, separately assignable capability, and Step 31 r15 contemplates second-person approval. Flattening it into `decision.create` may under-model locked behavior. See **OD-5**.

### A-3 — Two independent writes (feed + audit) → audit only, unless a feed is specified

**External:** every mutation writes to a notification bell **and** to an activity log, deliberately kept independent so the audit trail's retention is not tied to anyone's inbox.

**How to adapt:** the *reasoning* is excellent and matches locked **AUD-01** (append-only) and 41.26 (no casual deletion). But LegalMind has **no notification feature specified**. Adopt the principle — *the audit trail is never the same store as any user-facing feed* — without adopting the feed. See **OD-15**.

### A-4 — Audit rows that survive deletion of their subject

**External:** `causer_id`/`subject_id` carry **no foreign key**, explicitly so the audit trail survives an account or role being deleted.

**LegalMind:** locked **42.18** defines `audit_events.actor_id UUID FK → users.id`. The `entity_type`/`entity_id` pair is already FK-free (good), but the actor is not.

**How to adapt:** cannot be adopted without touching a locked decision. Record as conflict **C-EXT-6** and decision **OD-7**. LegalMind's 41.26 (no casual hard delete) reduces the practical risk, but a future retention policy that permits user deletion would collide with this FK.

### A-5 — Denial behavior

**External:** `401` unauthenticated, `403` unauthorized.

**How to adapt:** LegalMind locks HTTP status semantics in **43.22** and locks the anti-IDOR rule in **41.24**. Neither the external material nor LegalMind addresses whether a `403` on an object the viewer may not see leaks its existence. For contracts and Findings this matters — an unauthorized user learning that a contract with a given identifier exists is itself a disclosure. See **OD-8**.

### A-6 — Lockout guard → "never zero legal authorities"

**External:** permission edits are refused if they would leave zero roles system-wide both assigned to a user and able to manage permissions.

**How to adapt:** LegalMind's equivalent risk is worse — a configuration change that leaves **no user able to make a Legal Decision** would stall every Review requiring one (Step 31 r18, Step 30 r7). Same shape, different invariant. See **OD-13**.

### A-7 — One-time secret reveal (hash + display prefix)

**External:** issued token returned once; only a SHA-256 hash and a 12-character prefix persist.

**How to adapt:** correct pattern for any future LegalMind secret (machine tokens, export links, signed report URLs). Not required by V1 — LegalMind has no locked machine-to-machine API. See **OD-10**.

---

# 5. REFERENCE ONLY — inform future design, do not become requirements

| # | Concept | Why reference only |
|---|---|---|
| R-1 | Google OAuth / OIDC hand-rolled flow (PKCE, `state`, `nonce`) | LegalMind's authentication mechanism and any corporate-identity integration are explicitly **NOT YET SPECIFIED**. Useful detail if SSO is later chosen; not a LegalMind requirement today. |
| R-2 | Account linking by verified email | Only meaningful once more than one sign-in path exists. |
| R-3 | Machine identity ("API consumer") + ability-scoped tokens | LegalMind V1 exposes no public data API. The external project is candid that its own tokens "do nothing yet." |
| R-4 | Ability catalogue with sensitivity badges and a warning banner for high-risk grants | Good UX pattern for a future permission-grant screen. |
| R-5 | Stat cards that filter the underlying list | Presentation idea for a future Review dashboard; no locked requirement. |
| R-6 | Separating "the system" from "the human contact" on a machine record | Sound modelling instinct, no current LegalMind entity needs it. |
| R-7 | Search across several columns via a single input | Convention only; LegalMind's search/filter requirements are unspecified. |
| R-8 | Keeping a legacy column inert rather than dropping it | Migration-discipline precedent; LegalMind has no legacy schema yet. |

---

# 6. REJECT — must not enter LegalMind

| # | External approach | Why rejected |
|---|---|---|
| X-1 | **Pages calling data-access functions directly, bypassing the API layer** (which is why MoS's page-level guards are load-bearing) | Directly prohibited by locked **38.22** — "The frontend should not directly manipulate the database… UI → API/Application Layer → Domain Logic → Database." Adopting it would defeat centralized permission, validation and audit enforcement. |
| X-2 | **Business and authorization logic inside Next.js API route handlers** | LegalMind locks the stack as Next.js → **FastAPI** → Services → Repositories (Step 39 stack table; 43.24, 43.25). MoS's route-handler pattern has no place in that layering. |
| X-3 | **MySQL-specific idioms** — `mysql2`, `ENUM` columns, `INSERT IGNORE`, MySQL's "NULLs are distinct in a UNIQUE index" behavior | LegalMind locks **PostgreSQL** as system of record (Step 39, 41.1). The NULL-distinctness trick in particular does not transfer safely. |
| X-4 | **Non-transactional permission replacement** (`DELETE` then a loop of `INSERT`s, no transaction) | Prohibited by locked **43.26** (transaction boundaries). The external project names this as its own gap. |
| X-5 | **Blanket `is_super` authorization bypass** *(in its unmodified form)* | See **C-EXT-4** — would implicitly confer Legal Decision authority, contradicting **ROLE-05** and Step 4. A narrowed variant may be viable, but the pattern as written must not be imported. |
| X-6 | **Native browser `confirm()` for destructive actions** | Inadequate for irreversible legal-record actions; LegalMind's audit and reproducibility posture (41.26, AUD-01) calls for explicit, recorded confirmation. |
| X-7 | **Client-side-only mirroring of an authorization rule as the primary control** | LegalMind locks server-side enforcement (**38.21**). Client-side filtering is acceptable only as a convenience atop a server check — which the external project does correctly, but the pattern is easy to misread. |
| X-8 | **A status value that exists in the enum but affects nothing** (`pending`) | LegalMind's fail-closed posture (ENG-09) and "never claim an unspecified decision is finalized" rule make inert vocabulary a defect, not a placeholder. |

---

# 7. NEEDS DECISION

Recorded, not decided. Full list with IDs in §16.

* Session model: stateless token vs server-side session records permitting revocation (**OD-1**)
* Whether a Super-Admin-equivalent bypass exists at all, and whether it may ever reach Legal Decision authority (**OD-2**)
* Single-role vs multi-role assignment — LegalMind's locked schema permits many (**OD-3**)
* Permission catalogue contents and naming convention (**OD-4**)
* Whether Legal Decision authority is a permission or a distinct capability (**OD-5**)
* Whether permission-catalogue changes are governed by Step 29 configuration versioning (**OD-6**)
* Audit actor foreign key vs deletion survivability (**OD-7**)
* `403` vs `404` denial semantics and existence disclosure (**OD-8**)
* Authentication method(s) and corporate-identity integration (**OD-9**)
* Machine-to-machine API access in V1 (**OD-10**)
* Multi-tenancy / workspace isolation (**OD-11**)
* Escalation protection for *editing/deleting* privileged accounts, not only granting (**OD-12**)
* "Never zero legal authorities" invariant (**OD-13**)
* Rate-limiting scope and thresholds (**OD-14**)
* Whether a user-facing notification feed exists at all (**OD-15**)

---

# 8. LegalMind step mapping

| External concept | Proposed step | Why | Impact |
|---|---|---|---|
| Permission catalogue + grant table | **Step 47** | LegalMind locks roles (Step 23) but never enumerates permissions | Database, backend, API |
| Fresh per-request permission resolution | **Step 47** | Serves 38.21 / 41.24 | Backend |
| Privilege/authority escalation guard | **Step 47** | No LegalMind equivalent exists | Backend, authorization |
| `is_super`-style bypass question | **Step 47** | Must be reconciled with ROLE-05 | Authorization |
| Session model & revocation | **Step 47** | AUTHENTICATION.md is NOT YET SPECIFIED; B-15 | Backend, security, deployment |
| No-enumeration login responses | **Step 47** | Standard control | Backend, API |
| Rate limiting | **Step 47** (control) / **Step 55** (mechanism) | Step 39 lists it as recommended only | Backend, deployment |
| Lockout guard ("never zero authorities") | **Step 47** | Protects Step 31 r18 / Step 30 r7 | Backend |
| Object-level authorization on every route | **Step 47** | Already locked (41.24, 43.23); external confirms the pattern | Backend, API |
| Pagination clamping | **Step 49** | No locked pagination convention | API |
| Response & error structure | **Step 49** | 43.21 locks the envelope; error shape unspecified | API |
| `403` vs `404` existence semantics | **Step 49** (with Step 47) | 43.22 locks status semantics but not disclosure | API, security |
| Correlation / request identifiers | **Step 53** | Absent from both projects; needed for audit correlation | API, observability |
| Authentication-event logging | **Step 53** (with Step 47) | External names its absence as a gap; LegalMind's audit covers domain events only | Audit, observability |
| Permission-driven UI gating + "Access restricted" state | **Step 52** | Must remain a convenience over server checks | Frontend |
| No legal logic in the frontend | **Step 52** | Already locked (38.23); external independently arrives at the same rule | Frontend |
| Secret management (`SESSION_SECRET`, env separation) | **Step 55** | Step 39 lists "secrets outside source code" | Deployment |
| "Production blockers" register | **Step 55** | Mirrors LegalMind's blocker discipline | Process |
| Machine tokens / one-time reveal | **Future** (not 47–55) | No V1 requirement | — |
| Webhooks, generated API docs, resource registry | **Future / out of scope** | External project itself excludes them | — |
| Testing | **Step 54** | ⚠ External material contributes **nothing** — no test strategy is described in any of the four documents | — |

---

# 9. Conflict audit

| ID | External rule | LegalMind rule | Conflict | Severity | Recommended treatment |
|----|---------------|----------------|----------|----------|------------------------|
| **C-EXT-1** | Pages call data-access functions directly; page-level guards are load-bearing because of it | **38.22** — no direct UI→database access; UI → API → Domain → Database | Architectural inversion. The external project's central authorization pattern exists to compensate for a layering LegalMind forbids | **CRITICAL** | **REJECT** (X-1). Keep LegalMind's layering; port only the *permission-check-per-entry-point* idea |
| **C-EXT-2** | Auth/business logic in Next.js API routes; MySQL via `mysql2` | Step 39 locked stack: Next.js frontend → **FastAPI** → Services → Repositories → **PostgreSQL** | Stack incompatibility | **CRITICAL** | **REJECT** (X-2, X-3). Translate concepts, never code shapes |
| **C-EXT-3** | Exactly one role per user (`users.role_id`) | **42.3** `user_roles` junction, `PRIMARY KEY(user_id, role_id)` — "keeps role assignment flexible" | LegalMind's locked schema permits multiple roles; the external model forecloses it | HIGH | **Do not import.** Whether LegalMind *intends* multi-role is **OD-3** — the locked schema says it is possible, no locked rule says it is used |
| **C-EXT-4** | `is_super` returns permission granted immediately, without consulting grants at all | **ROLE-05** — "Admin is a system role and does not automatically confer legal approval authority"; Step 4 — approval authority is separately assigned | A blanket bypass would grant Legal Decision authority implicitly to any super role — precisely what ROLE-05 forbids | **CRITICAL** | **REJECT unmodified** (X-5). If any bypass exists it must explicitly exclude legal-decision authority — **OD-2** |
| **C-EXT-5** | Stateless JWT session; "nothing is revoked server-side because nothing is stored server-side"; fixed 7-day life | LegalMind locks auditability and reproducibility (AUD-01, AUD-05) and server-side security (38.21). No locked session model exists | Inability to revoke a session is difficult to reconcile with legal-document custody; not a direct contradiction of locked text | HIGH | **NEEDS DECISION — OD-1.** Note the external design *does* resolve authorization freshly per request, which mitigates but does not remove the issue |
| **C-EXT-6** | Audit rows deliberately carry **no** foreign keys, so history survives deletion of accounts/roles | **42.18** — `audit_events.actor_id UUID FK → users.id` | The external pattern is the stronger audit design; LegalMind's locked schema adopts the weaker one | MEDIUM | **Report only — OD-7.** Mitigated in practice by 41.26 (no casual hard delete); becomes real if a retention policy later permits user deletion |
| **C-EXT-7** | Permission replacement is `DELETE` + loop of `INSERT`s, not transactional (self-identified gap) | **43.26** — transaction boundaries locked | Direct violation | MEDIUM | **REJECT** (X-4) |
| **C-EXT-8** | Every capability is a flat permission string, including the most privileged | ROLE-05 / Step 4 / Step 31 r15 — legal approval authority is separately assignable and may require second-person approval | Flattening may under-model locked authority semantics | HIGH | **NEEDS DECISION — OD-5** |
| **C-EXT-9** | Only per-record protection is "you cannot delete yourself"; any admin may edit/delete any other account | **41.24** — full ownership/role traversal required before access | LegalMind is *stronger*; no conflict, but the external gap is instructive | LOW (informational) | Adopt LegalMind's stronger rule; add **OD-12** for the edit/delete escalation hole |
| **C-EXT-10** | `bcryptjs`, `jose`, HS256 | LegalMind's Python stack (Step 39); no locked crypto choices | Library-level incompatibility only | LOW | Translate the *controls* (strong hashing, signed sessions), not the libraries |
| **C-EXT-11** | An enum value (`pending`) exists but gates nothing | ENG-09 fail-closed; "never claim an unspecified decision is finalized" | Inert vocabulary contradicts LegalMind's discipline | LOW | **REJECT** (X-8). Instructive as an anti-pattern for J-4's Finding status enum |

---

# 10. Security gap analysis

Capabilities LegalMind will need that its current specification does not provide.

### Implementation blockers

| Gap | Note |
|---|---|
| **Authentication mechanism entirely unspecified** | Already tracked as **B-15**. External material offers two candidate shapes (password, OIDC) but LegalMind has chosen neither |
| **Permission catalogue does not exist** | Step 23 locks *roles*; no locked text enumerates permissions. Every `requirePermission`-style check presupposes one |
| **Session lifecycle unspecified** | Creation, lifetime, renewal, revocation, logout — none specified. Blocks any deployable system |

### High priority

| Gap | Note |
|---|---|
| No authority-escalation guard | Nothing prevents granting legal-decision authority upward (A-1, OD-12) |
| No rate limiting specification | Step 39 lists it as *recommended*; never locked (OD-14) |
| No authentication-event logging | Locked audit covers domain events; login/logout/failure are outside `audit_events`' `entity_type`/`entity_id` shape |
| Denial semantics undefined | `403` vs `404` and existence disclosure for contracts/Findings (OD-8) |
| No "never zero legal authorities" invariant | A configuration change could stall every Review requiring a decision (OD-13) |

### Medium priority

| Gap | Note |
|---|---|
| Password policy / credential lifecycle | Only if password auth is chosen (OD-9) |
| MFA | Appropriate for legal-document custody; not specified |
| Account lockout after repeated failures | Distinct from rate limiting |
| Session-fixation and CSRF posture | Depends on OD-1 |
| Export authorization | LegalMind locks reporting/export as a domain (38.17) but no export-specific permission exists |

### Future

Machine-to-machine tokens · webhook delivery · generated API documentation · account linking across identity providers.

---

# 11. Architecture impact

| Layer | Impact if the ADAPT set were later adopted |
|---|---|
| **Database** | New `permissions` and `role_permissions` tables (LegalMind already has `roles` and `user_roles`). Possibly a session/token store (OD-1). No change to `findings`, `evaluations`, `legal_decisions` or the evaluator path |
| **Backend** | A permission-resolution service; an authority-escalation guard in the service layer; authentication-event emission |
| **API** | Per-endpoint permission declarations; pagination clamping; error envelope; correlation identifiers |
| **Evaluator** | **None.** Nothing in the external material touches the analysis engine, and nothing should — the evaluator never performs authorization (36.15, 45B.14) |
| **Authorization** | Formalizes what 41.24/43.23 already lock; adds the escalation guard LegalMind lacks |
| **Audit** | Authentication events need a home; the actor-FK question (OD-7) affects retention |
| **Frontend** | Permission-driven navigation and controls; "Access restricted" state — all strictly atop server checks (38.21, 38.23) |
| **Deployment** | Secret management, session-secret rotation, rate-limit placement (reverse proxy vs application) |

---

# 12. Locked-decision impact

Every locked decision that would be touched if an external recommendation were adopted. **None is modified here.**

| Locked decision | How it would be affected | Verdict |
|---|---|---|
| **38.21** security boundary | Confirmed and reinforced, not changed | No amendment needed |
| **38.22** no direct UI→DB | Would be *violated* by X-1 | **Reject the external pattern** |
| **38.23** no UI-side legal logic | Confirmed — external independently reaches the same rule | No amendment |
| **38.24** API/domain boundary | Endpoint naming remains unlocked; conventions are additive | No amendment |
| **Step 39** locked stack table | Would be *violated* by X-2/X-3 | **Reject** |
| **41.24** object-level authorization | Confirmed | No amendment |
| **42.3** `user_roles` junction | Single-role adoption would contradict it | **Do not adopt; OD-3** |
| **42.18** `audit_events.actor_id` FK | The stronger external audit pattern conflicts | **Report only; OD-7** |
| **43.22** HTTP status semantics | Existence-disclosure refinement would extend, not replace | Possible future amendment; OD-8 |
| **43.26** transaction boundaries | Would be violated by X-4 | **Reject** |
| **ROLE-05 / Step 4** approval authority separate from system role | Would be *undermined* by the `is_super` bypass | **Reject unmodified; OD-2** |
| **Step 23 / ROLE-06** role matrix | A permission catalogue must be built *under* it, not replace it | No amendment |
| **Step 31 r15** second-person approval | Flat permission strings may under-model it | **OD-5** |
| **AUD-01** append-only audit | Confirmed | No amendment |
| **LEGAL-02** internal legal position confidentiality | Permission-gated field exposure supports it | No amendment |

---

# 13. Recommendations for Step 47 — Security / Authorization

**Proposed scope (not locked):**

1. **Permission catalogue** built from LegalMind's own domain: Contract, Document Version, Review, Finding, Evaluation, Legal Decision, Configuration, Audit, Export. Naming convention adopted from external practice; contents entirely LegalMind's.
2. **Role↔permission model** layered beneath the locked Step 23 roles, using the existing locked `roles` and `user_roles` tables. Resolve OD-3 first.
3. **Legal Decision authority** modelled explicitly — resolve **OD-5** before writing any permission string for it.
4. **Whether a super-role bypass exists**, and if so, an explicit carve-out preventing it from ever conferring legal-decision authority (**OD-2**).
5. **Authority-escalation guard** — no user may grant an authority they do not hold; extended to *editing and deleting* privileged accounts, not only granting (**OD-12**).
6. **Object-level authorization**, restating locked 41.24/43.23 as implementable service-layer requirements, including the Evaluation → Finding → Review → Contract → Owner traversal from the J-series work.
7. **Session model** (**OD-1**): lifetime, renewal, revocation, logout, and whether server-side session state exists.
8. **Authentication mechanism** (**OD-9**) — resolves B-15.
9. **Denial semantics** (**OD-8**) — `401`/`403`/`404` and existence disclosure.
10. **Rate limiting and lockout** (**OD-14**).
11. **"Never zero legal authorities" invariant** (**OD-13**).
12. **Authentication-event logging** — where login/logout/failure records live, given `audit_events`' entity-shaped schema.
13. **Non-enumeration** guarantees on all identity-related responses.

**Explicitly out of Step 47 scope:** machine tokens, webhooks, MFA (unless OD-9 requires it), multi-tenancy (OD-11).

---

# 14. Recommendations for Step 49 — API Finalization

**Proposed scope (not locked):**

1. **Per-endpoint permission declaration** — every endpoint names the permission it requires; no endpoint is implicitly public.
2. **Pagination convention** — server-side clamping, maximum page size, stable ordering.
3. **Error envelope** — structured, machine-readable, never leaking internal legal position (LEGAL-02) or object existence (OD-8).
4. **Response envelope** — extends locked 43.21.
5. **Correlation identifier** on every request, propagated into audit events (Step 53 overlap).
6. **Idempotency** — locked 43.28; the external material adds nothing but confirms the need.
7. **Versioning** — locked 43.30.
8. **The J-series API surface** — Finding with nested `evaluations[]`, decisions targeting an Evaluation, supersession as create-not-update, `409` on version conflict. Blocked until B-6/B-8/N-11 resolve.
9. **No Finding-level decision endpoint** may exist (D-3.3).

---

# 15. Recommendations for Steps 52–55

**Step 52 — Frontend Architecture.** Permission array threaded from the server to drive navigation and control visibility; "Access restricted" state rather than empty screens; **no legal evaluation logic in the frontend** (locked 38.23 — the external project independently reaches the same conclusion, which is corroborating evidence for the rule). All client-side gating is presentation only. Reject the direct-database page pattern (X-1).

**Step 53 — Error Handling / Observability.** Correlation identifiers linking request → audit event → evaluation. Authentication-event logging (the external project names its absence as a gap). Structured errors that never disclose internal legal position. Distinguish operator-facing diagnostics from user-facing messages — consistent with REC-07's rule that diagnostics never become legal conclusions.

**Step 54 — Testing Strategy.** ⚠ **The external material contributes nothing here** — none of the four documents describes a test strategy, fixtures, or coverage. Step 54 must be built from LegalMind's own locked ENG-12 golden-corpus requirement and the J-series workflow tests. The absence is itself informative: an admin application can survive without a documented test strategy; a deterministic legal evaluator cannot.

**Step 55 — Deployment / Infrastructure.** Secrets outside source control with a documented environment contract; secret rotation (session signing key); rate limiting placement; a "production blockers" register mirroring LegalMind's existing blocker discipline.

---

# 16. New open decisions

**All OPEN. None decided. None locked.**

| ID | Decision | Blocking? |
|----|----------|-----------|
| **OD-1** | Session model — stateless token vs server-side sessions with revocation; lifetime; renewal; logout semantics | **Implementation blocker** |
| **OD-2** | Does a super-role authorization bypass exist? If so, must it exclude Legal Decision authority? (ROLE-05) | **Implementation blocker** |
| **OD-3** | Single-role or multi-role assignment — locked `user_roles` permits many; no locked rule says which is intended | **Implementation blocker** |
| **OD-4** | Permission catalogue contents and naming convention | **Implementation blocker** |
| **OD-5** | Is Legal Decision authority a permission string or a distinct capability? (ROLE-05, Step 31 r15) | High |
| **OD-6** | Are permission-catalogue changes governed by Step 29 configuration versioning? | Medium |
| **OD-7** | `audit_events.actor_id` FK vs audit survivability under a future retention policy | Medium |
| **OD-8** | `403` vs `404` denial semantics; existence disclosure for contracts and Findings | High |
| **OD-9** | Authentication method(s); integration with any existing corporate identity system | **Implementation blocker (B-15)** |
| **OD-10** | Machine-to-machine API access in V1 | Low (likely deferred) |
| **OD-11** | Multi-tenancy / workspace isolation — unspecified in LegalMind | Medium |
| **OD-12** | Escalation protection for editing/deleting privileged accounts, not only granting | High |
| **OD-13** | "Never zero users able to make Legal Decisions" invariant | High |
| **OD-14** | Rate-limiting scope, thresholds, and placement | High |
| **OD-15** | Does a user-facing notification feed exist at all, separate from the audit trail? | Low |

---

# 17. Implementation impact — risk reduction

Patterns most likely to materially reduce LegalMind's implementation risk:

1. **Fresh per-request permission resolution (U-1).** Eliminates a whole class of stale-authority bugs and makes revocation immediate. Cheap to build if decided early; expensive to retrofit once tokens carry grants.
2. **The authority-escalation guard (A-1).** The vulnerability the external project describes — *any* admin able to grant the highest privilege through an ordinary edit form — maps directly onto LegalMind's legal-decision authority, where the consequence is a binding legal ruling rather than an account change.
3. **Hash/secret exclusion at the repository layer (U-3).** Structural rather than reviewer-dependent.
4. **Duplicate-key handling over check-then-insert (U-4).** Removes a real race; composes with locked transaction boundaries.
5. **Permission-catalogue seeding that never silently restores trimmed grants (U-8).** Directly analogous to LegalMind's locked "drafts never silently affect comparisons" rule — the same class of mistake in a different subsystem.
6. **The Known Gaps discipline.** The most transferable practice in the entire external set, and the one already mirrored by LegalMind's blocker register.

**Counter-risk:** the external material's greatest hazard is its *plausibility*. It is well written and internally coherent, which makes its architecture tempting to import wholesale — and its architecture is incompatible with LegalMind's locked layering at three separate points (C-EXT-1, C-EXT-2, C-EXT-7). Concepts should cross the boundary; structure should not.
