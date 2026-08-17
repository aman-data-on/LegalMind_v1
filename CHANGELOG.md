# Changelog

Notable changes to the LegalMind repository. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

**This is not the decision record.** Every decision, its reasoning and its exact locked text live in [`all_lock.md`](all_lock.md), indexed by ID in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md). This file records *what changed in the repository and when*, at milestone granularity, and links out. Decision history is deliberately not duplicated here.

No version has been released. The V1 specification is complete and implementation is authorized (`IMPL-01`, 2026-08-17). Build state is reported in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which is the only document that asserts it.

---

## [Unreleased]

### Added

* Repository-level documentation system: [README.md](README.md), [docs/README.md](docs/README.md) (documentation index), [CONTRIBUTING.md](CONTRIBUTING.md) (change management), [AGENTS.md](AGENTS.md), and this changelog.

* Frontend implementation of locked Step 52 — Next.js + TypeScript, ten screens, the API as its only data path (38.22), permission-driven rendering as presentation only (47.6), omitted-not-nulled confidentiality rendering (52.4), and no optimistic Legal Decision UI (52.7). Vitest suite. Detail in `frontend/README.md`.

* Backend implementation of the locked specification, on the owner's instruction of 2026-08-17 ("LegalMind V1 has now passed the Implementation Readiness Gate. Begin implementation"), in the sequence the owner set. Complete through the analysis orchestrator: database schema and migrations · authentication and authorization (Step 47) · document storage and ingestion (Step 34) · mapping (Steps 28, 35) · evaluation engine (`LIABILITY-001` and `PRESENCE`, Steps 44, 45A–45D) · decision and review workflow (Steps 4, 22, 30, 31) · HTTP API (Steps 43, 47, 49) · liability fact extraction and the analysis orchestrator (Steps 28, 34, 35, 44). Step 53 observability and the Step 55 preflight register, Dockerfiles and compose file are partial. 446 tests. No locked decision amended; the additive tables (`sessions`, `user_identities`, `evaluation_evidence`, `unmatched_provisions`, `review_assignments`, `escalations`) all traced to locked requirements the locked schema does not represent — `review_assignments` and `escalations` were subsequently ratified by Amendment Batch AB-2 as `AM-22` and `AM-23`. Detail in `backend/README.md`.

### Fixed

* **`F-1` EV-MIN had no removal path.** The invariant was enforced `AFTER INSERT` on `findings` only, so deleting or re-parenting the last Evaluation orphaned a Finding undetected — the exact bypass `F-5` chose a database trigger to prevent. Migration `9c2f41ab77e3` adds `AFTER DELETE` and `AFTER UPDATE` constraint triggers on `evaluations`, both `DEFERRABLE INITIALLY DEFERRED`, with 5 new invariant tests covering deletion of the last Evaluation, deletion of one of several, and re-parenting.

* **`F-4` test non-determinism.** Runs shared the `public` schema and reset it destructively; an intermediate `pg_terminate_backend` fix then killed concurrent runs' live connections. Each run now migrates into a private `t_<epoch>_<random>` schema and drops only its own, with a conservative sweep for debris from crashed runs. Verified by concurrency: 24 consecutive clean runs including 8 concurrent. The originally recorded diagnosis (a dev-database engine in `api/deps.py`) was disproved and corrected.

### Changed

* [CLAUDE.md](CLAUDE.md), [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) and this file synchronized against `IMPL-01` and Amendment Batch AB-2. They previously asserted that implementation was unauthorized and that nothing was past LOCKED, which contradicted both `all_lock.md` and the working tree. CLAUDE.md's "What 'no implementation' means concretely" section became "What implementation authorization does and does not cover", carrying `IMPL-01`'s own list of what it does **not** grant. No locked text was altered — `all_lock.md` remains append-only at 15,093 lines.

* **`REC-08`** — CI/CD tooling locked as **GitHub Actions**, appended to [`all_lock.md`](all_lock.md) (15,093 → 15,196 lines; the prior lines verified byte-identical). Resolves **C-11**, a contradiction between two locked records: the Step 39 stack table names GitHub Actions for CI/CD, while locked 55.6 listed CI/CD tooling among NOT YET SPECIFIED operational choices. Owner decision, 2026-08-17 — the Step 39 row governs. Consequence: `.github/workflows/ci.yml` is an authorized use of the locked Step 39 stack, not an unratified implementation choice, and is retained unchanged. 55.6's text is **not** rewritten; it carries a supersession banner for that one line item. Hosting platform, orchestration, object-storage provider, monitoring stack and DR objectives **remain NOT YET SPECIFIED**. Surfaced while correcting [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which asserted "No CI pipeline" while an eight-job pipeline was gating `main`.

* Removed a CI step that annotated every run with a warning saying `F-1` was still open. `F-1` was fixed in `e989012`; the step asserted nothing, and an annotation claiming a fixed bug is open is worse than none. Enforcement is `test_ev_min_triggers_are_deferred_to_commit`, which fails if any of the three triggers is missing.

* **`F-*` is an overloaded namespace.** [DECISION_FINALIZATION.md](docs/00-project/DECISION_FINALIZATION.md) §1 uses `F-1`–`F-12` for engineering resolutions; [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) § Blocking the VERIFIED state uses `F-1`/`F-3`/`F-4` for code-review findings. `AM-23` cites "engineering resolution `F-3`" (escalation at Finding level), which is not the `F-3` in the build-state table (Mapping State not persisted). Flagged in [CLAUDE.md](CLAUDE.md); merging or renumbering the two series is an owner decision.

* **Build-sequence numbering differs across three documents.** [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5 is a twelve-step list with the frontend at 10; [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)'s build table is an eleven-unit list with the frontend at 8, having gained an explicit analysis-orchestrator unit; the owner's build instruction also put the frontend at 8. The *order* agrees in every case — only the numbers differ. Left as written; no document was renumbered.

---

## 2026-08-17 — V1 specification complete

The V1 specification reached completeness. `all_lock.md` grew to 14,885 lines, append-only throughout.

* **Amendment Batch AB-1** locked — 13 amendments repairing locked requirements the locked schema could not represent; two new tables (`evaluation_evidence`, `unmatched_provisions`). No legal policy changed.
* **Steps 45B (re-lock), 45C, 45D** locked — evaluator data contract, liability edge cases, cross-evaluator structural contract and the generic `PRESENCE` evaluator.
* **Step 47** locked — security, authentication (OIDC primary with password fallback, `OD-9`), authorization, permission catalogue; new `sessions` and `user_identities` tables.
* **Steps 49, 52, 53, 54, 55** locked — API finalization, frontend architecture, observability, testing strategy, deployment. No schema impact.
* **Step 45E** opened — golden corpus, 64 fixtures specified. In progress.
* **Implementation Readiness Gate** — all nine criteria met. Reports readiness; does not grant it. Supersedes the interim readiness review.

Registry: [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) §AB, §S47, §S49–55 · Gate: [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md)

## 2026-08-16 — Cross-document reconciliation

* **`REC-01` – `REC-07`** locked. Conflicts C-01 – C-04 reconciled; none was a true contradiction. The Step 36 seven-value set became canonical for Finding Classification; `ADDITIONAL`/`EXTRA` became the document-level `UNMATCHED_PROVISION` observation; the **Five-Axis Decision State Model** was established as the canonical cross-layer state reference. No historical locked text was modified.
* Four low-severity conflicts (C-05 – C-08) remain open.
* The scoring-band → mapping-state mapping was **deliberately left unspecified** by owner decision. It must not be inferred.

Detail: [CONFLICTS.md](docs/00-project/CONFLICTS.md) · [DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md)

## Earlier — Steps 1–45A

The design specification: product scope, roles and authority, the legal domain model, document and evidence models, the layered analysis engine, `LIABILITY-001`, system and database architecture, audit and reproducibility. Recorded step by step in [`all_lock.md`](all_lock.md) and indexed in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md).
