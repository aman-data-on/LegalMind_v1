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


## Full-catalogue counterparty calibration, 2026-08-20 (owner: "complete the system — own it")

The 21-requirement probe matrix ran over every real document on this machine (own
source docs, the 8-specimen tranche, the public-web corpus PDFs) plus three real
executed agreements fetched from SEC EDGAR public filings. Every requirement now has
counterparty evidence — real where a public specimen exists, synthetic real-pattern
where none does (locked 54.6 expressly allows synthetic contract text; every synthetic
test is labelled and asserts only what follows mechanically from a ratified position).

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 38 | Extraction gained a configured `composite_phrases` fail-closed guard: a clause matching multi-limb terminology ("greater of", "whichever is less"…) yields UNKNOWN, never one readable limb | The dangerous case was live: a composite limb EQUAL to the standard would have produced a silent false MATCH needing no decision. Previously composites went unread only by drafting luck (reversed parentheticals) | Any multi-limb representation — a V2 modelling decision; the formula goes to a human as evidence |
| 39 | The mirrored digits-word convention ("15 (fifteen) calendar days") is now read — safe because composites are guarded first | The digits are stated; refusing them was blocking real specimens (ESDS's 15-day claim window). Word-only values ("one year", "a month prior") still refuse | Nothing: word-form values remain unread (44.24) |
| 40 | Per-document unit anchors extended (CtrlS cure sentence, Castlight purge sentence) — the data-level answer to page-level segmentation | First-match-in-segment reads a neighbouring section's number otherwise; anchors are each clause's own contiguous words | The proper fix — sentence-level magnitude anchoring — is reviewed mechanics work, recorded as the known gap (with #36) |
| 41 | SEC EDGAR full-text search adopted as an authorized public-filing source (Xerox/Global Imaging Mutual NDA; Castlight EX-10.11; Savvly EX-99.2K); documents stored outside the repository with the tranche | Real executed agreements, public by law — the owner's "excerpts from public filings" option. They supplied the NDA-side specimens no vendor page could | Nothing about the still-blocked liability patterns — negotiated paper remains the owner's supply |
| 42 | Xerox's survival clause ("expires two years from the Effective Date") is mapped but its anchor is deliberately NOT added to the NDA survival basis terms | Same number as the ratified standard, different clock — adding the term would let '2 == 2' assert a false MATCH across anchors, the exact 45B.4 trap the catalogue documents. Mapped-but-unable is the correct outcome | — |
| 43 | Four requirements pinned with SYNTHETIC real-pattern clauses only (DATA-RETRIEVAL, KYC-RETENTION, LATE-FEE value-variant, CONF-SURVIVAL-MSA value-variant) | Exhaustive search of public web terms and EDGAR found no third-party specimen stating a value for these (KYC retention is India-regulatory drafting; MSA survival years appear only as boilerplate). Synthetic pattern tests pin the mechanics; marked in the test file | The real-document requests, recorded in the session report — value-bearing counterparty specimens remain welcome but nothing is blocked on them |

**Verification at close: 683 backend passed (17 new calibration/mechanics tests) · ruff/mypy clean · verify_terminology 21/21 (own-document baseline held throughout) · `all_lock.md` untouched at 15,358 lines.**


## Requirement coverage-gap pass, 2026-08-20 (owner: audit, then "I am ready to approve all decisions — just implement")

A clause-by-clause coverage audit of all six LeapSwitch-issued documents preceded this.
Its finding was **not** that the catalogue was mis-scoped — document-type scoping,
fail-closed refusal and basis separation all verified working — but that it was **shallow
where the risk is highest**: `LIABILITY-MSA-001` read the cap number alone, so a
counterparty MSA capping at six months with no consequential-damages exclusion and no
fraud carve-out produced a clean `MATCH` and reached nobody. Eleven Requirements were
ratified in response, taking the catalogue to **32** (MSA 15 · TOS 8 · NDA 8 · SLA 1).

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 44 | All 11 new Requirements are `PRESENCE`, never numeric — including the two liability-depth ones and `AUTORENEW-TOS-001` | Each reads whether a provision EXISTS. The values behind them are not magnitudes: §7.2's early-termination fee is a *formula* ("total fees that would have become payable for the remainder of the Term"), TOS §4 renews for "the same billing period" (self-referential), and a perpetual trade-secret obligation has no number at all. Extracting any of them as a numeric position would require flattening — the 45B.4 trap | Nothing about the clause CONTENT: direction, breadth, seat and scope all go to Legal with the evidence. Categorical value comparison stays a V2 evaluator |
| 45 | Liability depth is **three separate Requirements**, not one enriched `LIABILITY-MSA-001`: cap value (existing), exclusion presence (§17.1/17.6), carve-out presence (§17.3) | A single Requirement cannot answer three questions without two of the answers becoming invisible — which is precisely the failure the audit found. Separate Requirements each produce their own Finding, their own evidence and their own Legal route | The existing `LIABILITY-MSA-001` is untouched: same clause, same basis, same 6-month position. Nothing was amended to add depth |
| 46 | `RETURN-DESTRUCTION-MSA-001` reuses the NDA standard's `scope_key` (`RETURN_OR_DESTRUCTION`); `ARBITRATION-TOS-001` reuses `ARBITRATION` | It is the same question, and the document-type filter guarantees the two never meet in one evaluation. Presence carries no basis, so no 45B.4 comparability question arises — unlike `CONF-SURVIVAL`, where the differing anchors forced two distinct basis names | Nothing merges the standards themselves: two files, two document types, two independently versioned positions |
| 47 | Absence is pinned with **STRUCTURAL** fixtures, not `DOCUMENT_SUPPORTED` ones | No supplied document omits these clauses, so there is no real material to cite and none is invented (45E.7 rule 1). The fixture asserts mechanics only: REQUIRED + mapping `NONE` → `MISSING`, zero evidence, `NOT_APPLICABLE` → human via D-3.5(b) | Nothing claims counterparty calibration for the new Requirements — 35.10 remains discharged only for the earlier 21 |

**Recorded rather than resolved, three items the pass surfaced and deliberately left open:**
the **CloudPe baseline** question (its TOS carries no liability cap and no arbitration
clause, yet both TOS standards cite the Leapswitch-branded document); the **missing
LeapSwitch NDA template**, which leaves the 2026-08-19 direction caveat unclosed; and
`CLAUDE.md`'s catalogue row, which still reads "15 Requirements across MSA/TOS/SLA" —
stale since the NDA block was added on 2026-08-19 and now doubly so. `CLAUDE.md` was
excluded from this change by instruction, so the drift is reported, not fixed.

**Verification at close: 699 backend passed (16 new corpus fixtures) · ruff/mypy clean · verify_terminology **32/32 PASS** on the real source documents · import gate accepts all 32 · document-type scoping tests 6/6 · `all_lock.md` untouched at 15,358 lines.**


## Public-source calibration of the 11 PRESENCE Requirements, 2026-08-21 (owner: "use public sources until real contracts arrive — do not wait for me")

The owner extended the test-only source authorization of 2026-08-18 to public web
terms, public filings, published corporate policies, legal articles and statutes, and
directed that calibration proceed on those until genuine counterparty contracts are
supplied. This closes the honest caveat recorded at the close of the 2026-08-20 pass:
the 11 new Requirements were pinned on LeapSwitch's own drafting only.

**Before the pass, 5 of 13 public specimens mapped. After it, 19 of 20.**

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 48 | Calibration is **data-only drafting variants** — 51 aliases and 23 keyword groups across the 11 files; no `exact_phrase` added, no position, threshold or `expected_presence` touched | Every gap found was a wording difference, not a concept difference: AWS writes "consequential OR EXEMPLARY damages" and "LOST profits" where MSA 17.1 writes "consequential, exemplary" and "loss of profits"; DigitalOcean disclaims with a bare "as is"/"as available" and no merchantability list; the EDGAR NDA says "destroy all Confidential Information" with no "return" verb at all | Nothing about what the clauses MEAN. These are PRESENCE Requirements: content goes to Legal with the evidence, and categorical comparison stays a V2 evaluator |
| 49 | Broad single words (`arbitration`, `trade secret`, `residuals`, `renewal term`) are configured as **aliases only, never `exact_phrase`** — and bare `as is` is not configured at all | With 35.8's weights an alias scores 3 against `confirm_threshold` 5, so no single generic term can confirm alone; two independent signals are always required. `as is` is ordinary English ("as is customary") and would over-match even inside that rule. The property is now pinned by `test_a_single_generic_term_cannot_confirm_alone` | The threshold itself — 5 remains STRUCTURAL pending 35.10's representative set |
| 50 | AWS §6.1 is left **deliberately unmapped** for `IP-OWNERSHIP-MSA-001` | It is a customer-content allocation, not the supplier IP-ownership clause the standard is the position for. Mapping it would need a term broad enough to fire on any sentence containing "rights", and an over-broad PRESENCE term yields a confident false PRESENT — worse than no mapping, because a reviewer never looks. Same judgement as the Xerox survival anchor (decision #42) | Nothing: a real supplier-IP-ownership specimen remains welcome |

**Statutes were used as NEGATIVE specimens, which is the only role they can hold** — a
statute is background law, never a Company Standard and never a Requirement source
(rule 7). A 7-statute × 32-Requirement sweep (224 pairs) produced **4 mappings**, and
the split matters:

* **1 was introduced by this pass** — `ARBITRATION-TOS-001` maps Contract Act §28
  Exception 1, which is genuinely about agreements to refer disputes to arbitration.
  Accepted: the text really is arbitration drafting, and a statute cannot reach the
  evaluator anyway without being falsely declared as a TOS at upload.
* **3 pre-date it and were not touched** — `KYC-RETENTION-TOS-001`,
  `TERM-NOTICE-NDA-001`, and most notably **`ARBITRATION-MSA-001`, which carries the
  bare word `arbitration` as an `exact_phrase` (weight 5)** and therefore confirms on a
  footnote citing "the Arbitration Act, 1940". That is a real precision defect in
  configuration ratified 2026-08-19 and calibrated 2026-08-20. **Reported, not fixed:**
  changing a calibrated pre-existing Requirement could regress the counterparty pass,
  and 35.10 forbids recalibrating without a representative set. It needs an owner call.

**Verification at close: 720 backend passed (21 new calibration tests) · ruff/mypy clean · verify_terminology **32/32 PASS** — the own-document baseline held throughout, which is what proves the new variants were additive · `all_lock.md` untouched at 15,358 lines.**

### Owner decisions recorded 2026-08-21 (not yet implemented)

| Decision | Status |
|---|---|
| **(b) MANUAL DROPDOWN — the user selects Document Type; no auto-detection in V1** | ✅ **Confirms the existing owner ruling Q9=A (2026-08-19), changes nothing.** The backend already requires a declared type and refuses an undeclared one. No work is created by this decision; the dropdown itself is frontend and belongs to the deferred design track |
| **(a) GROUPED REVIEW — one review session per upload batch, cross-document conflict checking REQUIRED** | ⚠️ **ESCALATED, NOT IMPLEMENTED.** Two parts, and they need separating — see below |

**Why (a) was escalated rather than built.** Its first half is fine and its second half
is not, and building them together would have buried the problem:

* *"One review session per upload batch"* is implementable **if "session" means a
  grouping** — N Reviews shown together, no schema change, exactly the shape the
  2026-08-21 impact analysis recommended. If it means a **domain object** with its own
  identity and status, it needs a `review_batches` table and a `Review.batch_id`
  column, which contradicts locked 42.13 and Step 26 r2 (*"A Review is tied to exactly
  one Document Version"*, locked in five places). **Which one is meant is unresolved.**
* *"Cross-document conflict checking is REQUIRED"* **contradicts the comparability
  rulings of 2026-08-19** (rule 5: report, do not resolve). Those rulings established
  that MSA liability (6 months, affected-service fees) vs TOS liability (12 months,
  total fees) are **DIFFERENT questions, twice over**, and that MSA confidentiality
  survival (3 years) vs NDA survival (2 years) are different questions with different
  clock anchors — *"'2 < 3' is not a true statement about protection strength."* A
  cross-document conflict checker would flag precisely those pairs as conflicts on day
  one. It would also need a home: locked 44.18 places conflict detection after fact
  extraction **within** a scope, and `Finding` is `UNIQUE(review_id,
  requirement_version_id)` — a cross-document finding belongs to no single Review.

**The safe subset, offered but not built:** a **cross-document OBSERVATION** that
reports differing positions across the batch without classifying them as a conflict —
the shape locked `REC-02` already uses for `UNMATCHED_PROVISION`, *"a document-level
observation [that] must never occupy a Finding's classification."* That still needs an
owner decision, and it is not what "conflict checking" was asked for.

### ✅ RESOLVED same day — the escalation above was a misreading of the requirement

The owner clarified the intended behaviour: *"a user makes a document set of MSA, TOS
and SLA, then the counterparty document set is analysed against LeapSwitch — MSA vs
MSA, TOS vs TOS etc — and gives, per document, what MATCH, what DEVIATION, what
MISSING."*

**That is type-matched pairing, not cross-type comparison, and it is already the
architecture.** Each document is measured against the Requirements for its OWN type;
"cross-document" describes the *set being reviewed together*, never a comparison
between two different document types. So nothing in the request touches Step 26 r2, and
the comparability rulings of 2026-08-19 are not in tension with it after all — they are
in fact what makes it correct, because they are the reason an MSA's liability position
is never measured against a TOS standard.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 51 | The multi-document requirement is **type-matched pairing over a grouped set**: N documents → N Contracts → N Reviews, each scoped by `_applicable_items` to its declared type, presented together. The "document set" is a **grouping, not a domain object** | This is what the owner described and it is already implemented and test-pinned (`test_an_nda_is_never_measured_against_an_msa_requirement`). Per-document MATCH / DEVIATION / MISSING is already what Findings plus `GET /reviews/{id}/report` return. No table, no column, no locked decision touched | The grouping's persistence — URL state vs a `batch_id` in the existing `document_versions.metadata` JSONB — remains a frontend decision on the deferred design track |
| 52 | **Cross-TYPE comparison stays OUT of V1** (comparing a counterparty MSA's position against their TOS's, or against a LeapSwitch standard of a different type) | It would contradict the 2026-08-19 comparability rulings on day one: MSA liability (6 months, affected-service fees) vs TOS liability (12 months, total fees) are DIFFERENT questions twice over, and MSA vs NDA confidentiality survival have different clock anchors — *"'2 < 3' is not a true statement about protection strength."* A checker would report those as conflicts. It also has no home: 44.18 places conflict detection within a scope, and `Finding` is `UNIQUE(review_id, requirement_version_id)` | Nothing forecloses a future **cross-document observation** on the `REC-02` `UNMATCHED_PROVISION` shape — a document-level note that never occupies a Finding's classification. Still an owner decision if ever wanted |
| 53 | **Within-document conflict detection is unchanged and already covers the real case** | The conflict that genuinely matters is two provisions in ONE document governing one scope and contradicting each other — MSA §17.2 vs §17.7 — which is `CONFLICT`, Tier 1, a human decides (fixture `DOC-LIAB-04`). Grouping documents adds nothing to it | — |

### Second calibration batch and the arbitration precision fix, same day

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 54 | **`ARBITRATION-MSA-001`'s bare `arbitration` demoted from `exact_phrase` to alias** (owner approval: *"YES, fix it"*), and the Requirement given the same counterparty drafting variants as its TOS counterpart | At weight 5 a single mention confirmed the mapping, so a footnote reading *"Cf. the Arbitration Act, 1940"* confirmed a Requirement about whether a contract contains an arbitration clause. Now weight 3: two independent signals required. MSA 19.3–19.4 still confirms — it states both `arbitration` and `arbitrator` | The threshold, still STRUCTURAL at 5 |
| 55 | **The five PRESENCE Requirements ratified 2026-08-19 were also calibrated** — `GOVLAW-MSA/TOS/NDA-001`, `COMPELLED-DISCLOSURE-NDA-001`, `RETURN-DESTRUCTION-NDA-001`. All five failed their first public specimen | The 2026-08-20 counterparty pass covered liability and the numeric clauses only; nobody had probed these. A public EDGAR NDA exhibit exposed all five at once: *"governed by and construed AND ENFORCED in accordance with"* misses the configured exact phrase by three inserted words, *"legally compelled … to disclose"* misses *"required by applicable law"*, and *"destroy all Confidential Information"* carries no `return` verb | Nothing — data only, same discipline as #48 |
| 56 | **The remaining statute matches are NOT treated as defects and no `negative_patterns` were added** | After #54 the surviving matches are on text that genuinely discusses arbitration agreements and termination notice (Contract Act §28 Exception 1), scoring 6–9 from several independent signals. The control against a statute reaching the evaluator is the **declared Document Type at upload** — "statute" is not one of Step 6's ten values — not the mapper. Suppressing them would need negative terms that also suppress genuine contract clauses, which 35.10 forbids without a representative set | Whether a future ingestion-side guard should refuse an obvious statute — an owner/product question, raised not answered |
| 57 | A latent **test defect** was found and fixed while pinning #54: the helper read scores from `map_requirement`, which exposes only candidates already at or above `confirm_threshold`, so `assert score < 5` passed on a score of 0 — trivially, for any terminology including terminology that matched nothing. It now reads `score_clause` directly and asserts `0 < score < 5`, so "recognised but not sufficient" is actually verified | A test that cannot fail is worse than no test: it reports safety it never checked | — |

**Verification at close: 726 backend passed (26 calibration tests) · ruff/mypy clean · verify_terminology **32/32 PASS** · statute sweep 224 pairs, the bare-word match eliminated · `all_lock.md` untouched at 15,358 lines.**
