# CLM R&D — 11 · Special Conditions annexure: system design

`📁 PROPOSAL` 2026-11-04 · design only; amends no lock by itself. Sources: 10 (R-1…R-12, Q-1…Q-9), 06–09, code in `clm-p1` (migration head `a8d4c2e6f1b9`). Written by the system-design agent; saved verbatim in substance.

## 0. Starting points (traced)
- Answers are append-only `comparison_choices` rows (`api/routers/negotiation.answer_change` → `document_comparison.write_choices`): `choice` ours/theirs/standard/custom, `wording`, `wording_sha256`, `clause_version_id`, `client_note`, `internal_note`, `reason`, `decided_by`, `version_number`; history via `negotiation.answer_lines`.
- `negotiation.changes(before, after)` rows keyed `N|KIND|<ours>|<theirs>`, with `clause.number`, before/after, `route`, `effect_for_us` (POSITIVE/NEUTRAL/FALLBACK/NEGATIVE, AM-306).
- "Write our wording" = APPROVE_CUSTOMIZATION decision tagged `[our wording sha256:…]` (`workflow/decisions.wording_tag`).
- Generation: `drafts.create_from_draft` → `model.resolve` → `render_contract.render` → `preflight.check` → `ingest_document` → `ContractDraft` (values, model_hash, renderer_version); worker PDF (`dispatch_pdf`, LibreOffice, `pdf.convert_contract` + `preflight.pdf_problems`).
- `model.resolve` numbers clauses and keyed sub-clauses (`r.numbers`); unkeyed sub-clauses have no bookmark. Schedules call `render_contract.restart_pages`.
- Reply path `prepare_reply`; gates `_reply_blockers`, `reply_open_points` (AM-293), `_require_decided`; `carry_decisions`/`carry_acceptances` key on `doc_metadata.reply_to`.
- `execution.agreed()` = latest non-signed version; `execution.compare` = `negotiation.changes(agreed, signed)`.
- AM-267 (`governed_by`) locked but not built.

## 1. Lifecycle on `domain/deal_stage.py` (no new stage)
| Step | Fact | Stage |
|---|---|---|
| Create from template | v1 COMPANY_DRAFT + ContractDraft | DRAFTING |
| Send | `sent_at` | WITH_CLIENT |
| Client returns (docx/pdf/scan) | CLIENT_MODIFIED | CLIENT_RETURNED |
| Answers | `comparison_choices` | CLIENT_RETURNED |
| **Prepare final contract** | new COMPANY_DRAFT, `doc_metadata.package_of`, own ContractDraft | INTERNAL_REVIEW → READY_TO_SEND when its Review has nothing undecided |
| Contract decision "Sign as is" | `contract_outcomes` | READY_TO_SIGN |
| Stamp/authority/signed copy/Mark signed | executions, FINAL_SIGNED | SIGNED |
| Client edits the package | CLIENT_MODIFIED | CLIENT_RETURNED (next round) |
| Change after signing | AMENDMENT contract, `governed_by_contract_id` | own stages; parent SIGNED |

`api/routers/contracts.py` VersionFacts: `reply_to=bool(meta.get("reply_to") or meta.get("package_of"))`.

## 2. Data model — derived, not stored
Agreed text of clause T = latest answer on a row targeting T (this round) → else previous package's agreed text → else template text. An entry exists only if agreed ≠ template (after `dc._norm` + typography), so formatting-only gives no entry.

Entry: `n`, `target {key, number, heading}` (key = clause/sub-clause key or synthetic `"<clause_key>~<number>"`), `op` replace | delete | insert_after (17.2A…) | add, `text` verbatim (client evidence minus its leading number, or `wording`, or `clause_text(cv)`; never parsed for slots).

| Answer | Entry |
|---|---|
| keep_ours | none |
| accept_theirs | client text (delete if DELETED row) |
| write_wording | `wording` |
| use_standard | `clause_text` (none if = body) |
MOVED / NEW_ANNEXURE / front-matter rows → blocker CANNOT_EXPRESS ("keep ours, or reply with tracked changes").

Row → target: before-side `unit.number` against the base model `model.resolve(template_dict(tv), clauses, ContractDraft.values)`; its hash must equal v1's `model_hash` (proves the body is untouched).

Internal trace (SEC-07) in `doc_metadata.special_conditions`: ids/hashes only `{n, target_key, op, choice_id, choice_version, text_sha256, effect, decision_ids[], holder_answer_audit_id?}`; never serialised by `declared_metadata`; who/reason/notes joined at read time.

Client model: `model["special_conditions"] = {title, opening, entries:[{n, op, lead_runs, blocks}], initials?, position}` — key present only with entries (existing hashes unchanged). Order: document position of target, then delete/replace before insert/add. Deterministic.

No new table. Amendments: `contracts.governed_by_contract_id` + trigger (AM-267/AM-279).

## 3. Generation (`drafting/special_conditions.py` new + `model.py` + `render_contract.py`)
- Template config `layout.special_conditions = {frame:{clause_key, version}, precedence:"<clause_key>", position:"after_execution"|"before_execution", pages:"continue", initials:bool}`. Frame is a ClauseVersion whose `p` blocks carry roles title/opening/op.replace/op.delete/op.insert_after/op.add/initials; slots `{sc:target}` `{sc:heading}` `{sc:new_number}` `{sc:template}` + template variables. `library.pins()` yields the frame pin (approval, template_hash, Template approval page cover it). Never rendered as body.
- `model.resolve(..., special=None)` builds the section with the same `_Resolver`; synthetic anchors for unkeyed sub-clauses in `self.anchors` (not `numbers`).
- `render_contract._special_conditions(b, sc)` after (or before) `_execution`: new section NEW_PAGE without `restart_pages`; furniture label "<short title> — <title>"; initials line in that section's footer when set; styles `LM Schedule Title`, `LM Front`, numbered entries with new abstract num `_ENTRIES = 13`; lead "Clause REF _LM_<target> \w \h “Heading” is replaced by the following:" + `LM Body 2` text; wrapped in sdt `lm:special-conditions`; bookmarks on unkeyed sub-clauses only when targeted. Bytes without special conditions identical (test). `RENDERER_VERSION = "lm-render-contract-2"`.
- Preflight: numbering round-trip `lm:special-conditions → 1,2,…`; REF_NO_BOOKMARK; new `SC_TRACE` (every entry has a choice; every NEGATIVE entry has an effective Legal Decision or AM-281 holder answer, R-12); new `SC_UNDECIDED` (reuse `_reply_blockers`); BLANK/UNDEFINED_TERM on client text; PDF: MARGIN, XREF_PDF, EXECUTION_SPLIT, one continuous PAGE_NUMBERS run, new `SC_NEW_PAGE`. Clean DOCX, worker PDF only (AM-293 r2).

## 4. Engine — the effective contract (`analysis/effective.py` new)
`effective_clauses(db, version_id) -> (clauses, status)` NONE | APPLIED | NOT_APPLIED(reason).
- Frame: version's own `package_of` template → latest earlier package in the contract → parent (amendment) → NONE (raw). Third-party paper unaffected; golden corpus unchanged.
- Read: find frame title row; lead sentences matched by regexes from the approved `op.*` phrases; text rows to the next lead.
- Validate: target number exists, heading matches, precedence clause present (hash); on our generated file count/targets/`text_sha256` = `doc_metadata.special_conditions`.
- Apply: drop target unit rows, insert entry rows with section number/title = target, real evidence ids kept; frame/opening/lead rows dropped. Amendment base = parent effective FINAL_SIGNED + earlier signed amendments.

| Caller | Behaviour |
|---|---|
| `analysis/service.run_analysis` | uses effective clauses; NOT_APPLIED → refuse `special_conditions_unapplied` |
| `negotiation.changes` | NOT_APPLIED → raw + banner `special_conditions_not_applied`, all rows HOLDER |
| `carry_acceptances` | effective text |
| `execution.compare` | raw vs raw |
| `reply_plan` | raw |

## 5. Precedence (R-3)
`layout.special_conditions.precedence` names a pinned body clause (new version of MSA 21.3). Generation blocked (PRECEDENCE_NOT_APPROVED) unless that version and the frame are APPROVED and the template PUBLISHED. Seed: DRAFT clause, source `{kind:"model", label:"For management approval"}`, modelled on Constitution §31.12 ("prevails only as to the specific terms it amends; all other original terms remain unchanged") and BHEL ATC ("…shall supersede those in GTC"); never seeded APPROVED; label "Reference text — not approved by Legal". Lawyer must also resolve the executed MSA §24.10 conflict (Q-1) before a real publish.

## 6. Amendments
`POST /contracts/{id}/amendments` → AMENDMENT contract, same counterparty, `governed_by_contract_id` = parent; trigger: parent SIGNED, parent not an AMENDMENT, same counterparty. v1 = parent effective text; same Changes flow; "Prepare amendment" needs a published AMENDMENT template (none → blocked, rule 21). Own Review, execution, stamp (R-11). Parent page shows current value beside the original (R-9).

## 7. Gates, audit, permissions, client paper
- `reply_open_points` generalised to `reply_to` or `package_of` (409 on /content, /pdf, mark_sent until cleared). `_replied_in` matches `package_of`: re-answering a closed round → 409 (new round needed, R-7).
- Audit `contract.package_prepared` {version, package_of, model_hash, renderer, [n, target_key, op, choice_id, text_sha256]} (no notes); `contract.amendment_created`.
- Generate: `contract_negotiable` + CONTRACT_UPDATE. Trace: `document.view`; internal note/position: `legal_position.view` only, key omitted. Frame/precedence: template approvers (AM-283). Amendment: CONTRACT_CREATE + parent readable.
- Package offered only when our side is a ContractDraft (v1 or earlier package); client paper (AM-290), blank template (AM-302) or a sent tracked-changes round → NOT_OUR_TEMPLATE / REDLINE_ROUND, `prepare_reply` remains. Both buttons when both possible.

## 8. API and UI
API: `GET /contracts/{id}/package` (dry run: available, blockers[{code,message,row_key?}], entries, precedence{clause_key,number,approved}, entries_sha256) · `POST /contracts/{id}/package {expected_entries_sha256}` → 201 {document_version, review_id, entries, downloads, open_points}; 409 STALE_PREVIEW / PACKAGE_NOT_READY · `GET /document-versions/{id}/special-conditions` {entries, trace?} · change rows gain `target`, `in_package` (replace/delete/insert/none/cannot) · `/templates/{id}` + `/check` gain `special_conditions {ready, missing[]}` · `POST /contracts/{id}/amendments` · `GET /contracts/{id}` gains `governed_by`, `amendments[]` · `GET /contracts/{id}/effective`. Schemas `PackageRequest`, `AmendmentCreate`.

UI (one component at a time):
| # | Component | Who |
|---|---|---|
| U1 | `SpecialConditionsSetup` in TemplateApproval.tsx — frame + precedence status, "For management approval" | lawyer, Lead |
| U2 | ChangesPane row line "In the final contract: replaced in Annexure A / no entry / can't be expressed" | all |
| U3 | `PackageBar` beside ReplyBar — dry-run list, blockers via GateList, "Prepare final contract"; nextStep `preparePackage`/`sendForSignature` | sales, lawyer |
| U4 | `PackageCard` on Contract page — downloads, SendOut "Send for signature" | sales |
| U5 | `SpecialConditionsTrace` — who, effect, decision link | lawyer; sales without notes |
| U6 | SigningSheet note "Agreed package vN (Special Conditions: 3)"; banner `special_conditions_not_applied` | sales, lawyer |
| U7 | `GovernedByLink`, `AmendmentsPanel`, "Start an amendment" | sales, Lead |
| U8 | TemplateList badge "Special Conditions ready / needs precedence" | Lead |

## 9. Lock records
Amend: AM-251 r1 (a generated file may carry a Special Conditions part built only from AM-251's own inputs; body = pinned template text) · AM-293 r1 (gates cover `package_of`) · AM-299 r3 + AM-284 r2 (carry onto the package's Review; effective text) · AM-260 r1 (package counted as our prepared version) · AM-267 r1 (built now; parent SIGNED, never an amendment) · AM-305 (note). New: AM-307 "Special Conditions annexure and the effective contract" (R-1, R-2, R-4…R-8, R-12; fail-closed reading; precedence gate under Constitution §8.2) — changes what Findings read, so owner **and** lawyer must confirm before real use. Not amended: rules 7/21 (frame, op wording, precedence from the lawyer), rule 18/SEC-07, append-only audit, zero tolerance (NEGATIVE entries need a Legal Decision), Gemini cost guard (no model call).

## 10. Work breakdown
Backend: **B1** frame/precedence config (`library.pins`, `tools/import_template.py`, readiness, DRAFT seed) · **B2** `special_conditions.derive` (op table, formatting→none, MOVED→CANNOT_EXPRESS, order, body-hash check) · **B3** `resolve(special=)` + renderer + preflight SC_* (identical bytes without; new page; continuous pages; round-trip; REF; LibreOffice PDF passes) · **B4** package endpoints, gates, audit, ContractDraft row, dispatch_pdf (409s; no trace keys without right) · **B5** `analysis/effective.py` + callers (golden corpus + Diff-Talk unchanged; tampered entry → ANALYSIS_FAILED; raw signed-copy compare) · **B6** carry-forward on `package_of` + golden E2E: 17.2 12 months (Fallback, owner), 8.5 15 days (Fallback), 19.4 Pune→Mumbai (Worse, lawyer Write our wording) → v3 with exactly 3 entries, body = v1, PDF clean/new page/xrefs 8.5/17.2/19.4, engine reads 12 months MATCH, 15 days favourable, Mumbai seat; gate clears; Sign as is → Mark signed · **B7** later rounds · **B8** amendments.
UI: U1 → U8, each with vitest; U3/U4 Playwright on :3399.

## 11. Risks / open questions
Q-1…Q-5 block a real publish (precedence wording vs executed §24.10, name, deletion wording, opening, position/initials; 17.2A vs next number). Contracts on templates without precedence never get a package. A deal that sent a tracked-changes reply stays on that path (owner ruling). Client edits to frame/precedence → NOT_APPLIED → person. `precedence_signals` (`_MSA_WINS`) may read our new clause — test. Client text with undefined quoted terms or `{` blocks preflight (lawyer supplies wording). OCR of scans may fail → fail closed. Amendment stamp article (Q-6), restatement after N amendments (Q-9) open. No side letters (R-10).
