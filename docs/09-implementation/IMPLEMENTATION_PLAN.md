# Implementation Plan

## Status: NOT YET SPECIFIED

**No implementation plan has been decided, and no implementation has begun.**

The master specification (`all_lock.md`, Steps 1–45B) is a *design* specification. It defines what LegalMind must do, how it must reason, and how it must be structured — it does not define build sequencing, milestones, team allocation, or a delivery schedule. None of that has been discussed or locked.

**Do not infer an implementation plan from the specification's step numbering.** Steps 1–45B are the order decisions were *made*, not the order work should be *built*.

---

## What must happen before implementation begins

Per the project's specification-first rule ([CLAUDE.md](../../CLAUDE.md)):

1. The specification phase must be explicitly declared complete for the area being built.
2. The open conflicts in [CONFLICTS.md](../00-project/CONFLICTS.md) that affect that area must be resolved by the specification owner. C-01–C-04 were reconciled on 2026-08-16 (`REC-01`–`REC-07`), so the finding-type enum is no longer blocked; four low-severity items remain open. Any state vocabulary must conform to [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md).
3. Step 45B (evaluator data contract) must be locked; it is currently in review.
4. Items listed as NOT YET SPECIFIED in [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md) that the work depends on must be specified — notably authentication implementation and API endpoint naming.
5. Explicit approval to begin implementation must be given.

---

## What the specification *does* already fix

These are locked and will constrain any eventual plan, but they are not themselves a plan:

* Architecture and domain boundaries → [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md)
* Technology stack table → [BACKEND_ARCHITECTURE.md](../05-architecture/BACKEND_ARCHITECTURE.md)
* Target database schema → [DATABASE_MIGRATIONS.md](DATABASE_MIGRATIONS.md)
* Target API contract → [API_CONTRACT.md](API_CONTRACT.md)
* Test strategy and the mandatory golden corpus → [TEST_STRATEGY.md](../08-testing/TEST_STRATEGY.md), [GOLDEN_CORPUS.md](../08-testing/GOLDEN_CORPUS.md)

---

## Current next step

The specification's own stated next step is **Step 45C — Liability Edge Cases**, not implementation. See [IMPLEMENTATION_STATUS.md](../00-project/IMPLEMENTATION_STATUS.md).
