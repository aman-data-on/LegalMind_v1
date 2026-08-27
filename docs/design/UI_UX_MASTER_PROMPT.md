# The LegalMind UI/UX Master Prompt

**Status: `DECIDED` — owner directive, 2026-08-27: full R&D pass, prior UI/UX decisions cancelled,
rebuilt from research.** This document is designed to be handed whole to a developer or an AI
implementer as a single, self-contained build brief. It **supersedes** `DD-1` through `DD-5` in
[DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) (marked there, not deleted — see `DD-6`) and is now the
authoritative source for visual/interaction decisions. [DESIGN.md](../../DESIGN.md)'s *principles*
section is retained almost entirely (it derives from locked product rules, not taste); this
document replaces its unfinished IA question (`DD-1`) and its fragmented identity (`DD-2`–`DD-5`)
with one finished system, and extends it to cover the assist/AI surface that didn't exist when
`DESIGN.md` was written.

**What this document is not:** a specification of legal behavior, a Company Standard, a Legal
Rule, or an amendment to any locked decision. It governs presentation only. Where it is silent or
in tension with `CLAUDE.md` rules 1–23, `CLAUDE.md` wins, and the conflict gets reported, not
silently resolved.

**Build against:** [docs/api/openapi.json](../api/openapi.json) — the frozen, drift-tested 45-operation
contract — and [BACKEND_FREEZE_HANDOFF.md](../00-project/BACKEND_FREEZE_HANDOFF.md) §5–6 for exactly
what's stable versus placeholder-only today.

---

## 0 — Read this first: what changed and why

A research pass (`ui-ux-pro-max` design-system search, cross-checked against this repo's own
locked constraints) found two real defects in the prior design work, not just stylistic
disagreements:

1. **Split identity.** `/login` received an elaborate deep-navy glass treatment (floating
   geometry, backdrop blur, ambient motion); every other screen stayed a plain light shell. The
   first thing a user sees doesn't match the tool they then use all day. **Fixed:** one identity,
   applied everywhere, no separate "moment" page.
2. **The core workflow layout was never finished.** The prior design log explicitly left the
   Review screen's list/detail structure as "a proposal, not a decision." **Fixed:** decided below,
   finalized, no longer provisional.

A third gap — no plan for the new AI assist surface — isn't a defect, it's just new: `AB-3`/`AB-4`
landed after the old design work. This document designs it from scratch, deliberately distinct
from the legal-authority surface it sits beside.

**Explicitly rejected from generic AI-assistant UX conventions, and why** (found via
`ui-ux-pro-max --domain ux "AI chat citation grounded"`, then overridden against this product's
actual constraints):

- **Token-by-token streaming** — rejected. Every claim is verified against its source *before*
  display (`guardrails.py`); streaming raw model output would show unverified text mid-stream,
  which is exactly what the citation guardrail exists to prevent. Show a deliberate
  "checking sources" state instead — see §5.
- **Thumbs-up/down feedback** — rejected. It implies the system tunes itself on preference, which
  contradicts the deterministic framing and the assist lane's explicit no-fine-tuning posture. Use
  the product's real escalation concept instead of importing a generic chat widget.
- **AI-generated-content labeling** — kept; already required (rule 12, `AI-03`) and correct.

---

## 1 — Product context (for an implementer with zero prior context)

LegalMind is an **internal** legal-document review tool, not a marketing product. There is no
signup funnel, no pricing page, no conversion goal — every screen serves someone already inside
the organization doing one of two jobs:

**A. Ruling** — a Legal Reviewer/Admin compares a contract against the organization's approved
position and either confirms a match or rules on a deviation. This path is deterministic, rule-
engine-produced, and legally consequential. **Zero tolerance is the live policy**: any deviation
routes to a human, nothing is auto-approved. Expect most work here to be *deciding*, not browsing.

**B. Asking** — anyone with access can ask a plain-language question about an uploaded document
and get an answer grounded in retrieved, cited text — or an honest "not found." This path is
assistive, never authoritative, and structurally incapable of producing a legal verdict.

**These two jobs must never visually blur into each other.** A cited AI answer and a ruled Legal
Decision are different kinds of object with different authority, and the design's central job is
making that difference legible at a glance, not just true in the data model.

---

## 2 — Non-negotiables (locked; restated only as pointers, never re-derived)

- The UI implements no legal logic and never computes a classification, rule outcome, or
  `requires_decision` client-side — every such value is rendered exactly as received (52.7).
- Permission gating is presentation only; the server authorizes everything regardless (47.6).
- A confidential field the caller lacks `legal_position.view` for is **simply absent** — no lock
  icon, no greyed placeholder, no "restricted" label (`LEGAL-02`, 52.4).
- An out-of-scope object renders **identically** to a nonexistent one (`API-10`, 49.5).
- No optimistic UI for a Legal Decision; a `409` is shown, never silently retried or overwritten
  (52.7).
- No confidence percentage, risk score, or traffic-light rollup anywhere, ever (rule 12, `AI-03`).
  A "retrieval score" is a plain number, never color-coded, never called confidence.
- The five legal state axes (Mapping State, Finding Classification, Rule Outcome, Legal Decision,
  Review Lifecycle) and the assist lane's sixth axis (`ANSWERED` / `NO_EVIDENCE_RETRIEVED` /
  `EVIDENCE_INSUFFICIENT` / `CLAIM_UNSUPPORTED`) are separate vocabularies and must never share a
  visual channel, a badge component, or a color scale.
- `RESOLVED ≠ MATCH`; `DEVIATION ≠ error`. Never style a factual comparison result as if it were a
  problem.
- The identical refusal sentence renders for every assist refusal cause, on a quiet surface, never
  styled as an error.

---

## 3 — Information architecture (finalized — supersedes `DD-1`'s open proposal)

**One persistent shell, everywhere:**

```
┌─────────────────────────────────────────────────────────────────────┐
│  SHELL (dark ink, 56px)  wordmark · contract switcher · nav · user   │  ← identity lives here only
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   FINDINGS LIST          FINDING DETAIL              ASK (drawer)    │
│   (bounded, ~340px)      (fills remaining width)      (420px,        │
│   default filter:                                     closed until   │
│   "needs a decision"     Evidence → Fact → Standard    invoked)      │
│   toggle: "all"          → Rule → Result, decision                   │
│   compact rows:          controls at Evaluation level,               │
│   classification +       decision history inline                    │
│   rule-outcome chips +                                               │
│   attention marker                                                  │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

- **Shell** is the one dark surface in the entire product — no other page gets a separate visual
  "identity moment." Contains: small wordmark, the current Contract/Document switcher, primary nav
  (Contracts · Reviews · Configuration · Audit · Admin, each permission-gated by absence), session
  menu. This is the single carryover from the old `/login` work worth keeping (`DD-5` correctly
  identified this half).
- **Findings list** (left, bounded width, internally scrollable) — this finalizes the old `DD-1`
  proposal: Direction B's structural navigation (bounded list, persistent detail, scales past
  hundreds of Findings) with Direction C's default framing (list defaults to `requires_decision`
  items, not creation order — because the zero-tolerance policy makes that the actual common case).
  An explicit, equally-weighted "All Findings" toggle sits at the top of the list, never hidden or
  demoted — a non-Legal `USER` role's primary need is browsing, and it must not feel like a second-
  class view of a "real" queue built for Legal.
- **Detail pane** (center) — the full evidence chain for the selected row. URL-addressable
  selection (a Finding is linkable/shareable). Keyboard `j`/`k` or arrow-key next/previous through
  the filtered list without a page navigation, for the repeat professional user reviewing dozens a
  day.
- **Ask drawer** (right, closed by default, opened by an explicit control) — never a modal, never
  displaces the center pane. Scoped to whatever document is currently open. Persists per document
  via the existing conversation API (`GET /conversations?contract_id=`). Closing it loses no state
  — reopening replays the conversation via citation-replay, already built.
- **Narrow viewport** (below ~1024px): the three regions become three full-width sequential views
  — list → detail → ask — with a persistent back affordance. This product's primary context is a
  desk, not a phone (`DESIGN.md` §Responsive, correctly established, kept); tablet-width is the
  floor to design for, not phone-width.

**One evidence viewer, used by both jobs.** A citation from a Finding's evidence list and a
citation from an Ask answer resolve to the *same* viewer component, scrolled to the same page/
offset (now possible: `GET /document-versions/{id}/evidence` carries page numbers and character
offsets). Do not build two different "show me the source" experiences — this is the single biggest
synthesis opportunity between the legal-review path and the new assist path, and skipping it would
mean re-solving the same problem twice.

---

## 4 — Visual system

### 4.1 — The two registers (the central design idea)

Everything in the **Ruling** path (Findings, Evaluations, Decisions, Configuration, Audit) reads as
**Authority**: structured, tabular, chip-and-border driven, sans-serif throughout, the five-axis
colors live only here. Everything in the **Asking** path (the Ask drawer, any answer text, any
citation excerpt) reads as **Inquiry**: quieter, deliberately colorless except for plain neutrals,
answer prose set with a serif for verbatim quotes specifically. A user should be able to tell which
register they're in with peripheral vision alone, before reading a word — because mistaking one for
the other is the one confusion this product cannot afford.

### 4.2 — Color

Refine, don't discard, the existing restrained instinct (`--success`/`--attention`/`--error`/
`--indeterminate`/`--accent` in `globals.css`) — it already resists decorating with color. The
correction is **rigor of separation**: `DESIGN.md` itself requires the five axes never share a
channel, and value-clustering (one color per *meaning*, e.g. "success" reused for any positive-
sounding value across axes) risks exactly that conflation over time as more screens are built. Fix:
one dedicated, low-saturation hue **namespace** per axis — still used only on small chips/pills,
never as a background, never decorative, so the palette stays calm even though it's now provably
separated rather than separated by convention.

| Axis | Hue | Reasoning |
|---|---|---|
| Mapping State | cyan `#0E7490` | Neutral/mechanical — "did the system find a match" is not a judgment |
| Finding Classification | indigo `#4338CA` | What a provision factually *is* — deliberately unlike the outcome hue below, so a reader can't conflate "what it is" with "what should happen" |
| Rule Outcome | amber `#B45309` | The axis that actually carries attention (`APPROVAL_REQUIRED`/`UNACCEPTABLE`) — giving attention its own axis's hue, rather than a separate ad hoc "warning color," ties urgency to the real field that means it |
| Legal Decision | forest `#15803D` | The one place an earned, settled "green" belongs — an actual completed human ruling, not a system verdict. Never used for `MATCH` (a factual result, not a decision) |
| Review Lifecycle | ink-neutral, no hue | Process, not judgment — deliberately the quietest axis, communicated by label/icon, not color, so it never competes with the four content axes |
| Assist answer state (6th axis) | **no color at all** | See §4.3 — the Inquiry register is colorless by design |
| Error/destructive | `#DC2626` | Reserved for actual errors (failed request, `409` conflict) — never for `DEVIATION`, which is not an error |

Neutral/chrome family (cool, slightly blue-shifted so it reads as "instrument," not "default grey"):

```
--ink-900 #0E1420   primary text / shell background
--ink-700 #2B3444   secondary text
--ink-500 #5B6478   muted / tertiary text
--ink-300 #A8AFBD   borders on light surfaces
--ink-100 #E4E7ED   hairlines, subtle fills
--paper   #FAFBFC   page background
--surface #FFFFFF   cards/panels on paper
--shell   #131826   the one persistent dark chrome surface
--accent  #1B4F9C   the one non-state accent — links, focus ring, primary buttons (kept from the existing token; it already clears AA on white)
```

Each axis hue gets a paired `-bg` tint at ~8–10% for the chip fill, exactly the existing
`--success`/`--success-bg` pattern — don't invent a new pairing convention, extend the one already
in `globals.css`.

### 4.3 — Typography

Reject two defaults: `ui-ux-pro-max`'s own top "legal" match (EB Garamond/Lato — reads as a law
*firm's* marketing brochure, wrong register for a dense tool used all day); and a generic
Inter-everywhere SaaS default (no functional reason to prefer it here). Three faces, each doing a
distinct, non-decorative job:

| Face | Role | Why |
|---|---|---|
| **IBM Plex Sans** | All UI chrome, labels, body, headings | Built for dense data-heavy interfaces; distinct geometric-humanist character without reading as ornamental |
| **IBM Plex Mono** | Case/version/requirement codes, evidence offsets, section refs, timestamps, retrieval scores | A real functional signal: mono type means "this is a precise, machine-tracked value," everywhere it appears |
| **Source Serif 4, italic** | Verbatim quoted clause/evidence text **only** — in the evidence viewer and inside Ask answers | The single functional use of a second typeface in the whole product: it tells the eye "this exact text came from the document," instantly and without a label, in both the Ruling and Asking registers alike |

No other face anywhere. No display/marketing type at any size — the largest heading in the product
stays under 30px; there is no hero, no landing page, nothing sized for persuasion.

```
--text-xs   12px   badges, table headers, footnote refs
--text-sm   13px   secondary metadata, captions
--text-base 15px   body, table cells
--text-md   16px   labels, h3
--text-lg   19px   h2
--text-xl   24px   h1 (page/task heading — task first, product name is chrome, per the sound half of old DD-2)
```

### 4.4 — Spacing & density

Density is a feature here, not a defect to hide (`DESIGN.md`, correctly established, kept). Scale:
`4 · 8 · 12 · 16 · 24 · 32 · 48`. No oversized hero padding anywhere. Tables and evidence text get
horizontal scroll inside a bounded container rather than destructive column-hiding — never drop a
column that carries state on a narrow viewport.

### 4.5 — Surfaces & motion

Flat, bordered surfaces only — the existing `--line`/`--surface` hairline approach is correct and
stays. No glassmorphism, no gradients, no floating/drifting decorative geometry anywhere,
**including `/login`** — the old deep-navy identity page is retired specifically because it broke
this rule while every other page followed it. Motion is functional only: focus/hover transitions
(150–200ms), a `409`/error banner fade-in, the Ask drawer's open/close slide, an `aria-live`
"checking sources" state (§5). Nothing decorative, nothing that isn't communicating a real state
change. `prefers-reduced-motion` removes all of it without losing any information — every motion
has a static equivalent.

---

## 5 — The Ask surface, specifically

- **Entry point:** a quiet, always-visible "Ask" control on any document view — never buried, never
  a floating chat bubble (that pattern belongs to consumer products with no other primary task).
- **While retrieving/verifying:** show what's actually happening, not a generic spinner — a short
  sequence ("Searching the document…" → "Checking citations…") tied to the real pipeline stages,
  `aria-live="polite"`. This is deliberately not streamed model text (see §0) — the wait is short
  (retrieval + verification, not long-form generation) and is more trustworthy shown honestly than
  hidden or faked with a typewriter effect.
- **An answer:** serif-italic for the verbatim-adjacent parts, sans for the connecting prose,
  numbered citation markers `[1]` `[2]` inline, each resolving to the shared evidence viewer.
  Retrieval score renders as a plain mono number next to its citation — never a bar, never a color,
  never the word "confidence."
- **A refusal:** the single locked sentence, rendered on the same quiet surface as a normal answer
  — same background, same weight, no red, no icon, no "error" framing. It is the system working
  correctly, not failing.
- **No thumbs-up/down.** If a user thinks an answer is wrong, the existing product concept for
  "a human needs to look at this" is escalation — surface a plain "Flag for review" affordance that
  reuses that real mechanism, rather than a generic AI feedback widget that implies the model
  retrains on preference (it doesn't, and the product's own rules forbid implying otherwise).
- **Compliance-shaped questions** ("does this meet our standard?") are already routed server-side to
  the evaluator with a pointer, never answered generatively — render that pointer plainly, as a
  distinct message type from a normal answer, not styled as a refusal or an error.

---

## 6 — Placeholder surfaces (build these visibly incomplete, never fake-functional)

Four areas are backend-blocked today (`BACKEND_FREEZE_HANDOFF.md` §6). Build their UI shape now so
no rework is needed later, but never let them look operational:

1. **Domain A/C search** (approved-positions and statute search) — show the intended entry point,
   disabled, with plain text explaining it's not yet available. Domain A *browsing* (the 32 ratified
   standards as configuration) is already live via `/requirements` — that's a real, working screen,
   not a placeholder.
2. **Single sign-on** — the existing "Sign in with Google" link pattern (an honest link to the real,
   not-yet-implemented OIDC route) is the right precedent: never fabricate a working-looking control
   for a route that 404s.
3. **Report export** — same treatment: visible, labeled, disabled, no fake download.
4. **Generated-answer text** — no placeholder needed; the refusal state *is* production behavior
   today, not a stand-in for it.

---

## 7 — Accessibility floor (build to this now; a later target is verification, not retrofit)

Keyboard-operable everything, visible focus never suppressed; state conveyed by text/icon, never
color alone; form errors bound to their field programmatically; real `<table>` semantics for
tabular data, not styled divs; disclosure widgets use real semantic patterns; loading/busy states
announced via `aria-live`, not only shown visually; 4.5:1 minimum contrast on all text.

---

## 8 — Anti-patterns (do not do these without a new, explicit, documented override)

Generic dashboard stat cards with a synthesized number · sidebar+header+card-grid adopted by
convention rather than because it fits this product's linear drill-down · rounded-everything,
heavy shadows, glassmorphism, gradients · purple/blue "AI product" aesthetics, sparkle icons, or
anything implying a result is probabilistic · confidence percentages or risk scores of any kind ·
a lock icon or greyed row standing in for an omitted confidential field · one merged badge mixing
two state axes · shimmer/bounce/confetti decorative animation · a modal for anything short of a
genuine interruption · escalation and decision rendered as interchangeable buttons · client-side
recomputation of any server-derived value · token-streamed unverified AI text · thumbs-up/down
feedback widgets.

---

## 9 — Build sequence

1. Tokens (§4.2–4.4) into `globals.css`, additive — do not remove working selectors before their
   replacements are verified against the existing 62 Vitest + 27 Playwright specs.
2. Shell (§3) — one persistent dark bar, replacing the current fragmented per-page chrome.
3. Findings list + detail pane (§3) — the finalized `DD-1` layout; reuse `FindingCard` /
   `EvaluationRow` / `EvidenceList` / `DecisionPanel` / `DecisionHistory` internals, replace their
   containing shell.
4. Shared evidence viewer component, consumed by both the detail pane and Ask citations.
5. Ask drawer (§5), wired to the existing conversation API — no backend change required.
6. Placeholder surfaces (§6).
7. Retire the `/login` deep-navy treatment; rebuild it inside the same one-identity system as every
   other page (task-first heading, real controls only, shell-dark limited to the persistent bar).

Every step re-runs the existing test suites before proceeding — this document changes presentation,
not the API contract or any locked behavior, so nothing here should require a backend change or
break an existing assertion. If one breaks, the assertion was pinned to old markup, not to a locked
behavior — fix the test's selector, never the underlying rule it protects.
