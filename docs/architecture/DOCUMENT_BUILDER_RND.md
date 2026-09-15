# Template-Driven Document Builder — R&D and Recommendation

`PROPOSAL` — 2026-09-15. Nothing in this document is locked, decides nothing, and authorizes no
build. It sits alongside [AI_RAG_ARCHITECTURE_RND.md](AI_RAG_ARCHITECTURE_RND.md) as forward-looking
architecture research, distinct from the locked specifications in [05-architecture/](../05-architecture/).
Per rule 4, implementation may not begin from this document alone — it requires an explicit owner
decision on placement, MVP scope, and (separately, per rule 21) real approved output templates,
which do not yet exist in the repository in any structured form (see §16, §23).

Grounding method: two read-only research passes over the live repository (backend, frontend) on
2026-09-15, cited by file path throughout. Nothing below assumes a capability, library, or table that
was not directly confirmed to exist (or confirmed absent) in that pass.

---

## 1. Problem statement

Every document LegalMind currently handles arrives from *outside* the system: a counterparty's MSA,
a signed NDA, an SLA — uploaded, parsed, and measured against a Company Standard. There is no path
in the other direction. When the organization itself needs to *issue* a new MSA or NDA, a user
today has no tool inside LegalMind for that — the platform is a reviewer, not an author.

The ask is a bounded authoring tool: pick an approved template for a document type, supply only the
deal-specific variable fields the template permits, see the customized result, and receive a draft
PDF — never a free-form "write me a contract" generator, and never a workflow that lets a user or an
LLM edit the organization's protected legal positions. The analogy the request gives — a student ID
card template where only name/roll number/course change — is exact: the fixed layout is not
negotiable, only the named blanks are.

This is a strictly harder problem than it looks, for one reason the codebase makes very visible: an
"approved template" for a legal agreement is not currently a repository artifact. The 40 ratified
files under `backend/config/company_standards/` (§5, §19 below) encode the organization's *required
positions* for review purposes ("liability capped at 12 months of total fees") — they do not encode
approved *output prose* ("Section 13. Limitation of Liability. In no event shall either party's
aggregate liability exceed…"). Those are different artifacts serving different purposes, and only
the first exists today. §16 and §23 return to this as the standing blocker.

---

## 2. Recommended product placement

**The owner's initial preference — Document Builder as the main workflow, Ask AI as an entry
point/assistant — is correct, and the codebase already argues for it independently.**

Three lines of evidence, from the research pass rather than from first principles:

1. **The existing Ask AI lane has a hard architectural ceiling that generation must not cross.**
   `legalmind/assist/routing.py` and `intent.py` are built entirely around *answering questions*
   — `Domain = DOCUMENT | POSITIONS | STATUTES`, all retrieval-and-cite. `ask()`
   (`legalmind/assist/service.py:575`) has exactly one output shape: a grounded, cited textual
   answer. Building document generation as an Ask AI capability would mean growing a fourth
   domain whose "answer" is a legal artifact, right beside AM-25's explicit list of things the
   assist lane must never produce (a Finding, an Evaluation, a Legal Decision, an organizational
   position). That is a fundamentally different risk class from citing evidence, and rule 10
   already draws this line — Document Builder as a separate workflow keeps generation observably
   outside the assist lane's determinism-exempt but still-bounded surface, rather than laundering
   it through the surface that answers "what does our MSA say."
2. **A conversational interface is the wrong shape for a form with locked fields.** The whole
   point of the template model (§5) is that most of the document is *not* open to negotiation
   through prose. A chat box invites "can you also remove the liability cap" — which must always
   be refused — whereas a form with a field that simply isn't there structurally cannot be asked.
   `UploadContract.tsx`'s intake pattern (checklist stages, no free text) is closer to the right
   shape than `AskDock.tsx`'s chat pattern.
3. **The existing "workflow inside Ask AI" precedent already redirects rather than absorbing.**
   The closest analogue in the current codebase to "detect intent, hand off to a purpose-built
   flow" is the citation-click handoff in `AskDock.tsx` (open the right document version, scroll
   to evidence) and the Finding's "Ask about this" `askIntent` seed (open the dock, prefill,
   never auto-send). Both patterns *open a specific surface and prefill it* rather than trying to
   do the target task inline. That is precisely the hybrid this document recommends for Ask AI →
   Document Builder (§9) — not a novel pattern, the same one already in production for a smaller
   case.

**Recommendation: a separate top-level Document Builder section** (a new `/dashboard/builder`
route, alongside Dashboard/Reviews/Legal/Ask in `navItemsFor`, `src/components/workspace/model.ts`),
gated by a new permission (§19), with Ask AI acting purely as a **detector and redirector** (§9) —
never a second implementation of the same flow. This is a hybrid of the options offered, but it is
not "hybrid" in the sense of splitting the workflow across two surfaces: the workflow lives in
exactly one place, and Ask AI's only job is routing a user there with the document type pre-selected.

Rejected alternatives and why:

| Option | Why not primary |
|---|---|
| Workflow inside **Documents**/Dashboard | The Dashboard's data model is "an uploaded contract with a status" (`Contract`/`DocumentVersion`, `dashboard/page.tsx`). A generated draft is authored, not uploaded, and conflating the two list views risks exactly the RESOLVED≠MATCH-style category error rule 14 exists to prevent — a generated draft is not "a contract we received," and a table built for the latter will keep implying it is one. |
| Workflow inside **Ask AI** | Covered above — wrong interaction shape, wrong risk boundary. |
| Hybrid with generation logic split across both | Two implementations of "fill a template" (one in a wizard, one in a chat loop) is the two-competing-implementations failure mode the working-alongside-other-sessions section of CLAUDE.md warns about, applied to product surfaces instead of code. |

---

## 3. User journeys

### 3.1 Primary journey — direct entry (matches the request's 12-step flow)

1. User opens **Document Builder** (new nav item, permission-gated).
2. Template picker: shows only document types with at least one **PUBLISHED** template
   (§5) — an approved-not-yet-published or draft template is invisible here, mirroring how a DRAFT
   Company Standard never reaches the evaluator (§19's `TemplateVersion.status`).
3. Selecting MSA shows the template's name, version, effective date, and approval status
   (`TemplateVersion` header fields, §6) — a direct parallel to how `dashboard/page.tsx` shows a
   contract's declared type and status today.
4. LegalMind reads the `TemplateDefinition` (§5, §6) and renders:
   - Fixed sections, shown but not editable.
   - Variable fields, grouped and labeled, each carrying required/optional and a validation rule.
   - Conditional sections, shown as togglable **only where the template itself declares them
     togglable** (§5) — never inferred from the user's answers by an LLM.
5. User fills the form. Given the codebase's actual form pattern (§8: plain controlled state, no
   form library anywhere in `frontend/`), this is a `useState`-per-field form validated by a pure
   function, following `StandardForm.tsx`'s and `EditContractDialog`'s existing shape — not a new
   library.
6. Client-side validation runs the same rules the server will re-run (client is a UX affordance
   per rule 18 — the server is authoritative).
7. Live preview renders the filled template as structured HTML (§10) — the same "server-rendered
   structured content" pattern `DocumentPane.tsx`'s Text view already uses for uploaded documents,
   not a PDF re-render on every keystroke.
8. User reviews the preview inline.
9. The preview visually distinguishes: user-supplied values (a subtle highlight, reusing the
   existing `data-evidence-id`-style inline-marker pattern from `DocumentPane.tsx`), fields still
   empty/invalid (an explicit "missing" treatment — never silently blank, echoing rule 15's
   fail-closed posture applied to a form instead of an evaluator), and any conditional section
   currently enabled.
10. User corrects fields inline; the preview re-renders from state, no round-trip needed for
    plain substitution (§10).
11. On "Generate draft," the server re-validates, renders the final document via the chosen
    backend renderer (§10), and returns a real PDF (and, if requested, DOCX) — reusing
    `export_render.py`'s renderer pair rather than inventing a third.
12. The PDF (and every on-screen preview) carries a persistent **"Draft — pending legal/business
    approval"** marker (§13) — a new visual treatment; nothing today plays this role (§8 confirms
    no watermark/draft-stamp component exists anywhere in the frontend).

### 3.2 Secondary journey — Ask AI entry (§9 covers the mechanics)

1. User asks Ask AI, in English or Hindi/Hinglish per the examples given, "Mujhe ek MSA banana
   hai."
2. Ask AI's intent layer recognizes a generation request for a supported type with a published
   template.
3. Ask AI responds with a short, non-committal sentence and a single action button — "Start MSA
   draft" — never attempting the fill itself.
4. Clicking the button navigates to `/dashboard/builder?type=MSA`, pre-selecting the template the
   way a citation click pre-selects a document version today.
5. From here the flow is identical to §3.1 step 4 onward. Ask AI does not carry any conversational
   context into the builder form — no field is ever pre-filled from a chat message (§10's
   prompt-injection concern in §11 is exactly why: a field value must always be something the user
   typed into a form field, never a string that arrived via a generation prompt).

### 3.3 Tertiary journey — general question, no generation intent

"NDA kya hota hai?" gets Ask AI's ordinary grounded-answer treatment (§7's existing `Domain`
routing, unchanged), with an *optional* suggestion appended only if a published NDA template
exists — never a redirect, since the user did not ask to create anything.

### 3.4 Explicitly out of scope for redirection

"Mere existing MSA ko Constitution ke against check karo" must **never** route to Document Builder
— it is a review request against an uploaded document, and stays on the existing review path
unchanged (§9 defines the exact intent boundary).

---

## 4. UX wireflow, in plain language

```
┌─ Document Builder ───────────────────────────────────────────────┐
│ [Template picker: MSA card, NDA card, TOS card, …]                │
│  each card: name · version · "Published <date>" · doc type icon   │
└─────────────────────────────────────────────────────────────────┘
                │  select MSA
                ▼
┌─ Template header ─────────────────────────────────────────────────┐
│ MSA — Template v3 — Published 2026-08-20 — DRAFT PDF ONLY badge   │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─ Two-pane builder (mirrors the AM-57 document/side-panel split) ──┐
│  LEFT: variable-field form, grouped by section          RIGHT:    │
│   • Required fields marked, validated inline             Live     │
│   • Conditional sections as checkboxes (template-gated)   preview │
│   • Fields the template marks "needs owner/legal          (HTML,  │
│     approval to change" show a lock icon + a note          fixed  │
│     instead of an input (§5)                               text   │
│                                                             + user │
│                                                             values │
│                                                             high-  │
│                                                             lighted)│
└─────────────────────────────────────────────────────────────────┘
                │  all required fields valid
                ▼
┌─ Review step ──────────────────────────────────────────────────────┐
│ Change summary: "8 fields set, 2 conditional sections enabled"     │
│ Missing/invalid list (if any) — generation stays disabled          │
│ [Generate draft PDF]  [Generate draft DOCX]                        │
└─────────────────────────────────────────────────────────────────┘
                │
                ▼
┌─ Draft ready ───────────────────────────────────────────────────────┐
│ PDF preview (iframe, same pattern as DocumentPane's Original view) │
│ Watermark: "DRAFT — pending legal/business approval" on every page  │
│ [Download]  [Edit fields]  [Discard draft]                          │
│ Audit line: generated by <user>, from Template v3, at <timestamp>   │
└─────────────────────────────────────────────────────────────────┘
```

No step implies the document is legally approved by existing. That claim is never made anywhere in
this flow (§12, §13).

---

## 5. Template architecture

### 5.1 Can an uploaded DOCX/PDF be customized directly by text replacement?

**No — and the research pass confirms the codebase already treats this exact question
correctly for a different purpose.** Two independent findings:

- `legalmind/ingestion/storage.py` write-once objects (§backend research) are chmod'd read-only
  after write — the storage layer has no update primitive at all. Even mechanically, "open the
  uploaded DOCX and replace some runs" is not a supported operation on stored bytes; you would
  regenerate a new object, not mutate one.
- More fundamentally: naive text substitution into a real DOCX/PDF is unreliable for reasons
  independent of this codebase — text can be split across multiple runs by the original editor's
  formatting, `{{placeholder}}` tokens can straddle run boundaries invisibly, page-break and
  numbering fields are position-relative not content-relative, and a PDF has no reliable notion of
  "the same field" across a regenerated layout at all. This is exactly the failure mode the task
  description warns against, and it is a correct warning: a system that "replaces text in the
  uploaded file" will intermittently corrupt formatting or silently miss a placeholder split across
  runs, with no error raised.

**Recommendation: a structured template definition, not a customized copy of an original file.**
The template is authored once, as data (§5.2), and every generated document is rendered fresh from
that structured definition plus the user's field values — never as an edited copy of anyone's
uploaded DOCX. This mirrors `export_render.py`'s existing `Block` model precisely: one canonical
content representation, rendered by more than one output renderer, never edited in place.

### 5.2 Recommended template representation: an ordered Block list

Reuse the shape already proven in `legalmind/api/export_render.py` (`Block` dataclass: `kind`,
`text`, `label`) and extend it with two new block behaviors:

```
TemplateBlock =
  | FixedBlock(kind: h1|h2|h3|p|kv|quote|note, text: str)                 # protected, verbatim
  | FieldBlock(kind: ..., field_key: str, prefix: str, suffix: str)       # one placeholder inline
  | ConditionalBlock(section_key: str, blocks: list[TemplateBlock])       # shown iff enabled
```

A `FieldBlock` is how `{{customer_legal_name}}` is represented: not a string search-and-replace
target inside a paragraph, but a distinct block whose rendered form is `prefix + value + suffix`
(e.g. prefix `"This Agreement is entered into by "`, field, suffix `", a company incorporated
under…"`). This sidesteps the run-splitting problem in §5.1 entirely, because there is never a raw
`{{token}}` string sitting inside a paragraph of the *rendered* output to search for — the
placeholder only exists in the *template definition*, as structure, and is resolved before any
text is emitted.

A `ConditionalBlock` is the only mechanism by which an optional schedule/appendix can appear at
all — never an LLM's judgment call, never a keyword the user typed. It is a template-authored
boolean gate, presented to the user as a checkbox exactly where the template says one is allowed.

### 5.3 Fixed / protected content

Everything not wrapped in a `FieldBlock` or inside an enabled `ConditionalBlock`'s optional part is
`FixedBlock` — rendered verbatim, never touched by user input, never touched by an LLM. Per the
task's own list, this covers: confidentiality wording, liability limitations, indemnity language,
IP protections, Constitution-mandated requirements, required notices/disclaimers. The template
author (not the end user, not a runtime LLM) is the only one who can turn a `FixedBlock` into a
`FieldBlock` — and only at template-authoring/versioning time (§6), which is itself
permission-gated and produces a new `TemplateVersion` (append-only, §6).

**How this actually prevents "remove the liability cap" / "make confidentiality one year"
(the task's explicit example):** structurally, not by content filtering. There is no code path
in the runtime generation flow that accepts free text describing what to change — the only inputs
accepted are `{field_key: value}` pairs for the `FieldBlock`s and `{section_key: bool}` pairs for
`ConditionalBlock`s that the *selected template version* actually declares. A request naming a
`field_key` the template doesn't have, or attempting to set a value on a block classified as fixed,
is rejected the same way `legalmind/assist/generation.py`'s `_forbidden_payload_check` rejects a
payload naming an internal legal-position field — not "the LLM refused," but "the field doesn't
exist as an input the server will accept." No LLM sits in the runtime rendering path at all (§10),
so there is nothing for an injected instruction to persuade.

### 5.4 Editable variable fields

Each `FieldBlock`'s field is declared once, at template-authoring time, with: `field_key`, label,
`field_type` (`text | long_text | date | currency | number | select | party_name | address`),
required/optional, a validation rule (regex, min/max, date-range, enum for `select`), an optional
default value, and — critically, per the task — an `approval_required: bool` flag. A field with
`approval_required: true` (e.g. a fee floor near a Constitution-adjacent boundary) renders in the
form as **read-only with a note**, not as an editable input a user can simply type over; changing
it requires the same kind of explicit authorization step §13's approval workflow already needs for
anything touching a protected position — this is a template-declared property, never inferred at
runtime.

### 5.5 Conditional sections

Declared per template as a named `section_key` with a human label ("Data Processing Schedule"),
default-enabled/disabled, and (optionally) its own nested fields that only apply when enabled. The
task's examples — support schedule, DPA schedule, security appendix, order-form section, special
annexure — are all representable this way. A template may declare zero conditional sections (a
short NDA, say) — nothing forces the concept to be used.

### 5.6 What a `TemplateDefinition` needs to hold (data-model preview; full shape in §6/§19)

| Field | Purpose |
|---|---|
| `template_id` | Stable identity across versions |
| `document_type` | One of the ten `legalmind/domain/document_types.py` values |
| `version` | Monotonic per `template_id`, immutable once published |
| `approval_status` | `DRAFT \| APPROVED \| PUBLISHED \| RETIRED` (§6) |
| `effective_date` | When this version becomes the one offered to users |
| `source_reference` | Provenance: who approved it, and against what real document, never invented (rule 21) |
| `blocks` | The ordered `TemplateBlock` tree (§5.2) |
| `fields` | Field declarations for every `field_key` referenced by a `FieldBlock` (§5.4) |
| `conditional_sections` | Declarations for every `section_key` (§5.5) |
| `constitution_refs` | Which Constitution section/topic each protected block traces to (§12) |
| `output_formats` | Which renderers are valid for this template (`pdf`, `docx`) |
| `change_history` | Append-only list of prior versions and what changed (mirrors `RequirementVersion`) |

---

## 6. Data model proposal

Follows the existing versioned-entity pattern used for Requirements/Company Standards
(`legalmind/db/models.py`: `Requirement` → `RequirementVersion`, `ConfigurationSnapshot` pinning a
set of versions) rather than inventing a new pattern. Full DDL-level detail belongs in §19; this is
the conceptual shape.

```
Template                     (stable identity: id, document_type, created_by, created_at)
  └─ TemplateVersion          (id, template_id, version_no, status, effective_date,
                                source_reference, blocks JSONB, fields JSONB,
                                conditional_sections JSONB, constitution_refs JSONB,
                                output_formats, approved_by, approved_at)
       └─ (immutable once status leaves DRAFT — mirrors RequirementVersion)

GeneratedDocument             (id, template_version_id, contract_id NULL,
                                created_by, created_at, status)
  └─ GeneratedDocumentField    (generated_document_id, field_key, value, value_type)
  └─ GeneratedDocumentSection  (generated_document_id, section_key, enabled)
  └─ GeneratedDocumentArtifact (id, generated_document_id, format [pdf|docx],
                                 storage_key, rendered_at, rendered_by)
```

Notes:

- `TemplateVersion.status` mirrors the Company Standard lifecycle already in use conceptually
  (`ratified`/`proposed`/`retired` per `docs/02-legal-domain/COMPANY_STANDARDS.md`'s provenance
  vocabulary) — reuse the vocabulary rather than inventing a parallel one, adjusted to
  `DRAFT | APPROVED | PUBLISHED | RETIRED` because a template additionally needs an
  "approved but not yet the one users see" state distinct from a Company Standard's simpler
  ratified/not-ratified split (a template can be legally approved before a business decision to
  make it the active default).
- `GeneratedDocument` deliberately has **no `contracts` foreign key requirement** (nullable) —
  a draft may be generated before any contract record exists yet (e.g., drafting an NDA to send to
  a prospective counterparty who has no `Contract` row). If the user later uploads the executed
  version, that's a new, ordinary `Contract`/`DocumentVersion` upload — generation and review stay
  two separate object graphs, exactly as §2 argues they should be two separate *workflows*.
- `GeneratedDocumentArtifact` reuses the existing `storage_key` pattern from `DocumentVersion`
  (`legalmind/db/models.py:299`) and the same write-once `StorageBackend` (§backend research §1) —
  no second storage abstraction.
- No new table is needed for "fixed clause text" separately from `TemplateVersion.blocks` — the
  Block JSON already carries fixed content inline, matching how `Company Standard` JSON files
  already carry an entire configuration in one JSONB blob rather than being split across dozens of
  narrow tables (§backend research §3). Consistent with the existing C-13 tradeoff already accepted
  for document types.

---

## 7. Backend architecture

New module: `legalmind/builder/` (sibling to `legalmind/assist/`, `legalmind/evaluation/`,
`legalmind/ingestion/`), so the domain boundary in `SYSTEM_ARCHITECTURE.md` gets one new bounded
module rather than logic smeared across existing ones (rule 19 — no new *service*, this stays
inside the existing modular monolith).

```
legalmind/builder/
  templates.py     # CRUD + versioning for Template/TemplateVersion (admin/legal-authoring side)
  validation.py     # pure functions: validate submitted field values against TemplateVersion.fields
  render.py          # build_generation_model() -> reuses export_render.Block-rendering machinery
  service.py          # orchestrates: load TemplateVersion -> validate fields -> render -> store artifact
```

- `render.py` deliberately **extends `export_render.py`'s existing block-rendering functions rather
  than duplicating them** — the `render_pdf`/`render_docx` pair already takes a `list[Block]` and
  produces bytes; the builder's job is only to turn a `TemplateVersion` + submitted field values
  into that same `list[Block]` shape (substituting `FieldBlock`s, expanding enabled
  `ConditionalBlock`s), then hand off to the renderer that already exists. This is the direct
  "no new dependency" (rule 19) answer to §10.
- **No LLM in `service.py`'s runtime path.** Per rule 9/AI-01/rule 10, and per §5.3's structural
  argument, generation is pure deterministic substitution — same inputs (a `TemplateVersion` id +
  field values) always produce the same output bytes. This gives the builder a determinism
  property for free, for the same reason the authoritative analysis lane has one.
- **Where an LLM legitimately helps, and only there:** template *authoring*. When legal/admin
  staff are setting up a new `TemplateVersion` from an approved source document, `templates.py`'s
  admin-only authoring UI may call `legalmind/assist/generation.generate_raw()` (the existing
  single egress seam, §backend research §7) with a new `prompt_version` to *suggest* candidate
  `field_key` boundaries in a pasted source document ("this looks like a party-name blank," "this
  looks like a fee amount") — exactly the "LLM-based field discovery may assist an admin during
  setup" mode the research questions call for. The suggestion is never auto-accepted: an admin
  reviews and confirms every suggested field before it becomes part of a `TemplateVersion`, the
  same verbatim-confirm posture AM-54 already requires of the (structurally similar) semantic
  recognition step in the review path. This reuses the egress gate, payload hashing, and
  prompt-versioning machinery already built for that seam — no new network path (rule 19).
- **Guard/permission pattern**: `service.py` handlers take `Guard` via `Depends(get_guard)`
  exactly like every existing router (§backend research §5, §10). New permissions (§19):
  `template.manage` (author/version a template — admin/legal only), `template.publish` (move a
  version to PUBLISHED — a heavier bar than `manage`, mirroring `configuration.publish`'s existing
  separation of authoring from activation), `document.generate` (fill a published template and
  produce a draft — the everyday-user permission), `document.generate.override_protected`
  (change an `approval_required` field — gated like `legal.approve_customization`, never
  IdP-provisioned, per the `NEVER_PROVISIONED_BY_IDP` pattern already enforced for
  `legal.decision`/`legal.approve_customization`).
- **Audit**: every `TemplateVersion` publish and every `GeneratedDocument` creation/artifact
  render writes an `AuditEvent` (existing append-only table, §backend research §9) — no new audit
  mechanism.

---

## 8. Frontend screens and states

New route: `frontend/src/app/dashboard/builder/page.tsx` (and `/builder/[templateId]/page.tsx` for
the fill flow), living under the AM-57 `/dashboard` tree and consuming the **`--ws-*`** token set
from `workspace.css` — not the legacy `globals.css` tokens (§frontend research §10's explicit
finding that these are two different, non-interchangeable token sets, and a new page under
`/dashboard` must use the workspace ones).

Screens/states, each named because the frontend research pass found no existing component to
reuse for it outright — the honest inventory of what is genuinely new work:

| Screen/state | Reuses | Genuinely new |
|---|---|---|
| Template picker (cards) | `TableCard`/card patterns already in `Primitives.tsx` | Card grid layout itself |
| Field-fill form | `useState`-per-field + pure `validate*` function pattern from `StandardForm.tsx`/`EditContractDialog` (§frontend research §6) — **no react-hook-form/zod, none exists in this codebase and none should be introduced for this alone** | The field-type-driven renderer (one input component per `field_type`) |
| Stepper/progress | **Nothing to reuse** — confirmed no wizard/stepper component exists anywhere (§frontend research §5). Closest precedent is `UploadContract.tsx`'s linear `Stage` checklist, which is a progress display, not a back/forward wizard | A genuine multi-step wizard component, new |
| Live preview pane | `DocumentPane.tsx`'s "Text view" pattern (server-rendered structured HTML, evidence-row-like blocks) — **not** the "Original" iframe-PDF view, since there is no file yet to embed | The field-substitution highlighting (`data-field-key` markers, parallel to `data-evidence-id`) |
| Draft-ready / PDF result | `ExportControl.tsx`'s blob-download pattern (§frontend research §7) for the actual generate-and-download action | **The watermark/"Draft — pending approval" treatment — confirmed to not exist anywhere in the UI today** (§frontend research §8); this needs a genuine new visual design pass |
| Async generation status (if rendering is not instant) | The polling pattern from `findingsState.tsx`/`WorkspacePage.tsx` (`window.setTimeout`/`setInterval` bounded loop, §frontend research §7) | None — this one reuses cleanly |
| Permission gating (nav item, "Generate" button, protected-field lock icon) | `useSession().can()` + `PermissionGate`/`AccessRestricted` (§frontend research §9) — same flat string-permission check as everywhere else | None — this one also reuses cleanly |

**Per the standing CLAUDE.md UI/UX rule, this is unambiguously UI/UX work** (new screens, a new
wizard pattern, a new watermark treatment) and must go through `ui-ux-pro-max`/`frontend-design`
(and `dataviz` if any progress/summary visualization is added) **before any markup is written**,
not after — flagged here so a future implementation session does not skip it. The DD-4 finish bar
(memory: visual finish bar) applies to this from the first pass, same as everything else shipped
since 2026-08-21.

---

## 9. Ask AI integration

Extend `legalmind/assist/intent.py` with one new lexical/heuristic detector,
`is_generation_request(question)` — pattern-matched the same way `is_comparison_question`,
`is_statute_question`, etc. already are (§backend research §8: **all existing intent detection is
lexical/heuristic, never LLM-based** — this stays consistent with that, not a new LLM classification
step). It should recognize both English and Hindi/Hinglish phrasing patterns for "create/draft/make
a [document type]" against the ten known `document_types.py` values plus their common transliterated
forms ("banana hai," "prepare karna hai").

`legalmind/assist/routing.py`'s `plan()` gets one new branch, checked before the existing
`Domain` routing: if `is_generation_request()` matches **and** a `TemplateVersion` with
`status = PUBLISHED` exists for the detected type **and** the caller holds `document.generate`,
return a new response shape — `routed_to_builder` — carrying just the detected `document_type` and
template id, no free text passed through. This is a sibling to the existing `routed_to_evaluator`
shape (§frontend research §4: `WsAnswerView` already renders three shapes; this adds a fourth) —
**not** a call into `generate_raw()` at all, because nothing needs generating: it's a lookup
(does a published template exist for this type?) plus a permission check, both already-solved
problems.

Frontend: `AskDock.tsx`'s `WsAnswerView` gets one more render branch mirroring the existing
`ComparisonHandoff` component — a short sentence plus a single button, "Start MSA draft," which
navigates to `/dashboard/builder?type=MSA` (§3.2). This is the same "prefill and hand off, never
auto-act" discipline the codebase already applies to `SUGGESTED_QUESTIONS` chips and the
`askIntent` Finding hand-off (§frontend research §4) — extended to a navigation hand-off instead of
a text-prefill hand-off.

Behavior table, matching the task's exact examples:

| User says | Ask AI does |
|---|---|
| "Mujhe ek MSA banana hai" | Detects generation intent, MSA has a published template → `routed_to_builder`, "Start MSA draft" button |
| "Mujhe Constitution ke according NDA prepare karna hai" | Same — the "ke according Constitution" clause doesn't change the routing; Constitution alignment is a template-authoring-time property (§12), not something Ask AI can honor per-request |
| "NDA kya hota hai?" | Ordinary `ANSWERED`/grounded-explanation shape (existing, unchanged); *optionally* appends "Create an NDA from an approved template" as a secondary action if a published NDA template exists — informational, never forced |
| "Mere existing MSA ko Constitution ke against check karo" | No generation intent detected (the verb is "check," an existing-document review verb) → stays on the existing `routed_to_evaluator`/document-Q&A path, unchanged |
| Type has no published template yet | No generation branch fires at all — Ask AI falls through to its ordinary answer, same as if the feature didn't exist. Never claims a template exists when it doesn't. |

If a generation-intent question also asks something answerable ("NDA banana hai, isme confidentiality clause kitne saal ki hoti hai?") the routing plan can carry **both** the `routed_to_builder` hint and fall through to the ordinary answer for the informational half — this needs no new mechanism beyond returning both, since `plan()` already returns a list of domains plus a fallback list rather than a single verdict.

---

## 10. Document-generation technology comparison

| Approach | Verdict | Why |
|---|---|---|
| **DOCX template replacement** (`docxtpl`/Jinja2-in-DOCX) | Not recommended | New dependency (rule 19 requires approval for this specifically); also reintroduces the run-splitting fragility of §5.1 for anything beyond simple `{{tag}}` substitution in unstyled runs |
| **HTML/CSS → PDF** | **Recommended — already the pattern in production** | `export_render.py`'s `render_pdf` already does exactly this via `pymupdf.Story(html=...)` + `DocumentWriter`, paginated onto A4, with headers/footers/page-numbering handled by the `Story` API. Zero new dependencies. |
| **Structured document rendering (Block model)** | **Recommended — the template representation itself, §5.2** | This *is* the mechanism, not an alternative to the row above — the Block tree is rendered by feeding assembled HTML into the existing `pymupdf.Story` pipeline for PDF, and by walking blocks into `python-docx` `Document()` calls for DOCX, exactly mirroring `render_docx`'s existing approach. |
| **LibreOffice-based conversion** (`soffice --headless --convert-to pdf`) | Not recommended for V1 | No existing dependency on a LibreOffice subprocess anywhere in the repo; would add an external process dependency and a new failure mode (subprocess timeouts, container/base-image requirements) that `pymupdf`'s in-process `Story` API doesn't have. Worth revisiting only if a future requirement needs full DOCX-fidelity round-tripping the Block model can't express (e.g. tracked changes) — not needed for a fixed-template draft generator. |
| **External API-based generation service** (any hosted "document assembly" SaaS) | Rejected outright | Sends the complete agreement and deal-specific data to a third party — exactly what the task's constraints forbid, and a different order of exposure than the assist lane's single, narrowly-scoped Gemini egress seam (§backend research §7), which never receives full documents, only short evidence spans. |

**Concrete elements from the task's list, mapped to the recommended pipeline:**

| Requirement | How the recommended pipeline covers it |
|---|---|
| Page breaks, headers/footers, numbering | `pymupdf.Story`'s existing CSS-driven pagination (`_PDF_CSS` in `export_render.py`) — extend the stylesheet, don't replace the mechanism |
| Tables | HTML `<table>` inside the assembled Story markup; `python-docx` table API for DOCX |
| Signatures | A `FixedBlock`/`FieldBlock` pair for signatory name/title/date — an actual wet-ink or e-signature integration is explicitly out of scope for a *draft* generator (§14) |
| Defined terms, cross-references | Represented as ordinary `FieldBlock`/`FixedBlock` content; a cross-reference to a section number is fragile if section numbering is itself dynamic — recommend defined-term and section-number values be computed once during rendering (not hand-typed by the user) so a reordered conditional section can't silently produce "see Section 7" pointing at the wrong place |
| Annexures/schedules | `ConditionalBlock` trees (§5.5), each schedule its own nested block list |
| Long service descriptions, multi-page agreements | No inherent limit in the Block/Story approach — it's the same pipeline already producing multi-page review exports today |
| Version tracking | `TemplateVersion` (§6) for the template; a `GeneratedDocument` row per generation event, immutable once its artifact is rendered |

All of this runs **on existing infrastructure, with zero new third-party services and zero new
Python dependencies** — the strongest form of the task's "must work on our own infrastructure"
requirement, satisfied by reuse rather than by a new self-hosted service.

---

## 11. Security and legal-safety risks

| Risk | Mitigation |
|---|---|
| **Prompt injection via a field value** (e.g. a "service description" field containing text engineered to look like an instruction) | Moot for the *rendering* path, because rendering is pure string substitution with no LLM in the loop (§7) — there is no prompt for injected text to hijack. It remains a live concern only for the **template-authoring assist** (§7's admin-side field-discovery suggestion), where the existing `_forbidden_payload_check`/payload-hashing/verbatim-confirm machinery in `legalmind/assist/generation.py` already applies unchanged. |
| **Malicious text in a long-text field (HTML/script injection into the rendered preview)** | The live preview renders as HTML (§8); every field value must be escaped exactly as `export_render.py`'s `_blocks_to_html` already escapes text before embedding it (`escaped-text-only`, §backend research §6) — reuse that helper, don't write a second escaping path. |
| **Attempting to set a value on a protected/fixed block** | Rejected at the API boundary: `validation.py` only accepts `field_key`s the selected `TemplateVersion` actually declares as editable; an unknown or `approval_required` key without the override permission is a 4xx, never a silent no-op, never a partial render (fail-closed, rule 15's spirit applied to a form). |
| **Unauthorized template editing / version changes** | `template.manage`/`template.publish` permissions (§7, §19), enforced server-side via `Guard`, same as every other write path — never a client-side gate. |
| **Sensitive data leakage in a generated draft** | Confidential-field omission (SEC-07/LEGAL-02) already means *omitted, not nulled* in every existing serializer (§frontend research §8); the builder's preview/export must follow the same discipline — a field the caller lacks permission to see (e.g. an internal fee floor default) must never appear pre-filled, only ever entered explicitly by an authorized user. |
| **External API exposure** | None — no external call exists anywhere in the runtime generation path (§7, §10); the only network egress in the entire feature is the already-audited, already-gated admin-authoring assist call, reusing the existing single seam. |
| **PDF/DOCX generation vulnerabilities** (e.g. XML entity expansion in DOCX, malformed-input crashes) | `python-docx`/`pymupdf` are already vetted, in-production dependencies (§backend research §6) — no new attack surface from a new library; the builder only ever *writes* documents from internally-constructed data, it never *parses* an untrusted uploaded file the way ingestion does, so the entire OCR/parsing threat surface is not applicable here. |
| **Hidden metadata / internal file paths in generated output** | `python-docx`/`pymupdf` document properties (author, application name, file paths) must be explicitly scrubbed/set to neutral values at render time — `export_render.py` should be checked for whether it already does this (not confirmed in the research pass; flagged as a concrete pre-implementation check, not assumed either way). |
| **A user submitting a field value shaped like a legal instruction** ("Effective date: N/A, and also waive the liability cap") | The value is stored and rendered as literal text inside the field's declared slot — e.g. it becomes the *content* of the effective-date blank, not a directive the system interprets. Because there is no LLM reading field values as instructions anywhere in the render path, this degrades to "the user typed something odd into a date field," which ordinary field-type validation (§5.4, e.g. a `date` field type rejecting non-date input) already catches — not a security bypass, a validation error. |

---

## 12. Constitution-alignment workflow

Reusing exactly the pattern already proven for Company Standards (§backend research §4): the
Constitution is **never chunked or retrieved** for this feature either. A `TemplateVersion`
declares its `constitution_refs` (§5.6) — which section/topic of
`docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md` each protected `FixedBlock` traces to — the
same structural pointer style a Company Standard's `configuration.constitution` block already
uses, not a live lookup against the document text.

**Five distinct concepts, kept separate per the task's own framing (and per rule 14's general
discipline against conflating adjacent-but-different states):**

| Concept | What it means | Who/what asserts it |
|---|---|---|
| **Template validity** | The `TemplateDefinition` is well-formed — every `FieldBlock` has a matching field declaration, every `ConditionalBlock` a matching section declaration, no orphaned references | Server-side schema validation at publish time (`templates.py`) |
| **Constitution alignment** | The template's protected blocks are checked, at authoring/review time, against the Constitution sections they claim to implement — a human (legal/admin) confirms the mapping is accurate; the system can only *display* the cited section for review, never verify semantic correctness itself | A human reviewer, shown the `constitution_refs` panel |
| **Business-field completion** | All required variable fields for a given generation have valid values | `validation.py`, at generation time, per instance |
| **Legal approval** | An authorized person has signed off that this `TemplateVersion` is fit to offer to users at all | `TemplateVersion.approval_status = APPROVED`, a template-level, one-time act |
| **Final document approval** | A *specific generated draft* (this deal, these field values) has been approved for use — separate from the template being approved, because a validly-completed form can still describe a deal the business doesn't want to proceed with | Out of scope for generation itself; belongs to whatever downstream approval process the organization runs before a draft is actually sent (§13, §15) |

If a template's `constitution_refs` for a protected block is empty, or names a Constitution section
that a reviewer cannot find covered, the authoring UI must show exactly the sentence the task
specifies:

> No clear Company Standard found — owner/legal review required.

— reusing the same *fail-closed, say-so-explicitly* posture as `NOT_APPLICABLE` in the evaluator
(rule 15), applied to template authoring instead of review.

**What this workflow must never do**, matching the task's explicit constraints: never assert a
generated document is "legally approved" merely because it rendered without validation errors
(§13 makes this the load-bearing distinction); never let a template silently substitute weaker
wording than its declared Constitution section requires — an authoring-time check, not a runtime
one, since by the time a user is filling a published template the protected content is fixed.

---

## 13. Approval and audit workflow

Every item in the task's checklist maps onto the model already built for §6:

| Item | Supported by |
|---|---|
| Draft status | `GeneratedDocument.status` (`DRAFT` is the only status a V1 generation ever reaches — see §14) |
| Preview before generation | §3.1 step 7-10, no artifact created until "Generate" is explicitly clicked |
| Field-level editing | The form itself; re-editing after a draft exists creates a **new** `GeneratedDocument` version rather than mutating the rendered artifact (write-once storage, §6) |
| Change summary | A diff between the current field values and the template's declared defaults, computed the same way `StandardForm.tsx` already shows "what changed" against stored values (§frontend research §6) |
| Protected-clause warning | Rendered inline wherever a `field.approval_required` block appears (§5.4) — a lock icon + explanatory note, not a silent disable |
| Constitution reference panel | §12's `constitution_refs`, surfaced read-only in the builder UI |
| Reviewer comments | Not modeled in V1 (§15) — no comment table proposed; if wanted, it is additive later without touching the core model |
| Legal/business approval | `TemplateVersion.approval_status` for the template; a *document-level* approval is explicitly deferred to §15 as a distinct, later capability — V1 produces drafts for human approval **outside** the tool (e.g. the existing review/decision machinery, or an out-of-band process), never an in-tool "approve" button that could be mistaken for the real thing |
| Version history | `TemplateVersion` chain (append-only) + `GeneratedDocument` rows per generation event |
| Regeneration after field changes | A new `GeneratedDocument`/`GeneratedDocumentArtifact`, never an edit to the old one — matches the immutable-version discipline already enforced everywhere else in this codebase (rule 16, rule 17) |
| Audit logs | Existing `AuditEvent` table, one event per template publish and per document generation (§7) |
| Final approval status | Deliberately **absent** from V1's data model — see next paragraph |

**The single most important guarantee this section exists to state plainly:** *PDF generation must
never imply legal approval.* Concretely, this means `GeneratedDocument` has no
`APPROVED`/`REJECTED` status value in V1 at all — only `DRAFT` — so there is no field anywhere in
the system that could be misread as "Legal signed off on this." The watermark (§3.1 step 12, §8) is
the only approval-adjacent signal a generated document carries, and it says the opposite: pending,
not approved. If a real in-tool approval step is wanted later, it is a deliberate, separately
-scoped Phase 2 decision (§15) — not something that should back into existence as a side effect of
adding a status enum value early.

---

## 14. Recommended MVP

| In scope | Rationale |
|---|---|
| **Two document types**: NDA and MSA | NDA is the structurally simplest (fewest conditional sections, per the existing Clause Catalogue's own count — 8 ratified NDA standards vs. 15 for MSA); MSA is the type named first in every example in the task and in CLAUDE.md's own worked examples, so it validates the harder case (conditional schedules, more protected blocks) early |
| One `TemplateVersion` per type, versioned, with a real publish/approve lifecycle | §6 |
| Explicit variable fields, typed and validated (§5.4) | Core requirement |
| Protected/fixed clauses, structurally un-editable (§5.3) | Core requirement — this is the feature's entire legal-safety premise |
| Required-field validation, server-authoritative | Rule 18 |
| Constitution-reference display (read-only, §12) | Cheap to build once `constitution_refs` exists on the template, and it is the thing that makes "approved template" mean something more than "a form" |
| Live HTML preview (§8, §10) | Core UX requirement from the task |
| Draft PDF generation, watermarked (§3.1, §13) | Core requirement |
| Audit trail (reuse `AuditEvent`) | Already free — no new mechanism |
| Ask AI entry point (detect + redirect only, §9) | Cheap once the builder exists; the redirect logic is small |
| No free-form generation anywhere | Non-negotiable per the task and per rule 10 |
| DOCX export | `render.py` reuses `export_render.py`'s existing DOCX renderer — marginal cost once PDF works |

| Postponed to later phases | Why |
|---|---|
| In-tool document-level approval workflow (a real `APPROVED` status, sign-off UI) | §13 — deliberately deferred so V1 cannot be mistaken for a legal-approval system |
| Reviewer comments on a draft | No existing comment primitive anywhere in the codebase to extend; net-new |
| E-signature integration | A different, larger integration surface, explicitly out of the task's stated scope ("generate a draft PDF") |
| More than two document types (TOS, SLA, DPA, Order Form, Amendment, …) | Each new type needs its own real approved source template supplied by the owner/legal (rule 21) — this is a content-supply bottleneck, not an engineering one; adding types is mechanically cheap once NDA/MSA prove the pipeline |
| LLM-assisted template authoring (§7's admin-side field-discovery suggestion) | Valuable but genuinely optional for V1 — an admin can hand-author the first two templates' Block trees directly; add the assist once the manual path is proven |
| Regeneration/diffing UI beyond a simple "start a new draft" | Nice-to-have, not blocking |
| Cross-reference/defined-term auto-numbering across arbitrarily reordered conditional sections | §10 flags the correctness risk; V1 can accept a simpler constraint (fixed section order, conditional sections only ever appended, never reordered) and revisit if that constraint turns out to bind |
| A dedicated stepper/wizard design-system component broadly reused elsewhere | Build the one this feature needs; generalize later only if a second feature actually wants it (YAGNI) |

---

## 15. Future-phase scope

- Real in-tool approval workflow for a specific generated draft (distinct from template approval).
- Additional document types as real source templates are supplied (rule 21 gates each one).
- Reviewer comment threads on a draft, if the business process actually needs asynchronous review
  rather than the existing out-of-band approval most legal teams already run.
- E-signature handoff (a real external integration, requiring its own security review and explicit
  approval per rule 19).
- LLM-assisted authoring tooling maturing from "suggest field boundaries" to "suggest which
  Constitution section a new protected clause maps to" — still admin-facing, still confirm-only.
- Template analytics (which fields are most often left at default, which conditional sections are
  rarely enabled) — informs future template revisions, never feeds back into runtime behavior
  automatically.
- Possibly generalizing the wizard/stepper component if a second unrelated feature independently
  needs one.

---

## 16. Risks and unresolved questions

**The load-bearing blocker, restated plainly:** *no approved output template exists yet, for any
document type, in any form.* The six-plus-six documents under `legal-docs/` (D1-D6 and the second
tranche, per CLAUDE.md's Source material table) are LeapSwitch's own **outbound reference
documents** — real contracts used to derive the organization's required *positions* (the Company
Standards, §5.6's `source_reference` concern) — not vetted, ready-to-issue template prose with
blanks marked out. Building even the NDA/MSA MVP template's `blocks` requires the owner/legal to
supply (or explicitly designate from the existing six-plus-six, and mark up) the actual approved
wording, with the fixed/variable boundary decided by them — never inferred, drafted, or
"reasonably assumed" by an implementation session (rule 21, rule 7). **This should be raised to the
owner as a concrete request before any template-authoring work begins**, not discovered mid-build.

Other open questions, none of which this document resolves:

- **Placement of the new permission tier.** `document.generate` clearly belongs to ordinary users
  (the department-scoped `USER` role generates its own drafts, matching the existing "USER sees the
  legal position on its own deals" precedent from AB-12) — but does `template.manage`/
  `template.publish` belong to `DEPARTMENT_LEAD`, or does it need a legal-specific grant
  independent of the four existing personas? AB-12's RBAC redesign didn't anticipate a
  template-authoring role, and this document doesn't decide whether it should reuse
  `DEPARTMENT_LEAD` or introduce a fifth grant — flagged for the owner.
- **Whether `GeneratedDocument` should ever become a `Contract`.** If a generated draft is sent,
  signed, and comes back executed, does the flow expect the user to separately upload the executed
  version as a brand-new `Contract` (this document's assumption, §6), or should there be an
  explicit "this draft became this contract" link? Left open; the simpler assumption is taken for
  V1 to avoid inventing a relationship the task didn't ask for.
- **Multi-department template ownership.** If Department A and Department B both use MSA but want
  slightly different default fee terms, is that a template variant, a field default override, or
  out of scope entirely? Not addressed by the task's examples; flagged rather than guessed at.
- **Whether the DOCX renderer's fidelity is acceptable for a real signature-ready document**, given
  it currently produces plain, unstyled `python-docx` output (§backend research §6) with no
  template-level styling (fonts, letterhead, footer text) beyond what `export_render.py` already
  implements for review exports — a legal MSA likely needs letterhead/styling the current DOCX
  renderer doesn't attempt. This is a real gap between "renders correctly" and "looks like an
  MSA," not addressed by this proposal, and worth a design pass before committing to python-docx's
  current minimal styling as sufficient.
- **Retention/lifecycle of unused drafts.** No policy proposed for how long a `DRAFT`
  `GeneratedDocument` a user never downloads or discards should live — plausibly the same regime as
  everything else (append-only, never auto-deleted, AB-17's real-delete endpoint available if
  wanted), but not decided here.

---

## 17. Recommended implementation phases

1. **Phase 0 — source material.** Owner supplies/designates approved NDA and MSA template source
   text with the fixed/variable boundary marked (rule 21). Nothing in Phase 1 can start without
   this.
2. **Phase 1 — data model + backend core.** `Template`/`TemplateVersion`/`GeneratedDocument*`
   tables and migration (§6, §19); `legalmind/builder/` module (§7); manual (admin-authored, no
   LLM) NDA `TemplateVersion` hand-encoded as a first real fixture, exercised end-to-end via API
   tests before any UI exists.
3. **Phase 2 — generation + rendering.** `render.py` extending `export_render.py`; PDF/DOCX output
   for the NDA template; validation; audit wiring.
4. **Phase 3 — frontend builder UI.** Template picker, field-fill wizard, live preview, draft-ready
   screen with watermark — through the `ui-ux-pro-max`/`frontend-design` design pass (§8) before
   markup.
5. **Phase 4 — MSA template**, exercising conditional sections and `approval_required` fields for
   the first time (NDA is unlikely to need either extensively).
6. **Phase 5 — Ask AI integration** (§9) — smallest phase, additive, no risk to the core flow if
   deferred.
7. **Phase 6 — hardening**: security review pass specifically against §11's table, golden-corpus
   -style fixtures for the renderer (does the same template + same fields always produce
   byte-identical output?), load/perf check on `pymupdf.Story` for a long MSA with several
   schedules enabled.

Each phase should ship independently reviewable — this document does not assume all six happen in
one PR or one session.

---

## 18. Acceptance criteria

- A user without `document.generate` cannot reach the builder's fill screen (403, not merely a
  hidden nav item) — object-level, not presentation-only (rule 18).
- Selecting a template with `approval_status != PUBLISHED` is impossible from the picker, and
  requesting it directly by id returns a byte-identical-shaped denial to a nonexistent template
  (SEC-07's existing 404-parity discipline extended here).
- No API request can set a value for a `field_key` not declared on the selected `TemplateVersion`,
  nor toggle a `section_key` not declared as conditional — verified by a test that attempts exactly
  this and expects a 4xx.
- No API request can change an `approval_required` field's value without
  `document.generate.override_protected` — verified the same way.
- The same `(template_version_id, field values, enabled sections)` tuple always renders
  byte-identical PDF and DOCX output across repeated calls (determinism — the property rule 9
  demands of the authoritative lane, deliberately extended here even though generation is not
  itself part of that lane).
- Every generated PDF/DOCX visibly carries the draft watermark on every page — verified by an
  automated check on the rendered output, not just a UI screenshot.
- No network call occurs during runtime generation (assertable via the same import-boundary test
  pattern `tests/test_import_boundaries.py` already uses to keep `legalmind/assist/generation.py`
  the only egress point — the builder's `render.py`/`service.py` must appear nowhere in
  `EGRESS_ALLOWED`).
- `AuditEvent` rows exist for every `TemplateVersion` publish and every `GeneratedDocument`
  creation, queryable by actor and timestamp.
- Ask AI's generation-intent detection never fires for a type with no published template, and
  never fires for an existing-document review question (§9's behavior table, each row a test case).

---

## 19. Required database changes

New Alembic migration, following the existing versioned-entity + append-only pattern
(`legalmind/db/models.py`, §backend research §9):

```sql
CREATE TABLE templates (
    id UUID PRIMARY KEY,
    document_type TEXT NOT NULL,          -- one of legalmind.domain.document_types values
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE template_versions (
    id UUID PRIMARY KEY,
    template_id UUID NOT NULL REFERENCES templates(id),
    version_no INTEGER NOT NULL,
    status TEXT NOT NULL,                 -- DRAFT | APPROVED | PUBLISHED | RETIRED
    effective_date DATE,
    source_reference JSONB NOT NULL,       -- provenance: who approved, against what real document
    blocks JSONB NOT NULL,                 -- TemplateBlock tree, §5.2
    fields JSONB NOT NULL,                 -- field declarations, §5.4
    conditional_sections JSONB NOT NULL,   -- §5.5
    constitution_refs JSONB NOT NULL,      -- §12
    output_formats TEXT[] NOT NULL,
    approved_by UUID REFERENCES users(id),
    approved_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (template_id, version_no)
);

CREATE TABLE generated_documents (
    id UUID PRIMARY KEY,
    template_version_id UUID NOT NULL REFERENCES template_versions(id),
    contract_id UUID NULL REFERENCES contracts(id),   -- nullable, §6
    created_by UUID NOT NULL REFERENCES users(id),
    department_id UUID NOT NULL REFERENCES departments(id),  -- for scope-based visibility, mirrors contracts
    status TEXT NOT NULL DEFAULT 'DRAFT',  -- DRAFT only in V1, §13
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE generated_document_fields (
    generated_document_id UUID NOT NULL REFERENCES generated_documents(id),
    field_key TEXT NOT NULL,
    value TEXT,
    PRIMARY KEY (generated_document_id, field_key)
);

CREATE TABLE generated_document_sections (
    generated_document_id UUID NOT NULL REFERENCES generated_documents(id),
    section_key TEXT NOT NULL,
    enabled BOOLEAN NOT NULL,
    PRIMARY KEY (generated_document_id, section_key)
);

CREATE TABLE generated_document_artifacts (
    id UUID PRIMARY KEY,
    generated_document_id UUID NOT NULL REFERENCES generated_documents(id),
    format TEXT NOT NULL,                 -- pdf | docx
    storage_key TEXT NOT NULL,            -- same StorageBackend as document_versions
    rendered_by UUID NOT NULL REFERENCES users(id),
    rendered_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

New permission catalogue entries in `legalmind/security/permissions.py`'s `CATALOGUE`:
`template.manage`, `template.publish`, `document.generate`,
`document.generate.override_protected` (the last added to `LEGAL_AUTHORITY_PERMISSIONS`'s
`NEVER_PROVISIONED_BY_IDP` set alongside `legal.decision`/`legal.approve_customization`).

No changes proposed to any existing table. This is additive-only, consistent with the append-only
discipline the rest of the schema already follows.

---

## 20. Required API endpoints

Following the existing router-per-resource, `Guard`-based pattern (`legalmind/api/routers/*.py`):

```
GET    /api/v1/templates                         list published templates (picker)
GET    /api/v1/templates/{id}/versions           version history (template.manage)
POST   /api/v1/templates                          create a new Template + first DRAFT version (template.manage)
PATCH  /api/v1/templates/{id}/versions/{v}         edit a DRAFT version only (template.manage)
POST   /api/v1/templates/{id}/versions/{v}/approve approve a version (legal-authority-equivalent gate)
POST   /api/v1/templates/{id}/versions/{v}/publish  publish an approved version (template.publish)

POST   /api/v1/generated-documents                start a draft: {template_version_id} (document.generate)
PATCH  /api/v1/generated-documents/{id}/fields      set field values (document.generate; rejects unknown/protected keys)
PATCH  /api/v1/generated-documents/{id}/sections    toggle conditional sections (document.generate)
GET    /api/v1/generated-documents/{id}/preview     structured HTML preview (document.generate)
POST   /api/v1/generated-documents/{id}/render      produce a PDF/DOCX artifact (document.generate)
GET    /api/v1/generated-documents/{id}/artifacts/{artifact_id}  download bytes (document.generate, own/department scope)
GET    /api/v1/generated-documents                list own/department drafts (scope param, mirrors contracts)
```

All list endpoints support the existing `scope=own|department` pattern (§backend research §10);
all mutating endpoints are POST/PATCH only, no PUT (locked 49.1); all responses use the existing
envelope (`legalmind/api/envelope.py`).

Assist router addition: no new endpoint needed — `POST /conversations/{id}/messages`'s existing
`ask()` response gains the new `routed_to_builder` shape (§9), not a new route.

---

## 21. Required frontend components

New, following the naming/placement conventions already in `src/components/workspace/`:

- `TemplatePicker.tsx` — card grid, published templates only.
- `TemplateBuilderWizard.tsx` — the new stepper (§8's flagged genuinely-new component); manages
  step state, delegates each step's fields to `BuilderFieldForm.tsx`.
- `BuilderFieldForm.tsx` — one input renderer per `field_type`, plain controlled state +
  `validateBuilderFields()` pure function in `src/lib/` (mirrors `src/lib/companyStandard.ts`'s
  `validateStandard` shape).
- `BuilderConditionalSection.tsx` — checkbox + nested field group.
- `BuilderPreviewPane.tsx` — structured-HTML live preview, reusing `DocumentPane.tsx`'s
  evidence-row rendering approach for structured content (not the iframe path).
- `DraftWatermarkBanner.tsx` — the new "Draft — pending legal/business approval" treatment (§8),
  used both in-app and burned into the rendered PDF/DOCX (server-side, §7 — the frontend component
  is for the in-app preview only).
- `AskBuilderHandoff.tsx` (or a new branch inside existing `WsAnswerView`) — the "Start MSA draft"
  action button (§9).
- Additions to `src/lib/api.ts`: one function per §20 endpoint, matching the existing
  one-function-per-endpoint convention.
- Additions to `src/lib/permissions.ts`: the four new permission constants from §19.
- Nav addition: one new entry in `navItemsFor()` (`src/components/workspace/model.ts`), gated on
  `document.generate`.

No new component library, no new state-management dependency, no new form library — all of it
composed from the existing `useState`/plain-fetch/`useSession().can()` conventions already
governing every other screen in `/dashboard`.

---

## 22. Required tests

Mirroring `STEP_54_TESTING_STRATEGY.md`'s existing tiers:

- **Unit — template validation**: a submitted field set against a `TemplateVersion.fields`
  schema — required-missing, wrong type, regex failure, unknown key, protected-key-without-override
  — one test per §18's rejection cases.
- **Unit — determinism**: same `(template_version_id, fields, sections)` rendered twice produces
  byte-identical PDF and DOCX bytes.
- **Unit — render correctness**: a `FieldBlock` renders with correct prefix/suffix; a
  `ConditionalBlock` disabled by default is absent from output; enabled, it is present with its
  nested fields.
- **Integration — API**: full create-draft → set-fields → toggle-section → preview → render →
  download flow against a real (test-fixture) `TemplateVersion`, asserting permission checks at
  each step (401/403 cases explicitly, not just the happy path).
- **Integration — Ask AI routing**: every row of §9's behavior table as an explicit test case,
  including the negative cases (no published template → no redirect; review-intent phrasing → no
  redirect).
- **Security**: attempt to set a value for a nonexistent `field_key`; attempt to override a
  protected field without the override permission; attempt to fetch another department's draft
  without `department.view`-equivalent scope; assert the import-boundary test (`EGRESS_ALLOWED`)
  still excludes `legalmind/builder/*` from network access.
- **Golden fixture**: exactly one hand-authored NDA `TemplateVersion` fixture (built from the real
  approved source once Phase 0 supplies it — never invented, per rule 21, mirroring how the
  golden corpus itself only uses supplied source material) with a small set of representative field
  combinations, checked into `backend/tests/` the same way liability fixtures already are.
- **Playwright/E2E**: the full `/dashboard/builder` journey (§3.1) against a real running backend,
  matching the pattern already used for the publish-checklist feature (`CHANGELOG.md`'s 2026-09-15
  entry: "10 unit tests… plus 3 Playwright tests against the real backend").
- **Visual regression**: the draft-ready screen and watermark, added to whatever visual-baseline
  suite already exists for `/dashboard/*` — per the standing memory on visual baselines, any new
  baseline must be established via CI, never a local `--update-snapshots` run, and diffed at full
  resolution rather than trusting a passing job alone.

---

## 23. Migration strategy for existing uploaded templates

There is nothing to migrate, in the database-migration sense — and this is worth stating precisely
rather than skipping, since the task explicitly asks for a migration strategy.

- **No existing table holds anything resembling a template today.** `DocumentVersion` rows are
  uploaded counterparty/organization documents under review, not templates (§backend research §1,
  §9) — there is no data to transform or backfill into `Template`/`TemplateVersion`.
- **The six-plus-six documents under `legal-docs/`** (D1-D6 and the second tranche) are reference
  material for deriving Company Standards, gitignored and outside the repository by policy (locked
  54.6) — they are not candidates for direct import into `templates` either, both because they are
  the *organization's own outbound documents* (LeapSwitch's TOS/MSA/SLA, not a vetted "this is what
  we send customers" template with a fixed/variable boundary already marked) and because rule 21
  forbids promoting an illustrative/reference document into production configuration without an
  explicit owner act designating it as such, for the specific purpose of being a template.
- **The correct "migration" is therefore a one-time authoring act, not a data migration**: once the
  owner supplies or designates approved template source text (Phase 0, §17), an admin (with
  `template.manage`) hand-authors the first `TemplateVersion` for NDA and MSA through the
  authoring UI or an admin-only import script that parses the supplied source into the Block tree
  (§5.2) for human review and correction before approval — mirroring exactly how
  `backend/tools/import_ratified_standards.py` already turns a supplied JSON file into versioned DB
  rows (§backend research §3), rather than turning a *parsed, uploaded contract* into one, since a
  contract is not a template.
- **If, later, the owner wants a Company Standard's existing values reflected inside a template**
  (e.g. the MSA template's fee-payment-terms default should match `LIABILITY-MSA-001`'s
  `preferred`/`unit`), that is a deliberate cross-reference the template author sets explicitly at
  authoring time (a `default value` on the relevant `FieldBlock`, §5.4) — never an automatic sync,
  since a Company Standard changing later must not silently rewrite a template someone already
  approved (the same append-only, no-silent-propagation discipline `ConfigurationSnapshot`
  enforces for reviews, rule 16, applied here to templates).
