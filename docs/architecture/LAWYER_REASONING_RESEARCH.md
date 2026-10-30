# Lawyer-grade reasoning for LegalMind — research and plan

> 📁 **PROPOSAL — decides nothing.** Research of 2026-10-30 (owner: "research first … read each and every
> resource … and how we use that knowledge to make LegalMind learn and develop"). Four research passes read
> the primary sources; the synthesis and the mapping to LegalMind are below. Every legal proposition here is
> research input for Counsel, not a position: nothing enters configuration without a ratified source
> (rules 7, 21). Confidence marks: **V** read in the primary source · **S** secondary source only ·
> **U** unverified.

## 1. The gap

LegalMind today is a **clause checker**: each clause against each ratified standard. A commercial lawyer is a
**deal reviewer**. Measured on a real customer MSA + NDA pair (2026-10-30), the engine's findings were right
where the text matched a standard, but it could not do six things a lawyer does:

| # | Lawyer skill | Example from the 2026-10-30 pair |
|---|---|---|
| a | Understand the deal | The customer is on **prepaid** CloudPe GPUs — known only from an email, not the contract |
| b | Know what applies to this deal | Payment period, late interest, non-payment suspension, early-exit fee and colocation clauses barely matter on prepaid; unused balance and data at zero balance matter a lot |
| c | Know the direction | A 5-working-day invoice-dispute window is a deviation **in our favour**; a 15-day data purge is one **against** us |
| d | Think through scenarios | "Balance hits zero → §15.3 suspension → §15.5 no data duty → §7.6.6 purge in 15 days" |
| e | Read the whole contract | Signature block names a different LeapSwitch entity; no Term defined though §7.2/§7.3 rely on it; §1.9 points Force Majeure at the payment clause |
| f | Prioritise and advise | What to accept, counter, escalate to management — and the reply to the other side |

## 2. What the evidence says

1. **Hand-written rules + LLM-extracted facts beat LLM-written logic.** SARA tax reasoning (arXiv 2508.21051, V):
   gold rules with LLM-parsed facts 86 correct / 9 wrong / 5 abstained vs LLM-authored Prolog 75 / 15 / 10.
   Logic-LM (arXiv 2305.12295, V): LLM formalisations of real-world problems executable only 32.6–79.9%.
   DeonticBench (arXiv 2604.04443, V): 44–47% on obligations. **→ LegalMind's design (code decides, the model
   reads on a verbatim span) is the evidenced one. Extend it; do not let a model reason to a verdict.**
2. **Whole-document defects need code.** ContractScrub (ICML 2026 workshop, abstract V): defined-term and
   cross-reference errors — only one frontier model above 0.60 recall. CLAUSE (arXiv 2511.00340, V): best
   ~63% F1, low precision, omissions and structure hardest.
3. **NLI never decides.** ContractNLI (V): contradiction F1 0.36–0.41; "negation by exception" across pages
   0.00 on the minority label. Matches our own finding that the verifier is negation-blind.
4. **Legal AI hallucinates.** Magesh et al. 2024 (V): commercial legal RAG tools wrong or misgrounded on
   17–33% of queries; causes: naive retrieval, inapplicable authority, reasoning error, sycophancy.
5. **AI is weakest exactly at (c) and (f).** Vals VLAIR 2025 (S): lawyers beat tools at redlining (79.7%).
   ContractBench (micro1, S): best model ~58%, lowest on high-priority items and on the reply to a markup.
6. **Industry pattern** (Ironclad, Evisort, SpotDraft, LegalOn, Harvey, Vaquill — documented behaviour, S/V):
   the party is set **explicitly before review**; positions are preferred → fallback → walk-away; change
   detection is kept apart from classification (Harvey's "quiet failure mode"); a failed position routes to an
   approver; approved wording and rationale are stored with the position; a person signs everything.
   Common Paper's cover-page model separates **deal terms** (product, fees, prepaid/invoice, term) from fixed
   legal text.
7. **No public benchmark measures (b), (c) or Indian law.** CUAD, ContractNLI, LegalBench, ACORD are
   US/UK-law and recognition-level. **The benchmark that matters is the one LegalMind builds from its own
   recorded Legal Decisions.**
8. **Indian law changes what "favourable" means** (§6): s.74 caps a stated sum at reasonable compensation,
   s.27 voids post-term restraints, s.28(b) voids time-bar extinguishment, and DPDP Rule 8(3) (from
   13 May 2027) requires a cloud processor to keep data and logs a year before erasure — **a 15-day purge
   conflicts with it** (Rule 8(3) Illustration, Case 2, read in the supplied Gazette copy, V).

## 3. Target architecture

Every layer below L5 is new or extended; L5 — the evaluator — is unchanged and still decides every Finding.

```
L0 Parse           existing: clauses, numbers, spans
L1 Extract         regex/spaCy first; the model proposes slot values, ACCEPTED ONLY on a verbatim span
                   (AM-54 precedent), else UNKNOWN
L2 Deal sheet      billing (prepaid/postpaid/committed), service, our role (provider/customer/reseller),
                   term, resale, entity — each {value, source DECLARED|EXTRACTED, span}; UNKNOWN fails closed
L3 Norm graph      per clause: kind (obligation/power/prohibition), holder, counterparty, trigger,
                   exceptions, cross-refs, defined terms — a Symboleo/LegalRuleML subset, plain JSON
L4 Reasoners       pure Python, pinned to the configuration snapshot:
                   applicability predicates · direction table · enforceability flags ·
                   scenario simulator · whole-contract consistency
L5 Evaluator       UNCHANGED — numeric / presence / categorical, the approved Legal Rules
L6 Advise          priority from deterministic factors; IRAC explanation filled from the trace;
                   the model only words it, verified; counterparty reply drafted from stored wording
```

The model sits only in L1 (proposing) and L6 (wording). Same inputs + same snapshot → same result.

## 4. Each method, and how LegalMind uses it

| Method / resource | Skill | How LegalMind uses it | Builds on | Effort |
|---|---|---|---|---|
| Bearer/Beneficiary of a norm (OASIS LegalRuleML, V) | c | Every standard records who is bound and who benefits; "in our favour" becomes a lookup with our role | `favourable_direction` (AM-165, AM-239) | Low |
| Explicit party / side before review (LegalOn, Spellbook, SpotDraft) | a, c | Role taken from the declared type, confirmed by the reviewer; unknown fails closed | `parties.PROVIDER_TYPES` | Low |
| Cover page / deal sheet (Common Paper CSA, V) | a, b | Deal sheet filled from the order form or a span-verified suggestion a person confirms (AM-34 pattern) | `commercial.read`, AM-34 | Medium |
| Applicability predicates `applies_when` | b | Prepaid → payment-period, late-interest, non-payment and early-exit standards shown "not applicable to this deal", with the reason | AM-173 "not applicable to this contract" | Medium |
| Fixed hypothesis sets with evidence (ContractNLI, V) | b | A recall checklist per standard; never a decision | mapping rules | Low |
| Enforceability flags as a **separate axis** (§6) | c, f | "In our favour — recovery limited by s.74", shown beside the Finding; never changes classification | `domain/enforceability.py` | Medium |
| Symboleo obligation/power lifecycle (SoSym 2022, V) | d | ~200-line simulator over a closed event list (balance_exhausted, payment_overdue, termination, retention_expired); UNKNOWN branches shown both ways (s(LAW) style) | — | Medium |
| Deterministic consistency checks (ContractScrub, CLAUSE evidence) | e | Defined terms used/undefined, cross-reference **target heading** check, party/entity in preamble vs signature, typed figures stated twice | `analysis/consistency.py` (AM-159) | Medium |
| Change detection apart from classification (Harvey) | e | Show every change on unmarked counterparty paper too, as unclassified observations | client changes (AB-128) | Medium |
| IRAC explanation (Yu et al., V; LegalBench grading) | f | Issue = standard; Rule = Constitution quote; Application = clause span + deal facts; Conclusion = copied from the evaluator | angles (AM-152) | Low |
| Chain-of-Verification, factored (arXiv 2309.11495, V) | f | Each claim in an explanation becomes a closed question checked against its span, draft out of context | Ask verifier (AM-90) | Medium |
| Approval matrix, "highest matched level wins" (Vaquill, SpotDraft) | f | Each standard names its approver; deal-sheet values raise it; **missing context escalates** (Vaquill does the opposite) | RBAC (AB-12) | Low–Medium |
| Standards linter (Vaquill) | f | CI check: every standard has a source quote, direction (or a stated reason for none), approver, fixtures | `import_ratified_standards` | Low |
| Priority from deterministic factors (WorldCC: scope and service levels matter more than the most-negotiated terms) | f | Rank by: Unacceptable position engaged, against us, ₹ exposure (AM-156), missing in a detected family; never a single risk score (rule 12) | angles ranking | Low |

## 5. How LegalMind learns (no fine-tuning)

1. **Gold set from our own Legal Decisions**, in ContractBench's rubric form: section, required action
   (accept / counter / escalate / preserve), priority weight, pass condition, the reviewer's justification.
   At least two reviewers on a sample, agreement recorded (Better Call GPT: senior lawyers agree only to
   α 0.72). Real reviews only (rule 21).
2. **Regression on every change**: the gold set joins the nightly hard-benchmark timer; a phase advances only
   on measured gain (the cost guard applies to paid models too).
3. **Retrieved precedent**: past decided findings for the same standard and similar clause are given to the
   explanation and drafting steps as examples (Liu et al. 2101.06804). The verdict stays the evaluator's.
4. **Attention ranking** from decisions (continuous active learning, Cormack & Grossman): which open points a
   reviewer sees first.
5. **Decision mining**: where reviewers keep accepting the same deviation, the owner sees it — the evidence
   for ratifying a fallback, never an automatic one.
6. **External component tests**: ContractNLI for the NLI verifier (negation by exception), CUAD for clause
   recognition recall, LegalBench-RAG for retrieval, the Magesh taxonomy for Ask error audits.

## 6. Indian enforceability checks (research input for Counsel)

| # | Check | Authority | Conf. |
|---|---|---|---|
| 1 | Sum on breach (early-termination fee, 200% holdover, liquidated damages, penal interest) — recovery limited to reasonable compensation; loss usually to be shown | Contract Act s.74 and Explanation; Kailash Nath v DDA (2015) para 43; ONGC v Saw Pipes (2003); Saisudhir v NVVN 2026 INSC 103 | V |
| 2 | Post-termination purge vs retention duties | DPDP Rules 2025 r.8(3) + Illustration Case 2 (from 13 May 2027); CERT-In Directions 2022 (iv) 180-day logs, (v) 5-year customer records | V |
| 3 | Post-term restraint (customer non-solicit, non-compete) | s.27; Percept D'Mark v Zaheer Khan (2006); Golikari (1967) for in-term; Wipro v Beckman Coulter (Del HC 2006) for B2B employee non-solicit | V |
| 4 | "Raise within N days or deemed accepted / barred" (invoice disputes, SLA claim windows) — both directions | s.28(b) as amended 1997; Union of India v IndusInd Bank (2016) | V (application to invoices U) |
| 5 | Arbitration venue read as seat absent contrary indicia | A&C Act s.20; BGS SGS Soma v NHPC (2019) | V |
| 6 | Interest: penal above default; MSMED override when LeapSwitch buys from a micro/small supplier (≤45 days, 3× bank rate) | s.74 Explanation; MSMED Act ss.15–16 (Sonali Power 2025 INSC 864) | V |
| 7 | Cap and exclusion enforceable B2B; a data-loss exclusion read against the backup duty and the fiduciary's non-excludable duty | Bharathi Knitting v DHL (1996); DPDP s.8(1); Rules r.6(1)(d) | V |
| 8 | Processor-contract completeness: valid contract, safeguards, breach cooperation for the 72-hour report, erasure on instruction | DPDP s.8(2), s.8(7)(b); Rules r.6(1)(f), r.7(2)(b) | V |
| 9 | Unconscionability depends on who the counterparty is (businesses vs consumer-like) | Brojo Nath (1986) para 89; Pioneer v Govindan Raghavan (2019) | V |
| 10 | Unstamped agreement inadmissible until cured, not void | In re Interplay … Stamp Act, 2023 INSC 1066 | V |

No Indian authority was found on: customer non-solicit between companies after the term, residuals clauses,
deemed-acceptance invoice clauses under s.28, or a fee for terminating early by choice under s.74 — these
reach the reviewer as "no Indian precedent located — Counsel", never as an invented rule.

## 7. Plan

| Phase | Builds | Exit criterion |
|---|---|---|
| 1 | ✅ **DEPLOYED 2026-10-30 `bfb70ca`** with phases 3 and 4 (AB-139). **Direction** (AM-239): favourable rule form, role guard, numeric direction table with sources; presence direction later via the norm holder | Pair re-run: 8.3 "in our favour, Counsel: s.28"; purge still a deviation; one-sided cap still unacceptable; zero new false Acceptables on the corpus and the 2026-10-28 critical cases |
| 2 | **Deal sheet + applicability** | Prepaid deal: inapplicable points shown "not applicable to this deal" with reason; unused balance and zero-balance data raised |
| 3 | ✅ **DEPLOYED (AM-241).** **Whole-contract integrity** (extend `consistency.py`) | Planted-defect set: entity mismatch, undefined Term, wrong cross-reference target, duplicated figures all caught |
| 4 | ✅ **DEPLOYED (AM-242).** **Enforceability flags** (separate axis, cited reference data, time-aware) | Each flag's citation resolves to stored primary text (test per flag) |
| 5 | **Norm graph, scenario simulator, IRAC, priority** | The zero-balance scenario rendered with every step cited; UNKNOWN branches shown |
| 6 | **Learning loop**: gold set, retrieved precedent, linter, approval matrix, external component tests | Gold-set score reported nightly; phase advances only on measured gain |
| G | **Governance** (runs alongside): NIST AI 600-1 risk mapping, ISO/IEC 42001-style register, citation-integrity gate, "report a wrong answer" channel, periodic transparency report | Register and controls documented and tested |

## 8. Decisions only the owner can give

1. **New storage** — deal sheet, norm graph and enforceability flags are new columns or tables; `IMPL-01`
   requires an approved amendment (named per phase when reached).
2. **Fallback positions** — the industry ladder (preferred → fallback → walk-away) conflicts with the
   zero-tolerance rule. AM-239 covers only deviations in our favour. Whether approved fallbacks exist is a
   policy call; LegalMind can store approved fallback wording for counter-proposals without changing verdicts.
3. **Gold-set material** — past deals with Legal's real comments or redlines (rule 21: supplied, never made).
4. **Market context** — whether a labelled "market practice" line (e.g. Common Paper: 85% of cloud
   agreements cap at 12 months' fees) may be shown; it can never be a position.
5. **Counsel gaps** — the four "no Indian precedent" questions in §6, and whether LeapSwitch is
   MSMED-registered.

## 9. Not recommended

A single overall risk score (rule 12) · model-generated favourability labels (a model would decide) ·
LLM-written formal logic of whole contracts (SARA, Logic-LM, DeonticBench) · NLI or LLM contradiction
detection as a decider · full LegalRuleML/Accord/SALI/FOLIO/LKIF adoption, Catala, nuXmv model checking,
HYPO/CATO (heavy, prototype, or no implementation) · LexNLP (AGPL, unmaintained) · self-consistency voting
as a decider (cost; a disagreement may only route to a person).

## 10. Sources

Benchmarks and evaluation: CUAD arXiv 2103.06268 · ContractNLI arXiv 2110.01799,
stanfordnlp.github.io/contract-nli · LegalBench arXiv 2308.11462 · LegalBench-RAG arXiv 2408.10343 ·
ACORD arXiv 2501.06582 · ContractEval arXiv 2508.03080 · CLAUSE arXiv 2511.00340 · ContractScrub
icml.cc/virtual/2026/80622 · micro1 ContractBench micro1.ai/benchmark/ivo-micro1-contract-bench ·
Magesh et al. arXiv 2405.20362 · Dahl et al. arXiv 2401.01301 · Vals VLAIR vals.ai/industry-reports/vlair-2-27-25 ·
Better Call GPT arXiv 2401.16212 · Harvey harvey.ai/blog/rebuilding-playbook-review-as-a-multi-agent-system ·
Legal Prompting arXiv 2212.01326 · CoVe arXiv 2309.11495 · self-consistency arXiv 2203.11171 ·
in-context examples arXiv 2101.06804 · MT-Bench arXiv 2306.05685 · LeMAJ arXiv 2510.07243 ·
Cormack & Grossman SIGIR 2014, arXiv 1504.06868.

Products and standards: Ironclad ironcladapp.com/resources/articles/jurist-redlining-playbooks · Evisort
doc.workday.com/evisort · SpotDraft help.spotdraft.com · LegalOn legalontech.com · Spellbook
help.spellbook.legal · Sirion sirion.ai · Vaquill vaquill.ai/engineering/teaching-the-reviewer-how-your-firm-negotiates ·
Common Paper commonpaper.com/standards/cloud-service-agreement, commonpaper.com/resources/contract-benchmark-2024-q1 ·
Bonterms bonterms.com · oneNDA onenda.org · WorldCC Most Negotiated Terms · OASIS LegalRuleML
docs.oasis-open.org/legalruleml · Accord Project accordproject.org · SALI sali.org.

Reasoning architectures: Catala github.com/CatalaLang/catala · OpenFisca · Blawx · s(LAW) arXiv 2401.14511 ·
LegalRuleML→defeasible logic arXiv 1711.06128 · Symboleo SoSym 2022, github.com/Smart-Contract-Modelling-uOttawa ·
LLM→Symboleo arXiv 2411.15898 · ContraDoc arXiv 2311.09182 · Logic-LM arXiv 2305.12295 · SARA arXiv 2508.21051 ·
DeonticBench arXiv 2604.04443 · Chain of Logic arXiv 2402.10400 · PyArg github.com/DaphneOdekerken/PyArg ·
LKIF-Core · Accord Concerto.

Indian law and governance: Contract Act, DPDP Act 2023, DPDP Rules 2025, A&C Act, IT Act (supplied copies in
`legal-docs/Indian_Laws_and_Acts/`) · CERT-In Directions cert-in.org.in · judgments on indiankanoon.org (docs
70828540, 919241, 144516251, 146573825, 452434, 571375, 647033, 42763766, 185400685, 126678, 477313,
154279163, 99709286, 143184125, 139003074) · NIST AI 600-1 nvlpubs.nist.gov · EU AI Act Annex III ·
MeitY India AI Governance Guidelines (Nov 2025) · Bar & Bench on BCI and AI citations.
