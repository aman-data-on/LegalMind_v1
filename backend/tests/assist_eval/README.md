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
