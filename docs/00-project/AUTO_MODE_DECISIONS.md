# AUTO-mode decision log — admin/standards API, 2026-08-19

**Status: 📁 RECORD.** Owner approved AUTO mode for the 5-unit plan (import tool ·
read paths · update-as-append · config audit events · tests/records) with these
rulings re-confirmed at kickoff:

* **MSA standard = 6 months / affected-service fees** (this morning's Q1 stands; the
  "12 months from C-01" line in the tasking message does not).
* **JSONB, no migration** (Q2=A stands; no `clause_standards` table, no C-13 resolution).
* **In-place editing is replaced by append-a-new-version with a mandatory reason**
  (locked rule 16); rollback = appending a version carrying the old values.

Every decision taken autonomously below is logged as: what · why · what it does NOT decide.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 1 | Requirement **detail** returns configuration values and `created_by`; the **list** stays values-free | The detail view is the admin read path; N values × M requirements would bloat every list load | Nothing about who may hold `configuration.view` |
| 2 | Legal Rule values are returned under `configuration.view` | Both roles holding it (Legal Reviewer, Legal Admin) also hold `legal.position.view`, so LEGAL-02 is not widened | No new permission; no change to the confidential surface elsewhere |
| 3 | Audit events carry **ids, version numbers and the reason — never configuration values** | 53.3: a standard value can encode a confidential legal position; the trail must not leak what the API gates | Values remain reachable through the gated version rows the event names |
| 4 | `POST /requirements/{id}/standard` refuses an untyped replacement **at save time** | Same gate publish applies, surfaced earlier — an admin should hear about it when saving, not at publish | Publish keeps its own check (defence in depth) |
| 5 | The standard-update endpoint requires a mandatory `reason` | A standard change is a legal-position change; "why" belongs in the trail | Nothing decides what reasons are acceptable |
| 6 | Import tool marks source `RATIFIED_CONFIG` provenance (file, clause, date) — **not** `RESOLVED_CONFLICT` | The owner's C-01–C-23 register was never supplied (Q1=B); citing it would fabricate provenance | The register can be imported later under its own namespace |
| 7 | Import tool creates **draft-only** Requirements when a file carries no mapping/evaluation rules, and reports them unpublishable | 35.9 fixes no threshold; inventing mapping rules here would put a number nobody chose into every Review | The owner may supply rules later; publish stays refused until then |
| 8 | The tool never publishes; it reports what a publish would cover | Publishing is a Legal-permission, audited API action; a CLI bypassing `configuration.publish` would evade both the permission and the audit trail | — |
| 9 | Permission for the new endpoint: `configuration.draft` | It drafts a version — identical consequence to the existing version endpoint; a new permission would change the locked catalogue (27) | — |

**Verification at close: 632 passed · ruff/mypy clean · determinism byte-identical ×2 · 4× concurrent suites green · `all_lock.md` untouched (md5 7aee32af…).**


## Clause-catalogue expansion, 2026-08-19 (owner instruction: review ALL clauses)

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 10 | Positions extracted ONLY from LeapSwitch documents, clause-cited; the located conflict register used as corroboration only | Its own tracker marks C-01/04/05/07/23 "Needs owner decision" — an unresolved register cannot source a ratified position; the manager's whatever-is-stated rule makes the documents authoritative | The register's cross-document unification items stay management decisions |
| 11 | 13 Requirements now; uptime %-tiers, categorical-value comparison (governing-law VALUE), and every NDA Requirement deferred | Uptime is per-service multi-scope (modelling decision); categorical comparison needs a new evaluator type (enum change, outside IMPL-01); no LeapSwitch NDA template exists | Nothing — each is recorded in CLAUSE_CATALOGUE.md gaps |
| 12 | Presence Requirements verify the clause EXISTS; its value goes to Legal with evidence | Asserting "India is present" via keyword mapping would be value comparison smuggled through presence — a silent guess (ENG-09) | What a categorical evaluator looks like (V2) |
| 13 | `deviation_outcome` checked BEFORE threshold keys; invalid value → NOT_APPLICABLE + human | A blanket disposition and a band in one rule contradict; the blanket is the stated policy. Misconfiguration is never permission to guess | Nothing narrows: every path still reaches a human or a configured outcome |
| 14 | New standards import as draft-only (no mapping/extraction terminology invented) | 35.9 fixes no threshold; publishable only when terminology is supplied per Requirement | The terminology itself — unstarted configuration work |
| 15 | P-01 closed by the first real presence fixture; P-02/R-14 → UNSTARTED; P-05 stays blocked on an owner OPTIONAL declaration | The catalogue supersession changed their premises; statuses now match reality | Which clause, if any, is OPTIONAL |

| 16 | NDA baseline = the executed NDA, per owner designation 2026-08-19, standards scoped to the RECEIVING-party direction with the caveat recorded in every file | The owner overrode my "counterparty paper" classification with direct knowledge; the manager's whatever-is-stated rule plus the designation make it authoritative. My earlier reasoning (one-way obligations against LeapSwitch) is preserved in the changelog as the reason the caveat exists | What LeapSwitch's DISCLOSING-party NDA position is — undefined until such a document exists |

| 17 | 54.6's "never enter the repository" re-enforced as VERSION CONTROL (gitignore + zero-tracked + no-copies), replacing the outside-working-tree assertion | Owner ruling 2026-08-19 places the docs at `legal-docs/` in-project; gitignored files are untouchable by `git add -A`, and the tracked-files check catches a force-add | 54.6 itself — untouched; only my earlier stricter interpretation was owner-overridden |

**Verification at close: 647 passed · 45 corpus fixtures · ruff/mypy clean · determinism ×2 identical · `all_lock.md` untouched.**


## Terminology supply, 2026-08-19 (owner tasking: make the 19 new Requirements publishable)

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 18 | Mapping/extraction terminology authored into ALL 21 ratified files (the 2 liability files carried none either); every term drawn from the cited clause's own wording or the clause type's generic name; `confirm_threshold` 5, labeled STRUCTURAL | The owner's tasking supplies the authorization decision #14 was waiting on; with 35.8 default weights one exact phrase confirms, matching every structural precedent in the tree | A calibrated threshold — 35.10's calibration against a representative counterparty set stays outstanding, and recalibration is a new mapping rule version (data, not code) |
| 19 | Extractor reads the `twelve (12) months` drafting convention (optional `)` between digits and unit), and `units` may map canonical key → clause terms, mirroring `bases` | Every source clause writes magnitudes this way, and strict unit equality (45C.23) needs a configured canonical key — the alternative was case-folding in the evaluator or respelling ratified files and fixtures | No unit equivalence not explicitly configured; word-only magnitudes ("six months") still yield UNKNOWN, never a value (44.24) |
| 20 | Clause-specific unit anchors for CURE-PERIOD-MSA (`days after receipt of written notice`), DATA-PURGE-MSA (`days of termination`), DATA-RETRIEVAL-TOS (`days following termination`, `days, after which`) | PDF parsing yields page-level segments spanning several sections; a generic `days` term read a *neighbouring* section's number (3 for 30, 30 for 15, the FM 60 for 7). Caught by verification against the real documents, not by review | Segmentation granularity — ingestion is untouched; a finer segmenter would be its own reviewed change |
| 21 | `evaluation_rules` = a minimal `{"evaluator": …}` payload | The publish gate requires the row (42.12) but the V1 evaluators read comparison semantics from code (44.29) and disposition from the Legal Rule; inventing parameters here would be ENG-09 | What a future evaluator's parameters look like |
| 22 | `tools/verify_terminology.py` — parses the real gitignored documents, requires each Requirement to reproduce its ratified position from the document it cites; SKIPs when documents are absent | 54.6 keeps the documents out of every test, so only a tool run where they live can close this loop. It found 3 real defects on first pass (#20) | Nothing about VERIFIED state — this is configuration verification, not 35.10 calibration and not third-party verification |

**Verification at close: 658 passed · ruff/mypy clean · verify_terminology 21/21 PASS, byte-identical ×2 · `all_lock.md` untouched at 15,358 lines.**


## Admin UI on the standards API, 2026-08-19

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 23 | The detail response is fetched **per Requirement on expand**, not for every row of the list | Decision #1 kept the list values-free on purpose; fetching N detail responses to render a list would undo that | Nothing about pagination or caching strategy |
| 24 | One control for "change" and "restore", both posting to the append-only standard endpoint pre-filled from the chosen version | Locked rule 16 makes them the *same* operation; a separate rollback button would imply a distinct mechanism that does not exist | What values are acceptable — the admin supplies them (rule 21) |
| 25 | `ValueCell` exported from the page module so the 52.4 test renders the REAL component | A test harness reproducing the component would assert a copy and pass while the page regressed | Nothing about component structure elsewhere |
| 26 | The 52.4 assertion compares withheld and never-existed renderings for **byte identity**, rather than checking for absent strings only | Identity is the actual guarantee: a viewer must not be able to infer that a position exists but was withheld. Absent-string checks would pass on a layout that leaked the distinction structurally | Whether a Legal Rule exists for any Requirement |

**Verification at close: 659 backend (incl. an end-to-end test importing all 21 ratified files and publishing them through the real gated endpoint) · 58 frontend · 26 Playwright · ruff/mypy/tsc clean · verify_terminology 21/21 PASS · reproducibility gate PASS · invariants 9 PASS 2 SKIP (broker/log checks need services) · `all_lock.md` untouched at 15,358 lines.**


## Counterparty test-specimen tranche, 2026-08-20 (owner tasking: find counterparty documents)

Eight public documents assembled at `/root/legalmind-source-material/second-tranche/`
(outside the working tree; manifest with URLs and pattern mapping in its README.md):
six selected from the pre-existing public-web captures at `/root/LegalMind/corpus/pdf/`
(AWS, Google Cloud, Microsoft, CtrlS, NxtGen, ESDS) and two downloaded (NYC-DOH Cloud
Services Agreement 2024 — customer-drafted; Common Paper Mutual NDA v1, CC BY 4.0).
All under the owner's 2026-08-18 test-only exception: **test specimens only, never v1
source material, never a source of any standard, rule or threshold.** The executed-NDA
file in that folder names a real counterparty and was excluded.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 27 | The still-blocked corpus cases stay BLOCKED: L-03, L-04, L-09, L-10, L-17, L-22, L-29a/b have **no specimen in public vendor paper** — vendors do not draft per-claim/per-event/>12-month/affirmatively-unlimited caps against themselves | Encoding a near-miss (e.g. OVH's 18-month limitation *period*, or NYC's 48×-average formula) as one of these patterns would fabricate a finding — the exact L-03 trap the coverage register warns about | The second-tranche request in SOURCE_MATERIAL_INTAKE.md §8.5 stands for those patterns (negotiated/counterparty-drafted paper); L-13 remains blocked on the owner's scope ruling, not on documents |
| 28 | A report-only probe ran the published liability terminology over all 8 specimens; results recorded, **no terminology changed and no fixture authored from the probe** | Every outcome fails closed (UNRESOLVED/UNKNOWN/MISSING/UNABLE — no false MATCH, nothing auto-approved). The 4 findings (will-vs-shall "not exceed"; "is limited to" unphrased; a carve-out matching an unlimited phrase on CtrlS — the L-29 hazard live; NYC's 12-month lookback read without a basis) are 35.10 **calibration inputs**, and calibration is a reviewed data change, not a silent edit | The calibration itself — a new mapping-rule version against this representative set, done deliberately |

**Verification at close: 659 backend passed · all 8 specimens parse (7 COMPLETE, CtrlS PARTIAL: image-only last page, no OCR) · repository unchanged except this record · `all_lock.md` untouched at 15,358 lines.**


## Comparability analysis, 2026-08-19

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 18 | `basis` now encodes the **measurement anchor**, not the topic: `CONFIDENTIALITY_SURVIVAL` → `…_POST_TERMINATION` (MSA) and `…_POST_TERMINATION_OR_RELATIONSHIP_END` (NDA), extraction terminology aligned | A counterparty MSA reading "three years **from the date of disclosure**" would have registered a false MATCH on the number 3 (45B.4). A false MATCH is the worst failure class here: it tells Legal there is nothing to look at | Whether any two anchors are ever comparable — they are not, and no conversion rule was added |
| 19 | C-07 ("3yr MSA vs 2yr NDA") recorded as **dissolved, not reconciled** | The clauses differ in trigger, definitional gate, direction, anchor and trade-secret treatment; they were never the same question, so there is no number to standardize | The register's other items — still management decisions |
| 20 | MSA §1.8/§1.9 blank cross-references, and TOS §22's US/European law carve-out, **reported not fixed** | Amending a template and re-scoping governing law are owner decisions; the defects are recorded where a reader will meet them | Nothing — both are surfaced for the owner |

**Verification at close: 659 passed · `verify_terminology` 21 PASS / 0 FAIL · ruff clean · `all_lock.md` untouched.**


## MSA.pdf cross-reference repair, 2026-08-19

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 21 | Verified both targets in the document before writing them (§12.1 defines "Confidential Information"; §18.1 defines "Force Majeure Event") | Writing an instructed clause number without checking would have risked replacing one defect with a wrong-but-authoritative-looking reference | Nothing — both were confirmed correct as instructed |
| 22 | **Discarded** the redaction+insert_text approach in favour of an inline content-stream splice through the font's Identity-H `ToUnicode` CMap | The first approach appended the text to the end of the content stream, so the project's own parser read *"Clause ␣ of this Agreement"* — a silently missing cross-reference, which is worse than a visible `___` | Nothing about the parser; the document was fixed to suit it, not the reverse |
| 23 | §1.4's blank (*"banks at ___________are open"*) left untouched and reported | It requires a **city** — substantive legal content no supplied document states (rule 21). Filling it would manufacture a legal term | Which city governs banking days — owner/counsel input |
| 24 | Reported that the source Word/Docs file still holds all three blanks and will regenerate them on the next export | A PDF patch is a final-form repair and does not propagate upstream; saying otherwise would leave the owner believing the template is fixed | Whether to amend the source file — owner's call, with counsel |

**Verification at close: 659 passed · `verify_terminology` 21 PASS / 0 FAIL · 21 pages · text length unchanged · only `___`→`12.1` and `_____`→`18.1` differ · `all_lock.md` untouched.**


## Legal Rule wiring + SLA scope ruling, 2026-08-20 (owner approvals)

Owner decisions received 2026-08-20: **(1)** the zero-tolerance Legal Rule is APPROVED —
wire it ("har deviation jo standard se match nahi karti → Legal team review");
**(2)** L-13 is ruled **NOT APPLICABLE** — service credits are a remedy, not a liability
cap; **(3)** the 5 missing corpus patterns stay blocked until the owner supplies
negotiated/customer-drafted paper; **(4)** EXTRA detection (Q13) is Phase 3.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 29 | The approved rule is expressed with the EXISTING tested keys — `deviation_outcome` + `unlimited_outcome`, both `UNACCEPTABLE` — attached to all 21 ratified files and imported as a `LegalRuleVersion` (rule_type THRESHOLD/PRESENCE by evaluator); the import tool and the corpus loader refuse any other rule | UNLIMITED is a DEVIATION under the ruling, and the unlimited branch reads its own key; two keys express "any deviation" exactly, with zero new engine vocabulary. Refusing everything else keeps "no tolerance exists" mechanically true | Nothing adds a threshold key anywhere; L-28's precedence_rule remains a separate undecided configuration |
| 30 | Numeric MATCH keeps `rule_outcome NOT_APPLICABLE` (requires no decision) while presence MATCH keeps ACCEPTABLE-with-rule — both pre-existing, both pinned by tests and 4 STRUCTURAL fixtures | The approval's operative demand is deviation → UNACCEPTABLE → Legal; MATCH routing is identical under either label, and relabelling numeric MATCH would change 4 structural corpus expectations nobody asked to change | Whether the MATCH label should read ACCEPTABLE for numeric under the rule — flagged for the owner only if the label ever matters downstream |
| 31 | Presence CONFIRMED-but-DEVIATION (expected ABSENT) hardened to read `deviation_outcome`, never inheriting MATCH's ACCEPTABLE | Latent path — no ratified standard expects ABSENT — but under the approved rule it would have auto-accepted a deviation, the one thing the policy forbids; fixed while wiring, with tests | No standard expecting ABSENT exists; none was created |
| 32 | Corpus expectation changes limited to CP-LIAB-01 and STD-LIAB-03 (DEVIATION outcomes → UNACCEPTABLE under the pinned approved rule); DOC-LIAB-05/07 stay NOT_APPLICABLE on the no-rule path, which Step 20 r4 keeps legitimate | The owner's "wire it in" is the approval rule 6 requires for these expectation changes; the no-rule fixtures still pin the fail-closed path that survives (UNRULED_DEVIATION_REQUIRES_DECISION) | Nothing about the 4 structural MATCH fixtures (#30) |
| 33 | L-13 CLOSED by ruling, pinned by a new analysis test (SLA → no liability Finding); L-08 AUTHORED (STD-LIAB-03 now asserts full 45E shape); L-04 blocked on SECOND_TRANCHE only | The ruling answers the scope question outright; the LEGAL_RULE half of L-04's blocker dissolved with the approval | The remaining SECOND_TRANCHE cases (L-03/04/09/10/17/22/29a/b) — owner supplies the paper |

**Verification at close: 660 backend passed · ruff/mypy clean · corpus 51 fixtures with L-08 newly complete · `all_lock.md` untouched at 15,358 lines.**


## Counterparty calibration pass, 2026-08-20 (owner: "go with your recommendation")

First 35.10-direction calibration of the liability terminology against the 8-specimen
counterparty set. Data-only: no engine change, no position/threshold/tolerance touched.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 34 | Liability mapping/extraction gained the counterparty drafting variants: exact phrases `will not exceed` / `not to exceed`, aliases `aggregate liability` / `limitation on damages`, cap phrases + `is limited to`; MSA basis FEES_PAID_FOR_AFFECTED_SERVICES gained the same concept in AWS's and CtrlS's words | The probe showed AWS and Microsoft caps scoring +3 (below threshold 5) and Google's cap extracting nothing — real counterparty paper was invisible. All added terms are generic drafting synonyms or the same basis concept verbatim from the cited clause | FEES_PAID's terms unchanged (`total fees paid` only) — service-scoped and product-scoped bases stay incomparable (45B.4) |
| 35 | Composite formulas stay unread BY DESIGN: no reversed-parenthetical (`6(six) months`) reading, no limb of a greater-of/lesser-of/average read as the cap | Reading one limb produces a confident wrong value — the L-11/45B.4 flattening failure; UNKNOWN → UNABLE_TO_EVALUATE → human is the correct outcome and is now pinned by test | A future multi-limb representation — an engine/modelling decision |
| 36 | CtrlS's same-clause "shall be unlimited" carve-out + composite cap resolves at clause level to UNLIMITED (→ Legal, evidence retained); the same-clause carve-out/cap split is recorded as an extraction-mechanics gap, not patched in a data pass | The document genuinely states the unlimited position; the outcome is fail-closed-to-human. Splitting one clause into carve-out + general caps needs reviewed mechanics work (44.17 at sub-clause granularity), not terminology | The mechanics change itself |
| 37 | Calibration pinned by `tests/test_calibration_counterparty.py` — 5 CI-safe tests using short cited excerpts of the public specimens against the REAL ratified files | 54.6 permits short excerpts; without pins, the next terminology edit could silently un-map AWS again. `confirm_threshold` 5 validated in passing: real counterparty cap clauses now score 5–8 | 35.10 remains not fully discharged — this is the first pass, on liability only; the 19 non-liability Requirements await counterparty specimens of their clause types |

**Verification at close: 666 backend passed · ruff/mypy clean · verify_terminology 21/21 PASS (own-document baseline held) · counterparty probe: AWS→first live-extracted DEVIATION vs the MSA standard, GCP/Microsoft/NYC fail closed on basis, CtrlS→CONFLICT, composites UNKNOWN · `all_lock.md` untouched at 15,358 lines.**
