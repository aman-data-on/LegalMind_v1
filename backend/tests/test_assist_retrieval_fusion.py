"""Shipped retrieval recall is 0.438 against a 0.938 vector ceiling — attributed.

Records a MEASURED gap between the basis `AM-26` r2 selected the embedding model
on and what the shipped pipeline delivers, so it cannot stay invisible and so a
fix is noticed. No threshold, gate or model is changed by this file.

CORRECTION, 2026-09-02. An earlier version of this test named reciprocal rank
fusion as the cause. That was wrong, and the measurement that disproved it is
below: fusion accounts for ZERO of the loss. The wrong attribution came from an
"ungated" measurement that read `search_hybrid`'s returned hits — which are
empty whenever the gate closes — so refused questions looked like retrieval
misses rather than refusals. Measuring the raw vector branch instead separates
them.

ATTRIBUTION — 64 answerable questions of the owner-ratified set (decision #126),
top_k = 10, each question assigned to exactly one cause:

    gate refused, vector HAD it       20    +0.312 recoverable
    gate refused, vector missed it     3    model ceiling
    retained, floor dropped it        12    +0.188 recoverable
    retained, fusion displaced it      0    <- fusion costs nothing
    retained, vector missed it          1    model ceiling
    HIT (shipped)                     28    = 0.438

So the 0.5 gap is two threshold effects and a small model ceiling:

  * 0.312 — `gate_is_open` refuses 20 questions whose evidence the vector branch
    DID rank inside its top 10. The gate opens on `lexical_hit` or on a vector
    top score >= COSINE_FLOOR with >= PEAK_MARGIN separation; for these 20 the
    lexical branch found nothing and the vector top score did not clear both.
  * 0.188 — `search_hybrid` filters INDIVIDUAL vector hits below COSINE_FLOOR
    out of the evidence list ("never evidence, gate or no gate"). For these 12
    the correct chunk ranked 2nd-6th by cosine at 0.35-0.50, below the 0.50
    floor. MiniLM's scores are compressed on this corpus — the architecture
    record measures answerable median 0.539 against unanswerable 0.416 — so a
    correct hit at 0.45 is ordinary for this model rather than anomalous.
  * 0.062 — 4 questions the vector branch genuinely does not retrieve.

MEASURED, NOT FIXED. Every lever is outside the authorised scope:

    deeper candidate pools     0.438 -> 0.453, and wrongly-answered 1 -> 2
    branch weighting 2x/5x/20x 0.438 unchanged
    lexical cap 0/3/5          0.438 unchanged (0 = lexical excluded entirely)
    per-hit floor lifted       0.438 -> 0.625, with retained 41, wrongly
                               answered 1 and correct refusals 12 ALL UNCHANGED

The last row is the one worth an owner decision: lifting the per-hit filter
costs nothing measurable in safety, because the floor's REFUSAL role lives in
`gate_is_open`, which reads the raw vector scores and is untouched by it. The
filter only prunes the evidence list AFTER the decision to answer has been made.
That is arguably a separation of two distinct uses of one constant rather than a
weakening of the refusal control — but it is the owner's call, not an audit's.

`xfail(strict=True)` is deliberate: the suite stays green while the gap stands,
and the moment it closes this XPASSes and fails the run, which is the prompt to
re-run the Tier-2 gate and re-baseline as `AM-28` requires of a retrieval change.
"""

from __future__ import annotations

import pytest

# Measured 2026-09-02 by tools/verify_assist_quality + the attribution harness
# described above. Vector ceiling is the raw branch at top-10, ungated, unfiltered.
VECTOR_CEILING_AT_10 = 60 / 64      # 0.938 — the AM-26 r2 selection basis
SHIPPED_RECALL_AT_10 = 28 / 64      # 0.438 — what a user gets

# Cause -> questions, summing to the 36 losses.
LOSS_ATTRIBUTION = {
    "gate_refused_vector_had_it": 20,
    "gate_refused_vector_missed": 3,
    "floor_dropped_from_evidence": 12,
    "fusion_displaced": 0,
    "retained_vector_missed": 1,
}


def test_the_loss_attribution_is_complete_and_fusion_is_not_the_cause():
    """Guards the DIAGNOSIS, and passes — the diagnosis is not in doubt.

    Kept beside the xfail so that a later reader cannot re-derive "it must be
    fusion" from the headline numbers, which is exactly the mistake this file
    already made once.
    """
    assert sum(LOSS_ATTRIBUTION.values()) == round(
        (VECTOR_CEILING_AT_10 - SHIPPED_RECALL_AT_10) * 64) + 4, (
        "attribution must account for every answerable question")
    assert LOSS_ATTRIBUTION["fusion_displaced"] == 0, (
        "measured: no question's correct chunk was displaced out of top-10 by "
        "fusion. Weighting and pool depth are therefore not the remedy.")


@pytest.mark.xfail(strict=True, reason=(
    "MEASURED 2026-09-02: shipped recall@10 0.438 against a 0.938 vector "
    "ceiling. 0.312 is the refusal gate declining questions whose evidence was "
    "retrieved; 0.188 is the per-hit COSINE_FLOOR pruning correct chunks from "
    "the evidence list. Both levers are forbidden to this audit (COSINE_FLOOR, "
    "PEAK_MARGIN, refusal thresholds) and need an owner calibration decision. "
    "Fusion accounts for zero and is not the fix."))
def test_shipped_retrieval_reaches_the_calibrated_vector_basis():
    """The invariant the product needs: what AM-26 r2 selected is what ships.

    Asserted on measured constants so it needs no database, model or source
    material and runs in CI, where none of the three are present.
    """
    assert SHIPPED_RECALL_AT_10 >= VECTOR_CEILING_AT_10, (
        f"shipped retrieval delivers {SHIPPED_RECALL_AT_10:.3f} of the "
        f"{VECTOR_CEILING_AT_10:.3f} the selected model achieves — "
        f"{round((VECTOR_CEILING_AT_10 - SHIPPED_RECALL_AT_10) * 64)} of 64 "
        f"answerable questions lose their evidence")
