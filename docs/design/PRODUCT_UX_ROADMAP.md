# LegalMind — Product UX Roadmap

**Status: `PROPOSED` (awaiting owner review). Prepared 2026-08-27 on the owner's
UI/UX-planning directive. Governed by [DESIGN.md](../../DESIGN.md); presentation only —
locks nothing.** This is the A–M strategy deliverable: the thinking that precedes broad
implementation. Designed against the current **Product Vision**
([legalmind-product-vision.md](../../legalmind-product-vision.md)) and the **frozen API
contract** ([docs/api/openapi.json](../api/openapi.json), 45 operations, verified today);
the legacy screens are not a design input (`LEGACY UI — DEFERRED` — a verification
harness, nothing more).

**How this relates to the two design documents that already exist.**
[UI_UX_MASTER_PROMPT.md](UI_UX_MASTER_PROMPT.md) remains the authority on the *visual
system* (registers, color namespaces, type, spacing, anti-patterns).
[WORKSPACE_UI_PLAN.md](WORKSPACE_UI_PLAN.md) is the detailed design of the *one core
screen*, and this roadmap **adopts it** — including where it supersedes the master
prompt's own §3 sketch (recorded as `DD-7`). This document is the layer above both: the
product-wide IA, roles, journeys, inventory, priorities, and sequence.

**Skill inputs (`ui-ux-pro-max`, this pass).** Adopted: empty states carry a next action;
complete keyboard operability with visible focus; compact controls are real buttons with
exposed state; sticky chrome never obscures content or focus. Rejected, with reasons:
mobile-first (this product's primary context is a desk — DESIGN.md §Responsive; tablet is
the floor, phone is out of V1 scope); glass/dark-OLED admin styling and "interactive
product demo" landing patterns (no marketing surface; admin is a control plane, not a
showcase). One query ("split pane document annotation workspace") returned **no database
match** — the workspace's split-pane reasoning below is our own, stated as such.

---

## A · Product UX understanding

LegalMind is **one workspace where every answer points at its source**. Two engines feed
it — a deterministic rules engine that produces verdicts, and an assist lane that answers
questions from retrieved text — and the product's whole trustworthiness rests on the user
never confusing the two, while experiencing them as *one place*.

**The primary experience is the document-anchored Review workspace** — not a dashboard,
not a chat app. The vision (§4) is explicit: one screen per document/session, where
verdicts, questions and evidence coexist; the user "never has to pick a mode." The
product's signature gesture, therefore, is **pointing at the text**: click a verdict or a
citation, and the exact source span highlights in the document pane
(WORKSPACE_UI_PLAN's cross-pane highlight — it costs no new endpoint because evidence
rows already carry page and offsets).

**What a user must understand in the first 10 seconds** (the §22 test):

1. *This tool works on documents* — the landing surface is your documents, not widgets.
2. *It shows you where everything came from* — the first answer or verdict seen carries
   a visible citation, and clicking it moves the document.
3. *Some things it will decline to answer* — a refusal reads as the product keeping a
   promise, not erroring.

**One vision claim deliberately deferred, not faked.** §4's "the retrieval layer decides
which domain(s), the user never picks a mode" describes a backend query-router that does
not exist yet (the ask endpoint is per-contract; Domain A search exists only as an
internal function; Domain C has tables and no statutes). The IA below is shaped so that
when the router arrives, the *same* ask surface absorbs it with zero restructuring — but
today's UI honestly reflects today's routing: ask-within-a-document answers from that
document; Research is a disclosed placeholder.

## B · User & role model (from the live grant matrix, verified today)

Five roles exist; they compose. The design consequence of each:

| Role | Verified capabilities | Experience it needs |
|---|---|---|
| **USER** (analyst/uploader) | create/update contracts, upload, view *own* reviews/findings/evidence, ask, escalate, report | The full document workspace, minus rule outcomes and thresholds (`LEGAL-02` omits them from responses — the pane is simply shorter). **Cannot see Domain A at all** (no `configuration.view`) — the Positions area does not exist in their navigation |
| **LEGAL_REVIEWER** | everything above *read-side* on reviews in Legal scope + `legal_position.view` + `configuration.view`; **no `contract.create`** | Works on *incoming* reviews, not uploads. Their landing bias is the review queue, and they see the full evidence chain including rule outcomes |
| **LEGAL_DECISION_AUTHORITY** | `legal.decision`, `legal.approve_customization` (additive) | The decision panel exists only for them; the *only* control that changes the legal record |
| **LEGAL_ADMIN** | + configuration draft/publish/deprecate | The configuration lifecycle (Domain A as configuration) |
| **SUPER_ADMIN** | `user.manage`, `role.manage`, `audit.view`, `platform.manage` — **and nothing else**: no contracts, no findings, no ask | Confirms §16: admin is a genuinely separate control plane, not "the user UI + more." A SUPER_ADMIN literally cannot open the workspace |

Navigation is derived from permissions by **absence** (52.3): a section the caller cannot
use is not rendered — never greyed, never tooltipped.

**Future external users** (vision §2) are an architecture constraint, not a V1 surface:
see Risks (L) — their promised access to "the same corpus" collides with `LEGAL-02`
today and needs an owner ruling before any external-facing design starts.

## C · Information architecture

**The mental model: "My documents. Open one; everything about it lives there."**

```text
GLOBAL NAV (permission-derived; a missing permission = a missing item)
│
├─ Documents            ← the landing surface. Contracts + their document versions,
│    └─ [open one] ────── review state at a glance, upload as the primary empty action
│         │
│         └─ WORKSPACE (the product)  — WORKSPACE_UI_PLAN.md, adopted
│              ├─ Document pane   (evidence rows, page gutter, highlight target)
│              ├─ Findings pane   (decision queue first, then all — per 52.5/DD-1)
│              └─ Ask pane        (conversations for this document, citations replay)
│
├─ Reviews              ← LEGAL_REVIEWER's bias: the incoming queue across contracts
│                          (lifecycle-filtered list → opens the same workspace)
│
├─ Research             ← Domain C. TODAY: a disclosed, calm placeholder (C-16).
│                          LATER: the statute search surface; same answer/citation
│                          grammar as the Ask pane, sources are statutes not uploads
│
├─ Legal                ← visible only with configuration.view
│    ├─ Positions        (Domain A browsed as configuration — LIVE today via
│    │                    /requirements; search pane is a disclosed placeholder until
│    │                    a positions-search endpoint exists — see K)
│    └─ Configuration    (draft → review → publish; LEGAL_ADMIN)
│
├─ Admin                ← SUPER_ADMIN only; a separate control plane (H)
│    ├─ Users & roles
│    └─ Audit
│
└─ [session menu]        sign out; no profile/settings screens — accounts are
                         administrator-provisioned and the product has no
                         user-configurable behavior to house (deliberate: a Settings
                         screen with nothing real in it is dashboard clutter)
```

**Decisions behind this shape** (§22 answers):

- **Land on Documents, not a dashboard.** There is no cross-document KPI a user acts on;
  every meaningful action starts from a document. A dashboard would summarize what the
  Documents list already shows in one glance (review-state pills per row). For a
  LEGAL_REVIEWER, "Reviews" *is* the queue view — no invented "attention across
  everything" metric (no endpoint provides one; none should be synthesized client-side).
- **Review and Ask are together** — one workspace. They are two lenses on the same
  document, the vision demands one screen, and the cross-pane highlight only works if
  they share the document pane. What keeps them from blurring is the **two-register
  visual system** (master prompt §4.1), not physical separation.
- **Research is separate from the workspace.** It is the one experience with no uploaded
  document — putting a statute search inside a document's workspace would misattribute
  its answers to the document. When cross-domain routing arrives ("does this clause
  comply with the Contract Act?"), that question is *asked in the workspace* and the
  answer cites both — the Research area remains the home of *document-less* research.
- **Positions live under Legal, not global nav.** Verified: ordinary users hold no
  `configuration.view`; internal positions are confidential (`LEGAL-02`). A globally
  visible "Positions" item would advertise a section most users can never open.
- **No Settings/Profile screens** (deliberate deviation from the owner's §10 example
  list): nothing real backs them — no self-serve credential change, no preferences.
  Building them would fake capability (§20).

## D · Core user journeys

**A — Entry:** Sign in → land on Documents (USER) / Reviews (LEGAL_REVIEWER's nav bias —
same app, different first click; not a fork). Failure states: one indistinguishable
credential error (S-7); rate-limit says try later. SSO button: absent until OIDC exists.

**B — Upload → verdicts:** Documents → New contract (name + **declared type** — the one
required choice, never inferred; refusing to guess is the product's character on display)
→ upload → processing states from the lifecycle (never a fake progress bar; queued
analysis re-reads until the lifecycle moves — the pattern the legacy harness already
proved) → workspace opens on the Findings pane, **decision queue first** → each
evaluation: classification · rule outcome (if permitted) · evidence links that highlight
the document pane → decision (authority holders; 409 freezes the form until explicit
refresh) or escalation (everyone; visually a request, never an act).

**C — Ask this document:** workspace → Ask pane → question → honest single wait state
("Searching the document…") → answer with citations (click = highlight) **or** the
refusal sentence, calm, identical wording regardless of cause · **or** the
evaluator-routing reply for compliance-shaped questions ("does this meet our
standard?") pointing at the Findings pane — a third message type, styled as a pointer,
not an answer or a refusal.

**D — Legal research (Domain C):** Research → today: the placeholder states plainly that
statute texts haven't been supplied; nothing pretends. The *designed* future journey
(query → section-cited answer → statute source view) reuses the Ask grammar wholesale —
one new source-viewer variant, no new interaction language.

**E — Administration:** see H.

## E · Screen inventory

| # | Screen | Primary user · action | Key states | API | V1? | P |
|---|---|---|---|---|---|---|
| 1 | Sign in | all · authenticate | error (S-7-identical), rate-limited | `POST /auth/login`, `GET /auth/session` | ✔ | P0 |
| 2 | Documents (landing) | USER · open/create | empty-first-run (upload is the action), loading skeleton, paginated | `GET/POST /contracts` | ✔ | P0 |
| 3 | Contract intake | USER · declare type + upload | validating, rejected-upload (type/size/sniff), processing, `assist_index` readiness | `POST .../document-versions`, `GET /document-versions/{id}` | ✔ | P0 |
| 4 | **Review workspace** | all · the product | see J — richest state matrix | evidence · findings · evaluations · decisions · escalate · conversations · ask | ✔ | **P0** |
| 5 | Reviews queue | LEGAL_REVIEWER · triage | empty (calm "nothing pending"), lifecycle filter | `GET /reviews` | ✔ | P1 |
| 6 | Report view | USER/Legal · read | no-export note (formats unspecified) | `GET /reviews/{id}/report` | ✔ | P1 |
| 7 | Ask history | USER · reopen | empty, citation replay | `GET /conversations`, `GET /conversations/{id}` | ✔ | P1 |
| 8 | Positions (browse) | Legal · consult Domain A | permission-absent for USER | `GET /requirements`(+`/{id}`) | ✔ | P2 |
| 9 | Configuration lifecycle | LEGAL_ADMIN · draft→publish | draft vs published clearly distinct; publish confirmation is a real interruption | `POST /requirements…`, `POST /configuration/publish` | ✔ | P2 |
| 10 | Research (Domain C) | all · placeholder | the one disclosed placeholder screen | — (C-16) | placeholder only | P2 |
| 11 | Users & roles | SUPER_ADMIN · provision | empty, last-admin guard messaging | `/users`, `/roles` ops | ✔ | P2 |
| 12 | Audit | SUPER_ADMIN · trace | dense table, request-id search-by-filter only (allow-listed) | `GET /audit-events` | ✔ | P2 |
| 13 | Not-found / access | all | byte-identical 404 story: one "Not found." — never "no access" | — | ✔ | P0 (as a state, not a screen) |
| 14 | Positions search · statute search · SSO · export | — | placeholder/absent per WORKSPACE_UI_PLAN's disclosure asymmetry | — | states only | P3 |

## F · Priorities — the reasoning

**P0 = the spine of Journey B+C** (screens 1–4 + the 404 discipline): without them the
product cannot demonstrate its one promise. **P1** completes daily work (queue, report,
history). **P2** is the legal/admin plane — real, needed, but its users are few and its
patterns are dense-table conventional. **P3** is placeholder/blocked surfaces — designed
states, minimal build.

## G · Build sequence — what first, and why

**First: the workspace document pane + the cross-pane highlight, as a thin vertical
slice** (one real contract, evidence rendered, one hard-coded-target click highlighting a
span). Reasons:

1. It is the **signature interaction and the highest technical risk** — mapping evidence
   offsets to rendered DOM spans is the one thing in the whole design that could force an
   IA rethink if it doesn't hold up. Risk first, while everything is still cheap to move.
2. Every other pane's value depends on it (verdict-click and citation-click both land
   here). Building findings/ask first would mean integrating against a pane that doesn't
   exist — the "20 disconnected screens" failure mode (§18).
3. It validates the three-pane shell and collapse behavior with real content.

```text
1  Workspace shell + document pane + highlight (the risk slice)
2  Findings pane in the shell — queue-first, pills, decision/escalate
   (re-pinning each legacy Playwright guarantee as it lands)
3  Ask pane in the shell — conversations, citations wired to the highlight
4  Documents landing + intake        (entry into the spine)
5  Login (DD-4 finish, new shell identity) + session states
6  Reviews queue · report · ask history                       (P1)
7  Legal area: positions browse + configuration lifecycle     (P2)
8  Admin plane: users/roles + audit                           (P2)
9  Research placeholder + remaining gated states              (P2/P3)
10 Responsive collapse hardening + accessibility audit + UX QA sweep
```

(Steps 1–3 continue WORKSPACE_UI_PLAN's own sequence — its step 1, the
`DomainPlaceholder` primitive, is already built and tested. Login lands at step 5, not
first: it gates nothing during development and validates nothing about the product.)

## H · Admin UX strategy

**A separate control plane, entered through the same shell.** Verified: SUPER_ADMIN
holds *only* user/role/audit/platform permissions — it cannot open a contract, so
"admin = user UI + extra menu" is structurally false here. Design consequences:

- **Optimize for traceability, not oversight theater.** No KPI dashboard (nothing backs
  one); the two real jobs are *provisioning* (users/roles, with the canonical role
  matrix visible as fixed vocabulary — roles are seeded, never invented in the UI) and
  *tracing* (audit: dense, filterable by the allow-listed fields, request-id as the
  correlation anchor — the same id every error banner shows users).
- **What admin never sees, by design:** legal content. The separation "no super-role
  path to legal authority" (SEC-02) becomes *visible* product shape: the admin area
  simply contains no legal surfaces, which is the honest rendering of the permission
  model rather than a diminished copy of the user app.
- Operational status (preflight, gate states) stays in operator tooling for V1 — a
  status screen would duplicate `preflight`'s register without its authority.

## I · Design system strategy

The foundation exists and is decided — [UI_UX_MASTER_PROMPT.md](UI_UX_MASTER_PROMPT.md)
(two registers; per-axis color namespaces; spacing/type scale; anti-patterns) plus the
implemented tokens in [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md). Component inventory for the
build: shell/nav, panes + collapse tabs, axis pills (existing namespaces), evidence
block + highlight span, citation chip, answer/refusal/routed message types, decision
panel (+conflict freeze), escalation control, `DomainPlaceholder` (built), skeletons
(built), shortcuts help (built), dense table, pager, dialog (one sanctioned use).

**One recorded conflict to resolve before mass build (owner line-item):** the master
prompt names IBM Plex Sans/Mono + Source Serif 4 via Google Fonts, but DD-4 already
ruled out runtime CDN fonts for this product (third-party page-load egress from a
confidential tool) and rule 19 governs the alternative (`next/font` bundling). **Until
the owner approves bundling, implementation stays on the system stack** — the master
prompt's type *roles* (mono for precise values, italic-serif for verbatim quotes) can be
honored with system faces meanwhile. Everything else in the master prompt is buildable
today.

## J · State strategy

Global rules, then the hard cases:

- **Loading** — skeletons matched to final layout (built); analysis progress is only
  ever the lifecycle state re-read (52.7); Ask shows one honest line, never staged
  theater. Anything under ~400ms renders nothing (no flash).
- **Empty** — always says what would fill it and offers the action where one exists.
  First-run Documents is the product's real onboarding: "Upload a contract" *is* the
  tutorial (no tour overlay).
- **Error** — banner + request-id (the audit correlation anchor); a failed load never
  coexists with a perpetual skeleton.
- **Refusal** — the identical sentence, quiet surface, no error styling, regardless of
  cause (`AM-29` r4). The evaluator-routing reply is a distinct third message type.
- **Permission** — absence, not apology (52.3/52.4); whole-section `AccessRestricted`
  is the single sanctioned disclosure level; 404s tell one story: "Not found."
- **Blocked/future** — WORKSPACE_UI_PLAN's disclosure asymmetry, adopted: Domain A/C
  search are *disclosed* placeholders (public product direction); SSO and export are
  *absent* (an unbuilt capability is not advertised). Generated-answer text needs no
  placeholder — the live refusal *is* current production behavior.
- **Conflict (409)** — frozen form until explicit refresh (built, browser-proven).

## K · API-to-UI mapping

Every V1 screen above maps to the frozen 45-operation contract (per-screen column in E);
the full surface-by-area mapping is
[BACKEND_FREEZE_HANDOFF.md §5](../00-project/BACKEND_FREEZE_HANDOFF.md). **Gaps found by
this roadmap — the §19 "smallest justified change" list, none blocking P0:**

1. **Positions search endpoint** — `assist/positions.py` exists (extractive, lexical,
   permission-gated) with **no route**. One `GET` under `configuration.view` unblocks
   the Legal-area search pane. Justified when P2 reaches it; not before.
2. **Cross-review "needs decision" count/list** — would let the Reviews queue lead with
   attention across contracts. *Not requested for V1*: per-review queues satisfy the
   journey; synthesizing the rollup client-side is forbidden (52.7), so it waits until
   real usage proves the need.
3. **Domain C surfaces** — blocked on C-16 material + ingestion, not on any UI decision.

No other screen requires anything the contract lacks.

## L · Risks & unknowns (do not finalize against these)

1. **External-customer access vs `LEGAL-02`** (vision §2 vs the verified grant matrix):
   "everyone queries the same corpus" cannot extend Domain A to non-legal users today —
   positions are confidential by locked rule. **Owner ruling needed before any
   external-facing design**; V1 correctly ships internal-only.
2. **The highlight mechanism** — offsets→DOM mapping over OCR'd/partial text is the one
   unproven interaction; hence build-first (G).
3. **Typography dependency** (I) — owner line-item; system stack meanwhile.
4. **"No modes" router** — a backend capability the IA is shaped for but must not fake;
   the Ask surface absorbs it later without restructure.
5. **Gemini gate & Domain C material** — external inputs; placeholders already designed.
6. **Usability findings** — the five-person plan
   ([USABILITY_TEST_PLAN.md](USABILITY_TEST_PLAN.md)) runs once the P0 spine is
   assembled; its blocker-severity findings outrank this document's layout choices.

## M · Phased roadmap

```text
Phase 0  Discovery + this roadmap                          — DONE (this document)
Phase 1  Foundation gaps: type-conflict ruling (I), shell   ← next
Phase 2  P0 spine, risk-first: doc pane + highlight → findings → ask → landing/intake → login
Phase 3  P1: reviews queue · report · ask history
Phase 4  P2 legal plane: positions browse · configuration lifecycle
Phase 5  P2 admin plane: users/roles · audit
Phase 6  P3 + states sweep: research placeholder, gated surfaces, 404/empty audit
Phase 7  Responsive collapse + accessibility pass (keyboard, SR, contrast, reduced motion)
Phase 8  Usability testing (the 5-person plan) → findings → fixes
Phase 9  UX QA: visual-regression baselines re-cut per screen; legacy screens retire
         one-by-one as each replacement re-pins its Playwright guarantees
```

Vertical slices throughout (§18): each phase lands connected to the real API, tested,
before the next begins. Nothing in Phases 1–9 starts without the owner's go on this
roadmap.
