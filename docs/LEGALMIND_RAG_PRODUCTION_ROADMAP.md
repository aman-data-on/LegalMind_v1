# LegalMind — Production RAG Roadmap

**Version:** 1.0  
**Date:** 2026-09-24  
**Goal:** Build LegalMind's retrieval-augmented generation (RAG) pipeline so complex, conversational legal/company questions are answered naturally, completely, accurately, and with traceable evidence.

---

## 0. Target outcome

LegalMind must behave like a strong conversational research agent, not like a search box that returns raw chunks.

Target flow:

```text
USER QUESTION
    ↓
Conversation/context understanding
    ↓
Question understanding + task decomposition
    ↓
Authority/source selection
    ↓
Query formulation / rewriting
    ↓
Broad authorized retrieval
    ├─ lexical / BM25
    ├─ dense / semantic
    └─ metadata / exact-reference retrieval
    ↓
Fusion + deduplication
    ↓
Cross-encoder reranking
    ↓
Context expansion / parent-child reconstruction
    ↓
Evidence sufficiency + authority + version + conflict checks
    ↓
Gemini grounded answer generation
    ↓
Claim-level verification
    ↓
Citation validation
    ↓
Natural final answer
```

### Golden acceptance question

LegalMind must correctly handle a question like:

> A client says their signed MSA mentions 6 months of compensation for early termination, but we cannot find the final signed copy. What does our Legal Constitution say about early termination compensation? Does it specify 6 months, 12 months, or the full remaining contract value? What should we do in this situation, and can we confirm the compensation amount without checking the signed MSA?

The answer must distinguish:

- the **Company Constitution position**;
- the **user/client assertion** about 6 months;
- the **actual signed MSA**, which is unavailable;
- any **historical negotiated exception** that is not current policy;
- the **current legal source**, where legal enforceability is asked;
- and the **operational next step**.

It must not invent a contract term or confirm an amount that requires the missing signed MSA.

---

# 1. Knowledge representation — fix the source model first

## Required design

The original Legal Constitution remains the canonical source document. Do **not** replace it with a collection of independent standards.

Create a structured representation alongside the original source:

```text
Canonical source document
    ↓
Sections
    ↓
Subsections / rules / provisions
    ↓
Structured legal/company facts
    ↓
Retrieval records
```

A "standard" may be a structured representation of a rule, but it must retain a pointer back to its Constitution section and surrounding context.

For every knowledge item retain at minimum:

```text
source_id
source_type
source_title
section_path
subsection / clause
content
parent_id
version
status
jurisdiction
effective_from
effective_to
authority_level
supersedes / superseded_by
cross_references
```

## Source authority model

LegalMind must know the difference between:

1. Current ratified Company Constitution
2. Current executed/signed customer document
3. Draft or unsigned document
4. Historical negotiated exception
5. Current primary law / regulation
6. Secondary commentary / reference

Authority is **question dependent**, not globally fixed.

Examples:

```text
"What does our Constitution say?"
→ Constitution is primary.

"What does the signed MSA say?"
→ Executed MSA is primary.

"Can we confirm the amount without the signed MSA?"
→ Answer must recognize that the controlling contractual amount is unavailable.

"What does Indian law say?"
→ Current authoritative legal source is primary.
```

### Exit criteria

- Original Constitution preserved.
- Structured rules mapped back to source sections.
- Historical exceptions separated from current policy.
- Authority/version/status metadata available to retrieval.

---

# 2. Ingestion and parsing — make the corpus trustworthy

## Required design

Every source must pass a deterministic ingestion pipeline before entering production retrieval:

```text
Original file
→ file validation
→ text/layout extraction
→ structural parsing
→ section/clause detection
→ table/list handling
→ metadata extraction
→ source fingerprint
→ integrity checks
→ indexing
```

### Contracts

Preserve:

- headings
- clause numbers
- subclauses
- tables
- footnotes where legally meaningful
- page numbers
- document version
- signature/execution status when known
- cross-references

### Statutes

Preserve:

- Act title
- section number
- subsection number
- chapter/part
- amendment/version information
- commencement/effective dates
- repeal status
- jurisdiction
- source publication metadata

A parsed statute section must never acquire a fabricated section number.

### Integrity tests

Each production ingest must test:

- expected document count
- expected section count where known
- missing section numbers
- duplicate sections
- impossible numbering jumps
- oversized malformed sections
- content loss
- repeated text explosions
- fabricated labels
- bad page joins
- repeal/supersession status

### Exit criteria

No document becomes searchable until ingestion integrity checks pass.

---

# 3. Chunking — use legal/semantic hierarchy, not one fixed chunk rule

Chunking must serve **retrieval precision** and **answer context** separately.

Use hierarchical representation:

```text
DOCUMENT
  ↓
SECTION / CLAUSE (parent)
  ↓
SUBCLAUSE / PARAGRAPH / PROPOSITION (child)
```

### Retrieval unit

Small, semantically coherent child units should be searchable.

### Generation context

When a child is retrieved, reconstruct its parent/nearby legal context before giving evidence to Gemini.

This avoids the common trade-off:

```text
small chunk → precise retrieval, weak context
large chunk → rich context, diluted retrieval signal
```

Parent-child retrieval is widely used for this reason, including for complex legal documents. citeturn580357search1turn580357search7turn580357academia60

### Contextualized chunk text

Each retrievable child should carry a breadcrumb such as:

```text
Document: Legal Constitution
Section: §14 Fixed-term
Subsection: Amount payable
Topic: Early termination
```

This improves retrieval without changing the source text.

### Important

Do **not** blindly choose token/character sizes.

Tune parent/child sizes using the legal benchmark and inspect:

- boundary failures
- cross-reference failures
- exception loss
- condition loss
- citation precision

### Exit criteria

- Rules, exceptions, and conditions remain connected.
- Child retrieval identifies precise evidence.
- Parent/context expansion restores enough surrounding meaning for generation.
- Duplicate child hits from one parent do not crowd out other sources.

---

# 4. Embeddings — benchmark, then select

`all-MiniLM-L6-v2` is a valid lightweight baseline, but it should not be treated as the final choice merely because it is already deployed.

Benchmark at minimum:

```text
A. all-MiniLM-L6-v2          baseline
B. BAAI/bge-m3               primary candidate
C. Qwen3-Embedding-0.6B     secondary candidate
```

BGE-M3 supports multilingual retrieval, long inputs up to 8192 tokens, and dense/sparse/multi-vector retrieval modes; its authors explicitly recommend hybrid retrieval plus reranking. citeturn742415search0turn198082search8

Qwen3-Embedding-0.6B supports 100+ languages, 32K context, instruction-aware embeddings, and up to 1024 dimensions. citeturn742415search5turn742415search8

### Benchmark dimensions

Measure on the **actual LegalMind corpus and benchmark**, not generic leaderboard claims:

- Recall@3
- Recall@10
- Hit@1
- MRR
- nDCG@5
- source-domain accuracy
- Constitution topic retrieval
- contract clause retrieval
- statute section retrieval
- paraphrase retrieval
- Hinglish/Roman-Hindi retrieval
- latency
- RAM/CPU
- indexing time
- reindex cost

### Selection rule

Use the best model that materially improves retrieval quality without creating unacceptable production latency/cost.

Do not change the model unless the benchmark demonstrates that the change improves the target workload.

---

# 5. Vector storage and indexing — keep Postgres unless evidence requires migration

A separate vector database is **not automatically an industry requirement**.

Postgres + pgvector is fully capable of vector search and hybrid retrieval using PostgreSQL full-text search, and supports HNSW indexing and reranking patterns. citeturn376130search4

### Default architecture

```text
Postgres
├─ source metadata
├─ chunk hierarchy
├─ lexical index / FTS
├─ dense embeddings
├─ retrieval metadata
└─ evidence/provenance
```

### Migrate to a dedicated vector store only if measurements show a real need:

- unacceptable latency at target scale
- operational pressure from indexing/query volume
- memory/storage constraints
- retrieval features not practical in Postgres

Do not migrate simply because another vector database is marketed as better for RAG.

---

# 6. Query understanding — move beyond regex-only routing

Query understanding must separate **understanding** from **authority**.

Recommended flow:

```text
User question
   ↓
Deterministic extraction
   ├─ explicit document names
   ├─ section references
   ├─ dates/numbers
   ├─ jurisdiction
   └─ obvious entities
   ↓
Semantic query understanding
   ↓
Structured Query Plan
```

The plan should capture:

```text
intent
question type
subject/topic
operation
entities
numbers/dates
jurisdiction
requested authority
conversation references
follow-up links
language
answerability requirements
sub-questions
```

### Conversational behavior

Equivalent wording must converge:

```text
"terminate early"
"end the MSA early"
"exit before the term ends"
"customer wants to leave early"
"agreement ko jaldi end karna hai"
```

### Query decomposition

For complex questions, create focused subqueries instead of forcing one embedding query to answer everything.

For the golden question, possible subqueries are:

```text
1. Constitution: early termination company position
2. Constitution: fixed 6-month compensation?
3. Constitution: fixed 12-month compensation?
4. Constitution: full remaining term?
5. Available executed MSA: term and fee language
6. Historical negotiated exceptions
7. Current Indian-law enforceability source
8. Missing-document operational action
```

LLM query rewriting/planning is an established pattern for conversational RAG, and 2026 multi-turn RAG evaluations continue to use query rewriting + hybrid retrieval + cross-encoder reranking. citeturn198082search0turn477585search0turn477585search3

### Cost rule

Use a small/fast model only when query complexity requires it. Simple queries should remain cheap and deterministic where possible.

---

# 7. Retrieval — optimize recall before precision

The current "top 3" dependency must be removed.

Industry-standard retrieval is generally multi-stage:

```text
Query
 ↓
Dense retrieval        ┐
Sparse/BM25 retrieval  ├→ candidate pool
Metadata retrieval     ┘
 ↓
Fusion
 ↓
Deduplicate
 ↓
Cross-encoder rerank
 ↓
Applicability/authority filter
 ↓
Evidence set
```

Hybrid dense+sparse retrieval combines semantic matches with exact lexical matches, while reranking applies a deeper relevance model to a smaller candidate set. citeturn376130search0turn376130search1turn198082search3

### Candidate pool

Start with sufficiently broad candidate retrieval, then tune from evaluation results. Example starting point:

```text
Dense:   top 30–50
BM25:    top 30–50
Metadata/exact: top 10 where relevant
Fuse:    ~50–100 unique candidates
Rerank:  top ~30–50
Evidence: ~5–12 final units, depending on question complexity
```

These are starting parameters, **not permanent rules**.

### Required retrieval features

- title/topic fields
- section heading fields
- exact clause/section reference matching
- document type
- source type
- jurisdiction
- version/status
- date/effective period
- authority level
- child-to-parent relationship
- source-specific filters

### Diversity

Avoid allowing five similar Company Standards to displace a required statute or executed agreement.

Use query/subquery-aware evidence diversity.

### Exit criteria

A correct gold source should be present in the candidate pool for nearly every answerable benchmark query, even when wording changes substantially.

---

# 8. Reranking and context assembly — relevance first, completeness second

Use a cross-encoder or equivalent late-stage semantic ranker on the candidate pool.

The reranker should answer:

> "Given this exact user/subquery, how relevant is this candidate?"

not merely:

> "Are these documents about the same topic?"

After reranking:

1. Deduplicate overlapping children.
2. Group by parent/source.
3. Restore required surrounding context.
4. Preserve provenance for each evidence span.
5. Keep enough evidence to answer all material subquestions.

Cross-encoder reranking after broad hybrid retrieval is a standard two-stage retrieval pattern. citeturn198082search2turn376130search0

---

# 9. Evidence layer — build an evidence bundle, not just a list of chunks

Before Gemini sees retrieval output, create a structured evidence bundle.

Example:

```text
EvidenceBundle
├─ Source A
│  ├─ authority
│  ├─ version
│  ├─ citation
│  ├─ exact text
│  └─ relevance
├─ Source B
├─ Source C
└─ unresolved questions
```

### Evidence states

```text
SUPPORTED
PARTIALLY_SUPPORTED
CONFLICTING
INSUFFICIENT
UNAVAILABLE
```

This lets the generator answer different parts correctly instead of forcing one global yes/no.

### Mandatory distinctions

The evidence layer must distinguish:

```text
Company position
Contractual term
User assertion
Historical exception
Law
Unknown / missing document
```

For the golden question, the evidence bundle should be able to represent:

```text
Constitution → full remaining committed-term value
User assertion → 6 months
Signed MSA → missing
Historical negotiated exceptions → separate/non-policy
Law → separate legal-enforceability layer
```

---

# 10. Gemini generation — conversational answer generation

Gemini is the **language/reasoning-over-evidence layer**, not the authority layer.

Input:

```text
User question
+
Conversation context
+
Structured evidence bundle
+
Answer requirements
```

Gemini should:

- answer the actual question;
- combine multiple evidence items;
- explain differences;
- use user-provided facts as context;
- paraphrase naturally;
- answer follow-up questions;
- clearly separate known facts from missing information;
- preserve conditions, exceptions, dates and quantities;
- state when the available evidence cannot confirm something.

It must **not**:

- invent company policy;
- invent contract terms;
- invent legal rules;
- treat a user assertion as verified evidence;
- turn a historical exception into current policy;
- silently fill a missing signed agreement.

### Answer style

Do not force every answer into three sentences.

For simple questions:

```text
Direct answer → short explanation → citation
```

For complex questions:

```text
Direct answer
→ Important distinction
→ What is known
→ What is missing
→ What to do
→ citations
```

Do not expose retrieval mechanics unless the user asks.

---

# 11. Verification — semantic grounding, not word overlap

The verifier must inspect **claims**, not simply compare words.

Required pipeline:

```text
Generated answer
 ↓
Claim extraction
 ↓
For each claim:
  evidence entailment
  contradiction check
  number/date provenance
  condition/exception preservation
  polarity check
  scope check
  citation check
 ↓
Answer decision
```

### Critical distinction

The verifier must understand three categories:

```text
USER CONTEXT
EVIDENCE
MODEL CLAIM
```

A user-provided number can appear in the answer as user context without being treated as company evidence.

A model-invented number without support must fail.

A grounded paraphrase must pass even when it does not repeat source wording.

### Verification design

Use a combination of:

- deterministic provenance checks;
- semantic entailment / claim verification;
- contradiction detection;
- numeric and temporal checks;
- authority/version checks;
- citation validation.

Do not remove verification merely because it rejects bad answers. **Fix the verifier so that it rejects bad claims while allowing correct paraphrases.**

Fine-grained evaluation frameworks such as RAGChecker explicitly separate retrieval and generation diagnostics and are useful models for this kind of component-level evaluation. citeturn477585academia12

---

# 12. Citation system

Every material factual claim must have traceable evidence.

Citation should identify:

```text
source
version
section/clause
page or locator when available
exact supporting span
```

Citation precision and citation completeness should be measured separately.

Do not cite a whole document when a specific clause can be identified.

---

# 13. Multi-source legal reasoning

The golden question demonstrates why LegalMind needs **multi-source reasoning**, not a single-document similarity lookup.

The final answer may require:

```text
Constitution
    +
executed MSA availability state
    +
historical exception evidence
    +
current statute/law
    +
conversation context
```

However, those sources must **not be blended into one undifferentiated truth**.

The answer must label the distinction naturally:

```text
"Our Constitution says..."
"The customer is claiming..."
"The signed MSA is not currently available..."
"Historical agreements are exceptions, not current policy..."
"The amount cannot be confirmed until the executed MSA is verified..."
```

This is a core LegalMind capability.

---

# 14. Authority, jurisdiction and temporal controls

Legal answers are not just semantic search.

Every legal source needs:

```text
jurisdiction
source_type
authority
publication_date
effective_from
effective_to
status
version
supersedes
superseded_by
```

Retrieval must respect:

```text
CURRENT ≠ AUTOMATICALLY APPLICABLE
LATEST ≠ ALWAYS LEGALLY EFFECTIVE

historical question → historical source
current-law question → current effective source
```

For Indian-law retrieval, prefer authoritative primary sources such as India Code and notified government material where applicable. India Code provides the Indian Contract Act, 1872 and explicitly lists Sections 73–75; MeitY publishes the notified Digital Personal Data Protection Rules, 2025. citeturn418915search2turn418915search1

---

# 15. Conversation intelligence

Conversation context must be first-class retrieval input.

Example:

```text
Turn 1:
"What does our Constitution say about early termination?"

Turn 2:
"What if the customer says they were promised 6 months?"
```

Turn 2 should inherit the topic from Turn 1 but must not assume that the 6-month statement is verified.

Store/use:

- active document
- active clause/topic
- entities
- user claims
- prior verified evidence
- unresolved questions
- current jurisdiction
- current source scope

Avoid injecting entire conversation history into every retrieval query.

---

# 16. Evaluation system — the control center

Do not judge the RAG only from the final answer.

Evaluate every layer independently:

### Retrieval metrics

- Recall@3
- Recall@10
- Hit@1
- MRR
- nDCG@5
- source selection accuracy
- authority accuracy
- version accuracy

### Generation metrics

- answer relevance
- completeness
- faithfulness
- citation precision
- citation completeness
- unsupported-claim rate
- contradiction rate

### Conversation metrics

- follow-up resolution
- context carryover accuracy
- wrong-context rate

### Safety metrics

- unauthorized retrieval = 0
- cross-tenant leakage = 0
- wrong jurisdiction = 0
- wrong active version = 0
- current policy confused with historical exception = 0
- user assertion incorrectly treated as evidence = 0

RAG evaluation literature supports measuring retrieval and generation separately because end-to-end scores can hide which module is actually failing. citeturn477585academia12turn477585academia13

---

# 17. Golden test suite

Build a permanent legal benchmark with categories:

```text
A. Exact wording
B. Legal paraphrase
C. Synonym / terminology variation
D. Multi-hop
E. Multi-source
F. Numeric questions
G. Exception / qualification questions
H. Historical questions
I. Missing-document questions
J. Follow-ups
K. Hinglish / Roman-Hindi
L. Wrong-source traps
M. Insufficient-evidence questions
N. Prompt-injection attempts
O. Current-vs-historical law questions
```

The golden early-termination test must have variants such as:

- 6 months compensation
- 6 months lock-in
- 12 months compensation
- remainder of term
- early exit
- terminate early
- cancel early
- customer says we promised 6 months
- signed MSA unavailable
- historical MSA says 30 days/no penalty
- ask for amount without signed MSA

---

# 18. Deployment discipline

Every change follows:

```text
Baseline
 ↓
Targeted benchmark
 ↓
Implementation
 ↓
Regression tests
 ↓
Full suite
 ↓
Canary / feature flag
 ↓
Production smoke
 ↓
Compare metrics
 ↓
Keep / rollback
```

Keep model, prompt, embedding, parser and retrieval configuration versioned.

Log enough to reproduce a bad answer:

```text
request_id
query
conversation_id
route
query_plan
retrievers used
candidate IDs
reranker output
evidence IDs
model versions
prompt version
verifier result
citations
latency
cost
```

Do not log unnecessary sensitive document content.

---

# 19. Recommended implementation order

Do this in dependency order:

```text
PHASE 0 — Golden benchmark + failure taxonomy

PHASE 1 — Canonical knowledge/source model

PHASE 2 — Ingestion + parser integrity

PHASE 3 — Hierarchical semantic chunking

PHASE 4 — Embedding benchmark + selection

PHASE 5 — Index/storage optimization

PHASE 6 — Query understanding + conversational rewriting

PHASE 7 — Broad hybrid retrieval + metadata retrieval

PHASE 8 — Reranking + parent/context reconstruction

PHASE 9 — Evidence bundle + authority/version/temporal controls

PHASE 10 — Gemini conversational generation

PHASE 11 — Semantic claim verification + citation verification

PHASE 12 — End-to-end multi-source legal evaluation

PHASE 13 — Production rollout + observability + rollback
```

### Dependency rule

Do not optimize a downstream stage before upstream quality is known.

```text
Bad corpus
→ bad chunks
→ bad retrieval
→ bad evidence
→ bad generation
```

```text
Good retrieval
→ good evidence
→ good generation
→ meaningful verification
```

---

# 20. Definition of DONE

LegalMind is not considered production-ready merely because:

- embeddings exist;
- pgvector works;
- Gemini produces text;
- the RAG pipeline returns something;
- or a few demo questions look good.

It is DONE when the complete benchmark demonstrates that LegalMind can reliably:

1. understand natural and conversational questions;
2. retrieve the correct source despite wording variation;
3. preserve legal structure, conditions and exceptions;
4. distinguish company policy, contract terms, law, user claims and historical exceptions;
5. retrieve multiple authoritative sources when the question requires them;
6. generate a natural answer instead of a source dump;
7. avoid inventing missing facts or numbers;
8. refuse only what the evidence genuinely cannot establish;
9. produce precise citations;
10. preserve authorization, jurisdiction and version boundaries;
11. answer the golden early-termination question correctly and completely;
12. remain stable across English, conversational phrasing and reasonable Hinglish/Roman-Hindi.

---

# 21. Golden answer behavior — reference shape

For the user's early-termination example, the system should be capable of producing an answer with this structure when the evidence supports it:

> **The Legal Constitution does not set a fixed 6-month or 12-month compensation figure. Its current position is that the full remaining committed-term value is payable for early exit from a confirmed fixed-term commitment.**
>
> The **6 months mentioned by the client must not automatically be treated as the compensation amount**. If an MSA contains a 6-month minimum service/lock-in period, that is the contractual term that must be verified in the executed agreement; it is not the same thing as a Constitution-mandated 6-month compensation figure.
>
> Because the **final signed MSA is missing**, LegalMind should not confirm the actual compensation amount yet. The executed MSA determines the committed term, fee structure and any negotiated exception that controls the contract.
>
> Historical agreements that contain different exit terms should be treated as historical negotiated exceptions, not as the current Company Constitution position.
>
> The next step is to locate/verify the executed MSA before confirming the contractual amount. Any separate question about legal enforceability should be answered from the applicable current legal sources, not inferred from the Company Constitution alone.

The exact wording above is illustrative. The production answer must be generated from the actual retrieved evidence available at runtime.

---

# 22. What must NOT happen

```text
User asks a complex question
→ retrieve 3 chunks
→ pick first chunk
→ copy/paste chunk
→ lexical overlap verifier rejects paraphrase
→ raw clause fallback
```

or:

```text
User says "6 months"
→ model assumes 6 months is company policy
→ invents missing contract details
→ gives a confident amount
```

or:

```text
Current statute
+ historical statute
+ company policy
+ signed contract
→ blended into one answer without source distinction
```

These are production failures.

---

# 23. Research basis

This roadmap is based on current RAG engineering guidance and 2026 retrieval work emphasizing:

- content preparation and chunking;
- hybrid dense+sparse retrieval;
- multi-stage ranking;
- query understanding/rewrite for conversational questions;
- parent/child context reconstruction;
- separate retrieval and generation evaluation;
- source/permission-aware knowledge access.

Key references:

1. Microsoft Azure AI Search — Retrieval-augmented generation overview and agentic/classic retrieval.  
   https://learn.microsoft.com/en-us/azure/search/retrieval-augmented-generation-overview

2. Microsoft Azure AI Search — RAG information retrieval architecture.  
   https://learn.microsoft.com/azure/architecture/ai-ml/guide/rag/rag-information-retrieval

3. Qdrant — Hybrid search with reranking.  
   https://qdrant.tech/documentation/tutorials-basics/reranking-hybrid-search/

4. Qdrant — Hybrid and multi-stage queries / RRF.  
   https://qdrant.tech/documentation/search/hybrid-queries/

5. pgvector — PostgreSQL vector similarity search, HNSW and hybrid search patterns.  
   https://github.com/pgvector/pgvector

6. BAAI BGE-M3 — multilingual, multi-granularity, hybrid retrieval guidance.  
   https://huggingface.co/BAAI/bge-m3

7. Qwen3-Embedding — multilingual embedding family and 0.6B model.  
   https://huggingface.co/Qwen/Qwen3-Embedding-0.6B

8. ACL 2026 — Multi-turn RAG using query rewriting, hybrid retrieval and cross-encoder reranking.  
   https://aclanthology.org/2026.semeval-1.32/

9. ACL 2026 — Three-stage multi-turn retrieval with query rewriting, hybrid search and reranking.  
   https://aclanthology.org/2026.semeval-1.225/

10. RAGChecker — fine-grained retrieval and generation evaluation.  
    https://arxiv.org/abs/2408.08067

11. ARES — automated RAG evaluation across context relevance, faithfulness and answer relevance.  
    https://arxiv.org/abs/2311.09476

12. India Code — Indian Contract Act, 1872.  
    https://www.indiacode.nic.in/handle/123456789/12845

13. MeitY — Digital Personal Data Protection Rules, 2025.  
    https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa

---

# 24. LegalMind source constraints incorporated

This roadmap preserves the important product/source principles already present in the LegalMind materials:

- answers must remain grounded in retrievable sources;
- LegalMind uses distinct knowledge domains rather than blindly blending all sources;
- contract comparison remains clause/requirement-level;
- Legal Findings remain distinct from authorized Legal Decisions;
- the original Constitution remains the source document while structured rules support the engine.

The implementation may change the technical mechanism when measured evidence shows a better approach, but it must preserve source authority, auditability, authorization and traceability.
