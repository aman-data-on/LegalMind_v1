# Test Strategy

Source: all_lock.md lines 6543-6612 (Step 39 - Testing strategy section). Canonical source: all_lock.md (Steps 36-39)

Status: RECOMMENDED (not yet locked) for the strategy narrative below, EXCEPT that the testing tools named (Pytest, Vitest, Playwright) are part of the stack table the source explicitly locks under "Step 39 - Technology Stack: LOCKED" (see ../05-architecture/BACKEND_ARCHITECTURE.md for the full locked stack listing).

See also ../05-architecture/SYSTEM_ARCHITECTURE.md for the Step 37 - V1 Scope Freeze content (V1 includes/excludes, acceptance boundary), which is not testing-specific and is documented there rather than duplicated here.

---

# Testing strategy (Step 39)

Status: RECOMMENDED (not yet locked), except tool names which appear in the locked final stack table.

LegalMind needs unusually strong automated tests.

I'd require:

### Unit tests

For:

```text
parsers
normalizers
mapping rules
evaluation rules
conflict detection
versioning
permissions
```

### Golden/test contracts

Create a controlled corpus:

```text
contracts/
├── liability/
├── termination/
├── indemnification/
├── governing-law/
├── conflicts/
├── missing/
└── ambiguous/
```

Each test contract has an expected result.

Example:

```text
Input:
12-month liability

Expected:
DEVIATION

Expected evaluation:
Within acceptable threshold
```

This is how we'll tune the deterministic algorithm instead of guessing thresholds.

### Integration tests

Test:

```text
upload
→ processing
→ analysis
→ findings
→ legal decision
→ audit
```

### Playwright

Test the actual UI workflow.

---

# Relevant rows from the Step 39 recommended stack table

| Layer            | Recommendation       | Why                                              |
| ---------------- | --------------------- | ------------------------------------------------- |
| Testing          | Pytest + Playwright   | Backend/domain + real browser workflow testing    |
| Frontend testing | Vitest                | Fast TypeScript unit testing                      |

---

# Testability by design (cross-reference, from "API architecture", Step 39)

Status: RECOMMENDED (not yet locked)

Keep the domain logic independent from HTTP.

That means the evaluation engine can eventually be tested like:

```text
evaluate(requirement, clause, standard, rule)
```

without running a browser or API server.

That's extremely valuable for legal testing.

(Full API architecture layering is documented in ../05-architecture/BACKEND_ARCHITECTURE.md.)

---

# Locked testing tools (from Step 39 final locked stack)

Status: LOCKED (part of the "Step 39 - Technology Stack: LOCKED" final stack listing)

```text
Testing:           Pytest + Vitest + Playwright
```

See ../05-architecture/BACKEND_ARCHITECTURE.md for the complete locked Step 39 stack table.

---

# Note on Step 37 (V1 Scope Freeze)

Step 37's V1 scope freeze (V1 includes / V1 explicitly excludes / acceptance boundary) is not framed in the source as testing-specific content — it defines the functional V1 boundary ahead of architecture, not a test plan. Per the source organization, it is documented in full in ../05-architecture/SYSTEM_ARCHITECTURE.md under its own "Step 37 — V1 Scope Freeze" heading rather than duplicated here. Note, however, that the Step 37 acceptance boundary ("A V1 Review is successful only if... is completely traceable") is directly relevant to designing integration tests and golden/test-contract expectations above.
