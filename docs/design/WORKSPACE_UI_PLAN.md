# The workspace UI — Phase-2 design plan for the new interface

**Status: `IN PROGRESS` (design). Governed by [DESIGN.md](../../DESIGN.md); presentation
only — locks nothing.** Prepared 2026-08-27, on the owner's authorization to start the
UI/UX phase in parallel with the AB-5/C-15 decision. Designs against the **frozen API
contract** ([docs/api/openapi.json](../api/openapi.json), 45 operations) and the current
Product Vision — never against the legacy screens, which are `LEGACY UI — DEFERRED`
(preserved and green as the backend-verification harness; reused only where technically
useful).

## Skill inputs, and the conflicts (reported per rule 5, resolved by precedence)

`ui-ux-pro-max` and `frontend-design` were invoked per the standing procedure. Adopted:
density 8/10 (dense-dashboard spacing bias), motion 2/10 (subtle, functional only),
its accessibility checklist (4.5:1 contrast, keyboard everywhere, visible focus,
reduced-motion), "avoid AI purple/pink gradients". **Rejected, DESIGN.md/DD winning**:

| Skill said | Why it loses here |
|---|---|
| "Trust & Authority + Conversion" landing pattern (hero, proof logos, CTA path) | LegalMind has no marketing surface; the workspace is a professional tool, not a funnel |
| Navy/gold brand palette (`#1E3A8A`/`#B45309`) | DESIGN.md: color is a state resource, not a brand one; the existing token palette maps 1:1 to the five axes + two emphasis levels and is settled Phase-1 foundation |
| EB Garamond display face | DESIGN_SYSTEM.md deliberately runs one system stack — a decorative display face competes with evidence text; DD-4's `/login` remains the finish reference |
| GSAP scroll-reveal | No dependency without owner approval (rule 19), and decorative reveal is an anti-pattern here; the only motion is functional transitions ≤200ms respecting `prefers-reduced-motion` |

## What carries over from the legacy frontend (technically useful, not authoritative)

The **token system** (`globals.css` — colors per axis, type scale, spacing, focus ring),
the **axis-separated pill namespaces** (`.badge`/`.status`/`.outcome`/`.tag`), the
security-critical component behaviors pinned by Playwright (confidential omission,
no-optimistic-decision, byte-identical 404 handling), and the API client. The legacy
*layouts* are obsolete for planning; nothing below assumes them.

---

## The one screen that matters: the Review workspace

The product's signature is the evidence chain (DESIGN.md). The new IA makes the chain
**one continuous act of inspection** by putting the document, the verdicts and the chat
in a single three-region workspace instead of the legacy drill-down pages.

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│ topbar: contract name · document type · review lifecycle pill · config snapshot  │
├─────────────────────────┬──────────────────────────────────┬─────────────────────┤
│ DOCUMENT PANE           │ FINDINGS / VERDICTS              │ ASK PANEL           │
│                         │                                  │                     │
│ Evidence rows in        │ Decision queue FIRST (52.5):     │ Conversation list   │
│ reading order           │ evaluations needing a decision,  │ for this contract   │
│ (GET /document-versions │ then the rest grouped by         │ (GET /conversations │
│  /{id}/evidence,        │ Requirement                      │  ?contract_id=…)    │
│  paginated)             │                                  │                     │
│                         │ Each card: classification pill · │ Ask box → POST      │
│ page markers in the     │ rule-outcome pill (separate      │ /conversations/{id} │
│ gutter; a citation or   │ namespaces, never merged) ·      │ /messages           │
│ evaluation click        │ evidence links that SCROLL THE   │                     │
│ scrolls + highlights    │ LEFT PANE, not navigate away     │ Answers cite chunks;│
│ the exact span          │                                  │ a citation click    │
│ (offsets from the       │ Decision control (legal.decision │ highlights the span │
│  evidence rows)         │ holders only — ABSENT otherwise, │ in the left pane    │
│                         │ never greyed) · escalate is a    │                     │
│ index state derived     │ visually distinct request-       │ Refusals render     │
│ from assist_index       │ shaped control                   │ calmly; retrieval   │
│ counts: ready /         │                                  │ scores labeled as   │
│ lexical-only /          │ Decision history inline,         │ retrieval scores;   │
│ not indexed             │ superseded shown in place        │ the word            │
│                         │                                  │ "confidence" never  │
│                         │                                  │ renders             │
├─────────────────────────┴──────────────────────────────────┴─────────────────────┤
│ Collapse behavior: ≥1280px three panes · ≥900px document+one tab pane (Findings /│
│ Ask as tabs) · below: single pane, tabbed. A collapsed pane is a labelled tab —  │
│ state columns are never silently dropped (DESIGN.md § Responsive).              │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**The cross-pane highlight is the signature interaction.** Verdict → evidence and
citation → evidence use the same mechanism (evidence row offsets), so the rules engine's
chain and the assist lane's grounding read as the same gesture: *point at the text*.
It costs no new endpoint — the evidence rows already carry page and offsets.

## Second-order screens (mapped to the frozen contract, in build order)

| Screen | Contract surface | Notes |
|---|---|---|
| 1 · Contracts list + intake | `GET/POST /contracts`, `POST .../document-versions` | Declared document type is a required, prominent choice (never inferred); `assist_index` renders as a calm readiness note |
| 2 · Review workspace | above | The core deliverable |
| 3 · Ask home | `GET /conversations` | A document's history; creator-only by contract, so no sharing affordances exist |
| 4 · Configuration | requirements/standards/publish | Browse Domain A *as configuration* (available today); draft/publish for `configuration.draft/publish` holders |
| 5 · Audit + admin | `/audit-events`, users/roles | Dense tables, real table semantics |
| 6 · Login/session | auth ops | DD-4 finish reference carries over |

## Blocked/gated surfaces — designed as placeholders from day one

One shared primitive (`DomainPlaceholder`) renders every owner-gated surface as a
**calm, labelled, deliberate state** — bordered panel, plain language, no lock icons,
no urgency, no "coming soon" marketing tone:

| Surface | Placeholder copy (plain, factual) | Unblocks when |
|---|---|---|
| Positions search pane | "Search across approved positions isn't available yet. Approved positions can be browsed under Configuration." | AM-32 approved (C-15) |
| Statute search pane | "Statute search isn't available yet — the statute texts haven't been supplied." | C-16 material + AM-32 |
| Generated answer text | Not a placeholder — the live refusal state *is* production behavior; the panel already renders it | AM-31 gate opens |
| SSO button | Absent entirely (a capability the deployment lacks is not disclosed) | OIDC approval + RIAAS details |
| Report export | Absent from the report screen (formats NOT YET SPECIFIED) | Export formats specified |

Note the asymmetry, which is deliberate: Domain A/C search panes are *disclosed*
placeholders (their existence is public product direction), while SSO and export are
*absent* (52.4's absence discipline — no affordance disclosing an unbuilt capability).

## What Phase 2 explicitly does not do

No Tailwind, shadcn or any dependency (rule 19 — unchanged). No client-side legal
logic, no confidence figures, no severity inventions (rules 7/12/18). No deletion or
migration of legacy screens — they retire only as each new screen replaces them with
its Playwright coverage carried over or re-pinned.

## Build sequence from here

1. **`DomainPlaceholder` primitive + tests** — done with this plan (the one component
   both blocked panes and future gated surfaces share).
2. Workspace shell: three-region layout + collapse behavior, empty panes.
3. Document pane on `/evidence` + highlight mechanism.
4. Findings pane: decision queue, axis pills, decision/escalate controls (re-pinning
   the legacy Playwright guarantees as each lands).
5. Ask pane: conversation list + replayed citations wired to the highlight mechanism.
6. Screens 1, 3–6.

Each step re-runs typecheck, Vitest and the browser suite before the next.
