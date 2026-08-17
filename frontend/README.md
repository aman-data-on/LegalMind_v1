# LegalMind V1 — frontend

Implementation of locked **Step 52 — Frontend Architecture**, against the locked
Step 49 API. The specification is the source of truth: `../all_lock.md`
(authoritative) and `../docs/` (organized reference). See `../CLAUDE.md`.

## Stack

Next.js 16 · React 19 · TypeScript · Vitest. All locked by Step 39
(*"Frontend: Next.js + TypeScript"*, *"Frontend testing: Vitest"*).

**Nothing else was added.** No component library, no CSS framework, no state
library, no DOM testing library. Two reasons, and they point the same way: locked
52.6 records visual design, component library, accessibility target and
internationalisation as **NOT YET SPECIFIED** (*"none is determined by a locked
decision"*), and rule 19 forbids adding a technology without approval. Picking one
here would quietly make it the project's answer to a question the owner has not
decided.

Consequences worth knowing:

* Styling is one plain stylesheet, `src/app/globals.css`.
* Component tests render to static markup with `react-dom/server`, which ships
  with React, instead of using `@testing-library/react` + `jsdom`.
* **Playwright is locked for browser-level workflow testing (Step 39, Step 54) and
  is not set up here.** It needs browser binaries and a running stack; it belongs
  with CI (unit 10), not with this unit.

## Setup

```bash
npm install
LEGALMIND_API_ORIGIN=http://127.0.0.1:8000 npm run dev   # http://localhost:3000
npm run test        # Vitest
npm run typecheck   # tsc --noEmit
npm run build
```

### Why there is a dev proxy

`next.config.ts` rewrites `/api/v1/*` to the API origin. This is a **request
proxy, not a data path** — it forwards HTTP and reaches no repository or database.

It exists because the session cookie is `HttpOnly; Secure; SameSite=Strict` (locked
S-3), so a browser will not send it cross-origin. Production puts the frontend and
the API behind one origin (Step 55); the rewrite reproduces that in development, so
no locked cookie attribute has to be weakened to make development work.

## The three boundary rules (52.1)

| Rule | How it is enforced here |
|---|---|
| **The frontend never touches the database** (38.22) | `src/lib/api.ts` is the only module containing `fetch`, and a test asserts that. No database driver is declared, no SQL string exists, and `DATABASE_URL` appears nowhere. The external reference's pages-call-data-access pattern was rejected as C-EXT-1 and is checked for by pattern, not by symptom. |
| **The frontend never implements legal logic** (38.23) | `classification`, `rule_outcome`, `requires_decision` and roll-up all arrive from the API and are rendered as received. A test scans for local derivation — a client-side roll-up would be a second implementation, free to disagree with the engine. |
| **Permission gating is presentation only** (47.6, 49.11) | `PermissionGate` hides controls; the server authorizes every operation regardless. A gate that failed open would change nothing about what actually happens. |

## Layout

```
src/
  lib/
    api.ts          the ONLY data path — one function per locked 49.3 endpoint
    types.ts        response shapes; confidential fields are OPTIONAL, not nullable
    session.tsx     session + permission context (presentation only)
    permissions.ts  Step 47 §47.4 permission names; locked decision types
  components/
    EvaluationRow    the confidentiality-critical component (52.4)
    FindingCard      classification + evaluations, inseparably (49.7 r1)
    DecisionPanel    per-Evaluation decision; no optimistic UI (52.7)
    DecisionHistory  append-only chain, current vs superseded (Step 31 r20)
    EvidenceList     evidence with document location (52.6)
    AccessRestricted the explicit restricted state (52.3) + PermissionGate
    Feedback         error taxonomy, loading, pagination
    Chrome           permission-driven navigation
  app/
    login/                      password fallback (47.1.3)
    contracts/  contracts/[id]/ Steps 2, 34
    reviews/    reviews/[id]/   Steps 9, 30 · findings + nested evaluations
                reviews/[id]/report/  Step 9 reporting
    configuration/              Steps 21, 29
    audit/                      Step 25
    admin/                      Step 23, Step 47
```

All ten locked 52.6 screens are implemented. Export is the one omission — see
**Deliberate omissions** below.

## The confidentiality rule, and why presence beats permission

Locked 52.4:

> The UI must render an omitted field as simply absent — no placeholder, no
> "hidden", no greyed-out row, no lock icon. A visible marker would disclose that
> an internal legal position exists, which is exactly what LEGAL-02 prevents. The
> normal-user and authorized-legal views are structurally different views, not the
> same view with fields masked.

So every legal-position field is rendered by testing whether the property is
**present in the response** — never by asking what the caller is permitted to see.
Those are different questions and only the first is safe: a permission check would
let the component know a value was withheld, and anything it then emitted (a dash, a
sized-but-empty row, a tooltip) would be the marker 52.4 forbids.

`src/lib/types.ts` makes the compiler enforce this: `rule_outcome`,
`expected_value`, `operator`, `comparison`, `explanation` and
`legal_rule_version_id` are declared **optional**, not `T | null`, with
`exactOptionalPropertyTypes` on. Code cannot read them and render a fallback,
because they may not exist.

Verified end to end against the running stack, with the locked 45C two-scope shape:

* the owning **User** receives an Evaluation with no `rule_outcome`,
  `expected_value`, `operator`, `comparison` or `explanation` **keys at all**;
* the assigned **Legal Reviewer** receives all of them.

## The Review screen (52.5) — five structural guarantees

1. **Every Finding shows its Evaluations.** `FindingCard` has no prop that
   collapses to a single verdict, so 49.7 r1 cannot be violated from a call site.
2. **Decision controls attach to the Evaluation.** `renderEvaluationActions` is
   per Evaluation. There is no Finding-level decision control, in the component or
   in the API client (AB-1.1).
3. **A Finding cannot be resolved from the UI.** No resolve control and no
   endpoint. Resolution is derived server-side (D-3.6, Step 30 r3/r16). *This is
   what makes the "hidden carve-out" failure structurally impossible* — a
   conforming aggregate cap cannot close a Finding whose exception still needs a
   decision, because nothing here closes Findings.
4. **No optimistic UI** (52.7). After a decision the screen re-fetches; a 409 is
   surfaced as its own state — someone decided first, re-read before deciding
   again. Showing the submission as accepted and reconciling later would be a UI
   that lies about a legal act.
5. **`RESOLVED ≠ MATCH`** (rule 14, Step 30 r8). Status and classification are two
   separate values in the header, so a resolved Finding still shows `DEVIATION`.

Also: an Evaluation with `APPROVAL_REQUIRED` / `UNACCEPTABLE` is visually distinct
(52.5). For a caller who cannot see rule outcomes the distinction comes from
`requires_decision`, which is not a legal position and which 49.7's own worked
example returns to everyone.

## Rule 21 — no legal content is authored here

The configuration screen passes every Company Standard, Legal Rule, mapping-rule and
evaluation-rule payload through **exactly as the authorized Legal admin wrote it**.
There is no template, no example threshold, no default tolerance and no suggested
keyword group anywhere in this codebase, and a test forbids one appearing: a
helpful-looking `6 months` placeholder would become the organization's legal position
by accident. Only the two locked evaluator types are offered (AM-16).

## Deliberate omissions

| Not built | Why |
|---|---|
| **Report export** | Locked 49.12 records export formats as **NOT YET SPECIFIED**. There is no API endpoint and no format to emit. A download button would be inventing product behaviour. |
| **OIDC sign-in** | Locked 47.1.3 makes corporate SSO primary, but the API implements only the password fallback: OIDC needs a JWT/JWKS client library (a dependency requiring approval) and the deployment's IdP configuration. The login screen says it is the fallback rather than presenting itself as the intended route. |
| **Analysis progress / triggering** | There is no analysis orchestrator yet — nothing extracts facts from evidence, and Step 35's scoring-band → mapping-state mapping is deliberately deferred by the owner. A Review created here therefore has no Findings until that lands. The screen says so rather than showing a spinner that will never resolve. |
| **Review status controls** | Step 30 r3 — users cannot arbitrarily set Review status. |
| **Visual design, a11y target, i18n** | 52.6 records all three as NOT YET SPECIFIED. |

## Tests (46, Vitest)

| File | Defends |
|---|---|
| `confidentiality.test.tsx` (8) | 52.4 — no marker of any kind where a field was withheld; no empty element in its place; structurally different views; the full position for a permitted caller; attention styling that works without a legal position |
| `boundary.test.ts` (13) | 52.1 — no database dependency, no SQL, `fetch` in one module only; no client-side classification, roll-up or `requires_decision`; no Finding-level decision, no resolve, no status assignment; no optimistic decision UI; no authored legal content; exactly two evaluator types |
| `findings.test.tsx` (11) | 49.7 r1/r2/r3 — classification never without evaluations, the exception always shown, no Finding-level rule outcome, `RESOLVED ≠ MATCH`, empty evidence stated as absence, document location shown, OCR labelled, escalation is not approval |
| `permissions.test.tsx` (14) | 47.5 / Step 23 — no decision without `legal.decision`, `legal.review` does not confer it, `APPROVE_CUSTOMIZATION` needs the extra grant; 52.3 restricted states; 49.5 error taxonomy including a 404 phrased so it cannot be read as out-of-scope |

Two of the source-level checks in `boundary.test.ts` are unusual and intentional:
the rules they defend are about what the frontend *must not contain*, and no
behavioural test can prove the absence of a database client or a locally
reimplemented roll-up.

## Verified

```
npm run test        46 passed
npm run typecheck   clean
npm run build       11 routes, 9 prerendered
```

Plus a live check against the running API: the same-origin `/api/v1` rewrite reaches
FastAPI, the locked envelope and `X-Request-Id` survive the proxy, and the
LEGAL-02 gate behaves as described above for two real signed-in users.

## What this cannot tell you

`npm run test` asserts rendering and structure. It does **not** verify browser
workflows — that is Playwright's job (Step 39, Step 54) and is not set up. Nothing
here is `VERIFIED` in the sense
[`../docs/00-project/IMPLEMENTATION_STATUS.md`](../docs/00-project/IMPLEMENTATION_STATUS.md)
uses the word, and that document — not this one — is the authority on build state.
