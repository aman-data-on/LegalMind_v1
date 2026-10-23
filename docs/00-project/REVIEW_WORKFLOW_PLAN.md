# The review workflow — research report and plan

**Status: 📁 PROPOSAL → APPROVED by the owner 2026-10-22** (plan approved; implementation in
progress on branch `research/review-workflow-20261022`, started from `2f433e5` = PR #228).
This document decides nothing by itself: the lock amendments it names land as AB-103 in
`all_lock.md`. Build state lives in IMPLEMENTATION_STATUS.md.

## How the evidence was gathered

* **Repository audit** — six read-only code audits (lifecycle, folding, concurrency,
  migrations, test harnesses, lock text), every claim cited file:line below.
* **Real-browser walkthrough** on an isolated scratch stack (owner sends → reviewer decides a
  mix → all decided → contract decided → closed), both roles, screenshots kept outside the
  repository.
* **Two adversarial reviews** of this plan (28 findings), all resolved in the text below.
* **External research** (marked as external, not repository fact):
  - Juro — "Approving the document completes the approval process: the document is now ready
    to be sent for signing" — https://intercom.help/juro/en/articles/5653139-handling-approvals ;
    statuses differ by viewer ("To approve" vs "Sent for approval") —
    https://intercom.help/juro/en/articles/5653189-contract-statuses-in-juro
  - Workday Evisort — per-issue Accept / Reject / Modify, accept applies a tracked redline —
    https://doc.workday.com/evisort/en-us/contract-management-and-document-intelligence/workflow/workflow-tickets/review-documents-with-ai-playbooks.html
  - Harvey — clause labels acceptable / needs review / unacceptable, and a status panel of
    assigned / verified / flagged — https://www.harvey.ai/blog/harvey-in-practice-build-and-run-playbooks-in-word
  - Ironclad — an Approver gates the Sign step (help-centre excerpts; the page returned 403).
  - Not found in any product: a progress counter like "8 of 14 resolved" (rare), "on hold".
  Common pattern: the AI label per clause and the human workflow on the contract are two
  separate layers; a review ends with an approval, not with "all labels green".

## Context

**What the owner asked (2026-10-22):**

- "I accept something and reject a lot, but how does the review end?"
- The attached brief: research → break tests → fix Summary and Findings/Document plus their backend → verify → self-critique.
- Two adversarial reviews of this plan (28 findings, all resolved below).
- Standing authority: *"if any locked decision is not right, review and update it as an enterprise would"* — amend with an appended record and report it.

**Owner rulings (2026-10-22):**

| # | Ruling |
|---|---|
| O1 | A late change that needs work **reopens** the review |
| O2 | An owner holding `legal.decision` **may** decide their own points (AM-170 stays an assignment rule) |
| O3 | Deleting a contract **removes** its decisions and contract decisions (as AM-55 r3 already says) |
| O4 | One click on a card decides **every requirement and scope on it, listed before confirm**; one decision per item, same reason; items already decided are **skipped** |
| O5 | Reopen triggers: becomes *Ask the client to clarify*, is escalated, or changes to *Change needed* / *Must change*. A change to Accept / Not applicable / Approve customised does **not** reopen; it refreshes the suggestion only |
| O6 | v1 stays decidable until v2 has a **completed** analysis; then v1 is read-only history |
| O7 | Retry = **optimistic concurrency, stated as such**: a duplicate is refused (409) and the screen says "Your decision was already recorded". There is no idempotency key |

**Scope:**

- In scope: Summary, Findings/Document, and their backend.
- Not touched: Ask, production, deploy.
- No commit/push/PR until the owner says so; each phase is saved as a `git diff` patch in the scratchpad.

**Branch:** `research/review-workflow-20261022`, worktree `/root/legalmind-worktrees/review-workflow-research-20261022`, from PR #228 @ `2f433e5`.

## Root causes (verified, file:line)

| # | Cause | Evidence |
|---|---|---|
| R1 | Summary/Findings/Document numbers read classification, never review state | `AnalysisPanel.tsx` `statusCounts`; `findingLanguage.ts:341`; `serializers.py:197` |
| R2 | Recommendation and Open points ignore decisions | `api/angles.py:574,657,720` |
| R3 | Angles cached in a module Map, never invalidated | `Angles.tsx:19-40` |
| R4 | Three different "needs a decision" sets; angle MUST_CHANGE vs NEEDS_DECISION | `user_status.py`; `serializers.py:192`; `reporting.py:122`; `angles.py:390` |
| R5 | OPEN (no decision required) counted as open forever | `evaluation/workflow.py:192`; `FindingsPane.tsx:99` |
| R6 | Three fold rules. The frontend key includes `requires_decision` and `nextStep`, so groups break apart when one member is decided. The backend omits `nextStep`, and `/angles` doesn't fold | `findingLanguage.ts:170-187,424-426`; `user_status.py:150-155,224-234`; `angles.py:678-688` |
| R7 | Document colours contradict the tiles and ignore decisions | `model.ts:680`; `DocumentPane.tsx:73` |
| R8 | The owner sees no decision; "Decided" never says what | `FindingsPane.tsx` card |
| R9 | Ambiguous decision words | `labels.ts` |
| R10 | No write-time completion. Decisions and escalations are accepted on RESOLVED/CLOSED reviews with no way back, and an outcome is accepted while a clarification is pending | `workflow/decisions.py:54-158`; `escalation.py:32-106`; `review_lifecycle.py:45-46`; `contract_outcome.py:69` |
| R11 | Contract hard delete likely fails once a decision exists: the trigger has no cascade exemption | `80dccb65:424-437`; `contracts.py:511-535` |
| R12 | `Finding.status` is stored and recomputed only for the touched finding, with inconsistent `requirement_required` | `models.py:573`; `analysis/service.py:1396`; `decisions.py:140` |
| R13 | `expected_version` optional, so a duplicate appends; full `db.rollback()` on a clash | `schemas.py:389,401`; `decisions.py:114-122`; `contract_outcome.py:84-86` |
| R14 | v1 stays actionable after v2; v2 failures are silent; "latest" = max `version_number` whatever its status; two reviews per version are possible | `contracts.py:249-257,624-723`; `analysisChain.ts:40`; `models.py:546-552` |
| R15 | Decision audit lacks review/finding/version (JSON only; there are no columns) | `decisions.py:128-136`; `models.py:836-856` |
| R16 | Misleading "another user" message on your own retry; ContractDecision disappears when its re-fetch fails; hook-order bug | `DecisionControl.tsx:60-72,111`; `ContractDecision.tsx:73-75` |
| R17 | Decisions accepted on an **archived** contract | `deps.py:273-279` (`_refuse_archived` only at `:270,297,321`) |
| R18 | Out of scope, accepted risk: Dashboard bucket, "Analysis completed" label, Legal queue mixing versions | `contracts.py:71-82`; `dashboard/page.tsx:1288`; `legal/page.tsx:64-77,178-180` |

## Lock amendments — AB-103 (appended record; registry, DECISION_STATE_MODEL, CHANGELOG, CLAUDE.md count)

Every amendment cites the exact text it changes.

| ID | Amends (quoted) | New rule | Enforcement point |
|---|---|---|---|
| AM-175 | Step 30 r2 "Review status follows a controlled state machine" (`all_lock.md:2700`): adds edges RESOLVED→LEGAL_REVIEW and CLOSED→LEGAL_REVIEW | **Reopen (O1, O5).** Triggers: a decision of type REQUEST_CLARIFICATION, REQUIRE_COMPANY_STANDARD or REJECT on a point of a RESOLVED/CLOSED review, or an escalation raised. Effect: status → LEGAL_REVIEW, `reviews.reopened_at` set (a **new nullable column**), audited `review.reopened` with the cause. The contract decision on record is no longer current: the stage reads from `reopened_at > latest outcome.created_at`; nothing is deleted. **Precedence:** superseded version → 409, archived → 409, then reopen. | `review_lifecycle.reopen()` called from `record_decision` and `escalate_finding` in the same transaction |
| AM-176 | AM-12 "Prior rows are never updated and never deleted" (`:13982-13990`), as amended for contract deletion by AM-55 r3 (`:18220-18223`) | `legalmind_append_only()` allows DELETE **only from a cascade** (`pg_trigger_depth() > 1`). Applied to `legal_decisions` and the new `contract_outcomes` trigger. Direct UPDATE/DELETE stays refused. Caveat declared: a DELETE issued by another trigger also passes; no such trigger exists. Downgrade restores the old function (cascades then fail again) — written in the migration. | DB trigger; tests prove a cascade passes and a direct DELETE fails |
| AM-177 | Step 49 decision concurrency (STEP_49 doc `:216-217`; `all_lock.md:14684-14688`) | `expected_version` **required** on both decision write endpoints; clashes caught in a savepoint (no full rollback). **Stated as optimistic concurrency, not idempotency (O7).** | Pydantic schema; savepoint in `record_decision` and `contract_outcome.record` |
| AM-178 | AM-174 r3 "Only once every required point is decided (Review RESOLVED or CLOSED)" (`:25636-25638`) | The contract decision needs `all_required_decisions_complete()` **at write time**. Every decision, outcome and escalation write refuses (409) on an **archived** contract, and on a review whose version is **superseded**. Superseded = a newer version with a **completed** analysis exists (O6); "the review" of a version = its newest review. | `contract_outcome.record`, `record_decision`, `escalate_finding`; a shared `latest_analysed_version()` helper |
| AM-179 | AB-1.1 "A Legal Decision resolves exactly one Evaluation and never implicitly disposes of another" (`:13980`, `:14366-14367`); Step 31 r4 "ACCEPT_DEVIATION applies only to the specific Review/Finding" (`:2825`) | **Group decision (O4).** A *point* = a server fold group keyed on fields that **don't change with decisions**: the sorted evidence set, the requirement title, the classification, the actual value, the expected value. One request decides a **named list** of evaluation ids. The server checks that they belong to the group, records one Legal Decision per evaluation (AB-1.1's row model kept; disposal is **explicit, never implicit**) and skips already-decided ones. It is **all-or-nothing**: any 409 aborts the whole group. A member needing second-person approval (r15) is excluded and shown separately. Plus the **review stage** vocabulary (non-axis, own field `review_stage`). | `POST /reviews/{id}/decisions` with `{evaluation_ids, decision_type, justification, expected_versions}`, in one transaction |

Unchanged and satisfied: AM-170 (O2), D-3.6, Step 31 r14/r19/r20 (one row per evaluation, append-only, audited), AM-55.

**New column:** `reviews.reopened_at` (nullable) in migration `d…` with the trigger change. It is the only schema change besides the trigger. The schema tests are updated (table count unchanged; columns +1).

## Definitions

**Decision words** (stored values unchanged):

| Stored | Shown | After | Reopens a finished review? |
|---|---|---|---|
| ACCEPT_DEVIATION | Accept as an exception (this contract only) | Decided — accepted as exception | no |
| REQUIRE_COMPANY_STANDARD | Change needed — send our wording | Decided — change requested (re-checked on the revised version) | **yes** |
| REJECT | Not acceptable — must change (this clause) | Decided — must change | **yes** |
| APPROVE_CUSTOMIZATION | Approve a customised clause | Decided — customised clause approved | no |
| NOT_APPLICABLE_TO_CONTRACT | Not applicable to this contract | Decided — not applicable | no |
| REQUEST_CLARIFICATION | Ask the client to clarify | Awaiting clarification | **yes** |

**Review stage** (`review_stage`, from `review_progress()`). The **first match wins**, in this order:

1. Superseded by version N
2. Analysing
3. Analysis failed
4. Waiting for clarification
5. Reopened — n of m decided (`reopened_at` after the last outcome)
6. With Legal — n of m decided / Not sent for review (when there is no assignment and no Legal scope)
7. Points decided — contract decision pending (RESOLVED; no current outcome, or On hold)
8. Review complete — <outcome> (CLOSED)
9. No issues found

Each stage names who acts next. Review complete ≠ approved to sign.

**Counts** are per **point**. "n of m decided" counts a point as decided only when every evaluation in it is decided. The report is generated on read (`export.py:60-109`); nothing that embeds counts is persisted.

## Break tests — red first (`backend/tests/test_review_workflow_breaks.py`, `frontend/e2e/review-workflow.spec.ts`)

Each test has two parts:

- **(a)** existing behaviour that must fail now, failing for an **assertion** reason (no 404, no collection error);
- **(b)** new-API assertions marked `xfail(strict=True)`.

Expected values come from the rule, written **before** running the code. Counts are compared with an **independent recompute** from `legal_decisions` + `evaluations`.

| # | Fixture | (a) red today | (b) new |
|---|---|---|---|
| T1 | 5 points: accept 1, change 2, reject 1, clarify 1. Then a late REQUEST_CLARIFICATION on CLOSED, a late Accept on CLOSED, and an escalation on RESOLVED | an outcome while clarifying is accepted today → assert 422; late clarify on CLOSED → assert review LEGAL_REVIEW (today CLOSED); late Accept on CLOSED → assert still CLOSED; escalation on RESOLVED → assert LEGAL_REVIEW | stage, `reopened_at`, counts == recompute |
| T2 | full `FIXED_TERM_EXIT` + 20.1 (30 days); a no-fee variant | **rule-derived:** two values in one scope → CONFLICT (`numeric.py:172-176`, 45B) citing 13.1 and 20.1 with pages; related = 13.2 + 13.3; ₹ == fee × term; no-fee → `commercial.missing`, no ₹; the action is never Accept for a conflict | the point counted once |
| T3 | one MSA review: a KYC-verification clause + a 6-month cap | no KYC MISSING; KYC UNABLE/APPLICABILITY_UNCERTAIN **and** the cap DEVIATION in the **same** review (the new combination) | "Legal to confirm" on the point |
| T4 | owner (USER), owner with `legal.decision` (allowed), assigned reviewer, unrelated user, other department, revoked assignee on ANALYSIS_COMPLETE (404) / LEGAL_REVIEW (200, REC-09); an archived contract | **deleting a contract with a decision** — run in `db.begin_nested()`; assert it succeeds (today it raises); a decision on an archived contract → 409 (today 201); direct DELETE of a decision is still refused | audit `after_state` has `review_id`/`finding_id`/`document_version_id` |
| T5 | v1 analysed + partly decided → v2 uploaded (pending) → a decision on v1 allowed → v2 analysed → a decision on v1; a POST without `expected_version`; a stale `expected_version` | after v2 completes, a v1 decision → 409 (today 201); without `expected_version` → 422 (today appends); a pending v2 does **not** block v1 | v1 stage "Superseded by version 2"; v2 counts == recompute |
| T6 | two requirements on one clause (the same 6-month cap via two standards); one member pre-decided | e2e (red today): decide the card → the hidden requirement **reappears as open** | backend group endpoint: decides the named, undecided items only, skips the decided one, all-or-nothing on a 409; group stable after the decision |

Every test isolates DB exceptions in `begin_nested()` (`conftest.py:321` re-raises server exceptions).

**Browser checks** (Playwright; failures via `page.route` — Vitest has no DOM):

- owner sends → mixed decisions → clarify → close → late clarify reopens;
- the Summary stage, counts and next person == the Findings chips/filters == the Document legend at each step;
- a 409/403/network failure shows an error and no success; your own retry shows "already recorded";
- the group confirm lists its items;
- 390 / 768 / 1440 px.

`tools.e2e_bootstrap` adds a second, changed fixture document for v2.

## Fixes, in order (patch saved per phase; tests re-run after each)

1. **Research report:** rewrite `docs/00-project/REVIEW_WORKFLOW_PLAN.md` (the branch copy is the old proposal) into the brief's deliverable.
2. **Baseline:** write T1–T6; run; record the red/xfail map and the commands.
3. **Migration:**
   - cascade-aware `legalmind_append_only()`;
   - trigger on `contract_outcomes`;
   - `reviews.reopened_at`;
   - a downgrade note.
4. **Workflow:**
   - `review_lifecycle.reopen()` (AM-175);
   - write-time guards: completion, archived, superseded via `latest_analysed_version()` (AM-178);
   - `expected_version` required + savepoints (AM-177);
   - a single-query recompute of every finding's stored status after any write (one query gathers each evaluation's current decision, then derive in memory; about 2 queries per write instead of ~75), with consistent `requirement_required` (R12);
   - audit JSON fields (R15).
5. **Folding + group decisions (AM-179):**
   - `evaluation/folding.py` with a stable key;
   - `group_id` on findings, `/angles` items, `folded_user_status_counts`;
   - `POST /reviews/{id}/decisions`;
   - the frontend uses `group_id`.
6. **`review_progress()`**, `GET /reviews/{id}/progress`, and the report field.
7. **Angles:** decision-aware recommendation and items; frontend cache cleared on reload.
8. **Summary**, top to bottom:
   1. stage + progress + next person;
   2. contract decision;
   3. "what was decided";
   4. Open points (undecided only);
   5. Money;
   6. "Our analysis" tiles, secondary;
   7. empty / loading / failed states.
9. **Findings/Document:**
   - the brief's card hierarchy; one decision-state chip; the analysis word on one line;
   - the decision line for everyone who can see the card;
   - the group Decide with a confirm list;
   - each choice says what it does;
   - filters: To decide · Clarification · Decided · Matches · All;
   - document marks follow the decisions; colours aligned;
   - error honesty (R16).
10. **Records:** AB-103 (prefix byte check), LOCKED_DECISIONS, DECISION_STATE_MODEL (the `review_stage` vocabulary), CHANGELOG, IMPLEMENTATION_STATUS, PROJECT_STATE, CLAUDE.md count. OpenAPI regenerated.

**Accepted risk, reported:** R18 (Dashboard/Legal queue) stays inconsistent until a follow-up; each fix is one field once `review_stage` exists.

## Verification

- **pytest:** T1–T6 (baseline → after), `test_review_assignment.py`, `legal_regression/`, `test_api_*`, `test_authorization.py`, `test_workflow_decisions.py`, `test_schema_invariants.py`, `test_locked_schema_columns.py`, `test_contract_archive.py`, `test_observability.py`; ruff + mypy.
- **Vitest:** full run, plus pure components (chips, stage line, form copy, the group confirm list; no "Acceptable" on any decided card).
- **Playwright** locally (scratch stack), then CI: `review-workflow.spec.ts`, plus the decision, escalation, legal-access, reviews, journey, keyboard, legal-area and workspace specs.
- **Screens and accessibility:** 390 / 768 / 1440 screenshots per stage; keyboard (`d`, Tab, focus after a decision); labels; contrast.
- Every command is reported as passed / failed / not run, with output. Scratch DB and test DB only.

## Self-critique carried forward

- The reopen touches Step 30. Every cell of the matrix (O5 × RESOLVED / On hold / CLOSED / archived / superseded) has a test.
- The cascade exemption is proven both ways by tests; the trigger-to-trigger caveat is declared.
- Group decisions keep one row per evaluation, explicit, all-or-nothing, with the confirm step naming every item.
- `expected_version` required may break a client that omits it. The frontend always sends it (`DecisionControl.tsx:104`, `ContractDecision.tsx:67`).
- The sixth test (T6) and the five amendments go beyond the brief. They are owner-ruled (O1–O7) and listed in the report.
