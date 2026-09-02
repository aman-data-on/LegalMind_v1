"""The measured retrieval configuration — every number here has a measurement behind it.

Nothing in this module is a preference. `AM-26` r2 requires the embedding model chosen
by measurement, smallest-that-passes; rule 7's discipline extends to product parameters:
a threshold nobody measured is a threshold somebody invented. The provenance for every
value is the calibration of 2026-08-26 against the owner-ratified 77-question evaluation
set (64 answerable / 13 unanswerable) over 15 real supplied documents — reproducible via:

    python3 -m tools.benchmark_retrieval --eval --candidates <candidates> --json out.json

--------------------------------------------------------------------------
Why this model
--------------------------------------------------------------------------
Four provisioned 384-dimension candidates were measured. Top-10 recall of the expected
clause on human-phrased questions: MiniLM 0.938 · bge-small 0.922 · gte-small 0.969 ·
arctic-embed-s 0.438 (rejected outright). MiniLM is the SMALLEST candidate (23M params
against 33M) and passes the quality bar — ≥90% top-10 recall, and a calibrated gate
refusing ≥10/13 unanswerable questions while retaining ≥60% of answerable ones. `AM-26`
r2 then decides: gte-small retrieves marginally better, but adopting a larger model when
a smaller one passes is precisely the "adopted for headroom" the record forbids.

--------------------------------------------------------------------------
Why this gate shape, and what it deliberately does not attempt
--------------------------------------------------------------------------
Measured on the ratified set, lexical search finds the right clause for human-phrased
questions almost never (1/64 — `websearch_to_tsquery` ANDs every term) but refuses
perfectly (13/13); dense retrieval finds clauses well (60/64 in top-10) but refuses
NEVER, because a nearest neighbour always exists. So the rule composes them:

    evidence  =  lexical hits  UNION  vector hits with cosine >= EVIDENCE_COSINE_FLOOR
    gate open iff  lexical hit  OR  (top cosine >= COSINE_FLOOR and top-gap >= PEAK)

where top-gap = top cosine minus the mean of the remaining top-k — a flat profile means
the "best" chunk is not meaningfully better than the field. A single absolute floor was
measured first and found insufficient (best Youden's J 0.50 across candidates); the
two-feature rule reached J 0.564 with 12/13 gate refusals.

The gate does NOT try to catch the adversarial near-misses — questions whose nearest
clause is genuinely topical but does not answer them (a provider-insurance clause for a
customer-insurance question). Measured: those score INSIDE the answerable distribution,
so no similarity feature separates them, for any candidate. Catching them is the
citation-verification guardrail's job (`AM-29`'s third outcome), and pretending a
threshold could do it would trade half the answerable set for the illusion.

--------------------------------------------------------------------------
Two responsibilities, two constants (separated 2026-09-02, E1 phase 1)
--------------------------------------------------------------------------
"Should LegalMind answer?" and "which retrieved chunks are allowed to become evidence
for generation?" are different questions, and until this separation they were answered
by the same number read at two call sites — `gate_is_open` (below) and
`store.search_hybrid`'s per-hit prune. The E1 retrieval audit
(`docs/00-project/RETRIEVAL_RECALL_AUDIT_2026-09-02.md`) measured them as
super-additive: relaxing either alone recovers only part of the gap, because closing the
gate on vector grounds already implies the per-hit filter would have emptied the branch.

    COSINE_FLOOR           the REFUSAL GATE's floor — `gate_is_open` only. Calibrated
                            2026-08-26, unchanged by this split, never relaxed since.
    EVIDENCE_COSINE_FLOOR   the EVIDENCE-INCLUSION floor — `store.search_hybrid`'s
                            per-hit prune only. Same calibrated value by default; this
                            name exists so the two can be evaluated and, if ever
                            changed, changed independently — never so the gate can be
                            weakened through the back door of the other name.

Do not read them as interchangeable, and do not let a future edit collapse them back
into one constant — that is the exact ambiguity this record removes.
"""

from __future__ import annotations

# `AM-26` r4 — pinned and recorded against every answer. The weights are additionally
# pinned by SHA-256 in the provisioning manifest (r5), verified at load.
EMBEDDING_MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_MODEL_REVISION = "main"
EMBEDDING_DIMENSIONS = 384

# The calibrated gate — measured 2026-08-26, ratified dataset. `gate_is_open` ONLY.
#   COSINE_FLOOR: the top vector score must clear this for the gate to open on
#                 vector grounds alone (lexical hits open the gate regardless).
#   PEAK_MARGIN:  gate opens on vector evidence only when the top hit stands out
#                 from the field by at least this much (top - mean(rest of top-k)).
# Operating point: 12/13 unanswerable refused at the gate, 41/64 answerable retained
# on vector evidence alone (lexical hits pass regardless); Youden's J = 0.564.
# NEVER weaken this to improve recall — it is the safety control. See the module
# docstring's "Two responsibilities, two constants" before touching either name.
COSINE_FLOOR = 0.50
PEAK_MARGIN = 0.059

# The evidence-inclusion floor — `store.search_hybrid`'s per-hit prune ONLY, applied
# AFTER the gate has already decided to answer. Individual vector hits below this are
# never surfaced as evidence to generation. Defaults to the same calibrated value as
# COSINE_FLOOR (this split changes no behavior on its own) but is a DISTINCT constant
# so the two responsibilities can be evaluated, and if ever changed, changed
# independently under their own measurement and their own AM-28 gate run.
EVIDENCE_COSINE_FLOOR = 0.50

# Candidates fetched per query before gating. Top-10 was the calibrated depth.
RETRIEVAL_TOP_K = 10

# Version string recorded on retrieval_runs rows, so a re-calibration is
# distinguishable from this one in every persisted record.
RETRIEVAL_STRATEGY_VERSION = "hybrid-rrf-gate-1 (calibrated 2026-08-26)"


def gate_is_open(lexical_hit: bool, vector_scores: list[float]) -> bool:
    """The deterministic refusal decision, exactly as calibrated.

    Pure and dependency-free so the guardrail tests can exercise it without a
    database, a model, or a prompt anywhere in sight (`AM-28` r2).
    """
    if lexical_hit:
        return True
    if not vector_scores:
        return False
    top = vector_scores[0]
    if top < COSINE_FLOOR:
        return False
    rest = vector_scores[1:]
    if not rest:
        return True
    gap = top - (sum(rest) / len(rest))
    return gap >= PEAK_MARGIN
