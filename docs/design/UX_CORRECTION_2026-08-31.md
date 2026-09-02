# UX Correction — 2026-08-31: Upload-first, analysis-in-flow

**Status:** 📁 PROPOSAL → implemented same day (owner-ordered "DEEP UX / PRODUCT MODEL
AUDIT"). This is the §17 A–L deliverable and the §18 change matrix. Outcomes land in
code, CHANGELOG and AUTO_MODE_DECISIONS — never here. The 2026-08-31 UI freeze stands
for the visual system; this is the owner-requested UX review the freeze anticipated
(decision #222 explicitly allowed "a mismatch with the approved product strategy").

**Design authority:** the ratified UI master prompt + ui-ux-pro-max (upload-feedback,
progressive-disclosure, error-recovery guidance applied throughout).

---

## A · UX problems found, ranked

| # | Problem | Rank |
|---|---|---|
| 1 | **The intake is the backend's object lifecycle, verbatim**: create a named, typed, EMPTY record → open a workspace that says "No document uploaded yet" → only then pick the file. The user's job — "here is a contract, analyze it" — is inverted into "register a database row, then attach evidence to it." | **Critical** |
| 2 | **Analysis is unreachable in the product.** Nothing in the new UI can start a Review; the findings pane literally said "Starting a Review isn't built into this screen yet." Root cause is an API hole: `POST /configuration/publish` exists but NO endpoint reads existing snapshots, so the UI cannot resolve "the current standards" to analyze against. The core journey (upload → analysis → report) dead-ends after upload. | **Critical** |
| 3 | **The Documents list speaks database** (`DRAFT`, a contract-lifecycle enum) instead of answering the one question a legal user has: *what did the analysis find, and where do I need to look?* | **High** |
| 4 | **Name (required)** forces the user to invent a label the filename already carries. | **Medium** |
| 5 | **Type selection is presented as a prerequisite gate** ("only then can upload happen") rather than a confirmation in the flow of uploading. | **Medium** |
| 6 | Upload offers no drag-and-drop and no staged progress (uploading → processing → analyzing), and duplicate detection (`duplicate_of`, already returned by the API) is never surfaced. | **Medium** |

Not problems (validated, preserved): the three-pane workspace, evidence highlight,
ungated Ask, the version picker (compact, honest, URL-addressable — audited under §11
and kept), the Reviews/Legal/Ask history/Admin areas, every guardrail.

## B · Current vs recommended flow

```
CURRENT                                   RECOMMENDED
Documents                                 Documents
  ↓ type a Name                             ↓ [Upload a contract]  (file picker + drop)
  ↓ pick a Type                             ↓ one confirm panel:
  ↓ "Add and open"                              Name   [RSA]      ← from the filename, editable
  ↓ EMPTY workspace                             Type   [choose…]  ← human-declared; filename
  ↓ "No document uploaded yet"                                       HINT shown, never preselected
  ↓ Choose File → Upload                    ↓ "Upload and analyze"
  ↓ (analysis impossible in UI)             ↓ workspace: uploading → processing (N passages)
                                                → analyzing against snapshot <id> → findings
                                            (each stage real, none faked; every failure
                                             states what to do next)
```

Internally the system still does create → version → parse → index → snapshot → review →
analyze. The user sees one act. (Owner §14: the frontend translates system complexity.)

## C · Information architecture

- **Documents** = the working inventory: each row answers "what is it, what did analysis
  find, when." Backend enums stay out of it.
- **Workspace** = the product's center (unchanged): text · findings/report · ask.
- Reviews/Legal/Ask history/Research/Admin: unchanged; their IA was audited 2026-08-31
  and matches the role model (analyst works Documents→workspace; legal works
  Legal/Reviews; admin works Admin — §I below).

## D · Upload experience (exact)

1. Documents page: primary control **"Upload a contract"** — a real file input, also a
   drop target. Empty state = the same control plus one sentence of purpose ("Give
   LegalMind a contract and it compares it with your approved legal standards").
2. On file choice: an inline confirm panel (no modal, no navigation):
   **Name** prefilled from the filename (extension stripped, separators tidied),
   editable. **Document type** — an empty, required select of the ten Step 6 values;
   when filename tokens match a type, a hint line: *"The filename mentions 'MSA' —
   select it if that's right"* (a button applies it). The hint is presentation only:
   nothing is preselected, nothing is inferred into the record (owner Q9 ruling intact —
   the declaration is the user's selection, always).
3. **Upload and analyze** (one primary act): create → upload → resolve latest published
   snapshot → create Review → run analysis — best-effort chain; the user lands in the
   workspace at whatever stage is real:
   - upload rejected (type sniff, size, empty) → the server's own message, beside the control
   - `duplicate_of` returned → plain note ("identical to version N — kept as a new
     version; whether it is a new contractual version is your call", 34.5)
   - parser failure → the processing error, with re-upload available
   - no published snapshot → "processed; analysis needs published standards" (honest
     blocked state naming who unblocks it: Legal)
   - no `review.create` → processed, note states the missing permission
4. No fake progress: stages render from real fields (`processing_run.status`,
   `evidence_count`, review lifecycle 52.7).

## E · Document identity model

- **Name**: derived from the filename as an editable default — never demanded up front.
  Identity and audit are untouched: identity is the id; `original_filename`, bytes and
  hash are preserved on the version (34.2/34.4); duplicates of a NAME are legal and
  harmless; rename stays possible via the existing `PATCH /contracts`.
- **Type**: remains **human-declared** (owner Q9, locked) and remains required before
  analysis (undeclared type still fails closed at analysis). What changes is WHEN and
  HOW: declared in the flow of uploading, with a local filename hint. **No LLM
  classification**: the AM-31 gate is closed (no generation credential exists), and a
  model suggestion that pre-fills an authoritative comparison choice would blur
  §6's classification/authority line for marginal benefit over the filename hint.
  Revisit only if the owner asks after AM-31 opens.
- **Classification ≠ authority (owner §6)**: type selects WHICH ratified standards
  apply; authority lives only in the ratified configuration (imported, cited,
  versioned). An uploaded "MSA" never becomes a baseline. Unchanged, by construction.

## F · Document workspace

Unchanged in structure (it already matches the owner's §9 sketch). Two behavior
additions: the findings pane's no-review state becomes the **Analyze** action (against
the latest published snapshot, named on screen — reproducibility visible), and the
processing stage renders between upload and analysis.

## G · Versioning UX

Kept as built on 2026-08-31 (audited under §11): versions live on one document; the
picker names "v2 (latest)"; each version's text/findings/report stay reachable; Ask
follows the latest version and says so. Addition: a freshly uploaded revision now offers
**Analyze** in place (same control), so Journey D is one screen.

## H · Chat relationship

Unchanged: Ask is available the moment a version is indexed, never gated on findings or
resolution (AM-25 r1, e2e-pinned). The corrected intake makes it REACHABLE faster.

## I · Role-based experience

Already differentiated by nav-by-existence + permissions: an analyst sees Documents/
Reviews/Ask history/Research; legal.review adds Legal; admin permissions add Admin (and
nothing legal — SEC-02). No change required; validated.

## J · UI changes required

- **Functional UX** (this correction): upload-first intake; analyze-in-flow; findings
  pane no-review state → Analyze; Documents rows speak analysis, not lifecycle enums;
  duplicate/processing/blocked states surfaced.
- **Visual**: none — existing tokens/components only (freeze respected). The two
  affected visual baselines are re-cut once via CI, batched in one round.
- **Backend/API**: below.

## K · Existing backend reused AS-IS

Everything: contracts, upload/ingest (incl. duplicate detection + diagnostics),
processing runs, evidence, assist indexing, reviews (idempotent creation), analysis,
findings/report, conversations, permissions, audit. No schema change. No engine change.

## L · Backend changes required (the only two, both additive)

1. **`GET /configuration/snapshots`** — list snapshots, newest first, **metadata only**
   (id, created_at, item count; no standard values — LEGAL-02). Gate: `review.create`
   (its sole purpose is starting a Review). Without it the correct UX is impossible;
   with it, "analyze against current standards" is one call. Recorded as a Step 49
   implementation addition (the #187 precedent).
2. **`latest_analysis` on `GET /contracts` rows** — the newest version's newest Review:
   status, classification counts, timestamps; `null` when none; **included only for
   callers holding `finding.view`** (counts are derived from Findings). Three
   page-bounded queries, no N+1. Same Step 49 record.

## §18 change matrix

| Area | Current | Recommended | Action |
|---|---|---|---|
| Intake | create empty record → open → upload | upload-first, one confirm panel | **Change (frontend)** |
| Name | required, hand-typed | filename-derived editable default | **Change (frontend)** |
| Type | required before anything | human-declared in the upload confirm, filename hint, never preselected | **Change (frontend)**; Q9 ruling untouched |
| Analysis | unreachable in UI | one-click / chained, latest published snapshot named on screen | **Change (frontend + additive endpoint)** |
| Documents rows | NAME/TYPE/DRAFT/date | name · type · findings summary or real stage · date | **Change (frontend + additive list field)** |
| Workspace | three panes, highlight, honest states | same | **Reuse** |
| Chat | ungated after indexing | same | **Preserve** |
| Versioning | picker + per-version panes + honest Ask note | same + Analyze in place for a fresh revision | **Keep, small addition** |
| Report/Findings/Legal/Reviews/Admin | as frozen | same | **Reuse** |
| Engine/API contract | AM-33 semantics | same | **Reuse** (two additive reads only) |

## N · Blockers

None for this correction. (Unchanged externals: AM-31 inputs, C-16, second tranche.)
