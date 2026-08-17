# Changelog

Notable changes to the LegalMind repository. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

**This is not the decision record.** Every decision, its reasoning and its exact locked text live in [`all_lock.md`](all_lock.md), indexed by ID in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md). This file records *what changed in the repository and when*, at milestone granularity, and links out. Decision history is deliberately not duplicated here.

No version has been released. LegalMind is in the specification phase and no implementation is authorized.

---

## [Unreleased]

### Added

* Repository-level documentation system: [README.md](README.md), [docs/README.md](docs/README.md) (documentation index), [CONTRIBUTING.md](CONTRIBUTING.md) (change management), [AGENTS.md](AGENTS.md), and this changelog.

* Backend implementation of the locked specification, on the owner's instruction of 2026-08-17 ("LegalMind V1 has now passed the Implementation Readiness Gate. Begin implementation"), in the sequence the owner set. Complete through unit 7: database schema and migrations · authentication and authorization (Step 47) · document storage and ingestion (Step 34) · mapping (Steps 28, 35) · evaluation engine (`LIABILITY-001` and `PRESENCE`, Steps 44, 45A–45D) · decision and review workflow (Steps 4, 22, 30, 31) · HTTP API (Steps 43, 47, 49). 339 tests. No locked decision amended; five additive tables (`sessions`, `user_identities`, `evaluation_evidence`, `unmatched_provisions`, `review_assignments`, `escalations`) all traced to locked requirements the locked schema does not represent. Detail in `backend/README.md`.

### Flagged

* **C-09** — a `backend/` directory containing Python source (`pyproject.toml`, SQLAlchemy declarative base, `alembic/`, `api/`, `domain/`, `services/`, `tests/`) exists in the working tree, untracked, contradicting the "no implementation exists" state asserted in [CLAUDE.md](CLAUDE.md) and [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md). Recorded in [CONFLICTS.md](docs/00-project/CONFLICTS.md); awaiting an owner decision. **Note:** implementation has since been authorized by the owner (see Added, above), so C-09's *authorization* question is answered while its *provenance* question — whose code the pre-existing untracked `backend/` was, and whether any of it survives — is not.

* **Stale authorization statements.** The line "LegalMind is in the specification phase and no implementation is authorized" near the top of this file, the equivalent statements in [CLAUDE.md](CLAUDE.md), and the build state in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) all predate the owner's 2026-08-17 authorization and are now out of date. Left as written rather than rewritten unilaterally: [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) is the only document permitted to assert build state, and how the authorization should be recorded there is an owner decision.

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
