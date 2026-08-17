<!--
LegalMind is specification-first. The checks below are not ceremony — each one
corresponds to a locked decision that a well-intentioned change can silently
break. See CONTRIBUTING.md for the six kinds of change.
-->

## What this changes

<!-- One or two sentences. -->

## Kind of change

- [ ] Implementation of an already-locked decision
- [ ] Documentation / navigation only
- [ ] Specification change — **requires prior owner approval** (link it below)
- [ ] Conflict report — no resolution attempted

## Decisions this implements

<!-- Decision IDs, e.g. SEC-05, AM-12, 45D.4.10, ENG-09. If none, say why. -->

## Required checks

- [ ] **No locked decision was modified.** If one had to change, approval is linked above and `all_lock.md` was **appended** — never edited in place.
- [ ] **Nothing unspecified was invented.** No legal rule, threshold, tolerance, carve-out or evaluator behavior that isn't in the specification. `NOT YET SPECIFIED` was preserved as-is.
- [ ] **No real legal source material was added.** No counterparty contracts; corpus fixtures are synthetic or cleared text only (Step 54).
- [ ] **State values conform to the five axes** (`DECISION_STATE_MODEL.md`). No axis shares a field or enum with another.
- [ ] **Any contradiction found was reported, not resolved** — added to `CONFLICTS.md` with both sources verbatim.
- [ ] **`IMPLEMENTATION_STATUS.md` updated** if this moves an area between specified / locked / implemented / tested / verified.
- [ ] **`CHANGELOG.md` updated** if this is user- or operator-visible.

## If this touches the analysis engine

- [ ] Golden corpus runs in full and passes.
- [ ] **No expected output was edited to make the build pass.** A changed expectation is a specification change (Step 54).
- [ ] Determinism holds — no clock, random source, locale or environment variable affects a result.
- [ ] Evidence survives every branch; no synthetic evidence is created.
- [ ] Fail-closed paths still fail closed.

## If this touches security, authorization or the API

- [ ] Authorization tests pass — they are **release-blocking**.
- [ ] Out-of-scope objects return a `404` byte-identical to a non-existent one.
- [ ] Confidential fields are **omitted, not nulled**, without `legal_position.view`.
- [ ] No path lets a super-role holder without `legal.decision` decide.
- [ ] Nothing in the "never logged" list reaches a log (Step 53).

## If this touches the database

- [ ] Migration is forward-only and additive over legal data; anything destructive is called out and approved.
- [ ] Reproducibility survives the migration.
- [ ] Append-only enforcement on `audit_events` and `legal_decisions` is intact.
