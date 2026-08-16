# Frontend Architecture

Source: all_lock.md lines 6024-6363 approx. (Step 39 - Recommended Technology Stack, frontend-relevant sections). Canonical source: all_lock.md (Steps 36-39)

Status: RECOMMENDED (not yet locked) for the rationale below, EXCEPT that "Next.js + TypeScript" as the frontend choice is part of the stack table the source explicitly locks under "Step 39 - Technology Stack: LOCKED" (see BACKEND_ARCHITECTURE.md for the full locked stack listing, which names `Frontend: Next.js + TypeScript`). The frontend section of Step 39 itself is brief and framed as a recommendation ("I recommend: Next.js + TypeScript").

See SYSTEM_ARCHITECTURE.md sections 38.22 and 38.23 for the locked architectural rules this frontend must follow (no direct UI→database access, no UI→analysis-engine shortcuts).

---

# Frontend (Step 39)

Status: RECOMMENDED (not yet locked), except the technology name itself which appears in the locked final stack table.

I recommend:

Next.js + TypeScript

The UI should consume the backend API.

Example:

```text
Next.js
    ↓
FastAPI
    ↓
PostgreSQL
```

The frontend should never contain legal evaluation logic.

For example, this should not exist in frontend code:

```text
if customerLiability > companyStandard:
    showDeviation()
```

Instead:

```text
FastAPI
 ↓
Evaluation Engine
 ↓
Finding
 ↓
Next.js displays Finding
```

---

# Frontend testing (cross-reference)

Frontend testing tooling (Vitest, Playwright) is documented in ../08-testing/TEST_STRATEGY.md rather than duplicated here.

---

# Relevant row from the Step 39 recommended stack table

| Layer            | Recommendation            | Why                                                                    |
| ---------------- | -------------------------- | ----------------------------------------------------------------------- |
| Frontend         | Next.js + TypeScript       | Strong admin/dashboard UX, server-side capabilities, mature ecosystem   |
| Frontend testing | Vitest                     | Fast TypeScript unit testing                                            |

---

# What the source deliberately doesn't recommend (frontend-relevant)

Status: RECOMMENDED (not yet locked)

### Business logic in Next.js

Legal evaluation belongs in the backend/domain layer.

(Full "what I deliberately DON'T recommend" list is in BACKEND_ARCHITECTURE.md.)
