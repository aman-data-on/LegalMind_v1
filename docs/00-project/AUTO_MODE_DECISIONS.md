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

## Post-audit reconciliation, 2026-08-25

**Owner instruction:** continue development, reconcile the audit, create the governance documents,
and *"make the engineering decision and continue"* where the owner's input is not genuinely required.
Owner decisions taken as given: **Gemini Flash** is the generative model; its no-training terms are
**not yet confirmed**, so only synthetic material may egress; the **embedding model is self-hosted**.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 58 | The Gemini selection lands as an **appended amendment** (AB-4: `AM-30`, `AM-31`, `IMPL-02`), not as code written against the instruction | `AM-25` r9 is a confidentiality guarantee and AB-3's Position lists hosted model APIs out of scope. `CONTRIBUTING.md`'s load-bearing rule is that an implementation change is never the vehicle for a specification change | Nothing about the provider tier, the model version, or the client library — rule 19 still governs the dependency |
| 59 | `AM-30` **scopes** `AM-26`'s `Inference runtime — no outbound network route` row rather than deleting it | The row still correctly describes the local runtime serving the embedding and reranking models. Leaving it unamended would have made AB-4 internally contradictory; deleting it would have removed a control that still applies | Whether a GPU is needed — it still is, for the local models |
| 60 | The real-contract egress gate is a **locked property** (`AM-31`), with the mechanism left to implementation | A feature flag would let the confidentiality posture change with no amendment and no owner signature. `AM-25` r2 sets the in-house precedent: a confidentiality boundary is enforced by mechanism, not convention. Locking the property while leaving the mechanism free keeps the *unlock* an auditable, named event | How the marker is stored. `AM-27` r2 forbids a new column on a locked table, so it must compose with locked 55.3's environment separation or sit on a permitted assist table |
| 61 | `AM-31` m1–m5 resolve the `AM-26` r3 contradiction **in writing** rather than leaving it to judgement | r3 requires the quality bar measured on real supplied documents; the gate forbids real text egressing. Unresolved, the predictable outcome is someone measuring on synthetic material and reporting r3 as satisfied | What the evaluation set contains. It does not exist and, per rule 21, is supplied rather than authored |
| 62 | **No corpus tables authorized in AB-4.** Domain A/C schema raised as **C-15** instead | Authorizing tables whose shape is not yet designed is speculative, and bundling a schema decision into the model-hosting batch makes it inherit that batch's fate. Also: the owner's no-flattening instruction **reverses** the audit's RA-3 shape-1 recommendation, which rule 5 requires registering rather than silently applying | Which shape wins. Two are recorded in C-15 |
| 63 | **No `legalmind/assist/` package or feature flag created yet** | `CONTRIBUTING.md` forbids generating scaffolding "to get started", and an empty package asserts a design not yet built. The *tests* that fence it ship now; the package ships in Gate §5b unit A1 | Nothing about the eventual package layout |
| 64 | The **corpus-parity harness is deferred**, reversing the audit's "safe now" classification | Verified premature: `evaluation/corpus.py::run_fixture` is a pure in-memory evaluator call with no database, so nothing an assist lane could do can perturb it, and `tools/verify_reproducibility.py` already double-runs the full pipeline. A parity test today asserts a tautology | That it is unnecessary later. It belongs in the phase that first adds an assist **write** path |
| 65 | The boundary test is an **allow-list**, not a deny-list, and asserts **no outbound network import anywhere** | An allow-list fences a package that does not exist yet: importing a future `legalmind.assist` from the deterministic core fails on the first run with no rule added, which is what makes `AM-25` r1/r2 structural. The no-network rule pins today's posture so that the day `AM-30`'s adapter lands, exactly one module is added to `EGRESS_ALLOWED` **by name** and the diff cannot be missed | Where the adapter lives, or which library it uses |
| 66 | A **locked-column snapshot test** (29 tables, 195 columns, against the live database) | `AM-27` r2 names the existing invariant tests as its evidence that no locked table changed. None of the 21 was sensitive to a column, so adding one passed all of them silently — the evidence sentence was true and proved nothing. Asserted against the database, not `Base.metadata`, because a migration adding an undeclared column is the more dangerous direction and is invisible to a metadata check | The table-count discrepancy. `all_lock.md` says 30, the repository says 29; registered as **C-14**, not corrected |
| 67 | A **full-suite CI job** added; job 5's flake probe left exactly as written | Job 5's `fails -gt 0 && fails -lt 3` predicate is correct for an `F-4` flake detector — three failures of three is not flaky. But no *other* job ran the whole suite, so ~250 tests in ~12 files had their results discarded. `AM-28` r2's own logic applies: a guardrail no job gates is not a guardrail | Nothing about the probe, which is unchanged and still useful |
| 68 | CI asserts **no model-provider credential is present** | `AM-30` t1/t8: a credential in CI means a misconfigured job could egress from a pull request. Asserting absence is cheaper than trusting that nobody adds one | Where the real credential lives in production |
| 69 | Two new documents, **not three.** No `CURRENT_ARCHITECTURE_AND_PHASE_PLAN.md` | `ARCHITECTURE_REFERENCE.md` already maps the architecture and `EXISTING_BACKEND_REUSE_AUDIT.md` §15 already holds the phase rationale. The *authorized* sequence went to `IMPLEMENTATION_READINESS_GATE.md` §5b via `IMPL-02` — mirroring how `IMPL-01` authorized §5 — because the audit is `ANALYSIS` and a working document may never become an authorized sequence | Nothing about the ordering itself, which `IMPL-02` r4 makes revisable except for two properties |
| 70 | Neither new document asserts build state | `IMPLEMENTATION_STATUS.md` is the only document permitted to, and this repository has concrete evidence of what happens otherwise: it read "653 tests" and "No Legal Rule exists" while the suite was 726 and the rule was wired in 32 of 32 files | — |
| 71 | The audit's contradiction series renamed `C1`–`C16` → **`RA-1`–`RA-16`** | It collided with `CONFLICTS.md`'s `C-01`–`C-16` — the second instance of the overloaded-`F-*` problem `CLAUDE.md` already documents. Reuse-audit findings are not register entries | Nothing in the register. Genuine unresolved items were registered separately as C-14/C-15/C-16 |
| 72 | Stale figures corrected only where **measured**: 726→781 tests, 53→58 Vitest, the Legal Rule claim, the Requirement count, the open-conflict count, `DATABASE_MIGRATIONS.md`'s "no migrations implemented" header, `AGENTS.md`'s "specification phase" paragraph | Rule: verify before writing. Each figure traces to a command run in this session | The table count, deliberately left as a reconciliation rather than a correction — see C-14 |

**Verification at close: 781 passed · ruff and mypy clean · `all_lock.md` appended only (337 insertions,
0 deletions, previous 16,048 lines byte-identical as a prefix) · both new boundary tests
independently proven to fail on a simulated violation before being accepted.**

## Gate section 5b unit A1 — assist schema, 2026-08-25

Authorized by `IMPL-02` r1. Every decision below is schema implementation within
`AM-27`'s authorized table list; none decides a legal question, and none adds a
technology beyond `AM-26` as amended.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 73 | **Eight of the nine tables. `chunk_embeddings` deferred to A3** | Its embedding column needs a fixed dimension, which is a property of the embedding model — and `AM-26` r2 selects that model *by measurement, smallest-that-passes*, so none is selected and no dimension is known. `vector(768)` today would write a number nobody chose into the schema: rule 7's habit applied to DDL. `test_chunk_embeddings_is_deliberately_absent` makes its arrival deliberate | Which model, or which dimension. `embedding_models.dimensions` is where the number gets recorded first |
| 74 | **The migration does not `CREATE EXTENSION vector`** | Verified on PG16: `vector` is **not** a trusted extension, so creating it needs superuser. The application role is not one and must not become one. A migration demanding superuser would force that permanently. pgvector is therefore a deployment precondition, reported by preflight | How it is provisioned. That is a deployment step |
| 75 | **pgvector pinned ≥ 0.8.0**, and Ubuntu's 0.6.0 recorded as insufficient | `AM-25` r6 requires authorization applied *inside* the retrieval query — pre-filtering. Under a selective pre-filter an approximate index can starve, and pgvector's fix is **iterative index scans, added in 0.8.0**. On an older build the only options are poor recall or a post-filter, and a post-filter is the enumeration oracle r7 forbids. So the version is a correctness constraint, not a preference | Nothing about the index type (IVFFlat vs HNSW) — an A3 measurement |
| 76 | **The migration does create `pg_trgm`**, pinned to `public`, with the operator class schema-qualified from a live lookup | `pg_trgm` **is** trusted, so the application role may create it. Pinned to `public` because an extension installs into the first schema on `search_path`, which in a test run is the per-run schema that gets dropped — the operator classes would vanish with it. The ops class is then qualified from where the extension actually is, rather than adding `public` to `search_path`: widening the path would give every unqualified lookup in a test run a fallback into a shared schema, which is the isolation `F-4` exists to provide | Whether trigram is the right lexical companion to `tsvector`; that is an A4 measurement |
| 77 | **The assist schema name is derived per test run** (`<run>_assist`), via `LEGALMIND_ASSIST_SCHEMA` | A hardcoded `assist` would be shared by every concurrent suite while the locked tables sit in private per-run schemas — reintroducing exactly the cross-run collision `F-4` fixed. The stale-schema sweep and teardown were extended to match, dropping the assist schema first because its foreign keys point into the locked one | Nothing about production, which uses the default `assist` |
| 78 | **`chunks` does not copy page, section number, section title or source type** | `AM-27` r4: a chunk *"carries no independent provenance"*. Those live on the evidence row and are reached by one join over immutable data. A denormalized copy is the standard way a derived store starts disagreeing with its source, and the R&D document already named it an anti-pattern | That `content` is also duplication — r6 says the text *"remains reachable through the chunk reference"*, which presupposes the chunk holds it |
| 79 | **`chunks.evidence_id` is NOT NULL and singular** | `AM-27` r4 says *"the Document Evidence row it came from"* — singular. So a chunk is a span within one evidence row, never a concatenation across several. Makes an untraceable chunk unrepresentable rather than merely discouraged (rule 11) | Whether a parent/child chunk pair is wanted later; no `parent_chunk_id` was added, since the retrieval strategy that would use it is unbuilt |
| 80 | **`content_tsv` is a generated column, not application-maintained** | A generated column cannot disagree with `content`. A stale search index over legal text is a silent correctness problem, not a visible failure | The text-search configuration (`english`), which is an A4 measurement |
| 81 | **`retrieval_runs.results` is JSONB holding `[{chunk_id, score, rank}]`** | `AM-27` lists nine tables and closes with *"No other table is authorized"*, so there is no child table available for a variable-length result list. r3 restricts JSONB to *"genuinely variable configuration"*; a result set is genuinely variable though not configuration, and parallel Postgres arrays trade one compromise for a worse one. **The cost is stated in the migration**: those chunk ids carry no foreign key, so a deleted chunk leaves a dangling id — tolerable only because this is a diagnostic record of one query, while the *verified* citations live in `answer_citations` with a real FK | Whether the result list should ever gain referential integrity. If it bites, that is an `AM-27` extension request |
| 82 | **`ai_answers.model_identity` and `prompt_version_id` are nullable** | `AM-29` r3's `EVIDENCE_INSUFFICIENT` means *"the model is not called at all"*. A NOT NULL column would force a placeholder, and a placeholder model identity on an answer that never reached a model is a fabricated record of an external call | Nothing about which model. `AM-30` t7 governs the identity format |
| 83 | **No `confidence` column anywhere**, asserted by a test | `AI-03` locked item 16: *"The system does not use generic AI confidence scores."* The sanctioned signal is the `AM-29` answer state plus per-citation retrieval scores, labelled as retrieval scores | How the frontend renders the answer state |
| 84 | **`messages.role` is a CHECK-constrained string, not an enum** | It is a transport concern, not a controlled legal vocabulary. Minting an enum type would place a non-legal vocabulary beside the five axes, which `AM-29` r1 spends its length keeping apart | Nothing about the answer state, which *is* an enum because it is the sixth axis |
| 85 | **The `AM-27` r5 cascade is tested at the evidence row**, plus a test pinning that a document version cannot be deleted at all | Discovered while testing: `document_processing_runs` and `reviews` both reference `document_versions` with no cascade, so the locked schema has **no delete path for a document version**. r5's cascade is implemented and verified where it is defined; r5's *premise* is currently unreachable. `test_the_locked_schema_has_no_delete_path_for_a_document_version` records that, and fails if someone later adds cascades — which would change whether historical Reviews stay reproducible | The retention and deletion policy, which remains genuinely undecided and owner-owned |
| 86 | **MinIO deferred from A1 to A10** | Locked 55.6 makes the object-storage *provider* a deployment choice, the existing `StorageBackend` Protocol already isolates it, and it is not on the retrieval critical path. Deferring also avoids settling the `boto3` dependency question (rule 19) before anything needs it | That MinIO is the provider; 55.6 still owns that |
| 87 | **Both compose and CI moved to `pgvector/pgvector:pg16`** | Keeping dev, CI and the staging reference on one image removes an environment difference, and it exercises the more production-like preflight path (extension *available but not installed*, rather than *absent*). Authorized by `AM-26` | Nothing about production hosting, which 55.6 leaves open |

**Verification at close: 817 passed · 1 skipped (the `legalmind_assist` grant check, which
asserts its property only where the role exists) · ruff and mypy clean · migration
round-trips · `tools.verify_reproducibility` PASS with the legal digest **unchanged**
across the new migration · `tools.verify_invariants` 9 PASS 2 SKIP ·
`test_locked_schema_columns.py` passed **unmodified**, which is `AM-27` r2's evidence.**

## Gate section 5b unit A2 — chunking and lexical search, 2026-08-25

Authorized by `IMPL-02` r1. The first application code in `legalmind/assist/`. No legal
question is decided here; the lane produces no Finding to decide one with (`AM-25` r1).

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 88 | **Chunking transforms evidence rows; it never re-reads the document** | `AM-27` r4. The parser already segmented paragraphs, detected the numbering the document itself states (34.12 — preserved, never generated), kept page numbers and offsets, and flagged OCR text. Re-deriving that from raw bytes would do it worse *and* create the second source of truth r4 forbids | The chunk *boundary* policy, which is the next row |
| 89 | **One chunk per evidence row, split only above 2000 characters** | The cap is a retrieval-shape choice, not a legal one. Characters rather than tokens deliberately: counting tokens needs a tokenizer, which is a dependency (rule 19) and a model-specific one — the unit would change meaning the moment the model did. Generous on purpose, because splitting is the lossy operation: a clause cut in half can strand a carve-out from the obligation it qualifies | Overlap and parent/child hierarchy, both omitted — they are retrieval tactics whose value depends on a strategy that is unbuilt, so adding them now would be tuning against a hypothesis |
| 90 | **Split boundaries are zero-width regexes** | Found by a test. A pattern that *consumes* the whitespace it splits on makes reassembly lossy — the pieces concatenated to `"law.Each"` instead of `"law. Each"`, which breaks phrase search and reads as a typo inside a citation. Zero-width lookarounds keep the separator with the following piece, so concatenation is exactly lossless | Nothing about the hard-cut fallback, which splits mid-token by nature and is documented as arbitrary |
| 91 | **Only the first piece of a split row claims the evidence offset; later pieces carry `None`** | The parser's offsets index the *extracted* text, and normalization between `original_content` and `content` means a character count into the normalized string is not an offset into the original. A computed offset would look right and be subtly wrong, and a wrong offset corrupts a citation. An absent offset is honest | Whether exact sub-row offsets are recoverable later; they may be, from `original_content` |
| 92 | **Core tables built per call, not declarative ORM models** | `AM-27` r1 puts the assist tables in a separate schema, and in a test run that schema is derived per process. A declarative model fixes its schema at import time — before `conftest` has decided what it is. Core avoids that entirely, and leaves the locked `Base.metadata` untouched, which is what keeps `test_locked_schema_columns.py` passing unmodified | That ORM models are never appropriate here; if a later unit needs them, `Base.metadata.schema` handling is the thing to solve then |
| 93 | **`similarity()` and `gin_trgm_ops` are schema-qualified from a live lookup, not reached by widening `search_path`** | pg_trgm's functions live in whichever schema the extension occupies, and the harness points `search_path` at a private per-run schema. Adding `public` to the path would give *every* unqualified lookup in a test run a fallback into a shared schema — the isolation `F-4` exists to provide. The lookup is cached because it is a property of the installation, not of the query | Where the extension is installed; the migration pins `public` and the lookup reads whatever is true |
| 94 | **Re-indexing is refused by default, not performed idempotently** | The obvious implementation — delete and reinsert — cascades to `answer_citations`, so a silent re-index would invalidate citations already recorded against the removed chunks: an answer whose sources have quietly vanished. Nothing cites a chunk yet, which is exactly why this is the cheap moment to decide it | Whether a *safe* re-index is possible later. It probably needs citation migration, and that is a real design question |
| 95 | **A failed index can never fail an ingestion** (`index_safely`, and the dispatcher swallows) | Evidence is authoritative and a chunk is derived and rebuildable. Refusing an upload whose parsing succeeded, because a derived index could not be built, would let the assist lane break the authoritative path — the inversion `AM-25` r1 and Step 38 rule 21 exist to prevent. Failures are logged as operational so they stay countable rather than silent | Nothing about retry policy for the queued path, which retries like any other job |
| 96 | **Indexing may enqueue before the commit, where analysis may not** | `dispatch_analysis` refuses to write before enqueueing because marking a Review `PROCESSING` and losing the message strands it — Step 30 gives `PROCESSING` no way out. Indexing marks nothing: if the caller's transaction rolls back, the message finds no document version and drops. The dual-write hazard does not arise, so requiring a post-commit hook would be complexity for its own sake | Nothing about analysis, whose posture is unchanged |
| 97 | **A separate `assist` queue and a separate worker process** | Indexing is high-volume, derived and non-authoritative; analysis produces legal records. One worker draining both queues would let an index backlog delay a Review's analysis, inverting the priority Step 38 rule 21 sets between the lanes. Two processes make that impossible rather than unlikely. Still one image with a different command — `AM-26`'s modular monolith is unchanged | Concurrency or scaling for either queue |
| 98 | **`search_chunks` takes one authorized `document_version_id`, applied as a `WHERE` clause** | `AM-25` r6: authorization before retrieval, **inside** the query. The signature is shaped so a caller cannot forget to scope it, and the scope is a pre-filter on the candidate set rather than a filter over results — post-filtering would let result count, ranking or latency reveal a chunk in a document the requester may not read, which is r7's enumeration oracle and what `API-10`'s byte-identical 404 exists to close | Multi-document and cross-domain retrieval, which arrive in A3/A8 and will need the visible-ids subquery form |
| 99 | **Two lexical signals, deliberately not fused into one weighted score** | `tsvector` stems and so matches paraphrase but mangles `17.2` and party names; trigram matches those literally but has no notion of meaning. They fail differently, so both are used — but a weight between them would be an invented number, and rank fusion belongs with the vector half in A3/A4 where it can be measured | The fusion method, which A4 measures (RRF is the likely candidate) |
| 100 | **No score is stored on a chunk row**, asserted by a test | A retrieval score is a property of one query. Storing it would make a per-question number look like a permanent attribute of the document — and it is a *retrieval* score, never legal confidence (`AI-03` item 16) | How a score is presented; the frontend surface is A7 |

**Verification at close: 841 passed · 1 skipped · ruff and mypy clean ·
`tools.verify_reproducibility` PASS with the legal digest unchanged ·
`test_locked_schema_columns.py` still passing **unmodified** · demonstrated end to end
against a synthetic MSA: phrase, quoted-phrase and section-number queries all resolve,
and an absent term returns an honest empty result, with no model reachable
(`EGRESS_ALLOWED` remains empty).**

## Gate section 5b unit A3 — retrieval measurement, 2026-08-25

Authorized by `IMPL-02` r1. **No model is selected and no vector dimension is pinned** —
`AM-26` r2 settles that by measurement, and the measurement is not yet complete. Two
owner inputs are required and are stated in
[LEGALMIND_PROJECT_STATE.md](LEGALMIND_PROJECT_STATE.md).

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 101 | **The instrument is built before any candidate exists** | `AM-26` r2 is a comparison — smallest-upward, stopping at the first that passes — and a comparison needs a fixed measuring instrument that predates the things it measures. Building the harness first also means the lexical baseline is a *measured* number rather than an assumption about what embeddings would improve on | Which model wins. That is what the harness is for |
| 102 | **Every probe is derived mechanically; none is authored** | The distinction that licenses it: a *retrieval* label ("the text about X is in §17.2") is a locatable fact about a document and asserts no legal position; an *answer* label ("our cap is 12 months") is a legal position and `AM-31` m5 requires it supplied. Three families are derivable — section numbers the document states, n-grams computed to be unique to one chunk, and out-of-vocabulary n-grams for refusal | The two families that are **not** derivable, which is the blocker below |
| 103 | **Semantic similarity and legal phrasing are reported as NOT MEASURED rather than approximated** | They need a question whose wording deliberately differs from the document's, which cannot be derived from the document. Measuring candidates only on the derivable families would score them where lexical is strongest and embeddings weakest — selecting a model on evidence that does not bear on the question. That is "claiming a model is best without measurement" wearing a table of numbers | Nothing. It names the gap precisely so it can be closed |
| 104 | **The unanswerable probe was tightened after its first result, and the first number discarded** | Version one required only that a 4-gram be absent, and reported **26 of 72 wrongly answered**. But `websearch_to_tsquery` ANDs stemmed terms, so a chunk containing all four words scattered matches — and topically that may be a fair result. The probe was measuring its own design. Requiring one genuinely out-of-vocabulary word took it to **8 of 72**, and the residual is consistent with stemming equivalence, so 89% is a floor | Whether the matching is too loose for `AM-25` r5's purposes; the guardrail in A4 answers that with a threshold it can justify |
| 105 | **Clause-boundary splitting, driven by a measured ingestion finding** | PyMuPDF emits **no blank lines** for the real PDFs (59 single newlines, 0 double on a representative page), so `segment_paragraphs` produced one page-sized evidence row per page: 99 page-fragment chunks across six documents, **2 of 59 rows with a section number**. The structure was not missing — `1.13.`, `4.1.`, `4. SCOPE OF SERVICES` are on their own lines. Splitting there gave **341 clause-sized chunks, 300 with a section (88%)**. Measuring an embedding model on page-sized, section-less chunks would have produced meaningless numbers | The sub-item granularity (`(a)`, `(i)`), deliberately not split on — that is a retrieval-granularity question for A4 to measure |
| 106 | **The section reference is derived at query time, never stored** | It is a pure function of text already selected, so deriving it cannot drift — whereas a stored copy is exactly the "independent provenance" `AM-27` r4 forbids. Prefers the evidence row's own `section_number` and falls back to the chunk's leading marker | Nothing about the `chunks` schema, which is unchanged |
| 107 | **A four-digit bare number is not treated as a clause marker** | `2024.` is a year, an amount or a page artefact far more often than a clause, and without the guard a contract mentioning a year would fragment at every occurrence. Requiring a dot or at most three digits admits `4.` and `1.13.` and rejects `2024.` | Roman-numeral and lettered markers, which are not split on yet |
| 108 | **Candidate metadata is fetched, not recalled** | Licence, dimension, parameter count and ONNX availability come from the HuggingFace model API on 2026-08-25 rather than from memory. Stating a dimension from recall and then pinning a schema column to it is the same class of error as inventing a threshold. Note this is *inbound* metadata about public models — no document, chunk or prompt leaves, so `AM-30` t1 is untouched | Which candidate is chosen, or whether the runtime to run them is approved |
| 109 | **`onnxruntime` + `tokenizers` recommended over `torch` + `sentence-transformers`** | ~50MB against ~2.5GB, CPU-only, and **inference-only** — so `AM-26`'s no-fine-tuning and no-training-on-the-corpus positions become structural rather than merely stated. All eight candidates publish ONNX exports, so nothing is given up. **Recommended, not taken**: rule 19 governs the dependency, and `AM-30`'s record draws exactly this line for the generative provider's client library, so self-approving here would be applying the project's own rule selectively | The choice itself, which is the owner's |
| 110 | **The pgvector requirement is corrected from BLOCKED to ATTEST, on measurement** | Verified on 0.6.0: exact cosine KNN with the authorization `WHERE` clause in the same statement works and genuinely excludes out-of-scope rows. Exact search loses no recall, so `AM-25` r6 is fully satisfiable now — it is O(n) over the pre-filtered set, which for one document's chunks is the right trade anyway. **≥ 0.8.0 buys iterative index scans**, which matter only for an *approximate* index under a selective pre-filter. The earlier BLOCKED framing overstated it | That the upgrade is optional at corpus scale. It is not — and the answer to an older build is exact search, **never** a post-filter (`AM-25` r7) |
| 111 | **The harness SKIPs when the source material is absent** | CI has no documents (locked 54.6), and "cannot measure here" must not read as "measured and fine". Same posture `test_source_material.py` already takes. Probes are generated at run time and no document text is written to any fixture | Nothing about CI gating, which A9 settles once there is a Tier-2 set to gate on |

**Verification at close: 848 passed · 1 skipped · ruff and mypy clean · benchmark runs
against six real supplied documents and reports a measured baseline · no model imported,
no dependency added, no vector dimension pinned, `EGRESS_ALLOWED` still empty.**

## Gate section 5b unit A3 — candidate measurement, 2026-08-25 (continued)

Owner approvals recorded the same day: `onnxruntime` + `tokenizers` under rule 19, and
30–50 real evaluation questions to follow. Decisions #101–#111 above cover the harness;
these cover running it.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 112 | **The installed footprint is reported as 118 MB, correcting the ~50 MB I gave when asking** | The estimate omitted numpy, which onnxruntime requires. The figure is now measured, not estimated. It does not change the recommendation — `torch` remains ~2.5 GB and carries a training stack the record excludes — but a provisioning number given to an owner should be right | Nothing. Recorded because the earlier number was quoted in a decision |
| 113 | **Weight fetching moved OUT of `legalmind/` into `tools/provision_model.py`** | The first draft put a `provision()` helper beside its consumer, and `test_import_boundaries.py` refused it for importing `urllib`. The right fix was not an `EGRESS_ALLOWED` entry but removing the capability: **no module under `legalmind/` imports a network client**, and that invariant is worth more than the convenience. `AM-26` r5's "never fetched at runtime" is now structural rather than promised, and `EGRESS_ALLOWED` is still empty | How weights are provisioned in production, which is an operator step |
| 114 | **The onnxruntime execution provider is pinned to CPU, asserted by a test** | onnxruntime ships an `AzureExecutionProvider` beside `CPUExecutionProvider`. Left to the default list an inference session could acquire a second network egress, and `AM-30` t1 permits exactly one — the generation call. Same reasoning as `AM-25` r2's database grants: a boundary enforced by mechanism survives a change that a boundary enforced by expectation does not | Whether a GPU provider is ever added; at this model size none is needed |
| 115 | **Embedding is batched at 16, and a test asserts batching changes no vector** | Not a tuning knob — a memory bound found by being OOM-killed at **14 GB RSS**. Padding takes every sequence to the longest in the batch, so one 512-token chunk inflates a 236-chunk document's activations. Embeddings are position-independent, so the bound cannot change a result — and the test proves that rather than assuming it | The batch size as a throughput choice; it is set by memory |
| 116 | **`intfloat/e5-small-v2` skipped rather than special-cased** | Its ONNX export is published at a non-standard path. Adding a per-model path exception to reach one more candidate would trade a general loader for a special case, and four candidates already showed the deciding result. Recorded as skipped, not as measured | Whether it would have scored well. It is untested, and is not described otherwise |
| 117 | **Vector and hybrid strategies live in the harness, not in `legalmind/assist/`** | They rank in memory to compare candidates. Production ranking must happen in SQL so `AM-25` r6's authorization sits inside the query; shipping an in-memory ranker would invite exactly the post-filter r7 forbids. So it is not shipped — it exists to answer "which model" and nothing else. The scope is still pre-applied: only one authorized document's chunks are ever candidates | The production hybrid implementation, which is SQL and comes after selection |
| 118 | **RRF k=60 is recorded as the conventional constant, not a tuned value** | It is the constant from the original formulation. Calling it tuned would imply a measurement that has not happened; fusion weighting is precisely the parameter that needs the evaluation set before it means anything | The fusion method or its parameters, both of which A4 measures |
| 119 | **No model is selected, and `chunk_embeddings` is still not created** | Four candidates were measured on the derivable families, and on those families lexical already wins or ties. The families an embedding model exists to win — semantic similarity, legal phrasing — remain unmeasured. Selecting now would be choosing on evidence that does not bear on the question, and pinning a dimension would settle by DDL what `AM-26` r2 settles by measurement. All four measured candidates happen to be 384-dimension, and that convenience is **not** a reason to pin 384: the 768 group is unmeasured | The eventual choice. The harness and the runtime are now in place to make it in one pass once the questions arrive |
| 120 | **A measured similarity floor is now recorded as a precondition for dense or hybrid retrieval** | Measurement finding, not a design preference: **every** vector and hybrid strategy refused **0 of 36** unanswerable probes against lexical's 34, because nearest-neighbour search returns its nearest neighbour however far away — a ranking is not a filter. `AM-29` r3 requires `NO_EVIDENCE_RETRIEVED` and `EVIDENCE_INSUFFICIENT` to be reachable, and `AM-25` r5 requires mechanical enforcement outside the model. So a floor is structural, and rule 7 requires it be **measured** against known-unanswerable questions rather than picked | The threshold value, which needs the evaluation set — the same blocker as the model choice, reached independently |

**Verification at close: 862 passed · 1 skipped · ruff and mypy clean · no module under
`legalmind/` imports a network client · `EGRESS_ALLOWED` empty · no vector dimension
pinned · `chunk_embeddings` absent · `AM-31` gate CLOSED.**

## Evaluation dataset drafted, 2026-08-26

Owner instruction: author the Tier-2 evaluation dataset from the actual documents, both
contract and statutory groups, as evaluator not advocate; stop before any calibration.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 121 | **The set is authored, and labelled DRAFT pending owner ratification** — reconciling the instruction with `AM-31` m5's "supplied, never manufactured" | The owner directed authorship with bias controls, which is a supply decision in substance; the label preserves m2's rule that no quality bar is passed on unratified material, and the owner's own pipeline puts HUMAN REVIEW before BENCHMARK. Flagged to the owner in one sentence before starting | Ratification, which is the owner's review |
| 122 | **Every question verified against a full read of the target document; 47 load-bearing claims re-checked mechanically** | Rule 21's discipline applied to evaluation material: an invented section number in a test dataset poisons the calibration it exists to serve. The Companies Act file turned out to be a 4-page **extract** (§21–24, §178–181) — questions were confined to what it actually contains, which only a read could reveal | Nothing about the statutes' legal effect; they remain background law (CLAUDE.md), and no Requirement or threshold is derived |
| 123 | **13 NOT_FOUND questions, each with the misleading nearby clause recorded** | The benchmark's purpose is calibrating refusal; a refusal probe is only as good as its trap. Three deliberately exploit real cross-document confusions (MSA vs TOS price notice; DPDP's *absent* breach deadline vs CERT-In's 6 hours; DPDP penalties vs IT Act 43A compensation) — the exact distinctions the owner asked the search to make | The similarity floor, which is measured later, never chosen |
| 124 | **Dataset lives in `backend/tests/assist_eval/`, not `tests/corpus/`** | `AM-28` r3: the evaluation set never shares the golden corpus's authority, and the corpus CI guard must not see it. No document text enters the repo (54.6) — questions, filenames, sections and short excerpts only; **no counterparty or signatory name appears**, verified by an automated check against the two executed documents | — |
| 125 | **64 answerable exceeds the original "30–50" band** | The mid-task expansion to statutory documents added a second group (44 contract + 20 statute); forcing the total back under 50 would have meant thinning whichever group the owner reviews. The report marks the questions to cut first if the owner trims | The final size — owner's review call |

**Verification at close: JSON valid · 77 questions, ids unique · every referenced document
present on disk · every ANSWERABLE has a verified section · every NOT_FOUND has a verified
absence and a recorded trap · no banned names · no near-duplicate wording · 47/47
mechanical claim checks pass · no benchmark run, no threshold computed, no code changed.**

## End-to-end assist implementation, 2026-08-26

Owner instruction: complete the smarter-search/RAG implementation end-to-end, deciding
routine engineering questions autonomously; ratified the drafted evaluation set by
directing its use; approvals for the runtime were given 2026-08-25.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 126 | **The drafted evaluation set is recorded as owner-ratified** (2026-08-26) | The owner directed: "Use questions_draft.json as the current evaluation dataset. Do NOT ask me to recreate these questions." That is the HUMAN REVIEW stage of their own pipeline passing; `AM-31` m1's explicit label is updated accordingly | Nothing about the golden corpus, which stays blocked on its own material (`AM-28` r3) |
| 127 | **Anchors added to the dataset** — a short cited excerpt per answerable question, used only by the harness to locate the expected chunk | Scoring must be mechanical: matching by clause number alone fails for descriptive locators ("Direction (ii)", table headings), and judging by rationale would measure the labeler. Every anchor was verified to resolve to ≥1 chunk before any measurement ran | The questions' legal meaning, untouched |
| 128 | **Model: `all-MiniLM-L6-v2`, by `AM-26` r2's own tie-break** | Measured on the ratified set: MiniLM (23M) passes the quality bar (hit@10 0.938; gate 12/13 refused at 64% retention); gte-small retrieves better (0.969) but is larger, and adopting it over a passing smaller model is the "adopted for headroom" r2 forbids. arctic rejected on retrieval (0.438); bge on score separation; e5 unmeasured (non-standard ONNX path, recorded) | Re-selection later on new evidence — the harness stays runnable |
| 129 | **The refusal gate is a two-feature rule, not a single cosine floor** | Measured: the best single global floor reached J ≈ 0.50 on every candidate; adding a peak-gap feature (top minus mean of rest — a flat profile is a nearest neighbour, not evidence) reached J 0.564 at 12/13 refusals. The owner's instruction explicitly authorized investigating a better deterministic rule if one cutoff was insufficient — it was | The threshold's permanence: constants live in `calibration.py` with provenance, revisable only by re-measurement |
| 130 | **Gate tuned for retention, precision delegated to claim verification** | At the gate a false refusal is unrecoverable while a false accept still faces citation verification — the asymmetry inverts by layer. Measured confirmation: the adversarial near-misses score inside the answerable distribution for every model, so no similarity feature separates them; only claim-level grounding can. This is `AM-29` r3's three-outcome design used as designed | The grounding overlap constant (0.5), which is a lexical-overlap floor for "could this text be the source", not a legal threshold — documented as such |
| 131 | **`chunk_embeddings` dimension is a DDL literal, not configuration** | A silently swapped model would write vectors incomparable with everything stored, and nothing downstream would notice. A migration is deliberate friction: model change = schema change = reviewed diff | Which ANN index to use at corpus scale — none created; per-document exact scan is lossless at ≤ hundreds of chunks |
| 132 | **The vector type AND its operator are schema-qualified from a live lookup** | Third instance of the same lesson (`gin_trgm_ops`, `similarity()`): extension objects live where the extension is installed, the harness pins `search_path` per run (`F-4`), and `OPERATOR("public".<=>)` beats widening the path | — |
| 133 | **Gemini adapter over stdlib urllib — no provider SDK** | `AM-30` left the client library as a separate rule-19 approval. stdlib HTTP needs no dependency at all, so the question never arises; the adapter is ~200 lines behind `AM-26` r1's single interface, and reverting to a local model stays a config-plus-file change | Adopting the SDK later if streaming/batching justify it — that is the rule-19 ask it always was |
| 134 | **The `AM-31` gate is a code constant + environment check, not a flag** | g3 forbids release by flag, env var or review — so `AM31_GATE` can only change in a reviewed diff landing alongside the appended lock record, and while CLOSED the adapter refuses production egress outright. g5's composition with 55.3 supplies the real/synthetic distinction: production is where real contracts live; dev/staging are synthetic-only | When the gate opens — that is the owner's written-terms action |
| 135 | **Every generation call writes an `audit_events` row (payload hash, model, prompt version)** | `AM-30` t5 says audit_events, and 53.1 says an operational log is never a substitute. First draft only logged; corrected. New event type, no schema change (`AM-27`) | — |
| 136 | **Compliance-shaped questions are routed by a conservative textual screen** | `AM-25` r4: "does this meet our standard?" belongs to the evaluator. False positives cost a pointer to the Review screen; false negatives are still caught by the prompt's rule 4 and verification. A classifier here would be a model deciding what reaches a model | The screen's recall — revisable with usage evidence |
| 137 | **One `assist.ask` permission, granted to USER / LEGAL_REVIEWER / LEGAL_ADMIN** | AB-3's registry entry pre-authorized "assist-lane access permissions only"; the three roles already hold document.view, and the Guard resolves the underlying contract before any retrieval. No legal-authority permission touched (`AM-25` r8) | — |
| 138 | **Conversations are creator-visible only, byte-identical 404 otherwise** | `AM-25` r7 + `API-10`: a conversation reveals which document someone asked about and what they asked — an existence oracle if distinguishable. Same normalization discipline as the S-7 login test | Sharing/collaboration semantics — a product question no record defines |
| 139 | **The refusal wording is a single constant every path converges on** | `AM-29` r4 verbatim; a drift is a one-line diff. The UI renders refusals on the quiet surface — the system working, not an error | — |
| 140 | **Frontend tests in the house static-render idiom; panel styles on existing tokens only** | The repo deliberately has no @testing-library (interactions belong to Playwright); and the design-system rule is exact-value tokens — my first draft invented five token names and was corrected against the real set | — |

**Verification at close: backend 893 passed · 1 skipped · ruff and mypy clean · frontend
62 Vitest + typecheck + production build · migration `c4a91f6e2d87` round-trips · live
end-to-end demonstrated on the real MSA (236 chunks embedded, gate OPEN/CLOSED as
calibrated, credential-less ask → identical refusal wording) · `EGRESS_ALLOWED` names
exactly one module · `AM-31` gate CLOSED.**


## A10 security hardening — dependency and container scanning, 2026-08-26 (owner instruction: keep the Gemini gate CLOSED pending Google's terms; continue safe remaining work; report exactly when input is needed)

`IMPLEMENTATION_READINESS_GATE.md` §5b unit A10 names five controls: network segmentation,
TLS, secrets, Trivy/pip-audit/npm audit, OpenVAS/ZAP. The first three are already reported
by `legalmind.deploy.preflight` as deployment-time properties, not repository checks. This
pass adds the two that a CI runner can actually exercise, as CI job 14.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 141 | pip-audit and npm audit block CI on **any** finding, not just high/critical | Both were measured before the job was written — zero known vulnerabilities across backend (`pip-audit --desc` against an editable install of `pyproject.toml`) and frontend (`npm audit`, 161 packages, prod+dev+optional). Matches job 1's own precedent: ruff/mypy block at a *measured* zero baseline rather than an invented tolerance | The severity split used for Trivy — a different tool scanning different material, reasoned separately below |
| 142 | Trivy image scanning blocks only CRITICAL/HIGH (`ignore-unfixed: true`); MEDIUM/LOW are reported, not blocking | Unlike pip-audit/npm audit, an image scan also covers the base OS (`python:3.12-slim`, `node:22-alpine`), which this repository does not pin package-by-package. Blocking on a LOW finding with no available fix converges to the job being disabled rather than the finding being fixed — the same "the gate must be real" reasoning argues for scoping it here, not against a gate at all | Nothing is silently dropped — MEDIUM/LOW still runs and still prints, `if: always()` |
| 143 | OpenVAS and ZAP are **not** added to CI; deferred to the deployment pipeline | Both scan a *running* instance. Standing one up inside this workflow means orchestrating Postgres + Redis + the API + the frontend as CI services — a materially larger change than an additive scan step, closer to "add a new CI service" than "check what the repository already contains." Treated like TLS and backup-restore in `preflight.py`: an ATTEST-shaped deployment control, not a repository check | Whether they are used at all — both stay named in A10 and belong in the release pipeline once a staging environment exists to point them at |
| 144 | Both Dockerfiles are built inside CI for the first time, as a side effect of the Trivy job | Neither image had ever been build-tested by CI — a broken Dockerfile would previously ship unnoticed until someone deployed it. Scanning required building, so this closes a real gap rather than adding one | Nothing about deployment orchestration, still NOT YET SPECIFIED (55.6) |

**Local measurement could not cover Trivy itself**: this sandbox has no Docker daemon, and
installing one (or piping a third-party install script through `sh`) is outside what this
pass should do unilaterally. The pip-audit and npm audit baselines above were measured
directly; the two image-scan steps are written against the well-known, version-pinned
`aquasecurity/trivy-action@0.29.0` and will report their first real result on the next CI
run — the same "cannot be checked from inside the application" honesty `preflight.py`
already applies to TLS and encrypted storage.

**Verification at close: `.github/workflows/ci.yml` parses (14 jobs); pip-audit 0 findings;
npm audit 0 findings (161 packages); no existing job modified; no schema, dependency-list,
or `all_lock.md` change.**


## A9 measurable half + A10 network segmentation, 2026-08-26 (same owner instruction: gate stays CLOSED, continue safe work)

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 145 | **`AM-28`'s Tier-2 gate becomes a runnable command** (`tools/verify_assist_quality.py`) blocking on exactly what the locked sentence names — the wrongly-answered rate; recall/retention regressions WARN but do not block | The gate text is specific: *"worsens faithfulness or the wrongly-answered rate does not ship."* Blocking on recall too would widen a locked gate on my own authority; not running the gate at all leaves it a convention (`preflight.py`'s own warning: a register nobody runs is an implicit assumption with extra steps) | Faithfulness's blocking role — it joins when generation on real material is possible (`AM-31`); the baseline file carries the placeholder |
| 146 | **The gate measures the SHIPPED path, not a mirror**: every question runs through the production `search_hybrid` (real SQL, real RRF, real `gate_is_open`) against a DB populated by the production `ingest_document` → `index_document_version` | The calibration harness ranks from an in-memory cache because it compares uninstalled candidates; a release gate has the opposite job. A re-implementation here would drift from the product exactly when the product changed — the case the gate exists to catch | Nothing about the calibration harness, unchanged and still the tool for comparing candidates |
| 147 | **Baseline recorded from live measurement, in the repo as numbers + hashes only** (`tests/assist_eval/baseline.json`: 12/13 refused, 41/64 retained, recall@10 0.438) — and the gate was **proven to fail** (tightened baseline → exit 1, restored → exit 0) | 54.6 permits numbers; a baseline that cannot be diffed makes "worsened" an argument instead of a fact. A gate that has never failed is not known to be a gate — the same discipline the full-suite CI job was verified with | Re-baselining, which is `--write-baseline`: a deliberate, reviewable act, never automatic |
| 148 | **End-to-end recall@10 0.438 investigated before being baselined** — decomposed: of 13 gate-open misses, 12 are the expected chunk found by vector in top-10 but **below the 0.50 floor** (the shipped "sub-floor hits are never evidence" rule), 1 a genuine rank>10 miss | A release baseline recording a harness artifact would hold the product to a bug. It is design, measured: the floor trades recall for never presenting sub-floor text as evidence, and the claim-level guardrails carry precision (#130's layering, seen from the other side) | Whether the floor should move — that is a re-calibration through this very gate, on evidence, not a hand adjustment |
| 149 | **The gate database persists between runs; only `public` + `assist` schemas are dropped** — pgvector lives in a dedicated `extensions` schema created once by an operator | Recreating the DB per run would demand superuser per run (`vector` is untrusted), the exact privilege posture 55.2 forbids. All application SQL already resolves the extension's schema at run time (the F-4 lesson), so the location is immaterial; the tool prints the one-time setup verbatim when it is missing | Production provisioning, still preflight's register |
| 150 | **Preflight gains `tier2_quality_gate` (ATTEST)** naming the runner, mirroring 55.5's reproducibility-gate row | Same reason verbatim: a release-pipeline act the preflight cannot run but must name — an unexamined gate is not a satisfied one. Register is now 22 checks (the documented "18" predated the assist rows; corrected against a run, not a memory) | — |
| 151 | **Compose splits `data` (internal: true) from `edge`** — db, queue, both workers on `data` only, so the whole document-processing path has NO route out; api on both (it holds the one permitted egress); frontend on `edge` only | `AM-30` t1 as a routing table rather than a promise: a worker that tried to egress has nowhere to send the packet. Free alignment: 38.22 (frontend never touches the database) becomes a network fact. Compose can remove routes but not enumerate destinations, so t8's full allow-list honestly remains production infrastructure | The production firewall/security-group design — deployment, per 55.6's NOT YET SPECIFIED hosting rows |
| 152 | **Model weights reach containers by read-only mount, never by download** (`LEGALMIND_MODEL_DIR` + `:ro` volume on api and worker-assist) | Consequence of #151 the compose file must resolve, not hide: the data network cannot download anything, and `AM-26` r5's locally-checksummed weights were already the rule — the mount makes the compose reference actually work instead of silently degrading to lexical-only | — |

**Verification at close: backend 894 passed · 1 skipped · ruff and mypy clean · gate tool
SKIP=0 with no source material, FAIL=1 with material but no model, exit 1 on a tightened
baseline, exit 0 on the recorded one · compare mode reproduces the baseline exactly ·
compose YAML validates with the intended service→network mapping · `AM31_GATE` still
CLOSED · `all_lock.md` untouched.**


## Browser suite run by hand → two latent breakages found and fixed, 2026-08-26

Writing a Playwright spec for the Ask surface meant running the suite — which had not run
since Phase 3.5 (2026-08-24) landed, because CI triggers only on `main`/PRs and all work
sits on a feature branch. It failed 13/22, every failure on the core Review screen.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 153 | **Fix the Review-screen crash by moving `useRef` above the early returns** — a hooks-order violation (React #310) introduced 2026-08-24 by the sticky-queue code-review fix; a scan of every page/component found no second instance | The first render has no `reviewId` and returns early, so a hook below the returns is skipped, then called on the next render. Typecheck and build cannot see it; only a browser can — and no browser run had happened. The one-line reorder changes no behavior the DD-1 screen decided | Nothing about the screen's design or the sticky-queue semantics, both preserved |
| 154 | **CI runs on every branch push**, not only `main` | Five days of commits ran zero CI jobs — long enough for the core screen to ship broken. `concurrency: cancel-in-progress` already bounds the cost to one run per push. A gate that cannot observe the branch where work happens is not a gate | Branch protection or merge policy — the owner's |
| 155 | **Harnesses provision pgvector best-effort; migrations still never do** (`tools/pg_extensions.ensure_vector_extension`, wired into conftest, the e2e bootstrap, both verifiers and the benchmark) | Every fresh-database harness died at `c4a91` the day it landed, hidden locally by long-lived databases that already had the extension. The migration's refusal is a PRODUCTION stance (55.2: the app role never holds superuser); a test harness satisfying its own precondition in a container where the role IS superuser weakens nothing. Where it cannot, it prints the operator step and the migration's authoritative error follows | The production precondition — still `preflight`'s register |
| 156 | **The Ask surface gets a browser spec asserting the pre-key state** — both refusal causes render the identical `AM-29` r4 sentence, no error banner, no "confidence" on the composed page | The API and static-render tests each prove a half; only the composed page under the real deployment posture (no credential — production until `AM-31` opens) proves the whole. The wording constant is asserted verbatim so drift in either repository fails here | — |

**Local one-time host step recorded:** `CREATE EXTENSION vector` in `template1`, so every
future locally-created database inherits it — the local analogue of the CI container role
being superuser. Reversible (`DROP EXTENSION` in `template1`); affects only this dev host.

**Verification at close: Playwright 27/27 (4 setup + 22 original + the Ask spec) · Vitest 62 ·
typecheck clean · backend 894 passed / 1 skipped · ruff and mypy clean · the 54.6 archive
guard correctly flagged the failed run's `trace.zip` artifacts, which were removed.**


## First CI runs on the branch → three corrections, 2026-08-26

The new every-push trigger produced the branch's first two CI runs (`32966768966`,
`32967405693`). Both were informative.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 157 | **Both images apply distro security upgrades at build time** (`apt-get upgrade` before installing the OCR toolchain; `apk upgrade` in the frontend runtime stage) | Job 14's first real scan found the backend image shipping `libssl3t64`/`openssl`/`openssl-provider-legacy` 3.5.6 with 3.5.7 already published — CVE-2026-14456, HIGH, three rows, one fix. The base tag floats behind Debian's security releases; upgrading at build measures the image against today's fixes instead of the tag's build date. Reproducibility is not worsened: the base tag already floated | Pinning base images by digest — a reproducibility/security trade-off worth its own decision, not made here |
| 158 | **The Ask spec's evidence-present question is a strict subset of the fixture sentence** | Lexical search ANDs every stemmed term; two words the fixture lacked ("clause", "say") made the first version depend on the vector branch, which exists locally and not in CI. A spec must prove the same thing everywhere it runs — reproduced locally under `LEGALMIND_MODEL_DIR=/nonexistent` before pushing | — |
| 159 | **Trivy pinned to `v0.36.0`** (tags are v-prefixed; `@0.29.0` did not resolve) | Latest release; the five inputs used have been stable across versions | — |

**Confirmed by those runs, not merely reasoned:** the fresh-database harness fix (#155) works
in container-fresh CI databases — jobs 2, 11, 12, 13 all green; job 10 (Playwright) green
in CI after the spec correction; jobs 6–8 skip on push by design (they diff against a PR
base). pip-audit and npm audit steps both passed in CI, matching the local zero.

The third run (`32968085103`) passed the backend scan after #157 and gave the **frontend**
image its first scan: Alpine clean, every `app/node_modules` package clean, and **9
CRITICAL/HIGH in the Node runtime's bundled npm** (`tar` gzip-bomb DoS, `sigstore`
certificate acceptance, `brace-expansion`/`picomatch` ReDoS, `ip-address` parsing) — none
ours, and invisible to `npm audit`, which only sees the lockfile.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 160 | **The frontend runtime image carries no package manager**: after `npm ci --omit=dev`, npm, npx and yarn are deleted, and Next is started with `node node_modules/next/dist/bin/next` | A serving image needs `node` and nothing else; npm and yarn each bundle a dependency tree that is attack surface with no job. Deleting them removes the whole finding class instead of chasing versions — the same reasoning as #157, one level up. Verified locally that Next's bin runs directly under `node` | Next's `standalone` output mode — a larger build-shape change that would achieve a similar minimal image; not needed to close the finding |
| 161 | **The Playwright trio is removed by name from the runtime image** | It survives `--omit=dev` because Next declares `@playwright/test` an optional peer and the root a devDependency; npm records the union as `devOptional`. Measured: `--omit=peer` does not remove it, and `--omit=optional` would also strip Next's SWC and sharp platform binaries. Not a scan finding (0 vulns today) — hygiene: a browser-automation framework in a serving image. Verified locally that Next runs without it | — |


## Backend first, UI later — closing the API contract for a new UI, 2026-08-26

Owner directive: *"Backend first. UI/UX later. Preserve the existing UI code but treat its
previous design as obsolete for planning... When the backend/API architecture is genuinely
ready to support a new UI/UX implementation, stop and tell me clearly."* The readiness audit
mapped every surface a workspace UI needs (document pane, verdict cards, chat panel with
history, configuration/audit/admin) against the running API and found four contract gaps,
all additive and all inside existing permissions.

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 162 | **`GET /conversations`** — the caller's own conversations, newest first, `contract_id` the one filter, paginated | A workspace shows a document's history; without a list the UI could only re-open ids it had cached in the browser. Creator-only scope identical to the single GET (49.6 r4) so the list can never become the enumeration oracle `AM-25` r7 forbids | Sharing or visibility beyond the creator — a product question no record defines |
| 163 | **`GET /conversations/{id}` replays citations** — rebuilt from `answer_citations` × the chunk's evidence row × the retrieval run's per-chunk score, and compared field-by-field against the live POST shape in a test | `AM-25` r5 binds every *view* of an answer, not the first; before this a reload lost every citation. The score is read from the run, not the chunk — a retrieval score is a property of the query (the same reasoning that put it on `retrieval_runs` in the first place) | — |
| 164 | **`GET /document-versions/{id}/evidence`** — paginated Evidence rows in reading order under `document.view`; not in 49.3's table, recorded as an implementation addition in Step 49's new record section | The document pane and every citation target need the text the pipeline read, with page and offsets (the locked Evidence model's whole purpose). Seeing the version and seeing what was extracted from it are one act under one permission; 49.0 excludes endpoint naming from the lock. Lineage (`processing_run_id`) and parser metadata stay server-side | Nothing about rendering the original bytes — `/content` is unchanged and still `document.download` |
| 165 | **`assist_index: {chunks, embedded_chunks}` on the document version** — counts, not an enum | A UI must know whether a version is searchable; counts let it derive ready / lexical-only / not-indexed. Deliberately not a new state vocabulary: `AM-29` r1 keeps the assist lane to one axis, and an index-readiness enum would be a second by another name | — |
| 166 | **The contract is frozen as `docs/api/openapi.json`, drift-tested** (`tools/export_openapi.py`, `test_the_committed_openapi_snapshot_matches_the_app`) | "Finalized backend contracts" must be an artifact a UI phase can design against and a reviewer can diff. Serving OpenAPI stays off by default (49.12 / 47.7 posture); freezing it is a different act. Step 49 wins any disagreement — the snapshot is derived, never the specification | — |

**Readiness call (mine, for the owner to confirm):** the backend is ready for the UI/UX
phase. Every workspace surface has a stable, tested, frozen contract — auth (password), contracts
and document versions (metadata · download · evidence · index counts), reviews and async
analysis, findings/evaluations/decisions/escalation (locked 49.7), report, configuration
browse/draft/publish, audit, admin, and assist conversations with the three refusal states and
evaluator routing. **Four surfaces stay owner-gated and must be designed as placeholders**:
Domain A/C *search* (C-15 amendment + C-16 statutes; browsing Domain A as configuration is
available), OIDC (49.2 specifies the redirects; implementation needs a rule-19 dependency
approval + RIAAS details), export (`POST /reviews/{id}/export`, formats NOT YET SPECIFIED),
and the generated-answer text (`AM-31` gate — the response *shape* is final; only whether
text or the identical refusal comes back changes).

**Verification at close: backend 901 passed / 1 skipped · ruff and mypy clean · frontend
typecheck + 62 Vitest untouched and green · `docs/api/openapi.json` regenerated (45
operations) and `--check` clean · `all_lock.md` untouched · `AM31_GATE` CLOSED.**


## Owner-directed gap-closing pass — five phases, 2026-08-27

Owner directive: close all remaining gaps end-to-end, dependency-ordered, with the
explicit statement *"UI/UX work is authorized to start in parallel"*. Two items in the
directive's task list cannot be completed without violating our own locks and were
delivered up to their gates instead: the C-15 tables (built only after the owner reads
and approves the draft) and the AM-31 gate (opens only on the recorded written-terms
confirmation).

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 167 | **The 2026-08-27 directive is recorded as the UI/UX greenlight** — the owner had reserved that call ("I will explicitly decide when UI/UX starts") and this message grants it, alongside "use ui-ux-pro-max, ignore the old design as source of truth, design against the frozen contracts" | The reservation and the grant are both owner statements; the later one governs. Recorded so no future session re-asks | Nothing about scope or schedule of the UI phase beyond its start |
| 168 | **The AB-5 draft (`AM-32`) proposes NO positions content table** — position chunks reference `company_standard_versions` directly; per-domain embedding tables instead of one polymorphic one; and Domain A output is EXTRACTIVE-ONLY, never included in a generation payload | The ratified standards are already the source of truth (a copy is the AM-27 r4 defect); 42.1 requires real FKs, which polymorphism breaks; and AM-30 t3 forbids any Company Standard value in an egressing payload — the extractive-only rule is a locked consequence surfaced, not a new restriction | Whether AM-32 is approved at all — the owner's; C-16, untouched |
| 169 | **`tools/verify_gemini_connection.py` goes through `generation.generate()`, the one permitted seam** — config-only by default, one fixed synthetic call with `--live`, key value never printed | AM-26 r1: a second egress path in a tool would bypass the gate, the payload screens and the audit rule; the seam applies them all to the tool for free. Synthetic-only text satisfies 55.3 in every environment | Opening the gate — g3's appended record only |
| 170 | **Preflight gains `egress_allow_list` (ATTEST, register now 23)** naming the exact posture: api → generativelanguage.googleapis.com:443 only, deny-by-default, proven by network-level probes | AM-30 t8 says asserted by a test "not by configuration review alone", and the application cannot see the firewall — so ATTEST, never a self-awarded PASS. It was the one operator item on the owner's Phase-9 list with no register row | The production firewall design — deployment's |
| 171 | **No `tools/preflight_production.py` was created; `ops/README.md` documents around the existing register instead** | A second register duplicating `legalmind.deploy.preflight` would drift from the first exactly when it mattered — the same reasoning that froze the OpenAPI snapshot as derived-not-parallel. The runbook maps every operator step to its named row | — |
| 172 | **Gated surfaces split into disclosed placeholders vs absent capabilities** — Domain A/C search render a calm `DomainPlaceholder` (their existence is public product direction); SSO and export render NOTHING (52.4's absence discipline); the generated answer needs no placeholder because the live refusal state IS production behavior | The placeholder/absence line is a disclosure question, not a style one: an affordance for an unbuilt capability discloses it. Copy is fixed in one component so every screen says the identical thing | — |
| 173 | **Skill-vs-DESIGN.md conflicts resolved by precedence and reported** (rule 5): the landing-page pattern, the navy/gold brand palette and the EB Garamond display face were rejected — DESIGN.md/DD govern; density 8, motion 2 and the accessibility checklist were adopted | CLAUDE.md's UI-skills section fixes the order: skills advise, DD decisions win, conflicts are reported not silently resolved | No DD entry is amended |

**Verification at close: backend 911 passed / 1 skipped (+9 gemini-tool, +1 preflight) ·
ruff and mypy clean · frontend typecheck + 68 Vitest (+6 placeholder) · preflight
register verified 23 by running it · `AM31_GATE` CLOSED and untouched · `all_lock.md`
untouched (the AB-5 text is a PROPOSAL document, appended only on approval).**


## AM-32 approved and implemented; six conflicts closed by owner ruling, 2026-08-27

Owner rulings (verbatim): "AM-32 approved" · "Code list authoritative maano, doc update
karo" (C-10) · "Permission checks server-side strict hain - code ko follow karo.
Documentation update karo." (C-08) · "Annotations add karo, lines edit mat karo (rule
22)." (C-05/06/07). All recorded alongside AB-5 in `all_lock.md` (16,385 → 16,494
lines, prior lines byte-identical).

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 174 | **`retrieval_runs`' per-domain references live inside its JSONB `results` entries (a `domain` key), not as new FK columns; the FK columns land on `answer_citations`** (nullable per-domain ids + CHECK exactly-one, `chunk_id` relaxed to nullable) | AM-27 designed `results` as a no-FK diagnostic record (dangling ids explicitly tolerated); AM-32's "FK references" is honored where referential integrity has a job — verified citations. Adding FK columns to a table whose own design rejects them would contradict the older record to satisfy a word of the newer one | Nothing about the diagnostic record's tolerance for dangling ids — unchanged |
| 175 | **Domain A chunk content is composed from the ratified file's verbatim fields** (code · source_clause · document_type · source_document · source_quote), chunked from `config/company_standards/` and FK-linked to the *imported published* `company_standard_versions` row; a file with a missing field or no imported row REFUSES, never skips | r3 makes the DB row the reference and the ratified file is where the verbatim quote lives (the DB `configuration` deliberately carries evaluator values only); a silently-skipped position would be a search surface lying about coverage; rule 21 forbids inventing the missing text | The quote's presence in the file — supplied configuration, owner-ratified 2026-08-19 |
| 176 | **The authorized-tables tripwire now expects AM-27's nine + AM-32's five, and the judgments slot stays a tripwire** — a judgments table appearing before its own record fails `test_only_authorized_tables_exist_in_the_assist_schema` | The test did its job (it failed the moment the migration ran, until the authorization was recorded in it); the reserved slot must keep the same teeth | — |
| 177 | **Domain A search is lexical-first** (`ts_rank` over the tsvector, trigram available); the shared embedding machinery joins in a later increment | 32 single-chunk positions are a small, keyword-dense corpus where lexical is measurably sufficient to start, and r9's Tier-2 questions (which gate shipping) don't exist yet; wiring vectors first would be optimization ahead of the gate that measures it | r9's evaluation-set requirement — still owed before Domain A ships to users |
| 178 | **Concurrent session's in-progress frontend work observed and left untouched** (KeyboardShortcuts/Skeleton/DESIGN.md/UI_UX_MASTER_PROMPT.md, mid-edit with typecheck failing); this commit stages only the AM-32/conflicts files | Rule 23: assume concurrency, never clobber or duplicate. The frontend failure is theirs mid-flight, not a regression in this work — backend 935 green, and the committed tree excludes their uncommitted files | Their UI direction — including how their "cancel all previous UI/UX decisions" directive relates to WORKSPACE_UI_PLAN.md; to be reconciled when their work lands |

**Verification at close: backend 935 passed / 1 skipped (+9 positions, +15 net) · ruff
and mypy clean (95 files) · migration `d7e2a9c41b58` round-trips (upgrade → downgrade →
upgrade) · locked-schema snapshot tests pass unmodified (AM-27/AM-32 r2's evidence) ·
OpenAPI drift clean (no API change) · `AM31_GATE` CLOSED · `all_lock.md` 16,494 lines,
append-only.**


## UI/UX execution, Phase 4/5/7 hardening — 2026-08-27 (owner: implement the final missing pieces, prepare for usability testing)

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 179 | **Skeletons reconcile the owner's shimmer request with DESIGN.md's shimmer caution**: functional, layout-shape-matched, few shapes (2–3, never a page of phantom rows), static under `prefers-reduced-motion`, `aria-hidden` over the existing `aria-live` text announcement | DESIGN.md's anti-pattern targets *decorative* shimmer and skeletons that "imply content that then contradicts a valid empty state" — a shape-matched loading stand-in whose empty case the caller already renders separately is neither. Owner instruction and design rule both satisfied, conflict resolved in the open (rule 5 spirit) | — |
| 180 | **The Ask skeleton carries ONE honest status line, not the mockup's staged sequence** | The client sees a single request; a timed "searching → verifying" progression would claim knowledge of pipeline progress it does not have — invented staging is the "urgency theater" DESIGN.md forbids, applied to waiting. The mockup's staged version is real only if the API ever streams stage events | Adding real stage events later — an API change, decided then |
| 181 | **The requested "document preview (PDF render)" skeleton has no surface to attach to, and none was invented** | Document bytes are deliberately served `attachment`-only, never rendered in the app's origin (34.16 posture, documents.py) — there is no in-app PDF render to load. The three real async surfaces (review list, findings, Ask answer) got the skeletons | Building an in-origin document viewer — a real feature decision with a security dimension, owner's call |
| 182 | **`a`/`r` prepare a decision, never record one** — preselect type + focus the mandatory justification; a browser test proves zero `POST /decisions` from any keyboard path | A single keystroke must not complete a legal act. Step 31 r11's mandatory justification makes this structural; the shortcut design aligns with it instead of fighting it. Shortcuts are also inert while typing — a justification containing "a" must not steer the form | — |
| 183 | **The 409 conflict now freezes the form until an explicit refresh** — replacing the previous automatic re-fetch; the e2e spec was extended to walk the full loop (real 409 → disabled submit → explicit refresh → form shows what won) | The auto-refetch shifted the ground under a decision-maker mid-read; 52.7's "the user must re-read before deciding again" is only real if the re-read is the user's own act. Owner's banner wording adjusted from "This review was..." to "This Evaluation was..." — the colliding object is the Evaluation's decision chain, and the UI must not misname the legal object | Nothing about the server's 409 semantics — untouched |
| 184 | **Visual regression is gated behind `DESIGN_QA=1`, outside the default e2e run** | Default-suite specs share one database, so a screenshot's row counts would depend on spec ordering and grow with the suite. Under the gate the DB is freshly bootstrapped and only the visual spec runs — baselines proven to reproduce across two full rebuilds before being committed. Threshold 0.1% per the owner's instruction; volatile ids/dates masked, not cropped | Baseline regeneration policy beyond "deliberate, reviewed like any diff" |
| 185 | **The forbidden-terms gate strips comments and exempts test files — and was proven to fail before being trusted** (planted violation → exit 1, file:line named → removed) | A comment *forbidding* the word is the rule, not a violation; a test may assert absence. The dangerous survivors — string literals, JSX text, identifiers — all outlive comment-stripping. Terms per owner: confidence, risk_score, ai_confidence, probability, likelihood | Backend sources — rule 12 is enforced there by review and existing tests; this gate covers the surface users see |
| 186 | **`npm run lint` = typecheck + forbidden-terms; no ESLint added** | The owner's task list invokes `npm run lint`, but no linter dependency exists and adding one is a rule-19 approval, not something to smuggle in via a task list. The script runs the two static gates the project actually has; adopting ESLint is flagged as the approval it always was | Whether to adopt ESLint — owner's rule-19 call |

**Verification at close: frontend 79 Vitest (+11) · typecheck clean · `check:terms` clean
and proven to fail on a violation · browser suite 30 passed / 8 gated (full run, includes
the new keyboard spec and the extended conflict loop) · visual baselines reproduce across
two full DB rebuilds · backend 935 passed / 1 skipped re-verified after AB-5's migration
landed mid-session · CI 15 jobs, YAML validated · docs screenshots regenerated from the
real app against synthetic fixture data.**


## UI/UX implementation, slice 1 — 2026-08-30 (owner: "UI/UX IMPLEMENTATION — GO")

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 187 | **`GET /contracts/{id}` gains `document_versions` (newest first)** — the one smallest-justified backend change of the slice | A document-anchored workspace opened on a contract had no API path to its document: nothing listed versions, and the legacy page only ever showed the version it had just uploaded. Additive, the same `contract.view` permission, the existing version-serializer shape; the frozen contract's only diff is the operation description. Detail endpoint only — the list stays lean | Nothing about the version resource itself; `assist_index` still lives on `GET /document-versions/{id}` |
| 188 | **The new application lives under `/workspace` with its own shell; `Chrome` yields there** | The two shells must never render together, and legacy screens must stay green as the verification harness until each is retired. One `startsWith("/workspace")` branch after the session check gives the new app its shell while the legacy chrome still guarantees authentication above it | When each legacy route retires — per slice, with its Playwright guarantees re-pinned |
| 189 | **Foundation on the system font stack; the master prompt's type *roles* kept** (mono = precise values, italic serif = verbatim text) | DD-7 §6: runtime CDN fonts are ruled out and bundling awaits the owner's rule-19 approval. The roles carry the meaning; the faces are swappable tokens | The bundling approval itself |
| 190 | **`NextSlice` is a separate primitive from `DomainPlaceholder`** | Two different truths: "the UI hasn't built this yet" (a sequencing fact, pointing at where the job is done today) vs "the backend does not offer this" (a capability fact). Conflating them would either overstate what's blocked or understate it | — |
| 191 | **The highlight target is an evidence-row id, carried in the URL** | Every source in the system already shares that unit (a Finding's `evidence_refs`, a citation's chunk → evidence row, the `/evidence` rows), so verdict-click and citation-click become the same gesture with no new endpoint; the URL form makes a citation shareable. Row-level lighting now; sub-span marking is a later refinement, not a different mechanism | — |
| 192 | **The skip-link test asserts tab order structurally and exercises the link directly** | Headless Chromium never moves focus off `<body>` on the very first synthetic Tab of a fresh page (measured: `activeElement` stayed `<body>`), so "press Tab, expect focus" tests the harness, not the product. The two real properties — first in DOM tab order, and Enter lands focus on `#ws-main` — are asserted instead | — |
| 193 | **The five legacy visual baselines were re-cut locally — and that was WRONG; corrected the same day** | At the time: design-qa failed on the four authenticated legacy pages, the diff images showed changes only on italic text runs, and I read that as session-to-session font drift and re-cut the PNGs after review. The real cause (found by the parallel session when CI job 15 failed on 4 of 6 surfaces): those baselines were **CI renders** from `0028b52`, and this box renders fonts ~1% differently and has the embedding model present, so text metrics and page heights differ from CI. A locally-cut baseline encodes the machine, not the product. The peer session re-adopted CI's renders (`691b72d`) and added a guard refusing `--update-snapshots` outside CI (`079f901`) | **Standing rule (owner, via session legalmind-v1-ea, 2026-08-30): baselines come from CI only** — commit the test, let job 15 fail once, adopt the `*-actual.png` from its `visual-regression-diffs` artifact (procedure in the job's comment). The `workspace.png` I cut locally needs the same treatment |

**Verification at close: backend 936 passed / 1 skipped · frontend 86 Vitest · typecheck
clean (after `next typegen` — the running dev server's stale generated route types were the
only failure) · `check:terms` clean · browser suite 37 passed / 9 gated (11 new workspace
tests, including the highlight from outline and from a shared link, the byte-identical
not-found story, tab collapse and the skip link) · six visual baselines reproduce ·
OpenAPI snapshot regenerated (one description line) · `AM31_GATE` CLOSED.**


## Strict frontend cleanup — new UI is the entire post-login experience, 2026-08-30

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 194 | **`navItemsFor` gates on EXISTENCE as well as permission** — an item appears only once its destination is a real new-UI screen; today that is Documents alone | The literal bug the owner's cleanup targeted: the shell's own nav still mapped "Documents" to `/contracts` and offered a live "Reviews" link into the legacy queue — an active navigation path into the retiring application, from code I wrote. Removing the destinations rather than patching the two hrefs, so the next slice adds its nav item in the same change that ships the screen, never before | Whether Reviews/Legal/Audit/Admin get new-UI screens — the roadmap already sequences that |
| 195 | **`NextSlice` carries a plain-text note, never a link** | It previously linked into `/reviews` and `/contracts/{id}` — exactly the pattern being removed. The capability isn't gone (the text says the legacy app still works); there's simply no click path to it from here, which is the letter of "remove access, not functionality" | — |
| 196 | **The empty-workspace "upload" affordance is now a real inline upload**, not a link to the legacy contract page | The alternative was removing upload capability from the new UI entirely, which the owner explicitly forbade ("not asking you to delete backend functionality"). The call was always real (`api.uploadDocument`); only the button pointed at the wrong screen | — |
| 197 | **Legacy routes are left in place, unredirected, reachable only by direct URL** | Every legacy Playwright spec (`decision.spec.ts`, `analysis.spec.ts`, `confidentiality.spec.ts`, etc.) navigates via `page.goto()` directly, never through a clicked nav link — confirmed by grep before touching anything. Redirecting the routes themselves would break the harness the owner explicitly said to preserve; removing the nav path (already the actual ask) does not | Retiring a legacy route — happens per-slice as its replacement ships, per the existing plan |
| 198 | **`Chrome`'s new-UI bypass covers `/` as well as `/workspace`** | Not a styling call: `Chrome`'s loading/signed-out branches never render `{children}` at all, so `/`'s own redirect-only page component never mounted for a signed-out visitor and the redirect silently never fired — found by testing the actual behavior, not assumed | — |
| 199 | **`/` uses `useRouter().replace()`, not the Server Component `redirect()`** | Measured with `curl -I` against a production build: this Next.js version (16.3.1) returns `200` with no `Location` header for a plain `redirect()` call in a streaming page — it encodes the target in the RSC flight stream, which did not complete through this app's provider tree in browser testing either. `login/page.tsx` already uses `router.push()` successfully for the identical need; followed the pattern proven in this codebase over the one measurably not working here | Nothing about `redirect()` elsewhere — no other page in this app relies on a bare Server Component redirect for full navigation |

**Verification at close: frontend 88 Vitest (+1) · typecheck clean · `check:terms` clean ·
browser suite 40 passed / 9 gated (three new specs: no legacy link anywhere in the new
UI, login lands on `/workspace`, Documents index links only into `/workspace`) · backend
936 passed / 1 skipped, untouched · `grep` swept clean for every `href="/contracts"`,
`href="/reviews"`, `href="/admin"`, `href="/audit"`, `href="/configuration"` under the
new UI's source before closing.**


## UI/UX slice 2 — the Findings pane, 2026-08-30

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 200 | **`api.reviews()` widened to pass `contract_id`** — an existing, already allow-listed backend filter (49.6), only newly exposed in the frontend client | The workspace has a Contract and a DocumentVersion but no Review of its own; resolving one by `document_version_id` needs to list a contract's reviews first. Zero backend change — the filter already existed and was already tested server-side | — |
| 201 | **No Review yet is a named, plain-text state — no id-pasting form, no link into the legacy app** | Creating a Review needs a published configuration snapshot, a distinct capability with its own UX question (which snapshot?) the roadmap does not scope into "the Findings pane." The legacy page's own answer to this (raw text inputs for a document-version id and a snapshot id) is not a bar worth carrying into the new UI, and linking to it would reopen the cleanup just closed | Review creation's eventual UX — a later, separate slice |
| 202 | **Axis chips are filled only for a non-calm value** (`MATCH`/`ACCEPTABLE`/`NOT_APPLICABLE` render as a quiet ghost chip; everything else in that axis renders filled at equal weight) | DESIGN.md's own rule: Tier-1-adjacent classifications must never be styled as if one is worse than another. A uniform filled/ghost split by "is this the calm value" avoids inventing a severity ranking while still surfacing the axis that matters | — |
| 203 | **`DecisionControl`'s conflict-refresh explicitly resets local `outcome` to idle** | Caught in review before any test ran: the first draft called `onRecorded()` (the parent's re-fetch) but never reset its own `outcome` state, which is component-local and survives a prop update — the form would have stayed frozen after the FIRST conflict forever, even once fresh, non-conflicting data arrived. Fixed by mirroring the exact pattern already proven in the legacy hardening pass (`refreshAfterConflict`) rather than inventing a new one | — |

**Verification at close: frontend 90 Vitest (+2) · typecheck clean · `check:terms` clean ·
browser suite 43 passed / 9 gated (+3: chip rendering + evidence-highlight, decision +
409-freeze-and-recover, escalation-is-quiet) · backend 936 passed / 1 skipped, untouched ·
first full run of the new Findings-pane e2e specs passed without a debugging cycle.**


## UI/UX slice 3 — the Ask pane, 2026-08-30

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 204 | **Citations carry `evidence_id`** (live and replayed) — the one backend change of the slice | The workspace's highlight is keyed on evidence-row ids because that is the unit a Finding's `evidence_refs` already use; a citation carried only `chunk_id` (an assist-schema table), so the Ask pane had no way to point at the document. The value already existed on `SearchHit` and in the replay SQL's join — it was serialized, not computed. Dict payload, so the frozen contract is unchanged; recorded in Step 49's additions section | Nothing about chunk↔evidence semantics — one chunk still derives from exactly one evidence row (`AM-27` r4) |
| 205 | **The evaluator-routed reply is a visibly distinct third message type** ("Not answered here", dashed edge) — not styled as an answer and not as a refusal | `AM-25` r4 routes "does this meet our standard?" to the deterministic evaluator. Rendering that as a refusal would tell the user the document lacks the answer (false); rendering it as an answer would present a pointer as content. It is a redirection, and it reads as one | The routing screen's recall — server-side, revisable on usage evidence (#136) |
| 206 | **The ANSWERED path is pinned by static render, not end-to-end, and the report says so** | No generator credential exists in CI or production until the `AM-31` gate opens, so a browser cannot observe an answered turn; faking one (a stub server, a mocked response) would test a UI against a backend behavior that does not exist. The static test pins the contract the browser will meet the day the gate opens (`data-evidence-id`, the score label, no "confidence") | — |

**Verification at close: backend 936 passed / 1 skipped (assist suite 28, replay-parity
key extended with `evidence_id`) · frontend 94 Vitest (+4) · browser 45 passed / 9 gated
(+2 Ask specs, first-run green) · typecheck · `check:terms` clean · OpenAPI `--check`
clean · `AM31_GATE` CLOSED.**


## UI/UX slice 4 — Documents landing and intake, 2026-08-30

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 207 | **The document type is REQUIRED in the UI although the API accepts a contract without one** | Owner Q9: declared, never inferred. An undeclared type is accepted by `POST /contracts` and then fails at analysis (`ANALYSIS_FAILED`); refusing at the door, with the reason beside the field, is the same rule enforced earlier and more kindly. Presentation stricter than the contract, contract untouched | Whether the API should also require it — a 49.3 change, owner's call |
| 208 | **"Add and open" navigates straight into the new document's workspace** | Intake is one act: name and type here, upload there (slice 1's empty state), findings and questions in the same place. Returning to the list after creating would make the user find the row they just made | — |
| 209 | **The Step 6 vocabulary is a presentation COPY guarded by a backend parity test**, not fetched | No endpoint exposes the vocabulary, and the frontend must not reach the backend source at build time (52.1). A copy drifts silently — so `test_frontend_vocabulary.py` reads the frontend file and asserts equality with `DOCUMENT_TYPES`, skipping only in a backend-only checkout, never to make a mismatch pass | Adding a vocabulary endpoint later — unnecessary while the guard holds |

**Verification at close: backend 937 passed / 1 skipped (+1 parity guard) · frontend 96 Vitest
(+2) · browser 46 passed / 9 gated (+1 intake spec; a regex of mine that only matched the
first-run heading, and an orphaned test body from a bad splice, were both caught by running
the suite unfiltered — recorded in the changelog) · typecheck · `check:terms` clean.**


## UI/UX slice 5 (P1) — reviews queue, report, ask history, 2026-08-31

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 210 | **Document names on queue/history rows come from per-id `GET /contracts/{id}` lookups (unique ids per page, `Promise.allSettled`), not a new list-level join** | Decision #187 keeps `GET /reviews` and `GET /conversations` lean; a page holds ≤25 rows and far fewer unique contracts, and a failed lookup falls back to the bare id rather than blanking the row | Whether a summary field belongs on the list endpoints later (§19 candidate, unchanged) |
| 211 | **Nav active state = longest matching href (`activeNavHref`)** | `pathname.startsWith(href)` lit "Documents" on every sibling screen the moment the nav grew — /workspace is a prefix of everything. Longest-match is the standard fix and is unit-pinned | — |
| 212 | **`AssistCitation.retrieval_score` widened to `number \| null`** | The replay endpoint returns null when the retrieval-run row is missing; the old type lied and the LEGACY AskPanel would have crashed on `.toFixed()`. Both renderers now omit the score line entirely when null — never "NaN", never a blank label | — |

**Verification at close: backend 937/1 (unchanged) · frontend 100 Vitest (+4) · browser 49
passed / 9 gated (+3: queue+report, status filter, transcript replay — all green on the
first run) · typecheck · `check:terms` clean. Screenshots of both new screens reviewed
against the DD-4 finish bar.**


## UI/UX slice 6 — the Legal area, 2026-08-31

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 213 | **The Legal queue COMPOSES existing endpoints** — `GET /reviews` for the two active statuses (LEGAL_REVIEW, ANALYSIS_COMPLETE), fan-out to `findings?status=DECISION_REQUIRED`, truncation stated on-page | No cross-review findings endpoint exists, and adding one is a Step 49 surface change no slice needs yet; RESOLVED/CLOSED reviews cannot carry an undecided Finding so they are not fetched | Whether a dedicated queue endpoint is worth adding later (§19 candidate) |
| 214 | **The queue triages, never disposes: rows deep-link `?finding=` into the workspace**, which scrolls to and focuses the exact Finding card | The master prompt puts every Legal Decision beside its evidence; duplicating the decision form on a list page would divorce ruling from reading. The gesture mirrors `?evidence=`; a target hidden by the attention view widens the view first | — |
| 215 | **One filter idiom app-wide**: slice 5's `.ws-filter__chip` duplicate is removed; Reviews uses slice 2's aria-pressed toggle | Two patterns for the same control is drift; the later CSS block was silently overriding the earlier container rule | — |

**Verification at close: backend 937/1 (unchanged) · frontend 101 Vitest (+1) · browser 51
passed / 9 gated (+2: queue + deep-link focus with counsel, restricted state + absent nav
with owner) · typecheck · `check:terms` clean. One of my e2e assertions was corrected by
the run: the STRUCTURAL config's own code is asserted, never a hardcoded LIABILITY-001
(rule 21).**


## UI/UX slices 7–8 + QA close, 2026-08-31

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 216 | **The Admin nav item gates on `user.manage` OR `audit.view`; the grant control additionally needs `role.manage`** | The roadmap's §H control plane has two doors with different keys; an account with only one still gets the door it can open, and the missing half is a plain note, never a faked control | — |
| 217 | **Research joins the nav as the one disclosed placeholder, gated like Ask (`assist.ask`)** | The ratified roadmap places it in the tree "TODAY: a disclosed, calm placeholder (C-16)"; its future grammar is Ask's, so Ask's permission is the honest gate until Domain C exists | When statute research is built — blocked on C-16, an owner decision |
| 218 | **Step 10 (a11y/QA) closes as a verification pass, not an audit project** | Every slice shipped its a11y pins with the slice (skip link, tab order, aria-pressed, labeled revokes, aria-busy, focus rings, reduced-motion); the close re-ran the full matrix green. An axe-style tooling audit would add a dependency (rule 19) for properties already test-pinned | Adopting an a11y scanner later, if the owner wants one |

**Verification at close: backend 937/1 · frontend 102 Vitest · browser 54 passed / 9 gated
· typecheck · `check:terms` clean. The §G build order (1–10) is complete; the new shell
carries Documents · Reviews · Legal · Ask history · Research · Admin. Deferred and
flagged: CI-cut visual baselines for the new screens.**


## UX audit pass, 2026-08-31

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 219 | **Structured evaluation values render as labeled key–value pairs, verbatim** — never a JSON blob, never an interpretation | A clipped `{"scope":…` line is below product standard and hides the value's tail; rule 12 requires the server's facts unaltered, so the fix is layout, not paraphrase | Any richer domain-aware rendering (e.g. "24 months of fees") — that would interpret, and needs a spec |
| 220 | **One page-container rule**: rich bodies wrap in `.ws-docs`; every bare full-page state gets the same centered 72rem gutter via `.ws-main > .ws-state` | Three screens (report, transcript, research) shipped without the container — the flush-left drift was exactly the "unfinished" look the audit was ordered to catch | — |
| 221 | **The changed `workspace.png` baseline is adopted from CI's artifact after the expected one-time DESIGN_QA failure** | Owner rule 2026-08-30: baselines only from CI renders | — |


## UI freeze, 2026-08-31

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 222 | **The UI is FROZEN at f9c3c0f** (owner order): no redesign, restyle or new pattern without an explicitly requested UX review; defect fixes (usability, a11y, inconsistency, responsive, broken interaction, strategy mismatch) and screens for NEW functionality remain allowed, built on the frozen tokens/components | The goal is a stable, tested baseline to build remaining functionality on — not an endlessly "better" UI. Baseline set: 15 CI-cut screenshots; matrix green everywhere | Nothing about future functionality's UI — new screens follow the frozen system |


## Product-intent R&D + corrective implementation, 2026-08-31

| # | Decision | Why | Does not decide |
|---|---|---|---|
| 223 | **AM-33 recorded as AB-6** — the owner's §6/§15 instruction is the authorization; the band form is withdrawn by APPENDED amendment (16,494 → 16,565 lines, zero deletions), never by editing 45B.9 | Rule 22; the owner ordered an auditable change record, not silent history editing | Nothing beyond the rule FORM: vocabulary, comparison semantics, zero-tolerance rule all unchanged |
| 224 | **The B-3 workflow tests construct the ACCEPTABLE axis value directly** (frozen-dataclass `_with_outcome` helper) instead of minting it through the engine | The locked B-3 semantics govern the outcome AXIS — historical rows included — and must stay tested; the engine may no longer produce the value on a deviation | — |
| 225 | **Version selection is a URL parameter (`?version=`), the picker lives in the existing context bar, and `?evidence=` is dropped on switch** | Smallest freeze-compatible change; an evidence row belongs to exactly one version's reading order, so carrying it across would point at nothing | Viewing old versions' ask answers (transcripts already serve that); a version-diff view (unrequested) |
| 226 | **Ask stays latest-version-only, stated on-screen when an older version is open** | The server resolves a conversation to the newest version (verified in `assist.py`); a form beside v1 answering about v2 would misattribute — the frozen API is kept and honesty is rendered instead | Version-scoped ask (would need an API change nobody asked for) |

**Verification at close: backend 938/1 · 104 Vitest · 57 browser passed / 18 gated · ruff
· mypy · typecheck · terms gate · final band-semantics sweep clean. Corpus expectation
changes were confined to STRUCTURAL fixtures (AM-33 r6 authorizes exactly that); no
DOCUMENT_SUPPORTED or STANDARD_DERIVED expectation moved.**
