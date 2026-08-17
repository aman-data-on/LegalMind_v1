# Implementation Plan

## Status: NOT YET SPECIFIED

**No implementation plan has been decided, and implementation is not authorized.**

> A **recommended** build sequence now exists in [IMPLEMENTATION_READINESS_GATE.md](IMPLEMENTATION_READINESS_GATE.md) §5 — schema → auth/RBAC → domain → ingestion → mapping → evaluators → findings → API → corpus harness → frontend → observability → deployment. It is a recommendation, not a locked plan: no milestones, schedule, or allocation have been decided.

The master specification (`all_lock.md`, Steps 1–45D, 47, 49, 52–55) is a *design* specification. It defines what LegalMind must do, how it must reason, and how it must be structured — it does not define build sequencing, milestones, team allocation, or a delivery schedule. None of that has been discussed or locked.

**Do not infer an implementation plan from the specification's step numbering.** The steps are the order decisions were *made*, not the order work should be *built*.

---

## What must happen before implementation begins

Per the project's specification-first rule ([CLAUDE.md](../../CLAUDE.md)):

1. The specification phase must be explicitly declared complete for the area being built.
2. The open conflicts in [CONFLICTS.md](../00-project/CONFLICTS.md) that affect that area must be resolved by the specification owner. C-01–C-04 were reconciled on 2026-08-16 (`REC-01`–`REC-07`); four low-severity items (C-05–C-08) and **C-09** remain open. Any state vocabulary must conform to [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md).
3. Items listed as NOT YET SPECIFIED in [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md) that the work depends on must be specified.
4. **Real legal source material the work depends on must be supplied by the owner.** Representative contracts, company standards, Requirement catalogues and any other legal source material not already in the repository must be **requested explicitly and provided** — never invented, and never substituted with an illustrative example treated as production truth. See [CLAUDE.md](../../CLAUDE.md) rule 21 and [IMPLEMENTATION_READINESS_GATE.md](IMPLEMENTATION_READINESS_GATE.md) §6 rule 11.
5. Explicit approval to begin implementation must be given.

---

## What the specification *does* already fix

These are locked and will constrain any eventual plan, but they are not themselves a plan:

* Architecture and domain boundaries → [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md)
* Technology stack table → [BACKEND_ARCHITECTURE.md](../05-architecture/BACKEND_ARCHITECTURE.md)
* Target database schema → [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md)
* Target API contract → [STEP_49_API_FINALIZATION.md](../05-architecture/STEP_49_API_FINALIZATION.md), [API_CONTRACT.md](API_CONTRACT.md)
* Security, sessions and permissions → [STEP_47_SECURITY_SPECIFICATION.md](../06-security/STEP_47_SECURITY_SPECIFICATION.md)
* Test strategy and the mandatory golden corpus → [STEP_54_TESTING_STRATEGY.md](../08-testing/STEP_54_TESTING_STRATEGY.md), [GOLDEN_CORPUS_45E.md](../08-testing/GOLDEN_CORPUS_45E.md)
* Deployment → [STEP_55_DEPLOYMENT.md](STEP_55_DEPLOYMENT.md)

---

## Current next step

Specification work: **Step 45E — Golden Corpus** (64 fixtures specified, authoring outstanding). Everything else awaits explicit approval to implement. See [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md).
