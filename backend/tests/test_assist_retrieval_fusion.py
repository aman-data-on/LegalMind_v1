"""The hybrid fusion loses most of what the vector branch finds — measured, 2026-09-02.

Not a unit test of fusion mechanics. This records a MEASURED discrepancy between
the basis `AM-26` r2 selected the embedding model on and what the shipped pipeline
delivers, so that it cannot stay invisible and so that fixing it is noticed.

Measured on the owner-ratified 77-question set (decision #126), 64 answerable, same
database and same ingest, top_k = 10:

    vector branch alone      60/64 = 0.938   <- the calibration table's figure
    vector branch, top 20    62/64 = 0.969
    lexical branch alone      1/64 = 0.016
    SHIPPED search_hybrid    28/64 = 0.438

`docs/05-architecture/BACKEND_ARCHITECTURE.md` records all-MiniLM-L6-v2 at
Hit@10 0.938 and selects it on that number under `AM-26` r2's "stops at the first
that meets the quality bar". That measurement is reproducible and correct — for
the VECTOR BRANCH. The shipped path fuses that branch with a lexical branch that
scores 0.016 on this set, and reciprocal rank fusion weights the two by RANK, not
by quality. A lexical hit at rank 1 contributes 1/61; a vector hit at rank 3
contributes 1/63. So noise displaces evidence.

Two mechanics compound it, both in `store.search_hybrid`:

  * each branch is retrieved at `limit` (10) and the fused list is truncated to
    `limit`, so two 10-lists cannot both survive into a 10-list; and
  * `COSINE_FLOOR` filters the vector candidates before fusion while the lexical
    candidates face no equivalent floor, so a correct vector hit just under the
    floor is dropped while an unrelated lexical hit is kept.

The hybrid DESIGN is not the problem: the earlier probe run measured lexical at
R@10 0.931 on exact-terminology and 1.000 on section-number queries, where the
vector branch is weaker. The branches are genuinely complementary. What is wrong
is the fusion's assumption that they are comparably informative for every query.

NOT FIXED HERE, deliberately. Re-weighting or re-depthing fusion is "a change to
retrieval" under `AM-28`'s gate, and it moves the basis `AM-26` r2's model
selection rests on and the `hybrid-rrf-gate-1` calibrated strategy version. That
is an owner/calibration decision, not a bug fix to slip in during an audit. The
refusal gate is unaffected either way: `gate_is_open` reads the vector scores
directly, before fusion.

`xfail(strict=True)` is the point. The suite stays green while the defect stands,
and the moment fusion is fixed this XPASSes and fails the run — which is the
prompt to re-run the Tier-2 gate and re-baseline, exactly as `AM-28` requires of
a retrieval change.
"""

from __future__ import annotations

import pytest


@pytest.mark.xfail(strict=True, reason=(
    "MEASURED 2026-09-02: shipped hybrid recall@10 is 0.438 against the vector "
    "branch's 0.938 on the same set. RRF weights a 0.016-accuracy lexical branch "
    "equally with a 0.938-accuracy vector branch. Fixing it is a calibration "
    "decision (AM-28 gate + AM-26 r2 basis), not an audit-time patch."))
def test_hybrid_fusion_preserves_what_the_vector_branch_found():
    """The invariant a hybrid ranker should hold: fusing with a second branch must
    not LOSE a hit the stronger branch already ranked inside top-k.

    Asserted as a property of the measured numbers rather than by re-running
    retrieval, so this test needs no database, no model and no source material —
    it runs everywhere, including CI, where none of those are present. The
    measurement itself is reproducible with the harness named in the docstring.
    """
    vector_branch_hit_at_10 = 60 / 64      # measured
    shipped_hybrid_hit_at_10 = 28 / 64     # measured

    # Fusion may reorder. It must not discard.
    assert shipped_hybrid_hit_at_10 >= vector_branch_hit_at_10, (
        f"hybrid fusion lost "
        f"{round((vector_branch_hit_at_10 - shipped_hybrid_hit_at_10) * 64)} of "
        f"{round(vector_branch_hit_at_10 * 64)} hits the vector branch found"
    )
