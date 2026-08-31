# Product-Intent Audit — 2026-08-31

**Status:** 📁 ANALYSIS — records the owner-ordered deep R&D of 2026-08-31 ("LEGALMIND —
DEEP PRODUCT / ARCHITECTURE R&D + CORRECTIVE IMPLEMENTATION"). Outcomes land in
`all_lock.md` (AM-33), `LOCKED_DECISIONS.md`, `CHANGELOG.md` and code — never here.

The owner supplied product intent, not a specification, and asked for a full audit of
current behavior against it before any correction. Verdict up front: **the intent and
the implemented system already agree on almost everything** — the five-axis separation,
MATCH/DEVIATION/MISSING semantics, ungated chat, version-scoped analysis — because the
locked specification made the same separations the owner described. Three genuine gaps
were found and are corrected: one dormant-but-live piece of forbidden rule semantics in
the evaluator, and two lifecycle gaps in the new UI.

---

## A · Current architecture (verified, not assumed)

```
POST /contracts                          Contract (declared type, Step 6/owner Q9)
POST /contracts/{id}/document-versions   DocumentVersion (bytes preserved 34.2; duplicate
                                         DETECTED and reported, never suppressed — 34.5;
                                         a re-upload is a business decision, Step 33.9)
  → ingestion → parsing → Evidence rows (reading order) → assist chunking/indexing
POST /reviews {document_version_id, configuration_snapshot_id}
  → Review (idempotent per version+snapshot+creator, 49.8)
POST /reviews/{id}/analyze → mapping → evaluation → Findings (classification +
  Evaluations + rule outcome + evidence refs) — deterministic lane, config snapshot
GET  /reviews/{id}/findings · /report    per-Review, any version, forever (audit
                                         append-only; snapshots keep it reproducible)
POST /conversations {contract_id} → messages    assist lane (AM-25): retrieval is
  strictly WHERE document_version_id = <the contract's LATEST version> — never
  cross-version, never cross-contract; cite-or-refuse; byte-identical refusal (AM-29)
```

## B · Current product semantics (exact)

| Term | Meaning today | Matches intent? |
|---|---|---|
| MATCH | provision agrees with the Company Standard | ✔ §5 |
| DEVIATION | provision present, differs from the standard | ✔ §5 |
| MISSING | required standard position absent from the document (`numeric.py` ABSENT branch; PRESENCE evaluator) | ✔ §5 |
| CONFLICT | two provisions **in the same uploaded document** govern one scope and contradict (MSA §17.2 vs §17.7; fixture DOC-LIAB-04) — never used for company-vs-counterparty difference | ✔ §8 — defined terminology, kept |
| UNABLE_TO_EVALUATE | fail-closed extraction/evidence insufficiency (rule 15) | ✔ |
| Rule Outcome | a SEPARATE axis (ACCEPTABLE / APPROVAL_REQUIRED / UNACCEPTABLE / NOT_APPLICABLE — Step 20, locked; 45B.26 forbids a fifth) mapping an already-detected deviation onto a disposition **only per an explicit configured rule**; no rule → NOT_APPLICABLE → a human | ✔ §7 — comparison and decision never collapse |
| Legal Decision | a human's ruling, its own axis, engine never produces one | ✔ §7/§11 |

The five state axes (Mapping / Classification / Rule Outcome / Legal Decision /
Lifecycle) plus the sixth assist answer state are locked in DECISION_STATE_MODEL.md and
implemented as separate fields. §7's layer separation **is** the current architecture.

## C · Product mismatch — everything found

1. **[REAL — corrected] A live tolerance-band interpreter in the evaluator.**
   `evaluation/numeric.py::_rule_outcome_for` still interprets `acceptable_max` /
   `approval_required_above` if a Legal Rule carries them — including mapping a
   DEVIATION to **ACCEPTABLE** (`actual <= acceptable_max`). Unreachable under the
   approved configuration (the import tool refuses those keys; the corpus loader
   refuses them; the ONLY approved rule is the zero-tolerance blanket) — but the code
   path is live, and the **e2e bootstrap actually uses the band form**
   (`acceptable_max: 12, approval_required_above: 12`) to exercise APPROVAL_REQUIRED.
   One unit test (`test_thresholds_come_from_configuration_not_code`) asserts
   DEVIATION→ACCEPTABLE through a lenient band. §6 forbids exactly this semantic.
2. **[REAL — corrected] The blanket path can also mint DEVIATION+ACCEPTABLE**: a rule
   `{"deviation_outcome": "ACCEPTABLE"}` would be honored verbatim. No such rule can be
   imported today, but the engine should refuse the semantic itself (rules 14/15).
3. **[REAL — corrected] Revised-version upload is absent from the new UI** (§3). The
   backend fully supports it; `UploadDocument` renders only in the no-version empty
   state, so a user cannot upload Version 2 through the frozen UI.
4. **[REAL — corrected] Historical versions are unreachable in the new UI** (§4/§17).
   The workspace always opens `document_versions[0]` (newest). After V2, V1's findings
   survive as counts (report page) but its document text and finding detail cannot be
   opened. Product intent: V1 "remains historically valid."
5. **[NOT a mismatch] Chat gating** (§2/§9/§19): chat is already ungated — it requires
   an uploaded, indexed document and nothing else (AM-25 r1 "asking is not judging";
   e2e-proven with `analyse: false`). No finding, resolution, or acceptability state
   gates it.
6. **[NOT a mismatch] Re-analysis is real** (§4): a new version gets its own Review and
   full pipeline run; nothing marks V1 findings resolved (rule 14: RESOLVED ≠ MATCH).

## D · Existing "acceptable deviation" logic — every occurrence

| Location | What it is | Disposition |
|---|---|---|
| `all_lock.md` 45B.9 (+ Step 20/35 worked examples: 6 preferred / ≤12 acceptable / >12 approval / unlimited unacceptable) | the LOCKED **rule-form definition** with the band example | superseded by **AM-33** (appended; original lines untouched per rule 22). The 45B.9 *separation principle* (Standard ≠ Rule) is reaffirmed — only the band FORM is withdrawn |
| `evaluation/numeric.py` 43-45, 275-286 | live interpreter of the band keys | **removed** — band keys now fail closed to NOT_APPLICABLE + a human |
| `tools/e2e_bootstrap.py` 130-131 | STRUCTURAL e2e rule using the band form | **swapped** to the approved blanket form (structurally) |
| `tests/test_evaluation_numeric.py::test_thresholds_come_from_configuration_not_code` | asserts DEVIATION→ACCEPTABLE via band | **rewritten** to assert the fail-closed refusal; §24 regression tests added |
| `evaluation/corpus.py` ACCEPTANCE_RULE_KEYS | **refusal** list — already forbids the keys on fixtures | kept (it is the guard, not the rule) |
| `tools/import_ratified_standards.py` | refuses any rule but the approved blanket | kept |
| `observability/redaction.py`, `assist/generation.py` | key names listed so values are REDACTED / never emitted | kept (confidentiality guards) |
| spec worked examples throughout `docs/` | illustrations, explicitly "not the organization's positions" | kept (CLAUDE.md: Preserve the examples) |
| `config/company_standards/*` `"preferred"` | the key naming THE company position value (single value, no band) | kept — name only; semantics are zero-tolerance |
| Frontend `ATTENTION_OUTCOMES` incl. APPROVAL_REQUIRED | rendering vocabulary for the locked outcome enum | kept — vocabulary ≠ policy |

## E · Document lifecycle (current)

Upload → DocumentVersion (per-contract sequence; duplicates detected, reported,
still versioned — business decision stays human) → parse → Evidence → assist index →
Review per (version, snapshot) → analyze → Findings → report → chat (latest version).
Re-upload = new version; old Reviews/Findings/evidence immutable and reproducible.
Versioning model: **Contract → DocumentVersion** already exists (42.13, 42.4) — no new
architecture needed (§18: the simplest model that satisfies the requirement is the one
already locked and built).

## F · Authority model

Company-authoritative positions are **ratified configuration**, one file per standard
(`backend/config/company_standards/`, 32 standards), each carrying `source_document`,
`source_clause` and a verbatim `source_quote` from the company's own executed/published
documents — extracted by the owner's 2026-08-19 full-document review, imported by a
tool that refuses anything but the approved rule form. The company MSA document itself
is deliberately NOT machine-read at analysis time: ratification-into-configuration is
what makes the authoritative lane deterministic, snapshot-versioned, and auditable
(rule 7/21: a machine inferring the company's position would itself be an invented
legal conclusion). §16 answered: the company document IS the source; the configuration
is its ratified, cited, versioned projection — no duplication beyond the cited value.
Uploaded counterparty documents are never authoritative; confidentiality of internal
positions is permission-gated (LEGAL-02, omitted-not-nulled).

## G–J · Impact (backend / database / API / frontend)

- **Backend:** `numeric.py` — band interpretation removed; blanket `ACCEPTABLE`-on-
  deviation refused; both fail closed to NOT_APPLICABLE (→ D-3.5/UNRULED routes the
  deviation to a human). No other engine change.
- **Database:** none. The model already supports the whole intent.
- **API:** the frozen contract is **sufficient**. No endpoint added or changed.
  (`GET /document-versions/{id}` + `/evidence`, `POST .../document-versions`,
  per-review findings/report, contract-scoped conversations already carry everything.)
- **Frontend (freeze-compatible behavioral changes only):**
  1. "Upload a revised version" available in the workspace when a version exists
     (same `UploadDocument` component, quiet disclosure).
  2. Version selection: `?version=<id>` on the workspace; the existing "N versions"
     context text becomes the selector when N>1. Document pane + findings pane follow
     the selected version (findings per that version's Review — already keyed so).
  3. Honest Ask scoping: the assist lane answers about the LATEST version (verified:
     `_latest_document_version` in the router). Viewing an older version shows a plain
     note in the Ask pane instead of a form that would misattribute answers.

## K–L · Tests & documentation

Backend: band unit test rewritten; §24 regression tests added (band keys never
interpreted; no path — blanket or otherwise — maps a DEVIATION to ACCEPTABLE); e2e
bootstrap swap ripples through the specs that named the band in comments/assertions.
Frontend: unit tests for version selection; new journey spec (§23): upload → analyze →
report → findings → ask, and V1 → chat → V2 → both histories intact. Visual baselines
whose fixture chip changes (APPROVAL_REQUIRED → UNACCEPTABLE) are re-cut via the
CI-artifact process. Docs: this file; CHANGELOG; AUTO_MODE decisions; registry; status
documents; CLAUDE.md line-count and rule notes.

## M · Lock/decision impact

- **45B.9 (and the Step 20/35 band examples): superseded in FORM by AM-33** — the
  owner's 2026-08-31 product clarification is the authorization (§15). The Standard-vs-
  Rule separation 45B.9 exists to state is explicitly REAFFIRMED.
- Step 20's four-value Rule Outcome vocabulary: **unchanged** (locked; 45B.26). A
  vocabulary value being unreachable is not a vocabulary change.
- Zero-tolerance rule (2026-08-19/20): **unchanged and now the only expressible form.**
- AM-25…AM-32, REC-*, SEC-*, API freeze: untouched.

## N · Blockers (external, unchanged by this work)

Owner/legal inputs only: AM-31 Google terms + key; C-16 statutes + Evidence Act choice;
second document tranche / NORMATIVE corpus material (rule 21); production credential
provisioning. Nothing in this correction waits on any of them.

## O · Recommended (and implemented) architecture

Keep the locked lifecycle exactly as built — it is the owner's intent:

```
Contract ── DocumentVersion v1 ── Review(s) ── Findings/Report/Evidence   (immutable)
        └─ DocumentVersion v2 ── Review(s) ── Findings/Report/Evidence   (new, real)
Chat: contract-scoped conversation, retrieval strictly over the LATEST version's
      chunks; available the moment a version is indexed; never gated on findings.
Rules: blanket dispositions only (deviation_outcome / unlimited_outcome); anything
      else — band keys, ACCEPTABLE-on-deviation — fails closed to a human.
```
