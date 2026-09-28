# LegalMind — Whole Product IA + UI/UX + Page Necessity Review

**Status: 📁 REVIEW BRIEF / operating mandate — NOT YET EXECUTED.** This document is the
owner's brief for a future review-and-implementation pass. It decides nothing on its
own and locks nothing; it directs how that pass should be scoped and run. Date issued:
2026-09-28.

**Relationship to the 2026-09-28 Product Reality Review.**
[PRODUCT_REALITY_REVIEW_2026-09-28.md](PRODUCT_REALITY_REVIEW_2026-09-28.md) already
covers functional correctness, security/RBAC, Ask/RAG current state, production
readiness, and documentation consistency — do not repeat that work. This document
covers a dimension that review did not: whether the product's **information
architecture** — its pages, routes, navigation, and terminology — is itself correct,
not merely whether each page functions correctly in isolation.

**Relationship to the Ask/RAG engine-unification work.** The P0 work of making the new
Ask engine the normal, unified Ask product (flagged as the top open item in the 28 Sep
review) is separate and already assigned. **Do not restart or redesign that work here.**
This review may touch Ask's product *surface* (discoverability, entry points,
conversation UX) but must preserve the verified RAG safety/evidence/citation/refusal
architecture exactly as built.

---

## 1. What this review is actually about

This is **not** another RAG/Ask audit, and not a repeat of the 28 September product
reality review.

This task is about the whole LegalMind product experience, especially:

- Information architecture
- Navigation structure
- Page/route necessity
- Page purpose and ownership
- User mental model
- Duplication between pages
- Whether a page should be merged, renamed, simplified, or removed
- Whether the current terminology makes sense to a real LegalMind user
- Whether admin/configuration/legal/standards/reviews/findings areas are logically
  separated
- Whether a user can understand what to do without knowing the internal architecture
- Whether each page supports a real workflow
- UI consistency and hierarchy
- Empty states, loading states, error states, responsive behavior
- Accessibility and interaction quality
- Over-engineering and unnecessary UI/code

The goal is **not** to preserve every existing page because it already exists.

The goal is to determine **the smallest, clearest, most coherent product structure**
that supports LegalMind's actual purpose.

---

## 2. Product context you MUST understand first

Before judging pages, inspect the actual product and current documentation.

LegalMind is an internal legal-document intelligence/review product. Its important
concepts include:

**Documents**
- Agreements uploaded by users
- OCR/parsing
- Document comparison/review

**Findings**
- Company Constitution / Standards
- The LegalMind Constitution is the company's source of truth.
- Current standards/positions should not be treated like generic user-uploaded
  documents.
- Relevant legal/company knowledge is already part of the RAG/knowledge system.
- Do not invent a new "standards management" product model without verifying how the
  current system actually works.

**Reviews / Findings**
- A review should represent an actual legal-document review workflow.
- Findings should explain deviations/issues against applicable company standards and
  legal evidence.
- Avoid duplicating the same information across multiple pages.

**Ask**
- The new RAG + LLM Ask engine is becoming the normal Ask product.
- Ask can work with or without an attached document.
- It must preserve evidence, citations, authorization, refusal behavior, history,
  follow-ups, and multi-source reasoning.
- Do not redesign the RAG architecture as part of this task.

**Administration**
- Users, permissions, configuration, etc.
- Admin functionality should be separated from ordinary legal-user workflows where
  appropriate.

**Client Profiles**
- Existing product area.
- Determine whether it has a genuine user workflow and whether its current placement
  makes sense.

---

## 3. Important user concern to investigate

The current product appears to contain multiple pages/areas such as: Legal, Reviews,
Findings, Standards / Constitution, Documents, Ask, Client Profiles, Administration,
Users, Permissions, Configuration, Dashboard.

Some of these may be valid. Some may overlap. Some may exist because they were created
during development rather than because a real user needs a separate destination.

**Do not assume the user's suspicion is correct.** For example, the owner suspects that
the current Legal and Reviews pages may not have a sufficiently clear purpose.

The correct response is **not**: "Yes, these pages are useless."

The correct response is: inspect the actual route, backend behavior, navigation entry,
data, user workflow, and downstream actions. Then determine whether the page has a
distinct job.

Likewise, do not assume Standards should remain a standalone upload-oriented page —
see §6.4 for what to verify before deciding.

---

## 4. Review the product like a senior product designer + senior frontend engineer

Think from the user's perspective first. For every page ask:

### A. Why does this page exist?

Write one sentence: *"A user comes here to ______."* If that sentence is weak, unclear,
or duplicates another page, flag it.

### B. Who needs it?

Classify: Legal user · Reviewer · Department lead · Admin · Developer/internal operator
· Everyone · Nobody / unclear.

### C. What job does it perform?

Identify the concrete user job. If it only displays information that is already
available elsewhere, question whether it deserves a separate route.

### D. What action happens here?

A strong operational page normally supports one or more meaningful actions: Review ·
Upload · Compare · Investigate · Ask · Approve · Publish · Manage · Configure · Search
· Resolve. If the page has no meaningful action or decision and is only a duplicate
dashboard/table, investigate whether it should be merged.

### E. Is the information duplicated?

Check whether the same document, finding, standard, client, review, status, or legal
information appears in multiple places with different labels. Duplication is a UX
problem even when the backend implementation is correct.

### F. Does the navigation match the user's mental model?

A user should not need to understand RAG, embeddings, evidence bundles, retrieval,
model routing, internal database entities, or backend terminology to understand the
product. Internal architecture should not leak into navigation unless it is genuinely
user-facing.

---

## 5. Page-by-page audit matrix

Build a concrete matrix for every route/page found in the repository, with these
columns: **Route · Current Name · Primary User · Real Job · Unique Data/Action ·
Duplicate With · Keep / Merge / Rename / Remove · Evidence · Confidence.**

Do **not** decide from route names alone. Inspect: frontend route, navigation entry,
page component, API calls, backend endpoint(s), permissions, data shown, actions, links
into other pages, tests, browser behavior, documentation, and the current user
workflow.

---

## 6. Specifically investigate these areas

Apply §4's A-F test to each area below. Only the area-specific trap is called out —
the why/who/job/action/duplication/mental-model questions are §4's, not restated here.

### 6.1 Legal

Trap: "Legal" may just be another view of Reviews, Documents, a knowledge browser, or a
standards browser dressed up as its own route. Verify unique actions/data before
keeping it as its own destination — a real legal user should know why they'd click it.

### 6.2 Reviews

Trap: a list page and a workspace can both be valid if they have different jobs, but if
Reviews and Findings/Legal/Documents all show essentially the same workflow, that's the
duplication to find.

### 6.3 Findings

Trap: do not remove a useful global finding workflow merely because findings also
appear inside a review — determine whether the two views serve different user jobs
first.

### 6.4 Standards / Constitution

This needs special care. **Do NOT assume** "Standards = upload documents," and do not
assume it should remain a standalone upload-oriented page. **Do not create a new
standards model just because the current UI is confusing — understand the existing
data model first.** Inspect the actual implementation and current source-of-truth
model. Determine:

- What users are actually allowed to upload?
- What constitutes an active company standard?
- How is Constitution content represented?
- How are retired standards represented?
- What is publishable, and by whom?
- What belongs in an admin workflow vs. a legal-user workflow?
- Is "Standards" a useful product concept or an implementation label?
- Should users see "Constitution", "Company Standards", "Legal Knowledge", or another
  concept?
- Are there separate pages that are actually the same source of truth?

### 6.5 Documents

Trap: check whether a user can naturally follow *Upload → OCR → review → findings →
resolve/archive* without detouring through unrelated pages — that's the difference
between a document library, an upload entry point, a review history, and a mixture of
all three.

### 6.6 Ask

Apply §4's A-F test to the product surface only — **do not redesign the RAG engine
here.** Check discoverability, whether the name is understandable, whether chat history
and "Add files" make sense, entry-point consistency, and whether document-attached and
plain questions present consistently. Preserve the current verified RAG
safety/evidence architecture.

### 6.7 Client Profiles

Trap: determine whether client data is actually used by Reviews/Documents/Ask, or
whether this is an admin data table wearing top-level navigation. Do not remove it
automatically.

### 6.8 Administration

Trap: separate administrative concerns (Users, Permissions, Configuration, Standards
publishing, System settings) from normal legal-user concerns. Determine whether each
belongs as a separate admin page, a tab under one Administration area, or should be
smaller — and keep admin concepts out of ordinary legal-user navigation.

---

## 7. Information architecture review

After the page audit, propose the simplest coherent navigation model. Do **not** start
by designing a new UI. First produce:

**Current IA** — show the current navigation tree.

**Problems** — show duplicates, ambiguous names, unnecessary hierarchy, implementation
terminology, admin leakage, missing workflow grouping, pages with no clear job.

**Proposed IA** — show the proposed navigation tree. For example, the agent may
discover that something conceptually like this is cleaner:

```
Dashboard

Work
├── Reviews
├── Documents
├── Findings
└── Ask

Knowledge / Standards
└── Company Standards

Clients
└── Client Profiles

Administration
├── Users
├── Permissions
└── Configuration
```

This is only an example. **Do not blindly implement it.** The actual structure must
come from repository evidence and real workflows.

---

## 8. UI/UX quality review

Once IA is understood, inspect the actual screens.

**Visual hierarchy.** Is the primary action obvious? Are secondary actions visually
subordinate? Are headings meaningful? Is content density appropriate? Is there
unnecessary whitespace? Are cards used merely because cards are available?

**Consistency.** Check buttons, status badges, tables, dialogs, forms, filters,
pagination, empty states, loading states, error states, typography, spacing, icon
usage. Use the existing design system/components where appropriate — do not introduce
another UI system.

**Responsive behavior.** Verify at minimum desktop, tablet-ish width, and 390px mobile.
Do not fix mobile by simply hiding important functionality.

**Accessibility.** Check keyboard navigation, focus states, labels, semantic headings,
button/link semantics, dialogs, tables, color contrast, screen-reader labels, ARIA
usage. If automated accessibility coverage is missing, record it separately from actual
UI defects.

---

## 9. User-flow review

Do not only inspect pages independently — trace real workflows end-to-end. Only include
steps actually supported by the implementation.

**Workflow A — Review a document:** Login → find/create review → upload document →
OCR/parse → analysis → findings → inspect evidence → resolve/act.

**Workflow B — Ask a legal question:** Login → Ask → ask question → retrieve evidence →
answer → citation → follow-up → history.

**Workflow C — Maintain company standards:** Admin/legal operator → standards/
constitution area → inspect current source → update/upload if actually supported →
publish → verify active state.

**Workflow D — Manage users:** Admin → Administration → Users → permissions/role →
save → verify access.

For each workflow ask: could a normal user understand where to start without already
knowing the codebase?

---

## 10. Over-engineering review

Use `/ponytail-review` / `/ponytail-audit` as a secondary lens only, not the primary
product review — they catch dead code and redundant abstractions, not whether a page
should exist. A page is never removed just because its code can be simplified: the
product question (*does a real user need this as a separate surface?*) comes before
the engineering question (*what's the smallest implementation that preserves it?*).

---

## 11. Important decision rules

**Do not redesign blindly.** Do not: invent new workflows, invent new entities, create
pages just to make navigation look organized, remove pages solely because they look
empty, rename everything at once, replace working components without evidence, rewrite
the whole frontend.

**Do not preserve things blindly either.** Do not say "everything is already working,
so keep it." A technically working page can still be a poor product decision.

**Prefer deletion/merging when justified** — two pages with the same job merge; a page
with no real job is removed or folded into its parent area; a valid-but-confusing name
is renamed; a valid-but-buried capability gets better navigation; an admin-only
capability stays out of ordinary user navigation. §19–§22 give the fuller
confidence/evidence/redesign-gate rules for exactly when each of these applies —
apply those before acting on this list.

---

## 12. Evidence standard

Every major recommendation must have evidence (§19's Evidence field says what counts).
Never make a product decision based only on filename, route name, visual appearance,
assumption, or personal preference.

---

## 13. Do not confuse "not useful to me" with "not useful"

A page can legitimately exist for admin, legal reviewer, department lead, operations,
audit, compliance, or system configuration. Classify the intended audience before
recommending removal.

But also do not use a hypothetical user as an excuse to keep everything. The
requirement is a real, evidenced user job.

---

## 14. What the agent should actually do

Work in this order:

**Step 1 — Understand.** Inspect repository, routes, navigation, frontend components,
backend APIs, permissions, current docs, roadmap/locked decisions, existing
screenshots/browser state where useful. Do not modify code yet.

**Step 2 — Map.** Create the complete page/route inventory.

**Step 3 — Evaluate.** For every page determine purpose, user, job, actions, data,
dependencies, duplication, necessity.

**Step 4 — Validate.** Use browser inspection for important flows. Use existing tests.
Add small targeted tests only where required to prove a change.

**Step 5 — Simplify.** Only after the evidence-based IA review: remove dead pages,
merge duplicate surfaces, rename ambiguous concepts, simplify navigation, consolidate
repeated UI, preserve real workflows.

**Step 6 — Verify.** Run targeted frontend tests, relevant backend tests, lint/type
checks, browser smoke tests, responsive checks, accessibility checks available in the
repo.

**Step 7 — Document.** Update the appropriate `.md` records so the next session knows
what pages existed, what was decided, why, what changed, what remains intentionally,
what was rejected and why, and test/verification results.

---

## 15. Critical continuity rule

This is an existing LegalMind project.

- Do not restart completed RAG work.
- Do not undo locked decisions.
- Do not invent Phase 14.
- Do not alter the Constitution source-of-truth model without explicit evidence and
  authorization.
- Do not weaken authorization, evidence gating, citation, refusal, verification, or Ask
  safety.
- If a UI issue touches the new Ask engine, preserve the verified engine and make the
  smallest product-surface change necessary.

---

## 16. Expected final deliverable

Before making large changes, produce a concise review report in the repository. It must
contain: current navigation map, complete route/page inventory, KEEP / MERGE / RENAME /
REMOVE decisions, reason and evidence for each non-trivial decision, proposed final
information architecture, user-flow problems, UI/UX problems, accessibility gaps,
over-engineering findings, implementation plan ordered by impact, tests/verification
plan, and documentation updates required.

Then **implement** the approved/clearly justified changes rather than stopping after an
audit.

---

## 17. Definition of success

The review succeeds when a new internal LegalMind user can look at the product
navigation and reasonably understand: where to review a document, where to see
findings, where to ask a legal question, where company standards/Constitution belong,
where clients belong, where administration belongs — **without needing to understand
LegalMind's internal RAG architecture.**

And a reviewer looking at the codebase can explain: every remaining top-level page has
a distinct user job. That is the standard — checked concretely in §23's sanity test.

### Final instruction to the coding agent

Think like a senior product designer, information architect, UX researcher, and senior
frontend engineer at the same time.

Do not merely make the existing pages prettier. First determine whether the product
structure itself is correct. Do not assume the owner's suspicion is right, and do not
assume the current implementation is right. Investigate, challenge, validate, simplify,
implement, test, and document.

If a page is genuinely needed, make its purpose obvious. If two pages represent the
same user job, consolidate them. If a page has no defensible user job, remove it. If a
page is useful only to admins, place it appropriately under administration. If
terminology exposes internal engineering concepts, replace it with language a
legal/product user understands.

Do not stop at "audit complete." Own the loop: understand → inspect → decide →
implement → test → verify → document.

---

## 18. Additional checks that MUST NOT be missed

The mandate above is the core; the following checks make it stronger and prevent a
common failure mode — reviewing pages visually while missing the product structure
underneath them.

### 18.1 Route reachability / dead-surface audit

Build a complete route graph. For every route determine: can a user reach it through
normal navigation? Is it linked only from another page? Is it reachable only by direct
URL? Is it protected by a role/permission? Is it an orphaned route? Does it still have
an active backend/API dependency? Does another route now replace its function? Is it a
legacy/deprecated screen?

Explicitly distinguish: dead route · admin-only route · deep workflow route · valid
top-level route · duplicate route · legacy compatibility route. Do not remove a route
solely because it is not in top navigation.

### 18.2 Navigation by role

Inspect the navigation separately for each meaningful role — at minimum ordinary
legal/reviewer user, Department Lead, Platform Admin, Developer/internal operator (if
exposed). Ask: does this role see only the navigation relevant to its actual jobs? A
page can be valid but should not necessarily be visible to every role. Hiding a
navigation item is only a UX decision; **authorization must remain enforced
server-side.**

### 18.3 Product object lifecycle

Map the lifecycle of the main product objects — extract the real state machine from the
code, do not invent states:

- **Document:** uploaded → processing/OCR → reviewed → findings → resolved/decision →
  archived/deleted.
- **Company Standard / Constitution:** draft/source → published/active → retired.
- **Review:** created → processing → completed → findings/decision → archived.

Check whether the UI reflects those states consistently. If a page exists mainly
because the underlying object lifecycle is unclear, flag that separately.

### 18.4 "Where does the user go next?" test

For every important page ask: after completing the primary action, what should the
user naturally do next? (Upload → Review; Review → Findings; Finding → Evidence /
decision; Ask → follow-up; Standard publish → verify active version; User update →
verify permissions.) If the interface ends in a dead end, flag it — a page can be
technically correct but still create poor product flow.

### 18.5 Entry-point duplication

Look for multiple ways to start the same workflow (e.g. Upload from Dashboard +
Documents + Reviews; Ask from Dashboard + floating button + dedicated page; Review from
Documents + Reviews + document detail; Findings from Review + global Findings).
Multiple entry points are not automatically bad — determine whether they are useful
shortcuts to the same canonical workflow, or competing workflows that confuse
ownership. Identify the canonical destination.

### 18.6 Information ownership

For every major piece of information identify its canonical home:

| Information | Canonical Home | Other Valid Views |
|---|---|---|
| Review status | Review | Dashboard summary |
| Finding | Finding/Review | Global Findings inbox |
| Company standard | Constitution/Standards | Review evidence |
| Document | Document | Review workspace |
| Client | Client Profile | Review context |
| User permission | Administration | User detail |

The same information may appear elsewhere as a contextual view, but there should be one
authoritative management surface. This is especially important for
Standards/Constitution.

### 18.7 Terminology audit

Create a small product glossary from the actual UI. Check whether terms such as Legal,
Review, Finding, Standard, Constitution, Document, Client, Ask, Configuration,
Administration have one consistent meaning. Flag cases where the same concept has
different names, or the same name refers to different concepts. Do not rename based on
preference — tie terminology to the actual user job.

### 18.8 Dashboard usefulness test

Do not automatically preserve Dashboard because it is conventional. Determine: what
decisions/actions does Dashboard enable? Is it a useful starting point? Does it
duplicate Reviews/Documents/Findings? Does it contain genuinely useful cross-product
information, or is it just a collection of cards linking elsewhere? If it is mainly
navigation disguised as analytics, consider whether it should be simplified rather than
expanded.

### 18.9 Table/list usability audit

For every important table/list inspect: column relevance, sorting, filtering, search,
pagination, row actions, bulk actions, status representation, empty state,
filtered-empty state, loading, error state, mobile behavior, long text, date/time
consistency. Do not add CRUD/search/filter controls just because tables normally have
them — only add controls when they support an actual user job.

### 18.10 Detail-page vs modal vs inline decision

For important actions determine whether the current interaction pattern is
appropriate: full page, side panel, modal/dialog, inline editing, dropdown/action menu.
Use a full page when the user needs context, navigation, evidence, or a sustained
workflow. Use a modal for focused confirmation or short tasks. Use inline editing for
low-risk, local changes. Do not turn complex workflows into modals simply to reduce
routes.

### 18.11 Back/forward and URL state

Test browser Back, Forward, refresh, deep link, query/filter state, selected
review/document, pagination, tabs. The user should not lose important context
unnecessarily. Where filters/search/tabs represent meaningful state, determine whether
they should be reflected in the URL.

### 18.12 Error and recovery UX

Review what happens when OCR fails, analysis fails, upload fails, permission is
denied, a record disappears, an API times out, Ask refuses an unsupported question, a
publish operation fails, or a destructive action is cancelled. For each: does the user
understand what happened, what is safe to retry, and where to go next? Do not expose
raw backend errors where a product-level message is appropriate.

### 18.13 Destructive and irreversible actions

Identify delete, archive, deactivate, publish, retire, revoke, overwrite. For each
verify: correct permission, clear consequence, confirmation where appropriate,
distinction between destructive and reversible actions, success feedback, failure
feedback, correct post-action destination. This is particularly important for Admin and
Standards/Constitution.

### 18.14 Search / filtering / discovery model

Determine whether users can find documents, reviews, findings, clients, standards
without knowing exact internal names. Do not build a global search just because it is
common in enterprise software — first identify actual discovery problems. If multiple
lists each implement search differently, consider consistency.

### 18.15 Context preservation

Check whether the product preserves useful context when moving between surfaces (e.g.
Review → Finding → source/evidence → original document; Client → Review → Document →
Findings). The user should not have to manually reconstruct what they were looking at.

### 18.16 State terminology and status semantics

Audit every status pill/badge. A status must have a defined meaning, a consistent
visual treatment, consistent wording, and clear transition rules — do not use color
alone. Pay special attention to distinctions such as: Active vs Published, Draft vs
Processing, Resolved vs Match, Archived vs Deleted, Retired vs Inactive, Needs decision
vs Requires modification. **Never collapse legally meaningful states merely to make the
UI simpler.**

### 18.17 Design-system compliance

Before changing UI: inspect the existing design system, identify existing shared
components, identify duplicate/hand-rolled versions, reuse shared components where they
actually fit. Use shadcn/ui where the existing project/design direction supports it. Do
not mass-replace working UI merely to standardize it. Specifically inventory repeated
buttons, badges/status pills, cards, tables, dialogs, dropdowns, form fields, tabs,
navigation, toast/notification patterns, loading/skeleton patterns. The goal is
consistent behavior, not component uniformity for its own sake.

### 18.18 Visual evidence

For high-impact UI decisions, capture browser evidence where practical. For each major
proposed change record: route, viewport, what was observed, before/after if changed,
and why the change improves the identified problem. Do not make large IA decisions from
screenshots alone — screenshots are supporting evidence.

---

## 18A. AI Chat / Ask UX Benchmark — Critical

The Ask / LegalMind AI interface requires a dedicated AI-product UX review. Do **not**
evaluate Ask only as a normal application page. Evaluate it as a modern AI assistant
experience and compare its interaction patterns with established AI products such as
ChatGPT, Gemini, Claude, and other mature AI-agent interfaces.

The goal is **not** to copy another product. The goal is to identify proven interaction
patterns that LegalMind is currently missing and determine which ones are appropriate
for a legal AI product.

### 18A.1 Conversation layout

Inspect: conversation width, message hierarchy, user vs AI message distinction,
readable answer width, whitespace and density, response grouping, long-answer
readability, markdown rendering, tables/lists, headings, inline citations, source
references, evidence presentation.

Ask: does this feel like a modern AI assistant, or like a normal CRUD application with
a chat box attached?

### 18A.2 Composer / input experience

Review: text input, auto-growing composer, send action, Enter vs Shift+Enter behavior,
disabled/loading state, Stop generation, Retry, Regenerate where appropriate, file
attachment, attached-file chips/previews, remove attachment, drag/drop if supported,
keyboard accessibility, focus behavior, error recovery.

The composer should make the next action obvious without unnecessary UI.

### 18A.3 Conversation lifecycle

Review: New chat, conversation history, conversation titles, rename behavior if
supported, active conversation state, switching conversations, refresh persistence,
deep linking, follow-up questions, context preservation, long conversations, starting a
new topic, empty conversation state.

Verify that conversation history behaves like a real AI product rather than a simple
database list.

### 18A.4 AI response states

Review every state: initial empty state, thinking/loading, streaming, completed
response, partial response, refusal, insufficient evidence, error, retry, generation
interruption, network failure, source/evidence loading.

The user must understand: is the AI still working, finished, unable to answer, or
failed? Avoid ambiguous spinners and generic "Something went wrong" states.

### 18A.5 Legal evidence and citations UX

This is especially important for LegalMind. Review how the UI presents: citations,
Constitution/company standards, legal sources, document evidence, source metadata,
supporting passages, insufficient evidence, user-provided information, historical
information, current vs non-current law.

The interface must clearly distinguish: **AI answer ≠ evidence ≠ company standard ≠
user assertion.** Do not overload the main answer with technical RAG terminology.
Evidence should be discoverable and trustworthy without making every response visually
complicated.

### 18A.6 Source interaction

Test whether a user can naturally go from AI answer → citation/source → supporting
evidence → original document/section.

> **Note on source completeness:** the owner's brief as supplied ends mid-thought at
> this point (18A.6 has no further content). Nothing beyond the line above was in the
> source material — do not extend it with invented criteria. If more was intended (a
> target destination for the flow, and any further §18A subsections), confirm with the
> owner before the review pass proceeds past this point.

---

## 19. Decision confidence and reversibility

Every KEEP / MERGE / RENAME / REMOVE decision should have:

- **Confidence:** High / Medium / Low
- **Evidence:** code + workflow + browser/test evidence
- **Reversibility:** Easy / Moderate / Costly

Rules:

- **High confidence** — implement when the evidence is clear.
- **Medium confidence** — prefer a small reversible change, or validate with browser
  workflow/user feedback first.
- **Low confidence** — do not delete or restructure a major product surface yet. Record
  the question and gather evidence.

This prevents a "cleanup" review from accidentally deleting a valid workflow.

---

## 20. Separate product decisions from implementation decisions

For every proposed change write two things:

**Product decision** — e.g. "Findings should remain a global workflow because users
need to investigate issues across multiple reviews."

**Implementation decision** — e.g. "Keep `/findings`, but reuse the shared
`FindingTable` and link each row to the canonical review context."

This prevents the agent from mistaking a code refactor for a product improvement.

---

## 21. Separate MUST-FIX from SHOULD-IMPROVE

Final findings should be classified:

- **P0 — Product confusion / broken workflow.** User cannot understand where to start;
  duplicate pages create competing workflows; wrong canonical location; important
  action inaccessible; role sees inappropriate workflow.
- **P1 — Significant UX/IA improvement.** Unclear terminology; poor navigation
  grouping; weak context preservation; inconsistent state semantics; important
  responsive/accessibility issue.
- **P2 — Polish / consistency.** Visual inconsistencies; minor spacing; cosmetic
  component differences; low-impact truncation.
- **Not a problem.** Explicitly record things investigated and intentionally retained.

The agent must not manufacture work just to produce a large report.

---

## 22. "No unnecessary redesign" gate

Before changing any existing page, answer: what user problem does this change solve?
What evidence proves the problem exists? Why is the proposed change better than the
current behavior? Does it alter a locked product decision? Does it affect
permissions/security? Does it affect an existing API contract? Can it be implemented
with the existing design system? How will it be verified?

If these cannot be answered, do not make the change yet.

---

## 23. Final product sanity test

After implementation, forget the codebase and behave like a new LegalMind user. Try to
answer:

- "I have a contract. Where do I start?"
- "I want to know what is wrong with this contract. Where do I go?"
- "I want to see all unresolved findings. Where?"
- "I want to ask a legal question. Where?"
- "I want to understand the company's current standard. Where?"
- "I want to manage users. Where?"
- "I want to change system configuration. Where?"
- "I want to see information about a client. Where?"

If any answer requires knowing internal architecture, the IA still needs work.

---

## 24. Final agent behavior

The agent must not interpret this document as permission to redesign the entire
product. The mandate is:

- Remove ambiguity, not functionality.
- Preserve real workflows.
- Remove duplicate concepts.
- Simplify navigation.
- Clarify terminology.
- Consolidate where evidence supports it.
- Keep specialist/admin workflows where they have a real purpose.
- Make important workflows easier to discover.
- Maintain the existing security, authorization, legal correctness, RAG safety,
  evidence, citation, and verification guarantees.
