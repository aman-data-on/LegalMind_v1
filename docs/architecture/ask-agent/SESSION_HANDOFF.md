# Ask agent — session handoff

Per-session log. Current state lives in [STATUS.md](STATUS.md); the end-of-session ritual in
[SESSION_CHECKLIST.md](SESSION_CHECKLIST.md). No client name, client text or key appears
here: fixtures are named by their private Drive id (`/root/.legalmind/test-corpus/raw/`,
mode 700/600, owner rulings D10/D11).

---

## Session 2026-10-07-LD — Latency diagnosis

**Diagnosis only. No behaviour changed:** no prompt, retrieval, model, chunking, cache, streaming or
UI change; no code committed. Branch `rag/latency-diagnosis-20261007` (worktree
`/root/legalmind-worktrees/latency-diagnosis`), from `origin/main` `0aee166` — the code production
runs (`f60d655` + the top-bar merge, which touches no Ask code). Local commits only, records only.

**Method, in the order the reuse rule demands.**
- Prior data was read first: the 2026-10-07-RG records below, the 2026-10-07-DF branch
  (`rag/defect-fixes-20261007`, `88ad229`, a live session), its raw per-stage files, 176 captured
  model calls, 31 run files, the scratch answer rows and the production log.
- Then only what was missing was run:
  - a zero-model profiler that replays real captured provider responses instantly against
    `main`'s agent, so every non-model millisecond is timed per function, with SQL round-trips
    counted (37 turns, 0 model calls);
  - 16 raw, STREAMED provider calls, built from public statute text, to expose first-token time,
    cached tokens and reasoning tokens. The app records none of these.
- Private harness, numbers only, no client text: `/root/.legalmind/latency/` (mode 700).
  - `profile_turn.py`, `profile_service.py`, `raw_calls.py`, `ui_paint.mjs`, `mine_captures.py`;
  - outputs `calls.json`, `profile_full{,2,3}.log`, `raw_calls.jsonl`.

**The canonical question.** "Is the liability cap in this agreement enforceable?" (T4) on the
executed MSA, Drive `1k_mgdJyyUE0sAJ3vOlLQysW_nHXruh0-`: 28 pages, 162 chunks, 68,444 characters.
The 17-point question is T7: the e-mail Drive `1qTS1TkK4Vfk2Vf5w20quyGJD-gpYB9_0` with "Which of
these points conflict with our standard positions?".

### 1. Prior data inventory (Step 0)

| # | Experiment / metric | Prior result | Source | Date | Still valid? | Action | Why |
|---|---|---|---|---|---|---|---|
| P1 | Per-stage live timing, T4, fresh chat, 3 models | Gemini 27,035 ms · DeepSeek 41,235 ms (floor: final timed out) · Bonsai 70,481 ms, with stages, calls, tokens, verify s | session `ddbb3cf3` scratchpad `d5_before.json` (method `d5_measure.py`) | 2026-10-07 17:55 | **yes** — run on DF `996dbc4` = `main` + D1–D4, none of which runs on T4 except D4's named-clause lookup (ms) | **reuse** | the in-process method is the one this report would use |
| P2 | Same, after D5 changes | Gemini 38,508 / 25,940 · DeepSeek 41,459 / 42,328 / 42,084 · Bonsai 110,382 / 87,297 / 45,545 | `d5_after.json`, `d5_after2.json`, `d5_after2b.json`, `d5_after3.json` (same scratchpad) | 2026-10-07 18:01–18:09 | **yes, as DF-branch evidence** (not `main`) | reuse | used for "after" levers and DeepSeek answered samples |
| P3 | Streamed provider first token inside the app | DeepSeek decisions 0.6 s, 2.0 s · Bonsai 9.5 s · Gemini not streamed | DF `SESSION_HANDOFF.md:190-191` (`88ad229`); `d5_after3.json` | 2026-10-07 | yes | reuse | — |
| P4 | Per-call duration, prompt and output tokens, role, thinking level | 176 captured calls (Gemini 61, IndieRouter 75, Bonsai 40); duration = capture file mtime − call start | `/root/.legalmind/rag-ground/captures/*` → `calls.json` | 2026-10-07 00:20–17:51 | **yes** for provider behaviour; **contaminated** for any per-turn sum where two drivers ran concurrently (negative non-model time: `gemini-after` T4/T7, `deepseek-after` T1/T2 — excluded) | reuse (mined) | — |
| P5 | Turn totals per run | 31 run files, per turn `ms` + its captures | `/root/.legalmind/rag-ground/runs/*.json` | 2026-10-07 | yes (except the contaminated rows above) | reuse | E6 live, single vs 17-point |
| P6 | DeepSeek reasoning levels | default: a decision spent all 2,048 tokens thinking; "done" decision 400–1,500 tokens of discarded prose; LOW answer > 23 s vs none 15 s | `SESSION_HANDOFF.md:104` (this file, RG #7), `agent.py:445-450` comment, captures (`thinking=None` 14 decisions p50 9,835 ms / 1,247 out; `MINIMAL` 26 decisions p50 5,086 ms / 405 out) | 2026-10-07 | yes for timing; **partial** — reasoning-token counts never captured | reuse + **run the missing part** (one default call, usage exposed) | the app drops `completion_tokens_details` |
| P7 | Bonsai throughput and gateway | ~700 prompt and ~18–26 output tokens/s; 50 s silence cut; thinking on unless `enable_thinking=false` | `SESSION_HANDOFF.md:258`, `model_router.py:58-62`, `agent.py:56-60` | 2026-10-07 | yes; **partial** — thinking-on cost never quantified | reuse + run thinking-on once | — |
| P8 | Verifier batching | DeepSeek T7 75 → 42.8 s; 118 → 20 NLI calls; ~24 s NLI over 530 pairs (~45 ms a pair, 6 CPUs) | `SESSION_HANDOFF.md:105,189-191` | 2026-10-07 | yes | reuse | — |
| P9 | Gemini implicit cache on agent calls | 32.7k–34.9k of ~35k input tokens cached on decisions and repair; first schema-mode call missed | `agent.py:1009-1013` comment; `STATUS.md:150` | 2026-10-05 | yes; app still drops `cachedContentTokenCount` | reuse; raw calls add a fresh check | — |
| P10 | Per-tool latency (77 questions) | p50/p95 ms: search_knowledge 31.2/43.3 · get_company_position 7.1/9.4 · search_statutes 184.4/218.4 · get_evidence 2.0/2.3 · list_attachments 0.7/0.8 · search_attachment 6.4/8.0 | `EVALS.md:32` (#28) | 2026-10-01 | **stale** — before the cross-encoder joined `search_knowledge` (A-39) and before whole-document reading (A-77): today one search_knowledge = 1,066–1,893 ms | **re-run** (zero-model profiler) | changed code path |
| P11 | Agent stage p50/p95 (Phase 3 run 2) | decision 1.6/4.3 s · final 3.3/4.6 s · tools 27/43 ms · context 1/5 ms; prompt p50/p95 3,032/4,908 tokens | `EVALS.md:40` (#36) | 2026-10-03 | **stale** (prompt now 34–61k tokens) | re-run | changed context |
| P12 | Scratch answer latencies (all prior runs) | Bonsai 11 · DeepSeek 26 · Gemini 17 rows (raw lists in §2) | `legalmind_rag_ground.assist.ai_answers` | snapshot 2026-10-07 ~18:45 | yes (distribution of the reported complaint) | reuse | — |
| P13 | Production per-call latency | `assist.generation.completed` per call; 8 asks since the 15:23 IST deploy (all DeepSeek), 4 Gemini asks before | `journalctl -u legalmind-api` (read-only, ids/counts only) | 2026-10-06 → 2026-10-07 13:11 UTC | yes | reuse | only source of real-user numbers |
| P14 | Phase A breakdown (embed, search, rerank, fetch, assemble, SQL) | none | — | — | — | **run** | never measured |
| P15 | Gemini TTFT, cached/thought tokens; DeepSeek/Bonsai cached and reasoning tokens; cold vs warm (E7); raw provider vs app (E8); bare prompt (E1); Gemini default thinking (E4) | none | — | — | — | **run** (16 calls) | not exposed by the app |
| P16 | ui_paint_ms, post-answer persistence, cold model loads, network/TLS per host | none | — | — | — | **run** (zero model calls) | never measured |

### 2. Raw measurements — phase × model

All values in ms unless a unit is given. "Fresh" = this session; "reused" names its source (§1 id).
App-turn numbers are T4 unless stated.

**Phase A — RAG layer (fresh, zero-model profiler on `main`; reps listed in run order).**

| Metric | Gemini path (whole document) | DeepSeek path (whole document) | Bonsai path (lean: ranked document) |
|---|---|---|---|
| embed_ms (calls) | 72.3, 55.4, 55.3 (10) | 23.5, 24.0, 26.9 (5) | 40.5, 34.2, 37.2, 33.2, 41.7, 34.8 (7) |
| cache_lookup_ms | 0 — no attachment or evidence cache exists on the path (`tools.search_knowledge`, `tools.py:443-569`) | 0 | 0 |
| search_ms (`retrieval._search` jobs) | 1,022.2, 934.3, 1,043.3 (10 jobs) | 425.4, 429.7, 379.3 (5) | 480.0, 427.0, 450.2, 442.8, 459.6, 440.4 (7) |
| rerank_ms (pairs) | 1,996.2, 1,803.5, 1,860.0 (60) | 877.7, 788.0, 804.6 (30) | 1,379.6, 1,267.6, 1,341.4, 1,280.7, 1,313.2, 1,275.0 (60) |
| fetch_ms | whole_document 17.9, 14.6, 17.2 · chunks_by_id 7.0, 5.6, 6.8 · section_headings 5.9, 5.0, 5.7 · constitution.expand ×10 8.1, 8.1, 7.8 · statute read ×10 4.0, 3.7, 3.4 | whole_document 7.1, 8.5, 7.2 · constitution.expand ×5 4.0, 3.9, 4.0 · statute read ×5 1.8, 1.7, 1.7 | clause_text ×5 8.1, 7.7, 7.4, 7.9, 7.8, 8.5 · constitution.expand ×5 3.7–4.1 · statute read ×5 1.7–2.1 |
| assemble_ms (`_context` + `_present`) | 1.1+2.2, 1.2+2.4, 1.1+2.2 | 1.2+1.2, 1.1+1.1, 1.1+1.2 | 0.8+0.2, 0.7+0.2, 0.7+0.2, 0.8+0.3, 1.1+0.2, 0.7+0.2 |
| thread + material read | 0.9+0.4, 1.0+0.4, 1.0+0.5 | 1.4+0.5, 0.9+0.4, 1.1+0.5 | 0.9–2.4 + 0.4–1.2 |
| `context` stage (seed search + all of the above) | 1,323, 1,235, 1,275 | 1,338, 1,253, 1,218 | 1,897, 1,730, 1,827, 1,770, 1,811, 1,752 |
| model-chosen search stage (`tools_1`) | 1,800, 1,601, 1,730 (one search_knowledge) | — (the replayed run asked none) | — (lean: no decision step) |
| SQL statements / SQL ms per turn | 91 / 992.7, 919.2, 1,025.5 | 52 / 409.3, 412.5, 360.3 | 111–113 / 434.8, 388.8, 408.7, 409.9, 419.2, 407.3 |
| retrieval_calls_count | 2 tool searches = 10 SQL search jobs | 1 = 5 jobs | 1 = 7 jobs (documents + statutes reranked) |
| retrieval_mode | **serial** — jobs `retrieval.py:272`, a step's tools `agent.py:1048` | serial | serial |
| prompt_tokens (live, fresh chat, per call: P1) | 34,167 · 34,990 · 34,935 · 36,390 | 33,800 · 40,170 | 9,357 |
| attachment / document / evidence / history / system / user tokens (in-chat T4 answer call, char share × provider total — the provider reports the total only) | material 0 · document 25,770 · evidence 6,055 · thread 1,488 + pinned evidence 9,370 · system 3,184 · user 16 (instructions 651, JSON envelope 2,434, schema 171; total 49,142) | material 1,244 · document 22,601 · evidence 4,602 · thread 3,467 + pinned 7,911 · system 3,053 · user 15 (instructions 624, envelope 341, schema 164; total 44,026) | material 1,216 · document 774 · evidence 4,679 · thread 2,108 + pinned 3,615 · system 2,985 · user 12 (instructions 575, envelope 380, schema 160; total 16,509, T6) |
| characters per token | 3.95–3.99 | 4.11–4.14 | 4.23 |
| truncation_happened | no on T4: document 68,444 < 240,000 (`tools.py:312`); thread under 6 messages/12,000 chars (`agent.py:69-70`); material under 120,000 (`agent.py:68`) | no | yes by design: lean material cap 24,000 chars (`agent.py:63`) and a ranked, not whole, document (`agent.py:977-978`) |
| attachment_re_embedded | **no** — material embedded once at add (`attachments.py:260`), documents at ingestion; the per-turn embeddings are the QUERY only | no | no |

17-point turn (T7) Phase A, fresh, Gemini replay:
- context 805 / 825 / 803; model searches serial 3,938 / 3,770 / 3,680;
- 4 tool searches = 18 jobs: embed 102.8 / 94.5 / 82.0, search 978.0 / 978.4 / 936.9, rerank (120 pairs) 3,591.2 / 3,447.0 / 3,381.8;
- SQL 159 statements, 953.5 / 957.2 / 931.6 ms;
- paste saved as material (chunk + embed, once): 374.7, 87.5, 96.2 ms. On `main` in production the paste is refused before any of this (`LEGALMIND_ASK_ATTACHMENTS` unset; `api/routers/assist.py:699-704`).

DeepSeek replay of T7:
- 6 tool executions, 19 jobs; seed 807.4 / 1,805.0 / 1,773.2, four model searches 57.8–131.5 each;
- this run's load average was 5.59–5.9, so its rerank 590.1 / 1,573.8 / 1,539.5 carries CPU contention.

T1 (no document) Phase A:
- context 1,163 / 1,165 / 1,112; embed 34.6 / 29.4 / 35.1 (6); search 265.7 / 224.3 / 240.1 (5 jobs);
- rerank 865.4 / 911.9 / 848.2 (30 pairs); SQL 48–49 statements, 241.4 / 214.2 / 213.5.

**Phase B — LLM layer.** Raw streamed calls are fresh. Their prompt is the repo's `SYSTEM_CONTRACT` + `ANSWER_SCHEMA` + public statute text, sized like the T4 answer call: Gemini 35,661, DeepSeek 33,912, Bonsai 10,111 prompt tokens. Calls are listed in run order: 1st (cold), 2nd, 3rd.

| Metric | Gemini `gemini-3.6-flash` | DeepSeek `deepseek-v4.1-flash` (IndieRouter) | Bonsai `bonsai-2-27b` (company endpoint) |
|---|---|---|---|
| ttft_ms (answer call) | 2,682 · 2,049 · 2,339 (LOW) · MINIMAL 2,071 | 2,030 · 566 · 644 (reasoning none) | 11,461 · 721 · 698 (thinking off) |
| ttft inside the app (reused P3) | not streamed: first token = call latency (2,341–6,350 per call, P1) | decisions 600, 2,000 | 9,500 |
| prefill_ms | **NOT EXPOSED**. Proxy: `Server-Timing gfet4t7` 2,649 · 2,020 · 2,327 (= TTFT). TTFT does not grow with prompt: 3,425 tokens gave first event 2,840 | **NOT EXPOSED**. Derived: (2,030 − 605) / 31,352 uncached = 0.0454 ms/token | **NOT EXPOSED**. `Server-Timing cfOrigin` 11,415 · 680 · 612. Derived: (11,461 − 709.5) / 7,300 uncached = 1.4728 ms/token (679 tok/s) |
| generation_ms after first token (output tokens) | 2,867 (511) · 2,877 (494) · 2,847 (488) · MINIMAL 3,519 (633) — 5.56–5.83 ms/token | 7,992 (1,349) · 7,532 (1,259) · 6,172 (1,111) — 5.56–5.98 ms/token | 15,378 (409) · 15,478 (409) · 15,394 (409) — 37.60–37.84 ms/token; bare 38,162 (918) — 41.57 ms/token |
| cached prompt tokens | 0 · 0 · 33,635 (`cachedContentTokenCount`) | 2,560 · 33,536 · 33,536 | 2,811 · 10,107 · 10,107 |
| reasoning_tokens | LOW on this prompt: none reported; LOW on the bare prompt: 858; **default: 2,169** | none: 0; **default: 3,701 of the 4,096 cap** | off: 0; **on: 3,971 of 4,096, no answer text at all** |
| reasoning_level in the app | decisions MINIMAL, answer and repair LOW (`agent.py:445,478`) | `reasoning_effort: "none"` on every call (`agent.py:501` → `generation.py:941`) | `enable_thinking: false` (`model_router.py:61`); `reasoning_effort: none` sent and ignored |
| model_name served | `gemini-3.6-flash` (`modelVersion`) | `deepseek-v4.1-flash` | `bonsai-2-27b` |
| provider_region | **NOT EXPOSED**. Google front end 172.217.112–119.x; ping 1.135/1.244/1.442 ms; TLS done 27.6–28.4 ms | **NOT EXPOSED**. One IP 165.140.164.102 (`Server: nginx`); TCP 13.6–19.4 ms after DNS; TLS done 50.5–53.0 ms | Cloudflare edge Mumbai (`cf-ray …-BOM`); origin **NOT EXPOSED**; TLS done 23.3–27.3 ms warm, 171.2 ms with the first DNS lookup (140.6 ms) |
| http_status | raw 6/6 = 200 | raw 5/5 = 200; production 19 completed + 1 `TimeoutError` (P13) | raw 5/5 = 200 |
| retries_count | 0 raw; app: one retry only on HTTP 429/500/503 with 2.0 s wait and ≥ 4 s left (`agent.py:440-463`); none seen in P1/P2/P13 | 0 | 0 |
| queue_wait_ms | **NOT EXPOSED** | **NOT EXPOSED** | **NOT EXPOSED** |
| cold_start | provider: none seen (cold 2,682 vs warm 2,049–2,339) | provider prefix cache: +1,386 to +1,464 TTFT cold | provider prefix cache: +10,740 to +10,763 TTFT cold |

App process cold start (fresh, first use in a new process):
- Two fresh processes: import 356.4 / 254.7; embedding load + first query 386.7 / 385.9; reranker 255.5 / 266.2; NLI verifier 1,955.4 / 1,895.6.
- Only the embedding model is warmed at startup (`api/app.py:58-86,111`). The first Ask after every restart or deploy therefore pays 2,161.8–2,210.9 more.

Within the LLM layer, per app call (P1, `main`-equivalent T4):

| Model | Calls (latency ms / prompt / output tokens) |
|---|---|
| Gemini | decision 2,341 / 34,167 / 30 · decision 5,633 / 34,990 / **650** · final 6,350 / 34,935 / 744 · repair 5,610 / 36,390 / 846 |
| DeepSeek | decision 4,988 / 33,800 / 254 · decision **11,181** / 40,170 / **754** (prose the loop discards) · final timed out after 19,605 → floor |
| Bonsai | final 66,321 / 9,357 / 1,353 |

Fit over the 176 captured calls (P4): duration = fixed + per prompt token + per output token.

| Model | Fixed | Per prompt token | Per output token | R² |
|---|---|---|---|---|
| Gemini | 2,125.1 | 0.00603 | 4.182 | 0.966 |
| DeepSeek | 1,303.1 | 0.03745 | 5.193 | 0.961 |
| Bonsai | — | — | — | 0.569 (unusable: streamed and cache-dependent; the raw calls above replace it) |

**Phase C — post-LLM.**

| Metric | Gemini | DeepSeek | Bonsai |
|---|---|---|---|
| verify_ms, live app (P1/P2, `verify` timer; `settle` separately) | 3,800 + 740 · 9,310 + 850 · 3,230 + 450 | 10,400 + 1,200 · 9,470 + 1,920 · 14,550 + 1,900 | 2,160 + 230 · 930 + 110 · 1,270 + 70 · 420 + 50 |
| verify_ms, fresh replay (NLI pairs, memo cleared each rep) | T4 2,939.6 · 2,729.8 · 2,852.1 (136); T1 197.2 · 205.8 · 201.7 (16); T7 4,459.8 · 4,871.1 · 4,330.1 (277) | T4 3,131.2 · 2,758.1 · 2,807.5 (224); T7 3,917.2 · 5,387.0 · 5,981.5 (236) | T4 132.6–165.3 (16) |
| citation_render_ms (`source_views`) | 0.9 · 1.1 · 1.2 | 1.0 · 1.0 · 1.0 | not run (same code) |
| after the agent, before the HTTP reply (persist + audit + sources + render) | 213.2 · 169.0 · 174.3, of which `registry.persist` 175.1 · 159.5 · 165.3 (one ledger insert per shown record, ~171) | 172.5 · 169.0 · 178.5 (persist 164.0 · 160.0 · 169.9) | — |
| ui_paint_ms (fresh, Chromium, mocked API, 3,500-character answer + 10 sources) | response parsed → DOM 10.9 · 10.7 · 12.0 · 13.2 · 12.5; → painted 150.3 (first) · 29.5 · 32.6 · 35.1 · 36.2 | same client | same client |
| total_ms (P1 / P2) | 27,035 · 38,508 · 25,940 | 41,235 (floor) · 41,459 · 42,328 · 42,084 | 70,481 · 110,382 · 87,297 · 45,545 |

The complaint, reproduced (P12, all prior scratch answers, server-side ms):
- Gemini: 11,846, 12,753, 14,815, 16,436, 18,294, 18,386, 19,648, 21,839, 23,305, 25,462, 25,958, 27,579, 27,847, 28,817, 35,759, 44,875, 45,387.
- DeepSeek: 27,485, 28,112, 28,158, 28,159, 33,211, 35,357, 36,991, 37,998, 39,327, 40,067, 40,089, 40,116, 40,118, 40,125, 40,128, 40,456, 41,127, 41,286, 41,478, 41,819, 42,200, 42,729, 46,033, 47,961, 75,045, 80,655.
- Bonsai: 48,184, 54,880, 58,600, 65,162, 69,995, 73,996, 78,346, 103,427, 110,081, 110,163, 110,172.

Production (P13), server ms per POST `/messages`, with the sum of completed model calls in brackets:
- since the deploy, all DeepSeek: 8,509.46 [7,171] · 26,252.69 [20,310] · 23,714.99 [17,940] · 36,114.97 [30,842] · 42,766.65 [25,302 + one `TimeoutError`] · 25,891.54 [18,330];
- two fixed replies: 33.26 and 25.17 ms;
- before it, Gemini (`ask-agent-17/18`): 17,440.36 [14,549] · 9,382.57 [8,690] · 21,751.77 [20,269] · 14,142.82 [9,552].

### 3. Experiments E1–E10

| Exp | Model | Result (raw ms) | Source | Notes |
|---|---|---|---|---|
| E1 no attachment, no evidence | Gemini | raw bare prompt (3,425 tokens): first event 2,840, first content 6,160, total 8,135, 432 out + 858 thought | fresh | the app has no evidence-free path; nearest app turn: T1 (evidence, no document) 12,792, 3 calls Σ 9,343 (P5 `gemini-before`) and Phase A 1,120.7–1,384.3 |
| E1 | DeepSeek | ttft 565, total 4,869, 685 out | fresh | app T1 37,023 is pre-fix (P5, stale) |
| E1 | Bonsai | ttft 2,497, total 40,659, 918 out | fresh | app T1 pre-fix timed out at 28,063 (P5, stale) |
| E2 attachment only | all | **NOT RUN live**: the app always searches evidence with the document | — | isolated arithmetically: document 22,601–25,878 tokens of 44,026–49,197 per call (52–53 %); at the fitted 0.00603 (Gemini) / 0.0454 (DeepSeek cold) ms per token that is ~156 / ~1,026 ms per call; Bonsai does not read it whole |
| E3 attachment + evidence | Gemini | 27,035 (RAG 3,290 · LLM 19,934 · post 3,811); 25,940; 38,508 | reused P1/P2 | Phase A/C breakdown fresh (§2) |
| E3 | DeepSeek | 41,235 floor; answered 41,459 · 42,328 · 42,084 | reused P1/P2 | production 8,509–42,767 (P13) |
| E3 | Bonsai | 70,481 · 110,382 · 87,297 · 45,545 | reused P1/P2 | — |
| E4 reasoning default | Gemini | ttft 12,553, total 14,277, 403 out, 2,169 thought tokens | fresh | LOW same prompt: 4,927–5,550 |
| E4 | DeepSeek | first event 2,508, content ttft 25,805, total 27,947, 3,701 reasoning of 4,096 (answer cut at the cap) | fresh (+ P6 timings reused) | — |
| E4 | Bonsai | first (reasoning) event 14,512, **no content**, total 171,071, 3,971 reasoning of 4,096 | fresh | beyond the app's 110 s lean budget and the client's 150 s |
| E5 reasoning low/off | Gemini | LOW 5,550 · 4,927 · 5,186; MINIMAL 5,590 | fresh | no thought tokens at LOW on this prompt |
| E5 | DeepSeek | none: 10,022 · 8,099 · 6,816; LOW answer > 23 s vs none 15 s (P6) | fresh + reused | — |
| E5 | Bonsai | off: 26,840 · 16,199 · 16,092 | fresh | — |
| E6 single vs 17-point | Gemini | T4 28,035 (4 calls) vs T7 35,927 (4 calls) | reused P5 `gemini-before` | replay: RAG T4 1,235–1,323 + 1,601–1,800 vs T7 803–825 + 3,680–3,938; verify T4 2,729.8–2,939.6 vs T7 4,330.1–4,871.1; DF D1 per-point build 45 s (DF `SESSION_HANDOFF.md:88`) |
| E6 | DeepSeek | T4 27,514 (3 calls) vs T7 42,763 (4 calls) | reused P5 `deepseek-after3` | DF D1: 81 s |
| E6 | Bonsai | T7 floor at 111,494–111,729 (timeouts) | reused P5 `d2-bonsai-T7*` | DF D1: 112 s, 0 points answered |
| E7 cold vs 3rd call | Gemini | ttft 2,682 → 2,049 → 2,339; total 5,550 → 4,927 → 5,186 | fresh | the cache hit (33,635) does not move Gemini TTFT |
| E7 | DeepSeek | ttft 2,030 → 566 → 644; total 10,022 → 8,099 → 6,816 | fresh | prefix cache −1,386 to −1,464 TTFT |
| E7 | Bonsai | ttft 11,461 → 721 → 698; total 26,840 → 16,199 → 16,092 | fresh (+ P4: identical prompt twice 56,298 / 56,902) | prefix cache −10,740 to −10,763 TTFT |
| E8 raw provider vs app | Gemini | one answer-sized call 4,927–5,550 vs app turn 25,940–38,508 | fresh vs P1/P2 | the app makes 4–5 calls + RAG + verify |
| E8 | DeepSeek | 6,816–10,022 vs 41,459–42,328 | fresh vs P2 | the app answer runs 2,030–2,238 tokens vs 1,111–1,349 raw |
| E8 | Bonsai | 16,092–26,840 (409 out) vs 45,545–110,382 (896–1,353 out) | fresh vs P1/P2 | output length dominates |
| E9 paste vs upload | all | paste saved as material: 374.7, 87.5, 96.2 (fresh); upload ATTACH 3,711 / 3,878 / 3,714 (P5); per turn the paste is inline material, the upload a whole document | fresh + reused | **on `main` in production a paste over 2,000 chars is refused** (`assist.py:704`); DF D3 changes that |
| E10 long vs short output | all | ms per output token: Gemini 5.56–5.83 (raw), fit 4.182; DeepSeek 5.56–5.98 (raw), fit 5.193; Bonsai 37.60–41.57 (raw) | fresh + reused P4 | e.g. 1,000 extra output tokens = +5.6 s Gemini/DeepSeek, +37.6 s Bonsai |

### 4. Layer attribution (RAG = context + tools stages; LLM = model calls + waits on failed calls; post = the rest)

| Run | Model | Total | RAG | LLM | Post |
|---|---|---|---|---|---|
| P1 `main`-equivalent | Gemini | 27,035 | 3,290 (12.2 %) | 19,934 (73.7 %) | 3,811 (14.1 %) |
| P2 | Gemini | 25,940 | 3,412 (13.2 %) | 19,282 (74.3 %) | 3,246 (12.5 %) |
| P2 | Gemini | 38,508 | 4,613 (12.0 %) | 24,572 (63.8 %) | 9,323 (24.2 %) |
| P1 `main`-equivalent | DeepSeek | 41,235 floor | 4,351 (10.6 %) | 35,774 (86.8 %), of which 19,605 a timed-out final | 1,110 (2.7 %) |
| P2 | DeepSeek | 41,459 | 3,029 (7.3 %) | 28,009 (67.6 %), incl. 3,147 timed-out repair | 10,421 (25.1 %) |
| P2 | DeepSeek | 42,328 | 4,695 (11.1 %) | 28,140 (66.5 %), incl. 4,612 | 9,493 (22.4 %) |
| P2 | DeepSeek | 42,084 | 4,533 (10.8 %) | 22,985 (54.6 %), incl. 5,043 | 14,566 (34.6 %) |
| P13 production (calls vs the rest; RAG/post not separable from logs) | DeepSeek | 8,509 · 26,253 · 23,715 · 36,115 · 42,767 · 25,892 | — | 84.3 · 77.4 · 75.6 · 85.4 · 59.2 · 70.8 % | 15.7 · 22.6 · 24.4 · 14.6 · 40.8 · 29.2 % (RAG + post + failed waits) |
| P1 `main`-equivalent | Bonsai | 70,481 | 1,998 (2.8 %) | 66,321 (94.1 %) | 2,162 (3.1 %) |
| P2 | Bonsai | 45,545 | 1,896 (4.2 %) | 43,228 (94.9 %) | 421 (0.9 %) |
| P2 | Bonsai | 87,297 | 1,879 (2.2 %) | 84,145 (96.4 %) | 1,273 (1.5 %) |
| P2 | Bonsai | 110,382 | 1,793 (1.6 %) | 107,657 (97.5 %), incl. 56,293 timed-out repair | 932 (0.8 %) |

### 5. Per-model bottleneck

- **Gemini — 12–13 % RAG, 64–74 % LLM, 13–24 % post; dominant: the number of sequential model calls.**
  - Every call pays a first-token latency of 2,049–2,682 ms whatever its size or cache. A turn makes 4–5 calls, so 8,196–10,728 ms of every turn is first-token wait alone.
  - A "done" decision writing 650 discarded tokens cost 5,633, and the repair cost 5,198–6,565.
- **DeepSeek — 7–11 % RAG, 55–68 % LLM (87 % on the floor run), 22–35 % post; dominant: output length, then verification of it.**
  - The answer writes 2,030–2,238 tokens in 13,969–18,253 ms, and verifying that many claims takes 9,470–14,550.
  - On `main` add a decision step's discarded prose (11,181 ms for 754 tokens) and timed-out repair waits (3,147–5,043).
- **Bonsai — 2–4 % RAG, 94–97 % LLM, 1–3 % post; dominant: output throughput.**
  - It streams 24.1–26.6 tokens/s, so a 896–1,353-token answer is 33.7–50.9 s.
  - Add the cold prefill of every uncached token at 1.4728 ms/token: 9,500 measured in the app, 11,461 raw.
- **The bottleneck differs by model.** RAG is never the dominant layer (2–13 %). Its biggest piece is the CPU cross-encoder: 26–30 ms a pair, 30–120 pairs a turn.

### 6. Levers that can reduce latency (measurement → verdict; nothing implemented)

| # | Lever | Layer | Current cost (ms) | Reducible? | Expected saving (ms) | Risk to grounding | Effort | Priority | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Attachment embedding cache | RAG | 0 per turn (embedded once, `attachments.py:260`); query embeds 15.6–103.1 per turn | no (≤ 103) | ≤ 103 | none | small | none | **RULED OUT** |
| 2 | Evidence retrieval cache | RAG | seed 1,066–1,893 + model searches 57.8–1,799.2 each | only on identical (query, scope) repeats; hit rate unmeasured | not supported by any measurement | low | medium | low | **NOT SUPPORTED** |
| 3 | Chunking / whole-document read | RAG + LLM | 22,601–25,878 document tokens per call; whole_document fetch 7.1–19.5 | yes, ranked instead of whole | ~156/call Gemini (fit), ~1,026/call DeepSeek cold, ~0 warm | **high** (A-77: ranking lost the second clause; D4 headings 25/57 ranked) | small | none | **RULED OUT** (gain small, risk high) |
| 4 | Retrieval parallelization | RAG | a step's searches serial: T7 3,935.8 / 3,768.1 / 3,677.8 for 3 searches; SQL jobs serial 224.3–1,043.3 | yes | 2,485.2 / 2,468.4 / 2,432.5 on multi-search steps (max single search kept); 0 on one-search steps; DF measured 5.5 → 2.8 s | none (same results) | done on DF `88ad229` | high | **SUPPORTED** (CPU-bound rerank may contend on 6 vCPUs) |
| 5 | Hybrid search | RAG | already hybrid; jobs 224.3–1,043.3 incl. SQL | no measured gain from changing | — | — | — | none | **RULED OUT** |
| 6 | Reranker | RAG | 26–30 ms/pair: 788.0–911.9 per 30 pairs; turns 810.1–3,591.2 | yes (depth 30 → 15, quantized ONNX) | 394–456 per reranked 30 pairs (half of 788.0–911.9); T4 Gemini 902–998, T7 Gemini 1,691–1,796, Bonsai lean 634–690 | medium (`AM-87` measured evidence recall 0.705 → 0.756 from rerank; re-measure with the zero-Gemini probe) | small | medium | **SUPPORTED** |
| 7 | Top-k size | RAG + LLM | evidence 3,928–6,080 tokens T4, 13,359–17,966 T7 | Gemini/DeepSeek ~0 (cached); Bonsai yes | Bonsai ~1,473 per 1,000 uncached tokens (cold) | medium (recall) | small | low (Bonsai only) | **SUPPORTED for Bonsai only** |
| 8 | Prompt compression | LLM | system 2,965–3,205 + envelope 341–7,546 + instructions 571–1,596 tokens per call | Gemini/DeepSeek ~0 (cached); Bonsai cold yes | Bonsai ≤ ~560 (380-token envelope) | low | medium | low | **RULED OUT** except a Bonsai margin |
| 9 | Streaming to UI | Post (perceived) | the reader waits the total: 25,940–110,382 | perceived only; provider first token 566–2,682 (Gemini/DeepSeek), 698–11,461 (Bonsai) | perceived wait → first token | **high** — unverified text on screen; forbidden by `AM-25` r5 / `AM-69` | — | owner decision | **BLOCKED BY LOCK** (DF blocker 1) |
| 10 | Model routing | LLM | Bonsai 37.60–41.57 ms/token vs 5.56–5.98 (Gemini/DeepSeek) | only with the reader's choice (`AM-116`: no silent fallback) | 896-token answer: ~33.7 s Bonsai vs ~5.0–5.2 s Gemini | none | UI / owner | owner decision | **SUPPORTED as disclosure, not routing** |
| 11 | Reasoning level per model | LLM | already minimal | no further gain measured | defaults would ADD +9,871 to +10,504 (Gemini), +23,775 to +25,239 (DeepSeek), no answer in 171,071 (Bonsai) | — | — | keep | **ALREADY OPTIMAL — keep** |
| 12 | Output token cap / brevity | LLM + Post | DeepSeek finals 2,030–2,238 tokens = 13,969–18,253; Bonsai 896–1,353 = 43,228–66,321; Gemini 744–870 = 6,350–6,787 | yes | Bonsai cap 600 → 11,130–28,313; DeepSeek cap 1,200 → 4,611–6,210 generation (830–1,038 tokens × 5.555–5.983 ms; verify saving NOT MEASURED) | medium (completeness: D1 needs every point) | small + measurement | high | **SUPPORTED** |
| 13 | Provider region / warm pool | LLM | network per call 57–93 total, TLS 23–53; a new TLS connection per call (no keep-alive) | region no; keep-alive small | 69–265 per turn (23–53 × 3–5 calls) | none | small | low | **RULED OUT** as region |
| 14 | System prompt size | LLM | 2,965–3,205 tokens, cached on all three (2,560 / 2,811 / 33,635 cached) | no | ~0 | — | — | none | **RULED OUT** |
| 15 | History window and prompt order | LLM | thread 1,476–3,491 + pinned 3,615–9,409 tokens sit BEFORE the document and the seed (`agent.py:796-816`), so the turn-specific part precedes the 25k-token document and the cross-turn cache stops at the system prompt | yes (stable-first order) | DeepSeek ≤ 1,386–1,464 TTFT per turn; Bonsai ~4,896 (3,324 stable tokens × 1.4728) | low for grounding (same content); medium for behaviour (B4 fixed order) — re-measure | small | medium | **SUPPORTED** |
| 16 | Duplicate context | LLM | within a call: 0 ids re-sent; identical text under 2+ ids 0–3,627 chars (≤ 1.7 %) | no | ≤ ~0.2 % of prefill | none | — | none | **RULED OUT** |
| 17 | Post-LLM verification | Post | live 420–14,550 (+ settle 50–1,920); NLI 15–46 ms/pair; first-request NLI load 1,955.4 + rerank 255.5 | yes | warm models at startup: 2,161.8–2,210.9 on the first Ask per process; faster NLI: if ms/pair halves, 4,735–7,275 DeepSeek, 1,615–4,655 Gemini (assumption, to be measured with `tools.eval_verification`) | warm-up none; NLI change high (`AM-90` model change, false-accept rate) | tiny / medium | high / medium | **SUPPORTED** |
| 18 | Per-call first-token × call count (Gemini) | LLM | 2,049–2,682 per call × 4–5 calls | yes (fewer calls) | a discarded-prose decision: 5,634 → 2,433–2,812 (cut) = 2,822–3,201; d5 after2 4,488 → 1,676–2,055 | low | medium (Gemini streaming in `_send`) | medium | **SUPPORTED** |
| 19 | Timed-out repair waits | LLM | DeepSeek 3,147 / 4,612 / 5,043; Bonsai 56,293; production 1 of 6 DeepSeek turns | yes (start a repair only with time to finish) | the full wait | none | done on DF `88ad229` | high | **SUPPORTED** |
| 20 | DeepSeek discarded decision prose | LLM | 11,181 for 754 tokens (P1) | yes | 7,628–8,575 (DF measured: → 2,606–3,553) | none | done on DF `88ad229` | high | **SUPPORTED** |
| 21 | Ledger persist N+1 | Post | 159.5–175.1 (~171 single-row upserts, `agent.py:597`) | yes (one batch) | ~150 | none | small | low | **SUPPORTED** |
| 22 | SQL round-trips in retrieval | RAG | 48–159 statements, 213.5–1,025.5 per turn | partly | ≤ ~500 (parallel/merged jobs) | none | medium | low | **SUPPORTED, small** |
| 23 | Rescue judge (an extra Gemini call before the main call) | LLM | 1,519–1,877, 2,034 prompt / 1 output (P4, 4 calls); fires only when a ranked document's gate shuts (lean Bonsai, DF D1) | yes | ~1.5–1.9 s on those turns | medium (it reopens a shut gate) | small | low | **SUPPORTED, conditional** |

### 7. Ranked fix list (saving ÷ risk; risk weight none = 1, low = 2, medium = 4, high = 8; nothing implemented)

| Rank | Fix | Layer | Expected total saving (ms per affected turn) | Risk to grounding | Effort | Model(s) |
|---|---|---|---|---|---|---|
| 1 | Merge DF D5: cut a finished decision's prose + start a repair only with time to finish (`88ad229`) | LLM | 7,628–8,575 + 3,147–5,043 = 10,775–13,618 (DeepSeek); Bonsai a 56,293 wait avoided | low | done; needs owner review and merge | DeepSeek, Bonsai, all for repairs |
| 2 | Brevity contract / output cap for Bonsai | LLM | 11,130–28,313 | medium (completeness) | small + one live measurement | Bonsai |
| 3 | Parallel searches within a step (DF `88ad229`) | RAG | 2,432.5–2,485.2 on multi-search steps | none | done; merge | all (agent path) |
| 4 | Warm the NLI verifier and reranker at startup (beside the embedding warm-up, `app.py:58-86`) | Post/RAG | 2,161.8–2,210.9 on the first Ask after each restart | none | tiny | all |
| 5 | Brevity contract / output cap for DeepSeek | LLM (+ post) | 4,611–6,210 generation; verify saving not measured | medium | small + measurement | DeepSeek |
| 6 | Streamed Gemini decision with the same prose cut | LLM | 1,676–3,201 on turns whose done-step writes prose | low | medium | Gemini |
| 7 | Stable-first prompt order (system → material → document → thread → pinned → seed → message) | LLM | DeepSeek ≤ 1,386–1,464; Bonsai ~4,896 | low (order only) — behaviour must be re-measured | small | DeepSeek, Bonsai |
| 8 | Faster NLI (quantized/smaller) or fewer stage-2 pairs | Post | if ms/pair halves: 4,735–7,275 DeepSeek, 1,615–4,655 Gemini | high (`AM-90`; false accepts) | medium | all |
| 9 | Reranker depth 30 → 15 (re-measure recall with the zero-Gemini probe first) | RAG | 634–1,796 per turn | medium | small | all |
| 10 | Batch the ledger persist; merge or parallelise the retrieval SQL; keep-alive to providers | Post / RAG / LLM | ~150 + ≤ ~500 + 69–265 | none | small–medium | all |
| — | **Owner decisions, not ranked:** (a) stream to the reader — `AM-25` r5 / `AM-69` forbid it; (b) tell the reader what Bonsai costs (~26 tokens/s, 45–110 s) at the picker — no silent routing (`AM-116`); (c) skip the repair when settle can drop the failing blocks (Gemini repair 5,198–6,565) — a completeness trade | — | (a) perceived only · (b) 30–60 s per switched turn · (c) 5,198–6,565 | (a) high · (b) none · (c) medium | — | — |

**Code questions — answered (file:line on `0aee166`).**
1. **Prompt re-assembled each turn, or cached?** Re-assembled on every turn from the database (`agent.py:1014`, the "Built ONCE per turn" comment at `:1009`). Within a turn every call re-sends the whole growing context. The providers cache the prefix themselves, measured in §2. No local cache exists.
2. **Attachment re-embedded each turn?** No. It is embedded once at add (`attachments.py:230-260`), and documents at ingestion. Only the query is embedded per search: 5–20 times a turn (§2).
3. **Serial or parallel retrieval?** Serial. Within a search: `retrieval.py:272`. Within a decision step: `agent.py:1048`.
4. **How many retrieval calls for the 17-point e-mail?**
   - On `main` in production: **0**. The paste is refused at 2,000 characters (`assist.py:701-704`) because attachments are off.
   - With attachments on, Gemini's replay ran 1 seed + 3 model searches = 4 tool searches = 18 SQL search jobs, 18 query embeddings and 4 rerank calls (120 pairs). DeepSeek's ran 1 seed + 1 `get_company_position` + 4 searches = 19 jobs. The cap is `MAX_TOOL_EXECS` 8 (`agent.py:52`, `tools.MAX_K`).
   - DF D1 adds 17 per-point searches, in parallel.
5. **Streamed to the UI, or buffered?** Buffered. The response is built after verification (`assist.py:739-800`; "Nothing is streamed" `:787`).
   - Provider calls: Gemini is not streamed (`generation.py:686-688`). DeepSeek is not streamed on `main`. Bonsai is streamed and folded before return (`model_router.py:61-62`, `generation.py:711-751`).
6. **Reasoning mode and level?** See §2 Phase B: `agent.py:445,478,501`, `generation.py:940-942`, `model_router.py:61`.
7. **Prompt tokens for the 28-page agreement + evidence + history?** 44,026–50,798 per call in a conversation with history; 33,800–40,170 in a fresh chat. 193,519 summed over Gemini T4's 4 calls; 134,267 over DeepSeek T4's 3.
8. **Truncation, and what goes first?**
   - The window keeps 6 messages / 12,000 characters (`agent.py:69-70,720`); older turns go to the case file.
   - The case file is capped at 9,000 characters (`:684`). The oldest reply openings go first, then middle user messages, keeping the first 3 (`:763-768`).
   - Material: 120,000 characters, newest kept first (`:836-841`).
   - Document: whole up to 240,000 characters, ranked above that (`tools.py:312,465-468`).
   - Pinned evidence: 16 records (`agent.py:736`). Seed query: 500 characters (`:987`).
   - Nothing is checked against a provider's context window.
9. **Region and endpoint?** See §2 Phase B: Gemini `generation.py:78`; DeepSeek and Bonsai `model_router.py:51-62` through their `*_BASE_URL`.
10. **Invisible retries, timeouts, back-offs?**
    - One retry on 429/500/503 after a 2.0 s wait (`agent.py:440-463`).
    - Every call's timeout is the remaining budget: `SOFT_S` 25, `HARD_S` 40, `FINAL_RESERVE_S` 12, `LEAN_HARD_S` 110 (`agent.py:53-62`). Stream per-read wait 50 s (`generation.py:708`).
    - The client waits 150 s (`frontend/src/lib/api.ts:128`).
    - The rescue judge is an extra Gemini call on a shut document gate (§6 #23).
11. **Synchronous work that could be async?**
    - The ledger persist and audit run after the answer is final but before the reply: 169.0–213.2 ms (§2).
    - The reranker and NLI load lazily on the request path (2,161.8–2,210.9 ms, first request).
    - Verification cannot move: `AM-25` r5.
12. **N+1 queries or repeated round-trips?**
    - The ledger persist issues one `_upsert` per shown record: ~171 records, 159.5–175.1 ms (`agent.py:597`).
    - `constitution.expand` and the statute read run once per record (5–29 calls, 3.7–41.8 ms).
    - `list_attachments` runs 2–3 times a turn (`agent.py:797,959`).
    - Retrieval runs 48–159 statements a turn.

### 8. What could NOT be measured, and why

- **prefill_ms** and **queue_wait_ms:** NOT EXPOSED by any of the three providers. First-token time and `Server-Timing` are the proxies used.
- **Provider region:** NOT EXPOSED for Gemini and IndieRouter. Bonsai exposes only the Cloudflare edge (BOM).
- **Reasoning, thought and cached tokens of LIVE app calls:** NOT MEASURED. The app keeps only prompt/output totals (`generation.py:760-770`); the raw calls stand in.
- **Production per-stage timing:** NOT AVAILABLE. The agent path returns (`service.py:1027-1037`) before `assist.ask.timings` / `assist.ask.trace` are emitted, so production logs carry per-call model latency only.
- **Gemini first token inside the app:** NOT MEASURED. Not streamed.
- **Behaviour under concurrent users:** NOT MEASURED. Production runs one uvicorn process and a sync endpoint on a thread pool; rerank and NLI are CPU-bound on 6 vCPUs shared with Postgres.
- **The browser → nginx → Next proxy → API chain in production:** NOT MEASURED. Through the API alone, a fixed reply took 15–76 ms (P5) and 25.17–33.26 ms in production (P13), which bounds the app's own plumbing.
- **E2 as a live app turn:** NOT RUN. The app cannot answer without searching evidence; isolated arithmetically.
- **The verify saving from shorter answers:** NOT MEASURED.
- **A stable-first prompt's behaviour:** NOT MEASURED (that would be a change).
- **Replay caveat:** the fresh verify numbers come from captured answers whose evidence keys may not match a fresh chat's registry. That changes which claims reach the NLI model, so live verify (P1/P2) is the authority and the replay gives its composition.
- **Noisy repeats:** T7 DeepSeek repeats ran at load average 5.59–5.9. Their rerank (1,539.5–1,573.8 vs 590.1) is reported, not cleaned.

### 9. Recommended next-session fixes — ranked, NOT implemented

0. **Prerequisite, logging only:** emit `assist.ask.timings` with the agent's `stages_ms`, and keep cached and reasoning token counts per call. Without that, production attribution stays invisible (§8).
1. Review and merge DF `88ad229`: ranks 1 and 3, already built and measured by that session.
2. Warm the NLI verifier and reranker at startup (rank 4).
3. Brevity contracts per model, Bonsai first (ranks 2 and 5), with one live measurement per model under the cost guard.
4. Stable-first prompt order (rank 7): A/B on the captured turns before any live call.
5. A streamed Gemini decision with the prose cut (rank 6).
6. Reranker depth and NLI speed (ranks 8–9), each gated on its zero-Gemini quality tool.
7. Owner decisions in §7 (streaming, the Bonsai disclosure, the repair policy).

### 10. Data reuse summary

- **Experiments:**
  - reused whole: E3 and E6;
  - partial (reused + only the missing part run): E1 (app T1 + raw bare), E4/E5 for DeepSeek (timings reused, reasoning-token exposure run), E7 for Bonsai (an identical pair reused + 3 raw), E9 and E10;
  - fresh: E4/E5 for Gemini and Bonsai, E7 for Gemini and DeepSeek, E8;
  - not run: E2 (arithmetic only).
  - Prior per-tool and per-stage figures (P10, P11) were stale and were re-measured with zero model calls.
- **Model calls made: 16, all diagnostic, public statute text only.**
  - Gemini 6: 181,730 prompt + 2,961 output + 3,027 thought tokens.
  - DeepSeek 5: 139,040 prompt + 8,500 completion (3,701 reasoning).
  - Bonsai 5: 43,916 prompt + 6,241 completion (3,971 reasoning).
- **Model calls reused instead of re-run:** 176 captured calls (P4), 29 completed + 7 failed calls in the DF per-stage files (P1/P2), and 35 production Ask calls (P13: DeepSeek 19 completed + 1 failed, Gemini 15).
- **Model calls avoided by zero-model replay:** 37 turns that would have made 112 calls.

**Coordination.** The DF session (`rag/defect-fixes-20261007`) is live and owns the D5 latency fixes. This
session changed no code and read its files without editing them. Its harness API on `:8378` and its
capture folder were left untouched; this session's API-free profiler ran in its own process against
the shared scratch database, every turn rolled back.

**Follow-up the same evening (owner: "ok go ahead", then "ok go").**
- **Fix #1 merged and deployed.**
  - The whole DF branch went in, because D5 builds on D1's `_run_tools`: PR #148, merge `08564b3`.
  - CI was 17/18; the failure was job 14, the pre-existing `npm audit`.
  - The ruleset requires only job 3, and it passed. The branch was 0 commits behind `main`; no `--admin`.
- **Deployed 23:10 IST.**
  - No migration; services active; 0 API errors; live build `EGQorxD-i0UngJDCo5-al` (the second of two deploys of `08564b3`, at 23:10:54; the first, at 23:10:18, built `YW163Q2NH1oMCu0Cs6Woi`).
  - The attachment purge timer is installed and enabled. Its manual run purged 0 and succeeded.
- **What is now live from the ranked list:** ranks 1 and 3.
  - The latency gain in production is not yet measured. Production logs only per-call latency (§8), so the next measurement needs rank 0's logging, or the scratch replay against `08564b3`.

**Batch 2 (owner: "fix"), branch `rag/latency-fixes-20261007`, uncommitted until the owner says commit.**
- **Rank 0:**
  - `generation._completed` keeps `cached_tokens` and `reasoning_tokens` (Gemini
    `cachedContentTokenCount`/`thoughtsTokenCount`; OpenAI-compatible `prompt_tokens_details`
    and `completion_tokens_details`) and logs them on `assist.generation.completed`.
  - `agent.turn_log` builds the turn's log fields: stages, `call_stats`, `tool_ms`.
  - It is shared by the shadow line and the new live `assist.agent.turn` line in
    `service._agent_answer`.
- **Rank 4:** `api.app._warm_models` warms the embedding model, the reranker and the verifier in one
  daemon thread, each through its public function, so a switched-off or missing model stays a
  mode, not an error.
- **Rank 6:** `generate_turn(prose_limit=)` streams a Gemini decision (`streamGenerateContent`)
  through `_send`. `_fold_gemini_stream` keeps every part (function calls whole, with their
  thought signatures) and stops at 400 characters of prose with no function call.
  `_fold_stream` and it share `_events`. Measured on 39 captured Gemini decisions: 0 characters
  beside every one of 21 tool calls; 657–3,403 characters, 2,898–9,160 ms, in the 18 done steps.
- **Live check (public statute text, 4 Gemini calls, 74,288 prompt + 547 output tokens):**
  - a done step: 4,367 ms uncut vs 2,662 ms cut (`PROSE_CUT` at 482 characters);
  - a tool-calling step stays valid streamed: 1,854 ms vs 2,053 ms.
- **Tests:**
  - ruff and mypy clean (148 files);
  - `test_openai_compat.py`, `test_embedding_warmup.py`, `test_assist_agent.py`: 61 passed;
  - new tests: the Gemini cut and its kept function call, an answer call not streamed, cached
    and reasoning tokens on both shapes, the startup warm-up of the reranker and verifier, and
    the live turn's log line with no text.

**Completion status: (b) partial.** All three phases are covered for all three models, with the reducibility table and the ranked fixes. The gaps are those in §8: prefill, queue wait and region (not exposed), production per-stage timing (not emitted), concurrency, the production proxy chain, E2 as a live turn, and the verify saving of shorter answers.

---

## Session 2026-10-07-DF — six known defects (D1–D6)

**Branch** `rag/defect-fixes-20261007` (worktree `/root/legalmind-worktrees/defect-fixes`),
from `main` `0aee166`. Local commits only: no push, merge or deploy.

**Regression baseline (must not break):**
- the agreement is read, the clause named, the standard compared, the law cited, and
  every sentence sourced;
- T4/T5/T6 (cap enforceable, convenience, indemnity survival) pass on all three models;
- a source click shows the clause, and the footer shows model + time;
- ungrounded sentences are removed;
- "my agreement" with no attachment asks for it.

### Fix order (written before any code)

1. **D1 [P0] — every requested point answered.**
   - A deterministic detector enumerates the numbered points in the reader's material
     (this email: "1. Title — request" … "17.").
   - Each point is searched on its own (local retrieval, no model cost).
   - The answer is asked for block by block, tagged with its point number.
   - After verification, code counts requested vs answered. Missing points get one
     continuation call; any still missing are listed by name, never dropped.
   - The reply states "N of N points".
2. **D2 [P0] — the fallback explains itself.**
   - Every floor is logged with its reason and the verifier's codes (codes and block
     indices only: no answer text in logs, per the log policy).
   - The reader is told why: the model did not finish in time; its answer could not be
     read; or which kind of check each draft statement failed.
   - Rejected sentences are never shown: an unverified claim reaching a reader is what
     `AM-25` r5 forbids.
   - The recorded floor cases are replayed to find real false positives.
3. **D3 [P1] — a long paste is accepted.**
   - Root cause: `LEGALMIND_ASK_ATTACHMENTS` is off in production, so the router refuses
     text over 2,000 characters.
   - The default becomes on, amending `AM-114`'s "default off". The owner's instruction is
     the approval, and the data boundary already approves sending material.
   - The paste then becomes the chat's material, exactly like an uploaded file.
   - The composer's counter is reworded.
   - Live verification needs a deploy, so it is the owner's step.
4. **D4 [P1] — a named clause is always in context.**
   - Clause numbers ("clause 13.1", "section 22") and clause topics named in the question
     are resolved against the selected document's own clause rows.
   - Those rows are forced into the turn's evidence even when ranking would miss them:
     the lean (Bonsai) path and documents over 240k characters are searched, not read
     whole.
5. **D5 [P2] — latency.**
   - Measure stage timings per model, before and after.
   - Make the safe speedups: the per-point searches of D1 run in parallel.
   - **Not done, by rule:** streaming tokens to the reader. The stage-9 invariant
     (`AM-25` r5, `AM-69`, CLAUDE.md) says nothing reaches a reader before verification;
     the owner must decide that. A progress-event stream would be an API contract
     change, so it is logged as a blocker.
   - Bonsai's reasoning is already off (`enable_thinking: false`, measured).
6. **D6 [P2] — two agreements in one chat.**
   - With a document already selected, a further file goes to the existing
     `POST /conversations/{id}/attachments` (no new API) instead of starting a new chat.
   - Material records carry their file name, so citations name the document.
   - The UI shows one chip per attachment.
   - The capability manifest's "one document per conversation" limit (L3) is updated.

Gemini cost guard: deterministic tests and offline replays first; one live check per
model per fix.

### Results (filled as each fix lands)

**D1 [P0] — FIXED** (`8d7a41b`, then the page fixes).
- Root cause: nothing counted. The model chose which points to answer, and the verifier's
  cite trim then stripped standards (see D2).
- Fix: `agent/points.py` reads the numbered list from the reader's own material, newest
  first (re-pasting the same text reuses its saved row). Each point is searched on its
  own, in parallel on read-only sessions. The answer is asked for point by point.
- After the checks, code counts. A point with no substantive block (a restatement does
  not count) is asked again, then named. The reply opens with the count and gives each
  point under its heading.
- Verified live on the real 17-point e-mail:

  | Model | Points named | Agreement clause cited | Standard (P/C) cited | Statute cited | Time |
  |---|---|---|---|---|---|
  | Gemini | **17/17** | 7 | 12 | 0 | 45 s |
  | DeepSeek | **17/17** | 7 | 15 | 1 | 81 s |
  | Bonsai | 0, all 17 **named** as not answered | — | — | — | 112 s |

  Before the fix, Gemini named 4 and DeepSeek 6.
- **Law per point:** cited only where the approved statute corpus bears. The calibrated
  statute gate finds nothing for business wording ("auto-renewal", "pricing
  protection"), and it is not loosened (wrong-source risk). One point (data retention)
  is offered the DPDP Rules.
- **Bonsai:** two attempts (pages of 4, then 2) both time out at about 20 tokens/s. Under
  the anti-loop rule this is now a **blocker**: the endpoint is too slow for long
  lists. The reply names every point and suggests Gemini or DeepSeek, or two points at a
  time.

**D2 [P0] — FIXED.**
- **Root cause 1:** `settle`'s cite trim kept a further cite only if the block then had
  no violation, V14 included. V14 means "the position and the agreement state different
  figures" (state both), so the trim stripped the standard from every "departs from our
  standard" claim, and some of those claims were then dropped.
  - Fix: the trim judges as the final check does (`SETTLE_IGNORED`).
  - Same 17-point answer: clause cites 5 → 8, standard cites 8 → 11.
  - Test: `test_settle_keeps_the_standard_a_differing_clause_is_compared_with`, which
    fails on the old code.
- **Root cause 2:** the floor said only "I couldn't write a full explanation".
  - Fix: `agent_verify.floor_reason` now says why: the model did not finish in time or
    could not be reached; its answer could not be read; or, statement by statement,
    which check failed on which source. The statement itself is never shown: an
    unchecked claim does not reach a reader (`AM-25` r5).
  - The failure flags now carry the cause ("TimeoutError", "HTTP 520").
  - Every floor is logged as `assist.agent.floor` with its kind and check codes; never
    text, per the log policy.
- **Verified live:**
  - Bonsai T6 is a full answer (58.6 s), where it had been the floor.
  - Bonsai T7 reads "Bonsai did not finish its answer within the time limit", with all
    17 points named.

**D3 [P1] — FIXED in code; live check after a deploy** (`c823259`).
- Root cause: `LEGALMIND_ASK_ATTACHMENTS` defaulted off, so the router refused any message
  over 2,000 characters, and production never set it.
- Fix: the default is on (`config.ask_attachments_enabled`, `off` = rollback; amends
  `AM-114`'s "default off", recorded as `AM-121`). A long message is saved as the chat's
  PASTE material and read exactly like an attached file. The composer's counter now says
  "N characters — kept as your material, like an attached file."
- Verified locally (scratch DB, code default, no env override): a 5,590-character message
  (an e-mail plus clauses 11–15) was accepted (201), saved as PASTE (READY, 5,542 bytes) and
  answered from its clause 13.1 beside our standard (C1, P2).
- **Deploy step:** install and enable the attachment purge timer
  (`ops/production/legalmind-attachment-purge.{service,timer}`), since material is now
  stored by default.

**D4 [P1] — FIXED.**
- Root cause: a document searched rather than read whole (the lean Bonsai profile, or
  any document over 240k characters) gave the model the top k ranked chunks only. A
  clause the reader named lost to better-scoring text.
- Fix: `tools.named_clauses` runs inside `search_knowledge` (the seed, the per-point
  searches and the model's own searches all go through it). It adds, whatever their
  rank, up to 4 clauses:
  - named by number ("clause 13.1" is 13.1 and its sub-clauses; the planner's own
    section regex);
  - named by heading (every heading word in the question, generic words aside:
    "indemnity" names "11 · INDEMNIFICATION"; "enforceable" alone does not name
    "Enforcement and Penalties").
  A clause named and found opens the document gate, as a Constitution section named by
  number already does.
- Measured on the 28-page executed MSA, every clause asked by name, ranked, zero model
  calls: **numbers 53/81 → 81/81, headings 25/57 → 53/57** (the four left are generic
  headings: "Services", "Annexure-1").
- **Not changed:** the blanket top-k. Point searches (k=3 × 17 points) would multiply it,
  and the model may already ask for up to 8. Chunking is already clause-wise (one
  clause, one record) and retrieval is already hybrid with a rerank.
- Two verifier fixes the live check exposed, each with a test that fails on the old
  code:
  - Bonsai writes keys as "(D4)". `normalise` moved only "[D4]" into the cite list, so
    V10 dropped all 9 of its sourced statements.
  - "Annexure-2" was read as the figure 2, which dropped the asked clause (V2).
    A document's own labels (annexure, schedule, appendix, exhibit) are now exempt like
    "clause 13.1".
- **Verified live (Bonsai, the ranked path):**
  - "What does clause 24.9 say?" (page 17; ranked alone missed it) → answered from
    24.9, cited, 54.9 s.
  - "What does the AUP annexure say about enforcement and penalties?" (page 22) → the
    answer leads with clause 3, Enforcement and Penalties, cited D1, beside clauses 4
    and 8.1 and the Constitution §17, 65.2 s. Before the verifier fixes it was the
    floor: first a timeout, then every statement dropped.
  - Gemini and DeepSeek read this 68k-character agreement whole, so every clause was
    already in their context.
- Known, not fixed: an annexure clause is located by its own number ("3"), which repeats
  the main body's numbering. The Sources line says "3, the selected document", not
  "Annexure-2, 3".

**D5 [P2] — partly FIXED; token streaming BLOCKED (owner decision).**
- Measured in process, per stage, T4 on a fresh chat over the 28-page MSA, rolled back:

  | Model | Before | After | What changed |
  |---|---|---|---|
  | Gemini | 27.0 s (L2) | 25.9 s (L2) | 2 searches in a step ran serially before; Gemini's steps here asked one |
  | DeepSeek | 41.2 s, **floor** (the final timed out) | 42.3 s and 42.1 s, both answered (L2), 8 and 10 sources | the "done" decision step 7.6–11.2 s → 2.6–3.6 s; one step's searches 5.5 s → 2.8 s |
  | Bonsai | 70.5 s | 87.3 s (repair ran and finished), 45.5 s | a repair started only with time to finish |

  Totals move with how much each model writes (DeepSeek's final: 2,030–2,238 tokens,
  14–18 s) and with verification (local NLI, 9–15 s on a 10-source answer). The stage
  savings above are measured directly.
- **Provider first token** (streamed calls): DeepSeek decisions 0.6 s and 2.0 s; Bonsai
  9.5 s. Gemini is not streamed, so its first token is the call's latency (2.8–6.8 s).
  **The reader's first token is the total**, by rule (below).
- Fixes:
  - A DeepSeek decision step is streamed and stopped once it writes 400 characters of
    prose with no tool call (`DECISION_PROSE_CHARS`, `_fold_stream`'s `prose_limit`).
    Measured over 31 captured decisions: prose beside a tool call ran 42–155 characters;
    a step that was done wrote 599–6,267, all of it discarded.
  - One step's searches run in parallel, each on its own read-only session
    (`_run_tools`, which D1's point searches now use too). The attachment tools stay on
    the request's session, which holds a paste saved by this request.
  - A repair starts only with 1.5× the answer call's time left (`REPAIR_FACTOR`, every
    model). Bonsai's 51 s answer had a repair still unfinished at 56 s, and DeepSeek's
    repair started with ~5 s left and timed out twice. A repair cut off ships the same
    answer as no repair.
  - Bonsai's reasoning was already off (`enable_thinking: false`, measured earlier).
- Tried and reverted: a prompt line asking a finished step to reply "DONE". Gemini and
  DeepSeek both ignored it (658 and 768 tokens of prose), so it was removed
  (`ask-agent-19` unchanged).
- **Not done here:**
  - Gemini decision steps are not streamed, so the prose cut-off does not reach them.
    That needs a streamed Gemini call in the egress seam: a separate, measured change.
  - The NLI verifier is already batched and length-sorted. A smaller or quantised model
    is a model change (`AM-90`).

**D6 [P2] — FIXED.** No API change: the attachment endpoints already existed.
- Root cause: a second file in a chat that already had a document started a new chat,
  and an attached file's records carried no name, so nothing could cite it by name.
- Fix:
  - The composer sends a further file to `POST /conversations/{id}/attachments`. The
    chat's document stays (earlier citations keep its reading order), and the file
    joins the chat's material list, one chip per file (`ChatMaterial`, unchanged). The
    note under a chosen file now says it is added beside the document.
  - Every record of an attached file is named after it: scope `your file "<name>"`
    and `from='…'` on its data tag (`attachments.label`). The prompt's existing "keep
    each record's scope in the sentence" makes the claim name it, and the Sources
    line names it. A name that could close the tag (`<`, `>`, `"`) is cleaned.
  - D4's named clauses reach attached files too (`search_attachment`): Bonsai reads a
    large attachment through search, not inline.
  - The live check found a D4 ordering bug, fixed with a test: clause numbers were
    taken in document order, so "clause 17.2 of the MSA … clause 13 of the ToS"
    filled every place with the MSA's 13, 13.1 … and never reached 17.2. Each named
    number now gets its own clause first (`tools._pick`). The 28-page sweep is
    unchanged: 81/81 and 53/57.
  - The capability manifest's L3 ("one document per conversation, cannot compare two
    uploaded documents") now states the real limit: a further file is read beside the
    document and named, but is not reviewed against our standards and is kept only
    with that chat.
- **Verified live** ("Does clause 17.2 of the MSA conflict with clause 13 of the Terms
  of Service I attached?", the MSA template as the chat's document, the Leapswitch ToS
  as the file). Each answer cites MSA 17.2 (D…) and the ToS's 13 as
  `your file "TOS-leapswitch.pdf"` (U…), and states the 6-month vs 12-month difference:
  - Gemini: 26.3 s;
  - DeepSeek: 41.5 s;
  - Bonsai: 82.8 s. Before the ordering fix, Bonsai said 17.2 "is not in the current
    records".
- Not changed: the selected document's Sources line still reads "the selected
  document". Its name is in the prose and in the chat header; on reload no source of any
  kind shows its scope (pre-existing).

### Blockers — needs human decision

1. **Streaming the answer's first tokens to the reader (D5).** The stage-9 invariant
   (`AM-25` r5, `AM-69`, CLAUDE.md: "nothing reaches a reader before mechanical
   verification") forbids showing a token before the whole answer is checked.
   Streaming would need the owner to amend that rule. A progress-event stream instead
   (stages, not tokens) is an API contract change, so it is skipped by this task's
   rule.
2. **Bonsai on a long numbered list (D1).** At ~20 output tokens/s, Bonsai does not
   finish even a two-point page of the 17-point e-mail inside its 110 s budget, so the
   reply names every point and suggests Gemini or DeepSeek. To fix: a faster endpoint, a
   longer budget for Bonsai (the client waits 150 s), or accepting that limit.

### Regression baseline, on the final code

A fresh chat per model: T3 with no agreement, then the 28-page agreement attached, then
T4 (cap enforceable), T5 (convenience termination) and T6 (indemnity survival). Private
runs: `runs/df-final-{gemini,deepseek,bonsai}.json`.

| Check | Gemini | DeepSeek | Bonsai |
|---|---|---|---|
| T3: "my agreement" with none attached asks for it (0 calls) | ✓ | ✓ | ✓ |
| T4–T6 answered from the agreement, the clause cited | ✓ 32 / 29 / 19 s | ✓ 36 / 34 / 25 s | ✓ 51 / 76 / 46 s |
| Our standard cited beside the clause | T4 | T4, T5 | none (none before either) |
| Footer: model and time, from `ai_answers` | ✓ 3 of 3 | ✓ 3 of 3 | ✓ 3 of 3 |
| Every Sources entry carries its record's text (the dialog's content) | ✓ 3 of 3 | ✓ 3 of 3 | ✓ 3 of 3 |

- **The law, a pre-existing gap, not this branch.** No T4–T6 answer cites a statute
  this time. Gemini's T4 searched the statutes ("Contract Act section 73 74 liability
  cap…") and was shown s. 74 and s. 154. The s. 74 record is a footnote and
  illustration fragment ("2. Subs. by the A.O. 1937…"), and s. 154 is about bailment,
  so not citing them was right. The model cited the Constitution's reading of the law
  instead (C2). The same search on `main` (`0aee166`), zero model calls, returns the
  same two records. Earlier runs cited statutes when the model's query reached the
  rule's own chunk. Fix: how the s. 74 chunk is read or ranked in the statute corpus;
  not one of D1–D6.
- **Found and fixed in this run** (`113dbac`): DeepSeek wrote "\`1\` year", and render
  marked the 1 of "Clause 13.1" ("13.\`1\`"). A value marked as code no longer lands
  inside a number.
- Ungrounded sentences are removed: the verifier suite passes, and the D4 replay shows
  V4 drops removed from the answer, not shown.

### Next session — pick up here

- ~~The owner's review, then the GitHub step~~ — done: PR #148 merged as `08564b3`, CI 17/18
  (job 14 fails on `main` too).
- ~~The deploy step for D3~~ — done: deployed 2026-10-07 23:11 IST; the attachment purge timer
  is installed and enabled, and one run purged 0.
- The statute gap above (Contract Act s. 74's record).
- D1 re-checked live on the final code (Gemini, the 17-point e-mail, agreement
  attached, 73.6 s with the full test suite running beside it): 16 of 17 answered
  (clause cited on 13, our standard on 11), and point 6 named as not answered with the
  "answer points 6" offer, never dropped. A model's miss on one point is what the
  continuation and the naming are for.
- Optional: name the selected document in its Sources line (render-time only;
  `_selected` depends on the scope string).

### Git

Branch `rag/defect-fixes-20261007`, local commits only (no push, merge or deploy):
`8d7a41b` D1+D2 · `aa9d917` D1/D2 pages, flags, records · `c823259` D3 · `996dbc4` D4 ·
`88ad229` D5 · `4232717` D6 · `c6812a6` `AM-121` records · `113dbac` the code-mark fix ·
then the closing records commit.

## Session 2026-10-07-RG — grounding and behaviour

**Branch:** `rag/grounding-and-behavior-20261007`, worktree
`/root/legalmind-worktrees/rag-ground`, based on `fix/ask-chat-micro` `18ad160`, which
carries `AM-116` `990cf39` (the model router this session needs). Local commits only: no
push, merge, rebase, tag or deploy, and no `npm run deploy`, no bare `next build`, no
visual-baseline update.

### Goal

Make Ask answer only from Attachment Context (an uploaded agreement, or pasted text) plus
Evidence Context (Constitution, statutes, standards), behave like a senior assistant on
short, vague and ungrounded inputs, and prove both end to end on Gemini, DeepSeek and
Bonsai.

### Plan (written before any code)

1. **Environment, production untouched.**
   - Scratch DB `legalmind_rag_ground`: a `pg_dump` of `legalmind_v1_demo` (it is in use by
     the demo, so it is copied, never altered). That gives the branch head `f4b8d2a6c1e9`,
     the Constitution with L1.11 current, and 79 standards. Statute tables are replaced
     with the `section-5` set production serves (`AM-104`), taken from
     `legalmind_ab_bench`. Old conversations are truncated.
   - API from this worktree on its own port: agent mode on, attachments on (the designed
     paste path), production's rerank and position-synthesis flags. Only the needed key
     lines are read from `/root/.legalmind.env`.
2. **Trace the 11-step chain in code and in a live trace:** upload → attach → paste →
   request → proxy → retrieval → prompt assembly → system prompt → LLM call → render →
   failure UX. Evidence for every row is a file:line, a request trace or a captured
   payload (private, IDs only in this file).
3. **Fixture (owner D10):**
   - Email: Drive `1qTS1TkK4Vfk2Vf5w20quyGJD-gpYB9_0`, a counterparty's 17 review points on
     our MSA (early termination, auto-renewal, retention, suspension, liability carve-outs,
     mutual indemnity, payment).
   - Agreement: Drive `1k_mgdJyyUE0sAJ3vOlLQysW_nHXruh0-`, an executed MSA on our paper. Its
     damages cap is an AVERAGE of fees (the CLAUDE.md trap), which must not be read as the
     12-month total standard.
   - The two come from different counterparties; the questions test grounding per source,
     and no answer may merge them.
4. **The conversation (identical for every model):**
   1. normal: our early-termination position;
   2. scenario: a customer wants a capped early exit on 60 days' notice;
   3. ungrounded: "Is my liability cap enforceable?", with no document;
   4. attach the agreement, then the three sales questions: the cap; termination for
      convenience; indemnity survival;
   5. paste the email with a question;
   6. paste a clause with no question;
   7. "hi", "thanks", "how can you help me?", "hi" again;
   8. vague: "I want to talk about a dispute."

   One chat per model (the comparison needs the same history). A re-check after a fix
   goes back to the same chat.
5. **Score** each reply 1–5 on grounding, brevity, accuracy, tone and failure honesty.
   Rank defects: P0 = no grounding reaches the model, or a confident answer without
   grounding; P1 = partial or wrong grounding; P2 = degraded grounding or a behaviour gap.
6. **Fix minimal, root cause, with tests.**
   - Known before the live run (code evidence):
     - (a) the fixed "hi" reply re-introduces the product (`conversational.py`);
     - (b) "how can you help me?" is not recognised as a capability question and reaches
       the model;
     - (c) a pasted clause under 2,000 characters is not treated as material at all;
     - (d) with attachments off, as in production, a paste over 2,000 characters is
       refused.
   - Wording changes to the fixed replies append an `AM-109` amendment.
7. **Providers.**
   - One OpenAI-compatible adapter in the egress module, so every gate, payload screen,
     audit row and token count applies to it.
   - Registry: DeepSeek via IndieRouter, Bonsai via the company endpoint.
   - An appended `AM-30` amendment per `AM-116` r5. IndieRouter's no-training terms are
     recorded as unconfirmed; Bonsai is on the company's own domain.
8. **Gemini cost guard:**
   - deterministic checks first;
   - one live pass per model;
   - a re-run only of the turns a fix touches.
9. **Before stopping:**
   - tests: backend pytest (agent + touched modules), vitest, tsc and lint, plus a
     Playwright run where the CI stack is not needed;
   - commits;
   - update STATUS.md, this file and SESSION_CHECKLIST.md, and the three CLAUDE.md
     records.

### What was fixed

Every item: root cause, the change, file:line, commit. Records: `AM-117` (AB-65), `AM-118`
(AB-66), both appended to `all_lock.md`.

| # | Rank | Defect (evidence) | Root cause | Fix · where · commit |
|---|---|---|---|---|
| 1 | **P0** | "Is my liability cap enforceable?" with no agreement in the chat got a confident answer from the company standard, as if the standard were the reader's cap (Gemini T3) | nothing told a question about the reader's OWN paper from one about ours | a fixed reply says what to attach or paste · `query/conversational.py:177,191`, `service.py` `preroute` · `7ebf84a` (`AM-118` r3). Re-checked: T3 in a fresh chat on all three models, 0 calls |
| 2 | P1 | a bare clause paste was analysed unasked (T8) | a paste under the 2,000-character cap was never material | `agent/attachments.py:139` `carries_material` + `api/routers/assist.py` (attachments on → saved, `MATERIAL_SAVED`); with attachments off, `service.py:317-321` → `MATERIAL_READ`, 0 calls · `7ebf84a` (r5, r6) |
| 3 | P1 | "hi" re-introduced the product (T9, T12) | the fixed wording | `query/conversational.py:156` · `7ebf84a` (r1) |
| 4 | P1 | "how can you help me?" reached the model: 4 calls, 12 s (T11) | the agent's pre-router never ran the capability route | the manifest's `brief` · `query/capability.py:76,91`, `config/capability_manifest.json`, `preroute` · `7ebf84a` (r2) |
| 5 | P1 | a vague "I want to talk … about a dispute" got the dispute clause dumped (T13) | no clarifying rule | one fixed question · `query/conversational.py:211` · `7ebf84a` (r4) |
| 6 | P1 | the loop was controlled by a count (3) alone (owner's 7 rules) | no stop rule | `MAX_DECISIONS` 6 as a net; one `_should_stop` (time, then asked / done / repeat) · `agent/agent.py:49,906,990,1035` · `7ebf84a` (r7) |
| 7 | P1 | DeepSeek ended T2 and T4–T7 on the floor at 28–40 s | reasoning tokens count against `max_tokens`: a decision spent all 2,048 thinking and returned no tool call; a "done" decision then wrote 400–1,500 tokens of discarded prose; a LOW answer ran past its time | `reasoning_effort` from Gemini's thinking level; OpenAI-compatible providers think at MINIMAL and cut a decision at 768 tokens · `llm/generation.py:886`, `agent/agent.py:441,489` · `0108624`, `bf72fec` |
| 8 | P1 | DeepSeek T7 took 75 s against `HARD_S` 40 s: 36 s AFTER the model answered | the verifier judged claim by claim — 118 NLI calls of 1–5 pairs | `verify.warm` scores stage 1, then stage 2 for the claims stage 1 did not entail, in two calls; `judge` reads the memo; pair builders shared (`_claim`, `_stage2`) · `verification/verify.py:287,307,319`, `agent_verify.verify` · `51614b1`. Replay: 41 → 31.7 s, 118 → 20 calls, identical verdicts; live T7 75 → 42.8 s, T4 41.8 → 27.5 s |
| 9 | P1 | the floor quoted a Partner Agreement position as "the clause that answers this most directly" in an MSA chat (Bonsai T2) | P2b held the model's answer to the conversation's kinds of agreement, not the floor | one predicate for both · `verification/agent_verify.py:450` (`_other_family`), `floor`, `ladder` · `dd83fb3` |
| 10 | P2 | the floor chose by shared words: force majeure for an early exit, "(f) violates applicable laws" for the liability cap | lexical ranking only | the local cross-encoder (`rerank.scores`, on in production) orders the candidates; a second quote must clear logit 0 · `agent_verify.py:1170` · `40c35d1`. Live Bonsai floors now quote 14.3, 13.1, 15.2 |
| 11 | P2 | e2e 32/34: a refused paste came back trimmed; a model option said only "DeepSeek" to a screen reader | the restore used the trimmed text; a Radix option is named by its `ItemText` alone | `components/workspace/AskWorkspace.tsx` `submit`, `ModelPicker.tsx` (visually hidden status) · `af3a586` |

The providers themselves: `48aa1e2` (`AM-117`: DeepSeek via IndieRouter, Bonsai on the
company endpoint, through the one egress seam).

#### Decision loop (owner, 2026-10-07) — the three lines asked for

- **Problem:** the loop stopped only on a fixed count (3 decisions). A bare paste reached the model, which analysed it unasked, and repeated searches spent calls the final answer needed.
- **Change:** `MAX_DECISIONS` is now 6, as a safety net only. One `_should_stop()` ends the loop on `soft_deadline`, `budget` (the `HARD_S` − `FINAL_RESERVE_S` reserve, or the call cap), `asked`, `model_done`, or `repeat` (a round that returned only chunks already shown). A bare paste is acknowledged with zero model calls (`MATERIAL_READ`).
- **Where:** `backend/legalmind/assist/agent/agent.py:49`, `:906` (`_should_stop`), `:990`, `:1035`; `backend/legalmind/assist/service.py:317-321`; `backend/legalmind/assist/agent/attachments.py:51`. Tests: `tests/assist/agent/test_assist_agent.py`.

### Behavioural test results

One conversation per model, the same 13 inputs, re-checked in the SAME chat after each fix
(Gemini `188b1b2b`, DeepSeek `c1fd2bb1`, Bonsai `080c07e0`; T3's fix in a fresh no-document
chat, because the original chats hold the agreement by then). Fixture: Drive
`1qTS1TkK4Vfk2Vf5w20quyGJD-gpYB9_0` (the e-mail, 17 points) and `1k_mgdJyyUE0sAJ3vOlLQysW_nHXruh0-`
(the executed MSA). Scores 1–5 as **G**rounding · **B**revity · **A**ccuracy · **T**one ·
**F**ailure honesty, on the final reply.

| Input | Expected | Gemini | DeepSeek | Bonsai |
|---|---|---|---|---|
| T1 our early-termination position | the MSA standard, cited | 5·4·5·4·5 — no early exit, remaining fees [P1]; 13 s | 5·3·5·4·5 — the standard, then the attached 14.3 (asked after the attach); 33 s (was: answered) | 2·4·3·3·4 — floor (endpoint), the liability standard quoted first |
| T2 capped exit on 60 days? | "no — needs approval", from the standard | 5·4·5·5·5 — no, commercial approval + legal review [C3, P1] | 3·3·3·4·3 — answers from the attached agreement's 5.1/14.3, never says whether we can agree; 46 s (was: floor) | 3·4·3·4·4 — floor quotes 14.3 (was: a Partner Agreement position — fixed #9, #10) |
| T3 my cap enforceable? (no agreement) | say the grounding is missing | 5·5·5·5·5 — fixed reply, 0 calls (was 1·3·1·4·1: confident, from our standard) | 5·5·5·5·5 (was: floor quoting standards) | 5·5·5·5·5 |
| T4 this agreement's cap enforceable? | the 13.1 cap + the law + the standard, kept apart | 5·3·5·4·4 — 3-month average cap, 13.2 exclusions, ss. 73/74; 28 s | 5·3·5·4·5 — not determinable, a counsel point; 3-month average vs the 12-month standard; 27.5 s (was: floor) | 4·4·3·4·4 — floor quotes 13.1 (was: an unlawful-content clause — fixed #10) |
| T5 terminate for convenience? | 14.3, 90 days, 5.1 | 5·4·4·4·4 — 90 days; puts "we" under the customer's 5.1 limit; 25 s | 5·3·5·4·5 — both parties, customer subject to 5.1; 42 s (was: floor) | 4·5·4·3·4 — floor quotes 14.3 |
| T6 indemnity survives? | 15.2 accrued; no express survival | 5·4·5·4·5; 18 s | 5·4·5·4·4; 40 s (was: answered) | 4·5·4·3·4 — floor quotes 15.2 (was: 12.4 — fixed #10) |
| T7 e-mail + "which conflict with our standards?" | every conflicting point, against the standards | 4·4·3·4·3 — four conflicts; indemnity / liability / auto-renewal left out, unsaid; 29 s | 4·3·4·4·4 — six conflicts named with clauses; 42.8 s (was: floor, then 75 s — fixed #8) | 2·4·2·3·4 — floor quotes one agreement clause; a 17-point comparison has no one-passage answer |
| T8 bare clause paste | short acknowledgement + offer | 5·5·5·5·5 — saved, "what would you like to know?", 0 calls (was: a full analysis) | same | same |
| T9 / T12 "hi" twice | one short line, identical | 5·5·5·5·5 — "Hello. What can I help you with today?" both times, 0 calls | same | same |
| T10 "thanks" | short acknowledgement | 5·5·5·5·5 | same | same |
| T11 "how can you help me?" | ≤ 2–3 lines | 5·5·5·5·5 — the three-sentence brief (what it does, its limit, how to start), 0 calls (was: 4 model calls, 12 s) | same | same |
| T13 vague dispute | ONE clarifying question | 5·5·5·5·5 — "payment, termination, a breach, or something else?" (was: the dispute clause dumped) | same | same |

T8–T13 are answered before any model call, so they are identical for every model by
construction. Bonsai's T1–T7 are floors because its endpoint cannot take the agent's
context (Blockers). Model use (captured, private): Gemini 47 calls over both passes,
1.87 M prompt tokens (mostly cached) and 19.7 k output — the after-pass 10 calls; DeepSeek
63 calls; Bonsai 15 attempts, all failed at the endpoint; plus about 18 direct replays to
diagnose (DeepSeek, Bonsai — none to Gemini).

### Proactive fixes applied

Two of thirteen changes (15 %, under the 20 % cap):
- the `Endpoint` key is excluded from its `repr`, because captured call arguments printed it (`0108624`);
- the NLI memo is bounded at 4,096 entries (the agent path never cleared it, so it grew
  for the life of the process) and read once per call, so a concurrent clear cannot lose a
  pair (`51614b1`).

### Assumptions logged

- T2's DeepSeek and Bonsai re-runs came after the agreement was attached in the same chat,
  so they answer from it. That follows the one-chat rule, but it is not like-for-like with
  Gemini's T2, which was asked before the attach.
- `reasoning_effort` is sent to every OpenAI-compatible provider. DeepSeek honours it;
  Bonsai accepts it and ignores it (probe, 2026-10-07).

### Blockers — needs human decision or external setup

1. **`LEGALMIND_ASK_ATTACHMENTS` is off in production.** A paste over 2,000 characters is
   refused, and a bare paste under the cap is acknowledged but not saved. Turning it on is a
   production configuration change for the owner.
2. **IndieRouter's no-training terms are not confirmed** (`AM-117` r5).
3. **Security housekeeping:**
   - rotate the IndieRouter and Bonsai keys pasted into the chat;
   - the production DB password was visible in a process command line (seen 2026-10-06).

*Resolved in round 3:*
- Qwen is removed from the model list (`AM-120`): the owner reports IndieRouter withdrew
  it, which agrees with its "Unknown model" answer for the key.
- Bonsai now answers (see below).
- Agent answers' sources are now structured and can be opened (it had needed an
  API-contract change, made on the owner's request).

### Next session — pick up here

- **T7 coverage of a many-point e-mail.** Gemini named 4 conflicting points and DeepSeek 6.
  Gemini's first draft said indemnity, liability and auto-renewal also conflict, and its
  repair dropped that line. Fixing this needs an answer-contract change ("one block per
  conflicting point") plus a Gemini measurement run, so it was not done blind (cost guard).
- **DeepSeek T7 is still 42.8 s.** About 24 s of that is local NLI over 530 pairs (~45 ms a
  pair on 6 CPUs). What remains is fewer stage-2 pairs or a smaller NLI model, and both
  need measuring.
- **A source cited across turns can lose its dialog on reload** (independent review #7,
  predates round 3). The registry re-adopts a pinned key with the current text, and
  `ledger._upsert` then mints a new key by text hash, so reload finds the record under
  that new key. The fix belongs in the ledger's key identity.
- **"Open in the document" for another document's clause** is not offered, live or on
  reload: replay can only re-read the conversation's own contract.
- **Owner:** review the branch, then decide on push / PR / merge / deploy.

### Review before the GitHub step (2026-10-07, owner: "again review your work")

The whole diff against `fix/ask-chat-micro` was re-read and the CI guards were run
locally.

**Defects found and fixed in the review:**
1. **A typed situation was read as a bare paste.** 80 typed words ending "Let me know our
   position on this" were acknowledged and never answered. A last sentence that asks the
   assistant for something now makes the message a question · `agent/attachments.py`
   `_ASKS` · test `test_a_long_typed_situation_that_asks_is_a_question_not_a_paste`.
2. **The capability brief listed only strengths.** `AM-68` r5 requires the capability
   answer to state its limits, and the brief dropped them. It now carries L1 ("I do not
   decide whether a document is acceptable or advise whether to sign; a person decides"),
   and `brief()` accepts limit ids as evidence.
3. **The floor asked the reranker with no question words.** It no longer calls the
   reranker on an empty question.

**Checked and sound:**
- A tool call cut at 768 tokens parses to `{}`, which the tool layer refuses.
- `my …` does not swallow "my company's".
- "Add files" matches the UI's own wording.
- The configured hosts match the `AM-117` record.
- No counterparty name and no key prefix appears anywhere in the diff.
- CI job 6 locally: 0 lines removed, main's 22,469-line prefix identical.
- Job 7: no corpus fixture changed.
- Job 8: no contract file type added.

**Risks carried forward:**
- **The rollback path.** `preroute` runs only on the agent path, which production serves
  to everyone. With `LEGALMIND_ASK_AGENT_MODE=off` (the rollback) the old pipeline answers,
  without the `AM-118` own-agreement reply.
- **Gemini cost.** `MAX_DECISIONS` 6 permits more Gemini decisions per turn than 3 did;
  `SOFT_S` and the repeat stop bound it. Measured: T7 used 6 calls (was 4), T4 used 4
  (unchanged).
- **The stack.** It carries `AM-116`'s migration `f4b8d2a6c1e9` (`conversations.title`).
  A deploy must confirm the Alembic version moved (the 2026-10-06 silent rollback).
- **Private harness data.** `/root/.legalmind/rag-ground/captures/` (mode 700/600) holds
  real document text and, from before `0108624`, the provider keys inside the captured
  `Endpoint` repr. Delete it when the comparison is no longer needed.

**Tests after the review:**
- backend `tests/assist` + source material + import boundaries: 1,701 passed, 4 skipped
  (6:29). A first attempt stalled at ~30%, with Postgres at 90% CPU on one position query
  while the e2e run shared the server; the re-run was clean;
- ruff and mypy clean (147 files);
- Ask e2e in ONE pass: 34/34;
- frontend vitest 557/557, lint clean.

### Round 3 (2026-10-07) — Bonsai, Qwen, who answered and how long, sources you can open

Owner: fix Bonsai, find out why Qwen is not configured, show the model and the time
under each answer, and (their manager) list the sources structurally, each opening to
show where it came from. Researched first (two code maps, one per side); then built,
reviewed by an independent reviewer (8 findings, 7 fixed, 1 logged above), and measured
live.

| Item | Root cause (measured) | Change | Evidence |
|---|---|---|---|
| **Bonsai** | ~700 prompt and ~18–26 output tokens/s; the gateway closes a request silent for 50 s; it reasons unless told not to | lean profile (`AM-119` r3): agreement searched not read whole, material capped (and searched), no decision step, the repair only with time to finish, a 110 s budget; streamed inside `_send` (`AM-119` r4); `enable_thinking: false` | live T4 70 s, T5 74 s, T6 78 s, all real answers; before, every turn ended on the floor |
| **Qwen** | IndieRouter: "Unknown model: qwen3.8-flash-next" for the key | none possible: recorded (`AM-119` r5) | blocker 1 |
| **Model and time** | the answer row stored them; nothing returned them | `answered_by` + `latency_ms` live and on reload, from the same row; the footer "Answered by DeepSeek (deepseek-v4.1-flash) · 41.3 s"; a fixed reply says no model was used | real browser, DeepSeek and Bonsai |
| **Sources** | the agent returned `citations: []`, with a text legend only | `sources` per legend key; each legend entry is a button opening a dialog with the record's own words and "Open in the document"; reload re-reads under current permissions | real browser: dialog opens, Escape closes, focus returns |

**Fixes from the independent review:**
- the footer names only the model whose words are shown (the floor names none, and the
  rescue judge is never named);
- a stream that is empty or reports an error fails, and `[DONE]` ends it;
- a stream's per-read wait is at most 50 s, its deadline holds over the whole stream, and
  a retry gets only the time left;
- lean searches the reader's attachments;
- another document's clause is not offered as a source;
- the dock offers no link (its document is already open);
- a marker's jump lands visibly.

**Tests (final code):**
- backend `tests/assist` + source material + import boundaries: 1,709 passed, 4 skipped; without models (as CI): 1,645 passed, 32 skipped, 0 failed; ruff and mypy clean;
- frontend vitest 560/560, lint clean;
- Ask e2e 34/34 in one pass;
- live: DeepSeek and Bonsai in their own chats, in a real browser through nginx (`next
  dev`'s proxy drops requests after ~30 s, a local limit only).

### Final review before merging (2026-10-07)

An independent review of the whole branch against `main` found one defect, now fixed. It
found no permission leak, no egress outside `_send`, no migration problem, no API break,
and no CI failure.
- **HIGH, fixed:** with attachments off (as in production), "I don't have that agreement"
  also answered questions that gave their own text: a quoted clause, a stated figure
  ("my cap of 3 months' fees"), a drafting request, or a clause pasted in an earlier turn.
  The neighbouring vague-intent rule caught "a claim under the DPDP Act".
  - `their_document_topic` now steps aside for a quote, a colon followed by text, a
    figure, a drafting verb, or more than 20 words.
  - A paste in the thread counts as material.
  - `vague_intent` asks only when nothing but generic words remain.
  - Tests: the reviewer's inputs.
- **Low, fixed:** a test name that gave the wrong reason.

Whole backend suite, run as CI job 13 runs it (no keys, no models): 3,216 passed, 167
skipped, 1 xfailed, 0 failed. ruff and mypy clean.

### Git

**Merged and deployed 2026-10-07:**
- PR #145 merged as `f60d655` (09:44 UTC) and deployed at 15:23 IST; migration verified
  (see STATUS.md).
- Branches `rag/grounding-and-behavior-20261007`, `fix/ask-chat-micro` and
  `feat/ask-chat-controls` deleted, together with their worktrees.
- The parked top-bar change is on `wip/topbar-account-menu` `d24c2b5`.

As it stood before the merge:

Branch `rag/grounding-and-behavior-20261007` (worktree
`/root/legalmind-worktrees/rag-ground`), on `fix/ask-chat-micro` `18ad160`, on
`feat/ask-chat-controls` `990cf39` (`AM-116`). **Neither parent is on GitHub**, so a PR
from this branch to `main` carries all of them (12 commits); `origin/main` has not moved
since the base (0 commits behind). Local commits only. Review: `git log --oneline fix/ask-chat-micro..rag/grounding-and-behavior-20261007`
and `git diff fix/ask-chat-micro..rag/grounding-and-behavior-20261007 --stat`.
