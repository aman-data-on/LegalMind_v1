# Ask agent — Phase 2 exit report: the tool layer (2026-10-01)

Branch `feat/ask-agent-phase0-1`, from `ecd1814`. Local commits only. **Nothing is pushed,
merged or deployed, and production is unchanged** — no production database write, no
production config, no service restarted, no unit installed.

## The seven tools — `backend/legalmind/assist/tools.py`

Entry point `tools.run(ctx, name, arguments)`. Not exposed by any endpoint; not wired
into Ask. Each wraps existing code; no second retrieval, ranking or permission rule.

| Tool | Wraps | Arguments (strict, `extra="forbid"`) | Returns |
|---|---|---|---|
| `search_knowledge` | `constitution.search`, `positions.search_positions`, `store.search_hybrid` | `query` ≤ 500 · `sources` ⊆ {constitution, positions, documents} · `document_version_id` ≤ 64 · `k` 1–8 | records + `by_source` quality |
| `get_company_position` | `positions.search_positions` (verbatim) | `topic` ≤ 500 · `k` 1–8 | records + quality |
| `search_statutes` | `statutes.search_statutes` | `query` ≤ 500 · `include_superseded` bool · `k` 1–8 | records + quality |
| `get_evidence` | `ledger.refetch` | `evidence_ids` 1–8 keys, each ≤ 64 | per key `current` / `stale` / `unavailable` |
| `list_attachments` | `attachments.list_for` | none | ids, names, status; `count_returned` |
| `search_attachment` | `attachments.search` (now with an in-WHERE attachment filter) | `attachment_id` ≤ 64 · `query` ≤ 500 · `k` 1–8 | records + quality |
| `ask_user` | — (nothing stored) | `question` ≤ 300 · `options` ≤ 4 × ≤ 80 | the question; ends the turn in Phase 3 |

**Record:** `ref` (natural key `CONST:` `POS:` `STAT:` `DOC:` `ATT:`), `source`, `authority`,
`status`, `location`, `text`. **Quality** (search tools): `gate_open`, `lexical_hit`,
`top_score` (None when empty), `count_returned` — from existing semantics (A-26). Other
tools: `count_returned` only.

## Authorization model (A-23, A-24)

- **Who** is never an argument: `ToolContext.open` takes the authenticated user, their live
  permissions and a conversation they own (`NotVisible` otherwise, as the router does). A
  contract the caller can no longer read drops out of scope for every tool.
- **IDs** resolve in ONE query that joins the authorization rule. Malformed, missing,
  nonexistent and another user's IDs give the **identical** `NOT_FOUND` envelope by the same
  path. Evidence keys answer per key `unavailable`. Only out-of-schema values are
  `INVALID_ARGUMENT`.
- **Filters** can only narrow: `sources` is a closed set; positions and the Constitution
  still check `assist.ask` + a position permission inside their own search.

## Read-only guarantee (A-25)

Every call runs inside a savepoint that is always rolled back. Tests: no tool's call moves
`pg_stat_xact_user_tables` (and the detector is proven to see a write the savepoint undid);
`ask_user` adds no message; the Gemini seam is trapped in every tool test. Ledger keys are
assigned when an answer is recorded, never by a tool.

## `get_evidence` behaviour

| Case | Result |
|---|---|
| visible, text unchanged | `current`, with text |
| visible, changed or superseded (newer document version, retired standard, repealed Act, non-current Constitution item, lost pointer) | `stale`, with text |
| expired or purged material; contract out of scope; another conversation's key; unknown key; malformed key | `unavailable`, no text, no ref — one shape |
| repeated call | identical result |

## Results

| Item | Result | EVALS |
|---|---|---|
| Tool tests | 33 passed: authorization (missing, malformed, nonexistent, unauthorized, authorized, cross-user, argument and filter bypass), schema (17 cases incl. `k > 8`), read-only, evidence states, quality signals | — |
| Frozen set q77-v1 | sha256 `c06162de020d8761e7ae02d056bb172f8751caf94d1ce9e6cf4d4f1f970a8b92`, pinned by `test_frozen_question_set` | #23 |
| Retrieval, zero calls | `main` recall@10 0.641 · hit@1 0.484 · MRR 0.546 · wrongly answered 1/13 — **branch 0.656 · 0.484 · 0.548 · 0/13** | #23 |
| Golden benchmark (wrong-source) | recall@10 0.9529 · wrong-source 0 · false admission 0 (= `main`'s EVALS #1) | #30 |
| Earlier probe | `main` 0.6406 / 0.4375 / 0.5107 — **branch 0.6562 / 0.4375 / 0.5126** | #24 |
| New probe | `main` 0.9765 / 0.9061 / 0.9344 / FA 0.026 — **branch 0.9982 / 0.9242 / 0.9544 / FA 0.026** | #25 |
| Per-tool latency p50/p95 ms | search_knowledge 31/43 · get_company_position 7/9 · search_statutes 184/218 · get_evidence 2.0/2.3 · list_attachments 0.7/0.8 · search_attachment 6/8 · ask_user 0.0/0.1 | #28 |
| Attachment-status UI | read-only list; 545/545 frontend tests, typecheck, terms check | — |
| Purge timer (scratch) | fired, purged 1, chunks/embeddings/ledger U → 0 | #29 |
| Full suite | **3033 passed, 0 failed**, 119 skipped (same skips as Phase 1), 1 xfailed; `ruff check .` and `mypy` clean | — |
| Model calls | **0** in Phase 2 | — |

## Carry-forwards

- **A1** — frozen and compared, zero calls. The branch is not below `main` on recall@10,
  hit@1 or MRR, and is lower on wrongly answered. Phase 1's 0.922 had the rescue judge on
  (33 calls) and is not comparable with these.
- **A2** — in progress: 0 calls today (the day's budget was the Phase 1 exception), 100
  remaining tomorrow. Plan in EVALS; the gate now has a generated-only mode and a question
  filter so no call is repeated.
- **A3** — probes and provenance below. **A4** — 80 → 75 explained (EVALS #27).
  **A5** — built (A-27). **A6** — tested on scratch (A-30).

### A3 — the two probes, their authors, and the 0.026

| | Earlier probe | New probe |
|---|---|---|
| Tool | `tools/probe_targeting.py` (2026-09-18) | `tools/probe_real_corpus.py` (2026-10-01, this programme) |
| Questions | 64 answerable of q77-v1 — **drafted 2026-08-26 in an auto-mode agent session "against a full read of the actual supplied documents, at the owner's direction"** (the file's `_about`; drafting choices logged as AUTO_MODE_DECISIONS #124–#127), **ratified by the owner the same day**: "Use questions_draft.json as the current evaluation dataset" (#126). Two fields added to the statute questions 2026-09-21, no anchor changed | 554 answerable + 384 unanswerable, **derived mechanically by the probe code from the parser's evidence rows** — no person wrote a question; the code was written by this agent |
| Answer keys | each question's `anchor` excerpt, authored with the question | SHA-256 hashes of each probe (`tests/assist_eval/real_corpus_keys.json`), pinned 2026-10-01 |
| Corpus | 15 supplied source documents | 32 real client documents (private, D11) |
| What it tests | a natural-language question finds its clause | a verbatim phrase or clause number finds its own text — a much easier lexical task |

They are not interchangeable. **Both are now required** on every retrieval change (STATUS).

**The 0.026 (10 of 384).** Five distinct phrases, each scored twice — the probe draws
"unanswerable" phrases from other documents, and near-duplicate files supply the same
phrase more than once (384 probes, 163 distinct). All five open the gate on the vector
branch alone (cosine 0.522–0.544, floor 0.50; peak gap above the 0.059 margin), with no
lexical match; the document holds no three-word run of the phrase. The probe labels a
phrase "unanswerable" by absent words; the calibrated gate admits by meaning. So this is
**expected gate behaviour on a lexically-defined label, not a retrieval defect** — and the
duplicate counting **is** a probe defect, recorded (A-29) and left unchanged in Phase 2 so
the number stays comparable; the distinct-probe rate is 5/163 = 0.031. In the agent these
openings arrive with `lexical_hit = false`, which the model can see.

## Caveats

- A2 (generation baseline) is not complete; it is not a Phase 2 exit criterion.
- The UI list was checked by static rendering, typecheck and the full frontend suite, not
  in a browser: with the flag off it renders nothing anywhere it is deployed.
- Record times written on 2026-10-01 before 18:30 IST ran ahead of the real clock (the
  system clock read 18:22 when the records said ~20:15); corrected from 18:30 on, and noted
  in the log. Order and content are unaffected.

## Phase 2 exit status: **MET**

Every exit criterion in STATUS is met; A2 is in progress as the brief allows. Phase 3 waits
for the owner's review.
