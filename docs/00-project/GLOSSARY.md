# Glossary

Terms as used in the LegalMind specification. Every entry is drawn from `all_lock.md`; none are invented here. Each points to its canonical document rather than restating the full rule.

The distinctions marked **⚠** are ones the specification explicitly and repeatedly insists on. Conflating them breaks the legal model.

---

## Core objects

**Contract** — the ongoing agreement with a counterparty. Distinct from any single uploaded file. → [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md)

**Document Version** — one immutable uploaded document belonging to a Contract. Never edited in place; a changed document is a new version. **⚠ Contract ≠ Document Version.** → [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md)

**Review** — the central historical record of one analysis of one Document Version against one configuration snapshot. Not a Report. → [WORKFLOWS.md](../01-product/WORKFLOWS.md)

**Report** — a rendering generated *from* a Review. **⚠ The Report is not the source of truth; the Review is.** → [LEGAL_ANALYSIS_PHILOSOPHY.md](../02-legal-domain/LEGAL_ANALYSIS_PHILOSOPHY.md)

**Finding** — a clause/requirement-level comparison result. A Finding is not necessarily a problem, and is not final legal truth. → [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md)

**Evidence** — the traceable source text (document, page, section) supporting a Finding or an extracted fact. Evidence is anchored to a processing run and must survive the evaluator. → [EVIDENCE_MODEL.md](../03-document-model/EVIDENCE_MODEL.md)

**Legal Decision** — an authorized human's decision about a Finding. **⚠ Only a human with explicitly assigned legal authority makes one. The engine never does.** → [LEGAL_DECISIONS.md](../02-legal-domain/LEGAL_DECISIONS.md)

**Audit Event** — an append-only record of an action. History is added to, never rewritten. → [AUDIT_TRAIL.md](../07-audit/AUDIT_TRAIL.md)

---

## Legal configuration

**Requirement** — a legal topic the system evaluates (e.g. `LIABILITY-001` for Limitation of Liability). Requirements are versioned. → [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md)

**Company Standard** — the organization's own standard position for a Requirement (e.g. liability = 6 months). Versioned, maintained inside LegalMind. → [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md)

**Legal Rule** — the structured, pre-approved evaluation policy that turns a comparison into an outcome (`ACCEPTABLE` / `APPROVAL_REQUIRED` / `UNACCEPTABLE`). **⚠ A Legal Rule is not a Company Standard:** the Standard says what we want, the Rule says how far we tolerate departing from it. → [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md)

**Standard Document** — the actual approved contract text. **⚠ Distinct from a Structured Legal Rule:** the document is authoritative for wording, the rule supports evaluation. → [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md)

**Legal Position** — the organization's internal tolerance and decision framework (preferred / acceptable / requires approval / unacceptable). Permission-controlled; must not leak to ordinary users or counterparties. → [WORKFLOWS.md](../01-product/WORKFLOWS.md)

**Configuration Version** — a published version of any configuration object (Requirement, Company Standard, Legal Rule, mapping rule, evaluation rule). Only active published versions affect new comparisons; drafts never do. → [COMPANY_STANDARDS.md](../02-legal-domain/COMPANY_STANDARDS.md)

**Configuration Snapshot** — the frozen set of configuration versions a specific Review ran against. Publishing new configuration never mutates an existing Review. → [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md)

**Document Type** — what kind of document this is (MSA, NDA, DPA, SLA…). **⚠ Distinct from a Legal/Regulatory Reference** (DPDP Act, GDPR…), which is a law, not a contract type. → [DOCUMENT_MODEL.md](../03-document-model/DOCUMENT_MODEL.md)

---

## Finding classifications

> **Canonical (axis 2).** The Step 36 set below is canonical per `REC-01`; Steps 18 and 27 are superseded for vocabulary. Before naming any state value, read [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) — five separate axes exist and must not share an enum.

**MATCH** — the contract provision aligns with the Company Standard.

**DEVIATION** — the provision differs from the Company Standard. **⚠ `DEVIATION` does not mean "unacceptable."** Whether a deviation is acceptable is a separate Legal Rule outcome.

**MISSING** — a required qualifying provision is absent.

**CONFLICT** — multiple provisions are established to be incompatible with each other.

**AMBIGUOUS** — the provision cannot be deterministically interpreted. Never silently resolved.

**UNRESOLVED** — a workflow state; the matter has not been settled.

**UNABLE_TO_EVALUATE** — extraction or evidence was insufficient. **⚠ Produced instead of a guess.** This is the fail-closed philosophy.

→ [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md), [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md)

**UNMATCHED_PROVISION** — a provision exists in the counterparty document with no corresponding configured Requirement. **⚠ A document-level observation, NOT a Finding Classification** — it must never occupy a Finding's `classification` field. Supersedes `ADDITIONAL` (Step 18) and `EXTRA` (Step 27) per `REC-02`. Not automatically negative.

---

## The five axes

**⚠ `AMBIGUOUS` means three different things** depending on layer: a mapping state (more than one plausible mapping), a finding classification (intended legal position undeterminable), and an extraction status (facts not reliably interpretable). Likewise `UNRESOLVED` exists on two layers. They must never share an enum.

| Axis | Question |
|------|----------|
| 1. Mapping State | Which Requirement does this clause relate to? |
| 2. Finding Classification | What is the comparison result? |
| 3. Rule Outcome | How does the organization tolerate it? |
| 4. Legal Decision | What did an authorized human rule? |
| 5. Review Lifecycle | Where is this in the workflow? |

→ [DECISION_STATE_MODEL.md](../02-legal-domain/DECISION_STATE_MODEL.md) (canonical)

---

## Legal Rule outcomes

**ACCEPTABLE** / **APPROVAL_REQUIRED** / **UNACCEPTABLE** — the outcome of applying a Legal Rule to a deviation.

**⚠ Classification and rule outcome are separate axes.** A Finding of `DEVIATION` carries a separate rule outcome; neither one is a Legal Decision. → [LEGAL_RULES.md](../02-legal-domain/LEGAL_RULES.md)

---

## Workflow terms

**Escalation** — a request that says "this requires authorized review." **⚠ Escalation is not approval.** → [WORKFLOWS.md](../01-product/WORKFLOWS.md)

**RESOLVED** — a review workflow state indicating a matter has been dealt with. **⚠ RESOLVED ≠ MATCH.** A resolved workflow state must never be recorded as a MATCH finding. This is an explicitly named locked rule. → [FINDING_CLASSIFICATION.md](../02-legal-domain/FINDING_CLASSIFICATION.md)

**Customization** — optionally producing a modified contract version *after* an authorized approval. **⚠ Approving a deviation does not automatically modify the contract, and never changes the Company Standard.** → [PRODUCT_REQUIREMENTS.md](../01-product/PRODUCT_REQUIREMENTS.md)

**Re-review** — explicitly re-running analysis. Does not create a new Document Version and does not erase the prior Review. → [DOCUMENT_VERSIONING.md](../03-document-model/DOCUMENT_VERSIONING.md)

---

## Engine terms

**Mapping** — determining *which Requirement* a clause relates to. **⚠ Mapping ≠ Evaluation:** mapping asks "what is this about," evaluation asks "what does it mean." → [REQUIREMENT_MAPPING.md](../04-analysis-engine/REQUIREMENT_MAPPING.md)

**Evaluation** — comparing extracted facts against the Company Standard and applying the Legal Rule. → [ANALYSIS_ENGINE.md](../04-analysis-engine/ANALYSIS_ENGINE.md)

**Fact Extraction** — pulling structured, requirement-specific values (cap value, unit, basis, scope, carve-outs) out of mapped evidence. → [FACT_EXTRACTION.md](../04-analysis-engine/FACT_EXTRACTION.md)

**Carve-out / Exception** — a provision excluding certain claims from a cap. **⚠ Carve-outs must never be discarded.** → [FACT_EXTRACTION.md](../04-analysis-engine/FACT_EXTRACTION.md)

**Negative pattern** — text that superficially matches a Requirement but must not be treated as satisfying it. → [FACT_EXTRACTION.md](../04-analysis-engine/FACT_EXTRACTION.md)

**Evaluator** — a specialized, per-Requirement component running on shared engine infrastructure. → [RULE_ENGINE.md](../04-analysis-engine/RULE_ENGINE.md)

**Engine version** — the version of the analysis engine, recorded per Review because engine changes can alter results. → [REPRODUCIBILITY.md](../07-audit/REPRODUCIBILITY.md)

**Golden corpus** — the curated document set with expected results that guards against regressions. Mandatory. → [GOLDEN_CORPUS.md](../08-testing/GOLDEN_CORPUS.md)

**Explainability contract** — every Finding must be reconstructable as Evidence → Fact → Standard → Rule → Result. **⚠ No generic risk score, no "AI confidence" percentage.** → [EXPLAINABILITY.md](../04-analysis-engine/EXPLAINABILITY.md)
