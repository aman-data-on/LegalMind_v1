# LegalMind V1 — Handoff for final review

**Prepared 2026-08-18.** The locked build sequence is complete and the project is in
**stabilization**. This document is the entry point: it states what exists, how to
verify it yourself, what is honestly *not* done, every decision still yours, and the
exact material required before the remaining work can start.

It asserts no build state of its own — [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)
is the only document permitted to do that, and this one links to it rather than
restating it. Where a number appears here it was measured on 2026-08-18, not remembered.

> ⚠️ **This document is a point-in-time review pack, dated 2026-08-18. It is not the
> day-to-day status page.** Work has continued since — AB-3 and AB-4 are locked, and the
> assist lane is under construction — so figures below are as measured on that date and
> several have moved.
>
> **For where the project stands now, read
> [docs/00-project/LEGALMIND_PROJECT_STATE.md](docs/00-project/LEGALMIND_PROJECT_STATE.md)**
> (plain language, with a "Picking up where we left off" block at the top) and
> [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) for build state.
> This pack is kept as the record of the V1 stabilization review, not superseded by it.

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
9  Golden corpus harness        PARTIAL  ← runner complete; 28 of 64 fixtures,
                                          normative authoring blocked on you
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
# Backend — 781 tests, none skipped (as of 2026-08-25)
cd backend && python3 -m pytest tests/ -q

# Lint and types — both at zero, and CI job 1 is blocking on them
ruff check . && mypy

# Frontend — 58 Vitest tests, clean typecheck
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

**Tests (626 + 53 + 22).** They assert what the code does against what the specification
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
That corpus is **28 fixtures — 16 `STRUCTURAL`, 9 `DOCUMENT_SUPPORTED`, 3
`STANDARD_DERIVED` — with 0 `NORMATIVE`**. Two fixtures assert `MATCH` against your ratified
standard, so conformance to what your documents *say* is partly established.

**Conformance to what you will *accept* is not established at all.** No fixture asserts any
Rule Outcome but `NOT_APPLICABLE`, because no Legal Rule exists — so nothing in the
repository says a deviation is acceptable, needs approval, or is unacceptable. Instead every
un-ruled deviation is routed to a human, which is fail-closed and correct but is *not*
conformance. That gap stays open until a Legal Rule is approved, and none of this is
third-party verification.

---

## 4 · Known limitations

Stated as limitations, not as work in progress.

| | |
|---|---|
| **No normative conformance** | 0 `NORMATIVE` fixtures. 15 of the 64 specified cases are authored and 4 partly, but every case needing an **acceptance policy** is blocked; 54.7's release gate cannot be met until they exist. Per-case status: `backend/tests/corpus_coverage.json` |
| **Every deviation needs a Legal Decision** | A consequence of there being no Legal Rule, not a defect. `UNRULED_DEVIATION_REQUIRES_DECISION` routes `DEVIATION` + `NOT_APPLICABLE` to `DECISION_REQUIRED`, so a Review holding any deviation cannot complete until Legal rules. Expect real review workload before a Legal Rule exists |
| **No calibration** | Mapping weights and `confirm_threshold` are uncalibrated; locked 35.10 requires validation against a representative contract set. Every threshold in the tree today is `STRUCTURAL` |
| **`MappingState.AMBIGUOUS` is never produced** | A consequence of your `M-2` decision, recorded rather than hidden. Cross-Requirement ambiguity detection is unimplemented and no producer was invented |
| **OIDC is not implemented** | Locked 47.1.3 makes it primary; only the password fallback exists. Needs an approved JWT/JWKS dependency and provider configuration |
| **Export is not implemented** | Locked 49.12 records export formats as NOT YET SPECIFIED, so the route is absent rather than dishonest |
| **Legal loses sight of a Review at resolution** | Under `REC-09`, a resolved Review with no active escalation leaves Legal scope — so the reviewer who just decided can no longer see it. Faithful to Step 24 r18, pinned by two tests, and a candidate for a further narrow decision (§6) |
| **Legal cannot reach Contracts or Documents** | `REC-09` governs Reviews, Findings and Evaluations. Whether Legal scope extends to the underlying Contract or to downloading the original document is explicitly not decided |
| **Per-user Legal assignment does not exist** | `G1`, deferred to V2 by `REC-09`. `review_assignments` stays ratified and unpopulated |
| **Analysis is inline unless a broker is configured** | Correct behaviour, and the preflight fails a production deployment configured that way rather than letting it pass |
| **Rate limiting is in-process** | Correct for one worker. A multi-worker deployment needs the shared Redis, and 55.2 also requires limiting at the edge |
| **A PDF with a broken font map is refused, not read — recovered by OCR where the toolchain exists** | Found 2026-09-03 on a real upload. Extraction detects text that is not language and refuses rather than passing a glyph stream into evidence, the clause list, the index and the evaluator (it had produced 3 MATCH findings against unreadable text). The owner installed `tesseract`/`ocrmypdf` the same day, and the affected real document now recovers by OCR (verified live: FAILED → COMPLETE, 413 segments, 30/30 pages). Without the toolchain the outcome remains an honest refusal |
| **The Original view + deferred background OCR are BUILT AND VERIFIED LOCALLY, not deployed** | 2026-09-03, DD-16 / decisions #289–294. Uploads no longer block ~62s on OCR (measured 0.4s upload, original viewable 0.7s, text ~20s and findings ~30s in the background on the real 30-page document), and the workspace shows the preserved original bytes in the browser's own PDF renderer beside the extracted text. The owner's pre-deployment review then surfaced the real durability gap (a daemon thread dies with its process → stuck PROCESSING), closed the same day (#295): claim-run before work, one-transaction completion including the index, per-version advisory lock, startup reconciliation, 3-attempt cap — proved by `kill -9` mid-OCR + restart and by racing two jobs. All suites green locally (backend 1139 · frontend 191 · browser 74). **Awaiting the owner's explicit approval to deploy** — deploy via `ops/deploy.sh` (API restart is REQUIRED: `assert_analysable`, ingestion, dispatch and the app's startup hook changed; the frontend depends on the new upload semantics) |
| **Two grants existed in code but not in the database** | Found 2026-09-03. `seed_default_grants` skips a role that already holds permissions, so `export.generate` and `contract.delete` never reached roles seeded before those grants were added — Export and Delete worked for `DEVELOPER` only. `backend/tools/reconcile_role_grants.py` fixes it additively and refuses once any `admin.permission_changed` audit event exists. **Not yet applied to any database** — it is a live authorization change and awaits owner approval |
| **Deploying the frontend and the API are separate acts, and the ORDER matters** | Discovered 2026-09-02 by consequence. `schemas.Body` sets `extra="forbid"`, so a frontend that sends a newly-added request field is rejected with a 422 by an API that has not been restarted — Ask returned "The request could not be validated." for every question until `systemctl restart legalmind-api` ran. `scripts/deploy-frontend.sh` restarts only the frontend and nothing in the repository restarts the API. **Now enforced (2026-09-02, #287/#288):** `deploy-frontend.sh` refuses when backend source is newer than the running API process (`LEGALMIND_ALLOW_STALE_API=1` overrides for a deliberate frontend-only deploy), and `ops/deploy.sh` deploys both in dependency order — sanity check, migrations, API restart, health probe, then the staged frontend deploy. `extra="forbid"` is correct and unchanged |
| **The browser suite used to overwrite the live build** | Fixed 2026-09-02 (decision 284) and recorded here because the class of fault recurs: `playwright.config.ts` ran `npx next build` with the default `distDir`, which is the `.next` the live service serves from this same working tree — so a suite run silently 500'd every live stylesheet until the next deploy, while nginx kept answering 200. It now builds into `.next-e2e`, **and the refusal moved inside `next.config.ts` itself (#286)**: every `next build` — npm, npx, a test runner's web server, CI — passes through config resolution, and the config throws before `distDir` is even known when the build targets `.next` while `legalmind-frontend` is active. The npm `prebuild` hook stays as a friendlier first layer |
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

> **A first tranche of six documents was supplied on 2026-08-18 and assessed in
> [SOURCE_MATERIAL_INTAKE.md](docs/00-project/SOURCE_MATERIAL_INTAKE.md).** It satisfies
> item 4 substantially and item 1 partially. A **V1 interim policy** followed on the same
> day — the supplied documents are authoritative for the positions they explicitly state —
> which unblocked `MATCH`/`DEVIATION`. **Item 2 is settled, per document type since
> 2026-08-19 (owner Q3=B)**: `LIABILITY-MSA-001` = 6 months of affected-service fees
> (`MSA.pdf` §17.2) and `LIABILITY-TOS-001` = 12 months of total fees
> (`TOS-leapswitch.pdf` §13 — the 2026-08-18 ratification, value unchanged), both under
> `backend/config/company_standards/`. The corpus stands at **32 fixtures,
> still 0 `NORMATIVE`**. **Item 3 (the Legal Rule / acceptance policy) and item 5 remain
> entirely unsupplied** — the owner has stated no Legal Rule exists, so un-ruled deviations
> are routed to a human rather than dispositioned. That document carries the remaining
> requests and three storage decisions 54.6 requires;
> `backend/tests/corpus_coverage.json` carries per-fixture status for all 64 cases.

### 6.1 · Corpus and calibration — after the rulings of 2026-08-18

**Six questions were settled that day. None is open.**

```text
Company Standard        RATIFIED — 12 months of total fees (ToS 13)
Legal Rule              NONE, and specified as such: un-ruled deviations keep
                        rule_outcome NOT_APPLICABLE and route to a human
Basis comparability     FEES_PAID and FEES_PAID_FOR_AFFECTED_SERVICES stay DISTINCT
Requirement catalogue   liability cap only in V1
MSA 17.2 vs 17.7        one scope, contradictory -> CONFLICT
Source-material path    outside the repository, at an agreed local directory
```

**The Legal Rule is DECIDED (manager ruling, recorded 2026-08-19): zero tolerance.**
MATCH → `ACCEPTABLE`; any DEVIATION → `UNACCEPTABLE` → Legal Decision; no deviation is
ever auto-approved, and there are deliberately no thresholds or tolerance bands. What
remains is *implementation*, not a decision: a small engine addition (`deviation_outcome`
Legal Rule key), after which the three `LEGAL_RULE` corpus cases (L-03, L-08 outcomes)
and the `NORMATIVE` tier become reachable. Routing already conforms — every deviation
reaches a human today.

**Material still outstanding — a second tranche, and it is the one substantial gap.**

Locked 54.6 is the constraint: *"golden fixtures use synthetic or cleared contract text.
Real counterparty contracts do not enter the repository."*

```text
1  The six documents, placed at the agreed path
   /root/Legalmind.v1/legal-docs/ (gitignored)   (LEGALMIND_SOURCE_MATERIAL_DIR)
   Currently empty of documents, so the 7 DOCUMENT_LEVEL_HARNESS cases cannot
   run — cross-reference resolution and parse-corruption normalisation, which
   exercise ingestion rather than the evaluator. The 28 existing fixtures need
   no file present; they were built from clause text quoted in conversation.

2  A SECOND TRANCHE — 14 cases. Cleared or synthetic, per 54.6.
   The six supplied documents contain no specimen of:
     · a cap longer than 12 months                                  (L-03)
     · unlimited-liability wording as a GENERAL position,
       "liability shall not be limited"                (L-04, L-17, L-29a/b)
     · a per-claim cap (L-09) or a per-event cap                     (L-10)
     · a fixed monetary sum rather than a fee multiple               (L-12)
     · a cap restated in materially identical terms                 (L-22)
     · two caps on genuinely different scopes                       (L-05)
     · a six-month cap on TOTAL fees — the ratified standard would
       make this the first real DEVIATION                           (L-01)

   COUNTERPARTY-DRAFTED paper serves better than more Leapswitch-issued paper.
   All six documents you supplied state your own position, so measured against
   your own standard they tend to MATCH — and DEVIATION is what most of the
   45E table exists to test.

3  One scope reading: are SLA service credits within LIABILITY-001's scope?
   The SLAs call credits the "sole and exclusive remedy", which interacts with
   the cap. Unblocks 1 case (L-13). Blocks nothing else.
```

Step 35.10 calibration needs the same set — locked 54.6 notes the corpus set and the
calibration set are one set.

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

### 6.4 · Scope note

Only the six documents you supplied are v1 source material (owner ruling, 2026-08-18).
Other document collections exist elsewhere on this machine; they belong to a different
project and are **not** to be read from, derived from, or used to satisfy the
second-tranche request above.

## 7 · Guardrails a reviewer should expect me to have kept

```text
all_lock.md          APPEND-ONLY, 15,358 lines at the time of this handoff. Two
                     records appended this cycle (REC-08, REC-09), each with the
                     prior lines verified byte-identical. CI job 6 enforces it on
                     every PR.
                     LATER: DOC-06 and DOC-07 were appended on 2026-08-21 (owner
                     decisions on Document Type declaration and multi-document
                     review), taking the file to 15,648 lines. Prior 327,138
                     bytes verified byte-identical by hash before and after.
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
