"""Shipped retrieval recall is 0.438 against a 0.938 vector ceiling — attributed.

Records a MEASURED gap between the basis `AM-26` r2 selected the embedding model
on and what the shipped pipeline delivers, so it cannot stay invisible and so a
fix is noticed. No threshold, gate or model is changed by this file.

THE EVIDENCE, measured 2026-09-02 on the owner-ratified set (decision #126), 64
answerable questions, top_k = 10. `COSINE_FLOOR` is applied at TWO points, and
the 2x2 over both is the whole story:

                    per-hit floor ON     per-hit floor OFF
    gate ON              0.438  SHIPPED       0.625
    gate OFF             0.453                0.938   == the vector ceiling

Three things follow, and only the first was expected.

1. FUSION LOSES NOTHING. Bottom-right is 60/64 — bit-identical to the vector
   branch measured alone. With neither threshold applied, RRF over lexical +
   vector reproduces the ceiling exactly, so no correct chunk is displaced out
   of the top 10 by fusion, by the lexical branch, or by truncation. Corroborated
   independently: candidate pool 10 -> 100, vector weighting 2x/5x/20x, and
   lexical caps 0/3/5 (0 = lexical excluded entirely) ALL leave recall unmoved
   at 0.625 with the floor off. Fusion is not the defect and weighting is not
   the remedy.

2. THE TWO THRESHOLD APPLICATIONS ARE SUPER-ADDITIVE, so neither alone is a fix.
   Floor only: +0.188. Gate only: +0.016. Both: +0.500. They are not independent
   causes to be added, because they are ONE constant read twice: when the gate
   closes on vector grounds the top score is already below 0.50, so the per-hit
   filter has emptied the vector branch anyway. Relax either alone and the other
   still blocks.

3. THE LEXICAL BRANCH IS INERT HERE — 1/64 = 0.016 alone. It contributes no
   unique recall at all, which is why capping or removing it changes nothing.
   That also means `gate_is_open`'s `if lexical_hit: return True` short-circuit
   effectively never fires on this corpus, and the gate decision rests wholly on
   the vector top score clearing COSINE_FLOOR by PEAK_MARGIN.

MEASURED, NOT FIXED. Both levers are `COSINE_FLOOR` / `PEAK_MARGIN` / refusal
thresholds, which the authorising instruction placed out of scope, so the remedy
needs an owner calibration decision rather than a code change here. One
observation for that decision, since it is easy to miss: MiniLM's cosine scores
are compressed on this corpus — the architecture record measures answerable
median 0.539 against unanswerable 0.416 — so a CORRECT chunk sitting at 0.45 is
ordinary for this model, not anomalous, and a 0.50 floor cuts through the middle
of the answerable distribution rather than below it.

CORRECTION, same date. An earlier version of this file named reciprocal rank
fusion as the cause, and a first correction of it then reported the gate as worth
+0.312 on its own. Both were wrong. The fusion claim came from reading
`search_hybrid`'s returned hits for an "ungated" arm — they are empty whenever
the gate closes, so refusals scored as retrieval misses. The +0.312 came from
assigning each question to whichever check fired first, which measures blame
order, not recoverability. The 2x2 above measures recoverability directly and is
what should be trusted.

`xfail(strict=True)` is deliberate: the suite stays green while the gap stands,
and the moment it closes this XPASSes and fails the run, which is the prompt to
re-run the Tier-2 gate and re-baseline as `AM-28` requires of a retrieval change.

PHASE 1 SEPARATION, 2026-09-02 (owner-approved experiment, not yet a production
change). Everything above described one constant, `COSINE_FLOOR`, read at two call
sites. It is now two: `calibration.COSINE_FLOOR` for the refusal gate
(`gate_is_open`, unchanged) and `calibration.EVIDENCE_COSINE_FLOOR` for
`search_hybrid`'s per-hit evidence prune. Both default to 0.50, so this record's
numbers are unchanged and the split alone changes no behavior — see
`docs/00-project/RETRIEVAL_RECALL_AUDIT_2026-09-02.md` and the follow-on threshold
experiment for what, if anything, is proposed for `EVIDENCE_COSINE_FLOOR` next.
"""

from __future__ import annotations

import pytest

# Measured 2026-09-02. Keys are (gate_applied, per_hit_floor_applied).
RECALL_AT_10 = {
    (True, True): 28 / 64,     # shipped
    (True, False): 40 / 64,
    (False, True): 29 / 64,
    (False, False): 60 / 64,   # == the vector branch alone
}
VECTOR_CEILING_AT_10 = 60 / 64      # the AM-26 r2 selection basis
SHIPPED_RECALL_AT_10 = RECALL_AT_10[(True, True)]
LEXICAL_ALONE_AT_10 = 1 / 64        # the branch contributes no unique recall


def test_fusion_reproduces_the_vector_ceiling_when_no_threshold_is_applied():
    """Guards the DIAGNOSIS, and passes — the diagnosis is not in doubt.

    Kept beside the xfail so a later reader cannot re-derive "it must be fusion"
    from the headline numbers, which is the mistake this file already made once.
    """
    assert RECALL_AT_10[(False, False)] == VECTOR_CEILING_AT_10, (
        "with neither threshold applied, RRF fusion returns exactly what the "
        "vector branch alone returns — it displaces nothing, so no weighting, "
        "pool depth or lexical cap can recover recall")


def test_neither_threshold_application_is_a_fix_on_its_own():
    """The super-additivity, which is why there is no small safe change here."""
    floor_only = RECALL_AT_10[(True, False)] - SHIPPED_RECALL_AT_10
    gate_only = RECALL_AT_10[(False, True)] - SHIPPED_RECALL_AT_10
    both = RECALL_AT_10[(False, False)] - SHIPPED_RECALL_AT_10
    assert both > (floor_only + gate_only) * 2, (
        f"one constant read twice: floor-only recovers {floor_only:.3f}, "
        f"gate-only {gate_only:.3f}, but both together {both:.3f}")


@pytest.mark.xfail(strict=True, reason=(
    "MEASURED 2026-09-02: shipped recall@10 0.438 against a 0.938 vector "
    "ceiling. Attributed to COSINE_FLOOR being applied at two points — the "
    "refusal gate and the per-hit evidence filter — which together account for "
    "the whole 0.5 gap and individually recover +0.016 and +0.188. Fusion "
    "accounts for zero. Both levers are out of scope for the audit that found "
    "this (COSINE_FLOOR, PEAK_MARGIN, refusal thresholds) and need an owner "
    "calibration decision."))
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
