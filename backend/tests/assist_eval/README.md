# Assist-lane evaluation dataset — Tier 2 (`AM-28`)

**Status: ✅ RATIFIED — owner, 2026-08-26** (by directing its use for calibration;
recorded as AUTO_MODE_DECISIONS #126). The calibration of 2026-08-26 ran against this
set; its results live in `docs/05-architecture/BACKEND_ARCHITECTURE.md`.

This directory holds the question set for measuring the assist lane's retrieval quality
and refusal correctness (`AM-28`: retrieval recall, citation precision, faithfulness, and
refusal correctness in both directions).

## What this is, and what it is not

* It is **not** the golden corpus, carries none of its Tier-1 authority, and never
  substitutes for it (`AM-28` r3). It lives outside `tests/corpus/` deliberately, so the
  golden-expectation CI guard and the corpus loader never see it.
* It contains **no document text** — questions, filenames, clause references and short
  cited excerpts only (locked 54.6). The documents themselves stay in the gitignored
  source directory and are read at benchmark time.
* Under `AM-31` m1 this is an **explicitly-labelled evaluation set whose provenance is
  stated per question**: every question was authored on 2026-08-26 against a full read of
  the actual supplied documents, at the owner's direction, with every answerable
  question's source clause verified and every unanswerable question's absence verified by
  search. **A result measured on it is reported as a draft-set result** until the owner
  ratifies the set; `AM-26` r3's quality bar is satisfied only on owner-ratified material
  (`AM-31` m2), and no assist answer reaches a user over real counterparty material on an
  unratified bar (m3).
* The 2026-08-26 calibration selected `all-MiniLM-L6-v2` and the two-feature refusal
  gate; changing a question here invalidates that calibration, so edits re-run
  `tools/benchmark_retrieval.py --eval` and re-record.

## Shape

`questions_draft.json` — one object per question:

| Field | Meaning |
|---|---|
| `id` | `Q-*` answerable · `N-*` not-found |
| `category` | `CONTRACT` (agreements and policies) or `STATUTE` (Acts, Rules, Directions) |
| `question` | As a lawyer, analyst or business stakeholder would ask it |
| `expected` | `ANSWERABLE` or `NOT_FOUND` |
| `document` | The file the question targets — retrieval is scoped per document (`AM-25` r6) |
| `section` | The clause/section that answers it (`ANSWERABLE` only) |
| `rationale` | Why that source answers it / why nothing does |
| `difficulty` | `EASY` (near the clause wording) · `MEDIUM` (different wording) · `HARD` (conceptual) |
| `nearby_trap` | `NOT_FOUND` only: the semantically-adjacent clause a naive system would wrongly return |
| `answered_elsewhere` | `NOT_FOUND` only: a different document that genuinely answers it, if one exists |

The four outcomes the owner asked the set to distinguish map as:
contract-answered (`Q-*`, `CONTRACT`) · statute-answered (`Q-*`, `STATUTE`) ·
related-but-unanswered (`N-*` with `nearby_trap`) · no source at all (`N-*` without).

## Confidentiality

Two supplied documents are executed with real counterparties. **No counterparty or
signatory name appears in this dataset**; NDA questions refer to "the Disclosing Party".

## The recorded quality bar — `baseline.json`

`baseline.json` is the Tier-2 gate's recorded bar (`AM-28`): the metrics the shipped
pipeline measured on this dataset, as numbers and hashes only — no document text (54.6).
`tools/verify_assist_quality.py` re-measures against it through the PRODUCTION path
(`service.plan_question` → `service.retrieve_document` for the retrieval half;
`service.ask` whole for the generated half) and **blocks a release on a worsened
wrongly-answered rate, a worsened user-visible wrongly-answered rate, or worsened
faithfulness**. Faithfulness and citation precision have been measurable since the
`AM-31` gate release of 2026-08-31 (this paragraph said `not_yet_measurable` until
2026-09-17; that was stale for seventeen days). Recall, retention and the three
targeting measures added on 2026-09-17 — **MRR** of the gold chunk, **gold-in-top-3**,
**evidence precision** (the share of chunks handed to generation that are gold), all
computed from the existing `section` anchors — are reported without blocking, because
the locked gate names faithfulness and the wrongly-answered rate. Stage latency
(p50/p95) and Gemini calls and tokens per question are printed and never written into
the baseline.

The baseline's `pipeline` block records the embedding model, strategy version, every
calibrated constant, and whether the evidence rescue and the query planner were live; a
run under a different pipeline is refused rather than compared.

**The baseline is ONE measured run, and some of its numbers are not deterministic.**
The evidence rescue is a model call, so whether it reopens a given shut gate varies
between runs, and every ratio computed over `retained` moves with it. Measured across
four consecutive runs of the identical build on 2026-09-17 (reranker on):

    hit@1        0.734 · 0.734 · 0.734 · 0.719      retained        61 · 61 · 61 · 60
    MRR          0.796 · 0.796 · 0.789 · 0.778      false refusals   3 ·  3 ·  3 ·  4
    gold@3       0.844 · 0.844 · 0.828 · 0.828      recall@10    0.906 · 0.906 · 0.891 · 0.891

The recorded bar is the fourth of those — the least favourable draw, which makes the
WARN-only lines harder to trip on noise and is the conservative direction for them. What
did NOT vary across any of the four is everything the gate BLOCKS on: wrongly-answered
1/13, user-visible wrongly-answered 0/13, faithfulness 1.0, citation precision 1.0. Read
a sub-0.02 movement in recall, MRR or gold@3 as noise unless it repeats; read any
movement in the blocking four as real.

Re-baselining is `--write-baseline`: a deliberate act whose diff is reviewed like any
other. The tool refuses to compare across a changed dataset (the sha256 is part of the
baseline), so editing questions and re-recording the bar land in the same reviewable
change.
