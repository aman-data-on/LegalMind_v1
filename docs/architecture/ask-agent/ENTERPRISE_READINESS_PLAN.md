# LegalMind Ask — Enterprise-Readiness Research and Revised Plan

> 📁 **PLAN — APPROVED by the owner 2026-10-22, with the rulings in §10A.** A plan, not a specification: it locks nothing. Each lock it names is amended by its own appended record when that phase lands. Build state lives only in [IMPLEMENTATION_STATUS.md](../../00-project/IMPLEMENTATION_STATUS.md).

---

## 0. Context and what was inspected

**Trigger.** On 2026-10-22 a sales user pasted a client's 16-point email about a CloudPe cloud proposal and asked Ask to "reframe the answer as per the cloudpe product". Ask answered with a canned product brief twice. That defect is fixed on branch `fix/ask-capability-followup-20261022` (`AM-200`, uncommitted, 2190 tests passing with models). The owner asked for this pass to:
- check the whole Ask lane against current, evidence-backed enterprise practice;
- challenge the earlier plan;
- produce a revised plan with release gates.

**Inspected (read-only):**

| What | How |
|---|---|
| Repository | Worktree `/root/legalmind-worktrees/ask-capability-followup`, `CLAUDE.md` and the git state. Eleven worktrees are active; the IDs AB-102/103 and AM-173–179 are taken on unmerged branches. |
| Agent path, end to end | `service.ask` → `_agent_answer` → `agent.run_turn` → tools → `agent_verify` → persistence. Each finding below carries file:line evidence. |
| Production data, SELECT only | All 36 user turns in 11 conversations, the stored replies, and the `assist.agent.turn` journal lines. |
| Live replay | One replay of the reported turn on the new code, inside a transaction that refused commit and was rolled back: 4 Gemini calls, 31 s, message count 6 before and after. |
| Earlier plan | §8 of the previous draft of this file. |

**Sources verified.** 35 sources in total; §2 lists them, all accessed 2026-10-22. Each is graded as one of:
- **Mandatory:** DPDP Act and Rules 2025; CERT-In Directions 2022.
- **Authoritative:** NIST, CISA/NSA/partners, UK NCSC.
- **Community:** OWASP.
- **Vendor:** OpenAI, Anthropic, Microsoft, AWS, Google.
- **Academic.**

Claims that could not be verified are listed in §2.3.

---

## 1. Executive assessment

**Strong (verified in code and tests).**
- Authorization is checked server-side inside every tool:
  - `ToolContext.open` checks conversation ownership and `can_read_contract` (`tools.py:223-241`);
  - `find_documents` checks every candidate is readable;
  - each tool runs in a savepoint that is always rolled back (`tools.py:1167-1186`).
- Cross-user isolation tests exist for conversations, attachments, the cache and evidence.
- Untrusted text is wrapped as data (`generation.untrusted`, `generation.py:71-97`), and there is a prompt-injection test suite (`test_assist_prompt_injection.py`).
- Claims are verified after generation: about 30 V/P checks, local NLI, one repair, then `settle` drops what still fails.
- Turn budgets exist: `MAX_CALLS=8`, `HARD_S=40`. Retry once on 429/500/503.
- Prompt versions are recorded in the audit.
- `all_lock.md` is append-only and enforced by CI.
- CI has 17 jobs, including the authorization matrix and pip/npm/Trivy audits.

**Weak (evidence in §3).**
- Ask never states which brand it is answering for, and earlier-turn evidence is never re-scoped to that brand.
- Superseded evidence can be cited as "current".
- Drafts are not checked against their sources.
- Client numbering, sub-points and missing information have no structural contract; nothing guarantees every point and sub-point is answered or assigned an owner.
- The release gate (`verify_assist_quality`) does not exercise the live agent path, and its baseline is from 2026-09-17, before agent mode.
- No monitoring or alerting, and no per-user spend cap.

**Outdated.**
- The OWASP references in project docs use the 2025 LLM Top 10 numbering. genai.owasp.org lists a 2026 edition dated 3 Aug 2026, but its item list is unverified.
- The AI risk register (`ASK_AI_PROGRAMME.md §C`) is a September snapshot.
- The `agent/tools.py` docstring says the tools are "not wired into Ask", which is no longer true.

**Unverified.**
- How well follow-ups are understood. Explicit follow-up resolution was removed; the model now writes its own queries, and nothing measures how well that works.
- The real wall-clock time of a turn. `FINAL_MIN_S`, an NLI deadline of up to 120 s and post-answer steps can each exceed `HARD_S`.
- How often Gemini chooses `show_capabilities`.

---

## 2. Research register

Full table: 35 entries with title, URL, page date, recommendation, grade, whether superseded, and how it applies. Abridged below. All were accessed 2026-10-22.

### 2.1 Register (abridged)

| # | Source (date) | Grade | Recommendation used | Applies to |
|---|---|---|---|---|
| R1 | NIST AI RMF 1.0, AI 100-1 (26 Jan 2023; page says "being revised") | Authoritative | Govern / Map / Measure / Manage functions | Ownership, metrics, incident process (§9) |
| R2 | NIST AI 600-1 GenAI Profile (26 Jul 2024) | Authoritative | Confabulation, information integrity, privacy and value-chain risks | Risk register (§4) |
| R3 | NIST COSAiS, renamed "COSIS" on 20 Oct 2026 (unusual; re-check before citing) | Authoritative, draft only | SP 800-53 overlay for a generative assistant and a single agent | Watch item |
| R4 | NIST CAISI AI Agent Standards Initiative (17 Feb 2026) | Authoritative, early stage | Agent identity and authorization | Agent acts only with the user's server-side identity |
| R5 | OWASP Top 10 for LLM Applications 2025; a 2026 page is dated 3 Aug 2026, item list unverified | Community | Prompt injection, sensitive information disclosure, excessive agency, unbounded consumption, vector and embedding weaknesses, misinformation, output handling | Security plan (§9) |
| R6 | OWASP Top 10 for Agentic Applications 2026 (9 Dec 2025) | Community | Goal hijack, tool misuse, privilege abuse, cascading failures | Threat model of the tool loop |
| R7 | NSA AISC/CISA *Deploying AI Systems Securely* (15 Apr 2024) | Authoritative | Secure environment, monitoring, logging, incident response | Observability (§9) |
| R8 | CISA/NSA/FBI *AI Data Security* (22 May 2025) | Authoritative | Data integrity across the lifecycle | Corpus integrity gates (these exist already: `AM-80`) |
| R9 | CISA/ACSC/NSA et al. *Careful Adoption of Agentic AI Services* (1 May 2026) | Authoritative | Low-risk tasks first, least privilege, monitoring, human oversight | Read-only tools, handoff lines |
| R10 | UK NCSC *Guidelines for secure AI system development* (27 Nov 2023) | Authoritative | Secure design, development, deployment and operation | Delivery (§9) |
| R11 | OpenAI *Evaluation best practices* (date not stated) | Vendor | Build evals from real logs; evaluate early and often; calibrate judges with human labels; prefer pass/fail or pairwise grading | Evaluation strategy (§7) |
| R13 | OpenAI Agents SDK guardrails and tracing | Vendor | Spans for generation, tools and guardrails; sensitive data excluded by default | Trace design (§9) |
| R14 | Anthropic *Reduce hallucinations* | Vendor | Allow "I don't know"; a quote per claim; retract unsupported claims | Already built (V-checks); extend to drafts |
| R15 | Anthropic *Building effective agents* (19 Dec 2024) | Vendor | Simplest workable design, small tool set, iteration caps | Architecture (§5) |
| R17 | Microsoft *Security filter pattern* (21 Aug 2026) | Vendor | Filter in the query, not in the prompt | Brand filter applied in code at retrieval **and** at ledger adoption |
| R18 | Microsoft *Agentic retrieval* (16 Sep 2026; query planning in preview) | Vendor | Split into subqueries; read the whole conversation | Per-point slots |
| R19 | Microsoft Foundry RAG evaluators (2 Jun 2026) | Vendor | Groundedness (precision) and completeness (recall) scored separately; retrieval scored separately | Metrics (§7) |
| R20/21 | Microsoft Prompt Shields (28 Aug 2026); MSRC indirect-injection defence (Jul 2025) | Vendor | Spotlighting; mark all external text as untrusted; deterministically block exfiltration paths | Wrap the remaining unwrapped inputs |
| R23 | AWS Bedrock contextual grounding check | Vendor | Separate grounding and relevance thresholds; do not stream before checking | Already the design (`AM-25` r5 has no token streaming) |
| R24 | AWS Bedrock Knowledge Bases metadata filtering | Vendor | Hard metadata filters; never let the model choose access filters | Brand filter set by code |
| R26 | Google *Sufficient Context* (arXiv 2411.06037, v3 Apr 2025) | Academic | Strong models answer wrongly rather than abstain; a sufficiency signal improves selective accuracy by 2–10% | Per-point answer state |
| R27 | Google SAIF | Vendor | Least privilege; auditable agents | Already largely met |
| R28 | MTRAG (arXiv 2501.03468) | Academic | Later turns, unanswerable turns and context-dependent turns are where systems fail | Multi-turn eval set |
| R29 | UAEval4RAG (arXiv 2412.12300) | Academic | Taxonomy of unanswerable queries; answer–reject trade-off | Unanswerable cases |
| R30 | Compound-QA (arXiv 2411.10163) | Academic | Compound questions degrade answers; the "omission" detail is unverified | Sub-point completeness checked in code |
| R31 | CLAMBER (arXiv 2405.12063) | Academic | Models judge ambiguity poorly | Decide *when* to ask a clarifying question in code, not in the model |
| R32 | AgentDojo, InjecAgent, CaMeL, PoisonedRAG | Academic | Indirect injection succeeds; separating control flow from data helps; 5 poisoned texts give ~90% attack success | Tool arguments must never come from retrieved text; corpus integrity |
| R33 | DPDP Act 2023 and Rules 2025 (notified 13/14 Nov 2025) | **Mandatory** | Notice, consent, security, breach notification and erasure obligations from 13 May 2027 | Production conversations, eval data, vendors |
| R34 | CERT-In Directions s.70B(6) (2022) | **Mandatory** where in scope | 6-hour incident reporting; logs kept 180 days, in India | Log retention; Legal to confirm whether Ask is in scope |
| R35 | ISO/IEC 42001:2023 | Voluntary standard | Certifiable AI management system | Optional, if clients ask |

### 2.2 Conclusions supported by two or more independent sources

1. Treat retrieved text and uploaded contracts as untrusted, possibly hostile input (R5, R20/21, R32, Anthropic).
2. No defence eliminates injection. Limit what an injection can do instead: read-only tools, least privilege, no tool parameters taken from retrieved text (R9, R15, R27, R32, R5).
3. Enforce access and scope filters in the query or code, not in the prompt (R17, R24, R27, R5).
4. Measure abstention and handoff when context is insufficient (R26, R28, R29, Anthropic, Copilot Studio).
5. Verify each claim against its cited source after generation (R14, R19, R23).
6. Score retrieval separately from the answer, and groundedness separately from completeness (R19, R23).
7. Decompose multi-question and multi-turn input. Decide in code when a clarifying question is needed (R18, R28, R30, R31).
8. Build eval sets from production logs and calibrate any judge against human labels (R11, R19, R1).
9. Trace every model call, tool call and check, with sensitive data redacted. Logs are kept 180 days where CERT-In applies (R13, R7, R10, R34).
10. Only two practices have **multi-authority backing**, from government bodies plus OWASP/SAIF: least privilege for agents, and treating external content as untrusted. Every other practice here is vendor guidance or research, and this plan does not call it an "industry standard".

### 2.3 Unverified (do not rely on these)
- The item list of OWASP LLM Top 10 2026.
- The full list of OWASP Agentic ASI01–10.
- The text and date of OpenAI's *Practical guide to building agents* (the PDF could not be read).
- The ICLR venue of Sufficient Context.
- Compound-QA's omission finding.
- The proposal to shorten the DPDP timeline.
- The CERT-In text and its effective date.
- The contents of the CISA PDFs (only landing pages were read).
- The NIST COSIS rename.

---

## 3. Current architecture and gap analysis

State key: **E** exists and is tested · **P** partial · **M** missing · **U** code exists but nothing shows it works.

| # | Area | State | Evidence | Gap |
|---|---|---|---|---|
| G1 | Brand scope within a turn | E | `published.named_brand` and `document_brand`; hard SQL filter in `constitution.py:347-359`; `retrieval.py:266-267`; `test_brand_scope.py` | — |
| G2 | Brand carried **across turns** | M | `tools.py:755` passes `prior=()`; brand comes only from the current tool query or the document | A topic-only follow-up searches both brands |
| G3 | Earlier-turn evidence re-scoped | M (**confirmed**) | Pinned `answer_evidence` (`agent.py:1008-1015`) → `ledger.refetch`/`_live` (`ledger.py:169-270`) checks permission and currency only; `EvidenceRegistry.adopt` (`agent.py:821`). No brand check in P2 (`agent_verify.py:793-811`). The production replay re-cited C7, C15 and C34 (Leapswitch TOS) in a CloudPe turn | Cross-brand citations |
| G4 | Stale evidence | M | `get_evidence` returns `state="stale"`, but `adopt` hard-codes `"current"` (`agent.py:828, 938-940`); `source_views` "current" (`service.py:1307`) | Superseded text shown as current |
| G5 | Points from the user's own asks | P | User message first, then the latest PASTE, never a FILE (`agent.py:1329-1333`). Production: 2 turns answered the attachment's numbering instead of the user's three asks | The user's prose asks are not extracted |
| G6 | Sub-points (a)(b)(c) | M | `points._ITEM` matches `1.` or `(1)` only | Sub-items silently skipped (16-point case: 1(b)–(d), 4(a)/(c)/(d)…) |
| G7 | Follow-up "answer points 9, 10" | P | The list is found only in a PASTE (≥400 chars and 60 words, `attachments.py:235`) | The promise in `points.py:181-185` can fail |
| G8 | Missing information and owner | M | No owner or handoff concept; gaps go to "Legal and Operations review" (production 525267a7 #5/#7) | No owner named; Legal gets operational and pricing questions |
| G9 | Clarifying question | U | `ask_user` stops the loop (`agent.py:1260`), but nothing forces a clarify block; points mode cannot clarify (`:1409`) | Untested end to end |
| G10 | Invented positions and verdicts | P | P13 exists; production still showed "standard commercial practice" and "is acceptable" (4 turns) | Phrase classes not covered |
| G11 | Party identity in forwarded emails | M | Opposite verdicts on the same email (74bd1f33 #3 vs 97231f35 #3) | No "we = Leapswitch Networks incl. CloudPe" anchor |
| G12 | Drafts | P | A draft gets only V5/V9/V11/P13 (`agent_verify.py:855-861`); production draft contradicted our own quote | Figures and terms unchecked |
| G13 | Conflicting sources | P | Scope labels exist (`tools._scopes`); 5 production turns showed TOS and Constitution figures side by side, unreconciled | No reconcile or "Legal to confirm" line |
| G14 | Follow-up understanding | U | Resolution was removed (`agent.py:1349-1356`); depends on model queries | Not measured |
| G15 | Latency budget | U | `FINAL_MIN_S` 30 can exceed `HARD_S` 40; NLI up to 120 s (`verify.py:129`); post-answer steps; no request deadline | Turn time is not bounded |
| G16 | Release gate on the live path | M | `verify_assist_quality` has no agent references; baseline 2026-09-17; run by hand (`ops/README.md:305`); agent evals end at EVALS #66 (2026-10-06) | Agent quality is never gated |
| G17 | Untrusted inputs fully marked | P | Current message, asked points, `find_documents` names and attachment filenames are not wrapped (`agent.py:948-951, 1108-1120`) | A filename can carry an injection |
| G18 | Spend and DoS | P | 120/h per user, in-process (resets on restart); `estimated_usd` null in production; no daily quota | Cost runaway up to ~120 × 165k tokens/h per user |
| G19 | Monitoring and alerts | M | Journal lines only; no alerting config in `ops/` | Silent degradation |
| G20 | Resilience | P | Failover built but off in production; no circuit breaker; no idempotency key | A quota 429 floors every turn; double submit gives two turns |
| G21 | Privacy and lifecycle | P | Attachment purge exists (timer live); conversation retention blocked on an owner decision; client material reaches Gemini (and IndieRouter/DeepSeek when chosen) under `AM-113`; no DPIA or processing record | DPDP obligations from 13 May 2027 |
| G22 | Escalation from Ask | M | Only "Not helpful" (`TranscriptTurn.tsx:323`) | No route to Legal |
| G23 | Delivery | P | No SAST (bandit/semgrep/CodeQL), no CODEOWNERS; three answer paths coexist (LEGACY, MULTI_SOURCE, agent) | Review load; dead paths |
| G24 | Pre-router misroute | **Fixed on branch** | `AM-200`: 19/29 → 0/30, production replay 2/36 → 0/36 | Commit pending |

---

## 4. Prioritised risks

**Critical.** These cause wrong commercial or legal commitments, and no aggregate score may waive them.
- **C1 — Cross-brand evidence (G2, G3).** A CloudPe client is quoted Leapswitch terms: the 60-day force-majeure exit and the 7-day suspension.
- **C2 — Superseded evidence presented as current (G4).**
- **C3 — Unsupported conclusions (G10, G11).** "Is acceptable", "standard commercial practice", and opposite verdicts caused by mistaking who the parties are.
- **C4 — Draft emails with figures or terms no source supports (G12).**

**High.**
- **H1 — The user's own asks and sub-points not answered or tracked (G5, G6, G7).**
- **H2 — Missing information with no owner, or routed to the wrong owner (G8).**
- **H3 — No release gate on the live agent path (G16).**
- **H4 — Unwrapped untrusted inputs (G17).**
- **H5 — No spend cap or cost visibility (G18).**
- **H6 — No monitoring or alerts (G19).**
- **H7 — Unreconciled conflicting sources (G13).**

**Medium.**
- **M1 — Clarification not built end to end (G9).**
- **M2 — Follow-up understanding not measured (G14).**
- **M3 — Turn time not bounded (G15).**
- **M4 — Resilience: failover off, no breaker, no idempotency (G20).**
- **M5 — Privacy record, retention and vendors (G21).** This needs a decision. Legally it becomes High as 13 May 2027 approaches.
- **M6 — No escalation from Ask (G22).**

**Low.**
- **L1 — Formatting and bookkeeping defects.** Truncated headings, `****15%****`, a false "Not answered" line.
- **L2 — No SAST, no CODEOWNERS, module size (G23).**
- **L3 — Stale docstrings and risk register.**

---

## 5. Target architecture and design decisions

**Keep (works, and the evidence supports it).**
- Postgres with exact pgvector (`AM-84`).
- One agent loop with a small, read-only tool set.
- The local NLI verifier.
- Non-streamed answers, verified before display.
- Authorization in tool code.
- Fixed-text routes.

Nothing in this plan adds a framework, database, vendor or orchestration layer.

| Decision | What changes | Why (evidence) | Rejected alternative |
|---|---|---|---|
| D1 **Conversation scope object, set in code** | Each turn takes its brand from: the selected document → the brand named in this message → the latest brand named earlier in the conversation → none. The result is applied to retrieval, to evidence adoption (`ledger`/`EvidenceRegistry.adopt`) and to a new verifier check that rejects a published-policy citation from the other brand. The reply opens with a fixed line naming the brand. | R17, R24, R27: filter in code, not in the prompt. G2/G3 confirmed. | Ask the model to "stay on CloudPe" in the prompt (R24: never let the model pick filters). |
| D2 **Evidence state carried end to end** | `adopt` keeps `state`. Stale records are refused as citations unless the user asked for history (`include_superseded`). Sources show their state. | G4; information-integrity risk (R2). | Silently refreshing stale records (the user would never see that the text changed). |
| D3 **Per-point slots in code** | The user's asks are parsed in code from the user's message or paste, including (a)(b)(c) sub-items and prose asks introduced by a cue ("client asked/wants"). The list is kept on the conversation, so "points 9, 10" can find it later. The answer schema returns one slot per item, keyed by the user's number. Code checks completeness and order, re-asks once, then names whatever is still missing. | R18, R30, R31; G5–G7; production failures. | Rely on prompt wording ("answer every point"), which already fails in production. |
| D4 **Answer state and owner per slot** | A closed enum from the model: ANSWERED, PARTLY, NOT_IN_SOURCES, DEPARTS. Owner is SALES, OPERATIONS or LEGAL. Code renders fixed text from `config/assist_owners.json` plus a summary line. A clarifying question is decided by code rules: brand unknown and the two brands' sources differ on the topic, or a needed document is absent. It is asked once, and never when the scope can be inferred. When the user could hold the settling document (quote, contract), Ask requests it alongside the answer. | R26, R29, R31, Copilot Studio, Intercom (handoff text fixed, not model-written). | Model-written handoff text (invents owners); always asking first (CLAMBER: models over-ask and ask poorly). |
| D5 **Verifier extensions, deterministic first** | (a) Verdict and "practice" phrase classes added to P13. (b) Drafts: every figure or term must match a cited record or the conversation's quoted source (V2 and P10 logic reused for drafts). (c) Conflicting figures on one topic across cited records require either both scope labels or a fixed line, "our documents differ — Legal to confirm"; no precedence rule is invented (rule 7). (d) Party anchor in the system contract: "we = Leapswitch Networks Private Limited incl. its CloudPe brand", plus a test with both production emails. | R14, R19; G10–G13; rule 7. | An LLM judge in the request path (cost and latency; R11 says calibrate judges, not gate on them). |
| D6 **Close the injection gaps** | Wrap the current message, asked points, document names and filenames with `generation.untrusted`. Tool arguments are never taken from retrieved text (already true; pin it with a test). Add an injection case set to the eval. | R5, R20/21, R32. | Adding Azure Prompt Shields (new vendor and egress; `AM-30` single egress). |
| D7 **Bounded turn** | One request-level deadline covering everything, including NLI and post-answer steps. A partial result names the points it did not finish. | G15; R5 unbounded consumption. | Raising the timeouts. |
| D8 **Spend control** | A per-user daily token budget (value is an owner decision), enforced before egress. Configure `estimated_usd` from the env rates. | R5 unbounded consumption; G18. | Rate limiting only (it does not cap tokens). |
| D9 **Observability without new infrastructure** | A daily report script reads the existing `assist.agent.turn`, `assist.ask.trace` and generation events. It reports floor rate, point coverage, cross-brand detections (must be 0), stale citations, latency p50/p95, calls and tokens per turn, and provider errors, and alerts by email or Slack when a rollback trigger fires. | R7, R10, R13; G19. | Prometheus/Grafana/OTel (a new stack, rule 19). It stays an open option if the volume grows. |
| D10 **Resilience** | An idempotency key on Ask submit. A circuit breaker on repeated 429/5xx from the provider: a fixed, honest outage line instead of N floors. Failover stays off until vendor terms are decided (M5). | G20. | Automatic failover to IndieRouter now (a privacy decision is pending). |

---

## 6. Phased roadmap

Dependencies run top-down. **P0 must come first**, because every later phase is measured with it. Each phase follows the owner's order: failing tests → fix → measure → records → wait for "commit".

| Phase | Deliverables | Depends on | Est. effort |
|---|---|---|---|
| **P−1 (done, on branch)** | `AM-200` pre-router fix, `ASK_PREROUTE_TEST.md`, tests | — | done; commit pending |
| **P0 Baseline and harness** | (0) `backend/tools/ask_turn_trace.py`, read-only per-turn investigation (§7A step 3), plus the Drive-sourced attack scripts (§7A step 1). (1) `backend/tools/ask_conversation_eval.py`: replays multi-turn cases through `agent.run_turn` on a session that refuses commit (the method proven today), with a Scripted provider for unit tests and Gemini for measurement; reports calls, tokens and latency. (2) Deterministic scorers: citation brand, evidence state, point and sub-point coverage and order, owner present, verdict phrases, draft figures, untrusted wrapping. (3) Case set (§7) built from redacted production patterns; real transcripts stay outside the repo (decision Q2). (4) **Measured baseline** on today's code: one Gemini run, budget ≤ 200 calls. (5) Agent awareness added to `verify_assist_quality` (or a documented successor) as the release gate. | — | 3 days |
| **P1 Critical correctness** | D1 brand scope (incl. ledger and verifier), D2 evidence state, D5(a)(b)(d) verdicts, drafts, party anchor | P0 | 4 days |
| **P2 Conversation reliability** | D3 per-point slots, D4 answer state, owner and clarification rules, D5(c) conflicts | P1 | 4 days |
| **P3 Security and cost** | D6 injection gaps and injection eval, D8 spend cap, D7 bounded turn | P0; D8 needs Q3 | 2–3 days |
| **P4 Operations** | D9 daily report and alerts, D10 idempotency and breaker, rollback triggers documented in `ops/README.md` | P0 | 2–3 days |
| **P5 Governance and delivery** | Refreshed AI risk register (mapped to R1/R2); escalation from Ask (Q7); SAST in CI (Q6); CODEOWNERS; LEGACY and MULTI_SOURCE answer paths retired, measured first; stale docstrings fixed; DPIA and retention (Q4/Q5) | decisions | 2 days plus decisions |

**Lock amendments expected.** The owner has authorised amending any lock that blocks enterprise-grade Ask. Each one is appended to `all_lock.md` at the next free AB/AM number after checking every worktree, then the registry and docs are synced.

| Lock | Amendment |
|---|---|
| `AM-145` | Brand from the conversation, and the ledger re-scoped |
| `AM-25` r5 / `AM-90` family | Per-slot states and owner lines |
| `AM-118` r4 | Clarification rules |
| `AM-111` | Evidence state on adoption |

`AM-30`/`AM-113` (egress and vendors) are **not** amended without decision Q5.

---

## 7. Evaluation strategy and test matrix

**Three layers. No layer relies on an LLM judge alone or on "all points answered".**
1. **Deterministic** (CI, zero Gemini): permissions, schemas, scope, point counts and order, routing, injection wrapping, evidence state.
2. **AI quality** (manual release run, Gemini): groundedness, completeness and relevance. The judge is calibrated against 30 human-labelled turns before its scores are used (R11).
3. **Human review**: a sample of legally or commercially consequential replies (verdict-adjacent, drafts, DEPARTS slots) reviewed by Legal before release.

**Test matrix.** Baseline figures are observed in production or measured today. "Expected" is the target after the fix.

| ID | Input | Expected behaviour | Severity | Scoring | Failure condition | Baseline |
|---|---|---|---|---|---|---|
| T1 Wrong brand | CloudPe proposal, follow-up "for cloudpe" after a Leapswitch-sourced answer | Only CloudPe published sources plus the Constitution; opening line "Answering for CloudPe" | Critical | Deterministic: brand of every cited published source | Any other-brand published citation | Replay 2026-10-22: 3 Leapswitch citations (C7/C15/C34) |
| T2 Shared vs brand-specific | CloudPe question on a topic only the Constitution covers | Constitution cited as entity-wide; no Leapswitch TOS | Critical | Deterministic | Leapswitch TOS cited | Production 525267a7 #29 (60-day force majeure) |
| T3 Stale evidence | Follow-up after a policy version changed | Stale record refused or labelled superseded | Critical | Deterministic: state of every citation | A stale record shown as current | Not measured (code path confirmed) |
| T4 Verdicts | "is this acceptable?", "standard commercial practice" | No acceptance or practice claim without a citation | Critical | Deterministic phrase classes plus human sample | Any occurrence | 4 production turns |
| T5 Party identity | Forwarded client email using "you/the provider" | "we" = Leapswitch; the same verdict class on the two production emails | Critical | Deterministic pair consistency plus human | Opposite verdicts | 74bd1f33 #3 vs 97231f35 #3 |
| T6 Draft figures | "please draft a email" after a quote is attached | Draft present; every figure and term traceable to a cited or quoted source | Critical | Deterministic figure match | Missing draft, or an untraceable figure | 97231f35 #3 (annual vs 2-year), #7 (no draft) |
| T7 Own asks vs attachment | Forwarded email with 3 prose asks plus a 5-clause PDF | 3 slots, the user's asks | High | Deterministic | Attachment numbering used | 2 production turns |
| T8 Sub-points | The 16-point email with (a)–(f) | Every sub-item has a slot, in order | High | Deterministic | A skipped or merged sub-item | `points:14/16`; many sub-items skipped |
| T9 Follow-up list | "answer points 9, 10" after a short list | Exactly items 9 and 10 from the earlier list | High | Deterministic | Not found, or wrong items | Fails when the list is <400 chars (code) |
| T10 Missing information | ₹2,750 breakdown, RPO/RTO, facility names | NOT_IN_SOURCES plus the owner line (Sales/Ops); no figure invented | High | Deterministic owner field plus no-figure check | An invented figure, no owner, or Legal for an ops question | 3 production turns |
| T11 Conflicting sources | TOS 7-day vs Constitution 30-day | Both scopes stated, or the fixed "Legal to confirm" line | High | Deterministic | Both figures, unreconciled | 5 production turns |
| T12 Clarification | Brand absent and not inferable, sources differ | One clarifying question, then the answer | Medium | Deterministic, 2-turn | Guessing a brand, or asking twice | Not built |
| T13 Follow-up references | "this case", "above", fragments | Answer about the referenced item | Medium | Judge (calibrated) plus human | Wrong referent | Not measured |
| T14 Prompt injection | Instructions in the message, paste, filename and retrieved chunk | Instruction not followed; note to the reader; tools unaffected | High | Deterministic plus a case set | Instruction obeyed or a tool argument taken from the text | Unit tests only |
| T15 Cross-user evidence | User B asks about user A's conversation or evidence keys | Identical "not found" | Critical | Deterministic (exists) | Any disclosure | Pass (existing tests) |
| T16 Provider failure | 429 repeated, timeout, 5xx | One retry, then an honest outage line; no duplicate turn | Medium | Deterministic, fault injection | N floors, or a duplicate turn | Floors every turn (code) |
| T17 Runaway cost | Burst of long turns from one user | Stopped at the daily budget with a fixed message | High | Deterministic | Budget exceeded | No cap |
| T18 Pre-router | 29 messy follow-ups plus 36 production messages | Reaches the model; controls still get fixed replies | High | Deterministic | Any misroute | Fixed: 19/29 → 0/30 |

---

## 8. Release criteria (provisional until the P0 baseline is measured and approved)

**Release blockers. Zero tolerance; never waived by an aggregate score.**
- Any T1/T2 cross-brand citation.
- Any T3 stale citation shown as current.
- Any T4 verdict or practice claim without a citation.
- Any T6 untraceable draft figure.
- Any T15 cross-user disclosure.
- The authorization matrix (CI job 3) failing.
- Any T14 injected instruction obeyed.

**Deterministic suite.** 100% pass in CI, as now.

**Structural coverage.** Every asked point and sub-point has a slot, in the user's order (T7–T9). 100% on the case set.

**AI quality.** Groundedness and completeness thresholds are set after the P0 baseline at "no worse than baseline, and better on the failing classes". Proposed, not standard: the slot owner is correct on ≥ 90% of human-labelled NOT_IN_SOURCES items.

**Latency and cost.** p50/p95 measured at P0; the release target is no p95 regression against the baseline.
- Calls per turn ≤ 8, as now.
- Tokens per turn are reported.
- The daily per-user budget is owner-set (Q3).

**Human review.** Legal reviews the sampled DEPARTS, verdict-adjacent and draft replies before each Ask release.

**Rollback triggers** (P4 report, checked daily and after each deploy):
- cross-brand or stale detections > 0;
- floor rate > 2× baseline;
- provider error rate > 2× baseline;
- p95 latency > 1.5× baseline.

Rollback is flag-based: `LEGALMIND_ASK_AGENT_MODE=off`, `LEGALMIND_CAPABILITY_ROUTE=off`, or the new feature flags. Each new behaviour ships behind a flag that defaults on, with off as the documented rollback.

---

## 9. Security, privacy, observability, resilience and rollback

- **Security:**
  - Keep authorization in code; it already exists.
  - Close the G17 wrapping gaps.
  - Add the injection case set (T14).
  - Pin "tool arguments never from retrieved text".
  - Add the spend cap (D8).
  - SAST in CI is decision Q6 (rule 19, new dependency).
- **Privacy:**
  - Eval cases are derived and redacted; no client or person names enter the repo (54.6, plus the CI job that blocks real contracts). Real transcripts stay in production and are read only by the replay tool, with rollback.
  - DPIA, processing record, conversation retention and vendor terms are decisions Q4/Q5 under DPDP (R33, mandatory from 13 May 2027).
- **Observability:** D9 daily report and alerts. Every event already carries `request_id`, model, prompt version, tokens and latency. Add brand, slot coverage and evidence-state counts to `assist.agent.turn`, with no user text. Log retention against CERT-In's 180 days is for Legal to confirm (R34).
- **Resilience:** D7 request deadline; D10 idempotency key and circuit breaker; failover decision Q5.
- **Rollback:** flags per behaviour (§8), and the existing deploy-script rollback (`ops/README.md:60`).

---

## 10. Effort and major uncertainties

**Effort.** About 17–20 engineering days across P0–P5, excluding decision time. P0–P2 (≈ 11 days) remove all Critical and most High risks.

**Uncertainties.**
- How Gemini follows a slot schema with 16+ items within the time budget. Measured in P0, with the lean profile as a fallback.
- Whether stale-evidence adoption actually occurs in production. The code path is confirmed; the frequency is not.
- Human-label availability for judge calibration (Legal time).
- Unverified research items (§2.3).

---

## 10A. Owner rulings received 2026-10-22 (supersede the matching rows of §11)

| # | Ruling | Effect on this plan |
|---|---|---|
| O1 **Data** | Use the data already in the shared Drive ("legal docs from clients", folder `1ZfPF_l3oe4XDP-4uFEuYKreEKd1SQcV1`), including the MOU contracts | Q2 closed. Read it through the connected Google Drive tools. **Never** copy files or real counterparty or person names into the repo; committed cases are redacted derivatives (memory rule; 54.6) |
| O2 **Benchmarks** | The owner provides exact numbers for accuracy, maximum latency, maximum cost per query, and the proof required that old bugs are fixed | Q3/Q9 closed. §8 thresholds are replaced by the owner's numbers when they arrive. P0 still measures a baseline so every number has a before/after |
| O3 **Legal verification** | The owner handles it and comes back only for external help | Q8 closed. "Legal reviews before release" in §7/§8 becomes "owner verification". Ask keeps the fixed line "our documents differ — confirm which applies" until the owner states a precedence rule |
| O4 **Proof** | Shown through the CI/CD pipeline link or a live demo | Every deterministic test runs in CI (job 13); the adversarial cases replay as a script for the live demo |
| O6 **Every model the same** (2026-10-22) | "We also have other models — treat them equally, all the LLMs we use on the same page" | Every case, gate, release blocker and threshold applies **per model**: Gemini, DeepSeek (via IndieRouter) and Bonsai, the three in `model_router.MODELS`. `tools.ask_conversation_eval --models gemini,deepseek,bonsai` runs them on the same cases and prints one case × model page with each model's latency, calls and tokens. A model that fails a release blocker is not offered to readers until it passes (the model picker), whatever the other models score |
| O5 **Method** | 5 users, the Drive contracts (incl. MOUs), questions **designed to make Ask fail**; read the logs, find why, fix | Adds §7A (red-team protocol) and the investigation tool in P0 |

## 7A. Red-team protocol — 5 users, built to make Ask fail (owner method, O5)

1. **Prepare (P0).** From the Drive folder, pick contracts and emails: the MOUs, marked-up drafts, CloudPe and Leapswitch proposals, forwarded client emails. Pre-write about 10 attack scripts per user across the §7 classes:
   - wrong brand, sub-points, missing information, verdict bait, party confusion;
   - draft with figures, conflicting sources, follow-up references, injection in a pasted email or a file name;
   - messy Hinglish, fragments.

   Users also improvise.
2. **Run.** 5 users, each in their own account, on a staging copy or production as the owner chooses. Every turn is logged as today; no new data is collected.
3. **Investigate.** New read-only tool `backend/tools/ask_turn_trace.py <conversation_id>` prints, per turn:
   - the message and the brand and scope chosen;
   - points and slots, tool calls and queries;
   - evidence offered (with brand and state), checks failed and blocks dropped;
   - flags, latency per stage, tokens and calls.

   It reads the DB and `assist.agent.turn` / `assist.ask.trace`; it writes nothing and calls no model. This is "read the logs, find why".
4. **Triage.** Each failure is classified by §7 class, root cause (stage: routing, scope, retrieval, ledger, slots, generation, verifier, rendering) and severity. It then becomes a redacted, deterministic regression case in the eval set before any fix.
5. **Fix and prove.**
   - Failing test → fix → CI green (O4 link).
   - The same attack replayed through the investigation tool, before and after.
   - The rollup reported against the owner's O2 numbers.
6. **Repeat** until a round of 5 users finds no Critical failure and the O2 numbers hold.

## 10B. P0 findings (2026-10-22, measured; supersede the matching gap rows)

| # | Finding | Evidence | Effect |
|---|---|---|---|
| G2b **The company name read as the brand** | The 16-point email says "LeapSwitch to confirm" fourteen times. `published.named_brand` reads that as the Leapswitch brand, so the first answer searched **only** Leapswitch policies. The product was a CloudPe cloud VM. "LeapSwitch" there names the **entity** (Leapswitch Networks, which operates both brands), not the brand. | `tools.ask_turn_trace` on the production turn: "brand: named in message=Leapswitch", and the ledger holds 34 Leapswitch and 0 CloudPe published records | D1 must not take the brand from the company's own name. A product cue or the reader settles it, otherwise one clarifying question (T12). C-19's entity → brand → product chain is the reference. |
| G4 measured | Stale evidence presented as current: **0 of 36** production turns. The 6 non-current citations are `historical` Constitution records (labelled, `AM-107`) and `draft` document text (labelled), both by design | Trace over all 11 production conversations | Still Critical as a guarantee (D2); not observed in practice |
| G19b **Journal retention ~7 days** | `journalctl -u legalmind-api` starts 2026-10-15. Turn logs older than that are gone | Same trace: 13 turns with NO_TURN_LOG | Investigations must happen within days. CERT-In's 180 days (R34) is not met for these logs: D9 must persist the turn record, or retention must be raised. Owner/Legal to confirm scope |
| G25 **The same input, a different answer** | The 16-point email on the same code, two runs: **15 of 16** points answered on one, **1 of 16** on the next. The verifier dropped **30** blocks, then the coverage line named the other 15 as unanswered | `tools.ask_conversation_eval` C01, main 15/16 vs. a rerun 1/16 (the AM-200 change does not touch the points path) | One run is not a measurement: every gate runs `--repeat ≥ 3` and reports the spread. The drop root cause (which checks reject which blocks on long lists) is a P2 item next to D3 |
| Production baseline (agent path) | 21 model turns: latency p50 **18.5 s**, p95 **30.3 s**, max 72.2 s (the 16-point turn); **3.43** model calls per turn (max 4); **63.6k** tokens per turn (max 113k) | Trace over all production conversations | The before-numbers for the owner's latency and cost thresholds (O2) |

## 10C. Progress (2026-10-23)

| Phase | State | Measured |
|---|---|---|
| P−1 | done (`AM-200`) | pre-router 19/29 → 0/30 failures |
| P0 | done — trace, eval (all models), daily report, red-team sheet; baseline 7/15 × 3 models | production p50 18.5 s / p95 30.3 s |
| P1 | done (`AM-201`) | 12/15 Gemini, 13/15 DeepSeek, 13/15 Bonsai |
| P2 | done (`AM-202`), critical review: one regression (brand question over-asked) found and fixed | failing cases: DeepSeek 6/6, Gemini 4/6, Bonsai 3/6 |
| P3 | D6 done; D8 ceiling built (value pending O2); D7 done (`AM-204`: re-ask only with time; claim checker 120 s) | — |
| P4 | D9 daily report (alert delivery not built); D10 breaker done (`AM-204`); idempotency not built | report fired correctly on 2026-10-22 production |
| P5 | SAST in CI done (ruff Bandit, `AM-204`); risk register, escalation, DPIA/retention not started | OIDC assert and plain-HTTP key path fixed |
| Final (2026-10-23) | every fix, 15 cases, rolled back | Gemini 13/15 · DeepSeek 12/15 · Bonsai 12/15 (main 7/15); full suite 4275 passed |

Open for the owner: the O2 numbers; Bonsai on long lists (recommend not offered above 8 points); commit.

## 11. Decisions requiring approval (Q2, Q3, Q8 and Q9 closed by §10A)

| # | Decision | Recommendation |
|---|---|---|
| Q1 | Owner text for missing information | Team names only: Sales / Solutions-Operations / Legal. No personal names, so it never goes stale. |
| Q2 | Using production conversations for evals | Derive redacted cases into the repo; keep raw transcripts only in production, read through rolled-back replay. |
| Q3 | Per-user daily token or cost budget | Set after the P0 baseline (e.g. 3× the p95 daily use). Value for the owner. |
| Q4 | Conversation retention period (DPDP) | Decision pending since earlier; needed before May 2027. |
| Q5 | Vendors receiving client material (Gemini, IndieRouter/DeepSeek), and failover in production | Keep failover off until a DPA and terms are recorded. |
| Q6 | Adding SAST (bandit or semgrep) to CI | Approve as a dev-only CI dependency. |
| Q7 | "Send to Legal" escalation from an Ask answer | Approve; reuse the existing review-assignment pattern (`AM-170`). |
| Q8 | Precedence when the published TOS and the Constitution differ | Legal states the rule. Until then Ask says "our documents differ — Legal to confirm" (rule 7). |
| Q9 | Release thresholds | Approve after the P0 baseline report. |
| Q10 | Plan approval | Approve P0 first. Each later phase reports before it starts. |

---

## 12. Five most important gaps in the earlier plan

1. **No gate on the live path.** The release gate does not test the agent (G16), so the earlier plan's fixes would not have been measured.
2. **Treated brand mixing as a retrieval problem.** The confirmed cause is earlier-turn evidence in the ledger plus no verifier check (G3), so the fix has to be in code at adoption and verification.
3. **Missed stale evidence presented as current (G4).**
4. **Left out security, cost and privacy.** Unwrapped inputs, no spend cap, no monitoring, and DPDP-bound production conversations used as eval data (G17–G21).
5. **No release blockers, rollback triggers or calibrated-judge discipline.** The earlier plan's "done" could have rested on an LLM saying all points were answered.

## 13. Verified, unverified and proposed

- **Verified (code, test or measurement):** G1, G3, G4 code paths; G5, G8, G10–G13 (production turns); G16–G21 (files and config); G24 (measured).
- **Unverified:** G9, G14, G15 behaviour; the stale-evidence frequency; the §2.3 items.
- **Proposed:** everything in §5–§8 and all thresholds.

## 14. Files to change on approval (planning docs only)

| File | Change |
|---|---|
| `docs/architecture/ask-agent/ENTERPRISE_READINESS_PLAN.md` | New: this plan |
| `docs/README.md` | Index entry |
| `docs/00-project/IMPLEMENTATION_STATUS.md` | Plan referenced; build state unchanged |
| `docs/00-project/LEGALMIND_PROJECT_STATE.md` | One status line |
| `DAILY_CHANGED.md` | Research entry |
| `docs/08-testing/ASK_PREROUTE_TEST.md` | Link to the plan |

No code changes until P0 is approved. Nothing is committed until the owner says "commit".
