# Changelog

Notable changes to the LegalMind repository. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

**This is not the decision record.** Every decision, its reasoning and its exact locked text live in [`all_lock.md`](all_lock.md), indexed by ID in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md). This file records *what changed in the repository and when*, at milestone granularity, and links out. Decision history is deliberately not duplicated here.

No version has been released. The V1 specification is complete and implementation is authorized (`IMPL-01`, 2026-08-17). Build state is reported in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which is the only document that asserts it.

---

## [Unreleased]

### Added

* **Owner-requested design polish pass (2026-08-31, "use plugin to make frontend
  design better")** — an explicit design-improvement request, so it lifts the
  2026-08-31 freeze for this one pass; the freeze stands again after it. The
  design skills (`ui-ux-pro-max`, `frontend-design`) were loaded first per the
  standing rule; the plugin's UX database rated the missing hover feedback a
  real defect, not taste. Presentation-only changes in
  `frontend/src/app/workspace/workspace.css` — zero markup, zero behavior:
  - **Interaction feedback everywhere something is clickable**: hover states
    added where none existed (`.ws-btn` both variants + a disabled treatment,
    filter pills, collapsed-mode tabs, shell nav/sign-out, evidence-ref and
    evidence-loc buttons, ask citations, escalate link, table rows, attend
    "Open" links), all driven by one shared motion token (`--ws-t`, 0.13s,
    color/border/background only — never layout) that the existing global
    reduced-motion rule already zeroes.
  - **`--ws-accent-strong`** (#16407e — the hue's one deeper stop, same value
    the legacy sheet already used) for primary-button hover.
  - **Stat tiles now actually use the mono voice** their own comment claimed
    (`.ws-stat__n`: mono face, tabular numerals, weight 600).
  - **The document pane's serif measure is bounded at 74ch** (left-anchored) so
    wide monitors don't produce unreadably long italic lines.
  - `::selection` in the accent-soft tint; drop-zone drag-over state now
    transitions instead of snapping.
  No axis color, chip semantics, register rule (Authority/Inquiry), or DD
  decision touched. Verified: typecheck · terms gate · **113 Vitest** ·
  browser suite **57 passed / 18 gated**. Expected: DESIGN_QA visual-baseline
  diffs on hover-independent screens are unlikely (hover states don't render in
  static captures) but any that appear are re-cut from CI per the standing rule.

* **Owner UX rethink (2026-08-31, "rethink the UX around the real user journey") —
  the drill, export, contextual Ask, the work dashboard.** The owner's 38-section
  directive is the explicit UX-review request the 2026-08-31 freeze anticipated;
  decisions #231–#241 in
  [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md). The audit found
  the core journey already built (upload-first intake, in-flow analysis, ungated
  Ask, real versioning — the two earlier 2026-08-31 passes); what was missing was
  the drill and the exits:

  - **Summary → category → finding → evidence, clickable end to end** (#233): the
    findings pane opens with classification counts as pressable filters; the report
    page's classification chips and the Documents rows' count chips deep-link
    `?classification=`; the cited excerpt now renders verbatim beside each finding
    (the highlight gesture kept); and the Evidence → Fact → Standard → Rule → Result
    explanation chain returned to the workspace card — it had regressed against the
    legacy screen (rule 12). All grouping is presentational counting of server
    values (52.7).
  - **The all-MATCH success state is designed, not an afterthought** (#234): a calm
    banner from real fields; no grade, no percentage.
  - **`POST /reviews/{id}/export` — PDF and DOCX** (#231/#232): 49.3's own row,
    formats per the owner's §30 list (49.12's open question closed by that
    directive). One content model built from the caller's own serializations —
    LEGAL-02 omission holds in the file exactly as on the wire, pinned by test.
    pymupdf + python-docx (already in the stack, rule 19 clean); audited
    (`report.exported`); rate-limited (49.10). `export.generate` granted alongside
    `report.view` (USER, LEGAL_REVIEWER, LEGAL_ADMIN) — **flagged for
    ratification**. Email summary deliberately not built (no mail component in the
    locked stack). Export buttons live on the findings pane and the report page.
  - **Finding → Ask handoff** (#235): "Ask about this" places an editable,
    document-shaped question in the Ask input and focuses it (switching to the Ask
    tab in collapsed layouts); nothing auto-sends, no hidden context enters the
    assist lane.
  - **The Ask pane is durable** (#236): it reopens the contract's latest
    conversation on mount, citations intact — the 2026-08-26 reopen endpoints,
    finally used by the pane itself.
  - **One loop, not two journeys** (#237): a revised version chains the same
    best-effort analysis as a first upload (shared `chainAnalysis`); the manual
    Analyze action stays for every degraded path.
  - **Documents is the work dashboard** (#238): a "Needs attention" group (any
    non-MATCH count, from the server's own counts) above "All documents"; no KPI
    cards, no synthesized metrics.
  - **Live analysis state** (#239): the findings pane polls the Review lifecycle
    (bounded, silent) and renders "Analysing against snapshot <id>…" plus an honest
    ANALYSIS_FAILED terminal state. **Upload preflight** (#240): friendly immediate
    messages for unsupported type / >50 MB / empty file, server validation still
    authoritative.
  - Consistency fixes: `NOT_APPLICABLE` removed from the frontend's classification
    rendering order (it is a Rule Outcome — different axis); the CALM set unified to
    MATCH; the reviews empty state no longer points at "the current application".
  - **Deliberate deviation from the owner's §22 (remove obsolete UI)** (#241): the
    legacy screens stay in the tree, unlinked and unreachable from the product,
    because ~10 browser specs and the visual baselines still drive them as the
    verification harness. Their retirement is a named follow-up: port the unique
    coverage, then delete screens + specs + baselines together.

  Verified: backend **949 passed / 1 skipped** (+7 export tests) · ruff · mypy ·
  **113 Vitest** (+6) · typecheck · terms gate · browser suite (see below) ·
  `openapi.json` regenerated deliberately (48 operations; the drift guard was
  satisfied, not silenced). Expected: visual-baseline diffs on the reworked screens —
  re-cut from CI per the standing rule (owner 2026-08-30).

* **The AM-31 gate is RELEASED — Gemini is live end to end** (owner confirmation,
  2026-08-31: paid-tier no-training terms per ai.google.dev/gemini-api/terms "Paid
  Services", verbatim-quoted in the appended record **"AM-31 GATE RELEASE"**;
  `all_lock.md` 16,565 → 16,616, prior lines byte-identical). One commit per g3:
  record + `AM31_GATE = "RELEASED-2026-08-31"` + the two tests that pinned the closed
  state now pin the released one. Same session: the provider retired
  `gemini-2.5-flash` for new accounts, so the pin moved to **`gemini-3.6-flash`** with
  `thinkingLevel: MINIMAL` (unconstrained thinking measurably consumed the whole
  output budget; AM-30 locks the family, not the version — decision #223), and the
  key was installed outside the repository (`0600`), audited absent from repo and
  logs (hash-only audit, t5). **End-to-end proven on the live dev app** (synthetic
  only, 55.3): upload → index → ask → `ANSWERED` with a verified citation; the
  sufficiency floor exercised live (a 77-char evidence set refused). Still owed
  before assist answers over real material are relied on: the Tier-2
  faithfulness/citation-precision baseline as a release-pipeline act (release r3),
  and t8's network allow-list stays a deployment ATTEST. Backend **941 tests** green.

* **UX correction (owner-ordered "DEEP UX / PRODUCT MODEL AUDIT"): upload-first intake,
  analysis in the flow.** Full proposal + change matrix:
  [docs/design/UX_CORRECTION_2026-08-31.md](docs/design/UX_CORRECTION_2026-08-31.md).
  The intake had leaked the backend object lifecycle into the product (create an empty
  named/typed record → open an empty workspace → attach the file), and — the root
  finding — **analysis was unreachable in the UI** because no endpoint read published
  configuration snapshots, so "analyze against the current standards" could not be
  resolved. Corrected end-to-end:

  - **Documents is upload-first**: one primary act ("Upload a contract", picker + drop
    zone). The confirm panel keeps exactly two decisions with the user — Name (derived
    from the filename as an editable default) and Type (HUMAN-declared, owner Q9 intact:
    the select starts empty; a filename token hint is text beside it, applied only by the
    user's click; deliberately no LLM classification — AM-31 is closed, and a model
    pre-filling an authoritative comparison choice would blur classification/authority).
    "Upload and analyze" chains create → upload → latest-snapshot → Review → analysis,
    best-effort: every failure degrades to an honest workspace state, never a dead end.
  - **The absent Review is now an ACTION**: the findings pane's no-review state is
    "Analyze against current standards" with the snapshot id named on screen (AUD-04
    visible), honest blocked states for no permission / no published snapshot / still
    processing. A freshly uploaded revision gets the same control — Journey D is one
    screen.
  - **Documents rows speak analysis, not lifecycle enums**: DRAFT is gone from the list;
    each row shows classification counts (attention-first order) or the real stage
    ("Processing…", "Not analysed yet", "No document yet").
  - **Two additive API reads** (Step 49 record updated, the #187 precedent):
    `GET /configuration/snapshots` (metadata only, `review.create`) and
    `latest_version`/`latest_analysis` on `GET /contracts` rows (permission-layered;
    counts OMITTED without `finding.view`). No schema change, no engine change, nothing
    removed; the API drift guards fired and were satisfied deliberately (registry +
    regenerated `openapi.json`).
  - Journey specs are now END-TO-END THROUGH THE UI: upload → chained analysis →
    findings → ask, and revision → one-click analyze → both histories intact.

  Verified: backend **941/1** (+3) · **107 Vitest** (+3) · browser **57 passed / 18
  gated** · ruff · mypy · typecheck · terms gate. The visual system is untouched (freeze
  respected; this is the owner-requested UX review #222 anticipated); the
  `ws-documents.png` baseline diff re-cuts from CI in one round. Decisions #227–#230.

* **Product-intent R&D + corrective implementation (owner-ordered).** Full audit of the
  system against the owner's clarified product behavior — recorded in
  [docs/00-project/PRODUCT_INTENT_AUDIT_2026-08-31.md](docs/00-project/PRODUCT_INTENT_AUDIT_2026-08-31.md)
  (§A–O: architecture, semantics, authority model, lifecycle, impacts, blockers).
  Verdict: the locked specification and the owner's intent already agree on the five-axis
  separation, MATCH/DEVIATION/MISSING semantics, CONFLICT's defined meaning
  (intra-document contradiction, never company-vs-counterparty difference), ungated
  document chat, and real re-analysis. Three genuine gaps found and corrected:

  **1. `AM-33` (AB-6) — the threshold-band Legal Rule form is withdrawn.** `all_lock.md`
  grew 16,494 → 16,565 lines (append-only; insertions verified, zero deletions). The
  engine's live band interpreter (`acceptable_max`/`approval_required_above` — including
  the DEVIATION→ACCEPTABLE mapping the owner explicitly forbade) is removed: band keys
  now fail closed to `NOT_APPLICABLE` and a human, and a blanket
  `deviation_outcome: ACCEPTABLE` is refused the same way — **ACCEPTABLE is reachable
  only from MATCH** (r3). 45B.9's Standard-vs-Rule separation is reaffirmed; only its
  band example is superseded. Enforcement: the corpus loader now refuses band keys on
  EVERY tier (STRUCTURAL included, r6); the e2e bootstrap and eleven structural corpus
  fixtures moved to the authorized blanket form; §24 regression tests added
  (`test_band_keys_are_never_interpreted`,
  `test_a_deviation_never_maps_to_acceptable_through_any_rule_form`). The locked B-3
  heterogeneous-workflow tests keep exercising the ACCEPTABLE axis value by constructing
  it directly — the vocabulary (Step 20, 45B.26) and the workflow semantics over it are
  unchanged, historical rows included.

  **2. Revised-version upload in the workspace** (intent §3): "Upload a revised version"
  is now a quiet, always-available control once a document exists — a new version, a
  genuinely new analysis, nothing auto-resolved (rule 14).

  **3. Historical versions are first-class** (intent §4/§17): the workspace takes
  `?version=`, the context bar grows a version picker when more than one exists, the
  document and findings panes follow the selected version — and the Ask region states
  plainly that answers are about the LATEST version when an older one is open (verified:
  the server resolves conversations to the newest version), instead of misattributing.

  **API unchanged** (the frozen contract already carried everything); **database
  unchanged**; UI freeze respected (smallest semantic-necessity changes only). Two
  journey specs pin the §23/§31 flows end-to-end: upload → analysis → report → findings
  → ask-with-findings-open, and v1 → chat → v2 → both histories intact. Final sweep:
  no rule configuration anywhere carries a band key; every remaining mention is a
  guard, refusal, or redaction list. Verified: backend **938/1** (+1) · **104 Vitest**
  (+2) · browser **57 passed / 18 gated** (+3) · ruff · mypy · typecheck · terms gate.
  Decisions #223–#226. Expected: visual-baseline diffs where the e2e rule's outcome chip
  changed (APPROVAL_REQUIRED → UNACCEPTABLE) — re-cut from CI per the standing rule.

* **Signed-out visits now land on /login** (owner ruling, 2026-08-31: *"the correct
  process: I log in, and then I land on the page based on RBAC"*). Previously a
  signed-out visit to any `/workspace` route rendered the new shell with an empty nav
  and the page's own "Access restricted" note — indistinguishable from an RBAC denial.
  `WorkspaceShell` now redirects a resolved-but-absent session to `/login`
  (client-side `router.replace`, the measured Next 16.3.1 pattern; hook declared above
  every early return — the React #310 lesson), rendering the quiet loading placeholder
  meanwhile, never a restricted flash. Page-level permission gates are untouched: they
  remain correct for an authenticated account that genuinely lacks a permission. The
  spec that pinned the old behavior now pins the new one, plus a deep-link case
  (`workspace.spec.ts`). Frontend: typecheck clean, 102 Vitest, browser suite 55/55.

* **UI FREEZE (owner-ordered) — final visual QA closed, baselines complete, CI green.**
  The nine new-UI baselines (documents, reviews, report, legal, ask history, transcript,
  research, admin, audit trail) were generated by CI, inspected render-by-render, and
  adopted from the `visual-regression-diffs` artifact — never locally. The set is now
  **15 screenshots** (6 legacy-era + 9 new-UI). One real defect surfaced by the process:
  the first baseline spec shared a module-level fixture across tests, and Playwright's
  worker restart on each missing-baseline failure wiped it — rewritten to the file's
  per-test idiom. Final verification re-confirmed containers, masks, responsive collapse,
  states and the login→new-UI boundary (all e2e-pinned). **Full matrix at the freeze:
  backend 937/1 · 102 Vitest · 54 browser passed / 18 gated · typecheck · forbidden-terms
  · CI 15/15 green (run on f9c3c0f).** From here the UI changes only for genuine defects
  (usability, accessibility, inconsistency, responsive, broken interaction, strategy
  mismatch) or new functionality — never polish; memory `legalmind-ui-freeze` records the
  rule. Decision #222.

* **UX audit of the whole new UI (owner-ordered), with fixes** — every screen captured
  with real fixture data at 1440px and 840px through a temporary gated Playwright harness
  (deleted after use), judged against the ratified master prompt and the ui-ux-pro-max
  checklist. Six findings, all fixed:

  1. **Structured values rendered as clipped JSON blobs** in finding cards ("Found in
     contract {"scope":"GENERAL","cap_unit":"months",…" cut mid-string at three-pane
     width). Now labeled key–value pairs that wrap — the server's keys and values
     verbatim, presentation only (rule 12 untouched).
  2. **The transcript page had no page container** — content flush against the viewport
     edge. 3. **The report body likewise.** 4. **Research likewise.** All three now sit in
     the same centered 72rem `.ws-docs` gutter as every other screen, and a CSS rule gives
     every bare full-page state (restricted/loading/not-found) the same alignment.
  5. **`ws-chip--flag` ("Decision required"/"Escalated") rendered oversized** — it lacked
     the chip metrics and inherited body type. Now chip-sized; the fill carries the
     weight, not the type size.
  6. **"report" vs "Report" casing** drift between the Legal queue and the Reviews screen.

  Judged fine and left alone: exact enum vocabulary in chips and selects (the Authority
  register is deliberate), the full-width primary at collapsed widths, the audit trail's
  density, and the empty states. Verified after fixes: **102 Vitest · 54 browser passed /
  9 gated · backend 937/1 · typecheck · terms gate clean.** Known consequence, flagged:
  the gated `workspace.png` visual baseline now differs — CI's DESIGN_QA job will fail
  once, and the new baseline is adopted from **CI's artifact** per the 2026-08-30
  CI-only-baselines rule (never `--update-snapshots` locally). Decisions #219–#221.

* **UI/UX slices 7–8 + the QA close — the roadmap's build order is complete** (owner:
  "you are the developer and lead this project"). The new UI now covers every §E screen
  that V1 backs:

  **Slice 7 — the admin plane.** `/workspace/admin` (Users & roles, `user.manage`): an
  account is created holding NO roles and the row says so plainly ("no roles — cannot act
  yet", 47.1.3); roles are chips with labeled revokes plus a grant control (hidden, with a
  note, without `role.manage` — `GET /roles` gates on it); disable/restore flips status
  and every server refusal (SEC-05's last-authority guard included) renders beside the
  row that caused it, worded by the server. `/workspace/admin/audit` (`audit.view`): the
  append-only trail, newest first, with the 49.6 exact-value filters (action, entity
  type) and the omitted-not-nulled state payloads not rendered at all. e2e: the full
  provision lifecycle (create → grant → revoke → disable) round-trips, the audit filter
  narrows to `admin.user_created`, and `owner` gets the restricted state and no nav item.

  **Slice 8 — Research, the ONE disclosed placeholder** (§E screen 10). It states why it
  is empty — the statute corpus is not ratified (C-16, an owner decision) — and offers
  nothing interactive: no search box faking capability, no link, no button
  (Vitest-pinned, the NextSlice discipline).

  **The QA close (roadmap step 10).** Keyboard/skip-link/collapse specs pass across the
  grown nav; aria-pressed toggles, labeled icon buttons, aria-busy skeletons,
  reduced-motion cover, and the focus-ring deep links are all pinned by tests written
  slice-by-slice rather than audited after the fact. Final state: **Documents · Reviews ·
  Legal · Ask history · Research · Admin** — all in the new shell, no navigation path
  into the legacy app anywhere. Verified: backend **937/1** · frontend **102 Vitest**
  (+1) · browser **54 passed / 9 gated** (+3) · typecheck · forbidden-terms clean.
  Deferred, stated: visual-regression baselines for the new screens (CI-only baseline
  rule — cut from CI artifacts, never locally) and the §E screen-14 placeholders that
  stay states-only by design. Decisions #216–#218.

* **UI/UX slice 6 — the Legal area** (owner: "NExt phase"). `/workspace/legal`, gated by
  `legal.review`: every Finding whose Evaluations await a Legal Decision, across the
  Reviews the account can see, in one flat queue — requirement, classification,
  escalation flag, document, review status, report link.

  **The queue triages; it never disposes.** A Legal Decision is made beside the evidence
  (master prompt), so each row deep-links into the document workspace with a new
  `?finding=` parameter: the findings pane scrolls to that exact card and moves focus to
  it (the same gesture `?evidence=` gives the document pane — widening the attention view
  if the target is outside it), where slice 2's decision flow already lives. Holding
  `legal.review` still confers no decision authority (SEC-01); the workspace's form
  enforces `legal.decision` server-side.

  **Composition, not a new endpoint**: there is no cross-review findings API, so the
  queue reads the two ACTIVE review statuses through `GET /reviews` (REC-09 scope
  server-side) and fans out per review to `findings?status=DECISION_REQUIRED`,
  page-bounded; when either list has more pages the screen says so plainly instead of
  implying completeness.

  Also unified the status-filter idiom: slice 5 had quietly introduced a second
  `.ws-filter` pattern next to slice 2's — the duplicate CSS is removed and the Reviews
  screen now uses the same aria-pressed toggle the findings pane always had. One e2e
  assertion of mine was corrected by the run itself: the queue rightly shows
  `STRUCTURAL-E2E-001` (rule 21 — the e2e config carries no real code), so the spec now
  asserts the code the API returns instead of a hardcoded `LIABILITY-001`. Verified:
  backend **937/1** (unchanged) · frontend **101 Vitest** (+1) · browser **51 passed / 9
  gated** (+2) · typecheck · forbidden-terms clean. Decisions #213–#215.

* **UI/UX slice 5 (P1) — the Reviews queue, the Review report, and Ask history**
  (owner: "continue from the phase you completed"). Three read surfaces over endpoints
  that already existed, completing PRODUCT_UX_ROADMAP §E screens 7–9:

  **Reviews** (`/workspace/reviews`) — the queue. Scope is entirely server-side (REC-09:
  own + assigned, plus everything escalated or in LEGAL_REVIEW for `legal.review`
  holders); the page adds no scope logic. Status filters are the API's own allow-list,
  one at a time; LEGAL_REVIEW rows carry the attention stripe and a filled chip — queue
  bias, no urgency theater. Starting a Review stays deliberately absent (snapshot-choice
  UX unscoped) and the empty state says so plainly.

  **Review report** (`/workspace/reviews/{id}`) — exactly what `GET …/report` carries:
  coverage, findings awaiting a Legal Decision, unmatched provisions, and the alignment
  count — with the F-9 sentence on the page ("never grades the document"). No risk
  figure, no verdict, no meter — counts in the mono voice, attention stripe only where a
  human owes work. `report.view` is layered: without it the Review's identity shows and
  the report body is a plain restricted note, never faked.

  **Ask history** (`/workspace/ask` and `…/ask/{id}`) — the caller's OWN conversations
  (`AM-25` r7 server-side), each transcript replaying the SAME citations the live answer
  carried (`AM-25` r5) as real links into the workspace highlight (`?evidence=`), and the
  byte-identical refusal sentence (`AM-29` r4) — pinned by e2e against the recorded turn,
  not just the live one. A replayed citation may lack a retrieval score (missing run
  row): the type now says so (`retrieval_score: number | null`) and both the new
  transcript and the LEGACY AskPanel guard it — the widening surfaced a latent
  `.toFixed()` crash path in the legacy pane, fixed rather than suppressed.

  **Navigation grew and got correct**: Reviews and Ask history join the nav (existence +
  permission gated), and the active item is now the LONGEST matching href
  (`activeNavHref`) — before this, "Documents" (`/workspace`) lit on every sibling
  screen. Verified: backend **937/1** (unchanged) · frontend **100 Vitest** (+4) ·
  browser **49 passed / 9 gated** (+3, all first-run green) · typecheck ·
  forbidden-terms clean. Decisions #210–#212.

* **UI/UX slice 4 — the Documents landing and intake screen** (owner: "go"). The minimal
  stand-in the strict cleanup left at `/workspace` is now the real front door
  (PRODUCT_UX_ROADMAP §E screens 2–3): the document TYPE is the one prominent **required**
  choice — Step 6's ten values in a select, declared, never inferred (owner Q9), with the
  reason stated beside the field — and "Add and open" lands directly in the new document's
  workspace, where the upload already lives, so intake is one continuous act. First-run
  empty state makes adding a document the onboarding (no tour); skeleton rows while
  loading; type/status chips per row; pagination; error and permission states.

  **The vocabulary is a presentation copy with a parity guard**: `src/lib/documentTypes.ts`
  mirrors `legalmind/domain/document_types.py`, and a new backend test
  (`test_frontend_vocabulary.py`) fails CI if the two ever differ — the frontend must not
  reach the backend source at build time (52.1), and no endpoint exposes the vocabulary,
  so a checked copy is the honest option. The UI requires a type even though the API
  accepts a contract without one: presentation stricter than the contract, because an
  undeclared type only ever fails later at analysis (`ANALYSIS_FAILED`) — better refused at
  the door with the reason than accepted and refused downstream. API unchanged.

  **Two of my own errors caught by the tests, recorded rather than smoothed over**: a
  text-splice while rewriting the e2e file left an orphaned test body that made the file
  unparseable — and a filtered "exit 0" briefly read as a pass until an unfiltered run
  showed "No tests found" (the lesson: never trust a grep-filtered summary); and the new
  form-name regex matched only the first-run heading, passing in isolation on a fresh DB
  and failing in the full file. Both fixed; the suite is now the arbiter again.

  **Declared out of scope, plainly**: a per-row "review state" column — the list endpoint
  deliberately stays lean (decision #187), so that needs a list-level summary field first
  (a §19 candidate, not smuggled in); Review creation from the landing (snapshot choice);
  retiring the legacy contract-detail page (it still uniquely hosts review creation and
  download). Verified: backend **937/1 skipped** (+1, the parity guard) · frontend **96
  Vitest** (+2) · browser **46 passed / 9 gated** (+1 intake spec) · typecheck ·
  forbidden-terms clean. Decisions #207–#209.

* **UI/UX slice 3 — the Ask pane in the Inquiry register, citations wired to the
  highlight** (owner: "yes go ahead with next phase"). The workspace's third region is
  live: ask about the open document, get an answer whose numbered citations *point at the
  document* through the same gesture as a verdict's evidence link, or the identical quiet
  refusal (`AM-29` r4), or — for a compliance-shaped question — an explicit "Not answered
  here" pointer toward Findings (`AM-25` r4), a third message type styled as neither an
  answer nor a refusal. Colorless by design: no state-axis hue appears in this pane, so a
  cited answer can never be mistaken for a ruling (master prompt §4.1). One honest status
  line while a request is in flight; retrieval scores as plain mono text, labelled as
  exactly that; the word "confidence" appears nowhere and is CI-gated.

  **One smallest-justified backend change**: every citation — live (`POST
  /conversations/{id}/messages`) and replayed (`GET /conversations/{id}`) — now carries
  `evidence_id`, the evidence row the chunk was cut from. Slices 1–2 key the highlight
  on evidence-row ids (a Finding's `evidence_refs` are evidence ids); a citation carried
  only `chunk_id`, a different table, so without this field the Ask pane could not point
  at the document at all. The data already existed (`SearchHit.evidence_id`, and the
  replay SQL already joined `document_evidence`); it was simply never serialized.
  Additive, dict payload — the frozen OpenAPI snapshot is byte-identical. Recorded in
  Step 49's additions section (#204).

  **What a browser can and cannot prove here, stated plainly**: the e2e specs prove both
  refusal causes render the identical sentence in the new pane and that a compliance
  question routes rather than answers — the real backend under the real `AM-31` posture
  (no generator credential exists in CI, exactly as in production today). The ANSWERED
  path — prose plus citations that highlight — **cannot** be exercised end-to-end until
  the gate opens, so it is pinned by static render instead (the citation button carries
  `data-evidence-id`, the score label, no "confidence"). That gap is the gate's, not the
  UI's, and closes the day the owner's two external inputs arrive.

  Verified: backend 936/1 skipped (28 assist tests incl. the extended citation-replay
  parity check) · frontend **94 Vitest** (+4) · browser **45 passed / 9 gated** (+2, both
  first-run green) · typecheck · forbidden-terms gate clean · OpenAPI drift clean.
  Decisions #204–#206.

* **UI/UX slice 2 — the Findings pane, wired to the highlight mechanism, against the real
  API** (owner: "ok now go ahead" — continuing PRODUCT_UX_ROADMAP's phased sequence).
  The workspace's Findings region is no longer a placeholder: it resolves the Review for
  the current document version (`GET /reviews?contract_id=` — an existing, already
  allow-listed backend filter, only newly exposed in the frontend client; no backend
  change), then renders the decision queue exactly per 52.5/DD-1: needs-decision first,
  an equal-weight "All findings" toggle, never hidden.

  **Per-axis chips, not a merged badge**: classification and rule outcome each render in
  their own hue (indigo / amber), filled only for a non-calm value (`MATCH` and
  `ACCEPTABLE`/`NOT_APPLICABLE` stay a quiet ghost chip) — no severity ranking invented
  within an axis, matching the master prompt exactly. **Evidence links reuse slice 1's
  highlight mechanism verbatim**: clicking "Evidence 1" on a citation scrolls, lights and
  focuses the exact document row — a verdict and a citation now point at the source
  through the identical gesture.

  **`DecisionControl`** ports the legacy `DecisionPanel`'s safety properties rather than
  reinventing them: no optimistic UI (52.7), and a `409` freezes the form until an
  explicit "Refresh to see the latest decision" — proven end-to-end in the browser
  (a real second decision via direct API call, a real conflict, a disabled form, an
  explicit refresh showing what won). **Caught and fixed before it shipped**: the first
  draft called the refresh but never reset local state back to idle, which would have
  left the form frozen forever after one conflict even with fresh data — found in review,
  not by a user. **`EscalateControl`** is deliberately quiet — an underline control, never
  styled like the one button that changes the legal record (master prompt: "decision
  authority is visually distinct from decision-adjacent activity").

  **Declared out of scope, stated plainly rather than built around**: when no Review
  exists yet for a document version, the pane says so and explains why, without an
  id-pasting form or a link back into the legacy app — creating a Review needs a
  published configuration snapshot, a distinct capability the roadmap doesn't scope into
  "the Findings pane." Decision history stays to the current decision only (no
  expandable superseded log) and keyboard shortcuts for this pane are deferred —
  both named as exclusions before writing any code, not discovered as gaps after.

  Verified: backend 936/1 skipped (untouched — no backend file changed) · frontend
  **90 Vitest** (+2) · browser **43 passed / 9 gated** (+3 Findings-pane specs: chips
  render and an evidence click highlights the document, a decision records and a 409
  correctly freezes-then-recovers, escalation renders as a request not an approval) ·
  typecheck · forbidden-terms gate clean. Decisions #200–#203.

* **Strict frontend cleanup — the new UI is now the entire post-login experience**
  (owner: "STRICT FRONTEND CLEANUP — KEEP LOGIN ONLY", 2026-08-30). Login is untouched;
  everything after it now leads into the new application, never the legacy one.

  **Entry point retargeted**: root `/` and a successful login both resolve to
  `/workspace` (was `/contracts`) — `src/app/page.tsx`, `src/app/login/page.tsx`,
  `e2e/support.ts`'s `signIn()` helper. A new **Documents index** (`/workspace`) is the
  actual landing screen — a minimal, faithful analog of the legacy list-and-create page
  (same two API calls) rebuilt on the new shell, since without it a fresh session had
  nowhere real to land.

  **Every remaining link into the legacy app was found and removed**, not hidden: the
  new shell's own wordmark and "not found" state pointed at `/contracts`; the empty
  workspace state's "Upload a document" was a `<Link>` to the legacy contract page; the
  Findings/Ask `NextSlice` placeholders linked to `/reviews` and `/contracts/{id}`; and
  — the one that mattered most — the shell's own primary nav still mapped "Documents" to
  `/contracts` and offered a live "Reviews" link into the legacy queue. Fixed:
  `NextSlice` now carries plain text only, no link, ever (its capability note says the
  legacy application still works, without a click path there); the empty state gained a
  real **inline upload** (`UploadDocument.tsx`, the same `api.uploadDocument` call, just
  never leaving the new screen to use it); and `navItemsFor` now offers a nav item only
  once its destination is a real new-UI screen — today that is Documents alone, so
  Reviews/Legal/Audit/Admin are absent from the new shell's nav until each is built
  (roadmap slices 2, 4, 5), rather than pointing at a screen this product line is
  retiring. A unit test now asserts structurally that no nav item ever matches a legacy
  route pattern.

  **Two real bugs found and fixed while proving the redirect, not assumed working**:
  (1) `Chrome`'s `!identity`/`loading` branches never rendered `{children}` at all, so
  root `/`'s own page component — whose only job is a client-side
  `router.replace("/workspace")` — never even mounted for a signed-out visitor, and the
  redirect silently never fired; the new-UI bypass (previously `/workspace` only) now
  also covers `/`, for exactly this reason, not styling. (2) The root page originally
  used the Server Component `redirect()`, measured (via `curl -I` against a production
  build) to return `200` with no `Location` header and no `<meta refresh>` — Next
  16.3.1 (this frontend's own `AGENTS.md` warns it is not the Next.js prior training
  data describes) encodes it in the RSC flight stream instead, which did not complete
  through this app's `SessionProvider`/`Chrome` tree; replaced with the same
  `useRouter().replace()` client-side pattern `login/page.tsx` already uses successfully.

  The legacy application is otherwise **completely intact** — no route deleted, no
  backend endpoint touched, no test weakened. Every legacy Playwright spec still
  navigates directly to its route by URL (never via a clicked nav link) and all pass
  unmodified; that direct-URL path is deliberately preserved as the verification
  harness the owner asked to keep. Verified: backend 936/1 (untouched) · frontend
  **88 Vitest** (+1) · browser **40 passed / 9 gated** (three new specs proving no
  `a[href^="/contracts"]` exists anywhere in the new UI, that a fresh login lands on
  `/workspace`, and that the Documents index links only into the new UI) · typecheck ·
  lint. Decisions #194–#199.

* **UI/UX implementation, slice 1 — the new workspace shell, the document pane and the
  cross-pane highlight, against the real API** (owner: "UI/UX IMPLEMENTATION — GO",
  2026-08-30; PRODUCT_UX_ROADMAP §G's risk-first slice). A new `/workspace/[contractId]`
  route with its own shell — the product's one dark surface, navigation derived from
  permissions by absence, a skip link first in the tab order — and the three-region layout
  that collapses to real tabs (role=tablist, arrow keys) at 1280/900px, never dropping a
  region. The **document pane** renders the document as the pipeline read it (evidence
  rows in reading order under page markers, verbatim text in the serif quote voice, OCR
  rows labelled, the document's own clause outline beside it, readiness derived from
  `assist_index` counts) and answers the **highlight gesture**: an outline click or a
  shared `?evidence=<id>` link scrolls to, lights and *focuses* the exact row — proven in
  the browser; every later trigger (verdict, citation) reuses this one mechanism. States:
  loading (announced skeleton), still-processing, no-text-extracted, error with request id,
  no-upload (offers the upload — a link, nothing fake), whole-section permission state,
  and the byte-identical "Not found." for out-of-scope and nonexistent contracts (asserted
  equal in the browser). Findings and Ask regions render as honest next-slice notes
  (`NextSlice`, distinct from `DomainPlaceholder`: UI not yet built vs backend not offered).
  Design foundation (`workspace.css`, scoped `.ws`) implements the master prompt's tokens
  on the **system font stack** pending the bundling decision (DD-7 §6); the type *roles*
  hold. **One smallest-justified backend change**: `GET /contracts/{id}` now carries
  `document_versions` newest first — a document-anchored workspace had no API path to its
  document (the legacy page only ever showed the version it had just uploaded); additive,
  same permission, frozen contract regenerated (the one diff is the operation description),
  recorded in Step 49's additions section. Legacy routes untouched; `Chrome` yields to the
  new shell under `/workspace` so the two never render together. Verified: backend **936**
  (+1), frontend **86 Vitest** (+7), browser **37 passed** (+7) with 9 gated, six visual
  baselines reproducing (the five legacy ones were re-cut locally — a mistake corrected the same day by
  the parallel session, which re-adopted CI's renders and added a guard refusing
  `--update-snapshots` outside CI; the dev box renders fonts ~1% differently and has the
  embedding model present. Owner rule: baselines come from CI only — decision #193), typecheck (after `next typegen` — the running dev server's stale
  generated types were the only "error"), lint clean. Decisions #187–#192.

* **The product-UX roadmap — the think-first deliverable before broad UI implementation**
  (owner directive, 2026-08-27 evening: senior-designer strategy first, roadmap not app;
  legacy UI fully disregarded as a design reference).
  [docs/design/PRODUCT_UX_ROADMAP.md](docs/design/PRODUCT_UX_ROADMAP.md), `PROPOSED`:
  the A–M strategy grounded in the current Product Vision and verified against the live
  system rather than remembered — the role model is read from the actual grant matrix
  (finding, among else, that SUPER_ADMIN cannot open a contract at all, so admin is a
  genuinely separate control plane, and that ordinary users hold no `configuration.view`,
  so Domain A lives under a Legal nav area rather than global navigation). Decides:
  landing = Documents, no dashboard (nothing backs one); Review+Ask together in the
  adopted [WORKSPACE_UI_PLAN.md](docs/design/WORKSPACE_UI_PLAN.md) three-pane workspace
  (DD-7 — superseding the master prompt's own drawer sketch); Research separate (the one
  document-less experience); no Settings/Profile screens (nothing real backs them);
  build order risk-first — the document pane + cross-pane highlight before everything,
  login deliberately fifth. Names the three API gaps honestly (positions-search endpoint
  exists as a function with no route; cross-review attention rollup deliberately not
  requested; Domain C blocked on C-16 material) and the risks that must not be finalized
  against — foremost the vision's future external users colliding with `LEGAL-02`'s
  confidentiality of Domain A, an owner ruling. One decision escalated: the master
  prompt's Google-Fonts typography vs DD-4's no-runtime-CDN ruling — system stack until
  `next/font` bundling is approved (rule 19). `ui-ux-pro-max` consulted with adopted and
  rejected guidance cited, including one declared no-match fallback. **No implementation
  started** — the roadmap awaits owner review, per the directive's own working principle.

* **UI/UX execution phase, first hardening pass — skeletons, keyboard navigation, the
  frozen-conflict flow, and two new design gates in CI** (owner directive, 2026-08-27:
  implement the missing pieces and prepare for usability testing). Frontend **79 Vitest**
  (+11) and **30 browser items** passing, typecheck clean, plus **8 deliberately gated
  specs** (5 visual baselines, 3 documentation captures) that run outside the default suite.

  **Loading skeletons** (`Skeleton.tsx`) on the review list, the findings pane and the Ask
  answer area — each matching the final layout's container so arrival causes no layout
  shift, `aria-hidden` shapes over the existing `aria-live` text announcement, static under
  `prefers-reduced-motion` (reconciling the owner's shimmer request with DESIGN.md's
  shimmer caution: functional skeleton yes, decorative implication of content no). The Ask
  skeleton carries **one honest status line** — the client sees a single request, so the
  mockup's staged "searching → verifying" sequence was dropped rather than faked with
  invented timings. The requested PDF-preview skeleton has no surface to attach to:
  documents are deliberately download-only (`attachment`, never rendered in-origin — 34.16
  posture), recorded rather than built around.

  **Keyboard navigation** on the Review screen: `n`/`p` walk the current view's findings,
  `d` jumps to the decision form, `?` opens a real dialog listing the bindings from the
  same table the handlers read. **`a`/`r` prepare, never record** — they preselect a
  decision type and focus the mandatory justification; a browser test proves no keyboard
  path emits a `POST /decisions`, and shortcuts are inert while typing (a justification
  containing "a" must not steer the form).

  **The 409 conflict now freezes the form** until an explicit "Refresh to see the latest
  decision": the earlier auto-refetch was well-meaning but shifted the ground under a
  decision-maker mid-read. The e2e conflict spec now walks the full loop — real second
  decision, real 409, disabled submit, explicit refresh, re-enabled form showing what
  actually won (52.7).

  **CI job 15 — Design QA**: (1) a forbidden-terms gate (`confidence`, `risk_score`,
  `probability`, `likelihood`, `ai_confidence`) over non-test frontend source with
  comments stripped — **proven to fail** on a planted violation before being trusted
  (exit 1, file:line named); (2) Playwright **visual regression at a 0.1% pixel
  threshold** over five surfaces (login, reviews list, review detail, contract/upload,
  admin), volatile ids/dates masked, gated behind `DESIGN_QA=1` with a freshly
  bootstrapped database so baselines are content-deterministic — **verified to reproduce
  across two full rebuilds** before committing. `npm run design-qa` runs it locally; new
  scripts `test:all`, `test:e2e`, `check:terms`, and `lint` (typecheck + terms — no ESLint
  dependency added; adopting one is a rule-19 approval).

  **Documentation:** [docs/design/UI_PATTERNS.md](docs/design/UI_PATTERNS.md) explains the
  two deliberately unusual patterns — confidential omission and the identical refusal —
  with screenshots captured from the real application against synthetic fixture data
  (regenerable via `DOCS_SHOTS=1`); [docs/design/USABILITY_TEST_PLAN.md](docs/design/USABILITY_TEST_PLAN.md)
  is the five-person think-aloud plan, including the permission-probe task where the pass
  condition is the participant noticing nothing.

* **Full UI/UX R&D pass — all prior identity/layout decisions cancelled and superseded**
  (owner directive, 2026-08-27: *"Cancel all previous UI/UX decisions... give you ONE prompt."*).
  Documentation only — no frontend code changed yet. Researched via `ui-ux-pro-max`
  (`--design-system`, `--domain ux/typography/color`), cross-checked against this repo's locked
  constraints; two real defects found in the prior work (a one-page deep-navy `/login` identity
  that never extended to the rest of the product, and the Review screen's list/detail layout left
  as an unfinished proposal since 2026-08-21) rather than restyled cosmetically. New authoritative
  document: [docs/design/UI_UX_MASTER_PROMPT.md](docs/design/UI_UX_MASTER_PROMPT.md) — one
  persistent shell (finalizing `DD-1`'s bounded-list-plus-detail proposal), a two-register visual
  system distinguishing the legal-authority workflow from the new AI assist surface so neither can
  be mistaken for the other, a five-axis color namespace refinement, an IBM Plex Sans/Mono +
  Source Serif 4 (verbatim-quote-only) type system, and an explicit rejection of three generic
  AI-chat conventions (token streaming, thumbs-up/down feedback) that would have conflicted with
  the citation-verification and non-learning requirements already locked (`AM-25`, `AM-28`).
  `DD-6` in [DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md) records exactly what's
  superseded (`DD-1`–`DD-5`) versus what's untouched (every locked behavioral rule — confidentiality
  rendering, the five-axis model, no-optimistic-UI — none of which is a "UI/UX decision" the
  cancellation instruction reaches).

* **Five-phase gap-closing pass on the owner's 2026-08-27 directive**, which also
  granted the UI/UX greenlight (decision #167). Delivered: **the AB-5/`AM-32` amendment
  draft** ([docs/00-project/AB5_DOMAIN_CORPUS_PROPOSAL.md](docs/00-project/AB5_DOMAIN_CORPUS_PROPOSAL.md))
  resolving C-15 on approval — six tables, no positions copy (chunks reference the
  ratified `company_standard_versions` rows), per-domain embedding tables for real FKs,
  and Domain A extractive-only because `AM-30` t3 forbids Company Standard values in
  egress (#168); **`tools/verify_gemini_connection.py`** (+9 tests) through the one
  permitted seam, config-only by default, synthetic-only `--live` (#169), with
  [GEMINI_ACTIVATION_RUNBOOK.md](docs/09-implementation/GEMINI_ACTIVATION_RUNBOOK.md)
  covering key → verify → gate-opening record → deferred quality-gate half;
  **[STATUTE_INTAKE.md](docs/00-project/STATUTE_INTAKE.md)** for C-16 — India Code
  sourcing, the mandatory provenance record, section-based chunking design, and one
  new owner question (Evidence Act 1872 vs the Bharatiya Sakshya Adhiniyam 2023 that
  repealed it); **preflight row `egress_allow_list`** (ATTEST, `AM-30` t8 — register
  now **23 checks**, +1 test) and **[ops/README.md](ops/README.md)** mapping every
  operator step to its register row instead of duplicating the register (#170, #171);
  and **the Phase-2 UI plan**
  ([docs/design/WORKSPACE_UI_PLAN.md](docs/design/WORKSPACE_UI_PLAN.md)) — three-region
  workspace IA with the cross-pane evidence highlight as the signature interaction,
  skill-vs-DESIGN.md conflicts reported and resolved by precedence (#173), the
  disclosed-placeholder/absent-capability split (#172), plus the first component:
  `DomainPlaceholder` (+6 Vitest). **Not done, by our own rules**: no Domain A/C table
  exists (AB-5 awaits the owner), and `AM31_GATE` is CLOSED and untouched. Backend
  **911 tests** (1 skipped), frontend **68 Vitest**, ruff/mypy clean. Decisions
  #167–#173 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md).

* **Backend freeze declared and the UI/UX handoff written** (owner instruction, 2026-08-27:
  *"backend freeze / dependency-wait state... VERIFY → DOCUMENT → FREEZE → PREPARE HANDOFF →
  WAIT FOR OWNER INPUT"*). [docs/00-project/BACKEND_FREEZE_HANDOFF.md](docs/00-project/BACKEND_FREEZE_HANDOFF.md)
  records the four-way split — completed · blocked-by-owner-decision (C-15 foremost) ·
  blocked-by-missing-input (Google no-training terms, Gemini key, NI/Evidence Acts,
  judgment list, RIAAS details) · operator-only (the preflight's ATTEST/BLOCKED rows,
  none relabelled) — plus the verified API contract (45 operations, envelope, error
  taxonomy, permissions, the four assist answer states and the byte-identical refusal
  sentence) and the UI/UX readiness assessment (stable / likely-to-change / blocked, with
  the two statuses kept explicit: *the API surface is stable enough to begin UI/UX; the
  product is not complete*). **No application code changed.** Everything re-verified
  first on 2026-08-27: backend 901 passed / 1 skipped · ruff and mypy clean · frontend
  typecheck + 62 Vitest · Playwright **27/27** (after reinstalling the dev host's missing
  Chromium binary — environment only, `~/.cache/ms-playwright`, no repository change) ·
  `docs/api/openapi.json` drift-check clean · `AM31_GATE` CLOSED. The existing frontend
  is `LEGACY UI — DEFERRED`: preserved, green, still the backend-verification harness.
  UI/UX starts only on explicit owner authorization.

### Fixed

* **The core Review screen (`/reviews/[id]`) had crashed on load for every user since
  2026-08-24.** A `useRef` introduced by that day's sticky-queue code-review fix sat *below*
  the page's two early returns; the first render has no `reviewId` yet and returns early, the
  next render calls the hook, and React throws #310 ("rendered more hooks than during the
  previous render") into the production error boundary — "This page couldn't load." Typecheck
  and build cannot see a hooks-order violation, the Phase 3.5 work was verified by manual
  browser passes rather than the Playwright suite, and **CI never ran**: the workflow
  triggered only on `main` and pull requests, and five days of commits landed on a feature
  branch with neither. Found on 2026-08-26 the moment the browser suite was run by hand
  (13 of 22 tests failed, every one on that screen); fixed by declaring the hook above the
  returns; a scan of every page and component found no second instance. **Two guards so it
  cannot recur unseen**: CI now runs on every branch push (the `concurrency` group already
  cancels superseded runs), and the suite passes **27/27** including the new Ask spec.

* **Every fresh-database harness broke the day `chunk_embeddings` landed.** Migration
  `c4a91f6e2d87` correctly refuses to `CREATE EXTENSION vector` (untrusted → superuser-only, a
  deployment precondition `preflight` reports), but the e2e bootstrap, the reproducibility and
  invariant verifiers, the retrieval benchmarks and CI's container-fresh test databases all
  create brand-new databases — which have no extension, so the migration raised and the
  harness died before testing anything. Locally it hid behind long-lived databases that
  already carried the extension. `tools/pg_extensions.ensure_vector_extension` now makes each
  harness **try**: succeeds where the role is superuser (every CI service container, by the
  official image's design), no-ops where the extension exists, prints the one-time operator
  step where neither holds and lets the migration's own error follow. Migrations are
  unchanged — the precondition stance is a production property, and a harness provisioning
  its own precondition does not weaken it. Local one-time step recorded: pgvector installed in
  `template1` so every future local database inherits it.

### Added

* **The API contract is closed out for a new UI and frozen** (owner directive, 2026-08-26:
  *"Backend first. UI/UX later... When the backend/API architecture is genuinely ready to
  support a new UI/UX implementation, stop and tell me clearly."*). A readiness audit mapped
  every surface a workspace UI needs — document pane, verdict cards, chat panel with history,
  configuration/audit/admin — against the running API and found four gaps, all additive and
  all inside existing permissions: **`GET /conversations`** (own-only, `contract_id` filter,
  paginated — a workspace needs a document's history, and the list carries exactly what the
  single GET would so it cannot become the enumeration oracle `AM-25` r7 forbids);
  **`GET /conversations/{id}` now replays citations** rebuilt from the verified
  `answer_citations` rows, the chunk's evidence row and the retrieval run's per-chunk score
  (`AM-25` r5 binds every *view* of an answer — before this a reload lost them; a test
  compares the replay field-by-field with the live reply); **`GET
  /document-versions/{id}/evidence`** (paginated Evidence rows in reading order under
  `document.view` — the document pane and the target every citation points at; lineage and
  parser metadata stay server-side; recorded in Step 49's new implementation-additions
  section, not locked); and **`assist_index: {chunks, embedded_chunks}`** on the document
  version — counts, deliberately not a new state vocabulary (`AM-29` r1). **The contract is
  frozen as [docs/api/openapi.json](docs/api/openapi.json)** (45 operations), generated by
  `tools/export_openapi.py` and drift-tested so a contract change is always a visible diff
  in the commit that made it; Step 49 wins any disagreement. The existing frontend is
  preserved and still green (typecheck, 62 Vitest) — its design is now obsolete for planning
  and receives no further work. Backend **901 tests** (1 skipped). Decisions #162–#166 in
  [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md).

* **The Ask surface is browser-proven in the exact state users meet it today**
  (`frontend/e2e/ask.spec.ts`). With no provider credential present — precisely production
  until the `AM-31` gate opens — one ask retrieves evidence but cannot generate, another
  retrieves nothing at all; the spec asserts both render the **byte-identical** `AM-29` r4
  sentence (declared verbatim so a drift in either repository fails here), on the quiet
  surface with no error banner, with **no "confidence" string anywhere on the composed page**
  (`AI-03` item 16). It travels the whole live path: contract → upload → inline index →
  conversation → two asks through Next's proxy and the CSRF pair. `createAnalysedReview` now
  also returns `contractId` (additive). **First CI run corrected two things**: the spec's
  evidence-present question is now a strict subset of the fixture sentence, because lexical
  search ANDs every stemmed term and CI provisions no embedding model to rescue a query the
  way a developer's machine silently did (it passed locally on vectors and failed in CI —
  the spec now proves the same thing in both places, with the run reproduced locally under
  `LEGALMIND_MODEL_DIR=/nonexistent`); and job 14's Trivy pin gained the `v` prefix the
  action's tags actually carry (`v0.36.0`). That run was also the first CI verdict on the
  fresh-database harness fix: jobs 2, 11, 12 and 13 all migrated container-fresh databases
  green. **The second run gave the image scan its first real catch**: the backend image
  shipped `libssl3t64`/`openssl`/`openssl-provider-legacy` 3.5.6 with 3.5.7 already released
  (CVE-2026-14456, HIGH — one fix, three rows), because the `python:3.12-slim` tag floats
  behind Debian's security releases. Both Dockerfiles now apply distro security upgrades at
  build time, so the gate measures the image against today's fixes rather than the tag's
  build date (decision #157). **The third run scanned the frontend image for the first
  time**: Alpine and every application package clean, and 9 CRITICAL/HIGH inside the Node
  runtime's *bundled npm* (`tar` gzip-bomb DoS, `sigstore` certificate acceptance,
  `brace-expansion`/`picomatch` ReDoS) — not our dependencies, and invisible to `npm audit`,
  which reads only the lockfile. Resolved structurally rather than by version-chasing: the
  runtime image now deletes npm, npx and yarn after installing and starts Next through
  `node` directly — a serving image needs no package manager (#160). The same pass found
  `@playwright/test` leaking into the production install (Next declares it an optional
  peer, so npm marks it `devOptional` and `--omit=dev` keeps it); removed by name (#161).

* **UI/UX design skills are now standing procedure** (owner instruction, 2026-08-26: *"apply this skills always when the task is ui-ux related."*). [CLAUDE.md](CLAUDE.md) gains "UI and UX work — apply the design skills, always": any task touching `frontend/`, a screen, styling, layout, typography, colour, accessibility or a chart — **including a one-line CSS change** — invokes `ui-ux-pro-max` (with `ui-styling`, `design-system`, `design`), `frontend-design` and, for any chart, `dataviz`, **before** markup or styles are written. Placed in `CLAUDE.md` for the same reason the session-resume protocol was: it is the only file auto-loaded into every session, so the rule holds from any terminal without configuration. The section fixes precedence explicitly — rules 1–23 first (rule 18: the UI implements no legal evaluation logic and its permission gating is presentation only), then [DESIGN.md](DESIGN.md) and the DD-1–DD-5 decisions, with a skill/DD conflict **reported** under rule 5 rather than silently resolved — and names three prohibitions a generic design skill cannot know: no probability, confidence score or "the AI thinks" hedging (rule 12), no urgency theater, and a confidential field stays **omitted** rather than nulled or greyed (`SEC-07`, `LEGAL-02`). The plugin's `brand`, `banner-design` and `slides` skills are marked out of scope for product screens — LegalMind has no marketing surface. Documentation only: no application code, schema, dependency or test changed, and nothing in `all_lock.md` or [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) is touched, presentation-layer work locking nothing (DESIGN.md's own preamble).

* **The Tier-2 quality gate is now a runnable release check, and the reference deployment
  is network-segmented — Gate §5b A9 (measurable half) and A10 continued** (standing owner
  directive: gate stays CLOSED, continue safe work). Backend **894 tests** (1 skipped),
  ruff/mypy clean; `AM31_GATE` verified CLOSED and untouched.

  **`AM-28`'s gate, as a command** — `tools/verify_assist_quality.py` runs all 77 ratified
  questions through the **production** `search_hybrid` (real SQL, real fusion, real gate —
  not the calibration harness's in-memory mirror) and blocks exactly on what the locked
  sentence names: a worsened wrongly-answered rate against `tests/assist_eval/baseline.json`.
  The baseline was recorded from live measurement (12/13 unanswerable refused, 41/64
  retained), the gate was **proven able to fail** (tightened baseline → exit 1, restored →
  exit 0), and CI never sees it — the documents and model stay out of the repository
  (54.6), so it is a release-pipeline act like 55.5's reproducibility gate, and the
  preflight register now names it (`tier2_quality_gate`, 22 checks — the documented "18"
  was stale). Faithfulness and citation precision are recorded `not_yet_measurable`:
  they need generated answers, and `AM-31` m4 forbids a synthetic substitute.

  **One measured finding worth reading**: end-to-end recall@10 is **0.438**, far below the
  ungated ranking quality (0.938) — and the decomposition shows why, verified per-question:
  of 13 gate-open misses, 12 are the right chunk found by vector in the top ten **but below
  the 0.50 evidence floor**, which the shipped rule deliberately never presents as evidence.
  The strict-refusal trade-off now has a number, a recorded bar, and a safe path to revisit
  it: change, re-measure, compare.

  **Network segmentation in `docker-compose.yml`** — two networks: `data` (`internal: true` —
  Docker attaches no gateway) holds db, queue, both workers and the api; `edge` holds
  frontend and api. Everything that touches a document (parsing, OCR, chunking, embedding)
  now has **no route out at all** (`AM-30` t1 as a routing table), the frontend's
  never-touches-the-database rule (38.22) becomes a network fact, and model weights arrive
  by read-only mount because the data network cannot download anything (`AM-26` r5 was
  already the rule; the mount makes the compose reference actually work rather than
  silently degrade to lexical-only). Honestly scoped: compose removes routes but cannot
  enumerate destinations, so t8's full allow-list remains production infrastructure. The
  stale "0.8.0 is not a substitute" comment on the db service was aligned with the
  measured 0.6.0 correction. Decisions #145–#152 in
  [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md).

* **Security hardening started — Gate §5b unit A10, CI job 14** (owner directive: keep the
  `AM-31` gate CLOSED pending Google's written terms; continue safe remaining work that does
  not depend on it). Adds dependency and container image scanning to CI, the two of A10's
  five named controls (network segmentation, TLS, secrets, Trivy/pip-audit/npm audit,
  OpenVAS/ZAP) that a CI runner can check directly — the first three are already reported by
  `legalmind.deploy.preflight` as deployment-time properties, not repository state.

  **pip-audit and npm audit block on any finding**, matching job 1's own precedent of a
  measured-zero baseline rather than an invented tolerance: both were run before the job was
  written and found nothing (backend, editable install of `pyproject.toml`; frontend, 161
  packages across prod/dev/optional). **Trivy scans both built images**, the first time either
  Dockerfile has been build-tested in CI at all; it blocks on CRITICAL/HIGH with
  `ignore-unfixed: true` and reports MEDIUM/LOW without blocking, because an image scan also
  covers the base OS this repository doesn't pin package-by-package, and a gate nobody can
  satisfy converges to being disabled rather than the finding being fixed.

  **OpenVAS and ZAP are deliberately not in CI.** Both scan a running instance; standing one up
  inside this workflow means orchestrating Postgres, Redis, the API and the frontend as CI
  services — a materially larger change than an additive scan step. Left for the deployment
  pipeline, alongside the TLS and backup-restore controls `preflight` already reports as
  ATTEST for the identical reason. Four decisions logged as #141–#144 in
  [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md).

  Project-state documentation resynchronized in the same change: `LEGALMIND_PROJECT_STATE.md`
  had drifted — its top summary reflected A0–A7 complete, but the detailed Current
  Phase/Blockers/Decisions-needed sections below it still described the pre-A3 state,
  including two decisions (test questions, `onnxruntime`/`tokenizers` approval) already
  resolved days earlier. Both are now consistent with `IMPLEMENTATION_STATUS.md`, which also
  had two stale CI job counts (12/twelve, actually 13 before this change, now 14) corrected.

* **Smarter search delivered end to end — Gate §5b units A3–A7** (owner directive: complete the RAG implementation, deciding routine engineering autonomously). Backend **893 tests** (1 skipped), frontend **62 Vitest + typecheck + production build**, ruff and mypy clean. Live-demonstrated on the real MSA: 236 chunks embedded, the gate opening and closing exactly as calibrated, and a credential-less ask returning the identical refusal wording.

  **Model selected by measurement, and by the locked rule's own tie-break.** The owner ratified the 77-question set by directing its use; four provisioned candidates were scored against it over 15 real documents. On human-phrased questions lexical search collapses (1/64 top-10 — it ANDs every term) while refusing perfectly (13/13); dense retrieval inverts both. **`all-MiniLM-L6-v2` (23M, 384d) won as the smallest candidate passing the bar** (hit@10 0.938) — gte-small retrieves marginally better (0.969) but `AM-26` r2 forbids adopting a larger model for headroom. arctic-embed-s was rejected outright (0.438); e5-small-v2 publishes ONNX at a non-standard path and is recorded unmeasured.

  **The refusal cut-off was derived, not chosen — and a single cut-off measurably wasn't enough.** The best global cosine floor reached Youden's J ≈ 0.50 on every candidate; the shipped rule adds a peak-gap feature (top cosine minus the mean of the rest — a flat profile is a nearest neighbour, not evidence): `lexical hit OR (top ≥ 0.50 AND gap ≥ 0.059)`, giving **12/13 unanswerable refused at 64% answerable retention (J = 0.564)**, with the full sweep curve reproducible via `tools/benchmark_retrieval.py --eval`. The measured limit is stated where it belongs: adversarial near-misses score *inside* the answerable distribution for every model, so the gate is tuned for retention and **claim-level verification carries precision** — `AM-29` r3's layered-refusal design used as designed.

  **Guardrails before generation** (`AM-28` r2, and `IMPL-02` r4's locked ordering): `guardrails.py` verifies every sentence's citation markers for existence and lexical grounding, honours the model's own NOT FOUND as `EVIDENCE_INSUFFICIENT`, and keeps the model uncalled on insufficient evidence; it imports no prompt or model code, asserted by test. A fabricated claim with a real citation — the case no similarity gate can catch — fails grounding and the user sees the refusal, never the fabrication (`AM-25` r5).

  **Gemini behind one interface, gate CLOSED.** `generation.py` uses **stdlib urllib — no provider SDK, so rule 19's separate dependency approval is never triggered** — and is the only module in `EGRESS_ALLOWED`, asserted by the boundary test that refused its first draft (a `provision()` helper importing urllib was evicted to `tools/`). The `AM-31` gate is a code constant an environment variable **cannot** open (g3): while CLOSED, production egress is refused outright, and dev/staging (synthetic-only, locked 55.3) call the provider only when `LEGALMIND_GEMINI_API_KEY` is set. Payload screening re-erects LEGAL-02 as an egress rule (t3); a floating model alias is refused (t7); **every call writes an `audit_events` row with model, prompt version and payload hash** (t5 — a first draft only logged it, and 53.1 says a log is never a substitute).

  **Conversation API + workspace.** Three endpoints behind the new `assist.ask` permission (the extension AB-3's registry entry pre-authorized), Guard-chained with byte-identical 404s on conversations — a conversation reveals what someone asked about, so distinguishability would be an oracle (r7). Compliance-shaped questions route to the deterministic evaluator with a pointer, never a generated answer (`AM-25` r4). The contract page gains an Ask panel: citations with §/page, refusals rendered on the quiet surface as the system *working*, and every score labelled a **retrieval score** — no confidence figure anywhere (`AI-03` item 16), asserted in tests on both sides of the API.

  **Schema:** migration `c4a91f6e2d87` creates `chunk_embeddings` — the ninth `AM-27` table, its 384 dimension a **DDL literal** so a model change is a reviewed migration, never a silent config drift (the A1 tripwire test that guarded this fired and was replaced by shape tests, exactly as designed). The pgvector *type and operator* are schema-qualified from live lookups — third instance of the `F-4` search-path lesson. Fifteen decisions logged as #126–#140 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md); full selection evidence in [BACKEND_ARCHITECTURE.md](docs/05-architecture/BACKEND_ARCHITECTURE.md).

* **Tier-2 evaluation dataset drafted — `backend/tests/assist_eval/`** (2026-08-26, owner-directed; dataset only, no code, no benchmark run, no threshold computed). 77 questions authored against a **full read of the actual supplied documents** — ten contracts/policies and the seven statutes — split 64 `ANSWERABLE` (44 contract, 20 statute) / 13 `NOT_FOUND`, each answerable question carrying its verified source clause and each unanswerable one a **verified absence plus the misleading nearby clause** a naive nearest-neighbour system would wrongly return. Three refusal probes exploit real cross-document confusions the owner asked the search to distinguish: the MSA has **no** price-increase notice while the ToS gives 30 days; the DPDP Act fixes **no** breach-notification deadline (that lives in the rules) while CERT-In's 6 hours sits nearby in the corpus; and the DPDP Act grants individuals **no compensation** — its own amendment schedule omits the IT Act section that did. Reading first paid: `Companies_Act_2013_sp.pdf` turned out to be a **4-page extract** (§21–24, §178–181), so its questions were confined to what it actually contains. 47 load-bearing claims (every number, period and penalty cited) were re-verified mechanically against source text — 47/47. **Labelled DRAFT pending owner ratification**, reconciling the authorship instruction with `AM-31` m5's supplied-never-manufactured rule: no calibration result counts until the owner reviews the set, which is their own pipeline's HUMAN REVIEW stage. Lives outside `tests/corpus/` so the golden-corpus guard and loader never see it (`AM-28` r3); contains no document text beyond short cited excerpts (54.6) and **no counterparty or signatory name**, enforced by an automated check. Decisions #121–#125 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md).

* **Session-resume protocol** (owner instruction, 2026-08-25: *"every day when I type hi you will give me the latest previous work we do."*). Placed in [CLAUDE.md](CLAUDE.md) under "🔔 Start of a session", because that is the only file auto-loaded into every session — so it works from any terminal on any day without configuration. On a bare greeting: read [LEGALMIND_PROJECT_STATE.md](docs/00-project/LEGALMIND_PROJECT_STATE.md), the top of this changelog's `[Unreleased]`, and [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)'s build state, then report current phase · what finished last session · real blockers · what is needed from the owner — in plain language, before asking anything. Two standing rules attached to it: **verify a figure rather than quoting it** (this is exactly how "653 tests" and "No Legal Rule exists" survived), and **do not re-ask for anything already supplied or decided** (rule 23). `LEGALMIND_PROJECT_STATE.md` gains a "Picking up where we left off" block so the answer is immediate, and [HANDOFF.md](HANDOFF.md) gains a banner marking it a point-in-time 2026-08-18 review pack rather than the live status page — it was `CLAUDE.md`'s named entry point and its figures have moved. No new document: the state page and this changelog already carry the two halves of the answer.

* **Embedding runtime and candidate measurement — Gate §5b unit A3 continued.** **862 tests pass** (1 skipped), ruff and mypy clean. Owner approved `onnxruntime` + `tokenizers` under rule 19; both declared in `pyproject.toml`. **Measured at 118 MB installed, correcting the "~50 MB" I gave when asking** — the estimate omitted numpy. The recommendation stands (`torch` is ~2.5 GB and carries a training stack `AM-26` excludes), but a provisioning figure quoted to an owner should be right.

  **Four 384-dimension candidates measured smallest-first per `AM-26` r2** (`all-MiniLM-L6-v2`, `bge-small-en-v1.5`, `gte-small`, `snowflake-arctic-embed-s`; `e5-small-v2` publishes ONNX at a non-standard path and was skipped rather than special-cased). Hybrid RRF reaches **R@10 1.000** against lexical's 0.917, and `arctic-embed-s` matches the lexical baseline's P@1 (0.833) while improving MRR (0.891 vs 0.875) — a strict improvement on that family.

  **The finding that matters is not about model choice: dense retrieval never refuses.** Every vector strategy and every hybrid scored **0 of 36 correct refusals**, against lexical's 34. Nearest-neighbour search returns its nearest neighbour however far away it is — a ranking is not a filter, and RRF inherits the property. `AM-29` r3 requires `NO_EVIDENCE_RETRIEVED` and `EVIDENCE_INSUFFICIENT` to be reachable, and `AM-25` r5 requires enforcement *mechanically and outside the model*, so **a similarity floor is a structural precondition for shipping dense or hybrid retrieval at all** — and by rule 7 it must be measured against known-unanswerable questions, not picked. The same owner-supplied material now unblocks two decisions rather than one.

  **No model is selected, no dimension is pinned, and `chunk_embeddings` still does not exist.** The families an embedding model exists to win remain unmeasured, so selecting now would be choosing on evidence that does not bear on the question. All four measured candidates happen to be 384-dimension and that convenience is explicitly **not** treated as a reason to pin 384 — the 768 group is unmeasured.

  **Three runtime properties, each learned by measurement rather than reasoning.** The onnxruntime **execution provider is pinned to CPU** and asserted by a test: onnxruntime ships an `AzureExecutionProvider` that could give an inference session a second network egress, and `AM-30` t1 permits exactly one. **Weight fetching was moved out of `legalmind/` into `tools/provision_model.py`** — the first draft put a `provision()` helper beside its consumer and `test_import_boundaries.py` refused it for importing `urllib`; the right fix was removing the capability rather than adding an `EGRESS_ALLOWED` entry, so no module under `legalmind/` imports a network client and the allow-list is **still empty**. And **embedding is batched at 16** because embedding a whole document in one call reached **14 GB RSS and was OOM-killed** (padding takes every sequence to the longest in the batch); a test asserts batching changes no vector, since the bound must not alter a result.

  Nine decisions logged as #112–#120 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md); full results in [BACKEND_ARCHITECTURE.md](docs/05-architecture/BACKEND_ARCHITECTURE.md) § Embedding-model selection.

* **Retrieval measurement and clause-aware chunking — Gate §5b unit A3** (authorized by `IMPL-02` r1). **848 tests pass** (1 skipped), ruff and mypy clean. **No embedding model is selected and no vector dimension is pinned**: `AM-26` r2 settles that by measurement, and the measurement is deliberately incomplete rather than approximated. `chunk_embeddings` still does not exist, and `EGRESS_ALLOWED` is still empty.

  **A measured ingestion finding, fixed before anything was benchmarked.** PyMuPDF emits **no blank lines** for the real supplied PDFs — 59 single newlines and zero double on a representative page — so `parsing.segment_paragraphs`, which splits on `\n\s*\n`, produced **one page-sized evidence row per page**. Across six real documents that meant 99 page-fragment chunks and **2 of 59 rows carrying a section number**, so nothing could cite "§17.2". The structure was never missing: `1.13.`, `4.1.`, `4. SCOPE OF SERVICES` sit on their own lines, and my `_SUBCLAUSE` pattern simply failed on the trailing period. Splitting on those markers **whenever they appear, regardless of length**, took the same six documents to **341 clause-sized chunks with a section on 300 of them (88%)** — MSA.pdf from 41 to 236 at 100% coverage. Measuring embedding models on page-sized, section-less chunks would have produced meaningless numbers. The section reference is **derived at query time, never stored**, so `AM-27` r4's bar on independent provenance is untouched.

  **`tools/benchmark_retrieval.py`** scores any strategy satisfying the new `RetrievalStrategy` contract, over probes derived **mechanically from the real supplied documents — none authored**. The distinction that licenses that: a *retrieval* label ("the text about X is in §17.2") is a locatable fact asserting no legal position, whereas an *answer* label ("our cap is 12 months") is a legal position and `AM-31` m5 requires it supplied. Three families are derivable; no document text enters the repository (54.6), and absence of the source directory is a SKIP, not a pass.

  **Measured lexical baseline**, 180 probes over six real documents: `section_number` P@1 **0.972** / R@10 **1.000** / MRR 0.986; `exact_terminology` P@1 **0.833** / R@10 **0.931** / MRR 0.870; `unanswerable` **64 of 72 correctly refused**. That last figure was **26 wrongly-answered** on the first run, and the first number was discarded rather than reported: `websearch_to_tsquery` ANDs stemmed terms, so a chunk containing all four words scattered matches and may be topically fair — the probe was measuring its own design. Requiring one genuinely out-of-vocabulary word gave 8, and the residual is consistent with stemming equivalence, so 89% is a **floor**.

  **Why the selection cannot be completed yet, stated rather than worked around.** Lexical retrieval is already strong on exactly the two categories a citation depends on, so an embedding model has to prove itself on **semantic similarity** and **legal phrasing** — questions worded differently from the document. Those cannot be derived from a document, and are reported as NOT MEASURED. Measuring candidates only on the derivable families would score them where lexical is strongest and embeddings weakest, selecting a model on evidence that does not bear on the question. Eight candidates are recorded with **fetched, not recalled** metadata (licence, dimension, params, ONNX availability), to be evaluated smallest-first per `AM-26` r2.

  **pgvector requirement corrected from BLOCKED to ATTEST, on measurement.** Verified on 0.6.0: exact cosine KNN with the authorization `WHERE` clause in the same statement works and genuinely excludes out-of-scope rows. Exact search loses no recall, so **`AM-25` r6 is fully satisfiable on 0.6.0** — it is O(n) over the pre-filtered set, which for one document's chunks is the right trade. `≥ 0.8.0` buys *iterative index scans*, which matter only for an approximate index under a selective pre-filter. My earlier framing overstated this. The answer to an older build remains exact search, **never** a post-filter (`AM-25` r7).

  **Two owner inputs now genuinely required**, both blocking the same decision and both stated in plain language in [LEGALMIND_PROJECT_STATE.md](docs/00-project/LEGALMIND_PROJECT_STATE.md): real evaluation questions for the two undecidable families, and rule-19 approval for a local inference runtime (`onnxruntime` + `tokenizers` recommended over `torch` — ~50MB versus ~2.5GB, CPU-only, and inference-only, which makes `AM-26`'s no-fine-tuning position structural). Eleven decisions logged as #101–#111 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md). Full record in [BACKEND_ARCHITECTURE.md](docs/05-architecture/BACKEND_ARCHITECTURE.md) § Embedding-model selection.

* **Chunking and lexical search — Gate §5b unit A2**, the first `legalmind/assist/` code (authorized by `IMPL-02` r1). **841 tests pass** (1 skipped), ruff and mypy clean, `tools.verify_reproducibility` passes with the legal digest unchanged, and `test_locked_schema_columns.py` still passes **unmodified**. **Demonstrated end to end against a synthetic MSA with no model of any kind**: `"aggregate liability"` finds the clause, `"17.2"` finds §17.2, `"ninety days notice"` finds *"ninety days prior written notice"* through stemming, a quoted phrase matches exactly, and `"arbitration in Singapore"` — absent from the document — returns an honest empty result rather than a guess. `EGRESS_ALLOWED` remains empty; no model is reachable.

  **The boundary test worked as designed before any of it landed.** Creating `legalmind/assist/` made `test_import_boundaries.py` fail immediately — the allow-list refuses an undeclared package by default — so the lane's dependencies had to be stated explicitly rather than accreting. The declared set is `{db, domain, observability}`, and it imports **none** of `evaluation`, `mapping`, `extraction`, `analysis` or `workflow`: that exclusion is the mechanical form of `AM-25` r1, since an import edge into the evaluator is precisely how an assist module would quietly acquire the ability to produce a Finding. `security` is deliberately absent until A3 needs it.

  **Chunking transforms committed evidence; it never re-reads the document** (`AM-27` r4). The parser has already segmented paragraphs, preserved the numbering the document itself states (34.12), kept pages and offsets, and flagged OCR text — re-deriving that from raw bytes would do it worse *and* create the second source of truth r4 forbids. Chunks carry **no provenance of their own**: page, section and source type are joined from the evidence row on every query, so a citation cannot display a stale copy.

  **A real defect the tests caught.** The sentence-split regex consumed the whitespace it split on, so pieces concatenated to `"law.Each"` instead of `"law. Each"` — which breaks phrase search and reads as a typo inside a citation. Both split patterns are now zero-width, making reassembly exactly lossless, verified across three text shapes. Relatedly, only the first piece of a split row claims the evidence offset: the parser's offsets index the *extracted* text, so a computed offset for a later piece would look right and be subtly wrong, and a wrong offset corrupts a citation — `None` is the honest value.

  **Search is `tsvector` + trigram ordered by `ts_rank`, and it is not BM25** (which needs an unauthorized extension). Two signals rather than one because they fail differently on legal text — stemming matches paraphrase but mangles `17.2`; trigram matches literally but has no notion of meaning — and deliberately **not fused into a weighted score**, because a weight would be an invented number and rank fusion belongs in A4 where it can be measured. `search_chunks` takes **one authorized `document_version_id` applied as a `WHERE` clause**: `AM-25` r6's authorization-inside-the-query, shaped so a caller cannot forget to scope it, because post-filtering would let result count or ranking reveal a chunk in a document the requester may not read — r7's enumeration oracle.

  **Two operational properties, both structural rather than intended.** A failed index **cannot fail an ingestion** (`index_safely`, and the dispatcher swallows): evidence is authoritative and a chunk is rebuildable, so letting a derived index reject a successfully-parsed upload would be the inversion `AM-25` r1 and Step 38 rule 21 forbid. And indexing gets its **own `assist` queue and worker process**, separate from `analysis`, so an index backlog can never delay a Review's analysis — still one image with a different command, so `AM-26`'s modular monolith is unchanged.

  **Re-indexing is refused by default rather than performed idempotently.** Delete-and-reinsert cascades to `answer_citations`, so a silent re-index would invalidate citations already recorded against removed chunks — an answer whose sources have quietly vanished. Nothing cites a chunk yet, which is exactly why this was the cheap moment to decide it. Thirteen decisions logged as #88–#100 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md), including why Core tables are built per call instead of declarative ORM models (a model fixes its schema at import time, before `conftest` has chosen the per-run one) and why pg_trgm's functions are schema-qualified from a live lookup instead of widening `search_path`.

* **Assist-lane schema — Gate §5b unit A1** (migration `b1e7c4d20f39`, authorized by `IMPL-02` r1). Creates **eight of `AM-27`'s nine tables** in a schema separate from the locked ones (r1), with `pg_trgm` and a **generated** `tsvector` column on `chunks`. **817 tests pass** (1 skipped), ruff and mypy clean, the migration round-trips, and `tools.verify_reproducibility` passes with the legal digest **unchanged across the new migration** — which is `AM-28` r1's property, that no assist work is admitted to the determinism guarantee and no determinism assertion is relaxed for one. Critically, `test_locked_schema_columns.py` **passed unmodified**, which is exactly what `AM-27` r2 names as its evidence that the locked model is intact.

  **`chunk_embeddings` is deliberately not created.** Its embedding column needs a fixed dimension; the dimension is a property of the embedding model; and `AM-26` r2 selects that model *by measurement, smallest-that-passes* — so none is selected and no dimension is known. Writing `vector(768)` today would put a number nobody chose into the schema, which is rule 7's habit applied to DDL. `test_chunk_embeddings_is_deliberately_absent` fails when it arrives, so its arrival has to be deliberate.

  **Two verified facts reshaped the design.** `vector` is **not** a trusted PostgreSQL extension, so `CREATE EXTENSION vector` needs superuser — and `CREATE ROLE` needs `CREATEROLE`, which the application role also lacks. Both are privileges the application must never hold, so pgvector and the `legalmind_assist` role are **deployment preconditions reported by `preflight`**, never migration steps. `pg_trgm`, by contrast, *is* trusted, so the migration creates it — pinned to `public`, with its operator class schema-qualified from a live lookup rather than widening `search_path`, because a wider path would give every unqualified lookup in a test run a fallback into a shared schema and that is the isolation `F-4` exists to provide.

  **pgvector is pinned ≥ 0.8.0 and Ubuntu's 0.6.0 recorded as insufficient.** `AM-25` r6 requires authorization applied *inside* the retrieval query; under a selective pre-filter an approximate index can starve, and pgvector's fix — **iterative index scans** — arrived in 0.8.0. On an older build the only options are poor recall or a post-filter, and a post-filter is the enumeration oracle r7 forbids. So the version is a correctness constraint. `docker-compose.yml` and all eight CI Postgres services moved to `pgvector/pgvector:pg16`.

  **Schema decisions, all logged as #73–#87 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md):** the assist schema name is **derived per test run** (`<run>_assist`), because a hardcoded `assist` would be shared by concurrent suites while the locked tables sit in private schemas — reintroducing the collision `F-4` fixed; `chunks` does **not** copy page, section or source-type from evidence (`AM-27` r4's "no independent provenance" — reached by one join over immutable data instead); `chunks.evidence_id` is NOT NULL and **singular**, because r4 says "the Document Evidence row it came from"; `retrieval_runs.results` is JSONB by necessity, since `AM-27` authorizes no child table for a variable-length result list, **with the cost stated in the migration** — those chunk ids carry no foreign key, tolerable only because the *verified* citations live in `answer_citations` with a real FK; `ai_answers.model_identity` is nullable because `AM-29` r3's `EVIDENCE_INSUFFICIENT` means the model was never called and a placeholder would fabricate an external call; and **no `confidence` column exists anywhere**, asserted by a test (`AI-03` item 16).

  **A finding while testing `AM-27` r5.** The cascade works, but the locked schema has **no delete path for a document version at all** — `document_processing_runs` and `reviews` both reference it without a cascade, so the delete is refused outright. r5's cascade is verified where it is defined (at the evidence row); r5's *premise* is currently unreachable. `test_the_locked_schema_has_no_delete_path_for_a_document_version` pins that, and fails if cascades are later added — which would change whether historical Reviews stay reproducible. The retention and deletion policy remains genuinely undecided.

  **Deferred with reasons:** MinIO to A10 (locked 55.6 makes the provider a deployment choice, the `StorageBackend` Protocol already isolates it, it is not on the retrieval path, and deferring avoids settling the `boto3` dependency question under rule 19 before anything needs it). `AM-31`'s real-contract egress gate remains **CLOSED**.

* **Amendment Batch AB-4 — the generative model is a hosted service** (owner decision 2026-08-25, appended to [`all_lock.md`](all_lock.md); the prior **16,048** lines verified byte-identical as a prefix, file now **16,385** lines). The owner selected **Gemini Flash** and reaffirmed it after the conflict was raised in writing, so the decision landed as an amendment rather than as code written against a contrary lock — `AM-25` r9 is a confidentiality guarantee ("no document text… leaves LeapSwitch-controlled infrastructure") and AB-3's Position block listed hosted model APIs out of V1 scope. Three records. **`AM-30`** widens `AM-25` r9 **for the generation call alone**, on ten minimum-egress terms: `embedding input` stays forbidden from egress because the embedding model is self-hosted (owner answer, same day); `LEGAL-02` becomes an **egress rule as well as a display rule** (r9's blanket ban had made that moot, so widening the destination would otherwise have silently widened `LEGAL-02`); no counterparty, signatory or contract identifier in a payload; a payload **hash, never the payload**, in `audit_events`; a trains-by-default provider tier is **ineligible whatever its cost**; a dated pinned model id, since a floating alias is not a pin; a one-endpoint network allow-list asserted by a test. It also **scopes rather than deletes** `AM-26`'s `Inference runtime — no outbound network route` row, which still governs the local embedding and reranking models — leaving that unamended would have made the batch internally contradictory. **`AM-31`** makes the real-contract egress gate a **locked property, default-closed and released only by a further appended record** citing written provider terms (a feature flag would let the confidentiality posture change with no owner signature; `AM-25` r2 sets the precedent that such a boundary is enforced by mechanism, not convention) — **the gate is CLOSED**, no terms exist — and resolves a contradiction `AM-30` would otherwise have created, since `AM-26` r3 requires the quality bar measured on **real** supplied documents while the gate forbids real text egressing: a provisional selection may use an explicitly-labelled **synthetic** set, but that is not a passed bar and **no answer reaches a user over real counterparty material on a synthetic-only bar**. **`IMPL-02`** authorizes the assist-lane build sequence **by reference** to a new [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5b, mirroring how `IMPL-01` authorized §5, and locks two orderings by consequence: citation enforcement **before** generation (`AM-28` r2 forbids the guardrail importing prompt or model code — built after, it must) and the egress allow-list **before** the first real generation call. `AM-25` r1–r8, `AM-27`, `AM-28`, `AM-29`, the modular monolith (**so no gateway service**), locked 54.6, locked 55.3 and **rule 19** are all explicitly unamended.

* **AB-3 finally landed across the five specifications its own registry entries cite** (documentation only). AB-3 was locked 2026-08-24 but `SYSTEM_ARCHITECTURE.md`, `BACKEND_ARCHITECTURE.md`, `DATABASE_MIGRATIONS.md`, `STEP_54_TESTING_STRATEGY.md` and `DECISION_STATE_MODEL.md` contained **zero** mentions of it or of `AM-25`–`AM-29`, while [CONTRIBUTING.md](CONTRIBUTING.md) requires an amendment to land as one synchronized operation. Each now carries a labelled section rather than a rewrite (rule 22): the assist lane as a 38.28 *consumer* and not an eleventh domain; the stack additions, with `ts_rank` flagged as **not BM25**; `AM-27`'s nine tables, separate schema, and the two hazards recorded before the first migration (the test harness builds one schema per run, and `AM-29` r2 is unenforced across schemas); `AM-28`'s Tier 2 with its build-order consequence; and **the sixth axis** — `DECISION_STATE_MODEL.md` was still titled and LOCKED as "The Five Axes" with no mention of `AM-29`, and now documents the three assist-lane outcomes, the nine value names r2 forbids, and that this axis is the sanctioned answer to the product vision's "confidence" (`AI-03` item 16 forbids the percentage).

* **Two boundary guards, before any assist-lane code exists** — both independently proven to fail on a simulated violation before being accepted. `backend/tests/test_import_boundaries.py` (22 tests) parses the import graph with `ast` rather than matching substrings: it asserts **no outbound network client anywhere** in `legalmind/` (verified true — zero network-family imports) with an `EGRESS_ALLOWED` map that is empty and must be added to **by name** when `AM-30`'s adapter lands, and it fences the deterministic core with an **allow-list**, so importing a future `legalmind.assist` fails on the first run with no rule added. `backend/tests/test_locked_schema_columns.py` (33 tests) snapshots all **29** locked tables and **195** columns against the **live database** — `AM-27` r2 names the existing invariant tests as its evidence that no locked table changed, but none of the 21 was sensitive to a column, so the evidence sentence was true and proved nothing. The existing substring check in `test_observability.py` is deliberately kept: it catches docstrings and comments an import graph cannot.

* **A full-suite CI gate** (`ci.yml` job 13, blocking), plus an assertion that no model-provider credential is present in CI (`AM-30` t1/t8). All 12 prior jobs block, but none ran the whole suite: job 5's probe is `if [ $fails -gt 0 ] && [ $fails -lt 3 ]`, which is **correct** for the `F-4` flake detector it is — three failures of three is not flaky — so it exits 0 and roughly **250 tests across ~12 files** had their results discarded. Job 5 is left exactly as written; the fix is additive. `AM-28` r2's own logic applies: a guardrail no job gates is not a guardrail.

* **Two governance documents, and deliberately not a third.** [docs/00-project/CLAUDE_WORKING_RULES.md](docs/00-project/CLAUDE_WORKING_RULES.md) (`ACTIVE`) is the operational index — source hierarchy, the assist-lane pointers, the `SOURCE REQUIRED`/`DECISION REQUIRED` markers, when to decide versus ask — and **restates no locked rule**, per the owner's instruction that a paraphrase drifts. [docs/00-project/LEGALMIND_PROJECT_STATE.md](docs/00-project/LEGALMIND_PROJECT_STATE.md) (`DERIVED`) is plain-language status for the owner, with no framework jargon, and derives build state rather than asserting it. No `CURRENT_ARCHITECTURE_AND_PHASE_PLAN.md` was created: `ARCHITECTURE_REFERENCE.md` already maps the architecture, the audit's §15 already holds the phase rationale, and the *authorized* sequence belongs in the Gate under `IMPL-02` because a working document may never become an authorized sequence. Both are indexed in [docs/README.md](docs/README.md) and reachable from the auto-loaded [CLAUDE.md](CLAUDE.md), which is the only mechanically reliable hop.

* **Stale records corrected, only where measured** (2026-08-25). [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md): 653 → **781** tests; 53 → **58** Vitest; **"No Legal Rule exists" refuted** — the zero-tolerance rule is present in **32 of 32** standards files, read by both evaluators and enforced by `tools/import_ratified_standards.py`, and the cell now says so and says it was corrected; a new unit 12 row records the assist lane as `SPECIFIED · NOT STARTED`. [CLAUDE.md](CLAUDE.md): line counts, "15 Requirements" → 32 ratified standards, "Six remain open" → nine, and rule 10 updated for `AM-30`. [AGENTS.md](AGENTS.md): the paragraph telling agents the project was "in the specification phase" and not to write application code — actively misleading since `IMPL-01`. `DATABASE_MIGRATIONS.md`'s "no migrations have been implemented" header, with four in existence. **The table count was deliberately not "corrected"**: `AM-27` r2 says 30, the ORM and migrations say 29, and since `all_lock.md` wins and is append-only the discrepancy is registered as **C-14** and derived documents now write "29 (+ `alembic_version` — the 30 counted by `AM-27` r2)".

* **Three conflicts registered, and one recommendation reversed.** **C-14** (the table count above). **C-15** — the owner's instruction that Domains A/B/C share a retrieval abstraction *without* being flattened into one data model rules out the shape this repository's own audit had recommended for Domain A/C tables, since `AM-27` authorizes nine tables and "no other table" and its r4 defines a chunk as derived from a Document Version; **only Domain B is buildable today**, and per rule 5 the reversal is registered rather than applied silently. **C-16** — the product vision's headline example is "what does Section 138 of the NI Act say", but the **NI Act and Evidence Act were never supplied**, and the seven statutes on disk did not come from India Code, which vision §9.2 makes a hard rule. Also fixed: `CONFLICTS.md`'s own intro omitted `C-13`. The audit's contradiction series was renamed `C1`–`C16` → **`RA-1`–`RA-16`** to end a namespace collision with the register — the second instance of the overloaded-`F-*` problem `CLAUDE.md` documents. Fifteen autonomous technical decisions are logged as #58–#72 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md), including two that **reverse the audit**: the corpus-parity harness is premature (`run_fixture` is a pure in-memory call with no database, and `tools/verify_reproducibility.py` already double-runs the full pipeline, so a parity test today asserts a tautology), and no `legalmind/assist/` skeleton was created because `CONTRIBUTING.md` forbids scaffolding "to get started".

* **Existing-backend reuse audit against the current product vision** (2026-08-25, audit only — no application code, schema, dependency or test changed): [docs/architecture/EXISTING_BACKEND_REUSE_AUDIT.md](docs/architecture/EXISTING_BACKEND_REUSE_AUDIT.md) classifies every significant backend component against [legalmind-product-vision.md](legalmind-product-vision.md) and [legal-mind-tech-stack-and-buildplan-v2.md](legal-mind-tech-stack-and-buildplan-v2.md). Baseline measured on the day: **726 tests passing**, `ruff`/`mypy` at zero. Finds the backend **substantially reusable** — ~66% of ~24,900 LOC reusable as-is, ~33% with additive modification, **~0% requiring replacement and ~0% obsolete**; the assist lane is ~6–9k LOC of *new* code, not rewrite. Records an 18-item "do not rebuild" list, and confirms **vision §3b is already satisfied**: the 32 ratified Company Standards in `backend/config/company_standards/` are Domain A, derived from real supplied documents and stored as versioned configuration — no category-discovery pass is pending. Registers **16 architectural contradictions**, four of them blocking and none resolved here (rules 5–6): both target documents make **hosted Gemini Flash** the core dependency, which `AM-25` r9 and `AM-26` — locked 2026-08-24, one day earlier — forbid outright in favour of a local self-hosted open-weight model; the target's `validate_clause → verdict` LLM call would replace the deterministic evaluator, barred by `AM-25` r1/r4 and by the Tier-1 determinism gate; **Domain A and Domain C have no table authorized by `AM-27`**, whose `chunks` is defined as derived from a Document Version; and the vision's user-facing "confidence" collides with `AI-03` locked item 16, with the `AM-29` answer state proposed as the substitute. Also flags two self-contradictions inside the tech-stack document (which component holds the sole egress; whether a GPU is required), the stale "8 clause categories / 22-conflict register" seed, the unspecified RIAAS contract, and that `AM-27` r5's chunk hard-delete is not satisfiable because no hard-delete path for a Contract exists. Provides an 11-phase dependency-ordered migration plan that moves isolation scaffolding to the front and guardrails **before** generation, and carves out a model-free shippable increment. **Reported for separate correction, not edited:** [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)'s Build-state table still reads "653 tests" and "No Legal Rule exists", both stale. Decides nothing, amends nothing, authorizes no build.

* **AI/RAG R&D document re-bannered, body preserved** (2026-08-25): [docs/architecture/AI_RAG_ARCHITECTURE_RND.md](docs/architecture/AI_RAG_ARCHITECTURE_RND.md) predates AB-3 by hours and framed the assist lane as post-V1. A supersession banner now records that AB-3 put the lane in V1 scope, closed its central open question (contract text may **not** reach a third-party model API), and superseded its §9 proposed schema with `AM-27`'s nine authorized tables — while re-affirming that every §2 codebase finding and the §5–§8/§13/§14/§24 design guidance still hold. No section rewritten or deleted; `docs/README.md`'s `architecture/` section retitled and re-indexed for two documents.

* **Post-V1 AI/RAG architecture R&D document** (2026-08-24, requested as a Principal-Solutions-Architect exercise, research only — no code, schema, dependency, or test changed): [docs/architecture/AI_RAG_ARCHITECTURE_RND.md](docs/architecture/AI_RAG_ARCHITECTURE_RND.md) audits whether the architecture can accept an assist-only LLM/RAG layer post-V1 without redesign, per `AI-02`. Finds it substantially holds, with three concrete gaps: ingestion has no async seam today (parsing runs synchronously in the request thread — the only Celery task is `analyse_review`), `AI-03`'s registry gloss implies a working spaCy assist-only precedent that does not exist anywhere in the codebase, and there is no existing outbound-HTTP infrastructure at all (a future LLM call would be the first external egress this codebase has ever made). Reproduces `AI-01`–`AI-04`'s verbatim locked text rather than the registry's paraphrase, flagging that the registry silently drops locked item 16 ("no generic AI confidence scores") — the rule most directly implicated by any AI-suggestion feature. Also notes the brief's questions assume a workspace/tenant primitive that does not exist in V1 (ownership is per-`owner_id` only). Recommends Option B (AI-assisted layer, self-hosted embeddings first, generation gated behind an explicit data-egress decision, pgvector over a separate vector service) with isolation proven by DB-level grants and a golden-corpus parity regression test, not code-review trust alone. New `docs/architecture/` folder added (unnumbered, alongside `docs/design/`) since no `docs/architecture/` entry existed in the documentation tree. Decides nothing, reopens no locked decision, authorizes no build.

* **Eight-angle code review of PR #6, findings applied** (2026-08-22): fixed a `TableCard` clipping regression (cascade order), the queue view silently flipping across pagination, a just-decided Finding unmounting before its server-confirmed decision was seen (queue membership now sticky per visit, 52.7), and misleading filtered-empty copy on the core screen; completed the DRY pass (`StatePill`/`Field`/`formatDate` in the shared legal renderers, one e2e `signIn` helper); removed dead CSS and tokenized deep-surface literals; corrected two stale records (DD-1 status, DESIGN_SYSTEM's overstated "values unchanged" claim) and synced CLAUDE.md's `all_lock.md` line count (15,648). **Reported for owner decision, not changed:** nested-alias double-counting re-enabling single-mention CONFIRMED in ARBITRATION/GOVLAW/RETURN-DESTRUCTION mapping rules, the unrecorded KYC-RETENTION-TOS-001 recalibration, and the public-terms-derived aliases vs the CLAUDE.md test-only authorization.

* **Phase 3.6–3.9 — report, configuration, audit, admin** (batched; established patterns only): count tables gain real classification/status pills; audit gets the labeled filter card and `.table-card` with full timestamps preserved; admin gets user-status pills and the Grant-secondary/Disable-danger button tiers; configuration forms move onto `.field` primitives with monospaced JSON textareas (syntax legibility only — no legal-content assistance, rule 21). Logic/API untouched; typecheck, 58/58 Vitest, build, real-browser pass on all four. **The Phase 3 page roadmap is now delivered end to end**; report export remains deferred (49.12 NOT YET SPECIFIED).

* **Phase 3.5 — `/reviews/[id]`, the core screen** (DD-1 hybrid, DOM/selectors preserved): Needs decision / All findings segmented view over the server-provided `requires_decision` flag (queue default, full list one click away, automatic fallback when the queue is empty); attention edge on findings needing a decision; the Legal Decision block styled as the page's single authority act versus escalation's quiet request treatment; header back link + status pill + snapshot + View report; forms and buttons moved onto the shared primitives. Fixed a pre-existing state bug (perpetual "Loading findings…" beside a load error). All e2e selector names and locked 52.5 structural guarantees untouched. Verified: typecheck, 58/58 Vitest, build, real-browser passes including the out-of-scope 404 path.

* **Phase 3.3 + 3.4 — `/contracts/[id]` and `/reviews`** (batched on owner instruction "go with the roadmap"): contract detail gains a back link, serif title with type/status pill meta, finished upload and start-review cards, and the reviews `.table-card`; the reviews list gains a labeled filter card, lifecycle pills (only `ANALYSIS_FAILED` error-tinted and `CANCELLED` muted — no other lifecycle state colored, preserving the needs-decision channel), and distinct filtered-empty vs true-empty copy. Logic/API untouched. Verified: typecheck, 58/58 Vitest, build, and a real end-to-end browser pass against the live stack (login → create contract → upload fixture document → all states screenshotted).

* **Phase 3.2 — `/contracts` + app-shell identity** (DD-5 finish standard; theme resolved per owner "go with your recommendation"): content pages stay light for dense legal reading while the topbar adopts the deep-navy identity app-wide (serif wordmark, accent-vivid active underline); `/contracts` gains the `.table-card` treatment (header band, row hover, neutral status pills, date-only display), a finished `.form-row` create card on `.field` primitives, and the first light-surface `.btn--primary` (recolored to `--accent` for ~7:1 contrast). Page logic, API calls, and gating untouched; e2e has no DOM selectors on this page. Verified: typecheck, 58/58 Vitest, build, mocked-API browser screenshots at 1440/375 + empty state; a mobile topbar wrap defect was caught and fixed in review.

* **`/login` DD-4 addendum** (owner instruction): restored three mock elements — the "New here? Learn what LegalMind does" header link and "Not a customer yet? Request access" line (both placeholder `#`, no product pages exist), and a generic "Sign in with Google" control linking to the locked 49.2 route `GET /api/v1/auth/oidc/start`, so it activates automatically when the OIDC backend ships. Verified: typecheck, 58/58 Vitest, build, screenshots at 1440/375.

* **`/login` redesigned to the owner-supplied deep-navy composition** ([docs/design/DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md) DD-4, superseding DD-3's visuals). Floating document geometry + glow behind a centered glass card; dark inputs with a Show/Hide password reveal; vivid submit with inline spinner; error banner restyled dark (wording untouched, S-7). Mock controls naming non-existent capabilities (SSO button, forgot password, Google chip, request access) deliberately omitted; Google Fonts substituted with system faces (rule 19). Deep-surface tokens retinted to `oklch` navy; e2e `getByLabel("Password")` call sites gained `{ exact: true }` in lockstep with the new reveal control. Verified: typecheck, 58/58 Vitest, production build, browser passes (1440/820/375, error, loading, reduced-motion, keyboard, reveal toggle).

* **`/login` copy pass** (owner directive, DD-3 addendum): removed the SSO-fallback paragraph (mechanism not offered on the page), the redundant second sentence of the admin note, and the explanation-chain microcopy; the panel now carries only task, fields, action, error feedback, and one recovery line. Verified: typecheck, 58/58 Vitest, production build, screenshots at 1440/820/375.

* **`/login` visual identity — "The Reading"** ([docs/design/DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md) DD-3, owner-directed creative pass superseding DD-2's composition). Asymmetric split: a deep-ink environment renders an abstracted contract being read — serif clause numbers, text-line bars, the product's evidence-excerpt left-border idiom, a 26s luminance scan with staggered clause attention, and the locked Evidence → Fact → Standard → Rule → Result chain as microcopy — beside a calm sign-in panel. New tokens (`--ink-deep` family, `--font-display` system-serif, `--ease-out-soft`); no dependency added; all ambience `aria-hidden`; `prefers-reduced-motion` removes every animation (verified via browser emulation). Authentication behavior, S-7 single-message rendering, labels/selectors, and all DD-2 behavioral decisions unchanged. Verified: typecheck, 58/58 Vitest, production build, browser screenshots at 1440/1280/1024/820/640/375 plus error, loading, reduced-motion, and keyboard-only passes; two defects caught and fixed in review (band row-crush below 1024px; error banner inheriting the entrance stagger and sitting invisible).

* **Phase 3.1 of the frontend visual retrofit — `/login`** ([docs/design/DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md) DD-2). The first page to adopt the Phase 1 foundation: task-first hierarchy (`<h1>` is now "Sign in"; the wordmark is a quiet label above it), the `.field*` form primitives with explicit `htmlFor`/`id` association, the first `.btn--primary`, `autoFocus` on the email field, and a `.visually-hidden` live region announcing the submitting state (new shared utility in `globals.css`). Behavior preserved exactly: same API call, same redirect, same S-7 single-message failure rendering (deliberately no per-field invalid styling on auth failure — that would visually contradict S-7's indistinguishability), same `getByLabel` selectors the Playwright suite drives. Verified: typecheck, 58/58 Vitest, production build, and a real-browser pass over default/focus/loading/error states at 1440/820/375px including a keyboard-only flow (autofocus → Tab → Enter → error announced).

* **UI/UX design governance, and Phase 1 (Design Foundation) + Phase 2 (Application Shell) of the frontend visual retrofit.** Step 52.6 leaves visual design, component library, accessibility target, and internationalisation `NOT YET SPECIFIED`; this is that implementation-phase choice being made deliberately. [DESIGN.md](DESIGN.md) (root-level, persistent) plus [docs/design/](docs/design/): a current-state audit of the already-implemented frontend ([UX_AUDIT.md](docs/design/UX_AUDIT.md)), three explored interaction directions for the Findings-review workflow with a recorded recommendation ([DESIGN_DECISIONS.md](docs/design/DESIGN_DECISIONS.md) DD-1, proposal only — not implemented), a page-by-page implementation roadmap ([UX_ROADMAP.md](docs/design/UX_ROADMAP.md)), and the concrete token/primitive spec as built ([DESIGN_SYSTEM.md](docs/design/DESIGN_SYSTEM.md)). The foundation itself was implemented as a **retrofit, not a redesign**: `frontend/src/app/globals.css` gained a full token set (color, type scale, spacing scale, radius, focus ring) by substituting every existing literal for an exact-value token — never a rounded or nearby one — plus new opt-in primitives (`.btn--*`, `.field*`, `.table-wrap`) that no existing page has adopted yet. Three narrowly-scoped, audit-cited exceptions actually changed rendered behavior: `.hint`/`.empty` are now visually distinct, `Loading` states (`Feedback.tsx` and `Chrome.tsx`) gained `role="status" aria-live="polite"`, and `form.inline`/the shell now have defined behavior below 640px where none existed before. No `.tsx` file's structure, no route, and no dependency changed. Re-verified after: `npm run typecheck`, `npm test` (58/58 passing, unchanged from before), `npm run build`. No locked decision touched.

* Repository-level documentation system: [README.md](README.md), [docs/README.md](docs/README.md) (documentation index), [CONTRIBUTING.md](CONTRIBUTING.md) (change management), [AGENTS.md](AGENTS.md), and this changelog.

* Frontend implementation of locked Step 52 — Next.js + TypeScript, ten screens, the API as its only data path (38.22), permission-driven rendering as presentation only (47.6), omitted-not-nulled confidentiality rendering (52.4), and no optimistic Legal Decision UI (52.7). Vitest suite. Detail in `frontend/README.md`.

* Backend implementation of the locked specification, on the owner's instruction of 2026-08-17 ("LegalMind V1 has now passed the Implementation Readiness Gate. Begin implementation"), in the sequence the owner set. Complete through the analysis orchestrator: database schema and migrations · authentication and authorization (Step 47) · document storage and ingestion (Step 34) · mapping (Steps 28, 35) · evaluation engine (`LIABILITY-001` and `PRESENCE`, Steps 44, 45A–45D) · decision and review workflow (Steps 4, 22, 30, 31) · HTTP API (Steps 43, 47, 49) · liability fact extraction and the analysis orchestrator (Steps 28, 34, 35, 44). Step 53 observability and the Step 55 preflight register, Dockerfiles and compose file are partial. Test counts are in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which owns build state. No locked decision amended; the additive tables (`sessions`, `user_identities`, `evaluation_evidence`, `unmatched_provisions`, `review_assignments`, `escalations`) all traced to locked requirements the locked schema does not represent — `review_assignments` and `escalations` were subsequently ratified by Amendment Batch AB-2 as `AM-22` and `AM-23`. Detail in `backend/README.md`.

* **Step 53 completed.** Every signal locked 53.5 names now has an emission site — authentication failures (`auth.failure_count`, carrying the source address and never the submitted email, so 53.3's enumeration-oracle prohibition holds), permission denials (`authz.denial_count`, carrying the object id *because* 53.5 asks for "repeated denials on one object"), and decision throughput and age, emitted where a decision is recorded so no scheduler is needed. `workflow.decisions.outstanding_decisions` answers the "stuck in `DECISION_REQUIRED`" half on demand; nothing publishes it on a timer, because 53.6 leaves the monitoring stack and alert thresholds NOT YET SPECIFIED. A test now asserts that no named signal exists only in a document.

* **Step 55 completed as far as the specification allows.** The 55.4 r3 / 55.5 **post-migration reproducibility gate** exists and runs: [`tools/verify_reproducibility.py`](backend/tools/verify_reproducibility.py) applies the latest migration's round trip, then checks both properties the locked rules state — that the historical legal record is **unchanged** (55.4 r1) and that the same Document Version and configuration snapshot still produce an **identical** legal record (55.4 r3, AUD-04, ENG-11). It re-runs the whole pipeline rather than reconstructing an `EvaluatorInput` from persisted rows, because an inference that was subtly wrong would report reproducibility it had not verified. The preflight register grew to 18 checks, covering every row of 55.2's checklist: TLS, encrypted storage, upload validation (checked against the validator, since the declared type is a claim and the magic bytes decide) and safe parsing. **No parse-time page or element cap was invented** — no locked decision fixes one, so sandboxing and resource limits are reported as container-level attestations naming the upload ceiling as the in-process bound.

* **CI jobs 11 and 12** — the reproducibility gate and the independent invariant verification, both against real Postgres (and real Redis for the queue), so the checks that found four defects run on every change rather than once.

* **Two more browser specs.** `escalation.spec.ts` exercises `ROLE-04` (a User may escalate and may approve nothing) and `REC-09` condition (a) end to end: a Review resolved by Legal, then escalated by its owner from the screen, becomes visible to Legal again — the only route back, since Step 30 has no `RESOLVED → LEGAL_REVIEW` edge.

* **Browser-workflow suite (Playwright, locked Step 39).** [`frontend/e2e/`](frontend/e2e/) — 22 tests against real Chromium, a real API and real Postgres, scoped to the locked properties no other layer can prove: S-3's `HttpOnly` session cookie (a browser behaviour, invisible to a `TestClient`), `LEGAL-02` omission surviving the Next proxy to the rendered page *and* its mirror image for a caller who may see it, 52.7's no-optimistic-UI rule including the `409` collision path, SEC-02's no-bypass claim over real HTTP, and 49.5 r1's byte-identical 404s. Fixtures are built through the real endpoints; the only out-of-API step is the first administrator, which locked 47.1.3 r3 puts there on purpose. **Supporting, not a locked tier and not a release gate** — 54.1 has no browser tier and 54.7's gate does not list one. Two harness changes were forced by the locked design rather than the reverse: configuration is published once as `LEGAL_ADMIN` (Step 23), and sessions are reused because seventeen logins exhausted S-5's limiter. No cookie attribute was weakened — `http://localhost` is a browser-trustworthy origin, verified empirically.

* **Independent verification pass.** [`backend/tools/verify_invariants.py`](backend/tools/verify_invariants.py) and [INDEPENDENT_VERIFICATION.md](docs/08-testing/INDEPENDENT_VERIFICATION.md) — each critical guarantee re-checked by a mechanism *other than* the test that asserts it: raw SQL outside the ORM and outside pytest for EV-MIN, append-only and uniqueness; two live schemas for the enum-scoping fix; real worker processes and a real `SIGKILL` for the queue; a grep of 188 real log lines for 53.3; two OS processes with a hostile locale for `ENG-11`. 12 checks, all PASS after one fix. Explicitly **not** third-party verification and it makes nothing `VERIFIED`.

* **Ten `STRUCTURAL` golden-corpus fixtures** covering 44.17 carve-out splitting (a general cap and two carve-outs producing three scoped Evaluations, never flattened), 45C.4's scope-local `UNLIMITED`, `UNKNOWN` magnitude, `FAILED` and `PARTIAL` extraction, unit and basis refusal, 45C.20 scope-required, Tier-1 dominance in the roll-up, and Step 20 r4's no-Legal-Rule case. Every expectation derived from the locked rule the evaluator cites. **The 58 `NORMATIVE` fixtures remain blocked** on real representative contracts and the organization's real Company Standards (rule 21).

* **CI jobs 9 and 10** — the frontend typecheck and Vitest suite (nothing ran them before) and the Playwright suite. Job 1 (`ruff`, `mypy`) is now **blocking** rather than advisory.

* **Queue-backed analysis (locked 55.1, Step 39).** `backend/legalmind/worker/` — a Celery application, the `analysis.analyse_review` task and a dispatcher that chooses queued (`202`) or inline (`201`) from whether `LEGALMIND_BROKER_URL` is set. Both modes call the same `run_analysis`, so submission mode cannot change a legal outcome. Dispatch performs **no writes** before enqueueing, because locked Step 30 leaves `PROCESSING` only for `ANALYSIS_COMPLETE` or the terminal `ANALYSIS_FAILED` — a lost message must not strand a Review. Messages carry identifiers only, plus the dispatcher's `EVALUATOR_VERSIONS` fingerprint, so a skewed worker refuses the job rather than recording Evaluations under a version the caller never ran (55.1's stated reason for deploying together). No result backend: 52.7 makes the Review lifecycle the single source of progress. The compose worker service now runs a real consumer instead of idling, the preflight register gained an `analysis_worker` check that **fails** an inline production deployment, and the frontend re-reads the Review on a bounded interval rather than inventing a client-side `QUEUED` state. `celery[redis]` added to `backend/pyproject.toml` — already in the locked Step 39 stack, so no new technology. 22 backend tests, 7 frontend tests, and an end-to-end run against a real Redis and a real Celery worker.

* **Mapping/extraction terminology for all 21 ratified Company Standards — every Requirement is now publishable as written (owner tasking, 2026-08-19).** Each file under `backend/config/company_standards/` now carries `mapping_rules` (structural `confirm_threshold` 5 — locked 35.9 fixes no value and 35.10's calibration against a representative counterparty set remains outstanding), an `evaluation_rules` payload, and, for the 15 numeric standards, a `configuration.extraction` block. Every term is drawn from the cited source clause's own wording or names the clause type generically; no term encodes a legal position. Two extractor-mechanics additions in tested code (44.29/44.30, no configured semantics moved): the ubiquitous `twelve (12) months` drafting convention is now read (word-only magnitudes like "six months" still refuse to a value, deliberately), and `units` may map a canonical unit key to its clause terms exactly as `bases` already did, so `sixty (60) calendar days` meets a Standard declaring `DAYS` without the evaluator equating units nobody configured (45C.23 untouched — strict equality stands). New [`tools/verify_terminology.py`](backend/tools/verify_terminology.py) parses the REAL gitignored source documents (54.6 keeps them out of every test) and requires each Requirement's terminology to reproduce its own ratified position from the document it cites: **21/21 PASS, deterministic byte-identical ×2**; it SKIPs cleanly where the documents are absent. First-pass verification caught three real defects (page-level segments span sections, so a generic `days` term read a neighbouring section's number) — fixed with clause-specific unit anchors, decisions #18–#22 in [AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md). Publishability is pinned by tests; the import-tool test now asserts no ratified file imports as an unpublishable draft. No locked decision touched; no Legal Rule created; corpus expectations unchanged.

* **The configuration admin screen gained the read and edit paths the standards API already served.** Before this, stored values were write-only through the UI: an admin could draft a version but never see what the current Company Standard said. The screen now fetches the detail response on demand (per Requirement, not per list load) and shows each version's stored Company Standard, with the current version marked. "Change these values" and "Restore these values" both post to the append-only standard endpoint with a mandatory reason — locked rule 16 means there is no in-place edit control anywhere on the screen, and rollback is the same operation pre-filled from an older version. Rule 21 holds: no template, default or suggested value was added. **A version whose Legal Rule the response omitted renders byte-identically to one that has none** (52.4/LEGAL-02) — pinned by a test that compares the two rendered outputs directly, plus tests that the API client exposes no edit-in-place or delete path for a version. 5 frontend tests (58 total); no new endpoint, permission or type.

* **The zero-tolerance Legal Rule is APPROVED and WIRED (owner approval, 2026-08-20), and the L-13 SLA scope question is RULED.** Every ratified standard file now carries the ONE approved Legal Rule — `deviation_outcome` + `unlimited_outcome`, both `UNACCEPTABLE` — which the import tool writes as a `LegalRuleVersion` and refuses in any other form (no tolerance band exists by policy; `acceptable_max`/`approval_required_above` stay forbidden below NORMATIVE). Consequence: any deviation from a ratified standard, unlimited positions included, is `UNACCEPTABLE` and requires a Legal Decision; MATCH requires none; unruled paths still fail closed to a human. The presence evaluator's latent expected-ABSENT deviation path was hardened to read `deviation_outcome` rather than inherit MATCH's ACCEPTABLE. Corpus: CP-LIAB-01 and STD-LIAB-03 now pin the approved rule and expect `UNACCEPTABLE` on their deviations (the owner's approval is the authorized expectation change), closing case **L-08** in full; the loader and the corpus-wide policy test admit the approved rule verbatim and nothing else. **L-13 ruled NOT APPLICABLE**: service credits are a remedy, not a liability cap — liability stays inapplicable to the SLA document type, pinned by a new analysis test. 660 backend tests.

* **First counterparty calibration pass (locked 35.10 direction, 2026-08-20).** The liability standards' terminology now reads counterparty drafting: `will not exceed` / `not to exceed` / `is limited to` join the mapping and extraction vocabulary, and the MSA affected-services basis recognises the same concept in AWS's and CtrlS's words. Probed against the eight public counterparty specimens: AWS §9.2 now maps and extracts **the first live counterparty DEVIATION** (12 months affected-services vs the ratified 6 — `UNACCEPTABLE` under the approved rule); Google and Microsoft caps extract but fail closed on their service-scoped bases (45B.4 — never equated with total fees); CtrlS's genuine same-clause "shall be unlimited" + composite cap resolves to CONFLICT for a human; greater-of/lesser-of/average composites stay deliberately unread — one limb is never presented as the cap. Data-only (no engine change, no position or threshold moved); the own-document baseline held at 21/21 in `verify_terminology`; pinned by 5 new CI-safe tests over short cited excerpts ([test_calibration_counterparty.py](backend/tests/test_calibration_counterparty.py)). 666 backend tests.

* **Full-catalogue counterparty calibration — every one of the 21 Requirements now demonstrably works on counterparty text (2026-08-20).** A 21-requirement probe matrix over every real document available (own source documents, the counterparty tranche, public-web corpus PDFs, and three real executed agreements fetched from SEC EDGAR public filings) drove a second data-calibration round: claim windows now read ESDS's 15-day and Google's 30/60-day drafting, CtrlS's 10-day cure period and rolling-90-day renewal term extract (the latter surfacing an explicit unit mismatch rather than an unreadable clause), the MSA force-majeure requirement reads the generic "continues for more than" trigger a real negotiated 30-day clause used, Castlight's 90-day purge window extracts from a public filing, and the Xerox/Global Imaging Mutual NDA supplies real specimens for survival (its effective-date anchor is deliberately kept incomparable — the 45B.4 trap), non-solicitation and return/destruction. Two extraction-mechanics hardenings with tests: a configured `composite_phrases` fail-closed guard (a multi-limb formula is never reduced to one readable limb — a limb equal to the standard would have MATCHed silently), and the mirrored `15 (fifteen) calendar days` convention (safe only because composites are guarded). Four requirements with no public value specimen anywhere (data-retrieval window, KYC retention period, %-per-month late fee, MSA survival years) are pinned with labelled SYNTHETIC real-pattern tests per locked 54.6. 17 new tests ([test_calibration_clauses.py](backend/tests/test_calibration_clauses.py)); own-document baseline held at 21/21 throughout; 683 backend tests. Decisions #38–#43.

* **Requirement coverage-gap pass — the catalogue goes from 21 to 32 Requirements (owner tasking, 2026-08-20).** A clause-by-clause coverage audit of all six LeapSwitch-issued documents found the 21 ratified Requirements correctly scoped and correctly targeted — document-type scoping, fail-closed refusal and basis separation all verified working — but **shallow where the risk is highest**: `LIABILITY-MSA-001` read the cap number alone, so a counterparty MSA capping at six months with no consequential-damages exclusion and no fraud/gross-negligence carve-out produced a clean `MATCH` and reached nobody. Eleven Requirements ratified in response, all `PRESENCE`, each extracted from a clause the 2026-08-19 full-document review had already read: **MSA** gains `LIAB-EXCLUSIONS` (§17.1/17.6), `LIAB-CARVEOUTS` (§17.3), `INDEMNITY` (Clause 16), `RETURN-DESTRUCTION` (§12.2), `IP-OWNERSHIP` (§13.1), `WARRANTY-DISCLAIMER` (§14.3) and `EARLY-TERM-RESTRICTION` (§7.2); **TOS** gains `ARBITRATION` (§21) and `AUTORENEW` (§4), closing two asymmetries the audit found with no recorded rationale for the omission; **NDA** gains `RESIDUALS` (§11) and `TRADE-SECRET-CARVEOUT` (§9). Final shape: MSA 15 · TOS 8 · NDA 8 · SLA 1. Liability depth is three separate Requirements rather than one enriched Requirement, because one Requirement cannot answer three questions without two answers becoming invisible; `LIABILITY-MSA-001` itself is untouched. Nothing is numeric — §7.2's early-termination fee is a formula, TOS §4 renews for "the same billing period", and a perpetual trade-secret obligation has no magnitude, so extracting any as a value would be the 45B.4 flattening trap. 16 new corpus fixtures: one `STANDARD_DERIVED` MATCH per new Requirement carrying the approved zero-tolerance rule verbatim (`ACCEPTABLE`), plus five `STRUCTURAL` absence cases for the highest-risk clauses (`MISSING`, zero evidence, `NOT_APPLICABLE` → human via D-3.5(b)) — labelled STRUCTURAL because no supplied document omits these clauses and none was invented. Configuration only: no schema change, no new table or column, no locked decision amended, no Legal Rule created (the one approved zero-tolerance rule is attached verbatim to all 32 files, and the import gate still refuses any other). `verify_terminology` **32/32 PASS** against the real gitignored documents; 699 backend tests; ruff/mypy clean. Also recorded and deliberately left open: the CloudPe baseline question (its TOS carries no liability cap and no arbitration clause, yet both TOS standards cite the Leapswitch-branded document), the missing LeapSwitch NDA template, and `CLAUDE.md`'s stale "15 Requirements" catalogue row. Detail in [CLAUSE_CATALOGUE.md](docs/00-project/CLAUSE_CATALOGUE.md); decisions #44–#47.

* **Public-source calibration of the 11 PRESENCE Requirements (owner tasking, 2026-08-21).** The owner extended the test-only source authorization to public web terms, public filings, published policies and statutes, and directed calibration to proceed on those until genuine counterparty contracts arrive — closing the caveat recorded on 2026-08-20, when the 11 new Requirements were pinned on LeapSwitch's own drafting only. **Before: 5 of 13 public specimens mapped. After: 19 of 20.** Data-only — 51 aliases and 23 keyword groups added across the 11 ratified files, **no `exact_phrase`, no position, no threshold, no `expected_presence` touched**. Every gap was a wording difference rather than a concept difference: AWS §9.1 writes "consequential OR EXEMPLARY damages" and "LOST profits" where MSA §17.1 writes "consequential, exemplary" and "loss of profits"; AWS §9.2 writes its carve-out as a saving clause ("nothing in this Section 9 will limit") rather than an exclusions list; Hetzner uses civil-law drafting ("willful and gross negligence", "injury to life"); DigitalOcean disclaims with a bare "as is"/"as available" and no merchantability list, and auto-renews by billing conduct ("recurring basis… automatically charged"); the EDGAR NDA says "destroy all Confidential Information" with no "return" verb at all. Safety property preserved and now pinned: broad single words (`arbitration`, `trade secret`, `residuals`) are aliases only — scoring 3 against `confirm_threshold` 5, so **no single generic term can confirm a mapping alone**; bare `as is` is deliberately not configured, being ordinary English. AWS §6.1 is deliberately left unmapped for `IP-OWNERSHIP-MSA-001` (customer-content allocation, not supplier IP ownership) rather than forcing it with an over-broad term. **Statutes were used as negative specimens** — the only role a statute can hold (rule 7) — in a 7×32 sweep of 224 pairs: 1 mapping introduced by this pass (`ARBITRATION-TOS-001` on Contract Act §28 Exception 1, genuine arbitration drafting), and **3 pre-existing ones discovered and reported unfixed**, of which `ARBITRATION-MSA-001` is a real precision defect — it carries the bare word `arbitration` as an `exact_phrase` and so confirms on a footnote citing "the Arbitration Act, 1940". 21 new tests ([test_calibration_presence.py](backend/tests/test_calibration_presence.py)) using short cited excerpts per locked 54.6; own-document baseline held at **32/32** throughout, which is what proves the variants were additive; 720 backend tests. Decisions #48–#50.

* **Arbitration precision fix, second calibration batch, and the multi-document requirement resolved (2026-08-21).** `ARBITRATION-MSA-001` carried the bare word `arbitration` as an `exact_phrase` at weight 5, so a *single mention* confirmed the mapping — a footnote in the Indian Contract Act reading "Cf. the Arbitration Act, 1940" confirmed a Requirement about whether a contract contains an arbitration clause. Demoted to an alias on owner approval, so two independent signals are now required, and given its TOS counterpart's drafting variants; MSA §19.3–19.4 still confirms on `arbitration` + `arbitrator`. The same pass calibrated the **five PRESENCE Requirements the 2026-08-20 counterparty pass never reached** — `GOVLAW-MSA/TOS/NDA-001`, `COMPELLED-DISCLOSURE-NDA-001`, `RETURN-DESTRUCTION-NDA-001` — every one of which failed its first public specimen: a public EDGAR NDA exhibit writes "governed by and construed **and enforced** in accordance with" (three words inserted into the configured exact phrase), "legally compelled … to disclose" rather than "required by applicable law", and "destroy all Confidential Information" with no `return` verb. Also fixed a **latent test defect**: the score helper read `map_requirement`, which exposes only candidates already at or above `confirm_threshold`, so `assert score < 5` passed on a score of 0 — trivially, even for terminology matching nothing; it now reads `score_clause` and asserts `0 < score < 5`, so "recognised but not sufficient" is genuinely verified. The remaining statute matches are recorded as **not defects** and no `negative_patterns` were added: they fall on text that genuinely discusses arbitration agreements and termination notice, and the control against a statute reaching the evaluator is the declared Document Type at upload, not the mapper. **The multi-document requirement was also resolved as type-matched pairing** (MSA vs MSA, TOS vs TOS), which is already the implemented architecture — a "document set" is a grouping, not a domain object, and cross-*type* comparison stays out of V1 because it would contradict the 2026-08-19 comparability rulings. 726 backend tests; `verify_terminology` 32/32; decisions #51–#57.

### Fixed

* **A database error wrote contract text into an operational log.** Locked 53.3 forbids contract text in logs; locked 53.4 requires the operator-facing stack trace to reach them. `exc_info` was rendered by the log formatter rather than passed through `redact_fields` — the one path that skipped the redactor — and a driver embeds the failing statement **and its bound parameters** in the exception message, so a failure while writing `document_evidence` logged the clause. Confirmed against a real `IntegrityError`, not reasoned about. Exceptions are now rendered as structure: frames and exception type are identifiers and survive in full, while the message is cut at the payload marker (`DETAIL:`, `[SQL:`, `[parameters:`) and then length-guarded like every other logged value. Both locked rules are satisfied rather than traded off, and the rendering happens in the formatter so no caller can bypass it.

* **Running migrations silently disabled application logging.** Alembic's `env.py` called `fileConfig` with its default `disable_existing_loggers=True`, which sets `disabled = True` on every existing logger — including `legalmind`. Migrations run in-process in the test harness, in both verification tools, and in any deployment that migrates from the application image, so after a migration nothing would have been logged for the rest of the process. Nothing legal would have broken (53.1 makes logs non-authoritative) and nothing would have been observable either, which is the failure 53.4's operator-facing half exists to prevent. Found because a test that logged after touching the database captured nothing at all. Two guards added: the flag itself, and a test asserting both the default's behaviour and `env.py`'s use of it.

* **`acks_late` was set; crash recovery was an hour away.** Found by `SIGKILL`ing a real worker: 23 of 24 Reviews recovered and one looked lost. It was not lost — the Redis transport restores a delivered-but-unacked message only after its **visibility timeout**, and kombu's default is 3600 seconds, so a crashed worker's Review would have looked stuck for an hour with no error anywhere. Every earlier test stopped workers gracefully, which restores immediately, so the suite could not see it. `visibility_timeout` is now derived from `task_time_limit` (limit + 60s) so the two cannot drift, and `test_worker.py` asserts the *relationship* rather than the two flags it previously checked. Re-verified: 24/24.

* **A lint baseline that was advisory forever.** Measured at 228 ruff findings and 33 mypy errors, configured where the default rules were wrong for this codebase (with the reason beside each exclusion), and fixed to **zero** — so CI job 1 is now blocking. Two findings were real: an authorization call whose result was bound to an unused name, reading as a lookup rather than a check; and ten `db.get()` results used unnarrowed where a NOT NULL foreign key already guarantees the row, now `db.lookup.must_exist`, which fails loudly instead of letting `None` propagate into the decision path. `ruff format` is deliberately not part of the gate — it would reflow 85 files of hand-aligned tables and locked-rule citations.

* **A worker consumed nothing, silently.** Found by running a real worker rather than by reading the code: the broker was configured only on dispatch, which a worker never calls, so `celery -A legalmind.worker.app worker` came up cleanly on Celery's default `amqp://localhost` and served nothing — a queue that appears to be served and is not. The broker is now configured at import, and a `RequireBroker` bootstep exits non-zero when none is set. The guard was first written as a `worker_init` signal handler, which cannot work: Celery signals swallow receiver exceptions by design, so a handler cannot abort startup.

* **`test_each_axis_has_its_own_enum_type` was not schema-scoped**, so it failed under concurrent runs — `pg_type` is database-wide and each run migrates into its own schema, making an unscoped count report 21 labels for a 7-label enum. [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) recorded this as fixed alongside `F-4`; the query on disk carried no `current_schema()` predicate, so the fix had been lost. Re-applied and verified with four concurrent suites.

* **A truncated skew diagnostic.** The version-skew log line passed both fingerprints inside one prose `detail`, and a real worker log came back reading `[209 chars omitted]` — locked 53.3's length guard correctly treats an over-long value as content, and the operator lost precisely the versions they needed. The fingerprints are now separate short fields; the guard was not relaxed.

* **`F-1` EV-MIN had no removal path.** The invariant was enforced `AFTER INSERT` on `findings` only, so deleting or re-parenting the last Evaluation orphaned a Finding undetected — the exact bypass `F-5` chose a database trigger to prevent. Migration `9c2f41ab77e3` adds `AFTER DELETE` and `AFTER UPDATE` constraint triggers on `evaluations`, both `DEFERRABLE INITIALLY DEFERRED`, with 5 new invariant tests covering deletion of the last Evaluation, deletion of one of several, and re-parenting.

* **`F-4` test non-determinism.** Runs shared the `public` schema and reset it destructively; an intermediate `pg_terminate_backend` fix then killed concurrent runs' live connections. Each run now migrates into a private `t_<epoch>_<random>` schema and drops only its own, with a conservative sweep for debris from crashed runs. Verified by concurrency: 24 consecutive clean runs including 8 concurrent. The originally recorded diagnosis (a dev-database engine in `api/deps.py`) was disproved and corrected.

### Changed

* **`REC-09` — "explicit Legal scope" defined; `F-6` resolved.** Owner decision, 2026-08-17, appended to [`all_lock.md`](all_lock.md) (15,196 → 15,358 lines; the prior lines verified byte-identical). A Review is in Legal scope when **either** any Finding has a non-withdrawn escalation (Step 24 r5, `AM-23`) **or** its status is `LEGAL_REVIEW` (Step 30); a `legal.review` holder may **view** such a Review, with **no ownership** (r16, r17) and **no decision authority** (SEC-02, SEC-05). Both conditions are load-bearing: Step 30's machine has no `RESOLVED → LEGAL_REVIEW` edge, so an escalation after resolution is reachable only by the first; and the engine derives `LEGAL_REVIEW` with no human escalation, so engine-raised work is reachable only by the second. Implemented in `can_see_review` plus the mirroring list scope — **no new permission, endpoint, table or schema change**, and Contract/Document access is unchanged and owner-only. Per-user assignment (`G1`) is **deferred to V2** on `AM-24`'s precedent, since r6's "and/or" permits the assignment branch without mandating it. 15 tests, including a browser spec that cannot fake a `review_assignments` row. Analysis: [LEGAL_ACCESS_GAP.md](docs/06-security/EDGE_CASES/LEGAL_ACCESS_GAP.md).

* **`C-12` registered** — locked Step 39's stack table names `Pytest + Playwright` while locked 54.7 lists "test framework selection" among items "none determined by a locked decision". The same shape as C-11, which `REC-08` resolved **for that one line item only**, so it does not generalize. **Not resolved, and it blocks nothing**: both readings permit Playwright, since it is inside the Step 39 stack either way. Recorded in [CONFLICTS.md](docs/00-project/CONFLICTS.md) with a note appended to [STEP_54_TESTING_STRATEGY.md](docs/08-testing/STEP_54_TESTING_STRATEGY.md) — appended, never an edit to locked text.

* **`F-6` registered — a Legal Reviewer cannot reach any Review.** Visibility is ownership or an active `review_assignments` row, and **no endpoint writes that row**: locked Step 24 r6 requires assignment-controlled Legal access, `AM-22` ratified the table, and neither Step 49 nor Step 47 specifies an endpoint or a permission for creating one. `LEGAL_REVIEWER` holds no `review.create`, so Legal cannot own one either — the Legal decision workflow is unreachable for the roles meant to perform it. The backend suite hides it: **nine test sites insert the row with `db.add()`**, so every Legal-workflow test runs through a fixture the product cannot produce. Surfaced by the browser suite, which cannot fake it. **Not resolved** — a new endpoint and a new permission in the locked 27-permission catalogue are a specification decision. Owner decision required.

* The build-state table was removed from `backend/README.md`. It had drifted ("Frontend ⏳ Next" after the frontend shipped), and [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) is the only document that may assert build state.

* [CLAUDE.md](CLAUDE.md), [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) and this file synchronized against `IMPL-01` and Amendment Batch AB-2. They previously asserted that implementation was unauthorized and that nothing was past LOCKED, which contradicted both `all_lock.md` and the working tree. CLAUDE.md's "What 'no implementation' means concretely" section became "What implementation authorization does and does not cover", carrying `IMPL-01`'s own list of what it does **not** grant. No locked text was altered — `all_lock.md` remains append-only at 15,093 lines.

* **`REC-08`** — CI/CD tooling locked as **GitHub Actions**, appended to [`all_lock.md`](all_lock.md) (15,093 → 15,196 lines; the prior lines verified byte-identical). Resolves **C-11**, a contradiction between two locked records: the Step 39 stack table names GitHub Actions for CI/CD, while locked 55.6 listed CI/CD tooling among NOT YET SPECIFIED operational choices. Owner decision, 2026-08-17 — the Step 39 row governs. Consequence: `.github/workflows/ci.yml` is an authorized use of the locked Step 39 stack, not an unratified implementation choice, and is retained unchanged. 55.6's text is **not** rewritten; it carries a supersession banner for that one line item. Hosting platform, orchestration, object-storage provider, monitoring stack and DR objectives **remain NOT YET SPECIFIED**. Surfaced while correcting [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md), which asserted "No CI pipeline" while an eight-job pipeline was gating `main`.

* Removed a CI step that annotated every run with a warning saying `F-1` was still open. `F-1` was fixed in `e989012`; the step asserted nothing, and an annotation claiming a fixed bug is open is worse than none. Enforcement is `test_ev_min_triggers_are_deferred_to_commit`, which fails if any of the three triggers is missing.

* **`F-*` is an overloaded namespace.** [DECISION_FINALIZATION.md](docs/00-project/DECISION_FINALIZATION.md) §1 uses `F-1`–`F-12` for engineering resolutions; [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) § Blocking the VERIFIED state uses `F-1`/`F-3`/`F-4` for code-review findings. `AM-23` cites "engineering resolution `F-3`" (escalation at Finding level), which is not the `F-3` in the build-state table (Mapping State not persisted). Flagged in [CLAUDE.md](CLAUDE.md); merging or renumbering the two series is an owner decision.

* **Build-sequence numbering differs across three documents.** [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md) §5 is a twelve-step list with the frontend at 10; [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md)'s build table is an eleven-unit list with the frontend at 8, having gained an explicit analysis-orchestrator unit; the owner's build instruction also put the frontend at 8. The *order* agrees in every case — only the numbers differ. Left as written; no document was renumbered.

---

## Stabilization — 2026-08-19

### Fixed

* **`MSA.pdf` blank cross-references repaired (owner instruction, 2026-08-19).** §1.8 *"'Confidential Information' shall have the meaning set forth in Clause ___"* → **Clause 12.1**, and §1.9 *"'Force Majeure' … Clause _____"* → **Clause 18.1**. Both targets were **verified before writing**, not taken on instruction: §12.1 carries the parenthetical `("Confidential Information")` and §18.1 carries `("Force Majeure Event")`. Backup preserved as `legal-docs/MSA-original.pdf` (byte-identical, md5 `9631c36f…`, gitignored like everything in that directory).

  **How, and why it matters.** A first attempt using PyMuPDF redaction plus text insertion was **discarded**: it looked right but appended the replacement to the end of the content stream, so the project's own parser — which reads in stream order, not sorted order — rendered §1.8 as *"set forth in Clause ␣ of this Agreement"* with the number orphaned elsewhere. That is **worse than the blank**: a visible `___` at least signals a defect, while a silently vanished cross-reference does not. The shipped fix instead splices the replacement **inline in the content stream**, decoding the subset font's Identity-H `ToUnicode` CMap to emit the correct glyph IDs. Verified: `legalmind.ingestion.parsing` now reads *"set forth in Clause 12.1 of this Agreement"*; page count unchanged at 21; total extracted text length unchanged; the **only** word-level differences across the whole document are `___`→`12.1` and `_____`→`18.1`; all 8 MSA-cited ratified standards still reproduce their values (`verify_terminology` 21 PASS / 0 FAIL) because no cited clause was touched. Suite **659** passed.

  **Two things deliberately NOT done.** §1.4's blank — *"banks at ___________are open"* — was left untouched: it needs a **city**, which is substantive legal content the documents do not state, and rule 21 forbids supplying it. And the underlying source document (the Word/Docs original) still contains all three blanks — **a PDF patch does not propagate**, so the next export from the template will regenerate them. The durable fix belongs in the source file, with counsel.

### Added

* **Comparability analysis, and a false-MATCH bug it caught.** The owner asked whether the MSA's 3-year and the NDA's 2-year confidentiality survival contradict each other. Read from the clause text: **they are different questions**, on three independent grounds — different trigger (during service delivery vs pre-contractual partnership evaluation), different definitional gate (MSA requires *marking at the time of disclosure*; the NDA protects what "reasonably should be understood to be confidential"), and different clock anchor (MSA: termination; NDA: the **later** of termination and the end of the underlying relationship, with **trade secrets perpetual** where the MSA lets them expire). The decisive consequence: the NDA's two years can run **longer** than the MSA's three, so **"2 < 3" is not a true statement about protection strength** and the numbers are not comparable quantities. This resolves the register's **C-07** by establishing the two clauses were never the same question — nothing to standardize. Same analysis applied to liability (MSA vs TOS: different relationship *and* different basis), termination (committed Term vs self-serve) and governing law (all three agree on India; forums differ legitimately). Recorded in [docs/00-project/CLAUSE_CATALOGUE.md](docs/00-project/CLAUSE_CATALOGUE.md) § Comparability.

  **The bug:** both survival standards carried the bare basis `CONFIDENTIALITY_SURVIVAL`, so a counterparty MSA reading *"three years **from the date of disclosure**"* would have registered a **false `MATCH`** on the number 3 — the 45B.4 basis trap in a second guise, and the worst failure class in this system. Both bases now encode their measurement anchor (`…_POST_TERMINATION`, `…_POST_TERMINATION_OR_RELATIONSHIP_END`), with extraction terminology aligned; `verify_terminology` still reproduces both values from the real documents. Suite **659** passed. Also reported, not fixed: MSA **§1.8**'s cross-reference for "Confidential Information" is **blank** (as is §1.9's for Force Majeure) — the same drafting-defect class as §17.7's blank period; amending the template is the owner's call.

* **The legal documents moved into the project — `legal-docs/`, gitignored, never tracked (owner ruling 2026-08-19).** Formerly at `/root/legalmind-source-material/`. Locked 54.6's "real counterparty contracts do not enter the repository" is now enforced as *version control*, with three guards replacing the old outside-the-tree assertion: the `.gitignore` rule must exist, `git ls-files legal-docs` must be empty (a force-add past the ignore rule is caught), and no copy of any document may exist elsewhere in the tree. Verified live: `git status` shows zero `legal-docs` entries and the executed NDA is ignored. `config.source_material_dir()` now defaults to the in-project path (still `LEGALMIND_SOURCE_MATERIAL_DIR`-overridable); the root README lists all 19 documents.

* **The NDA baseline exists after all — an owner correction, recorded as one.** I had classified `NDA.pdf` as counterparty paper unusable as a baseline, reasoning from its text (the counterparty is the Disclosing Party; every obligation runs against LeapSwitch as Receiving Party). The owner corrected this on 2026-08-19: the executed NDA **is** the LeapSwitch NDA — the positions LeapSwitch **accepts as receiving party**, which is precisely the baseline for reviewing counterparty NDAs, since in that flow LeapSwitch is again the receiving party. **6 NDA Requirements ratified** from it: confidentiality survival **2 years** (§9, trade secrets perpetual) · non-solicitation **2 years** (§10) · termination notice **30 days** (§9) · governing-law, return/destruction and compelled-disclosure presence (§14/§6/§5). Direction caveat recorded once in every standard: these state the *receiving-party* position only. The counterparty is never named. 6 `STANDARD_DERIVED` fixtures; corpus 45 → **51**; suite 647 → **653**. The catalogue's "NEEDS: NDA template" gap is closed — **no document is now owed for the V1 catalogue**.

* **The clause catalogue — LegalMind reviews the document, not just the liability clause.** On the owner's instruction of 2026-08-19 (superseding the 2026-08-18 "liability cap only in V1" ruling), **13 new Requirements** were ratified across three document types, every position **extracted verbatim from a LeapSwitch document and cited to its clause** under the manager's whatever-is-stated rule — none invented. MSA: confidentiality survival 3 years (§12.3) · force-majeure exit 60 days (§18.3) · cure period 30 days (§7.4) · auto-renewal 6 months (§7.3) · data purge 15 days (§7.6.6) · governing-law and arbitration presence (§19). TOS: late fee 5%/month (§7) · data retrieval 7 days (§16) · KYC retention 5 years (§8) · force majeure 60 days (§15) · governing-law presence (§22). SLA: credit-claim window 60 days. Full map with gaps: [docs/00-project/CLAUSE_CATALOGUE.md](docs/00-project/CLAUSE_CATALOGUE.md). **13 new `STANDARD_DERIVED` fixtures** (10 numeric, **the first 3 PRESENCE fixtures** — closing 45E's `P-01`) prove the engine is requirement-agnostic end to end. Corpus 32 → **45**; suite 632 → **647**. NDA Requirements remain blocked on the one genuinely missing input: **a LeapSwitch NDA template** (the NDA in hand is counterparty paper). AUP/Privacy stay Requirement-free (unilateral policies).

* **Zero tolerance is wired: the `deviation_outcome` Legal Rule key.** The manager's ruling is now expressible in configuration: `{"deviation_outcome": "UNACCEPTABLE"}` maps **every** deviation — above or below the standard — to `UNACCEPTABLE`, which locked D-3.5(a) routes to a Legal Decision. Added because the threshold keys cannot express it (`acceptable_max = preferred` would wrongly ACCEPT below-preferred values). Checked before the threshold keys; an invalid outcome value fails closed to `NOT_APPLICABLE` and a human (ENG-09). MATCH never reaches the mapping. The import tool now also handles `PRESENCE` standards and refuses a standard whose evaluator cannot read its position.

* **The owner's conflict register was located and assessed** at `/root/LegalMind/docs/CONFLICT_GAP_ANALYSIS.md` (location use authorized 2026-08-19). Its own tracker marks C-01/C-04/C-05/C-07/C-23 "Needs owner decision" and C-08/C-09 "Needs fact-check" — so it corroborates but does not source positions; the documents themselves do, which the per-type model makes consistent (C-07's "3yr MSA vs 2yr NDA" dissolves: the MSA standard is 3 years, and the NDA in hand is counterparty paper).

* **The Legal Rule is decided: ZERO TOLERANCE (manager ruling, recorded 2026-08-19).** *"Whatever is stated in our approved LeapSwitch legal documents is the final position. We do not provide/customize anything beyond those approved legal-document positions."* Concretely: a client clause that MATCHES the Company Standard is `ACCEPTABLE`; **any** DEVIATION is `UNACCEPTABLE` and requires a Legal Decision; **no deviation is ever auto-approved**. This supersedes every earlier "no Legal Rule exists" statement — the acceptance policy is not missing, it is *that there is no tolerance*. Recorded honestly on two points: **(1) routing does not change** — locked D-3.5(a) already sends `UNACCEPTABLE` to a human, and `UNRULED_DEVIATION_REQUIRES_DECISION` already sends unlabelled deviations to the same place, verified side-by-side; what changes is that the system may now *assert* "unacceptable" as a configured position rather than "no rule, human decides". **(2) The label is not yet wired** — the threshold configuration keys cannot express zero tolerance (`acceptable_max = preferred` would wrongly ACCEPT below-preferred values), so a small engine addition (a `deviation_outcome` Legal Rule key) is the follow-up implementation unit; until then a deviation carrying `NOT_APPLICABLE` is correct and still reaches Legal. Consequential: the three corpus cases blocked on `LEGAL_RULE` (L-03, L-08 outcomes) now await *implementation*, not a decision. Locked Step 8 r8 stands unchanged: approval of a deviation never changes the standard.

* **The admin standards surface — the configuration API can finally be read, changed and audited.** Four gaps found by the earlier config survey are closed, all inside `IMPL-01`, zero schema change. **(1) Values readable:** `GET /requirements/{id}` now returns each version's Company Standard and Legal Rule configuration plus `created_by` — previously write-only, making the stored configuration unreviewable; LEGAL-02 holds because both `configuration.view` roles also hold `legal.position.view`, and the list view stays values-free. **(2) Edit-and-save, lawfully:** `POST /requirements/{id}/standard` appends a new version carrying mapping/evaluation/legal-rule artifacts forward unchanged — locked rule 16's never-edit, wearing the admin UX; a mandatory `reason` lands in the audit trail; an untyped replacement is refused at save time. Rollback = the same call with an older version's values. **(3) Config writes audited:** `config.requirement_created / version_created / standard_updated / published` — closing the gap where every other privileged router audited and configuration did not. Events carry ids, versions and the reason, never configuration values (53.3). **(4) Import tool** [tools/import_ratified_standards.py](backend/tools/import_ratified_standards.py): the ratified standards files, until now read only by the corpus loader, can be written into the runtime database — idempotent by content, refuses files lacking a document type or provenance, creates draft-only Requirements when a file carries no mapping/evaluation rules (none invented, 35.9), and never publishes (that stays a Legal-permission, audited API action). Suite 626 → **632**. Autonomous decisions logged in [docs/00-project/AUTO_MODE_DECISIONS.md](docs/00-project/AUTO_MODE_DECISIONS.md).

* **Document-Type scoping, end to end — an NDA no longer gets MSA rules.** Locked Step 6 (the ten V1 Document Types, `Source = Organization | Counterparty`) and locked Step 28 (each Requirement carries a `Document Type`) were concepts with no implementation: `_snapshot_items()` evaluated every Requirement against every document, which made a counterparty NDA read `MISSING liability cap → Legal Decision`. Now: the uploader declares a Contract's type from Step 6's vocabulary (`legalmind/domain/document_types.py`; owner Q9 — declared, never inferred); every Company Standard declares `document_type` in its JSONB configuration (owner Q2 — the `D-3` route, **no schema change**), which **publish refuses to omit**; and analysis evaluates only the Requirements whose type matches the document's, **refusing with `ANALYSIS_FAILED`** when the Contract's type is undeclared or a pinned standard is untyped, rather than guessing in either direction. The audit record now carries `document_type` and `requirements_applicable` alongside `requirements_in_snapshot`, so "2 pinned, 1 applicable" reads as exactly that. The concept-vs-schema divergence (Step 28/Step 23 vs 42.7's tables) is registered as **C-13**, open and blocking nothing.

* **Per-type Company Standards (owner Q3=B, 2026-08-19).** `LIABILITY-001` is retired as a code; the ratified 12-month/total-fees value survives **byte-identically** as `LIABILITY-TOS-001` (TOS, from `TOS-leapswitch.pdf` §13), and `LIABILITY-MSA-001` is ratified at **6 months of affected-service fees** from `MSA.pdf` §17.2 — the owner choosing §17.2 as the operative clause over the self-contradicting §17.7, whose period is blank. Each document type is now measured against the position its own document states.

* **Two corpus expected outcomes changed — specification-visible under locked 54.1, both direct consequences of Q3=B, both reported to the owner before landing.** `STD-LIAB-02`: MSA §17.2's six months against the MSA standard drawn from that clause is now **`MATCH`** (was `UNABLE_TO_EVALUATE` against the global 12-month standard) — the per-type model's defining consequence, and exactly 45E.2's stated L-01 expectation, so **`L-01` closes** after being blocked since authoring began. `CP-LIAB-04`: Linode's twelve months of *total* fees against the MSA standard's *affected-service* fees is now **`UNABLE_TO_EVALUATE`** (was `MATCH`) — same number, different quantity, and the 2026-08-18 basis ruling keeps them incomparable. The corpus's third-party `MATCH` moves to the TOS side. Suite 617 → **626**; determinism and the reproducibility gate re-verified.

## Stabilization — 2026-08-18

### Added

* **Second Leapswitch/CloudPe document tranche placed (2026-08-19).** Eleven files delivered; five were byte-identical duplicates and were not re-placed. The six new ones: an **executed** Master Services Agreement with a real customer (28 July 2026), a second draft round of the MSA template, and both Acceptable Usage Policies and Privacy Policies. All placed at `LEGALMIND_SOURCE_MATERIAL_DIR`; the archive was moved out of the working tree, and the `*.zip` rule added earlier that day caught it before it could be committed — the first live confirmation that the fix works.

  Three findings worth recording rather than discovering later. **(1)** The executed MSA's §13 is headed "Limitation on **Damages**", not "of Liability", so a heading-based search misses it entirely — and its cap is a formula not seen before: *"the average price or fee paid for Services over a three (3) month period in the period of one (1) year before the liability arose"*, expressly excluding death or bodily injury. An **average** is not a total, so under the basis ruling of 2026-08-18 it is not comparable to `FEES_PAID` and fails closed rather than deviating. **(2)** The second MSA draft's liability clauses are *identical* to the July 2025 template — same six-month §17.2, same blank §17.7 — so it adds no new pattern. **(3)** Both AUPs are saturated with *"includes but is not limited to"* in the enumerative sense while capping nothing; that is the `L-29a/b` false-positive trap appearing in live material, and it is now recorded where an extraction author will see it.

  **No blocked Step 45E case is closed by this tranche**, and the counts are unchanged. The executed MSA does name a real counterparty, so it carries the same handling rule as the NDA.

* **The six source documents are in place, and the ingestion-path cases are no longer blocked on the owner.** Placed at `LEGALMIND_SOURCE_MATERIAL_DIR` under the canonical filenames, byte-identical to the supplied originals and each verified against the attached text by signature clause. `legalmind.ingestion.parsing` reads all six as `COMPLETE`, and the liability detection matches what each document actually contains — a cap in the MSA and the Leapswitch ToS, none in the CloudPe ToS, neither SLA, nor the NDA. `test_source_material.py` went from 3 passed / 6 skipped to **10 passed**; suite 611 → **617 with no skips**.

* **A new `UNSTARTED` coverage status, so the owner's outstanding list stays honest.** Seven cases (L-14, L-15, L-16, L-21, L-23, L-24 and L-27's SUPPORTING-evidence half) were `BLOCKED` on `DOCUMENT_LEVEL_HARNESS`. That precondition is now met, but the fixtures are not authored — which is *our* unstarted work, not something owed by the owner. Recording them as still `BLOCKED` would have overstated what the owner owes; recording them as `AUTHORED` would have been false. `DOCUMENT_LEVEL_HARNESS` is retired as a `needs` value, and the rule that a `PARTIAL` entry must name an owner input was relaxed for the same reason — L-27 is partly authored with the remainder being ours. **What the owner still owes drops to three things: a second tranche (11 cases), an approved Legal Rule (3), and one scope reading (1).**

* **Seven Indian statutes supplied and placed outside the repository** — Contract Act 1872, IT Act 2000, SPDI Rules 2011, Companies Act 2013, CERT-In Directions 2022, DPDP Act 2023, IT Rules 2021. Extracted to `LEGALMIND_SOURCE_MATERIAL_DIR`, not into the working tree (locked 54.6). Recorded with the guardrail that matters: **a statute is neither a Legal Rule nor a Company Standard.** The Contract Act does not state what cap the organization will accept and the DPDP Act does not create a Requirement — rule 7's trap in a new form. They are also not counterparty contracts, so they close none of the blocked Step 45E cases.

### Fixed

* **An archive walked straight past the control that exists to keep legal documents out of the repository.** A `.zip` of seven statute PDFs was delivered into the repository root, and neither guard objected: `.gitignore` listed `*.pdf`/`*.docx` but no archive types, and CI job 8's reject regex was `\.(pdf|docx?|xlsx?|rtf)$`. So the blocked types were committable inside a container. Closed in three places — archive patterns added to `.gitignore`, the CI regex extended to `zip|tar|tgz|gz|7z|rar`, and a local test (`test_no_archive_sits_in_the_repository`) that scans the working tree rather than the diff, because the failure mode is a file dropped in and forgotten, which is exactly how it happened. The zip was moved out of the repository.

* **Four counterparty fixtures — the first genuine `DEVIATION` and the first third-party `MATCH` in the corpus.** Owner authorized third-party public web terms as **test inputs only** on 2026-08-18. `CP-LIAB-01` (Vultr) caps at six months of *total* fees paid — the same basis and scope as the ratified standard, so unlike MSA §17.2 it is comparable, and six against twelve is the corpus's **first `DEVIATION`-by-value**, routed to a human because no Legal Rule dispositions it. `CP-LIAB-04` (Linode/Akamai) caps at twelve months of fees paid and **`MATCH`es** — the first match against independently drafted paper, which establishes more than matching the organization's own documents does. `CP-LIAB-02` (GoDaddy, fixed `$10,000`) and `CP-LIAB-03` (Microsoft Customer Agreement, separate perpetual-licence and subscription ceilings) meet **45E's stated expectations for L-12 and L-05 exactly** — `UNABLE_TO_EVALUATE` not `DEVIATION`, and two Evaluations not `CONFLICT`. Corpus: **32 fixtures — 16 `STRUCTURAL` + 9 `DOCUMENT_SUPPORTED` + 7 `STANDARD_DERIVED`**, still **0 `NORMATIVE`**. Suite 606 → **610**. Coverage: **16 AUTHORED · 2 AUTHORED_RATIFIED · 3 PARTIAL · 18 BLOCKED · 4 OUT_OF_V1_SCOPE · 13 STRUCTURAL_ONLY · 8 SEPARATE_TRACK**.

* **A false positive caught before it became a fixture.** OVHcloud's *"Customer may not bring a claim … more than eighteen (18) months after the cause of action arises"* matched a search for caps longer than twelve months, and is **not a cap at all** — it is a limitation period, a deadline to sue. Encoding it as an 18-month cap would have put a fabricated finding into a Tier-1 normative fixture. `L-03` remains BLOCKED, with the trap recorded in its manifest note.

* **Rule 23 — session continuity — and a `Source material` section in [CLAUDE.md](CLAUDE.md).** On the owner's instruction, after repeated re-derivation of settled work across sessions. Rule 23 states that recorded work stays done regardless of which session, terminal, process or agent performed it, and that "this session did not do it" is never evidence that it has not been done. It requires reading the state first (repository, CLAUDE.md, HANDOFF, IMPLEMENTATION_STATUS, changelog, `all_lock.md`, relevant tests), checking whether a change is already made before making it, assuming concurrency, and keeping five states distinct — already decided · already implemented · material supplied · genuinely missing material · genuinely pending decision. `## The twenty-two rules` became `## The twenty-three rules` and "Working a session" gained a matching step. The companion `Source material` section names **the six supplied documents as the only source material for this project** (owner ruling, 2026-08-18), and records that a second tranche is still outstanding and must not be satisfied from any other directory on this machine.

### Fixed

* The ratified standard's provenance now records the owner's attribution as given (the stakeholder-confirmed C-01 resolution), alongside the corroborating textual source — Leapswitch Networks ToS §13, second bullet — and a note that C-01 as recorded in CONFLICTS.md concerns the Finding-type vocabularies. Both are kept so a future reader is not confused; the owner's attribution governs.

* **Six owner rulings settled, and the four that needed code are implemented.** (1) Company Standard ratified at 12 months of total fees. (2) No Legal Rule exists — recorded as fail-closed behaviour rather than an open request. (3) `FEES_PAID` and `FEES_PAID_FOR_AFFECTED_SERVICES` stay **distinct**: an affected-services cap is never compared numerically to the standard, which needed **no code change** because 45B.4's default already fails closed — recorded in the standard's `_owner_rulings` so nobody "fixes" it later, and pinned by `STD-LIAB-02`. (4) Requirement catalogue is the liability cap only in V1, so four presence/alignment cases move from BLOCKED to the new `OUT_OF_V1_SCOPE` status — decided, not owed. (5) MSA §17.2 and §17.7 govern one scope and contradict, confirming `DOC-LIAB-04`'s `CONFLICT` as ratified rather than merely available. (6) Source documents live outside the repository.

* **Source-material path outside the repository, per locked 54.6.** `config.source_material_dir()` (`LEGALMIND_SOURCE_MATERIAL_DIR`, default `/root/legalmind-source-material`) with a README fixing the six filenames so a fixture can cite a document without embedding its content. [tests/test_source_material.py](backend/tests/test_source_material.py) asserts the properties that matter rather than the documents: that the path is **outside the working tree** (an ordinary `git add -A` must not be able to commit the executed NDA), that absence degrades to a skip rather than a failure so CI stays green, and that **no file named like one of the six exists anywhere in the repository**. 3 pass, 6 skip until the files are placed.

* Coverage after the rulings: **14 AUTHORED · 1 AUTHORED_RATIFIED · 3 PARTIAL · 21 BLOCKED · 4 OUT_OF_V1_SCOPE · 13 STRUCTURAL_ONLY · 8 SEPARATE_TRACK**. Only **3 cases** still await an owner *decision* (a Legal Rule); 22 await *material*. Suite **606 passed, 6 skipped**.

* **The Company Standard for `LIABILITY-001` is ratified: 12 months of total fees.** Owner-supplied 2026-08-18, from Leapswitch Networks ToS §13 second bullet. Recorded once, at [backend/config/company_standards/](backend/config/company_standards/) (then `LIABILITY-001.json`; re-scoped per document type on 2026-08-19 to `LIABILITY-TOS-001.json`, value unchanged), with its provenance, the verbatim source quote, and an explicit statement of what it does *not* contain. Corpus fixtures reference it by `company_standard_ref` and the loader refuses a fixture that supplies both a ref and inline values, so the standard is stated once and cannot drift. It is **configuration** — no `all_lock.md` entry, no locked decision amended. The owner's instruction cited "the confirmed C-01 decision"; `C-01`/`REC-01` resolved the Finding-type *vocabularies* and supplies the `MATCH`/`DEVIATION` terms, but **does not** establish the 12-month figure and no locked decision does. Provenance is recorded accordingly.

* **Un-ruled deviations are now routed to a human — `UNRULED_DEVIATION_REQUIRES_DECISION`.** The owner's fail-closed policy: with no Legal Rule the outcome stays `NOT_APPLICABLE` *and* goes to Legal review. This was a real gap. Locked D-3.5's four conditions do not cover `DEVIATION` + `NOT_APPLICABLE` — `DEVIATION` is Tier 2 — so such a Finding derived to `OPEN`, meaning "nothing ever required a decision", while locked Step 20 r4 says in prose that with no rule "the deviation stands and a human decides". `F-4` expressly permits configuration to **widen** the D-3.5 set and never to narrow it, and `widen_decision_requirement` existed for the purpose but was **never called**; it is now the wired extension point. Verified end to end against a real database, not only through the predicate: a 24-month clause against the ratified 12-month standard persists a Finding at `DECISION_REQUIRED`. **Consequence, recorded deliberately:** no Legal Rule exists anywhere, so in V1 essentially every deviation requires a Legal Decision and a Review holding one cannot complete until Legal rules.

* **`AUTHORED_RATIFIED` coverage status.** 45E.2's expected outcomes for L-01–L-04 were written against the *illustrative* six-month standard; ratification at twelve months supersedes them. The status marks that distinction rather than quietly restating either. No text in `GOLDEN_CORPUS_45E.md` was altered — the six-month examples were labelled illustrative, and this is them behaving as labelled.

* **`STANDARD_DERIVED` corpus tier, and the first `MATCH` assertions in the repository.** On the owner's V1 interim policy of 2026-08-18 — *"I do not currently have a formally approved LeapSwitch Company Acceptance Policy or Legal Rule. For V1, use the supplied LeapSwitch legal documents as the authoritative source for the positions they explicitly state"* — four fixtures now measure real clauses against a position the documents state: MSA 17.2's six months and ToS 13's twelve months each `MATCH` their own clause, and ToS 13's cap plus its three carve-outs reaches 45E's L-08 shape in full (general `MATCH`, carve-outs `DEVIATION`, roll-up `DEVIATION`, 45C.4 holding). Corpus at this step: **29 fixtures**, suite 593 → **601**; superseded later the same day by the ratification entry above (**28 fixtures**, suite **603**) — `STD-LIAB-MSA-01` was withdrawn because it used MSA 17.2's six-month position as a Company Standard, which the ratification of twelve months displaced.

* **`STD-LIAB-CROSS-01`, which settles how the open standard ruling must be made.** MSA 17.2 measures against fees for *the affected Services*; ToS 13 against *total* fees. Evaluating ToS 13's clause against MSA 17.2's position therefore yields `UNABLE_TO_EVALUATE` on basis comparability (45B.4, 45C.23), **not** a twelve-versus-six `DEVIATION` — six and twelve are not two values of one quantity. The choice between the documents' positions cannot be made by preferring the smaller number.

* **The classification/rule_outcome separation enforced, not described.** No approved Legal Rule exists, so `load_fixture` refuses any `DOCUMENT_SUPPORTED` or `STANDARD_DERIVED` fixture that configures `acceptable_max`/`approval_required_above`/`unlimited_outcome` or expects a Rule Outcome other than `NOT_APPLICABLE`, and `test_no_fixture_asserts_an_acceptance_policy` re-checks every real-material fixture at once. `STRUCTURAL` fixtures stay exempt by design — `STRUCT-FC-*` exercise the threshold machinery over `UNIT_X`/`SCOPE_A`, values declared to carry no legal meaning. **`NOT_YET_SPECIFIED` was requested and deliberately not added**: locked Step 20 r4 already gives `NOT_APPLICABLE` that meaning (*"the deviation stands and a human decides"*), and a fifth `RuleOutcome` value would be an enum change outside any lock record.

* **A document-derived golden-corpus tier, and nine fixtures built from the supplied contracts.** On the owner's instruction of 2026-08-18 the corpus was extended using only the six supplied documents — no synthetic contract, no invented clause, no fixture written to satisfy a count. `provenance` gains `DOCUMENT_SUPPORTED` (the expected output follows from real clause text plus the locked specification alone) and `STANDARD_DERIVED` (computed from a supplied Company Standard; **none exists**), each fixture citing `source_document` and `source_clause` per 45E.7 rule 1. The nine assert the fail-closed, conflict and absence paths, where the engine's answer does not depend on what the organization will accept: `CONFLICT` between MSA 17.2 and 17.7 with in-document precedence detected but not applied (45C.2/45C.27) · the unfilled period in 17.7 refused rather than guessed (45C.19) · two bases in one agreement not silently converted (45B.4/45C.23) · carve-out splitting in two independently drafted provisions, with the whole provision never classified `UNLIMITED` (45C.3/45C.4) · a liability clause with exclusions but no cap as `MISSING` **with** evidence, against an agreement with no liability provision at all as `MISSING` with **zero** evidence (45C.14/45C.15). Corpus at this step: **25 fixtures — 16 `STRUCTURAL` + 9 `DOCUMENT_SUPPORTED`**, suite 508 → **593**; both figures were superseded later the same day by the `STANDARD_DERIVED` entry above.

* **The provenance boundary is enforced rather than documented.** `load_fixture` refuses a `DOCUMENT_SUPPORTED` fixture that supplies `preferred`, supplies `acceptable_max`/`approval_required_above`/`unlimited_outcome`, expects `MATCH`, or expects any Rule Outcome but `NOT_APPLICABLE`. This mechanically closes the inversion the owner ruled out: `preferred: 6` lifted from Leapswitch's own MSA would otherwise yield a `MATCH` labelled as derived from the document, turning a cap a vendor grants itself into a standard that vendor demands.

* **[backend/tests/corpus_coverage.json](backend/tests/corpus_coverage.json)** with [test_corpus_coverage.py](backend/tests/test_corpus_coverage.py) — a status for each of the 64 fixtures Step 45E specifies, so the dangerous failure (a fixture nobody wrote and nobody noticed) is caught. At this step **14 AUTHORED · 4 PARTIAL · 25 BLOCKED · 13 STRUCTURAL_ONLY · 8 SEPARATE_TRACK**; the V1 interim policy later the same day moved it to **15 · 4 · 24 · 13 · 8**. Every blocked or partial entry names what it needs from one of six values, and the ids are derived from 45E rather than copied, so a dropped or invented id fails.

* **[HANDOFF.md](HANDOFF.md)** — the entry point for final review. States where the build stands, how to verify it independently (with expected results), what is honestly not done, every decision still with the owner (8 pending-ratification items, 6 conflicts, 14 open decisions, the NOT YET SPECIFIED register), and the **exact material required** before the 58 `NORMATIVE` fixtures and Step 35 calibration can begin. It asserts no build state of its own — [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md) remains the only document permitted to do that.

* **[docs/00-project/SOURCE_MATERIAL_INTAKE.md](docs/00-project/SOURCE_MATERIAL_INTAKE.md)** (📁 ANALYSIS) — assessment of the first tranche of legal source material, six Leapswitch-issued documents supplied 2026-08-18, against HANDOFF.md §6.1. Two of five required items are met: extraction terminology is substantially supplied (real, quoted, attributed) and representative contracts partially. **The Company Standard, the Legal Rule and Requirement applicability are entirely unsupplied**, so the tranche yields fixture *inputs* for roughly 18 of the 30 liability fixtures and expected outputs for none — an expected output is a legal conclusion only the owner can state. Records a fixture-by-fixture coverage table, the eight fixtures with no specimen text in this tranche (including L-29a/b, since no document contains unlimited-liability wording), an evidenced false-positive hazard ("without limitation" occurs throughout in the enumerative sense), three storage decisions locked 54.6 requires, and two divergences observed in the documents — reported, not resolved, and deliberately **not** filed in [CONFLICTS.md](docs/00-project/CONFLICTS.md), which tracks specification contradictions rather than contradictions between the organization's own contracts. **No fixture was authored, no configuration value chosen, and no document committed to the repository.**

### Changed

* **Documentation synchronized against the current locked state.** [CLAUDE.md](CLAUDE.md) had `all_lock.md` at 15,196 lines and `REC-01`–`REC-08`; it now reads 15,358 and `REC-01`–`REC-09`, records the build sequence as complete, counts six open conflicts rather than five (adding **C-12**), and points at the handoff. [README.md](README.md) moved from "IMPLEMENTATION" to "STABILIZATION" and had its locked-decision list corrected. Three stale figures were fixed in [IMPLEMENTATION_STATUS.md](docs/00-project/IMPLEMENTATION_STATUS.md): the corpus row still said "6 of 64" (it is 16 `STRUCTURAL`, 0 `NORMATIVE`), the CI row still said "eight jobs" (twelve), and the independent-verification count said 11 PASS (twelve, including the 55.4 r3 gate).

* **A correction to a figure previously reported as "26 Playwright tests".** 26 is what the runner prints; **22 are tests** and 4 are setup steps (three sign-ins and the configuration publish). Both numbers are now stated wherever the count appears.

* The historical `F-4` concurrency evidence in `IMPLEMENTATION_STATUS.md` is now dated, so its `385 passed` figures read as a record of what was run on 2026-08-17 rather than as current counts.

### Not done, deliberately

* **No feature work.** No endpoint, permission, table, column, enum or architectural boundary was added or changed, and `all_lock.md` was not touched — it stands at 15,358 lines.
* **No `NORMATIVE` fixture and no Step 35 calibration.** The owner's rulings of 2026-08-18 settled the Company Standard, Requirement applicability and the storage question, so the outstanding inputs are now exactly two: an approved **Legal Rule**, and a **second tranche** of counterparty-drafted paper for the 14 cases with no specimen (HANDOFF §6.1). Nothing was invented to fill either. In particular the six-month cap in the supplied Master Services Agreement was **not** read as the organization's Company Standard — it limits Leapswitch's own liability as vendor, and treating it as a standard would invert the direction of the limit. See [SOURCE_MATERIAL_INTAKE.md](docs/00-project/SOURCE_MATERIAL_INTAKE.md) §2.2.
* **No pending-ratification item, conflict, `OD-*` or ATTEST/BLOCKED item was resolved.** Each is reported in `HANDOFF.md` §5 with what it blocks and what deciding it would take.

## 2026-08-17 — V1 specification complete

The V1 specification reached completeness. `all_lock.md` grew to 14,885 lines, append-only throughout.

* **Amendment Batch AB-1** locked — 13 amendments repairing locked requirements the locked schema could not represent; two new tables (`evaluation_evidence`, `unmatched_provisions`). No legal policy changed.
* **Steps 45B (re-lock), 45C, 45D** locked — evaluator data contract, liability edge cases, cross-evaluator structural contract and the generic `PRESENCE` evaluator.
* **Step 47** locked — security, authentication (OIDC primary with password fallback, `OD-9`), authorization, permission catalogue; new `sessions` and `user_identities` tables.
* **Steps 49, 52, 53, 54, 55** locked — API finalization, frontend architecture, observability, testing strategy, deployment. No schema impact.
* **Step 45E** opened — golden corpus, 64 fixtures specified. In progress.
* **Implementation Readiness Gate** — all nine criteria met. Reports readiness; does not grant it. Supersedes the interim readiness review.

Registry: [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md) §AB, §S47, §S49–55 · Gate: [IMPLEMENTATION_READINESS_GATE.md](docs/09-implementation/IMPLEMENTATION_READINESS_GATE.md)

## 2026-08-16 — Cross-document reconciliation

* **`REC-01` – `REC-07`** locked. Conflicts C-01 – C-04 reconciled; none was a true contradiction. The Step 36 seven-value set became canonical for Finding Classification; `ADDITIONAL`/`EXTRA` became the document-level `UNMATCHED_PROVISION` observation; the **Five-Axis Decision State Model** was established as the canonical cross-layer state reference. No historical locked text was modified.
* Four low-severity conflicts (C-05 – C-08) remain open.
* The scoring-band → mapping-state mapping was **deliberately left unspecified** by owner decision. It must not be inferred.

Detail: [CONFLICTS.md](docs/00-project/CONFLICTS.md) · [DECISION_STATE_MODEL.md](docs/02-legal-domain/DECISION_STATE_MODEL.md)

## Earlier — Steps 1–45A

The design specification: product scope, roles and authority, the legal domain model, document and evidence models, the layered analysis engine, `LIABILITY-001`, system and database architecture, audit and reproducibility. Recorded step by step in [`all_lock.md`](all_lock.md) and indexed in [LOCKED_DECISIONS.md](docs/00-project/LOCKED_DECISIONS.md).

---
