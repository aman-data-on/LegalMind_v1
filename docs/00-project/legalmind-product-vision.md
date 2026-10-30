# LegalMind — Product Vision (Consolidated)

## 1. What LegalMind is
A single, secure, internal-first legal workspace where **every answer is grounded in a retrievable source** — never the model's own knowledge speaking freely. Think of it as "Google search, but the index is our own legal truth": ask it anything, and it either shows you the exact source it found the answer in, or tells you plainly that it doesn't have the answer.

**Core principle (non-negotiable):** No answer without a citation. No citation, no answer — just "Information not found," with a pointer to where to look instead.

## 2. Who uses it
- **Now:** Internal Leapswitch/CloudPe legal team.
- **Later (architecture must support without rework):** Other internal departments, and external customers reviewing their own contracts.
- **Important constraint:** Regardless of who's asking, everyone validates and searches against the **same central Legal Constitution / statute corpus** — there's one shared source of truth, not per-customer isolated knowledge bases. This keeps the trust model simple: one verified corpus, many users querying it.

## 3. The three knowledge domains LegalMind draws from
This is the key structural idea — LegalMind isn't one RAG index, it's **three**, and every query is answered from exactly the right one, never blended sloppily:

| Domain | What's in it | What it answers |
|---|---|---|
| **A. Internal Legal Constitution** | Leapswitch/CloudPe's approved legal positions — clause categories (exact count and names TBD, see note below), resolved conflict register, approved clause language, confirmed positions (e.g. liability caps, SLA credit schedule, confidentiality terms) | "Does this clause in this MSA match our approved position?" |
| **B. Uploaded Document** | Whatever the user uploads in this session — an MSA, judgment, case file | "What does this specific document say about X?" |
| **C. Statute Corpus** | Pre-indexed Indian statutes (Constitution, IPC, CrPC, Evidence Act, NI Act, Contract Act, DPDP Act, IT Act) + key judgments | "What does Section 138 of the NI Act say?" — general legal research with no uploaded doc |

A single query may need one domain or a combination (e.g., validating a clause needs both A and B). The retrieval layer decides which domain(s) to search based on the query — the user never has to pick a "mode."

## 3b. Note on Domain A category count — don't hardcode, derive it
The exact number and names of clause categories (8? 10? more?) should **not be assumed or hardcoded** by whoever builds this. Instead, the build process must:
1. Ingest the actual Legal Constitution document(s) and any related source-of-truth files from Drive.
2. Programmatically/analytically extract the actual category structure used in that source material — via a one-time clause-category discovery pass (parse the document's own section headers, cross-check against the resolved conflict register's category tags).
3. Use whatever count and naming the real source material has — treat any specific number as a placeholder guess until verified against the actual document, never as a fixed spec.
4. Store the derived category list itself as versioned, structured data in the rules DB — not hardcoded in application code — so it can be corrected later without a rebuild if the Legal Constitution is revised.

This applies to every other "confirmed position" mentioned in Domain A too (liability cap, SLA credit schedule, etc.) — these should be pulled from and validated against the real document at ingestion time, not carried forward from memory or conversation history as fixed facts.

## 4. The unified workspace (how it feels to use)
One screen per document/session — not separate tabs for "validation" vs "chat." A user can, in the same conversation:
- Upload an MSA and get automatic clause-by-clause verdicts against Domain A (pass/fail/flag, cited).
- Ask a direct question about that same document ("what's the termination notice period here?") — answered from Domain B, cited to the exact page/clause.
- Ask a general legal question with no document open ("what does Section 138 NI Act say?") — answered from Domain C, cited to the statute.
- If a question spans domains — "does this termination clause comply with the Contract Act?" — the system retrieves from both B and C and answers with both citations.

Whatever the query, the answer surface is the same: **text answer + explicit source citation(s) (document/page/clause or statute/section) + confidence, or "Information not found in LegalMind's knowledge base."**

## 5. Zero-hallucination enforcement (applies uniformly across all 3 domains)
1. Retrieval always runs first — hybrid: semantic vector search (pgvector) + keyword/BM25 (exact statute sections, case numbers, party names).
2. The LLM (Gemini Flash, via the isolated `llm-gateway`) is only ever shown **retrieved chunks**, never asked to answer from its own general knowledge.
3. LLM's job is strictly: understand query intent → summarize/synthesize *only* the retrieved chunks → attach citations to every claim.
4. If retrieval returns nothing relevant → skip the LLM call entirely, return "Information not found," and (for statute queries) suggest an external source (Indian Kanoon, SCC Online, internal Legal team).
5. Guardrail layer (code, not LLM) verifies every citation actually exists in the retrieved chunk before the answer is shown — same discipline as the original clause-validation guardrails.

## 6. Feature set (all grounded in the model above)
- **Document validation**: clause-by-clause verdicts against Domain A — the original core use case.
- **Document Q&A**: chat against Domain B.
- **Legal research**: chat against Domain C (statute corpus).
- **Smart briefing**: summarize long judgments/documents (Domain B) into facts/issues/ratio — still citation-backed.
- **AI drafting**: generate notices/contracts from verified internal templates (a sub-set of Domain A) via RAG, not free generation.

## 7. Build sequencing (confirmed)
All three domains are built together in the initial phased plan — not sequenced as "core first, statute corpus later." This means Phase work now includes:
- Seeding Domain A (already largely done — Legal Constitution + conflict register).
- Building Domain B ingestion (per-session document upload/parse/chunk — already scoped).
- Seeding Domain C (indexing Indian statutes at build time, same chunking + pgvector pipeline as B) — **new work added to the build plan**.

## 8. Infra/security posture (unchanged, restated for completeness)
Fully open-source, self-hosted stack (Postgres+pgvector, MinIO, FastAPI, Next.js, Ubuntu 24.04) for everything **except** the LLM call itself, which is Gemini Flash — isolated behind a single `llm-gateway` service that is the only component in the entire stack permitted to reach the internet, with minimal-context sending, redaction, and audit logging on every call.

## 9. Decisions on previously open items (resolved — recommended defaults)

1. **Statute scope for v1**: Prioritized subset, not all acts at once — start with **Indian Contract Act 1872, Information Technology Act 2000, DPDP Act 2023, Companies Act 1956/2013** (most directly relevant to hosting/SaaS MSAs), plus **Evidence Act** and **NI Act** if time permits in the phased build. Full statute library (IPC, CrPC, Constitution, etc.) is Phase 2/future — LegalMind's early users are validating commercial contracts, not doing criminal law research, so scope follows actual usage.
2. **Source of statute text**: **India Code (indiacode.nic.in)** — the official Government of India digital repository of central acts — as the canonical source for indexing. Never scrape/index from unofficial aggregator sites; if India Code is missing a specific act, fall back to the Ministry of Law & Justice's official gazette PDF, never a third-party summary site. This is a hard rule — Domain C's trustworthiness depends entirely on this.
3. **Key judgments scope**: **Fixed curated set for v1** — Legal team supplies a specific list of judgments relevant to hosting/SaaS/contract disputes (not an open crawl of case law). Open-ended ingestion (via an admin upload flow, same pipeline as Domain B) is a documented future phase, not v1.
4. **Domain A category structure**: Resolved via the discovery-pass approach in Section 3b — no fixed number assumed. This is a Day 1, Phase 1 task, not a later cleanup.
5. **Hybrid search / BM25 engine**: **Postgres native full-text search (`tsvector`/`tsquery`)**, not a separate Elasticsearch/OpenSearch service. Keeps the stack minimal and consistent with the open-source/self-hosted/single-Postgres-instance approach already chosen for structured + vector data — one fewer service to secure, patch, and network-isolate. Only reconsider a dedicated search engine if query volume/complexity later proves Postgres FTS insufficient.
6. **Chunking strategy by domain type** (differs because structure differs):
   - **Domain A (Legal Constitution)**: chunk by clause/sub-clause boundary, using the document's own numbering — one chunk per approved position, tagged with category.
   - **Domain B (uploaded documents)**: chunk by clause/section as already planned in the ingestion pipeline, preserving page/byte offsets.
   - **Domain C (statutes)**: chunk by Section number (the statute's own atomic unit) — never split a Section across chunks, since a citation to "Section 138 NI Act" must map to exactly one retrievable chunk.
   - **Domain C (judgments)**: chunk by paragraph/para-number if the judgment uses numbered paragraphs (common in Indian judgments), else by logical section (facts / issues / holding / ratio).

