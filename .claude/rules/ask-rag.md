---
paths:
  - "backend/legalmind/assist/**"
  - "backend/tests/assist/**"
  - "backend/tools/*rag*"
  - "backend/tools/probe_*"
  - "backend/tools/benchmark_*"
  - "backend/tools/verify_assist_quality.py"
  - "backend/tools/chunk_*"
  - "frontend/src/**/ask/**"
  - "frontend/src/**/Ask*"
  - "docs/LEGALMIND_RAG_PRODUCTION_ROADMAP.md"
  - "docs/DAILY_CHANGED.md"
  - "docs/00-project/ASK_*.md"
  - "docs/architecture/ask-agent/**"
---

# Ask / RAG lane

Read `AM-25` (its nine terms) and `AM-30` (the generation egress) in LOCKED_DECISIONS.md /
`all_lock.md` before building anything here. Ask never decides (CLAUDE.md rule 10).

## The master roadmap (owner, 2026-09-24)

[LEGALMIND_RAG_PRODUCTION_ROADMAP.md](../../docs/LEGALMIND_RAG_PRODUCTION_ROADMAP.md) is the
**only** master roadmap and is already approved as the target ("i want industry standard rag
system … i will give you ownership you do not have to ask me"). It supersedes
[ASK_TARGET_ARCHITECTURE.md](../../docs/00-project/ASK_TARGET_ARCHITECTURE.md) as the target;
that document stays the record of what was built and measured. Never create another roadmap;
keep its phase order (§19, PHASE 0 → 13) and goals.

- **A legacy lock that conflicts with the roadmap is AMENDED, not preserved** — the roadmap
  approval satisfies rule 6 for roadmap conflicts only. Procedure: skill `lock-amendment`
  (name the old ID → append to `all_lock.md` → LOCKED_DECISIONS.md and every affected doc/test →
  log in DAILY_CHANGED.md → continue).
- **Not changed by the roadmap** (report a conflict, never amend): rules 7 and 21 (roadmap
  §10/§22 forbid inventing legal content too), rule 18 and authorization inside every query,
  the append-only audit trail, the cost guard below.
- **Every phase:** implement → test → measure against the exit criteria → fix → log in
  [DAILY_CHANGED.md](../../docs/DAILY_CHANGED.md) → report and wait for "commit". Code-only
  success never completes a phase.
- The programme branch `feat/legalmind-rag-production` merged and deployed on 2026-09-28
  (PR #121); new Ask work goes on a fresh task branch from `main` in your own worktree.
- DAILY_CHANGED.md is the programme log (not the operations log `docs/00-project/DAILY_CHANGES.md`).
  Its first entry is the 2026-09-24 baseline audit; do not re-run it unless evidence shows it stale.

## The ten canonical stages (owner, 2026-09-17) — name them this way

**1** conversation context → **2** query understanding → **3** knowledge router + authority
policy (DOCUMENT · COMPANY STANDARD · GENERAL LAW) → **4** query planner → **5** authorized
targeted retrieval (hybrid lexical + vector + metadata) → **6** reranker → **7** evidence
sufficiency gate → **8** grounded generation → **9** answer verification → **10** response
(answer + citation + expandable evidence).

The per-stage state, code and measurements are in ASK_TARGET_ARCHITECTURE.md §0 and the
roadmap's requirement matrix ([ROADMAP_REQUIREMENT_MATRIX.md](../../docs/00-project/ROADMAP_REQUIREMENT_MATRIX.md)).
**Do not trust a stage-state summary anywhere else** — the old CLAUDE.md said stage 6 was
"never built" long after the reranker shipped (`AM-87`). Check the code and the flags
(`LEGALMIND_RERANK`, `LEGALMIND_ASK_MULTI_SOURCE`, `LEGALMIND_ASK_AGENT_MODE`, …) before
asserting.

Invariants no stage may weaken:

- **Stages 3 and 7 are code, never a prompt.** Permissions decide candidate domains before
  question shape (`AM-45` r1); answerability is decided deterministically on the caller's
  original question (since `AM-84` r4: reranker + evidence sufficiency + authority/version
  checks), so a model's rephrasing can never turn a refusal into an answer.
- **The model never decides.** It may understand, plan, reformulate, synthesise and explain
  within authorized domains; it never routes to/away from the evaluator, opens the gate, states
  a position absent from a ratified standard, says whether anything complies, or is cited
  (`AM-25` r1–r5, `AM-28` r2).
- **Stage 9 fails closed, so there is no token streaming** (`AM-25` r5, `AM-69`). Perceived
  speed comes from streamed progress states.
- Language is not a safety boundary: a screen that cannot evaluate an input fails closed (`AM-69`).
- Retired (`DEPRECATED`) standards are excluded from BOTH lexical and vector retrieval (`AM-71`).

## Paid-model cost guard (owner, 2026-09-18; extended to every paid provider 2026-10-29)

Gemini (`AM-30`), DeepSeek via Together (`AM-225`) and any other metered model are the LAST
instrument, not the iteration loop.

1. Test with deterministic/local logic and existing retrieval first; call a paid model only when
   the model-dependent behaviour is ready to validate.
2. No measurable gain → STOP calling it; diagnose locally, retest.
3. Every benchmark reports model call count, latency and tokens/cost; never add one that hides them.
4. Do not advance a phase until improvement is demonstrated.
5. Before any paid run, estimate tokens and dollars, check the balance, and state the cost.

Fixed order for the assist lane:

| | Tool (`backend/`) | Paid model |
|---|---|---|
| 1 | `python3 -m tools.rag_benchmark` — the roadmap benchmark | none |
| 2 | `tools/probe_targeting.py` — recall@10 / hit@1 / MRR / gold@3 through `search_hybrid` | none |
| 3 | `tools/benchmark_rerank.py` — reranker ordering; `tools/probe_gate.py` — gate ideas | none |
| 4 | `tools/verify_assist_quality.py` — Tier-2 gate end to end, run once as confirmation | generation + rescue judge |

The Tier-2 gate cannot settle a retrieval question: its targeting metrics are scored only over
questions whose gate opened, which moves with the nondeterministic rescue judge. Use the probe.

## Testing here

CI has no model weights — 48 Ask tests skip there and read green. For a change to a prompt, the
model router, retrieval or the verifier, run `tests/assist` locally twice: with models
(`LEGALMIND_RERANK=on`) and CI-shaped (`LEGALMIND_MODEL_DIR=/nonexistent`). A test needing an
embedder carries `@pytest.mark.skipif(not embedding_runtime.available(), ...)`. Validate verifier
or rule changes on real-claim evaluation data, not synthetic cases only. The nightly
`assist-models-nightly.yml` runs the suite with the pinned models.
