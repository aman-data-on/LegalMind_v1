# `F-6` — Legal access to a Review: what is locked, what is missing

> 📁 **Working document — analysis only, nothing locked here.** It records *how* a
> conclusion was reached and decides nothing. A conclusion is authoritative only where
> it appears in [LOCKED_DECISIONS.md](../../00-project/LOCKED_DECISIONS.md) and
> `all_lock.md`. Do not implement from this file.

> **§4 was APPROVED and is now locked as `REC-09`** (2026-08-17), appended to
> `all_lock.md` after AB-2 and implemented. `G1` (per-user assignment) was **not**
> approved and is deferred to V2. See **§7** for what was built and for one consequence
> the end-to-end exercise produced.

**Prepared 2026-08-17.** Scope: trace every locked rule governing Legal Reviewer access
to a Review, establish exactly which specification is absent, and prepare the **smallest
possible** decision that would let the locked Legal workflow function. No endpoint,
permission or locked decision is invented here, and nothing is implemented.

Basis: locked Steps 22, 23, 24, 30, 31 · `ROLE-03`, `ROLE-04`, `ROLE-07` · Step 47
(`SEC-04` permission catalogue, `SEC-06`) · Step 49 · Amendment Batch AB-2 (`AM-22`,
`AM-23`, `AM-24`) · the implementation in `backend/legalmind/security/authorization.py`.

---

## 1 · The symptom

A Legal Reviewer can reach **no Review at all** through the API.

`can_see_review` (`security/authorization.py`) grants access on ownership **or** an
active `review_assignments` row. Nothing else — correctly, since locked Step 24 r12 says
access is "permission + resource scope, not simply role name".

* **No application code path writes `review_assignments`.** Verified: the table is read
  in two places (`authorization.py`, `api/routers/reviews.py`) and constructed nowhere
  outside tests.
* **`LEGAL_REVIEWER` does not hold `review.create`** (Step 23 default grants), so a Legal
  Reviewer cannot own a Review either.

Therefore every Legal-facing surface — `GET /reviews/{id}`, findings, evaluations, the
report, `POST /evaluations/{id}/decisions` — returns **404** to the roles that exist to
use them. Confirmed by browser test, not inferred.

**The backend suite conceals this.** Nine test sites insert `review_assignments` rows
with `db.add()`:

```
tests/test_api_decisions.py:58   tests/test_api_findings.py:68, 239
tests/test_authorization.py:179, 190, 202                tests/test_api_authz.py:75
tests/test_workflow_decisions.py:91, 145
```

Every Legal-workflow test therefore runs against a fixture the product cannot produce.
The tests are not wrong about the *rules*; they are silent about the *reachability* of
the state those rules govern.

---

## 2 · What is locked

| Source | Locked text |
|---|---|
| Step 23 r11 | "Role names alone do not determine resource scope." |
| Step 23 r12 | "Permissions support resource scope such as **own, assigned, Legal scope, or system scope**." |
| Step 23 r15 | "Review visibility/scope is **deliberately left for a separate decision** before implementation." |
| Step 23 example | `Legal Reviewer` + `legal.review` + **`review.scope = assigned`** |
| Step 24 r5 | "**Escalation makes the Review available to the authorized Legal workflow.**" |
| Step 24 r6 | "Legal Reviewer access is controlled by **assignment and/or explicit Legal scope**." |
| Step 24 r7 | "Legal Admin has **authorized Legal-scope access** but does not automatically have unrestricted platform access." |
| Step 24 r8 | "Super Admin does not automatically have access to confidential contract or Legal content." |
| Step 24 r13 | "Least-privilege access is the default." |
| Step 24 r16 / r17 | A Review may be visible to a Legal Reviewer **without transferring ownership**; assignment "gives access for Legal work; it does not make the Legal Reviewer the business owner". |
| Step 24 r18 | A resolved Review stays accessible to its owner, "while Legal access remains governed by Legal scope/assignment". |
| Step 30 | `LEGAL_REVIEW` = "**One or more Findings require an authorized Legal decision.**" |
| Step 22 r4 / `ROLE-03` | Normal Users **can escalate** findings. |
| `ROLE-04` | "Escalation is not approval — it means 'this requires authorized review'." |
| `AM-22` | `review_assignments` ratified: `review_id`, `user_id`, `assigned_by`, `revoked_at`. Driver: r6, r16, r17. |
| `AM-23` | `escalations` ratified at **Finding** level, with a working endpoint. Driver cites **Step 24 r5**. |

Step 24's locked example draws the intended flow end to end:

```text
User A escalates  →  Legal Queue  →  assigned to  →  Legal Reviewer B
```

So escalation and assignment are **two stages of one locked flow**, not competing
mechanisms: escalation makes the Review *available*; assignment allocates it.

---

## 3 · The gap, stated precisely

Three things are absent. Only the second one blocks.

**G1 — No operation creates an assignment.** The locked example's "assigned to" arrow has
no actor. Step 49's endpoint table contains no assignment endpoint; the `SEC-04`
catalogue of **27 permissions** contains nothing that would authorize one (`Reviews` holds
exactly `review.create` and `review.view`); and no locked rule says who may assign.

**G2 — "Explicit Legal scope" is never defined.** It is *named* in Step 23 r12 and Step 24
r6, and given a criterion nowhere in `all_lock.md`. Consequently **both branches of r6 are
unimplementable**, which is why `can_see_review` has only ownership.

**G3 — The "Legal Queue" is never specified.** The phrase occurs exactly **once** in
`all_lock.md` — line 1796, inside Step 24's example diagram — and is defined by no rule,
no table and no endpoint. So even the listing by which a Legal user would *find* work is
unspecified.

### Corroboration: a locked permission with no call site

`legal.review` is granted to `LEGAL_REVIEWER` and `LEGAL_ADMIN` by Step 23's default
grants and is **checked nowhere in the codebase**. Every other permission in the
catalogue has an enforcement site. A locked permission that grants nothing is what an
unimplemented scope rule looks like from the inside.

### Why G1 cannot be fixed on its own

Adding an assignment endpoint appears to be the obvious repair. It does not work alone,
and the reason is locked:

* Whoever assigns must first **see** the Review in order to assign it.
* Step 24 r8 denies Super Admin access to Legal content, so a platform administrator
  cannot be the assigner.
* Step 24 r7 gives Legal Admin "authorized **Legal-scope** access" — which is exactly the
  thing G2 leaves undefined.

**So G2 must be decided regardless of what happens to G1.** And once G2 is decided, the
locked workflow functions with no new endpoint and no new permission.

---

## 4 · The smallest possible decision

**Decide G2 only. Defer G1.**

Proposed decision text, offered for approval and **not** treated as settled:

```text
Step 24 r6's "explicit Legal scope", for V1:

    A Review is IN LEGAL SCOPE while either
      (a) any of its Findings has an escalation that has not been
          withdrawn                                    (Step 24 r5, AM-23)
      (b) its Review lifecycle status is LEGAL_REVIEW   (Step 30)

    A holder of `legal.review` may access a Review that is in Legal scope.
    Access confers NO ownership (Step 24 r16, r17) and NO decision
    authority (SEC-02, ROLE-05, Step 23 r8).

    Per-user assignment (`review_assignments`, AM-22) is NOT an access
    path in V1. The table stays as ratified and unused for access;
    scoping access to individually assigned Reviews is DEFERRED TO V2.
```

Both disjuncts are needed, and each traces to a locked rule:

* **(b) alone is insufficient.** A user may escalate a Finding on a `RESOLVED` Review, and
  Step 30's state machine has no `RESOLVED → LEGAL_REVIEW` edge — verified in
  `workflow/escalation.py`, which refreshes the *Finding* status and never the Review's.
  Without (a), a user's escalation after resolution would be invisible to Legal, and
  `ROLE-04` says escalation means "this requires authorized review".
* **(a) alone is insufficient.** The engine derives `LEGAL_REVIEW` with no user
  escalation whatsoever (Step 30 r6, `advance_after_analysis`), and Step 30 defines that
  status as "one or more Findings require an authorized Legal decision". Without (b), a
  Review that the *engine* says needs a Legal Decision would wait for a human to escalate
  it first.

### Why deferring G1 is not a shortcut

`AM-24` set the precedent inside AB-2 itself: ownership **transfer** was deferred to V2
because "no locked rule requires the capability; Step 24 r2 permits it without mandating
it." The identical reasoning applies here — Step 24 r6 says "assignment **and/or**
explicit Legal scope", and *and/or* permits the assignment branch without mandating it.

### What this costs

Honestly stated, because it is the one real objection:

* Every `legal.review` holder can see every Review in Legal scope. That is coarser than
  Step 23's illustrative `review.scope = assigned`, and sits against Step 24 r13's
  least-privilege default. It is, however, precisely the "Legal scope" that Step 23 r12
  names as a first-class scope kind and that Step 24 r7 grants Legal Admin.
* A Review **not** in Legal scope stays invisible to Legal — ownership-only, exactly as
  r4 requires. The widening is bounded by escalation and by the engine's own signal.
* Step 24 r15 ("access to confidential Legal information must be auditable") is already
  satisfied: `Guard` audits every denial, and `legal_position.view` gates internal legal
  position independently of visibility.

### What it does not touch

No new endpoint · no new permission · no schema change · no locked table amended · no
change to `SEC-02`/`ROLE-05` (a super-role still cannot decide) · no change to
`LEGAL-02` confidentiality · `AM-22` stays ratified · Step 49's endpoint table unchanged
(the Legal queue becomes the existing `GET /reviews` under the same scope predicate,
which 49.6 already requires to mirror `can_see_review`).

---

## 5 · The alternative, for completeness

**Implement G1 as well: an assignment endpoint plus a permission.**

This is the larger change and is recorded so the choice is visible, not to argue against
it. It would require:

* a new endpoint (`POST`/`DELETE` on a Review's assignments) — a Step 49 addition;
* a **28th permission** in the `SEC-04` catalogue — an amendment, since Step 47 locks the
  catalogue;
* a rule naming who may assign, which no locked decision supplies;
* **and G2 anyway**, so that the assigner can see the Review (§3).

It buys per-user least privilege (r13) and matches Step 23's `review.scope = assigned`
example most literally. It is strictly a superset of the §4 decision, so §4 does not
foreclose it: V2 can narrow Legal scope to assignment once the assignment operation
exists.

---

## 6 · What I have not done

* **`all_lock.md` is untouched.** 15,196 lines, byte-identical.
* **Nothing is implemented.** `can_see_review` is unchanged, and the browser suite still
  works around `F-6` with the workaround labelled as one (`tools/e2e_bootstrap.py`).
* **No new endpoint, permission or table** exists or is drafted in code.
* **The STRUCTURAL corpus is unchanged** at 16 fixtures *(as of this record, 2026-08-17; nine `DOCUMENT_SUPPORTED` fixtures were added on 2026-08-18 — see [SOURCE_MATERIAL_INTAKE.md](../../00-project/SOURCE_MATERIAL_INTAKE.md))*; the 58 `NORMATIVE` fixtures are
  untouched and remain blocked on real material.
* **`C-12` remains registered and open**, and is treated as blocking nothing.

Recorded in [IMPLEMENTATION_STATUS.md](../../00-project/IMPLEMENTATION_STATUS.md) as
`F-6`. If §4 is approved it becomes a lock record appended to `all_lock.md` by the owner,
after which the implementation is a change to one function plus the list-scope query that
mirrors it.

---

## 7 · Outcome — `REC-09`, and one consequence worth deciding

**§4 was approved verbatim and locked as `REC-09`.** `G1` was not, and stays deferred.

Implemented, and no more than this:

```text
security/authorization.py   `review_in_legal_scope` + a third branch in
                            `can_see_review`, permission before scope
api/routers/reviews.py      `_visible_reviews` mirrors it — the same locked
                            rule in two places, with a test asserting they
                            cannot disagree (49.6)
```

No new permission, endpoint, table or schema change. 15 tests: 10 object-scope, 4 over
HTTP, and one browser spec — `frontend/e2e/legal-access.spec.ts` — which is the only one
that could have caught `F-6` in the first place, because a browser cannot insert a
`review_assignments` row.

Two of the existing tests changed, and both changes are the point rather than noise:

* `test_legal_reviewer_needs_assignment` still passes untouched — the Review it uses is
  `DRAFT` with no escalation, so it is in no Legal scope, and role name alone still
  grants nothing (r12).
* `gating.spec.ts`'s out-of-scope 404 test had used an *analysed* Review, which `REC-09`
  correctly makes visible to Legal. Its fixture is now a `DRAFT` Review, so it still
  tests `SEC-07` non-disclosure rather than testing the old gap.

### The consequence: Legal scope ends at resolution

When a Legal Decision resolves the last outstanding Evaluation, `_advance_if_resolved`
moves the Review `LEGAL_REVIEW → RESOLVED` (Step 30 r7/r16) — and a `RESOLVED` Review
with no active escalation is **no longer in Legal scope**. So the Legal Reviewer who has
just decided immediately loses sight of the Review, including the decision chain they
authored.

This is `REC-09` behaving exactly as approved, and it is faithful to locked Step 24 r18:
*"a resolved Review remains accessible to its owner according to the same ownership
rules, while Legal access remains governed by Legal scope/assignment."* The owner keeps
access; Legal access is governed by scope, and the scope has ended.

It is **asserted, not worked around** — `test_legal_scope_ends_when_the_review_resolves`
and the browser spec both pin it. Widening the definition to keep Legal in sight after
resolution would exceed what was approved, so it is reported instead. If the owner wants
Legal to retain sight of Reviews it decided, that is a further narrow decision, and the
three candidate criteria are:

```text
(c) the caller recorded a Legal Decision in the Review's chain
(d) the Review was in Legal scope within some retention window
(e) accept as-is — a resolved Review is business-owned history, and
    audit access (audit.view) is the route for reviewing past decisions
```

No recommendation is offered here; each has a different disclosure profile, and this
document decides nothing.
