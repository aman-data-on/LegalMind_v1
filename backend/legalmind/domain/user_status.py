"""The three words a reader sees — the PURE projection (AM-56, owner 2026-09-09).

ACCEPTABLE · REQUIRES_MODIFICATION · NEEDS_DECISION, derived from the engine's
classification and nothing else. This module holds only the mapping and the
ranking; `legalmind.evaluation.user_status` keeps the database-reading helpers
(`by_finding`, `counts`) and re-exports these names, so every existing caller is
unchanged.

It lives in `domain` (2026-09-10) because the assist lane needs to READ a
Finding's word to show it beside a quoted position — and the assist package may
import `domain` but never `evaluation` (`test_import_boundaries.py`; `AI-01`).
Reading the projection is not deciding anything: the classification it projects
was made by the evaluator, and nothing here is fed back to it.

  MATCH                                        -> ACCEPTABLE
  DEVIATION                                    -> REQUIRES_MODIFICATION
  MISSING                                      -> MISSING  (AB-104, owner 2026-10-23:
                                                  "Missing" = not in the contract)
  DEVIATION inside a Constitution UNACCEPTABLE
  POSITION (§24.4 "Not Negotiable", AM-63)     -> NEEDS_DECISION
  UNABLE_TO_EVALUATE / CONFLICT / …            -> NEEDS_DECISION
"""
from __future__ import annotations

from legalmind.domain.enums import FindingClassification as C
from legalmind.domain.enums import RuleOutcome as R

ACCEPTABLE = "ACCEPTABLE"
REQUIRES_MODIFICATION = "REQUIRES_MODIFICATION"
NEEDS_DECISION = "NEEDS_DECISION"
#: AB-104 (owner, 2026-10-23): the reader's fourth word — the obligation is not in the
#: contract at all, said apart from "change needed" (a clause there, differing).
MISSING = "MISSING"
#: Every reader word, in the one order every surface shows them.
WORDS = (ACCEPTABLE, REQUIRES_MODIFICATION, MISSING, NEEDS_DECISION)
_RANK = {ACCEPTABLE: 0, NEEDS_DECISION: 1, MISSING: 2, REQUIRES_MODIFICATION: 2}
_MODIFY = {C.DEVIATION, C.MISSING}


def user_status(classification: C, rule_outcome: R | None = None,
                prohibited: bool = False) -> str:
    """The word follows the classification (AM-56), with ONE Constitution-stated
    exception (AM-63, Constitution L1.10 §24.4, owner 2026-09-13): a deviation
    that falls within a defined UNACCEPTABLE POSITION of the Constitution —
    `prohibited`, from `constitution_boundaries.py` — is "Not Negotiable" and
    "requires a human legal or business call": NEEDS_DECISION, not a clause to
    be modified. §24.4(1): never displayed as a rejection. `rule_outcome` is
    accepted for the callers' sake and recorded beside the word."""
    if classification is C.MATCH:
        return ACCEPTABLE
    if classification in _MODIFY:
        if prohibited:
            return NEEDS_DECISION
        if classification is C.DEVIATION and rule_outcome is R.ACCEPTABLE:
            return ACCEPTABLE       # AM-239: in LeapSwitch's favour, accepted by the
                                    # approved favourable rule; still a DEVIATION
        return MISSING if classification is C.MISSING else REQUIRES_MODIFICATION
    return NEEDS_DECISION


def worst(statuses: list[str], fallback: str) -> str:
    """A Finding's status is its worst Evaluation's; with none, the fallback."""
    return max(statuses, key=_RANK.__getitem__) if statuses else fallback
