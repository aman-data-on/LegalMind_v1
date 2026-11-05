# CLM R&D — Workstream 2: Commercial-contracts lawyer and CLM research

📁 `ANALYSIS / PROPOSAL` — 2026-11-02, branch `research/clm-contract-creation-20261102`. **Research only.
Decides nothing, locks nothing, authorizes no build** (CLAUDE.md rules 1, 4, 19). Sits beside
[DOCUMENT_BUILDER_RND.md](../DOCUMENT_BUILDER_RND.md) and [LAWYER_REASONING_RESEARCH.md](../LAWYER_REASONING_RESEARCH.md).
Counterparties are written "the client". No source contract under `legal-docs/` was opened for this report;
repository facts come from the Legal Constitution L1.14 and `backend/config/company_standards/*.json`.

**Labels used on every statement**

| Label | Meaning |
|---|---|
| **VF** | Verified fact, with a URL or a repository path. *VF (repo)* = this repository. *VF (statute)* = read from the statute text supplied under `legal-docs/Indian_Laws_and_Acts/` (India Code copies) or the official/PRS text named. |
| **VF (vendor)** | Stated in the vendor's own help centre / documentation. Where the page refused a direct fetch (Ironclad support returns 403; DocuSign's support portal is JavaScript-only; the Icertis wiki refused the connection), the statement is taken from the search-indexed text of that official page and marked *(indexed)*. |
| **IP** | Industry practice — how in-house teams and CLM tools commonly work; not law, not a LeapSwitch position. |
| **REC** | Recommendation of this workstream. Never a company position. |

Statutes are **background law** (CLAUDE.md, Source material): nothing below derives a Requirement, threshold or
acceptance position from a statute.

---

## 0. Key conclusions

1. **VF (repo)** LeapSwitch has **no approved issuable template** for either document this R&D targets:
   the MSA is "reference/template document — not yet formally adopted as Source of Truth" (Constitution §8, §7.1),
   and the NDA reference document "is not itself a lawyer-approved standing mutual template — each adaptation should
   be reviewed individually" (§15.5). There is also **no company Order Form/PO form** (§20), **no Amendment/Addendum
   form** (§21), **no DPA form** (§8, §12.2), and the company "does not use Statements of Work" (§31.13).
   The Constitution's clause wording is labelled *"Drafting Notes for Counsel — Illustrative Clause Language (not yet in
   any signed contract)"* throughout §§9–22. → The standing blocker in DOCUMENT_BUILDER_RND §16/§23 still holds:
   **positions exist; approved output prose does not.** Contract *creation* cannot ship until the lawyer supplies
   approved template text (rule 21).
2. **VF (repo)** The reference MSA template does not match the company's own positions on at least two points already on
   record: its liability cap (§17.2, six months of affected-service fees) fails closed against the 12-months-total-fees
   position (`AM-43` r4, CLAUDE.md), §17.2 and §17.7 contradict (fixture `DOC-LIAB-04`), and its indemnity is one-way
   customer-to-LeapSwitch (`INDEMNITY-MSA-001` `_about`) while Constitution §10 states a **mutual** framework.
   Generating from that template as-is would issue paper that LegalMind's own review marks as deviating.
3. **VF (vendor)** Every mature CLM (Ironclad, Juro, DocuSign CLM, Icertis) builds creation the same way:
   **intake form → properties/smartfields → conditional clauses from a governed clause library → rule-routed
   approvals → signature → archive**, and negotiation as **versioned uploads compared clause by clause, each change
   accepted/rejected/edited, approvals reset when text changes after approval**. LegalMind already has most of the
   negotiation half (AM-146/157/158 markup reading, AM-223 client-changes report, AM-224 triage, Diff-Talk,
   AM-173/174 decisions); what it lacks is the *creation* half and a *fallback library*.
4. **VF (repo) / REC** The industry "preferred → fallback → walk-away" playbook collides with the **zero-tolerance
   Legal Rule** (any deviation → UNACCEPTABLE → a Legal Decision). The Constitution itself names only a few
   approval-required alternatives (§9 longer mutual cap period; §10 minor drafting variations; §12 a weaker vendor
   breach-notification commitment, vendor-facing only; §16 Net-30 or a different reasonable cure period; §31.15 renewal
   period). A fallback library can store **approved counter-proposal wording** without changing any verdict; making a
   fallback *pre-approved* (no Legal Decision) would need an owner/lawyer decision and an appended lock amendment.
5. **VF (statute)** India-specific execution is not optional detail: **stamp duty** in Maharashtra is due "before or at the
   time of execution … or on the next working day" (Maharashtra Stamp Act 1958 s.17); an unstamped instrument is
   **inadmissible in evidence until duty plus penalty is paid** (s.34; Indian Stamp Act 1899 s.35), but **not void**
   (Supreme Court, 7 judges, *In re Interplay …*, 2023 INSC 1066). The Constitution records stamp duty as
   **"Not yet assessed for any document type"** (§27 Item 18). E-signature is valid for commercial contracts
   (IT Act s.5, s.10A; s.3A + Second Schedule for Aadhaar eSign; First Schedule exclusions do not cover an MSA/NDA).
6. **REC** Build order that respects the rules: (a) a **deal sheet / intake questionnaire** shared by creation and review
   (it is also LAWYER_REASONING_RESEARCH Phase 2); (b) a **template registry that only holds lawyer-supplied prose**
   with each clause tagged *populated / fixed / approval-to-vary*; (c) a **fallback library** of lawyer-approved
   wording per Constitution topic; (d) run the existing review engine on every generated draft before it leaves.
   LegalMind never writes clause prose.

---

## 1. What LeapSwitch's records already say (inventory for creation)

| Item | Status | Source |
|---|---|---|
| Contracting entity | Leapswitch Networks Pvt. Ltd. is **the sole contracting legal entity**; CloudPe is a brand with no legal personality | VF (repo) Constitution §4 |
| Registered office | Office 1104, Gokhale Business Bay, Kothrud, Pune 411038 (address of record) | VF (repo) §4.1 |
| Incorporation | "Companies Act, 2013" as published; CIN records a 2010 registration — **verification required** | VF (repo) §4.1, §27 Item 16 |
| MSA | Reference/template, not adopted | VF (repo) §8, §7.1, Appendix C |
| NDA | Reference template, not lawyer-approved; NDA standards state **receiving-party** positions only ("If a review ever concerns LeapSwitch DISCLOSING its own information, these standards do not state that position") | VF (repo) §15.5; `NON-SOLICIT-NDA-001` `_about` |
| Order Form / PO | No company form; analysis rules only (§31.11) | VF (repo) §20 |
| Amendment / Addendum | No company form; analysis rules only (§31.12) | VF (repo) §21 |
| DPA | No company form | VF (repo) §8, §12.2 |
| SOW | Not used | VF (repo) §31.13 |
| Stamp duty / execution | Not assessed; question posed to Counsel | VF (repo) §27 Item 18 |
| Document precedence | Follow an express precedence clause; otherwise REVIEW REQUIRED; no invented hierarchy | VF (repo) §8.2 |
| Escalation roles | Not locked in the Constitution; "only a person with explicitly assigned legal-approval authority may approve or reject a deviation" | VF (repo) §25, §25.1 |
| Retired standards (no current position) | Force majeure (MSA, TOS), warranty disclaimer (MSA), liability carve-outs (MSA), return/destruction (MSA, NDA), compelled disclosure (NDA) | VF (repo) `retired` key in those seven files (`AM-65`) |

---

## Part A — Contract creation lifecycle

### A.1 The twelve steps, as CLMs do them, and the Indian differences

| # | Step | How CLM tools do it | India-specific | LegalMind today |
|---|---|---|---|---|
| 1 | Template selection | **VF (vendor)** Ironclad: "Control access to only pre-approved templates" ([Workflow Designer](https://ironcladapp.com/product/workflow-designer)). Juro: approvers and rules are set on the template so they "carry over into your contracts" ([Juro approvals](https://intercom.help/juro/en/articles/5653139-handling-approvals)). | — | **None approved** (§1 table) |
| 2 | Variant (mutual/one-way NDA; MSA + Order Form) | **VF (vendor)** Juro keeps "text variations in one template" driven by rules on smartfields ([Juro rules](https://intercom.help/juro/en/articles/5653125-adding-and-managing-rules)); Ironclad conditional clauses use a launch-form question whose answer is a property, the property value being the condition criterion *(indexed)* ([Ironclad conditional clause](https://support.ironcladapp.com/hc/en-us/articles/12250550045463-Create-a-Conditional-Clause-in-Workflow-Designer)). | — | One-way NDA = Constitution §15 Unacceptable when it protects only one party (`CONF-MUTUAL-NDA-001`) |
| 3 | Counterparty data | **VF (vendor)** Juro smartfields: text, long text, number, email, list, date, plus registry look-ups (Companies House — a UK registry) ([Juro smartfields](https://intercom.help/juro/en/articles/5652971-using-smartfields)). | **VF (statute)** Indian companies must print name, registered office and **CIN** on business letters and notices (Companies Act 2013 s.12(3)(c)); signatory authority under s.21 (A.4). **IP** GSTIN, PAN collected for invoicing/TDS. UK registry look-ups do not apply; the Indian equivalent is the MCA master data. | Counterparty entity exists (`AM-42`) |
| 4 | Commercial data | **VF (vendor)** Ironclad's flow runs "from inputs like counterparty, governing law, and payment amount to a final document" ([Workflow Designer](https://ironcladapp.com/product/workflow-designer)). | Fees **exclusive of GST** (Constitution §16; `GST-EXCLUSIVE-MSA-001`). Contract value drives Maharashtra stamp duty (A.4). | — |
| 5 | Clause / schedule selection | **VF (vendor)** Icertis clause library manages "fallbacks and dependents, requiring mandatory language … tracking deviations, organizing clause approval workflows" ([Icertis authoring](https://www.icertis.com/contracting-basics/contract-authoring/)); Ironclad global vs local conditional clauses *(indexed)*. | — | Standards ≠ clause text |
| 6 | Conditional clauses | **VF (vendor)** Juro rules test empty / contains / equals / greater-or-less, combined with AND/OR; "Each portion of text can have a maximum of one single-tier/combined rule" ([Juro rules](https://intercom.help/juro/en/articles/5653125-adding-and-managing-rules)). Ironclad conditions can drive clauses, form questions/sections, signer roles and generation *(indexed)*. | DPDP processor terms only when personal data is processed (A.4) | — |
| 7 | First draft | **VF (vendor)** DocuSign CLM "Create or Upload Doc" step "launches a document generation intake form … Optionally, you can use the data with a document template to generate a document that includes merged fields" *(indexed)* ([DocuSign CLM human steps](https://support.docusign.com/s/document-item?language=en_US&bundleId=yks1643320936212&topicId=qkt1576610095922.html)). | — | — |
| 8 | Review | **REC** run LegalMind's existing evaluator on the generated draft: a draft built from an approved template should read 100% Acceptable; anything else is a template or input defect. | — | Engine exists |
| 9 | Internal approval | **VF (vendor)** Juro: "Internal changes made after the document has been approved will retrigger the approval process"; "Approvals precede the signing stage and must be completed before the document can be sent for signing" ([Juro approvals](https://intercom.help/juro/en/articles/5653139-handling-approvals)). Ironclad: going back to Review "will also reset all Approvals" *(indexed)* ([Ironclad Review and Approve](https://support.ironcladapp.com/hc/en-us/sections/12271366818327-Review-and-Approve)). Icertis: deviation approvers "by defining rules"; editing an approved clause returns it to Draft *(indexed)* ([Icertis Clauses](https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=Clauses)). DocuSign CLM Approve step can require one or all approvers *(indexed)*. | **VF (statute)** Board authority for the signatory (s.21 Companies Act) is a *corporate* approval distinct from Legal's approval. | `legal.decision` holders; Constitution §25 leaves routing to the product |
| 10 | Send | **VF (vendor)** DocuSign CLM "Send Documents for Signature" needs a preceding Prepare Template step ([DocuSign Workflow Builder](https://support.docusign.com/s/document-item?language=en_US&bundleId=yff1696971835267&topicId=uww1698167288211.html)) *(indexed)*. | Stamp **before or at execution** in Maharashtra (s.17) — the stamp must exist before signing, so it sits between 9 and 11. | — |
| 11 | Execution | **IP** e-signature platforms or wet ink. | IT Act s.3A/s.5/s.10A; Aadhaar eSign (Second Schedule); Maharashtra s.2(i) Explanation: "signed" includes attribution of an electronic record under IT Act s.11 (A.4). | — |
| 12 | Store executed | **VF (vendor)** Ironclad: Archive "comes after all signatures have been collected and is the last step" *(indexed)* ([Ironclad Archive](https://support.ironcladapp.com/hc/en-us/articles/12448503998871-Archive-Step-Overview)). | **VF (statute)** BSA 2023 s.66 (proof of e-signature unless secure), s.86 (presumption for secure e-signature) — keep the signing certificate/audit trail with the record; Constitution §27 Item 17 already asks Counsel about BSA s.63 certificates. | Upload + review exists |

### A.2 How the four CLMs differ (only what the official docs support)

| Tool | Creation model | Conditional logic | Approvals | Verified from |
|---|---|---|---|---|
| Ironclad | Workflow Designer: Create → Review → Sign → Archive tabs; launch form with properties; "Tag required fields for requesters" | Global (clause library) vs local conditions; conditions also drive signers and generation | Rule-routed; reset when sent back to Review | product page (fetched); support articles *(indexed)* |
| Juro | Browser-native template with smartfields | Rules on smartfields, AND/OR, one rule per text span | Template-level + conditional approvers; re-approval on internal edit; approvals gate signing | help centre (fetched) |
| DocuSign CLM | Doc Gen intake form → merge into Word template; legacy steps and newer Workflow Builder | Conditional form fields; community reports of Doc Gen not always honouring non-Salesforce conditions ([community](https://community.docusign.com/docgen-115/can-you-have-document-generation-fields-under-a-conditional-logic-field-26096)) — **IP**, not official | Approve step (one / all respondents) | support pages *(indexed)* |
| Icertis | Clause library with mandatory, alternate and dependent clauses | Rules | Clause-level deviation approval, rule-assigned approvers; AI playbook with "multiple playbook positions" and risk scores per exception | wiki *(indexed)*, product page |

**REC** LegalMind must not copy Icertis's "risk score per exception" — rule 12 forbids a generic risk score.

### A.3 The intake questionnaire — field classification

Classes: **M** mandatory · **O** optional · **C** conditional (shown only when its trigger holds) · **LA**
legally-approved-only (choose from a lawyer-approved list; **never free text**). "Constitution" names the section that
holds a position; **GAP** = no current position, so the field cannot be offered as a choice until the lawyer supplies one.

#### A.3.1 NDA

| Field | Mutual | One-way | Class | Constitution / standard | Note |
|---|---|---|---|---|---|
| Our entity | ✓ | ✓ | **LA** (fixed: Leapswitch Networks Pvt. Ltd.) | §4 | Brand (Leapswitch/CloudPe) is a separate **M** list field; never a second entity |
| Our signatory + designation | ✓ | ✓ | **LA** (approved signatory list) | — GAP (who signs) | s.21 Companies Act |
| Counterparty legal name | ✓ | ✓ | M | — | Exactly as registered |
| Counterparty entity type | ✓ | ✓ | M (list: company, LLP, partnership, proprietor, foreign entity, individual) | — | Drives the next three |
| CIN / LLPIN | ✓ | ✓ | C (Indian company / LLP) | — | VF s.12(3)(c) for CIN |
| Registered office | ✓ | ✓ | M | — | |
| GSTIN, PAN | | | O (no fees under an NDA) | — | **IP** |
| Country of incorporation | ✓ | ✓ | C (foreign entity) → routes to Legal | — GAP | Foreign governing-law requests are not covered |
| Counterparty signatory, designation, authority evidence | ✓ | ✓ | M; authority evidence C (signatory not a director) | — GAP | **IP** board resolution / POA extract |
| Notice address + e-mail | ✓ | ✓ | M | — | |
| Direction | mutual | who discloses | **LA** | §15: mutual is the position; "A one-directional confidentiality obligation protecting only one party" is Unacceptable | One-way **where LeapSwitch only receives** is the case the NDA standards describe; one-way **where LeapSwitch only discloses** has no stated position (direction caveat) → Legal Decision |
| Purpose | ✓ | ✓ | M (free text, reviewed) | — | The only free-text legal field; it bounds permitted use, so Legal reads it |
| Effective date | ✓ | ✓ | M | — | |
| Agreement term / early end notice | ✓ | ✓ | **LA** | `TERM-NOTICE-NDA-001` 30 days | |
| Survival | ✓ | ✓ | **LA** (fixed 3 years; trade secrets while secret) | §15; `CONF-SURVIVAL-NDA-001`, `TRADE-SECRET-CARVEOUT-NDA-001` | |
| Definition of Confidential Information | ✓ | ✓ | **LA** (fixed two-part test) | §15; `CONF-DEFINITION-NDA-001` | |
| Residuals | ✓ | ✓ | **LA** (fixed) | §15; `RESIDUALS-NDA-001` | |
| Non-solicitation | ✓ | ✓ | **LA** (2 years) | §15; `NON-SOLICIT-NDA-001` | §15 asks Counsel to confirm enforceability; s.27 (A.4) |
| Governing law / courts / arbitration | ✓ | ✓ | **LA** (fixed: India; Pune) | §22; `GOVLAW-NDA-001` | |
| Return / destruction on request | ✓ | ✓ | **LA** | **GAP** (`RETURN-DESTRUCTION-NDA-001` retired) | |
| Compelled (legal) disclosure | ✓ | ✓ | **LA** | **GAP** (`COMPELLED-DISCLOSURE-NDA-001` retired) | |
| Permitted disclosees (affiliates, advisers, sub-contractors) | ✓ | ✓ | **LA** | **GAP** | |
| Personal data will be shared? | ✓ | ✓ | M (yes/no) → C DPDP clause | §12, §28.2 | DPDP s.8(2) (A.4) |
| State of execution / stamp payer | ✓ | ✓ | M / **LA** | **GAP** (§27 Item 18) | A.4 |
| Execution method | ✓ | ✓ | **LA** (e-sign type / wet ink) | **GAP** | A.4 |

#### A.3.2 MSA (+ Order Form; no SOW)

Counterparty fields as the NDA, plus **GSTIN (M for an Indian GST-registered customer — IP)**, **PAN (M — IP,
TDS under Income-tax Act ss.194C/194J named in §16)**, billing contact (M).

| Field | Class | Constitution / standard | Note |
|---|---|---|---|
| Brand + products/services (Bare Metal, GPU, VPS, Kubernetes…) | M (list) | §5, Appendix D | Selects which brand's SLA applies (§11 — never merged) |
| Initial term | M (list) | §31.15 (renewal period "treated as a negotiable commercial term") | Commercial |
| Committed term / minimum service period | C (fixed-term deal) | §14, §31.2; `EARLY-TERM-RESTRICTION-MSA-001` | Full committed value payable on early exit; s.74 enforceability is Counsel's (§27 Item 4) |
| Auto-renewal + non-renewal notice | **LA** (30 days) | §31.15; `AUTORENEW-MSA-001` | |
| Fees, billing cycle, currency | M (Order Form) | §16 | Order Form only; MSA refers to it |
| Payment period | **LA** (21 days; Net-30 = approval required) | §16; `PAYMENT-PERIOD-MSA-001` | |
| Late interest | **LA** (2%/month subject to law) | §16; `LATE-INTEREST-MSA-001` | §27 Item 3 |
| Billing-dispute window | **LA** (15 days) | `DISPUTE-WINDOW-MSA-001` | s.28(b) concern noted in LAWYER_REASONING §6 |
| Price-change notice | **LA** (30 days) | `PRICE-CHANGE-NOTICE-MSA-001` | |
| Suspension for non-payment | **LA** (notice + cure) | §16, `SUSPENSION-NOTICE-CURE-MSA-001` | **C-28 open** (§13 immediate suspension vs §16 notice-and-cure) — must be resolved before a template fixes this text |
| Liability cap | **LA** (12 months total fees, mutual; longer mutual period = approval required) | §9; `LIABILITY-MSA-001` | |
| Indirect/consequential exclusion | **LA** (mutual) | §9; `LIAB-EXCLUSIONS-MSA-001` | |
| Data-loss exclusion | **LA** | §9 (L1.14); `DATA-LOSS-EXCLUSION-MSA-001` | §9 itself requires Counsel reconciliation |
| Liability carve-outs (fraud, death/injury, non-excludable) | **LA** | **GAP** (`LIAB-CARVEOUTS-MSA-001` retired) | |
| Indemnity | **LA** | §10 mutual framework; **template is one-way** (`INDEMNITY-MSA-001`) | Lawyer must say which text is the template |
| SLA / service credits | **LA** (brand's published schedule, exclusive remedy, 60-day claim window) | §11; `SLA-CREDIT-REMEDY-SLA-001` | Incorporated by reference as a schedule |
| Data protection role + DPA | C (customer personal data hosted) | §12, §12.2, §28.2 | No DPA form exists |
| Data residency | C (India-designated service) | §12, §19 | |
| Termination for convenience / cure | **LA** (30 / 30 days) | §13; `CONVENIENCE-NOTICE-MSA-001`, `CURE-PERIOD-MSA-001` | Subordinate to committed term (§31.2 note) |
| Post-termination data export | **LA** (30 days, free) | §13; `DATA-PURGE-MSA-001` | |
| Change of control | **LA** (30-day notice) | §31.14; `CHANGE-OF-CONTROL-NOTICE-MSA-001` | |
| Service discontinuation | **LA** | §31.14; `SERVICE-DISCONTINUATION-MSA-001` | |
| Confidentiality survival | **LA** (3 years) | §15; `CONF-SURVIVAL-MSA-001` | |
| IP ownership | **LA** | §15; `IP-OWNERSHIP-MSA-001` | |
| Warranty / disclaimer | **LA** | **GAP** (retired) | |
| Force majeure | **LA** | **GAP** (retired) | |
| Governing law, courts, arbitration (sole arbitrator, seat Pune, English) | **LA** (fixed) | §22; `GOVLAW-MSA-001`, `ARBITRATION-MSA-001`, `DISPUTE-VENUE-MSA-001` | Arbitration value threshold: none approved — never invented (§22) |
| Order of precedence (MSA vs Order Form vs SLA) | **LA** | §31.11: MSA prevails over a PO; §8.2: no other hierarchy invented | GAP for MSA vs SLA, MSA vs DPA |
| Assignment, notices, entire agreement, severability, counterparts, e-sign clause | **LA** | **GAP** (boilerplate not in the Constitution) | |
| Partner tiers | never in an MSA | §31.4 | Hide for end customers |

**Order Form** (per §31.11): products/services, quantity, price, taxes, commencement date (M); reference to the
governing MSA by date/version (M, `REFERENCE-GOVERNING-MSA-ORDER_FORM-001`); payment terms **by reference only**
(LA); binding on written acceptance (`ACCEPTANCE-ORDER_FORM-001`); MSA prevails on conflict
(`ORDER-PRECEDENCE-PO-ORDER_FORM-001`). **REC** an Order Form generator must not restate MSA terms — any legal
text typed into an Order Form is a deviation channel.

### A.4 Indian-specific items

**Identifiers and authority**

* **VF (statute)** Companies Act 2013 s.12(3)(c): every company prints "its name, address of its registered office and the
  Corporate Identity Number" on business letters, billheads, notices and official publications — so CIN and registered
  office belong in the parties block.
* **IP** CIN is 21 characters (listing status, industry, state, year, type, serial); LLPs carry an LLPIN under the LLP
  Act 2008; GSTIN is 15 characters, state code + the 10-character PAN + entity number + default "Z" + check character
  (secondary sources only, e.g. [TaxGuru](https://taxguru.in/goods-and-service-tax/gstin-goods-and-service-tax-identification-number-structure.html);
  verify on gst.gov.in / mca.gov.in before building validators). **REC** validate format only; never infer an entity from an ID.
* **VF (statute)** s.21: a contract "made by or on behalf of a company, may be signed by any key managerial personnel or an
  officer or employee of the company duly authorised by the Board in this behalf." The common seal is optional since the
  2015 amendment ("the words 'and a common seal' omitted by Act 21 of 2015"). **IP** the counterparty's authority is
  evidenced by a board resolution extract or power of attorney when the signatory is not a director/KMP.

**Stamp duty**

* **VF (statute)** Stamp duty on agreements is a State subject; in Maharashtra the **Maharashtra Stamp Act 1958** applies
  ([IGR Maharashtra consolidated text](https://igrmaharashtra.gov.in/SB_PUBLICATION/DATA/Schedule/_STAMP_ACT%20amended%2003.6.2022.pdf);
  [PRS copy, amendments to 2025](https://prsindia.org/files/bills_acts/acts_states/maharashtra/1958/Act60of1958MH.pdf)).
  * s.17: instruments executed in the State "shall be stamped before or at the time of execution or immediately thereafter
    on the next working day following the day of execution".
  * s.34: an instrument not duly stamped shall not "be admitted in evidence for any purpose … or be acted upon, registered
    or authenticated" unless the duty and a penalty of **2% of the deficient duty per month, capped at four times** the
    deficiency, are paid.
  * s.2(i) Explanation: "signed" and "signature" include attribution of an electronic record under IT Act s.11 — an
    e-signed agreement is an executed instrument and is stampable.
  * Schedule I Article 5(h)(A)(iv): an agreement "creation of any obligation, right or interest and having monetary value,
    but not covered under any other article" — **0.1%** of the amount agreed if ≤ ₹10 lakh (min ₹100), **0.2%** otherwise.
    Article 5(h)(B) "If not otherwise provided for" — **₹100** in the PRS text; raised to **₹500** by the Maharashtra Stamp
    (Amendment) Ordinance 2024 per law-firm notes ([Khaitan & Co., July 2026](https://www.khaitanco.com/sites/default/files/2026-07/Maharashtra%20Stamp%20Amendment%20Bill_17072026.pdf);
    [Argus Partners](https://www.argus-p.com/updates/updates/maharashtra-stamp-amendment-ordinance-2024/)) — **confirm against the gazette**.
  * Which article an MSA (monetary value) vs an NDA (no monetary value) falls under is a **lawyer question**, not a system rule.
* **VF (statute)** Other States: Indian Stamp Act 1899 s.35 (same inadmissibility bar; proviso (a) admits on payment of duty
  plus penalty of ₹5 or ten times the deficiency) ([India Code](https://indiacode.nic.in/bitstream/123456789/15510/1/a1899-2%20.pdf)),
  as adapted by each State's own Act.
* **VF** *In re: Interplay between Arbitration Agreements under the A&C Act 1996 and the Indian Stamp Act 1899*, 2023 INSC 1066
  (13 Dec 2023, seven judges): unstamped/insufficiently stamped agreements "are inadmissible in evidence under Section 35"
  but not void; "Non stamping or inadequate stamping is a curable defect"; overrules *N.N. Global* on this point
  ([Verdictum report](https://www.verdictum.in/app-lite/court-updates/supreme-court/unstamped-arbitration-agreement-not-void-1509237);
  also LAWYER_REASONING_RESEARCH §6 row 10).
* **VF (statute)** Payment mode in Maharashtra: GRAS e-payment / e-SBTR ("electronically Secured Bank and Treasury Receipt")
  and franking are recognised in the Act. **IP** SHCIL e-stamp certificates (shcilestamp.com) serve most other States;
  secondary sources report Maharashtra uses GRAS/e-SBTR instead — verify on the IGR site.
* **VF (statute)** Maharashtra Act s.18(1): an instrument "executed only out of this State may be stamped within three months
  after it has been first received in this State". **IP** the place of each party's signature therefore matters for
  e-signed contracts with out-of-state parties. **Lawyer question.**

**Electronic signatures**

* **VF (statute)** IT Act 2000 s.5: where a law requires a signature, the requirement is satisfied by an electronic signature
  affixed as prescribed; s.10A: a contract formed through electronic communications is not unenforceable solely for that.
* **VF (statute)** s.3A + Second Schedule: a reliable electronic signature/authentication technique specified in the Second
  Schedule — item 1 is **"e-authentication technique using Aadhaar or other e-KYC services"** (Aadhaar eSign via a
  Certifying Authority's trusted service). s.3 covers digital signatures (asymmetric crypto, DSC).
* **VF (statute)** First Schedule (as substituted by S.O. 4720(E), 26-9-2022) — the Act does **not** apply to: negotiable
  instruments (other than cheques/DPN/BoE in favour of RBI/SEBI/IRDAI/NHB/PFRDA-regulated entities), powers of attorney
  (same exception), trusts, wills; serial 5 (immovable-property contracts) was **omitted**. An MSA, NDA, Order Form or
  amendment is not on the list.
* **VF (statute)** BSA 2023 s.66: except a *secure* electronic signature, the fact that an e-signature is the subscriber's must
  be proved; s.86: presumptions for secure electronic signatures.
* **IP** Click-to-sign / typed signatures on common e-signature platforms are not Second Schedule techniques; they are
  widely used for commercial contracts relying on s.10A and the Contract Act (no writing requirement for these
  contracts), with proof through the platform's audit certificate. **Differs from EU/US practice**, where eIDAS/ESIGN
  give simple e-signatures explicit statutory footing. Choice of method is a **lawyer question**.

**Indian Contract Act 1872** (VF (statute), India Code copy)

* s.10: agreements are contracts "if they are made by the free consent of parties competent to contract, for a lawful
  consideration and with a lawful object". s.23: object/consideration unlawful if forbidden by law, defeats any law,
  fraudulent, injurious, immoral or opposed to public policy.
* s.27: "Every agreement by which any one is restrained from exercising a lawful profession, trade or business of any kind,
  is to that extent void" — the only exception is sale of goodwill. **Differs from UK/US**, where reasonable post-term
  restraints can be enforced; in India post-term non-solicits and non-competes are the risky clause
  (LAWYER_REASONING_RESEARCH §6 row 3; Constitution §15 asks Counsel about the 2-year non-solicit).
* s.73/s.74: compensation for breach; for a named sum, "reasonable compensation not exceeding the amount so named";
  Explanation — increased interest from default "may be a stipulation by way of penalty". **Differs from English law**'s
  liquidated-damages/penalty dichotomy: Indian courts award reasonable compensation up to the named sum (Constitution
  §28.4.1, §27 Items 4, 10, 19).
* s.62: "If the parties to a contract agree to substitute a new contract for it, or to rescind or alter it, the original
  contract need not be performed" — the statutory basis for amendments and restatements (Part D).

**DPDP Act 2023** (VF (statute); commencement per Constitution §28.2.1, not restated here)

* s.8(1): the Data Fiduciary is responsible "irrespective of any agreement to the contrary" for processing by its Data
  Processor; s.8(2): a Processor may be engaged "only under a valid contract"; s.8(5) reasonable security safeguards
  including over the Processor; s.8(6) breach intimation to the Board and each Data Principal; s.8(7)(b) the Fiduciary
  must "cause its Data Processor to erase" personal data. → **REC** a DPDP schedule is a **conditional** schedule of the
  MSA (customer content with personal data). Which party is Fiduciary is relationship-dependent (Constitution §12.2,
  §27 Items 5, 20) — never defaulted.

---

## Part B — Typical enterprise MSA and NDA structure

Classification: **P** safely populated from inputs · **F** fixed approved text · **A** needs legal approval to vary.
"LeapSwitch position" = Constitution section and/or ratified standard; **NONE** = a real gap for the lawyer.

### B.1 MSA

| # | Part (IP: typical order) | Class | LeapSwitch position |
|---|---|---|---|
| 1 | Title, date, parties block (name, CIN, registered office) | P | §4, §4.1 (ours); s.12(3)(c) |
| 2 | Recitals | F (+P for service description) | NONE |
| 3 | Definitions and interpretation | F | NONE (only "Confidential Information" in §15) |
| 4 | Services; ordering mechanism (Order Forms) | F | §31.11 |
| 5 | Term, renewal | P (period) / A | §31.15 |
| 6 | Minimum committed term, early exit | A | §14, §31.2 |
| 7 | Fees, invoicing, payment, late interest, disputes, taxes | P (amounts) / A | §16 |
| 8 | Suspension | A | §13 vs §16 — **C-28 open** |
| 9 | Customer obligations, AUP | F (by reference) | §17 |
| 10 | Service levels and credits | F (by reference to brand SLA) | §11 |
| 11 | Data protection, security, residency, sub-processors | A (C for DPA) | §12, §19, §28 |
| 12 | Confidentiality | A | §15 |
| 13 | Intellectual property | A | §15 |
| 14 | Warranties and disclaimers | A | **NONE** (retired) |
| 15 | Indemnities | A | §10 (template differs — §0 item 2) |
| 16 | Limitation of liability, exclusions, data loss | A | §9 |
| 17 | Termination, effects, data return | A | §13 |
| 18 | Change of control, assignment | A | §31.14 (change of control); assignment **NONE** |
| 19 | Service discontinuation / changes | A | §31.14 |
| 20 | Force majeure | A | **NONE** (retired) |
| 21 | Non-solicitation (if any) | A | §15 (2 years, enforceability to Counsel) |
| 22 | Governing law, disputes, arbitration | F | §22 |
| 23 | Notices | P (addresses) / F | NONE |
| 24 | Boilerplate: entire agreement, order of precedence, amendment in writing, waiver, severability, counterparts, e-signature, survival | F | §8.2, §31.11 (precedence vs PO), §31.12 (amendment in writing); rest **NONE** |
| 25 | Signature blocks (name, designation, date, place of execution) | P | s.21; place of execution matters for stamp duty |
| S1 | Schedule: Order Form template | P/F | §20, §31.11 |
| S2 | Schedule: SLA (brand) | F | §11 |
| S3 | Schedule: DPA / data-processing terms | C, A | §12.2 — no form |
| S4 | Schedule: AUP | F (by reference) | §17 |
| — | SOW | not used | §31.13 |

**IP** Cross-references are the most common defect in generated contracts (renumbering when a conditional clause is
removed). **REC** a generator must number clauses at render time and resolve cross-references by clause ID, then run
the existing whole-contract integrity checks (AM-241: wrong cross-reference target, undefined Term).

### B.2 NDA

| # | Part | Class | LeapSwitch position |
|---|---|---|---|
| 1 | Parties, date | P | §4 |
| 2 | Purpose | P (free text, reviewed) | NONE |
| 3 | Definition of Confidential Information (two-part test) | F | §15, `CONF-DEFINITION-NDA-001` |
| 4 | Exclusions (public, known, independently developed, third-party) | F | **NONE** |
| 5 | Obligations, mutuality | F | §15, `CONF-MUTUAL-NDA-001` |
| 6 | Permitted disclosees | A | **NONE** |
| 7 | Compelled disclosure | A | **NONE** (retired) |
| 8 | Return / destruction | A | **NONE** (retired) |
| 9 | Term and early termination | A | `TERM-NOTICE-NDA-001` |
| 10 | Survival, trade secrets | A | §15 |
| 11 | Residuals | A | §15 |
| 12 | Non-solicitation | A | §15 |
| 13 | No licence / no obligation to proceed / no warranty | F | **NONE** |
| 14 | Remedies (injunctive relief) | F | **NONE** — **IP** standard; Specific Relief Act is background law only |
| 15 | Governing law, disputes | F | §22, `GOVLAW-NDA-001` |
| 16 | Boilerplate, counterparts, e-signature | F | **NONE** |
| 17 | Signature blocks | P | s.21 |
| S1 | Schedule (negotiated variations) | A | §31.12 notes "negotiated Schedule 1 amendments observed in signed NDAs" |

---

## Part C — Negotiation: handling a returned redline

### C.1 How the tools do it

* **VF (vendor)** Ironclad: a counterparty redline is uploaded as a **new version** of the document (.doc/.docx/.pdf);
  "Compare" shows redlines between selected versions; "Edit from Redlines" opens the differences as tracked changes to
  accept, reject or edit; saving logs a comment and link in the Activity Feed; uploading lets the user decide whether to
  "switch turns and reset approvals"; a document generated from a template "is no longer generated from the template once
  uploaded" *(indexed)* ([Compare Document Versions](https://support.ironcladapp.com/hc/en-us/articles/12274718080791-Compare-Document-Versions);
  [Update a Workflow's Properties and Documents](https://support.ironcladapp.com/hc/en-us/articles/12274791253271-Update-a-Workflow-s-Properties-and-Documents)).
* **VF (vendor)** Ironclad playbooks: "preferred and fall back positions"; the AI "will first search for those exact
  positions in the document" then falls back to clause detection; swaps a detected clause for preferred or fallback
  language *(indexed)* ([AI Playbooks in Workflow Designer](https://support.ironcladapp.com/hc/en-us/articles/24948981301143-Create-Ironclad-AI-Playbooks-in-Workflow-Designer)).
  Ironclad's own guidance: Tier 1 negotiator within standard and fallback positions, Tier 2 legal ops beyond fallbacks,
  Tier 3 GC near a walk-away ([Ironclad, modern contract playbook](https://ironcladapp.com/resources/articles/modern-contract-playbook)) — **IP**.
* **VF (vendor)** Juro: the counterparty's first redline sets status NEGOTIATION; "the document remains locked to the
  other side until the version with the latest changes is sent back"; "An accepted change will be incorporated into the
  document as part of the text"; "Unresolved suggestions can block the signing process"; resolved suggestions give "a
  clear, clickable audit trail" ([Negotiating in Juro](https://intercom.help/juro/en/articles/5897857-negotiating-in-juro)).
  External users cannot accept or reject redlines *(indexed)* ([Juro comments & suggestions](https://intercom.help/juro/en/articles/5653051-collaborating-on-contracts-comments-suggestions)).
* **VF (vendor)** Icertis: deviations listed on the agreement's Deviations tab and routed to rule-assigned approvers; each
  clause shows Approved or Requires Approval *(indexed)* ([Icertis Clauses](https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=Clauses)).
* **VF (vendor)** Microsoft Word legal blackline "compares two documents and displays what changed between them in a third
  new document … The documents that are being compared are not changed"; for several reviewers use Combine instead
  ([Microsoft Support](https://support.microsoft.com/en-US/Word/compare-document-differences-using-the-legal-blackline-option);
  [Combine revisions](https://support.microsoft.com/en-us/word/combine-document-revisions)).

### C.2 What LegalMind already does (VF (repo), LOCKED_DECISIONS.md)

`AM-146/157/158` read a marked-up PDF/DOCX as **two versions, never merged** (struck/inserted text, tables, scans);
`AM-223` lists every client change by section (Added / Removed / Changed) with their Word comments, never judged;
`AM-224` says one of six fixed reasons per change ("moves risk onto LeapSwitch") with the sentence quoted; Diff-Talk;
`AM-173/174` point decisions (incl. Not applicable to this contract) and the contract decision Sign as is / Sign after
our changes / Do not sign / On hold, by a `legal.decision` holder.

### C.3 Recommended negotiation workflow for LeapSwitch (REC)

1. **Ingest the return as a new version** of the same contract (never a new contract); keep our sent version immutable.
   If the client returned a clean copy, compare against our last sent version (Word-blackline semantics: neither input
   changes).
2. **Clause-level detection**, aligned by clause ID, not page: Accepted-unchanged · Modified · Deleted · Added clause ·
   New annexure/schedule · Moved. New annexures are read whole (an annexure can override the body via a precedence
   clause — §8.2).
3. **Legal impact per change**: run the evaluator on the *proposed* text (already the AM-146 r2 evidence rule) and show
   AM-224's fixed reason. Conflicts between a change and another clause go to REVIEW REQUIRED (§8.2), never auto-resolved.
4. **Per-change response**, each recorded with its author and reason:
   * **Accept** — only when the proposed text is Acceptable against the standard, *or* by a Legal Decision.
   * **Reject** — restore our wording verbatim (kept from the sent version, never retyped).
   * **Counter-propose** — choose wording **only from the lawyer-approved fallback library** for that Constitution topic;
     no free-text legal drafting by non-lawyers, no model-written counter-text. Under the zero-tolerance rule a
     counter-proposal that is not our standard still needs a Legal Decision before it is sent, unless the lawyer
     pre-approves that fallback (decision list Q5–Q6).
5. **Approvals reset** whenever text changes after approval (Juro/Ironclad pattern) — maps to AM-175's "a finished review
   reopens when a point needs work again".
6. **Version naming** (IP): `<Type>_<Counterparty-short>_<YYYY-MM-DD>_v<NN>_<LS|CP>` with *LS* = our turn, *CP* = client
   turn; executed copy suffixed `_EXECUTED`. The negotiation history is the ordered list of versions with each change's
   disposition — append-only, like the audit trail.
7. **Final clean consolidated version**: all changes resolved (unresolved suggestions block signing — Juro), tracked
   changes accepted, comments removed, cross-references re-resolved, the evaluator re-run on the clean text, then the
   AM-174 contract decision, then stamping and signature.

### C.4 Where negotiated changes end up

| Timing | Mechanism | Basis |
|---|---|---|
| Before signing | **Fold into the executed text** — the signed document is the clean consolidated version; nothing is called an amendment | **IP** universal practice |
| Before signing, deal-specific deviation the template must not absorb | A **schedule/annexure of negotiated terms** that expressly overrides named clauses, with a precedence clause | **IP**; §31.12 notes negotiated "Schedule 1" in signed NDAs |
| After signing, change to terms | **Amendment / addendum**, in writing, signed by authorised representatives of both parties, naming the clauses changed, effective date, the version/date of the agreement amended | VF (repo) §31.12 (company-approved: written mutual amendment; precedence limited to the terms amended); VF (statute) Contract Act s.62; the contract's own amendment clause governs form |
| After signing, many changes | **Amended and restated agreement** (replaces the text in full from its effective date, preserving accrued rights) | **IP** |
| After signing, new parties/obligor | **Novation** (s.62 "substitute a new contract") | VF (statute) |
| After signing, commercial order change | New/changed **Order Form**, never touching MSA terms | VF (repo) §31.11 (changes follow §31.14 unless the MSA says otherwise) |

---

## Part D — Definitions, with MSA/NDA examples

| Term | Meaning (IP unless marked) | MSA / NDA example | When used | Indian nuance |
|---|---|---|---|---|
| **Schedule** | A part of the agreement, incorporated by the body, usually holding operative detail (pricing, SLA, DPA) | MSA Schedule 2 — Service Levels | Operative terms that change by deal | Indian drafting commonly uses "Schedule" for operative parts and "Annexure" for attached documents/forms; usage is not uniform |
| **Annexure** (Annex) | A document attached for reference or as a form | Annexure A — Order Form template; Annexure B — board resolution format | Forms, specimens, technical descriptions | "Annexure" is the dominant Indian/Commonwealth term; check the precedence clause — an annexure binds only as far as the body says |
| **Exhibit** | US term for an attached document | Exhibit A — Security Measures | US-style templates | Treated as equivalent to an annexure in India; avoid mixing the two terms in one contract |
| **Addendum** | A document **adding** terms to an existing agreement | NDA Addendum adding a data-sharing clause | Additions without rewriting | VF (repo) Constitution treats Amendment/Addendum together (§21, §31.12) |
| **Amendment** | A document **changing** existing terms of a signed agreement | Amendment No. 1 changing MSA payment period | Post-signing change | VF (statute) s.62 "alter"; VF (repo) §31.12 written + signed by both. **Lawyer question:** separately stampable as its own instrument |
| **Side letter** | A separate letter between the parties varying or clarifying terms, often confidential | Letter granting a one-off fee waiver | Discouraged in-house: invisible to reviewers | Under §8.2 it conflicts silently unless its precedence is express; stamp as an agreement (Maharashtra s.34 proviso (b) treats letters forming a contract as one instrument when any one is stamped — VF (statute)) |
| **Amended and restated agreement** | The whole agreement re-issued with all changes, superseding the prior text from its effective date | MSA v2 restating MSA v1 + 3 amendments | Many accumulated amendments | Fresh instrument for stamp purposes — **lawyer question** on duty and credit for duty paid |
| **Order Form** | Transaction document under an MSA | Order Form for 4 GPU servers, 12 months | Each purchase | VF (repo) §31.11; Maharashtra Art. 5(h)(A)(iv) may make value-bearing orders stampable — **lawyer question** |

**Stamp duty on supplementary instruments (IP + lawyer question):** each amendment, addendum, side letter or restatement is
generally a separate instrument chargeable on its own under the State Act (in Maharashtra, Schedule I Article 5 unless
another article applies). Maharashtra s.4 relief for several instruments in one transaction is limited to development
agreements, sale, lease, mortgage and settlement (VF (statute)), so it does not obviously cover a commercial MSA chain.

---

## E. Recommendations for LegalMind (REC — nothing here is decided)

1. **One deal sheet for creation and review.** The A.3 questionnaire is the same object LAWYER_REASONING_RESEARCH Phase 2
   needs to judge applicability. Build it once; creation fills it before the draft, review fills it from an uploaded
   contract.
2. **Template = lawyer-supplied prose + clause tags.** Each clause carries: Constitution topic, class (P/F/A), the
   input fields it uses, its condition. LegalMind renders; it never writes clause prose (rule 7; AM-25 forbids the assist
   lane producing a legal position).
3. **Fallback library as configuration** — per Constitution topic, lawyer-approved counter-proposal wording, each with
   who may use it. Storing it changes no verdict; whether using it skips a Legal Decision is a decision for the owner and
   lawyer (lock amendment).
4. **Self-review gate**: a generated draft must evaluate 100% Acceptable before it can be sent; anything else blocks with
   the Finding.
5. **Execution metadata**: state of execution, stamp article, stamp certificate/e-SBTR number, e-sign method and audit
   certificate — stored with the executed version (new storage needs an approved amendment, `IMPL-01`).
6. **Do not build** risk scores per exception (rule 12), model-written counter-text, or a free-text clause editor for
   non-Legal users.

---

## F. Questions only LeapSwitch's commercial contracts lawyer can decide

1. **Which document is the approved master** for each type — MSA, NDA (mutual), NDA (one-way, each direction), Order
   Form, Amendment, DPA — and its approved text. The reference MSA conflicts with §9 (cap) and §10 (indemnity
   direction) and contradicts itself (§17.2 vs §17.7).
2. **Indemnity**: the template's one-way customer indemnity or §10's mutual framework?
3. **One-way NDAs**: may LeapSwitch issue a one-way NDA where it only discloses? Only receives? (§15 makes one-directional
   Unacceptable; the NDA standards cover only the receiving side.)
4. **The gaps**: approved wording for force majeure, warranty disclaimer, liability carve-outs (fraud, death/injury,
   non-excludable), return/destruction, compelled disclosure, permitted disclosees, NDA exclusions, assignment, notices,
   boilerplate, and the MSA-vs-SLA / MSA-vs-DPA precedence.
5. **Fallback positions per clause**, beyond those the Constitution names (§9, §10, §12 vendor-only, §16, §31.15) —
   and for §11, §13, §15, which say "NOT DEFINED".
6. **Who approves which deviation** (approval matrix by topic and value), and whether any fallback is pre-approved
   (which would amend the zero-tolerance rule's effect — owner + lock record).
7. **C-28**: immediate suspension (§13) vs notice-and-cure (§16) for non-payment — the template needs one text.
8. **Authorised signatories** for LeapSwitch per document type and value; what authority evidence to demand from the
   client (board resolution, POA) and when.
9. **E-sign vs wet ink** per document type; whether Aadhaar eSign / DSC is required or platform click-to-sign suffices;
   counterparts clause.
10. **Stamping**: which party pays, which State's Act applies for e-signed out-of-state counterparties, which Article
    applies to an MSA, an NDA, an Order Form and an amendment, and whether duty is assessed on contract value
    (Maharashtra Art. 5(h)(A)(iv)) — Constitution §27 Item 18.
11. **Post-signing variation**: when an amendment vs an amended-and-restated agreement vs a new Order Form; whether
    side letters are ever allowed.
12. **Non-solicitation** enforceability under s.27 (2 years, §15), and the s.74 structuring of early-exit fees (§27 Item 4)
    and late interest (Item 3), before those texts are fixed in a template.
13. **DPDP**: which party drafts the DPA per relationship and its minimum contents under s.8 (§27 Items 5, 6, 20).
14. **Incorporation statute** to print in the parties block (Companies Act 1956 vs 2013 — §27 Item 16).

---

## G. Sources

Repository: `docs/02-legal-domain/LEGAL_CONSTITUTION_L1.14.md` (§§4, 7–16, 20–22, 24–27, 28.4.1, 31); `backend/config/company_standards/*.json`;
`docs/00-project/LOCKED_DECISIONS.md` (AM-146, 157, 158, 173, 174, 175, 223, 224); `docs/architecture/DOCUMENT_BUILDER_RND.md`;
`docs/architecture/LAWYER_REASONING_RESEARCH.md` §6–§8.

Statutes (India Code copies in `legal-docs/Indian_Laws_and_Acts/`): Indian Contract Act 1872 ss.10, 23, 27, 62, 73, 74;
IT Act 2000 ss.3A, 5, 10A, First and Second Schedules; DPDP Act 2023 s.8; Companies Act 2013 ss.12, 21, 22; BSA 2023 ss.66, 86.

Web:
- Maharashtra Stamp Act 1958 — https://prsindia.org/files/bills_acts/acts_states/maharashtra/1958/Act60of1958MH.pdf ; https://igrmaharashtra.gov.in/SB_PUBLICATION/DATA/Schedule/_STAMP_ACT%20amended%2003.6.2022.pdf
- Indian Stamp Act 1899 — https://indiacode.nic.in/bitstream/123456789/15510/1/a1899-2%20.pdf ; s.35 summary https://lawx.in/acts/section/27/370/4538
- Maharashtra amendments — https://www.khaitanco.com/sites/default/files/2026-07/Maharashtra%20Stamp%20Amendment%20Bill_17072026.pdf ; https://www.argus-p.com/updates/updates/maharashtra-stamp-amendment-ordinance-2024/
- 2023 INSC 1066 — https://www.verdictum.in/app-lite/court-updates/supreme-court/unstamped-arbitration-agreement-not-void-1509237
- Ironclad — https://ironcladapp.com/product/workflow-designer ; https://ironcladapp.com/resources/articles/modern-contract-playbook ; https://support.ironcladapp.com/hc/en-us/articles/12250550045463-Create-a-Conditional-Clause-in-Workflow-Designer ; https://support.ironcladapp.com/hc/en-us/sections/12271366818327-Review-and-Approve ; https://support.ironcladapp.com/hc/en-us/articles/12448503998871-Archive-Step-Overview ; https://support.ironcladapp.com/hc/en-us/articles/12274718080791-Compare-Document-Versions ; https://support.ironcladapp.com/hc/en-us/articles/12274791253271-Update-a-Workflow-s-Properties-and-Documents ; https://support.ironcladapp.com/hc/en-us/articles/24948981301143-Create-Ironclad-AI-Playbooks-in-Workflow-Designer
- Juro — https://intercom.help/juro/en/articles/5653125-adding-and-managing-rules ; https://intercom.help/juro/en/articles/5652971-using-smartfields ; https://intercom.help/juro/en/articles/5653139-handling-approvals ; https://intercom.help/juro/en/articles/5897857-negotiating-in-juro ; https://intercom.help/juro/en/articles/5653051-collaborating-on-contracts-comments-suggestions
- DocuSign CLM — https://support.docusign.com/s/document-item?language=en_US&bundleId=yks1643320936212&topicId=qkt1576610095922.html ; https://support.docusign.com/s/document-item?language=en_US&bundleId=yff1696971835267&topicId=uww1698167288211.html ; community (IP only) https://community.docusign.com/docgen-115/can-you-have-document-generation-fields-under-a-conditional-logic-field-26096
- Icertis — https://www.icertis.com/contracting-basics/contract-authoring/ ; https://iciwikiapac.icertis.com/ICIHelp8.2/index.php?title=Clauses
- Microsoft Word — https://support.microsoft.com/en-US/Word/compare-document-differences-using-the-legal-blackline-option ; https://support.microsoft.com/en-us/word/combine-document-revisions
- GSTIN structure (secondary) — https://taxguru.in/goods-and-service-tax/gstin-goods-and-service-tax-identification-number-structure.html
