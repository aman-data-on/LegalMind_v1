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

## 12. Backend build log (2026-11-04, backend agent, worktree `clm-p1`, uncommitted)

Lock record: **AB-161 `AM-307`** appended to `clm-records/all_lock.md` + a LOCKED_DECISIONS row (numbers scanned free on main, every worktree and every remote branch). Owner **and** lawyer confirm before real use.

| Slice | Built | Files |
|---|---|---|
| B1 | `layout.special_conditions {frame, precedence, position, pages, initials}`; `publish.pin_list` (body, annexures, then the frame) behind `library.pins`, `pinned_clauses`, the publish gate and `template_hash`; approving the frame re-pins it; `special_conditions.readiness` → `{ready, missing[{code,detail}]}` (NOT_CONFIGURED, FRAME_MISSING/NOT_APPROVED/INCOMPLETE, PRECEDENCE_NOT_PINNED/NOT_APPROVED, POSITION) on `GET /templates/{id}` and `/check`; DRAFT seed `config/templates/special_conditions/reference.json` (SC.FRAME, SC.PRECEDENCE; source kind `model`, label "For management approval — Reference text — not approved by Legal"); `tools.import_template --special-conditions KEY` / `attach_special_conditions` (DRAFT template only, precedence pinned last in the body) | `drafting/special_conditions.py` (new), `publish.py`, `library.py`, `tools/import_template.py`, `api/routers/templates.py` |
| B2 | `derive(changes, old_units, new_units, alignment, base_model, standard_text)` → entries/blockers; op table as §2; formatting/typography-only and "agreed = template" give none; clause-level replace keeps the clause heading; insert numbered `17.2A…`; ordered by target position, replace/delete before insert | `special_conditions.py` |
| B3 | `model.resolve(special=)` (key absent without entries — same model, same hash); synthetic anchors `<clause_key>~<n>` (bookmarked only when targeted); renderer `_special_conditions` (new section, no page restart, furniture label, optional initials line in that footer, `LM Schedule Title` / `LM Front` / numbered `LM Body 1` leads with `REF \w \h` / `LM Body 2` text, sdt `lm:special-conditions`, abstract num 13 only when used); `RENDERER_VERSION = lm-render-contract-2`; preflight round-trip of entries, a varied clause's quoted heading not an UNDEFINED_TERM, `SC_NEW_PAGE` on the PDF | `model.py`, `render_contract.py`, `preflight.py` |
| B4 | `GET /contracts/{id}/package`, `POST /contracts/{id}/package {expected_entries_sha256}`, `GET /document-versions/{id}/special-conditions`; gates `reply_open_points`/`_replied_in`/`client_version`/VersionFacts/execution read `reply_to or package_of` (`negotiation.answers`); `SC_TRACE`; audit `contract.package_prepared`; ContractDraft row; worker PDF; serializer `package {of_version_id, special_conditions}`; permission map; schema `PackageRequest` | `api/routers/negotiation.py`, `analysis/negotiation.py`, `serializers.py`, `schemas.py`, `permission_map.py`, `audit.py`, `contracts.py`, `execution.py` |
| B5 | `analysis/effective.py` `effective_clauses → (clauses, NONE|APPLIED|NOT_APPLIED, reason)`; callers: `run_analysis` (NOT_APPLIED → ANALYSIS_FAILED `special_conditions_unapplied`), `negotiation.changes` (both sides effective; NOT_APPLIED → raw, `special_conditions_not_applied`, every row HOLDER), `carry_acceptances`; `execution.compare` raw (`effective=False`) | `analysis/effective.py` (new), `service.py`, `negotiation.py`, `execution.py` |
| B6 | carry-forward on `package_of` (`carry_decisions`, `carry_acceptances`); evidence rows hashed in sorted order (a varied clause sits in the annexure); approved wording also matched with the other rows the Evaluation read | `workflow/decisions.py` |

**Tests.** `tests/drafting/test_special_conditions.py` (12): model/bytes unchanged without entries · section, anchors, REF bookmark, new section without page restart, initials · an unknown target refused · PDF (LibreOffice): new page, pages run on, preflight clean · derive table and fail-closed cases · reference frame DRAFT and readiness · end to end on the placeholder (dry run, STALE_PREVIEW, body = v1 row for row, schedules after, effective reading, trace with internal note, client returns the package unchanged → no change) · tampered trace → NOT_APPLIED → ANALYSIS_FAILED · another reader 404 · SC_TRACE · carry and gate on `package_of`. One existing test adapted (`/check` gains `special_conditions`). Byte-identical rendering without Special Conditions also verified once against HEAD `ca1d73ba`'s renderer (placeholder DOCX sha256 `9d8e1338…`); not pinned in CI (python-docx is unpinned).

**Golden run (local demo DB only, scratchpad `bin/golden_package.py`; DEMO template v12 by `bin/demo_special_conditions.py`, frame/precedence rows `SC_DEMO.*` labelled DEMO).** 17.2 six → twelve months, 8.5 seven → fifteen days, 19.4 Pune → Mumbai: changes FALLBACK (8.5, owner) · NEGATIVE (17.2: counsel's Legal Decision, then the owner accepts) · NEGATIVE (19.4: counsel writes our wording) → v3 with exactly 3 entries, preflight on the PDF clean (margin, xrefs, new page, page numbers 1–22 continuous); the engine reads the effective text; both decisions carried onto v3's Review (ACCEPT_DEVIATION, APPROVE_CUSTOMIZATION); the gate cleared once counsel decided INDEMNITY-MSA-001, an open point of the DEMO template itself; `/content` 200; Sign as is 201. Contracts in `legalmind_clm_demo`: `5b2315c4…` (package v3, signed-off), `484d552e…` (answered, package not prepared); files `/root/legalmind-clm-local/sc-golden/`.

**Deviations from the design, and why.**
- LIABILITY-MSA-001 reads **CONFLICT**, not "12 months MATCH", on the demo template: its 17.3 still carries the (d)/(e) carve-outs pending management (`AM-304`). That is the engine being right about the template, not the annexure.
- `op: add` (no anchor) is not produced: an addition before any clause of ours is CANNOT_EXPRESS. A clause holding a list, table or image cannot be *replaced* (its lettering would not survive as plain paragraphs), and a clause with sub-clauses cannot be replaced or deleted — both CANNOT_EXPRESS (fail closed). Next: structured entry blocks.
- SC_TRACE / SC_UNDECIDED are checked in the package endpoint (they need the DB), not in `preflight.check`; SC_UNDECIDED is the reply's `_reply_blockers` (code PACKAGE_NOT_READY). A "Worse for us" entry answered "use our standard" is exempt (our own text is no concession).
- The publish gate does not render a sample annexure; each package is preflighted when made.
- A sub-clause's heading in a lead is its run-in title, else its clause's title (Q-3 open).
- Not built: B7 later rounds (a package that went out and came back answers with LATER_ROUND), B8 amendments, `GET /contracts/{id}/effective`, change-row `target`/`in_package`.

**Round 2 (coordinator's PDF review, same day).** (1) Title "Annexure A — Special Conditions" (house caps), its label in that section's header. (2) Opening "These Special Conditions form an integral part of the {sc:agreement} dated {sc:date} between {sc:parties}. …" — new slots read the template's short title, its effective-date field and the parties' names; precedence sentence kept. (3) A lead names a sub-clause by its own run-in title only, else "Clause 8.5 is replaced by the following:" (the quoted heading dropped; the effective reading takes it as optional) — never the parent's heading. (4) An entry opening on the varied clause's run-in title keeps its underline (bold where the body's is). (5) `initials: true` closes the annexure with both parties' lines in the signature-table style (house `annexure_signature_rows`: By / Name / Initials or Signature / Date), kept with the last entry; the footer initials line and the frame's `initials` role are gone. (6) The precedence sentence is a new DRAFT version of the clause whose "Order of Precedence" sub-clause holds it (`attach_special_conditions(precedence_into=…)`, CLI `--precedence-into`), 21.3's entire-agreement words kept — not a clause 22 (that was only the fallback for a template with no such sub-clause, e.g. the placeholder). Demo template v13 (frame `SC_DEMO.FRAME@2`, 21.3 in `GENERAL_PROVISIONS@5`, DEMO labels); golden contract `a5c29584…` v3; PDF `/root/legalmind-clm-local/sc-golden/final.pdf` (22 pages, annexure p. 22, preflight and margin clean). Tests: 14 in `test_special_conditions.py`.

## 13. UI build log (2026-11-04, UI agent, worktree `clm-p1/frontend`, uncommitted)

One component at a time, `frontend-design` + `ui-ux-pro-max` loaded, existing tokens only (`--ws-*`), then
screenshots per person/state at 1440 and 390, then an independent critic (two rounds: U2–U5 together, then U1+U6).
Files: `components/workspace/Package.tsx` (new), `lib/package.ts` (new), `__tests__/package.test.tsx` (new, 16),
edits to `ChangesPane.tsx`, `WorkspacePage.tsx`, `SigningSheet.tsx`, `TemplateApproval.tsx`, `lib/{api,nextStep,
labels,types,changes,templates}.ts`, `changes.css` (one "final contract" block).

| # | Built | Notes |
|---|---|---|
| U3 | `PackageBar` under the Changes filter bar: "Final contract", one sentence (count, Annexure A, "Clause 22 says Annexure A wins"), Annexure A's entries as an `ol` (its own numbering) with the effect tag; blocked = each reason in words, a change's reason "Open the change". Header primary `preparePackage` "Prepare final contract" → confirm dialog ("This makes version N…", each entry's wording behind "Wording") → POST with `entries_sha256`; STALE_PREVIEW reloads the list and says so; PACKAGE_NOT_READY lists the reasons, removes the retry and links each change. Quiet "Prepare a reply with tracked changes instead" keeps the old route. Absent when the dry run names another route (NOTHING_TO_ANSWER, NOT_OUR_TEMPLATE, REDLINE_ROUND, LATER_ROUND, ROUND_CLOSED). | SC readiness codes said in words (`lib/package.ts` SAID); "The final contract cannot be prepared yet:" prefix dropped from the server's reason |
| U2 | "In the final contract: Entry 1 of Annexure A. Replaced with the client's wording." / "Can't be written into Annexure A. <reason>" / "No entry. Our wording stays." on the answer card | Derived from the dry run's `entries[].row_key` + `blockers[].row_key`, or once prepared from `/special-conditions` `trace[].row_key`. No backend `target`/`in_package` needed |
| U4 | `PackageCard` on the Document tab (a `ws-replynote`, `h2` title): what the version is, Word/PDF via `ReplyDownloads` (202 "Preparing the PDF…", 503 said), held while the stage is not Ready to send/sign. Header primary `sendForSignature` "Send for signature" (`SendOut`, then "Sent for signature on …"); at Ready to sign it comes before "Mark signed" | Who may send is the server's `can_send` (counsel holds it on the demo contract) |
| U5 | `SpecialConditionsTrace` inside the card, read on open: per entry who answered, when, "Agreed by a Legal Decision", "Reason, kept in LegalMind", the client note, the internal note with a lock ONLY when the key arrives | Decisions are not linked: no decision page exists |
| U1 | `SpecialConditionsSetup` group on Template approval (draft and published): "Set up." / "Not set up. Agreed changes go back … It does not stop publishing. An administrator sets it up when the template is imported; it cannot be set up from this page yet." + missing items in words | Lead/admin gets 404 on a draft template, so U1 is the lawyer's |
| U6 | Signing sheet: "Upload the copy both sides signed, including Annexure A with its N Special Conditions. It is compared with version N, the final contract…"; Changes banner (warn rule) when `special_conditions_not_applied` | |
| U7 | Skipped — backend B8 (amendments) not built | |
| U8 | Skipped — `GET /templates` rows carry no `special_conditions`; one detail call per row was not worth it. Needs the field on the list | |

Critic findings declined, with reason: "agreed" while a review point is open (the changes are agreed; the point is
the final version's own review); counsel's "Send for signature" (server's `can_send`); list rows still showing the
analysis word after a decision (Changes row logic, out of scope); decision links and "Prepared by" (no API field);
the double space in "Download  Word" and the pale busy label (shared `ReplyDownloads`, every PDF button).
Screenshots: scratchpad `ui-build/shots/{owner,counsel}-{1440,390}-u{1..6}-<state>.png` (states mocked by route
interception for 202, 503, STALE_PREVIEW, PACKAGE_NOT_READY, preparing, sent, not-applied — the demo DB was not
written). Checks: tsc clean; vitest 72 files / 830 passed; `npm run lint` (terms, hooks, baseline: no file worse).

**PR #287 browser tests (CI job 10, 40 of 172 failing).** Reproduced locally (40/40, own DB `legalmind_clm_uie2e`,
API :8599, web :3599), then fixed to the redesigned screens: full local run **168 passed, 0 failed, 16 skipped**
(2 of the skips are the `fixme`s below). Product fixes made on the way (frontend only): the upload lands on
`/contracts/{id}` (was `/dashboard?id=`), the contract page drops the duplicate `?id=` the old redirect carries,
and the declared effective date is back in the record header ("Effective 28 Jul 2026", removed by mistake in the
CLM header). Spec changes, by cause:
- `/contracts` is the app now (AM-262/263): `support.openUploadPanel` picks "Upload a contract" in the New contract
  chooser; new `openUploadNewVersion` (⋯ → menu item) used by journey, revision-upload, version-comparison; URL
  waits/regexes and row hrefs in workspace, workspace-panes, journey, legal-area, counterparty, reviews; "legacy
  link" checks now mean `/contracts?`, `/dashboard?id=` and `/reviews`; workspace "login lands on" → `/contracts`,
  home heading "My contracts".
- Page 2 card and pane: stage header gone → the card's "Needs Legal — not sent yet" and the "Open point N" filter
  (analysis, gating, journey, review-workflow); filters are the legend's four marks (journey); the quote is on the
  card face + "View in document" (workspace slice 2, journey); card facts `[]` / `["our standard"]`, polled because
  "Contract" shows until the case loads (confidentiality); the requirement code is Legal details only — the owner
  test now asserts the name on the card and the code absent (analysis); the readiness footer was cut — asserted
  absent (workspace); outline mark aria-label "Open point" (workspace).
- Summary: tiles are Legal details → "What needs attention", `.ws-attn__count`, open points list, path via the
  point's "View in document" (workspace 3-column); viewports measure the side card's heading and open points
  instead of tiles; review-workflow reads the stage from Legal details (counsel) and `.ws-attn__count` (owner).
- Locators: "Reason" by role (label text includes the textarea's value), searchbox role, record header `.ws-record`,
  notifications "No notifications" or real items + "Open your to-do", contracts home row → "1 open point" in words.
- Server rule `AM-298` r1: client-profiles files v3 as signed before v2 is declared the client's (same three roles).
- Phone layout: below the three-pane width the page scrolls by design — the y-scroll rule now applies to three-pane
  only (workspace-panes small).
- **`test.fixme`, for the owner:** review-loop "a clause carries the way back to the finding" (Page 2 removed the
  in-text analysis strip and nothing replaced the clause → finding link) and lifecycle "declared state read back"
  (the header shows the deal stage, and no screen shows the declared Draft/Active any more). Both are product gaps.

**Visual baselines (job 15).** Not re-cut locally. Locators fixed so every shot is reached (workspace waits for ⋯,
mask `.ws-record h1`; the documents landing is counsel's "For my review" home, masked on `.ws-hq__doc`/`__since`).
Locally 9 shots now differ by pixels only (workspace, documents, reviews, report, legal, ask conversation, research,
admin, audit — nav gained To-do/Templates/Standards, the record header, the home). The CI update needs: push, let
job 15 fail once, download `visual-regression-diffs`, crop every diff band of each `*-actual.png` against the
baseline (0.001 = 1152 px hides a real element), then commit the actuals as baselines and name the drifts absorbed.
`ws-documents.png` is a new composition (counsel's home), so it has no prior render to disagree with — check it by eye.
