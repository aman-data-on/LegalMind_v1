"""Where a deal stands — `AM-260`'s derived negotiation status (CLM R7, 2026-11-02).

A PURE function over facts the database already holds: version roles, when a version was
sent (`document_versions.sent_at`), the review of the latest version and the contract
decision on it. Nothing is stored and nothing writes a stage (`AM-260` r3).

Its own vocabulary, `NEGOTIATION_STAGE` (r2): never a value of the five legal state axes,
the Review lifecycle, `review_stage` (`AM-179`), ContractStatus or ConfigStatus (REC-06).

The first match wins:

```text
SIGNED           a FINAL_SIGNED version exists
READY_TO_SIGN    the latest version's contract decision is Sign as is / after our changes
ON_HOLD          ... or On hold
CLIENT_RETURNED  the latest version is the client's (CLIENT_MODIFIED) — our turn
WITH_CLIENT      the latest version was sent to the client
INTERNAL_REVIEW  the latest version's review is with a reviewer / Legal, or it is our
                 prepared reply and its Review is unfinished or holds an undecided
                 point (`AM-293` r1: such a reply cannot leave, so it is not ready)
READY_TO_SEND    the latest version is our prepared reply (reply_to), its Review
                 finished with nothing undecided, not yet sent
DRAFTING         otherwise (only our draft, not sent; or no version yet)
```

Do not sign is a sub-state of the record, not a stage, so it falls through.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NegotiationStage(StrEnum):
    DRAFTING = "DRAFTING"
    INTERNAL_REVIEW = "INTERNAL_REVIEW"
    WITH_CLIENT = "WITH_CLIENT"
    CLIENT_RETURNED = "CLIENT_RETURNED"
    READY_TO_SEND = "READY_TO_SEND"
    READY_TO_SIGN = "READY_TO_SIGN"
    SIGNED = "SIGNED"
    ON_HOLD = "ON_HOLD"


NEGOTIATION_STAGES: tuple[str, ...] = tuple(s.value for s in NegotiationStage)

_READY = {"SIGN_AS_IS", "SIGN_WITH_CHANGES"}


@dataclass(frozen=True)
class VersionFacts:
    version_number: int
    created_at: datetime
    role: str | None = None            # metadata.version_role
    sent_at: datetime | None = None
    reply_to: bool = False             # metadata.reply_to: our prepared reply (AM-251)


@dataclass(frozen=True)
class ReviewFacts:
    """The latest review of the LATEST version only — an older version's decision is
    superseded by the newer text."""
    in_review_since: datetime | None = None   # the active assignment (Send for review)
    outcome: str | None = None        # the current ContractOutcome; None once reopened
    outcome_at: datetime | None = None
    # AM-293 r1: the reply's Review finished with no undecided point. False — the
    # default, and the value without `review.view` — fails closed to With Legal.
    reply_cleared: bool = False


def derive_stage(created_at: datetime, versions: list[VersionFacts],
                 review: ReviewFacts | None = None) -> tuple[NegotiationStage, datetime]:
    """(stage, since). ``created_at`` is the contract's, when nothing else dates it."""
    signed = [v for v in versions if v.role == "FINAL_SIGNED"]
    if signed:
        return NegotiationStage.SIGNED, min(v.created_at for v in signed)
    if not versions:
        return NegotiationStage.DRAFTING, created_at
    latest = max(versions, key=lambda v: v.version_number)
    review = review or ReviewFacts()
    if review.outcome in _READY and review.outcome_at:
        return NegotiationStage.READY_TO_SIGN, review.outcome_at
    if review.outcome == "ON_HOLD" and review.outcome_at:
        return NegotiationStage.ON_HOLD, review.outcome_at
    if latest.role == "CLIENT_MODIFIED":
        return NegotiationStage.CLIENT_RETURNED, latest.created_at
    if latest.sent_at is not None:
        return NegotiationStage.WITH_CLIENT, latest.sent_at
    if review.in_review_since is not None:
        return NegotiationStage.INTERNAL_REVIEW, review.in_review_since
    if latest.reply_to:
        return (NegotiationStage.READY_TO_SEND if review.reply_cleared
                else NegotiationStage.INTERNAL_REVIEW), latest.created_at
    return NegotiationStage.DRAFTING, latest.created_at


def stage_payload(stage: NegotiationStage, since: datetime, now: datetime) -> dict:
    """What the API carries: the stage, when it began, and whole days in it."""
    return {"stage": stage.value, "since": since.isoformat(),
            "days": max(0, (now - since).days)}
