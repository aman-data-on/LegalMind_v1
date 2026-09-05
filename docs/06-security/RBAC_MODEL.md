# Who can do what — the LegalMind access model

**Status: 🔒 LOCKED by AB-12 (2026-09-05).** Source of truth: the AB-12 record in
[`all_lock.md`](../../all_lock.md); registry rows `AM-39`–`AM-41` in
[LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md). This page is the
plain-language reading of it, written so an engineer joining in six months can answer
every question below without opening the code. The code that enforces it:
`backend/legalmind/security/permissions.py` (what), `security/authorization.py` (on
which objects), `api/deps.py` (where it is checked).

---

## The people

| Persona | Role code | In one sentence |
|---|---|---|
| **Department User** | `USER` | Runs their own deals: creates the contract, uploads versions, analyses, reads the findings *and why*, asks the AI, archives what they no longer need. |
| **Department Lead** | `DEPARTMENT_LEAD` | A Department User who also sees every deal in **their** department, can hand a deal from one colleague to another, and owns the Company Standards. |
| **Platform Admin** | `PLATFORM_ADMIN` | Creates accounts and departments, grants roles, reads the audit trail. **Never opens a deal.** |
| **Developer** | `DEVELOPER` | Break-glass for debugging. Holds every permission **except** legal authority. Every read of someone else's deal is audited like anyone else's. |

Two roles exist for a workflow nobody runs yet and are granted to nobody:
`LEGAL_REVIEWER` (global legal scope over escalated reviews, `REC-09`) and
`LEGAL_DECISION_AUTHORITY` (`legal.decision`, `legal.approve_customization`). They are
kept, hidden from the everyday picker (`tier: future_legal`), and grantable only by
someone who already holds what they confer (S-8).

## How a permission becomes a yes or a no

```text
ROLE  →  PERMISSIONS  →  RESOURCE SCOPE  →  ACTION

permission   WHAT the caller may do        e.g. document.view, contract.transfer
scope        on WHICH contract             OWN | DEPARTMENT | PLATFORM
```

Every object in the product — a document version, a review, a finding, an
evaluation, a report, a comparison — hangs off exactly one **Contract**, and the
caller's relationship to that contract decides everything:

| Basis | When | Grants |
|---|---|---|
| **OWNER** | `contract.owner_id` is you | read **and write** |
| **DEPARTMENT** | you hold `department.view` **and** the owner is in your department (`users.department_id`) | read only |
| **LEGAL_SCOPE** | you hold `legal.review` and a review of the contract is in `REC-09` scope | read only (future workflow) |
| none | anything else | **404** — not 403. Existence is itself a disclosure. |

Three consequences worth stating plainly:

* **Writes are owner-only.** A Lead cannot upload to, rename, analyse or archive a
  colleague's deal. To act on it they transfer it to themselves first — one audited
  step — so "who may change this contract" always has a one-word answer.
* **"Department" is a real boundary, not a flag.** The Lead's scope is bounded by the
  department table. An account in no department is widened to nothing, even with the
  permission. There is no "everyone" department and no global read.
* **The platform administrator is outside all of it.** They can put you in a
  department and still cannot see one line of your contract.

## Who owns a contract, and how it moves

The uploader owns it. A Department Lead can transfer it to an active colleague **in
the same department** with a reason (`POST /contracts/{id}/transfer`). Recorded in
`audit_events` as `contract.ownership_transferred`: previous owner, new owner, actor,
reason, contract, timestamp.

Everything anchored on the contract moves with it — versions, reviews, findings,
reports, annotations — because visibility is rooted in the contract. The previous
owner loses access. `reviews.created_by` stays as history. **Ask conversations do
not move**: they belong to the person who asked (below).

## What a Department User sees on a finding

Everything about their own deal, including the internal position: the expected value,
the comparison, the explanation chain that makes a MATCH / DEVIATION / MISSING
understandable (`legal_position.view`, granted to every Department User by AB-12 r7).
What they do **not** see is the configuration itself — the list of standards and their
version history (`configuration.view`) stays with the Lead.

## Ask history is private

A conversation is visible to its creator only. Department scope does not reach it,
a transfer does not move it, and no sharing feature exists. A Lead may ask about a
department deal (they can read it), and that conversation is theirs alone. If a
contract leaves your scope, you keep your old conversation and can no longer ask new
questions about the document.

## Archive, never delete

There is **no** verb that destroys a contract — `DELETE /contracts/{id}` does not
exist (405). Archiving (`POST …/archive`, mirror `…/restore`) sets `archived_at`:
the contract leaves the working lists and summary, refuses every write with 409, and
stays readable by its owner and department lead (`GET /contracts?archived=true`).
The document, every version, the evidence, reviews, findings, decisions, Ask
citations and the audit trail all remain — "what did LegalMind know about this
contract at that point in time?" stays answerable forever.

## Standards and their history

The Lead drafts, publishes and deprecates configuration through the existing
lifecycle (`configuration.draft/publish/deprecate`). Publishing never changes an
existing Review: every Review pins a `configuration_snapshot_id`, and a finding is
explained against the snapshot it was evaluated under — the 2026 analysis stays
reproducible under the 2026 standard after the 2027 change.

## Nobody approves inside LegalMind — for now

The initial workflow flags deviations; the yes/no happens outside the system. A
Review holding a deviation therefore reaches `LEGAL_REVIEW` and stays there — that
*is* the flag. `legal.decision` exists, is held by nobody, and can be granted to the
Lead later (`LEGAL_DECISION_AUTHORITY`) without any further amendment if the
organisation wants Reviews to close inside the product.

## What is audited

| Event | Action |
|---|---|
| Someone reads a deal they do not own | `contract.read_via_department_scope` / `contract.read_via_legal_scope` (basis recorded) |
| Ownership transfer | `contract.ownership_transferred` |
| Archive / restore | `contract.archived` / `contract.restored` |
| A department is created; a user is placed | `admin.department_created` / `admin.user_updated` (department in before/after) |
| A denial, or a probe of an invisible object | `authz.permission_denied` / `authz.object_not_visible` |

Owner reads of their own deals are **not** audited: that is not a disclosure, and
recording it would bury the events that are.

## When someone leaves

The Lead transfers their deals (each transfer audited), then the Platform Admin
disables the account (S-9/SEC-05 guards apply; sessions are revoked immediately).
Their Ask history stays theirs and unreadable to anyone else.

## Sign-in never grants authority

Authority is resolved from the database on every request (S-1); the JWT's `roles`
claim is advisory. A first-time SSO sign-in receives the configured JIT role(s) —
and since AB-12 r11 a configured role that carries legal authority or platform
administration is **refused at provisioning**, whatever the environment says.
