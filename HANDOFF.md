# LegalMind V1 — Handoff for final review

**Prepared 2026-08-18.** The locked build sequence is complete and the project is in
**stabilization**. This document is the entry point: it states what exists, how to
verify it yourself, what is honestly *not* done, every decision still yours, and the
exact material required before the remaining work can start.

It asserts no build state of its own — [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)
is the only document permitted to do that, and this one links to it rather than
restating it. Where a number appears here it was measured on 2026-08-18, not remembered.

---

## 1 · Where the build stands

Every step of the locked Gate §5 implementation sequence is implemented. **One unit is
not complete, and it is blocked on you** rather than on engineering:

```text
1  Schema + migrations          IMPLEMENTED · TESTED
2  Auth + session + RBAC        IMPLEMENTED · TESTED
3  Domain + repositories        IMPLEMENTED · TESTED
4  Document ingestion           IMPLEMENTED · TESTED
5  Mapping engine               IMPLEMENTED · TESTED
6  Evaluators                   IMPLEMENTED · TESTED   LIABILITY-001 + PRESENCE
7  Findings/Evaluations/Decisions IMPLEMENTED · TESTED
8  API surface                  IMPLEMENTED · TESTED   39 endpoints
9  Golden corpus harness        PARTIAL  ← runner complete, fixtures blocked
10 Frontend                     IMPLEMENTED · TESTED   10 of 10 locked screens but export
11 Observability (Step 53)      IMPLEMENTED · TESTED
12 Deployment (Step 55)         IMPLEMENTED · TESTED   as far as the specification allows
```

Measured surface: **29 tables · 39 mapped endpoints · 27 permissions** — each unchanged
from what the locked specification fixes, with no addition.

**Nothing is `VERIFIED` and nothing is production-ready.** `TESTED` means automated tests
exist and pass; §3 says exactly what that does and does not establish.

---

## 2 · Verifying it yourself

Everything below runs from a clean checkout. Expected results are stated so a difference
is visible rather than interpretable.

```bash
# Backend — 508 tests
cd backend && python3 -m pytest tests/ -q

# Lint and types — both at zero, and CI job 1 is blocking on them
ruff check . && mypy

# Frontend — 53 Vitest tests, clean typecheck
cd ../frontend && npx vitest run && npx tsc --noEmit

# Browser workflows — 22 tests (26 runner items, including 4 setup steps)
npx playwright test

# Migrations round-trip
cd ../backend && python3 -m alembic downgrade base && python3 -m alembic upgrade head

# The two independent passes (throwaway databases; the second needs Redis)
python3 -m tools.verify_reproducibility          # 55.4 r3 / 55.5 release gate
python3 -m tools.verify_invariants               # 12 checks by other mechanisms

# What a production deployment still owes
python3 -m legalmind.deploy.preflight            # 18 checks; expect NOT READY
```

CI runs all of it in **12 jobs**; `main` is protected on job 3, which locked Step 54
makes release-blocking. Branch protection is yours and was not touched.

---

## 3 · Verification evidence, and its limits

Three tiers, deliberately distinguished.

**Tests (508 + 53 + 22).** They assert what the code does against what the specification
says, and they run under concurrency: four simultaneous full suites pass, which is the
property `F-4` was fixed to guarantee.

**Independent verification (12 checks, all PASS).** Each critical guarantee re-checked by
a mechanism that is *not* the test asserting it — raw SQL outside the ORM for EV-MIN and
append-only, two live schemas for the enum-scoping fix, real worker processes and a real
`SIGKILL` for the queue, a grep of 188 real log lines for 53.3, two OS processes under a
hostile locale for `ENG-11`, and a real migration round trip for 55.4 r3. Recorded in
[INDEPENDENT_VERIFICATION.md](docs/08-testing/INDEPENDENT_VERIFICATION.md).

It has found **six defects a green suite could not**, which is the argument for keeping
it: `acks_late` set while crash recovery was an hour away; a worker silently consuming
nothing; a database error writing contract text into an operational log; Alembic
switching application logging off; an enum test that passed alone and failed beside a
sibling; and `F-6`, where a Legal Reviewer could reach no Review at all.

**What is NOT verified — and this is the important line.** Locked `IMPL-01` condition 2:
*conformance is verified against the locked corpus, not asserted by the implementation.*
That corpus is **16 `STRUCTURAL` fixtures and 0 `NORMATIVE`**. Structural fixtures verify
the algorithm; they assert nothing about whether it reaches **your** legal conclusions.
No amount of the above substitutes for that, and none of it is third-party verification.

---

## 4 · Known limitations

Stated as limitations, not as work in progress.

| | |
|---|---|
| **No normative conformance** | 0 of 58 `NORMATIVE` fixtures. The release gate of 54.7 cannot be met until they exist |
| **No calibration** | Mapping weights and `confirm_threshold` are uncalibrated; locked 35.10 requires validation against a representative contract set. Every threshold in the tree today is `STRUCTURAL` |
| **`MappingState.AMBIGUOUS` is never produced** | A consequence of your `M-2` decision, recorded rather than hidden. Cross-Requirement ambiguity detection is unimplemented and no producer was invented |
| **OIDC is not implemented** | Locked 47.1.3 makes it primary; only the password fallback exists. Needs an approved JWT/JWKS dependency and provider configuration |
| **Export is not implemented** | Locked 49.12 records export formats as NOT YET SPECIFIED, so the route is absent rather than dishonest |
| **Legal loses sight of a Review at resolution** | Under `REC-09`, a resolved Review with no active escalation leaves Legal scope — so the reviewer who just decided can no longer see it. Faithful to Step 24 r18, pinned by two tests, and a candidate for a further narrow decision (§6) |
| **Legal cannot reach Contracts or Documents** | `REC-09` governs Reviews, Findings and Evaluations. Whether Legal scope extends to the underlying Contract or to downloading the original document is explicitly not decided |
| **Per-user Legal assignment does not exist** | `G1`, deferred to V2 by `REC-09`. `review_assignments` stays ratified and unpopulated |
| **Analysis is inline unless a broker is configured** | Correct behaviour, and the preflight fails a production deployment configured that way rather than letting it pass |
| **Rate limiting is in-process** | Correct for one worker. A multi-worker deployment needs the shared Redis, and 55.2 also requires limiting at the edge |
| **No retention policy** | Locked 41.26 defers it. Log expiry must never remove auditable history (53.6), so the two stores are already separate — but the policy itself is yours |

---

## 5 · Decisions still yours — reported, not resolved

Nothing in this section was decided, worked around, or quietly implemented.

### 5.1 · Pending ratification (8)

`IMPL-01` condition 4 leaves these unratified. Each is implemented as described and open
to revision without amending anything. Full table in
[IMPLEMENTATION_STATUS.md § Pending ratification](docs/00-project/IMPLEMENTATION_STATUS.md).

```text
D-1  absent confirm_threshold refuses at publish time
D-2  Mapping State persisted in evaluations.result.evaluated_facts
D-3  Requirement applicability from the Company Standard, failing closed to REQUIRED
D-4  the orchestrator writes no UNMATCHED_PROVISION rows
M-2  tied supporting clauses are CONFIRMED; contradiction is the evaluator's business
tie_margin              audited unused; retained pending your review
analyze-endpoint permission   mapped to review.create (49.3 has no analysis row)
second-person approval  co-signature within the append-only decision chain
```

### 5.2 · Open conflicts (6)

Registered in [CONFLICTS.md](docs/00-project/CONFLICTS.md), none resolved here.

```text
C-05  stale 45A status block                       clerical
C-06  two "Step 29" sections                       low
C-07  superseded draft lists                       informational
C-08  Reviewer role authority                      low
C-10  roles seed list (42.2) vs Step 23 matrix      MEDIUM
C-12  Step 39 names Playwright vs 54.7 "framework  low — blocks nothing;
      selection NOT YET SPECIFIED"                  both readings permit it
```

### 5.3 · Open decisions (14)

The security track's `OD-1`–`OD-15` less `OD-9`, which Step 47 closed. Tracked in
[EXTERNAL_REFERENCE_AUDIT.md](docs/00-project/EXTERNAL_REFERENCE_AUDIT.md) §16.

### 5.4 · NOT YET SPECIFIED, reported rather than assumed

The preflight's own words. Of 18 checks: **6 PASS, 3 FAIL, 7 ATTEST, 2 BLOCKED**.

```text
BLOCKED  oidc                 locked primary mechanism, unimplemented (47.1.3)
BLOCKED  retention_policy     locked 41.26 defers it — your decision

ATTEST   tls                  terminates at the proxy; unobservable from here
ATTEST   encrypted_storage    a platform property
ATTEST   safe_parsing         container-level; NO parse cap was invented
ATTEST   rate_limiting        in-process; the edge cannot be checked from here
ATTEST   malware_scanning     55.6 requires the decision recorded either way
ATTEST   backup_restore       "restore is verified, not assumed"
ATTEST   reproducibility_gate a release-pipeline act, not a start-up check

FAIL     secrets              no injected LEGALMIND_DATABASE_URL   ← deployment
FAIL     analysis_worker      no LEGALMIND_BROKER_URL              ← deployment
FAIL     database_roles       the dev role holds DDL rights        ← deployment
```

The three `FAIL`s are **development-environment facts, not defects**: each becomes a
`PASS` in a deployment that injects secrets, configures the broker, and runs the
application under a role without DDL rights. `ATTEST` and `BLOCKED` are deliberately not
passes — an unexamined blocker is not a satisfied one.

### 5.5 · A candidate decision, offered and not taken

Under `REC-09`, Legal loses access to a Review the moment its last Evaluation is decided.
Three candidate criteria are set out in
[LEGAL_ACCESS_GAP.md](docs/06-security/EDGE_CASES/LEGAL_ACCESS_GAP.md) §7 with no
recommendation, because each has a different disclosure profile. Doing nothing is a
coherent choice: it is what Step 24 r18 says as written.

---

## 6 · What I need from you

Two pieces of work are blocked, and both are blocked on the same material. Locked 54.6 is
the reason it cannot be improvised: *"golden fixtures use synthetic or cleared contract
text. Real counterparty contracts do not enter the repository."*

### 6.1 · To author the 58 `NORMATIVE` fixtures (Step 45E) and calibrate Step 35

```text
1  Representative contracts       3–10 documents of the kind you actually review
                                  (MSAs, DPAs, or equivalent), PDF or DOCX.
                                  CLEARED or SYNTHETIC — 54.6 bars real
                                  counterparty documents from the repository, so
                                  we must also agree where they live if they
                                  cannot be committed.

2  LIABILITY-001's Company        the preferred cap value, its unit, its basis,
   Standard                       and the scope it applies to. This is the
                                  organization's position, not an example.

3  LIABILITY-001's Legal Rule     the acceptable maximum, the value above which
                                  approval is required, how UNLIMITED is treated,
                                  and which carve-out scopes are comparable.

4  Extraction terminology         the cap phrases, unlimited phrases, unit names,
                                  basis names and carve-out terms as they appear
                                  in your documents. Everything in the tree today
                                  is STRUCTURAL placeholder text.

5  Requirement applicability      which Requirements are REQUIRED and which are
                                  OPTIONAL (D-3 reads this from configuration and
                                  fails closed to REQUIRED).
```

Locked 54.6 also notes that the corpus contract set and the Step 35 calibration set are
**the same set** — one gathering exercise, two consumers.

### 6.2 · To make a deployment possible

```text
OIDC          issuer, client id, client secret — and approval for the JWT/JWKS
              dependency, which is outside the Step 39 stack (rule 19)
Retention     the policy itself (locked 41.26 defers it)
Export        the formats (locked 49.12 records them NOT YET SPECIFIED)
Malware       "available" or "explicitly accepted as absent" — 55.6 requires the
              decision recorded either way
Infrastructure  injected secrets, a broker, an application DB role without DDL
```

### 6.3 · Decisions that would unblock nothing but would settle the record

The eight pending-ratification items, the six conflicts (C-10 is the one with real
consequences), and `REC-09`'s resolution-visibility question.

---

## 7 · Guardrails a reviewer should expect me to have kept

```text
all_lock.md          APPEND-ONLY, 15,358 lines. Two records appended this
                     cycle (REC-08, REC-09), each with the prior lines verified
                     byte-identical. CI job 6 enforces it on every PR.
No invented material No threshold, cap value, clause, Company Standard, legal
                     position or normative expected output was authored. CI job 8
                     rejects contract file types and unsourced NORMATIVE fixtures.
No unapproved change No permission added (27, as locked), no endpoint added, no
                     table or column added, no architectural boundary moved.
Gaps reported        F-6 and C-12 were registered and surfaced rather than
                     resolved; G1 was left deferred; the corpus was left blocked.
```

Where the specification and the implementation disagree, the specification wins —
`IMPL-01` condition 1: *the code is not a specification.*

---

## 8 · Where to read next

| Question | Document |
|---|---|
| What state is everything in? | [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) — the only document that may assert build state |
| What is locked, and where? | [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) → `all_lock.md` for exact text |
| What is contradictory? | [CONFLICTS.md](docs/00-project/CONFLICTS.md) |
| How was it verified? | [INDEPENDENT_VERIFICATION.md](docs/08-testing/INDEPENDENT_VERIFICATION.md) |
| Why can a Legal Reviewer see a Review? | [LEGAL_ACCESS_GAP.md](docs/06-security/EDGE_CASES/LEGAL_ACCESS_GAP.md) + `REC-09` |
| How does the code work? | [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md) |
| What changed and when? | [CHANGELOG.md](CHANGELOG.md) |
| How do I work in this repository? | [CLAUDE.md](CLAUDE.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
