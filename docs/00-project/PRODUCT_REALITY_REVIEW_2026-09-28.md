# Product Reality Review — 28 September 2026

**Status: 📁 REVIEW RECORD.** This document records the results of a full product-reality
review, not a specification and not a build-state assertion — [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)
remains the only document that may assert build state. Where this review found that
document's own bookkeeping to be stale, that is reported below as a finding, not corrected
here (rule: this review does not fix what it finds, it reports it for a later, owner-ordered
pass).

**Commissioned by:** the owner, 2026-09-28, as a full audit of the running product — not
a RAG-only review and not a repeat of prior audits. **Scope:** everything currently
implemented — core product, administration, Ask/RAG, UI/UX, production readiness,
documentation consistency. **Method:** five parallel investigations (four static
code/test/doc analysis, one live empirical run against a real local stack in an isolated
worktree with a scratch database — `/root/legalmind-worktrees/product-review-e2e`,
branch `review/product-e2e-2026-09-28`, left in place for reuse), synthesized here.
**Repo state reviewed:** `main` @ `9792df7`, clean, immediately after PR #121/#122
(RAG production release + release-record docs).

**Nothing was fixed during this review**, per the owner's instruction. Section I gives the
fix order for a follow-up pass.

> **Update, same day (28 Sep, later):** the top item this review flagged in §A/§B/§E/§I —
> Ask not yet being "one real Ask product" — was closed the same day by a separate
> session's work, merged as PR #123 (`c9a2876`, "AM-106 — one Ask for every reader; the
> verified path is the default") and recorded in
> [LEGALMIND_PROJECT_STATE.md](LEGALMIND_PROJECT_STATE.md). The 10% canary split and the
> document-vs-no-document routing fragmentation described below in §A, §B, §E, and §I's
> "Should fix next" item 1 describe the state as it stood **before** that merge — left
> unedited here as the record of what was true when this review ran, per this project's
> append-don't-rewrite convention for superseded findings. Everything else in this review
> (functional correctness, admin/security, UI/UX, production readiness, documentation
> drift) is unaffected by that merge and still describes current state.

---

## A. Executive summary

**The core product is real and functionally sound.** Every workflow investigated —
Dashboard, Reviews, Findings, Client Profiles, Standards publish, Documents/OCR/compare,
Ask's fail-closed refusal behavior — has a genuine backend endpoint, a genuine frontend
consumer, passing tests, and (for the areas driven through a real browser) observably
correct behavior on live data. No dead buttons, no client-only state pretending to be
persisted, no hardcoded legal values were found anywhere in the areas reviewed.

**Authorization and security are genuinely enforced server-side, not just in the UI.**
This was tested empirically, not merely read in code: a Platform Admin account calling
`POST /configuration/publish` directly got a real `403`; a Department Lead got a real
`201`. A user in one department calling `GET` on another department's real contract ID
got a byte-identical `404` to a nonexistent ID. Every admin-write endpoint traced
(contract transfer, Standards publish, user/role administration) independently
re-checks permission and object scope server-side — no instance was found anywhere of
the UI hiding an action the API would still permit. This is the single most important
class of defect this review looked for, and none was found.

**The one genuine, owner-relevant product gap is Ask/RAG routing.** The new
evidence-grounded, claim-verified multi-source Ask engine (PR #121, 2026-09-28) is real,
well-tested, and fails closed correctly — but it is **not yet "one real Ask product."**
Today, on `main`: any conversation with a document attached is 100% pinned to the legacy
engine; a document-less conversation has a ~10% chance (deterministic per-conversation
hash) of the new engine. No plan or code currently exists to unify these — the
plausibly-named branch `feat/ask-new-engine-default` is an empty placeholder, zero
commits ahead of `main`, no open PR. This is a safe, honestly-labeled, fail-closed
canary — not a defect in what's shipped — but it does not yet meet the standard the
owner named.

**The most concrete, fixable defects found are documentation drift, not product
defects.** `IMPLEMENTATION_STATUS.md`'s own sync marker is 2,356 lines / 15 days stale
against `all_lock.md`; `CLAUDE.md` undercounts open conflicts (says five, `CONFLICTS.md`
itself shows seven — C-22 and C-24 are missing from the list); and the C-14 table-count
conflict has drifted through three different numbers (29 / 30 / 31) with none current.
None of these block product use, but they are exactly the "stale number survives for
days" trap the project's own greeting protocol exists to catch — see §H.

**One real gap: no automated accessibility test suite.** Manual ARIA discipline is
visibly present (`aria-live`, `.visually-hidden` regions), but there is no `axe-core` /
`jest-axe` check anywhere in CI, despite CLAUDE.md's standing accessibility expectation.

**Nothing rises to "must fix before broader internal use."** No correctness defect, no
authorization bypass, no data-integrity problem, and no locked-decision violation was
found in any of the five investigations. The fix list below is real but is a "tighten
and unify" list, not a "stop and repair" list.

---

## B. Product area matrix

| Area | Status | Evidence | Problem | Severity | Recommended next action |
|---|---|---|---|---|---|
| Dashboard | ✅ Correct | Live browser run: real counts, 0 dead links, 200 OK, clean at 390px and desktop | Nav label "Client Profiles" truncates to "Client" at 390px | Low (cosmetic) | Fix truncation in a UI pass |
| Reviews | ✅ Correct | Three-word status (`AM-56`/`AM-53`) server-derived (`evaluation/user_status.py`), 31 passing tests, live-verified 23 findings (12/6/5 split) with reader word over engine word exactly as designed | none | — | none |
| Legal / Findings | ✅ Correct | Evidence→Fact→Standard→Rule→Result rendered ("How this was determined"); `classification`/`rule_outcome` kept as distinct fields everywhere checked | none | — | none |
| Ask | 🟡 Partial | Every stage (retrieval, evidence, generation, verification, citation, fallback, observability) is ✅ individually with real tests and a live-verified fail-closed refusal; but routing is fragmented — see §E | Not yet one consistent product across document vs no-document conversations | Medium (roadmap gap, not a defect) | Owner decision: plan and build the unification, or explicitly accept the current split as the interim state and widen the canary on trace evidence |
| Client Profiles | ✅ Correct | Live-verified create → list → link-to-contract → relationship reflected on read; delete-when-empty (AM-70) code-verified with race handling | none | — | none |
| Standards / Constitution | ✅ Correct | 72 active + 7 retired = 79 files, independently recounted from disk, matches CLAUDE.md's claim exactly; publish workflow fail-closed on incomplete config, live-verified 403/201 role split | none | — | none |
| Administration | ✅ Correct | Live-verified: Platform Admin sees Users/Departments/Roles/Audit only, explicit "Contract content is never administered here" copy, cannot open a deal | none found | — | none |
| Users | ✅ Correct | Deactivation revokes sessions immediately (password path); OIDC stateless-JWT path re-checks account status every request (code-verified) | No per-token/per-device revocation on the pure-OIDC path — only full-account disable | Low (documented trade-off, `AM-36`) | Owner call only if per-device revoke is ever needed |
| Permissions | ✅ Correct | S-1 (fresh per-request resolution), SEC-02/ROLE-05 (no bypass to legal authority), SEC-07 (byte-identical 404) all code-verified AND live-verified on real cross-department data | Developer role's non-legal grant is broader than its own "break-glass for debugging" framing | Low (informational) | Confirm with owner whether the framing or the grant should narrow |
| Documents | ✅ Correct | OCR pipeline real (OCRmyPDF+Tesseract, fail-closed), original/text toggle real, Compare versions deterministic and boundary-enforced (33.16); live-verified upload → 21-page render → clause index | none | — | none |
| UI/UX (product-wide) | 🟡 Partial | Terminology/state-axis discipline (`StatePill`, three-word status) is strong and consistent everywhere checked | No automated accessibility test suite; a few screens hand-roll status pills instead of reusing the shared component; loading-state consistency not independently verified | Medium (a11y gap) / Low (rest) | Add `axe-core`/`jest-axe` to CI; note pill consolidation for a later pass |
| Production readiness | 🟡 Partial | Single clean Alembic head matching deployed revision exactly; real, tested, restore-verified backup pipeline; zero hardcoded secrets found | CI job 10 (Playwright) failed on the latest main run — pre-existing, documented, nondeterministic, non-gating flake, not a new regression; a couple of Ask feature flags (`LEGALMIND_QUERY_PLANNER`, `LEGALMIND_QUERY_EXPANSION`) may be dead code referencing a parked feature | Low | Confirm and remove dead flags if genuinely unreachable |
| Documentation consistency | 🔴 Incorrect | `IMPLEMENTATION_STATUS.md` sync marker 2,356 lines stale; `CLAUDE.md` "five open conflicts" is actually seven (C-22, C-24 omitted); C-14's table count has drifted through 29/30/31 with none current | Concrete, evidence-backed staleness in exactly the class of number the project's own rules warn about | Medium | Correct the three numbers in a small, isolated doc-only pass |

---

## C. Functional workflow findings

Verified end-to-end, live, in a real browser against an isolated local stack (fresh
Postgres DB, backend `:8199`, frontend `:3199`, no production data touched, no Gemini
credential spent):

1. **Login → role-differentiated navigation.** A Department User account and a clean
   single-role Platform Admin account log in through the real form and land on
   different, correctly-scoped navigation. The Admin account is explicitly refused
   document access ("Access restricted") and shown only `Administration`.
2. **Upload → OCR → workspace.** `MSA.pdf` (source material D6) uploaded, chained
   through create → version → analysis without manual steps, rendered with a working
   original/text toggle and a clause-numbered contents index matching the PDF.
3. **Analysis → Findings.** 23 Findings produced with the correct 12/6/5 Accepted /
   Requires modification / Needs a decision split, each showing both the reader word
   and the underlying engine classification, with Constitution citations and a
   plain-English "how this was decided" disclosure.
4. **Ask — grounded refusal, not hallucination.** A document question that the
   confirmed evidence doesn't support returns the exact pinned honest-refusal sentence.
   A no-document general-knowledge question ("What is the capital of France?") is
   **also refused**, not answered from the model's open-domain knowledge — confirms
   Gemini is never used outside authorized domains (`AM-25`), even without spending a
   Gemini call to test the positive path.
5. **Client Profiles.** Real create → list → link-to-contract → relationship-reflected-
   on-read round trip, not UI decoration.
6. **Compare versions, Archive vs Delete, publish workflow** — all code-verified with
   passing tests (`test_version_comparison.py`, `test_contract_archive.py`,
   `test_publish_payload.py`) and, for publish, also live-verified via a real API call.

No dead buttons, mocked data paths, or placeholder UI were found in any area reviewed.
201 targeted backend tests were run live against a real database during this review, in
addition to the existing test suite: 0 failures.

**Not verified in this pass** (explicitly, not assumed working): the full non-RAG
backend suite as a single run (a background attempt was killed by a timeout — the
targeted subset that did complete is 201/201 green and covers the same areas); frontend
component-test execution for these areas (`client-profiles.test.tsx`,
`dashboard-actions.test.tsx`, `finding-card.test.tsx` etc. — confirmed present, not run
this session); a real Gemini-generated, cited Ask answer (deliberately not spent, per
the cost guard — the refusal path was verified instead, which needs no credential).

---

## D. Admin / security findings

**Trust chain traced and verified, both in code and live:** Authentication →
Authorization → Business Operation → Database, with no shortcut found anywhere.

- **S-1 (fresh per-request permission resolution):** `security/resolver.py`
  `effective_permissions` queries the database on every call; nothing is cached across
  requests.
- **SEC-02 / ROLE-05 (no super-role bypass to legal authority):** `ROLE_DEVELOPER`'s
  grant is computed as *all permissions except* `LEGAL_AUTHORITY_PERMISSIONS` — a
  self-updating exclusion, not a hand-maintained list that could drift; `PLATFORM_ADMIN`
  grants only user/role/platform/audit management, nothing under `legal.*` or
  `contract.*`. Live-verified: Platform Admin's direct `POST /configuration/publish`
  call returned `403`; the same call as Department Lead returned `201`.
- **SEC-07 (byte-identical 404):** Live-verified on real data, not just code-read — a
  second user in a different department calling `GET` on another department's real
  contract ID got the same `404` as a nonexistent ID, versus `200` for the actual owner.
- **LEGAL-02 (confidential omission):** `redact_legal_position` is a single choke point
  that filters dict keys out — never sets a field to `None` — consumed by every
  serializer that touches legal-position fields.
- **UI-hides-but-API-permits check (the single most damaging bug class in this
  domain):** none found. Contract transfer, Standards publish, and user/role admin
  writes all independently re-check permission, visibility, and ownership/department
  scope server-side; the frontend gates only on a server-resolved permission array,
  never a client-held role string.
- **Deactivation:** password-login sessions are revoked immediately on status change;
  the stateless-JWT OIDC path (`AM-36`) has no token blocklist by deliberate,
  documented design, but re-checks account status against the database on every
  request, so a disabled account cannot act mid-token-lifetime regardless.
- **Escalation guards (S-8/S-9) and the zero-legal/zero-admin lockout guard (SEC-05):**
  both wired into every relevant admin write, code-verified.
- **Prior regression class (PR #85, Stage 10 conversation-replay leak) is now the
  general pattern, not a one-off patch:** the fix generalized the same "resolve fresh
  every time" discipline already used elsewhere (session resolution, permission
  resolution, redaction), rather than patching only the one replay endpoint.

**Two informational-only items, not defects:** no per-token/per-device revocation for
the pure-OIDC path (only full-account disable) — a named, deliberate `AM-36` trade-off;
and the Developer role's non-legal permission grant is broader than its own
"break-glass for debugging" framing in code comments, worth an owner confirmation but
not a spec violation.

One investigator (the admin/security agent) could not execute the local DB-backed test
suite in its own environment (`password authentication failed`), while two other
investigators in the same review successfully ran the same tests against
`legalmind_lmtest` — this looks like a setup slip in that one agent's session rather
than a real environment gap, since the credential is documented and worked elsewhere in
this same review.

---

## E. Ask / RAG findings

Do not restart or re-measure the RAG production programme (`AM-79`–`AM-105`) — it is
done and documented in `CHANGELOG.md` and `DAILY_CHANGED.md`. This section assesses
current state only.

| Sub-area | Status | Evidence |
|---|---|---|
| Retrieval | ✅ Correct | `assist/retrieval.py`; pool recall 0.988; authorization inside every query |
| Evidence bundle | ✅ Correct | `assist/evidence.py`; wrong-source 0, false admission 0 |
| Generation | ✅ Correct, minor known defects | Single audited egress (`generate_raw`), no bypass found anywhere in `assist/`; three small open items already tracked in the roadmap matrix (a follow-up once answered from the wrong period; a duplicated citation marker slipping the legend's collapse regex; one Constitution sentence addressed to the system itself shown verbatim) — none flagged unsafe |
| Verification | ✅ Correct | NLI-based claim check + claim contracts; bad sentences shown down to 0.7% in replay; fails closed (unverified claim never shown) |
| Citation | ✅ Correct | Markers assigned by code, not the model; one known duplicate-marker cosmetic bug (see Generation) |
| Conversation | ✅ Correct, one open gap | Bounded prior-turn context works and is tested; roadmap §15 still notes one case of a bare-figure misattribution and one lost-topic 3-turn chain |
| **Routing** | 🟡 **Partial — see below** | |
| Latency | 🟡 Partial | Real per-stage tracing exists and is tested; live figures are wide (rerank p50/p95 801/1071ms, generation p50 2.8s, browser Ask 6–21s per answer) and not yet tightened — a stated, open item in the roadmap matrix, not a new finding |
| Fallback | ✅ Correct | Single branch point (`_ask_path`), three independently coded and tested fallback triggers, fails closed to legacy Ask on any new-path error or non-verification |
| Observability | ✅ Correct | `assist.ask.trace`, one per request, fields tested to explicitly exclude question/answer/source text |
| Temporal/authority controls | ✅ Correct | DPDP s.33/Schedule correctly labelled "not yet in force until 13 May 2027," credited to the Constitution's own date, not the Act's — live-verified in the canary |
| Dead/stale Ask surface | ✅ Clean | No client-controllable engine selector found; every generation call site funnels through the one audited egress |

### Routing — "one real Ask product," specifically

Today, `main` does **not** give every authorized user one consistent Ask experience —
and this is by explicit, documented design, not an oversight:

- `LEGALMIND_ASK_MULTI_SOURCE` is set to `no_document` in production: **any conversation
  with a document attached always gets the legacy engine, unconditionally**, regardless
  of the canary percentage.
- For document-less conversations, `LEGALMIND_ASK_MULTI_SOURCE_PERCENT=10` in
  production: a hash of the conversation id decides engine membership, and that
  assignment is sticky for the conversation's lifetime — but two different
  conversations by the same user in the same sitting can and do land on different
  engines, with materially different answer shapes and verification depth.
- The plausibly-named branch `feat/ask-new-engine-default` is a placeholder: zero
  commits ahead of `main`, no open PR. **No plan or implementation currently exists to
  unify the two engines**, and the roadmap's own recorded next action ("widen the share
  on trace evidence") has no numeric target or document-path timeline attached anywhere
  found in the repo.

This is a safe, honestly-labeled, fail-closed canary rollout — not a functional defect
in what has shipped — but it is explicitly short of the standard the owner named. See
§I for where this sits in priority.

### CI status (Ask-related)

Latest `main` CI run (PR #122 merge): 14/15 jobs passing; job 10 (Playwright browser
workflows) failed — matches the pre-existing, previously-documented nondeterministic,
non-gating flake, not a new regression.

---

## F. UI/UX findings

- **Strong:** terminology discipline (three-word status, `StatePill`/`AXIS_CLASS`
  five-axis separation) is consistently applied everywhere checked — no internal enum
  or raw technical term found leaking to a reader-facing surface in the areas reviewed.
- **Empty vs. filtered-empty states** are deliberately distinguished and implemented
  (Dashboard, Client Directory) — a conscious design decision, not an oversight.
- **Responsive behavior** is genuinely breakpoint-driven (640/760/900/1080/1200/1400/1500px
  media/container queries); the one fixed-pixel block found (decorative hero art) is
  correctly hidden below 1180px. Live-verified clean rendering at 390px and desktop for
  Dashboard and the document workspace.
- 🔴 **No automated accessibility test suite.** No `axe-core`/`jest-axe`/
  `@axe-core/playwright` dependency anywhere in `frontend/`, and no a11y-specific spec
  among the 31 e2e spec files. Manual ARIA care is visible (`aria-live="polite"`,
  `.visually-hidden` regions) but nothing catches a regression automatically. Medium
  severity — a real gap against CLAUDE.md's standing accessibility expectation, not a
  redesign question.
- 🔵 **Cosmetic:** narrow-viewport (390px) nav label "Client Profiles" truncates to
  "Client"; Dashboard/Client screens hand-roll their own status-pill CSS classes
  instead of reusing `StatePill` (same correct values and terminology, just architectural
  duplication); loading-state consistency across screens was not independently verified
  (no shared skeleton/spinner component was found, but no visible inconsistency was
  confirmed either).
- No stylistic redesign is proposed anywhere in this section — the product is UI-frozen
  per the 2026-08-31 owner instruction, and every item above is either a real,
  evidence-backed defect (a11y) or a small, isolated cosmetic note, not a preference.

---

## G. Production-readiness findings

- **Migrations:** single clean Alembic head (`b8e2f6a4d1c3`) matching the deployed
  revision exactly, per `IMPLEMENTATION_STATUS.md`'s 2026-09-28 release note — verified
  by running `alembic heads` directly, not by reading the doc.
- **Backups:** real, tested, two-stage pipeline (14-day local, 90-day encrypted
  off-site) with restore verified by actual decrypt-and-restore into a scratch
  database, not narrated.
- **Secrets:** repo-wide grep for hardcoded credentials/keys across all source file
  types (excluding the gitignored `legal-docs/`) returned zero hits.
- **CI:** the one red job on the latest main run is the documented, pre-existing,
  nondeterministic Playwright flake (job 10) — not a new regression. Three jobs (6/7/8)
  show as skipped as expected when their trigger conditions (`all_lock.md` changes, etc.)
  don't apply to this push.
- 🔵 **Dead-flag candidates:** `LEGALMIND_QUERY_PLANNER` and `LEGALMIND_QUERY_EXPANSION`
  are still read by code and referenced by `tools/probe_targeting.py`, but
  `IMPLEMENTATION_STATUS.md` records the query planner as "PARKED... absent from the
  deployed tree" (2026-09-17). Worth confirming whether these flags gate genuinely
  reachable code or should be removed alongside the parked feature.

---

## H. Documentation / record consistency findings

This is where the review's most concrete, easily-fixed defects live — exactly the class
of drift the project's own rules (rule 23, the greeting protocol's "verify before
asserting a number") exist to prevent.

1. 🔴 **`IMPLEMENTATION_STATUS.md`'s own sync marker is stale.** It states "Last
   synchronized against `all_lock.md` at 19,374 lines" (dated 2026-09-13), while the
   same document's body narrates events through 2026-09-28 (`AM-104`/`AM-105`, PR
   #121/#122) and `all_lock.md` is now measured at 21,730 lines — a 2,356-line, 15-day
   gap between the document's own header claim and its actual content.
2. 🔴 **`CLAUDE.md` undercounts open conflicts.** It states "Five remain open: C-12,
   C-13, C-14, C-17, C-19." `CONFLICTS.md` itself currently shows **seven** open
   (⏳, not ✅ RESOLVED): those five plus **C-22** (registered 2026-09-15, provenance
   question between two Constitution-version cohorts) and **C-24** (registered
   2026-09-21, whether a Schedule is a citable unit under `AM-32` r7). Both omitted
   conflicts are marked low severity and "blocks nothing" in their own record, but the
   count in CLAUDE.md is factually wrong today.
3. 🔴 **C-14 (table count) has drifted through three different numbers with none
   current.** The summary table says "declares 29"; the conflict's own detail section
   (AB-12 r14, 2026-09-05) says "repository now has 30"; a direct count today
   (`grep -c "__tablename__"`) gives **31**. Low severity (the conflict record itself
   says this blocks nothing) but a clean illustration of the exact trap named above,
   recurring inside the very document meant to catalog drift.
4. ✅ **`all_lock.md`'s line count claim is accurate**: `wc -l` gives 21,730, matching
   CLAUDE.md exactly.
5. ✅ **The "three traps" table's older-vs-successor pairs are still accurate** on
   spot-check (`AUTHENTICATION.md` vs `STEP_47_SECURITY_SPECIFICATION.md` verified
   directly).
6. ⚪ Not independently confirmed line-by-line: whether `CHANGELOG.md`'s
   `[Unreleased]` section still needs updating now that PR #122 (same-day release
   record) has merged — plausible it's already current given the timing, but not traced
   in full this session.

None of items 1–3 changes any legal, security, or functional conclusion elsewhere in
this review — they are bookkeeping defects, not product defects — but they are cheap to
fix and exactly the kind of stale figure the project has been burned by before.

---

## I. Fix priority

**Must fix before broader internal use**
- *(none)* — no correctness defect, authorization bypass, data-integrity problem, or
  locked-decision violation was found anywhere across all five investigations. This is
  a genuinely clean result, not an omission — see §A.

**Should fix next**
1. Decide and build (or explicitly, formally defer with a stated timeline) the Ask
   engine unification — today's document-vs-no-document, per-conversation-canary split
   is safe but not "one real Ask product." This is the single substantive product gap
   this review found.
2. Correct the three stale numbers in §H (items 1–3) — a small, isolated,
   doc-only pass; no code touched.
3. Add an automated accessibility check (`axe-core`/`jest-axe` or
   `@axe-core/playwright`) to the frontend test suite and CI.
4. Confirm and, if genuinely dead, remove `LEGALMIND_QUERY_PLANNER` /
   `LEGALMIND_QUERY_EXPANSION`.
5. Run the existing frontend component-test suite for the core areas
   (`client-profiles.test.tsx`, `dashboard-actions.test.tsx`, `finding-card.test.tsx`,
   etc.) to close the one verification gap left in §C.
6. Fix the narrow-viewport nav label truncation ("Client" → "Client Profiles").

**Can improve later**
1. Consolidate hand-rolled Dashboard/Client status-pill CSS into the shared `StatePill`
   component (values/terminology are already correct — this is architecture cleanup,
   not a correctness fix).
2. Add a shared loading-state (skeleton/spinner) primitive if a follow-up visual pass
   confirms real inconsistency.
3. Per-token/per-device session revocation for the pure-OIDC path, if the owner ever
   wants finer-grained revocation than full-account disable.
4. Owner confirmation on whether the Developer role's permission breadth should narrow
   to match its "break-glass for debugging" description.
5. Confirm CI jobs 6/7/8's skip conditions are the intended path filters.

**No action required**
- CI job 10's Playwright flake (known, pre-existing, non-gating).
- Everything else classified ✅ Correct across §B–§G.

---

## Provenance

Five parallel investigations, synthesized by the coordinating session on 2026-09-28:
core product functional review; admin/RBAC/security review; Ask/RAG pipeline
current-state review; UI/UX + production-readiness + documentation-consistency review;
live browser end-to-end verification (isolated worktree
`/root/legalmind-worktrees/product-review-e2e`, scratch database, no production or
other sessions' worktrees touched). Full per-investigator evidence (file:line
citations, test run output, HTTP status codes from live calls, screenshots) is retained
in this conversation's transcript; this document is the synthesized, continuity-facing
record per rule 15.
