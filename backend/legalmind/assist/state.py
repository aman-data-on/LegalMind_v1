"""The sixth state axis — `AM-29`, and nothing else.

A separate module, deliberately far from `legalmind/domain/enums.py` where the five
legal axes live: r1 says the assist answer state *"never shares a field, a column, an
enum or a name with any of the five"*, and separate files make an accidental merge a
diff someone has to write rather than an import someone forgets.

r2's nine forbidden values (`UNABLE_TO_EVALUATE`, `NOT_APPLICABLE`, `AMBIGUOUS`,
`MATCH`, `DEVIATION`, `MISSING`, `CONFLICT`, `ACCEPTABLE`, `UNACCEPTABLE`) appear
nowhere below, and `tests/test_assist_schema.py` asserts the same of the database enum.
"""

from __future__ import annotations

from enum import Enum


class AssistAnswerState(str, Enum):
    """r3's three distinguishable outcomes, plus the successful case.

    Recorded separately because they have different causes and different remedies:

        NO_EVIDENCE_RETRIEVED   nothing available within the requester's authorized
                                scope — the calibrated retrieval gate stayed closed
        EVIDENCE_INSUFFICIENT   retrieved, but too weak to support an answer; the
                                model is NOT called at all
        CLAIM_UNSUPPORTED       the model answered and a claim failed verification
    """

    ANSWERED = "ANSWERED"
    NO_EVIDENCE_RETRIEVED = "NO_EVIDENCE_RETRIEVED"
    EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
    CLAIM_UNSUPPORTED = "CLAIM_UNSUPPORTED"


# `AM-29` r4, verbatim requirement: a user-facing refusal is worded identically
# whether the cause was an empty corpus or an authorization exclusion — r6 and r7 of
# `AM-25` depend on this. One string, used by every refusal path, so a wording drift
# is a diff on this line and nowhere else.
REFUSAL_TEXT = ("Information not found in the selected document. "
                "The available material does not answer this question.")
