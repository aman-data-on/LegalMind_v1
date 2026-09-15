# Capability manifest — PROPOSAL for owner approval

📁 **PROPOSAL. Not in force. Nothing reads this file.**

`AM-68` r3 makes this manifest the **only** evidence a capability answer may be generated
over, and r4 restricts it to *"behaviour that is built and covered by a test"*. Rule 7's
discipline applies: **an invented capability is as bad as an invented legal rule.** So every
entry below names the endpoint that implements it and a test that covers it, and I have
checked each against the code rather than describing the product from memory.

**Deliberately absent:** anything planned, partial, roadmap or speculative. Template drafting
is **not** listed — it does not exist (`DOCUMENT_BUILDER_RND.md` is a proposal, and its
blocker is that no approved output template exists). Multi-document comparison is **not**
listed — one contract per conversation, permanently. Neither is "coming soon"; they are
simply not capabilities.

On approval this becomes `backend/config/capability_manifest.json`, and changing it
afterwards is a configuration change needing owner approval (r4).

---

## Proposed entries

| # | Capability, in the words a user would recognise | Implemented by | Covered by |
|---|---|---|---|
| c1 | Upload a contract as PDF or DOCX; its text and clause numbering are extracted, and existing clause numbers are preserved, never invented | `POST /contracts/{id}/document-versions` | `test_contracts_upload.py`, `test_ingestion_*.py` |
| c2 | Compare an uploaded document against the organisation's ratified Company Standards, producing Findings | `POST /reviews/{id}/analyze` | `test_analysis_*.py`, `test_evaluation_*.py` |
| c3 | Each Finding is classified MATCH, DEVIATION, MISSING, CONFLICT or UNABLE_TO_EVALUATE, and every one reconstructs as Evidence → Fact → Standard → Rule → Result | evaluation engine | `test_findings_*.py`, golden corpus |
| c4 | Read a Finding in three plain words — Accepted, Needs review, Not accepted — derived from the classification, never from a score | `GET /reviews/{id}/findings` | `test_reader_status*.py` |
| c5 | Ask a question about an uploaded document and get an answer whose every sentence points at the passage it came from | `POST /conversations/{id}/messages` | `test_assist_ask.py` |
| c6 | See the organisation's approved position quoted **verbatim** from the ratified standard, with its standard code, version and source clause | Domain A retrieval | `test_positions.py`, `test_assist_positions_sanitization.py` |
| c7 | Ask about the approved statute corpus and get an answer cited by Act and section | Domain C retrieval | `test_assist_statutes.py` |
| c8 | Ask a follow-up in ordinary language — "what does that mean?", "isko samjhao" — and have it understood as referring to the previous question | conversation memory | `test_assist_conversation_memory.py`, `test_assist_language_safety.py` |
| c9 | Be told plainly when the available material does not answer a question, rather than being given a guess | refusal path | `test_assist_ask.py`, `test_assist_source_matrix.py` |
| c10 | Record a Legal Decision on an Evaluation, by a person authorised to make one | `POST /evaluations/{id}/decisions` | `test_decisions_*.py`, `test_workflow_decisions.py` |
| c11 | Escalate a Finding for a human ruling, and withdraw that escalation | `POST`/`DELETE /findings/{id}/escalate` | `test_escalation*.py` |
| c12 | Compare two versions of the same contract, clause by clause, deterministically | `GET /contracts/{id}/version-comparison` | `test_version_comparison.py` |
| c13 | Export a Review as a PDF or DOCX report | `GET /reviews/{id}/report` | `test_api_export.py` |
| c14 | Extract a document's key obligations as a descriptive list — never as Findings | `POST /document-versions/{id}/extract-obligations` | `test_assist_obligations.py` |
| c15 | Archive, restore, transfer or delete a contract, with every such act audited | `POST /contracts/{id}/archive` · `/restore` · `/transfer`, `DELETE /contracts/{id}` | `test_contracts_lifecycle.py`, `test_rbac_*.py` |
| c16 | Publish a configuration snapshot so past Reviews stay reproducible against the configuration they were run under | `POST /configuration/publish` | `test_configuration_*.py` |

## What the manifest must also say — the honest limits

`AM-68` r5 lets the model phrase the manifest, nothing more. These entries exist so that a
capability answer describes the product **accurately**, including where it stops:

| # | Limit |
|---|---|
| L1 | LegalMind does **not** decide whether a document is acceptable, approve it, or advise whether to sign. It shows Findings and the approved position; a person decides. |
| L2 | It does **not** draft or generate agreements. |
| L3 | It answers about **one** document per conversation; it cannot compare two uploaded documents with each other. |
| L4 | It states no legal position that is not already in a ratified Company Standard, a published Legal Rule or an approved template. |
| L5 | Where no approved source answers, it says so rather than guessing. |

---

## Open question for the owner

`AM-68` r5 permits "constrained wording over the manifest". The entries above are written in
user-facing language already, so a reasonable alternative is to **skip generation entirely**
for capability questions and render the manifest deterministically — simpler, and immune to
the model embroidering a capability.

My recommendation is to **generate**, because a manifest read aloud verbatim answers "what
can you help me with?" poorly — the user asked a question, not for a feature list — and r6's
deterministic fallback already covers the failure case. But it is a product judgement and the
cheaper option is genuinely defensible.
