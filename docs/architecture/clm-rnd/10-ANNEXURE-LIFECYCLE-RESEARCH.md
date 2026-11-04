# CLM R&D — 10 · Accepted client changes: the Special Conditions annexure, precedence, execution and amendments

`📁 PROPOSAL` — research only. Decides nothing, authorizes no build, amends no lock, and drafts no legal text as
approved. 2026-11-04, worktree `clm-rnd-20261102`. Companion to [00-CLM_RND_REPORT.md](00-CLM_RND_REPORT.md) §10 and
[05-verification-ledger.md](05-verification-ledger.md). Counterparties are "the client" throughout (no client name is
recorded here, including the client named in the executed MSA in `legal-docs/`).

**The owner's question.** When LeapSwitch's standard MSA template stays unchanged and the client's negotiated changes
are accepted, how do contract lawyers record them in the final contract? The owner expects a "Special Conditions"
annexure at the end that lists everything accepted.

**Short answer.** That is an established, documented practice. The Government of India's own procurement manual
requires it for standard conditions: *"The GCCs should not be altered and changes, if any, in conditions of contract
should only be made through the Special Conditions of Contract."* Large cloud providers use the same layered method to
vary their own standard terms (Salesforce's MSA replaces named sections "with the following section" for each
jurisdiction). The method works only if **an express order-of-precedence clause** ranks the annexure above the body
for the clauses it names. **LeapSwitch's current paper does not have one.** The template MSA's §21.3 is headed "Order of
Precedence" but sets no order. The executed MSA of 28 July 2026 says the **MSA body prevails** over "any other agreement
entered between the Parties". As written, that wording works against a Special Conditions annexure. The precedence
wording is therefore the first decision for the lawyer (Q-1).

## How to read the grades

| Grade | Meaning |
|---|---|
| **P** | Primary. The official text was read for this report: the statute's India Code copy in `legal-docs/Indian_Laws_and_Acts/`, the issuer's own published contract or manual, or the vendor's own help or API page. |
| **P-m** | Primary text read from a mirror. The document is the issuer's own, but it was fetched from another government host because the issuer's site refused the request (noted against each one). |
| **S** | Secondary. Law-firm or legal-press commentary, a search-engine summary, or a forum. It is not to be relied on without checking the primary source. |
| **R** | Repository. LeapSwitch's own documents in `legal-docs/` (gitignored, 54.6) or the Legal Constitution L1.15. Each is quoted only as a short cited excerpt. |

Sites that could not be reached in this session, so that a claim stays at S: `main.sci.gov.in` / `digiscr.sci.gov.in`
(DNS failure, as in VL-29), `assets-bg.gem.gov.in` (HTTP 403), `support.ironcladapp.com` (HTTP 403, as in VL-39),
`adamsdrafting.com` (HTTP 403), and the Lexis+ glossary (paywalled).

---

## Q1 · Practice: four ways to record agreed changes

### 1.1 The four instruments

| Instrument | When it is used | How it is drafted | Evidence |
|---|---|---|---|
| **Special Conditions / schedule of agreed variations** (before signing) | The provider's standard form must stay byte-identical across customers, and the deal-specific changes are agreed before execution | A separate part of the same instrument. It lists each change against the clause it varies: clause X "is replaced by", "is deleted", or "a new clause X.Y is added". An express precedence clause ranks it above the general conditions | DoE Manual (P), Salesforce MSA (P), GeM GTC (P-m), BHEL ATC (P), Lexis glossary (S) — below |
| **Redline in the body** (before signing) | Bespoke contracts, or a provider that is willing to fork its template per deal | The agreed changes are written into the clauses themselves, and the signed copy is clean. Standard-form drift results, because every customer's MSA differs | This is the approach the DoE Manual tells government buyers **not** to use for GCCs (P, below) |
| **Side letter** (at or after signing) | A one-off concession the parties want kept out of the main document | A separate letter. It binds only as far as its own precedence wording says. Nobody reviewing the main contract sees it | Report 02 C.4 / 00 §10 (practice, already recorded). Maharashtra s.34 proviso (b) (VL-28) |
| **Amendment / addendum** (after signing) | Any change to a signed agreement | A separate signed instrument that names the clauses changed, its effective date, and the version and date of the agreement it amends. It prevails only as to the terms it amends | Contract Act s.62 (P, VL-36). Constitution §31.12 (R). LeapSwitch MSA §21.9 (R). Google Cloud §14.13 (P) |

### 1.2 Evidence that "standard conditions untouched + special conditions" is the recognised method

* **Government of India, Ministry of Finance, Department of Expenditure, *Manual for Procurement of Goods* (updated June
  2022), para 5.1.1(b)** — *"In tenders containing General Conditions of Contract (GCC), additional/ special conditions
  to be incorporated in the tender document, shall be need based and specific. The GCCs should not be altered and
  changes, if any, in conditions of contract should only be made through the Special Conditions of Contract."* Para
  5.1.2(viii) adds: *"Special Conditions of Contract (SCC) (instead of modifying GCC every time, it is better to have it
  as a separate section)"*. **P-m**: the DoE manual was read from the copy that IIT Kharagpur hosts
  (https://sric.iitkgp.ac.in/web4/public/docss/Manual%20for%20Procurement%20of%20Goods.pdf). Its cover reads "Government
  of India, Ministry of Finance, Department of Expenditure". The issuer's index is https://doe.gov.in.
* **Salesforce Main Services Agreement (version "SFDC-MSA, October 15, 2026"), §12.12, §12.16 and §12.17.** The
  standard body is left untouched. Jurisdiction-specific variations follow it as numbered operations, each naming the
  clause and its heading: *"(1) Section 8.2 "SFDC Warranties" is replaced by the following :"* · *"(2) a new Section
  12.12.1 is added as follows:"* · for India, *"12.16.2 Section 5.2 "Invoicing and Payment" of this Agreement is replaced
  with the following section:"*, followed by the full replacement text. **P**:
  https://www.salesforce.com/en-us/wp-content/uploads/sites/4/documents/legal/salesforce_MSA.pdf. This is the closest
  published model of the operation wording the owner describes. It is a provider's own variation layer, not a
  per-customer annexure.
* **GeM General Terms and Conditions on GeM 4.0, Version 1.29, dated 25 March 2026, §1.** The contract is governed by
  the GTC *"(unless otherwise superseded by Product / Service specific Special Terms and Conditions (STC) … and
  BID/Reverse Auction Specific Additional Terms and Conditions (ATC) as applicable)"*. **P-m**: gem.gov.in returned 403.
  The text was read from https://www.iiserbpr.ac.in/uploads/file_upload/GeM%20Latest%20Guidelines%20Mar%202026.pdf,
  whose title page reads "General Terms and Conditions on GeM 4.0 (Version 1.29)". GTC §6(x) also makes the buyer
  *"solely responsible for the impact of these additional clauses"*. In other words, the party that adds special
  conditions owns them.
* **Schedule of amendments (UK construction practice).** A Lexis+ UK glossary entry describes it as a compiled list of
  agreed departures from a standard form, to be read alongside the form, which can delete, substitute or add clauses
  clause by clause. **S**: https://www.lexisnexis.com/en-gb/legal/glossary/schedule-of-amendments (paywalled; known only
  from the search summary).

### 1.3 Drafting conventions observed in the published examples

| Element | What the published examples do | Source |
|---|---|---|
| Structure | One entry per varied clause, in clause order, each a numbered item | Salesforce §12.12 (1)–(5) **P** |
| Reference to the clause varied | Section number **and** heading in quotes: *Section 8.2 "SFDC Warranties"* | Salesforce **P** |
| Replace | *"is replaced by the following"* / *"is replaced with the following section"*, then the full new text, renumbered as the clause it replaces | Salesforce **P** |
| Insert | *"a new Section 12.12.1 is added as follows"*. The new number is stated | Salesforce **P** |
| Delete | No "is deleted" example was found in the primary sources read. The Lexis glossary records deletion as one of the operations (**S**). This is a gap: the lawyer must supply the deletion wording | — |
| Specific over general | *"as between two Clauses of this Agreement, the provisions of a specific Clause relevant to the issue under consideration shall prevail over those in a general Clause"* | Delhi PDS model contract (MeitY Model RFP 2018 template) **P-m**, below |
| Initials on each page | No Indian statute requires them. They are practice and evidence against page substitution | §3.3 below |
| Position | Annexures follow the execution block in LeapSwitch's executed MSA: "Annexure-1" (SLA) starts directly after "IN WITNESS WHEREOF…". The Delhi PDS model places Schedules I–VI, then Annexures A–D, after the body | **R**; **P-m** |

---

## Q2 · Order-of-precedence clauses: real published wording

| Document | Precedence wording (verbatim excerpt) | Hierarchy | Grade / URL |
|---|---|---|---|
| **Google Cloud Terms of Service §14.16** | *"If there is a conflict between the documents that make up this Agreement, the documents will control in the following order (of decreasing precedence): the Cloud Data Processing Addendum, any applicable Order Form, the remainder of this Agreement (excluding the URL Terms), and the URL Terms…"*. §14.13: an amendment *"must be in writing, signed by both parties, and expressly state that it is amending this Agreement."* | DPA > Order Form > body > URL policies | **P** https://cloud.google.com/terms |
| **Salesforce MSA §12.3** | *"…any term or condition stated in a Customer purchase order or in any other Customer order documentation (excluding Order Forms) is void. In the event of any conflict or inconsistency among the following documents, the order of precedence shall be: (1) the applicable Order Form, (2) this Agreement, and (3) the Documentation."* | Order Form > body > documentation. **Customer PO terms are void** | **P** (URL above) |
| **AWS Customer Agreement §11.2** (as returned by the fetch) | The Agreement controls over the Policies, *"except that the Service Terms will control over this document"*. Terms in a customer order *"different from or in addition to"* the Agreement do not bind | Service Terms > body > Policies | **P**, via a fetch summary that quoted the text. https://aws.amazon.com/agreement/. Re-read before quoting it in any document |
| **Microsoft Customer Agreement** | Not read in primary. A reseller's amendment form says the amendment controls over the agreement | — | **S** https://www.bechtle.com/de-en/clouds/cloud-services/microsoft-services/microsoft-amendments |
| **BHEL GeM ATC (Bid GEM/2024/B/5686614, 23.12.2024)** | *"In case of any conflict, terms and conditions stipulated in ATC shall supersede those in GTC on GeM."* Order of precedence: *"Amendments to Order/ Contract … Purchase Order … LOI/LOA … Clarifications agreed … Corrigenda to NIT, with those of later date having precedence … Technical Specifications … Additional Terms & Conditions (ATC) … Special Conditions of Contract (SCC), if any … GeM General Terms & Conditions (GTC)"* | **Amendment > order > … > ATC > SCC > GTC**: the later and more specific document wins | **P** (PSU's own tender host) https://tenders.bhel.com/sites/default/files/GeM_ATC-2024-12-23-04%3A33%3A49.docx |
| **Delhi PDS model contract, "Contract Agreement for Model RFP Templates for Implementation Agencies" (MeitY Model RFP 2018 template, adopted by GNCTD)** | *"as between the provisions of this Agreement and the Schedules/Annexures, the Agreement shall prevail, save and except as expressly provided otherwise in the Agreement or the Schedules/Annexures"* and *"the terms of this Agreement shall prevail over the Annexures / Schedules and Annexures / Schedules shall prevail over the contents and specifications of the RFP."* §23.7: *"No amendment, variation or other change to this Agreement … shall be valid unless authorised in accordance with the change control procedure … made in writing and signed by the duly authorised representatives"* | **Body > Schedules/Annexures > RFP**, unless a schedule *expressly* says otherwise | **P-m** https://fsd.delhi.gov.in/sites/default/files/FS/tender/10.appendix_iv_ver0.c_delhi_pds_rfp_for_pos.pdf. MeitY's covering letter: https://audit.delhi.gov.in/sites/default/files/generic_multiple_files/selection_of_implementation_agencies_for_e-governance_projects.pdf. MeitY's own page was not reached |
| **LeapSwitch MSA template, July 2025 (`MSA.pdf`, `MSA-Feb.pdf`) §21.3** | Headed *"Entire Agreement and Order of Precedence"*, but the text only says that the Agreement *"along with the purchase order form, the terms of use and applicable policies, represents the entire agreement"*. **No order is stated.** §21.9: *"may not be modified except by an instrument in writing signed by the duly authorized representatives of the Parties."* | **None** | **R** |
| **LeapSwitch executed MSA, 28 July 2026 (`legal-docs/`) §24.10** | *"All annexures to this Agreement are hereby incorporated in this Agreement. … In the event of any conflict or inconsistency between the provisions of the Master Services Agreement, SLA, AUP, Purchase Order, or any other agreement entered between the Parties, the provisions of the Master Services Agreement shall prevail."* | **MSA body > everything**. A Special Conditions annexure written under this wording would arguably be **overridden by the body it is meant to vary** | **R** |
| **Legal Constitution L1.15 §8.2** | *"where the applicable agreement contains an express order-of-precedence clause, Legal Mind shall follow that agreed precedence. … must not arbitrarily select one document as controlling — the correct output is REVIEW REQUIRED"*. No general hierarchy is invented. Counsel validates the wording but does not design the rule | Follow the express clause; otherwise REVIEW REQUIRED | **R** |
| **Constitution §31.12** | *"The amendment prevails only as to the specific terms it amends; all other original terms remain unchanged"* (Company-approved) | Limited-scope precedence | **R** |
| **Constitution §31.11** | *"Where a PO and the governing MSA conflict, the MSA prevails"* (Company-approved) | MSA > PO | **R** |

**Pattern.** Two families exist:

1. **The specific document wins.** Google Cloud, Salesforce, AWS's Service Terms, BHEL, GeM and the DoE Manual all
   rank the deal-specific or product-specific layer above the general terms. This is the hierarchy the owner expects:
   special conditions > MSA body > order form / PO > policies.
2. **The body wins unless a schedule expressly says otherwise.** The MeitY-derived model takes this approach.

LeapSwitch's executed paper is a third, stricter variant: the body wins over "any other agreement". The owner's
hierarchy is therefore **not** what LeapSwitch's paper currently says. Constitution §31.11 (MSA > PO) is consistent with
the owner's ordering of the lower layers. Nothing yet ratifies "Special Conditions > MSA body".

---

## Q3 · Indian law (primary where reached)

### 3.1 Modification, and reading the contract as a whole

* **Contract Act 1872 s.62** — *"If the parties to a contract agree to substitute a new contract for it, or to rescind
  or alter it, the original contract, need not be performed."* **P** (India Code copy,
  `legal-docs/Indian_Laws_and_Acts/Indian_Contract_Act_1872_indiacode.pdf`; https://www.indiacode.nic.in/handle/123456789/2187;
  already verified as VL-36). A post-signature amendment is an agreed "alteration". A pre-signature Special Conditions
  annexure is not a modification at all: it is part of the one contract formed at execution.
* **Bharatiya Sakshya Adhiniyam 2023 s.95** (formerly Evidence Act s.92). Once the terms are reduced to a document, *"no
  evidence of any oral agreement or statement shall be admitted … for the purpose of contradicting, varying, adding to,
  or subtracting from, its terms"*. A proviso allows proof of *"any distinct subsequent oral agreement to rescind or
  modify"*, except where the contract is by law required to be in writing or is registered. **P** (`legal-docs/…/Bharatiya_Sakshya_Adhiniyam_2023.pdf`).
  Consequence for practice: an accepted change that is **not** written into the signed instrument (for example, agreed
  only by e-mail) is hard to prove against the written terms. This is the evidential reason for listing every accepted
  change in the signed annexure.
* **Reading the whole contract.** In *Nabha Power Ltd v. Punjab State Power Corporation Ltd* (Civil Appeal 179 of 2017,
  decided 5 October 2017, Nariman and Kaul JJ.), the Supreme Court held that *"the multi-clause contract inter se the
  parties has, thus, to be understood and interpreted in a manner that any view, on a particular clause of the contract,
  should not do violence to another part of the contract."* The Delhi High Court applied it in *GAIL v. Saw Pipes*,
  FAO(OS)(COMM) 313/2019, 29 October 2024. **S**: the SCR PDF on digiscr.sci.gov.in did not resolve. The source is
  https://www.livelaw.in/amp/arbitration-cases/multi-clauses-contract-interpreted-in-manner-view-on-particular-clause-not-do-violence-to-another-part-of-contract-delhi-high-court-274998.
  The rule that a specific clause beats a general one appears as **contract wording** in the MeitY-derived model
  (above, P-m). No Supreme Court authority for it as a general canon was verified in this session.

### 3.2 Do annexures form part of the contract? (incorporation by reference)

* **Statutory recognition, in the arbitration context only.** Arbitration and Conciliation Act 1996 s.7(5): *"The
  reference in a contract to a document containing an arbitration clause constitutes an arbitration agreement if the
  contract is in writing and the reference is such as to make that arbitration clause part of the contract."* **P**
  (`legal-docs/…/Arbitration_Conciliation_Act_1996.pdf`).
* **Case law.** In *M.R. Engineers & Contractors v. Som Datt Builders* (2009) 7 SCC 696 and *NBCC (India) Ltd v.
  Zillion Infraprojects* 2024 SCC OnLine SC 323, the Court distinguished a "single-contract" case (a general reference
  incorporates) from a "two-contract" case (an arbitration clause in another contract needs a **specific** reference).
  **S**: https://www.scconline.com/blog/post/2024/03/23/reference-to-document-in-contract-show-intention-incorporate-arbitration-clause-supreme-court/
  and https://disputeresolution.cyrilamarchandblogs.com/2024/04/unravelling-the-distinction-between-reference-to-and-incorporation-of-arbitration-clauses/.
* **What this means.** An annexure that is attached to the signed instrument and expressly incorporated by the body
  (*"All annexures to this Agreement are hereby incorporated"*, executed MSA §24.10, R) is part of one contract. That is
  the single-contract case. A Special Conditions **separate** from the executed instrument (a side letter, or a later
  document) is closer to the two-contract case. The strict-reference line of cases concerns arbitration clauses. Applying
  it to commercial terms generally is an **inference** for the lawyer, not settled law.

### 3.3 Execution: initials, signatures and e-sign

* **Initials.** No Indian Act requires a contract to be signed or initialled on every page: *"There is no Act, rule,
  regulation, or law in India that requires a contract to be signed or initialled on every page"* (LiveLaw, 7 August
  2025, in-house counsel column; **S**,
  https://livelaw.in/articles/everyday-questions-inhouse-counsels-automated-chatbot-responses-300141). Initialling is a
  safeguard against a page being substituted after signing, and banks often insist on it. That is practice, **S**. The
  one statutory analogue found is in stamp law: Maharashtra Stamp Act s.13 Explanation I requires the executant to sign
  an **impressed-stamp sheet that carries no text**, with an endorsement that it is attached. Explanation II says plain
  paper subjoined to a stamp sheet *"may or may not be signed by the executant but where it is not so signed it shall
  not render the instrument not duly stamped."* **P** (IGR consolidated text,
  https://igrmaharashtra.gov.in/SB_PUBLICATION/DATA/Schedule/_STAMP_ACT%20amended%2003.6.2022.pdf). So in Maharashtra,
  unsigned continuation pages do not defeat stamping. Initials are evidential, not formal.
* **Electronic signature.** IT Act s.5: a law that requires a signature is satisfied by an electronic signature affixed
  as prescribed (**P**, VL-32). s.3A and the Second Schedule cover Aadhaar/e-KYC e-sign (**P**, VL-33). s.10A: an
  electronic contract is not unenforceable for that reason alone (**P**, VL-32).
* **Does one e-signature cover the annexures?** IT Act s.3(2): authentication *"shall be effected by the use of
  asymmetric crypto system and hash function which envelop and transform the initial electronic record"*. The hash
  function is defined so that an electronic record *"yields the same hash result every time"* and two records cannot
  share one result (**P**, `legal-docs/…/IT_Act_2000_indiacode.pdf`). A digital signature therefore authenticates the
  **whole electronic record that was hashed**. If body and annexure are one PDF, any change to either breaks
  verification. If the annexure is a separate file, it is not covered unless it is signed too. This is a technical
  reading of s.3(2) for the lawyer to confirm, not case law. GeM itself applies Aadhaar e-sign to its documents and
  states *"The e-sign is at par with digital signatures"* (GTC v1.29 §1, **P-m**). DocuSign issues **one** Certificate of
  Completion per envelope. Splitting or merging the PDFs afterwards can break signature verification (DocuSign community
  answers; **S**, https://community.docusign.com/esignature-111/can-i-send-multiple-documents-in-one-envelope-but-merge-each-document-with-certificate-of-completion-separately-23158).
* **The Maharashtra Stamp Act follows the IT Act.** "signed" and "signature" include attribution of an electronic
  record under IT Act s.11, and "document" includes an electronic record under IT Act s.2(1)(t) (s.2 Explanations,
  **P**, IGR text).

### 3.4 Stamp duty: annexure versus amendment (Maharashtra)

* **"Instrument"** (s.2(l)) includes every document by which any right or liability *"is, or purports to be created,
  transferred, limited, extended, extinguished or recorded"* (**P**, IGR text).
* **An annexure executed with the MSA** is part of the one instrument, so there is no separate charge by reason of the
  annexure. This is an inference from s.2(l) and the single-instrument reading. **S/inference, lawyer to confirm.**
* **s.5:** an instrument *"comprising or relating to several distinct matters or transactions shall be chargeable with
  the aggregate amount of the duties"* of separate instruments (**P**). Whether a Special Conditions annexure is a
  "distinct matter" is a lawyer question. It most likely is not, because it varies the same transaction.
* **A post-signature amendment** "limits, extends … or records" a right, so it is plausibly a **separate instrument
  chargeable on its own**, most likely under Schedule I Article 5 (agreement). Art. 5(h)(B) is ₹500 since Mah. Act IX
  of 2025, and Art. 5(h)(A)(iv) covers value-bearing agreements (VL-30, VL-31). **S/inference**. Which article applies
  is the lawyer's call (as already recorded in 00 §10).
* **s.4** (several instruments, one transaction) is limited to development agreements, sale, lease, mortgage and
  settlement (**P**, already recorded in report 02). It does not obviously relieve an MSA plus amendment chain.
* **Timing:** s.17 allows stamping before or at execution, or on the next working day (VL-26). s.34 makes an
  unstamped instrument inadmissible until duty and penalty are paid (VL-28). LegalMind derives no Requirement or
  threshold from any of this. Statutes are background law (CLAUDE.md).

---

## Q4 · CLM products: deviations, the executed package, and amendment links

| Product | Deviation / special terms | Final package | Amendment ↔ parent | Grade / source |
|---|---|---|---|---|
| **Oracle Contracts** (closest documented "deviation report") | *"checks for invalid, nonstandard, and missing clauses by comparing the contract terms in the contract with those in the latest version of the contract terms template"*. Also checks policy deviations through rules. With "Generate for Approval", *"A copy of the report is automatically attached to the contract approval notification"* as a PDF, and it is regenerated on submission | The report is an **internal approval artefact**, not a client-facing annexure | — | **P** https://docs.oracle.com/en/cloud/saas/sales/fasca/how-reviewing-contract-deviations-work.html |
| **Ironclad** | Playbooks give *"clause-level guidance and recommended fallback language"* attached per workflow (support snippet). Approval resets are configurable (VL-39) | — | API: the parent link type *"Must be "amendment""*; *"No self-parenting, no amending amendments, and no cycles"*; property roll-ups to the parent keep an `originalValue`, the parent lists its `amendments`, and deleting the amendment reverts the parent | **P** (API) https://developer.ironcladapp.com/docs/record-amendments-crud-api-guide. **S** (support centre, 403) |
| **SpotDraft** (India-founded, VL-41) | — | Supporting files *"do not exist as separate records"*. A document needing its own signature *"should be uploaded as a separate contract … and then linked"* | Relationship types *"Child, Parent, Amendment, or Addendum"* | **P** https://help.spotdraft.com/articles/9796058949-connecting-your-contracts-linking-documents-in-spotdraft |
| **Juro** | Changes after approval re-trigger approval (VL-39, **P**) | Addenda can be attached to a contract | The blog suggests duplicating the original to draft an amendment. No formal parent link was found | **S** https://blog.juro.com/contract-amendment |
| **LegalOn** | First-party playbook: a negotiation framework with **fallback** and **non-negotiable** positions. Redlines are tagged as meeting the fallback or violating a non-negotiable | — | — | **S** (search summary of help.legalontech.com articles 11709754 and 10159978) |
| **DocuSign CLM** | No official page was reached. The community shows record linking exists and a "family" tree is a feature request | One Certificate of Completion per envelope (eSignature) | Users pick a parent document when generating an amendment form | **S** https://community.docusign.com/ideas/family-of-documents-in-clm-23078 |
| **Icertis** | Marketing says it flags non-standard terms. No documentation was reached (VL-39) | — | — | **S** |

**Pattern.** No vendor documentation found describes auto-generating a *client-facing* "Special Conditions" annexure.
Vendors separate two things:

1. The **internal deviation record**: Oracle's deviation report, Ironclad and LegalOn playbook statuses. This is
   attached to the approval.
2. The **signed contract text**, which is clean.

Post-signature changes are **separate child records with exactly one parent** (Ironclad, SpotDraft). The parent shows
a rolled-up current value with the original kept beside it (Ironclad). The owner's annexure is therefore a
LegalMind-specific output, generated from the accepted-change list that already exists (07 §1.2 change list). Every
entry needs a trace to its approval.

---

## Q5 · Formatting conventions for annexures in Indian commercial contracts

| Convention | Observed | Source |
|---|---|---|
| Heading | "SCHEDULE – II – CHANGE CONTROL SCHEDULE"; "ANNEXURE – A – FORMAT FOR CHANGE CONTROL NOTICE" (Delhi PDS model). "Annexure-1", "Annexure-2", "Annexure-3A" (LeapSwitch executed MSA) | **P-m**; **R** |
| Schedule vs Annexure | MeitY-derived model: Schedules hold operative terms (change control, exit, payment) and Annexures hold formats and lists. LeapSwitch's template defines "Clause" or "Schedule" (§2.4), while its executed MSA uses "Annexure" for the SLA and AUP. **Usage is not uniform** (as recorded in 00 §10) | **P-m**; **R** |
| Integral-part statement | *"This Agreement, including its Schedules and Annexures, represents the entire agreement"* (Delhi PDS); *"All annexures to this Agreement are hereby incorporated in this Agreement"* (executed MSA §24.10). The phrase "forms an integral part of the Agreement dated …" is common practice, but no primary specimen was read in this session (**S**) | **P-m**; **R** |
| Cross-reference to parent | Each annexure is referred to from the body by its definition (*"the SLA annexed as Annexure-1 hereto"*, executed MSA) | **R** |
| Numbering | Roman for schedules (I–VI), letters for annexures (A–D), in the Delhi PDS model. Arabic with suffix (1, 2, 3A) in the executed MSA | **P-m**; **R** |
| New page | Each schedule and annexure begins on its own page in both specimens | **P-m**; **R** |
| Page numbering | "Page 6 of 95" running through body and schedules (Delhi PDS). Salesforce: "Page 15 of 17" running through body and local-law variations | **P-m**; **P** |
| Initials blocks | Practice only (§3.3). No primary specimen with initials blocks was read | **S** |
| Position | After the execution block (executed MSA). After the body (Delhi PDS). The Delhi PDS signature position was not checked | **R**; **P-m** |

---

## What this means for LegalMind (requirements, each traced)

These are product requirements for the drafting lane, not legal text. Every sentence that would appear *in* the
contract (the precedence clause, the annexure's opening statement, the delete wording) comes from the lawyer (rule 21,
Constitution §8.2: Counsel validates, the system does not invent).

| # | Requirement | Traced to |
|---|---|---|
| **R-1** | Accepted client changes are **not** written into the template body. The body stays the published template version, byte-identical. Every accepted change is rendered as one entry in a separate **Special Conditions** part of the same instrument | DoE Manual 5.1.1(b) (P-m); GeM GTC §1 (P-m); Salesforce §12.12/§12.16 (P); owner request |
| **R-2** | Each entry carries: a sequential number · the varied clause's **number and heading** as in the pinned template version · one operation (**replaced** · **deleted** · **inserted after** · **added**) · the full verbatim agreed text, with no paraphrase and no summary. The operation wording comes from a lawyer-approved set | Salesforce operation wording (P); 1.3 delete gap; rule 7/21 |
| **R-3** | Generation is **blocked** unless the template carries a lawyer-approved, express precedence clause that ranks the Special Conditions above the body **for the clauses they name only**. Without one, the output is REVIEW REQUIRED, never a guess. The current template §21.3 sets no order and the executed MSA §24.10 ranks the body first, so today the block fires | Constitution §8.2, §31.12 (R); MSA §21.3, executed MSA §24.10 (R); Delhi PDS "save and except as expressly provided" (P-m) |
| **R-4** | The annexure names its parent: agreement title, template key and version, agreement date, parties. It is referenced from the body. Its opening statement is lawyer-supplied text | Executed MSA §24.10 incorporation (R); §3.2 single-contract reading (P/S); Constitution §31.12 "reference the version/date" (R) |
| **R-5** | Layout: the annexure starts on a new page, under one consistent term (Annexure **or** Schedule, chosen by the lawyer). Page numbers ("Page x of y") run continuously through body and annexures. Position (before or after the execution block) is a template setting | §5 specimens (P-m/R); page-substitution rationale (S) |
| **R-6** | Execution produces **one** PDF (body + Special Conditions + other annexures) that is signed once. For e-sign, the hash covers every page. Splitting or merging after signing is forbidden. An initials block per page or per annexure is an **optional** template element, for wet-ink execution only | IT Act s.3(2) hash (P); DocuSign one certificate per envelope (S); no initials requirement (S); Stamp Act s.13 Expl. II (P) |
| **R-7** | Every Special Conditions entry links to the accepted client change and review point it came from, who accepted it, and when (append-only audit). The annexure is regenerated deterministically from that list. Any text change after approval resets approval | 07 §1.2 change list; Juro approval reset (P, VL-39); rule 17; Oracle regenerate-on-submit (P) |
| **R-8** | The **internal** deviation record (our position, why it was accepted, who approved) is separate from the **client-facing** annexure. No internal position, Constitution citation or reviewer note enters the annexure | Oracle deviation report attached to the approval, not the contract (P); LegalOn fallback/non-negotiable statuses (S); `LEGAL-02`, `SEC-07` |
| **R-9** | After signature, the executed annexure is frozen. Any further change is a new **Amendment** contract record with exactly one parent (no amending an amendment, no cycles). It names the clauses changed, its effective date and the parent's version and date. The parent shows the current value with the original kept beside it | Contract Act s.62 (P); Constitution §31.12 (R); Ironclad amendment API (P); SpotDraft relationship types (P); `A-18` proposal in 00 §10 |
| **R-10** | Side letters are not generated. An uploaded side letter is reviewed as its own record, with §8.2 REVIEW REQUIRED where its precedence is not express | 00 §10 / 02 C.4 (practice); Constitution §8.2 (R) |
| **R-11** | Stamp duty is recorded, never computed. Each instrument (MSA + annexures; each amendment) carries a stamping status field filled by a person. No article, rate or duty is inferred | Maharashtra Stamp Act s.2(l), s.5, s.17, s.34 (P); 00 §10 (lawyer's call) |
| **R-12** | A Special Conditions entry for a clause whose ratified standard is a **non-negotiable / zero-tolerance** position appears only after the Legal Decision that accepted it exists. The annexure never becomes a way round the evaluator | Zero-tolerance Legal Rule (CLAUDE.md); rule 13; `SEC-02` |

---

## Open questions for the owner / lawyer

| # | Question | Why it needs a person |
|---|---|---|
| **Q-1** | **The exact precedence wording.** Should Special Conditions prevail over the MSA body, and only for the clauses they name? How should the template's §21.3 (no order) and the executed MSA's §24.10 ("the provisions of the Master Services Agreement shall prevail") be reworded? Where do the SLA, AUP, Order Form/PO and Privacy Policy sit? | Constitution §8.2 forbids inventing a hierarchy. The published models split (specific-wins vs body-wins). This is a legal decision |
| **Q-2** | **Name and term:** "Special Conditions", "Schedule of Agreed Variations", or "Annexure – Special Conditions"? Use "Annexure" or "Schedule" consistently? | LeapSwitch's own paper mixes both (§5) |
| **Q-3** | **Operation wording**, especially deletion ("Clause X shall stand deleted" or similar). No primary specimen was found | Rule 7: no invented legal phrasing |
| **Q-4** | **Opening statement** of the annexure (for example, that it forms part of the Agreement dated …) and how it identifies the template version | The incorporation wording is legal text |
| **Q-5** | **Position:** before or after the execution block? Is a separate signature or initials block required on the annexure for wet-ink signing? | Practice varies. Initials are evidential only (§3.3) |
| **Q-6** | **Stamp duty:** is a Special Conditions annexure executed with the MSA one instrument (no extra duty)? Is each post-signature amendment chargeable separately, and under which Maharashtra article? | §3.4 rests partly on inference |
| **Q-7** | Should an accepted change that only **adds** a commercial detail (a specific fee, date or service) go into the Order Form instead of the Special Conditions? | Constitution §31.11 keeps POs subordinate and not restating MSA terms. The boundary is a drafting choice |
| **Q-8** | Are side letters ever permitted? | Already open (00 §16 item 11) |
| **Q-9** | For changes accepted **after** signing, is the policy always a numbered Amendment, or an amended-and-restated MSA after N amendments? | Already open (00 §16 item 11). Stamp consequences differ (02 C.4) |

**Not verified in this session**, and to be checked before any of it is relied on: the Supreme Court PDFs (Nabha
Power, M.R. Engineers, NBCC v. Zillion) on sci.gov.in; MeitY's own Model RFP download page; gem.gov.in's own copy of the
GTC; the Ironclad support centre; the DocuSign CLM documentation; Icertis documentation; and the Microsoft Customer
Agreement's precedence clause.
