"""A client's changes, answered change by change — CLM Phase 1 (AB-150, 2026-11-02).

Three routes, each through `Guard` before anything is read (rule 18):

* ``GET /contracts/{id}/changes`` — every change from our previous version to the
  client's (`analysis.negotiation`), under the READ traversal: a contract out of scope
  is the same byte-identical 404 as one that does not exist (SEC-07).
* ``POST /contracts/{id}/changes/{row_key}/answers`` — keep ours, accept theirs, use
  our standard or write our wording (`AM-284`/`AM-285`), by the owner, a collaborator,
  the department Lead (`AM-259` r2) or a `legal.decision` holder on a contract sent to
  Legal, assigned to them or created by them (`AM-288` r2), kept with its history
  (`AM-253`). Our wording on a measured point is decided BEFORE the reply: the answer
  records an APPROVE_CUSTOMIZATION Legal Decision carrying the wording's SHA-256 on
  every Evaluation of the client's clause, second person per `requires_second_person`
  or `AM-289` (then "Waiting for approval"). Client paper first (`AM-290`): with no
  version of ours before the client's, the rows are that version's Findings.
  Accepting a change a holder must decide is refused (`AM-250` r2): where the change
  carries an Evaluation that is a Legal Decision, recorded through
  ``POST /evaluations/{id}/decisions`` by a holder of `legal.decision`, its second
  person unchanged; once an EFFECTIVE decision accepts every Evaluation (`AM-281` r3),
  the answer may record "accept theirs". Where it carries none, a `legal.decision`
  holder who can read the contract records "accept theirs" as an answer, reason
  required, audited (`AM-281` r1/r2) — never a Legal Decision. Other answers are not
  audited one by one — the rows are the history (`AM-253` r8').
* ``POST /contracts/{id}/changes/formatting/keep-ours`` — "keep ours" on the named
  formatting-only rows (the deal owner's route) in one write, all or none.
* ``POST /contracts/{id}/changes/accept`` — "accept theirs" on the named rows that are
  all "Better for us" or all "No change for us" (`AM-299` r2), by the deal owner, in one
  write, all or none, each with that effect as its reason, audited. A worse-for-us change
  is never among them: only those go to Legal. A holder reopens one by answering again.
* ``POST /document-versions/{id}/mark-sent`` — when one of OUR versions went to the
  client (`AM-260`), once, by the owner, a collaborator or the Lead, audited; refused
  for a reply with an undecided point (`AM-293` r1, 409 REPLY_UNDECIDED).
* ``POST /contracts/{id}/reply`` — our reply (R6, `AM-251` r2): the client's DOCX with
  our recorded answers as tracked changes, ingested as our next version, audited
  `document.reply_prepared` (`AM-253` r8'); a change that cannot be written is listed,
  and left to a person only when the caller names it (AB-151);
  ``GET /document-versions/{id}/reply-pdf`` (or ``…/pdf``, also a created contract's)
  its PDF, made by the worker (`AM-293` r2; 202 while rendering) — gated like
  ``…/content`` (`AM-293` r1).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Path, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, update

from legalmind import notifications
from legalmind.analysis import document_comparison, negotiation
from legalmind.analysis.service import AnalysisNotPermitted
from legalmind.analysis.version_comparison import ComparisonNotPossible
from legalmind.api.angles import ACCEPT_FAVOURABLE
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import attachment_headers, data
from legalmind.api.errors import (
    BusinessRuleRejected,
    Conflict,
    LegalDecisionRequired,
    ReplyUndecided,
)
from legalmind.api.routers.decisions import _advance_if_resolved
from legalmind.api.routers.documents import CHANGED_BY_A_COLLEAGUE, download_name
from legalmind.api.routers.reviews import open_review, with_legal
from legalmind.api.schemas import (
    AcceptByEffect,
    FormattingKeepOurs,
    NegotiationAnswer,
    PackageRequest,
    ReplyRequest,
)
from legalmind.api.serializers import serialize_document_version
from legalmind.api.storage import get_storage
from legalmind.db import models as M
from legalmind.db.lookup import contract_signed, must_exist
from legalmind.domain.client_profile import FINAL_SIGNED
from legalmind.domain.enums import DecisionType, FindingStatus, ProcessingStatus
from legalmind.domain.user_status import ACCEPTABLE
from legalmind.drafting import (
    blank,
    clean,
    effective,
    instrument,
    pdf,
    preflight,
    publish,
    render_contract,
    special_conditions,
)
from legalmind.drafting import model as model_
from legalmind.drafting.reply_docx import ReplyError, apply_reply, placeable, unplaceable
from legalmind.drafting.reply_plan import Answer, clause_text, reply_rows, sha256
from legalmind.evaluation.workflow import (
    carried_forward,
    current_decision,
    derive_finding_status,
    effective_decision,
    second_person_needed,
)
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import StorageBackend
from legalmind.ingestion.validation import DOCX_MIME, PDF_MIME
from legalmind.mapping.service import load_clauses
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import require_contract_negotiable
from legalmind.security.errors import NotVisible, SecurityError
from legalmind.security.resolver import has_permission
from legalmind.worker.dispatch import dispatch_analysis, dispatch_indexing, dispatch_pdf
from legalmind.workflow.decisions import record_decision, wording_tag
from legalmind.workflow.escalation import is_escalated
from legalmind.workflow.review_progress import review_progress

router = APIRouter(tags=["negotiation"], route_class=CommitBeforeResponse)

#: `AM-299`: the reason an acceptance records when the person gives none — the effect
EFFECT_REASON = {negotiation.POSITIVE: "Better for us",
                 negotiation.NEUTRAL: "No change for us",
                 # AM-306: audited as a fallback acceptance — inside our standard
                 negotiation.FALLBACK: "Fallback — within what we can offer"}

#: the client's change on a point a holder decides: who may accept it, in fixed words
HOLDER_DECIDES = ("Accepting this change is a Legal Decision — a person with the right "
                  "decides it from the finding.")


def _pair(guard: Guard, contract: M.Contract, from_version: int | None,
          to_version: int | None) -> tuple[M.DocumentVersion | None, M.DocumentVersion]:
    """The two versions compared: by default the latest and the latest of OURS before it
    (`negotiation.our_previous`), else the one before it. None before the client's own
    paper when no version of ours precedes it (`AM-290`: client paper first)."""
    versions = list(guard.db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number)).scalars())
    by_number = {v.version_number: v for v in versions}
    after = by_number.get(to_version) if to_version is not None else (
        versions[-1] if versions else None)
    if after is None:
        raise BusinessRuleRejected("This contract has no such version.")
    if from_version is None:
        if negotiation.our_previous(versions, after) is None and (
                not negotiation.is_ours(after)
                or blank.link(guard.db, contract, after) is not None):
            return None, after
        before = negotiation.our_previous(versions, after) or next(
            (v for v in reversed(versions) if v.version_number < after.version_number),
            None)
        if before is None:
            raise BusinessRuleRejected(
                "This contract has one version only — there is nothing to compare yet.")
        return before, after
    if from_version not in by_number:
        raise BusinessRuleRejected("This contract has no such version.")
    return by_number[from_version], after


def _changes(guard: Guard, contract: M.Contract, from_version: int | None,
             to_version: int | None, *, counting: bool = False
             ) -> tuple[dict, M.DocumentVersion | None, M.DocumentVersion]:
    """``counting`` (`deal_counts`, M4): only what the counts read — an answered row's
    holder state and offers are skipped; never used for a write or a page."""
    before, after = _pair(guard, contract, from_version, to_version)
    # AM-302: paper made from our blank template is compared with that template
    template = blank.link(guard.db, contract, after) if before is None else None
    try:
        listed = negotiation.paper_first(
            guard.db, contract, after, legal_position=guard.sees_legal_position) \
            if before is None and template is None else negotiation.changes(
                guard.db, contract, before, after,
                legal_position=guard.sees_legal_position, template=template,
                clause_loader=effective.effective_clauses)          # AM-307
    except ComparisonNotPossible as exc:
        raise BusinessRuleRejected(str(exc)) from exc
    for change in listed["changes"]:
        if counting:
            if change["route"] == negotiation.HOLDER and change.get("answer") is None:
                change["holder_accepted"] = _holder_accepted(guard, change, before, after)
            continue
        if change["route"] == negotiation.FAVOUR:
            change["favour_reason"] = ACCEPT_FAVOURABLE        # AM-239, its own words
        if change["route"] == negotiation.HOLDER:
            change["unmeasured"] = _unmeasured(change)
            change["holder_accepted"] = _holder_accepted(guard, change, before, after)
        change["waiting_for_approval"] = _waiting(guard, change)
        change["offers"] = _offers(change)
    return listed, before, after


def _approves(db, ev: M.Evaluation, digest: str) -> bool:
    """An EFFECTIVE APPROVE_CUSTOMIZATION on ``ev`` carrying this wording's hash — in
    the decision itself, or in the one it co-signs (F-2 / `AM-289`)."""
    d = effective_decision(db, ev, escalated=is_escalated(db, ev.finding_id))
    if d is None or d.decision_type is not DecisionType.APPROVE_CUSTOMIZATION:
        return False
    tag = wording_tag(digest)
    if tag in d.justification:
        return True
    prev = db.execute(select(M.LegalDecision).where(
        M.LegalDecision.evaluation_id == ev.id,
        M.LegalDecision.version_number == d.version_number - 1)).scalar()
    return (prev is not None and prev.decision_type is d.decision_type
            and tag in prev.justification
            and second_person_needed(db, ev, prev.decided_by))


def _to_decide(change: dict) -> list[str]:
    """The client's Evaluations a Legal Decision is recorded on: those whose point is not
    already Acceptable (as `_holder_accepted`) — every one when all are (fail closed)."""
    after = change["review"]["after"]
    ids = [e for f in after if f["user_status"] != ACCEPTABLE
           for e in f["evaluation_ids"]]
    return list(dict.fromkeys(ids or [e for f in after for e in f["evaluation_ids"]]))


def _their_evaluations(db, change: dict) -> list[M.Evaluation]:
    return [ev for e in _to_decide(change)
            if (ev := db.get(M.Evaluation, UUID(e))) is not None]


def _waiting(guard: Guard, change: dict) -> bool:
    """Our wording on a measured point whose Legal Decision is not effective yet —
    "Waiting for approval" (`AM-291` r1): no reply is prepared from it (`AM-284` r2)."""
    a = change.get("answer")
    if a is None or a["answer"] != "write_wording" or _no_finding(change):
        return False
    evs = _their_evaluations(guard.db, change)
    return not evs or not all(_approves(guard.db, ev, a["wording_sha256"]) for ev in evs)


def _replied_in(db, after: M.DocumentVersion) -> int | None:
    """The version number of our reply to ``after``, if one was prepared: that round is
    closed, and its answers are the record the reply was written from (`AM-251` r2)."""
    return db.execute(
        select(M.DocumentVersion.version_number)
        .where(M.DocumentVersion.contract_id == after.contract_id,
               (M.DocumentVersion.doc_metadata["reply_to"].astext == str(after.id))
               | (M.DocumentVersion.doc_metadata["package_of"].astext == str(after.id)))
        .order_by(M.DocumentVersion.version_number).limit(1)).scalar()


#: a holder's decision that lets the client's wording stand (`AM-250` r2)
_ACCEPTING = {DecisionType.ACCEPT_DEVIATION, DecisionType.NOT_APPLICABLE_TO_CONTRACT}


def _unmeasured(change: dict) -> bool:
    """No Evaluation on either side of the change: no standard measures it."""
    return not any(f["evaluation_ids"] for side in ("before", "after")
                   for f in change["review"][side])


def _no_finding(change: dict) -> bool:
    """No Evaluation on the CLIENT's side (`AM-281`): unmeasured, or a measured clause of
    ours the client deleted — nothing a Legal Decision could be recorded on, so a
    holder's answer, reason required and audited, is the record."""
    return not any(f["evaluation_ids"] for f in change["review"]["after"])


#: what a person may answer (presentation only — `answer_change` checks again)
_ALL_ANSWERS = ("keep_ours", "accept_theirs", "use_standard", "write_wording")


def _offers(change: dict) -> list[str]:
    """Paper first (coordinator ruling under the owner's delegation, AB-152): on a
    THEIRS row "Keep ours" IS our standard clause, offered only where a published clause
    anchors the row; with none, only Accept theirs and Write our wording."""
    if change["kind"] != negotiation.THEIRS_KIND:
        return list(_ALL_ANSWERS)
    if (change.get("anchor") or {}).get("clause_version_id"):
        return ["keep_ours", "accept_theirs", "write_wording"]
    return ["accept_theirs", "write_wording"]


def _left(before: M.DocumentVersion | None,
          change: dict) -> tuple[UUID | None, str | None]:
    """A row's left side as stored: our version, or — client paper first — our template
    clause's key, or nothing (`AM-290` r1/r2)."""
    if before is not None:
        return before.id, None
    return None, (change.get("anchor") or {}).get("left_key")


def _current_choice(guard: Guard, before: M.DocumentVersion | None,
                    after: M.DocumentVersion, row_key: str) -> M.ComparisonChoice | None:
    C = M.ComparisonChoice
    return guard.db.execute(
        select(C).where(C.left_version_id == before.id if before is not None
                        else C.left_version_id.is_(None),
                        C.right_version_id == after.id, C.row_key == row_key)
        .order_by(C.version_number.desc()).limit(1)).scalars().first()


def _holder_accepted(guard: Guard, change: dict, before: M.DocumentVersion | None,
                     after: M.DocumentVersion) -> bool:
    """Whether the client's wording may stand. Measured: every Evaluation on the
    returned clause that needs a decision — a point not already Acceptable, the same
    points the Changes tab offers to decide; a MATCH beside a deviation in one clause
    needs none — carries an EFFECTIVE Legal Decision that accepts it — co-signed
    where the standard requires a second person, and not answered before an active
    escalation (`AM-281` r3; `effective_decision`, never the bare current one).
    No Evaluation on the client's side (`AM-281` r1): the current answer is "accept
    theirs", recorded by a person who holds `legal.decision` now. Anything else is not
    accepted (rule 15)."""
    db = guard.db
    if _no_finding(change):
        choice = _current_choice(guard, before, after, change["row_key"])
        return (choice is not None
                and choice.choice == negotiation.ANSWERS["accept_theirs"]
                and has_permission(db, choice.decided_by, P.LEGAL_DECISION))
    ids = {e for f in change["review"]["after"] if f["user_status"] != ACCEPTABLE
           for e in f["evaluation_ids"]}
    if not ids:             # routed to Legal for another reason: no decision opens it
        return False
    for e in ids:
        ev = db.get(M.Evaluation, UUID(e))
        d = None if ev is None else effective_decision(
            db, ev, escalated=is_escalated(db, ev.finding_id))
        if d is None and ev is not None and _carried_acceptance(db, ev.finding_id):
            continue
        if d is None or d.decision_type not in _ACCEPTING:
            return False
    return True


def _carried_acceptance(db, finding_id: UUID) -> bool:
    """`AM-323` r2: Legal's acceptance on an earlier version, carried to this one on the
    same words (`AM-317` r7 as `AM-321` re-checks it), lets the client's wording stand as
    the decision itself would — only while the Finding still derives RESOLVED by it."""
    carried = carried_forward(db, finding_id)
    finding = db.get(M.Finding, finding_id)
    if carried is None or finding is None or carried.get("decision_type") not in {
            t.value for t in _ACCEPTING}:
        return False
    escalated = is_escalated(db, finding_id)
    return derive_finding_status(db, finding, escalated=escalated) \
        is FindingStatus.RESOLVED


def _reader(guard: Guard, contract: M.Contract,
            after: M.DocumentVersion) -> tuple[int | None, bool]:
    """(our reply's version number, if prepared; whether THIS reader may answer) —
    presentation only, every write checks again."""
    replied_in = _replied_in(guard.db, after)
    try:
        require_contract_negotiable(guard.db, guard.user_id, contract.id)
        writer = contract.archived_at is None and guard.negotiation_permission(
            contract, P.CONTRACT_UPDATE) in guard.permissions \
            and not contract_signed(guard.db, contract.id)     # as the write's 409
    except NotVisible:
        writer = False
    return replied_in, writer


def _mine(change: dict, *, can_decide: bool, can_answer: bool) -> bool:
    """A change left for THIS reader — the Changes tab's "Yours to answer": Legal's are
    the holder's rows; anyone else's, the deal owner's routes and a holder change Legal
    has accepted. Counted by who answers, never by who may."""
    if change.get("answer") is not None:
        return False
    if can_decide:
        return change["route"] == negotiation.HOLDER
    return can_answer and (change["route"] != negotiation.HOLDER
                           or bool(change.get("holder_accepted")))


def client_version(versions: list[M.DocumentVersion]) -> M.DocumentVersion | None:
    """The client's version this round answers: the latest when it is theirs, the one
    our prepared reply answers when the latest is that reply; else none (no round)."""
    if not versions:
        return None
    latest = max(versions, key=lambda v: v.version_number)
    to = negotiation.answers(latest.doc_metadata)
    if to and not latest.sent_at:
        return next((v for v in versions if str(v.id) == to), None)
    role = (latest.doc_metadata or {}).get("version_role")
    return None if negotiation.is_ours(latest) or role == FINAL_SIGNED else latest


def deal_counts(guard: Guard, contracts: list[M.Contract]) -> dict[UUID, dict]:
    """`AM-291` — the two nouns, counted ONCE for every screen (home, To-do, the contract
    page, the Changes tab): CHANGES are the client's edits in the open round, POINTS the
    gaps against our standard still undecided on the latest version. Each key is present
    only when its source is readable (`document.view` / `review.view`) — absent, never 0.

    ponytail: one change list per contract in a live round (~0.4 s each); bounded by a
    list page. A stored per-version tally is the upgrade if the list grows slow."""
    db, out = guard.db, {}
    can_decide = P.LEGAL_DECISION in guard.permissions
    for contract in contracts:
        counts: dict[str, int] = {}
        versions = list(db.execute(select(M.DocumentVersion).where(
            M.DocumentVersion.contract_id == contract.id)).scalars())
        latest = max(versions, key=lambda v: v.version_number, default=None)
        if latest is not None and P.REVIEW_VIEW in guard.permissions:
            review = negotiation._latest_review(db, latest)
            if review is not None and review.status in negotiation._ANALYSED:
                n = review_progress(db, review,
                                    legal_position=guard.sees_legal_position)["to_decide"]
                mine = can_decide and db.execute(select(M.Review.id).where(
                    M.Review.id == review.id, with_legal(guard.user_id))).first()
                counts.update(points_open=n, points_for_me=n if mine else 0)   # B11
        theirs = (client_version(versions)
                  if P.DOCUMENT_VIEW in guard.permissions else None)
        if theirs is not None:
            try:
                listed, _, after = _changes(guard, contract, None, theirs.version_number,
                                            counting=True)
            except BusinessRuleRejected:
                listed = None           # one version, unreadable or still processing
            if listed is not None:
                replied_in, writer = _reader(guard, contract, after)
                rows = listed["changes"]
                counts.update(
                    changes_total=len(rows),
                    changes_left=sum(c.get("answer") is None for c in rows),
                    # answers our reply must carry back to the client (verifier item 1):
                    # none — the client's version is the agreed text, final copy next
                    changes_ours=sum(bool(c.get("answer")) and c["answer"]["answer"]
                                     != "accept_theirs" for c in rows),
                    changes_left_for_me=sum(_mine(
                        c, can_decide=can_decide,
                        can_answer=writer and replied_in is None) for c in rows))
        out[contract.id] = counts
    return out


_FROM = Query(None, ge=1, description="our version number (default: the one before)")
_TO = Query(None, ge=1, description="the client's version number (default: the latest)")


@router.get("/contracts/{contract_id}/changes")
def list_changes(contract_id: UUID, from_version: int | None = _FROM,
                 to_version: int | None = _TO,
                 guard: Guard = Depends(get_guard)) -> dict:
    """Every change between two versions of this contract (R1–R4). `can_answer` and
    `can_decide` say what THIS reader may do — presentation only; every write checks
    again server-side, without the audited refusal a reader opening a page is not.
    A collaborator reads this (`AM-280` r1)."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    listed, before, after = _changes(guard, contract, from_version, to_version)
    _in_package(guard, before, after, listed)                       # AM-308
    replied_in, writer = _reader(guard, contract, after)
    # can_send: this reader may record our version as sent (`mark_sent`'s own check),
    # which outlives the round — answering closes once the reply is prepared.
    # can_write_wording: `AM-284` r1 — presentation only, the write checks again
    return data({**listed, "replied_in": replied_in,
                 "can_answer": writer and replied_in is None, "can_send": writer,
                 "can_decide": P.LEGAL_DECISION in guard.permissions,
                 "can_write_wording": writer and replied_in is None
                 and P.LEGAL_APPROVE_CUSTOMIZATION in guard.permissions})


class NoStandardClause(Conflict):
    """409 — "Use our standard" with no published template clause realising this
    point's requirement (`AM-284` r5), or one whose text needs the contract's own
    values (slots, tables, images: slices S5/S6)."""

    code = "NO_STANDARD_CLAUSE"


class NothingOfOurs(Conflict):
    """409 — "Keep ours" on the client's own paper where no published clause of ours
    anchors the point (`AM-290` r2, as ruled for AB-152): accept theirs or write our
    wording."""

    code = "NOTHING_OF_OURS"


def _standard(guard: Guard, change: dict, body: NegotiationAnswer) -> M.ClauseVersion:
    """The published clause "Use our standard" inserts, chosen in code by its
    `realises` codes against the change's requirement codes (`AM-284` r5); a named
    ``clause_version_id`` must be that one."""
    codes = {f["requirement_code"] for side in ("before", "after")
             for f in change["review"][side]}
    cv = negotiation.realising_clause(guard.db, codes)
    if cv is None or (body.clause_version_id not in (None, cv.id)):
        raise NoStandardClause("no published template clause for this point yet")
    if clause_text(cv) is None:
        raise NoStandardClause("our standard clause for this point needs this contract's "
                               "own values — use it from the template")
    return cv


def _decide_wording(guard: Guard, contract: M.Contract, change: dict, digest: str,
                    reason: str) -> None:
    """`AM-284` r2: the wording is decided BEFORE the reply — an APPROVE_CUSTOMIZATION
    on every Evaluation of the client's clause, carrying the wording's SHA-256, through
    `record_decision` (its own checks, second person and `AM-289` included). An
    Evaluation already approving this wording, or holding the caller's own pending
    signature on it, is not decided twice. Only called with at least one Evaluation —
    none is the `AM-281` path."""
    db = guard.db
    evs = _their_evaluations(db, change)
    tag = wording_tag(digest)
    reviews: dict[UUID, M.Review] = {}
    for ev in evs:
        cur = current_decision(db, ev.id)
        if _approves(db, ev, digest) or (
                cur is not None and cur.decided_by == guard.user_id
                and cur.decision_type is DecisionType.APPROVE_CUSTOMIZATION
                and tag in cur.justification):
            continue
        record_decision(db, actor_id=guard.user_id, evaluation_id=ev.id,
                        decision_type=DecisionType.APPROVE_CUSTOMIZATION,
                        justification=f"{reason} {tag}", request_id=guard.request_id)
        finding = db.get(M.Finding, ev.finding_id)
        if finding is not None and (review := db.get(M.Review, finding.review_id)):
            reviews[review.id] = review
    for review in reviews.values():
        _advance_if_resolved(guard, review)


@router.post("/contracts/{contract_id}/changes/{row_key}/answers", status_code=201)
def answer_change(contract_id: UUID, body: NegotiationAnswer,
                  row_key: str = Path(..., max_length=200),
                  from_version: int | None = _FROM, to_version: int | None = _TO,
                  guard: Guard = Depends(get_guard)) -> dict:
    """Keep ours, accept theirs, use our standard or write our wording (`AM-253`,
    `AM-284`). A new answer is a new row; a stale `expected_version` is 409, and an
    answer replacing a colleague's tells them (`ANSWER_CHANGED_BY_COLLEAGUE`).

    * accept theirs, with an Evaluation on the client's clause — 403
      LEGAL_DECISION_REQUIRED until an effective Legal Decision accepts every one
      (`AM-250` r2, `AM-281` r3); with none — unmeasured, or a measured clause of ours
      the client deleted — a `legal.decision` holder who can read the contract records
      it as an answer, reason required, audited (`AM-281` r1/r2), never a Legal
      Decision;
    * write our wording — holders of `legal.approve_customization` only (403), reason
      required; with an Evaluation on the client's clause: an APPROVE_CUSTOMIZATION
      carrying the wording's SHA-256 is recorded on it in this request (`AM-284` r2 —
      "Waiting for approval" until effective); with none (the deleted clause too): no
      Evaluation to decide on, so the holder's answer with its reason is the record,
      audited — the `AM-281` path `AM-284` r2 names;
    * use our standard — the published clause realising the point (409
      NO_STANDARD_CLAUSE otherwise);
    * keep ours on the client's own paper — our standard clause where a published one
      anchors the row (recorded as "use our standard"); with none, 409 NOTHING_OF_OURS
      (`AM-290`, as ruled for AB-152).

    ``internal_note`` is stored and shown only to holders of `legal_position.view`
    (`AM-285` r3) — never in the audit trail, a notification or the reply."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    _lock(guard, contract)        # M-3: never between a package's read and its write
    listed, before, after = _changes(guard, contract, from_version, to_version)
    change = next((c for c in listed["changes"] if c["row_key"] == row_key), None)
    if change is None:
        raise NotVisible("change not found")
    # L6: a round the client has since replaced (a later version of theirs) is closed
    later = guard.db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract.id,
        M.DocumentVersion.version_number > after.version_number)).scalars()
    if any(not negotiation.is_ours(v) for v in later):
        raise Conflict("This is not the client's latest version — answer the changes in "
                       "their latest version.")
    if body.answer == "keep_ours" and change["kind"] == negotiation.THEIRS_KIND:
        if "keep_ours" not in change["offers"]:
            raise NothingOfOurs("We have no standard clause for this point, so there is "
                                "nothing of ours to keep — accept the client's wording "
                                "or write our wording.")
        body = body.model_copy(update={"answer": "use_standard"})   # ours IS the standard
    if _replied_in(guard.db, after) is not None:
        raise Conflict("our reply to this version is already prepared — its answers are "
                       "the record it was written from; answer the client's next version")
    no_finding = _no_finding(change)
    holder_answer = (body.answer == "accept_theirs"
                     and change["route"] == negotiation.HOLDER and no_finding
                     and P.LEGAL_DECISION in guard.permissions)
    wording = body.answer == "write_wording"
    if holder_answer:
        if contract.archived_at is not None:
            raise Conflict("this contract is archived; restore it to make changes")
        if not body.reason:
            raise BusinessRuleRejected(
                "say why the client's wording may stand — no standard measures it, so "
                "your reason is the record")
    else:
        guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
        if (body.answer == "accept_theirs" and change["route"] == negotiation.HOLDER
                and not change["holder_accepted"]):
            raise LegalDecisionRequired(HOLDER_DECIDES)
    if wording:
        guard.additional_permission(P.LEGAL_APPROVE_CUSTOMIZATION,
                                    entity_type="contract", entity_id=contract.id)
        if not body.reason:
            raise BusinessRuleRejected("say why our wording — your reason is the record "
                                       "of the decision")
    if body.answer == "accept_theirs" and not body.reason \
            and change["effect_for_us"] in EFFECT_REASON:
        body = body.model_copy(update={"reason": EFFECT_REASON[change["effect_for_us"]]})
    standard = _standard(guard, change, body) if body.answer == "use_standard" else None
    digest = sha256(body.wording) if body.wording is not None else None
    replaced = _current_choice(guard, before, after, row_key)
    try:
        document_comparison.write_choices(
            guard.db, _left(before, change), (after.id, None),
            {row_key: negotiation.ANSWERS[body.answer]}, guard.user_id,
            reason=body.reason, expected={row_key: body.expected_version},
            extra={"wording": body.wording, "wording_sha256": digest,
                   "clause_version_id": standard.id if standard else None,
                   "client_note": body.client_note, "internal_note": body.internal_note})
    except document_comparison.ChoiceChanged as exc:
        raise Conflict(CHANGED_BY_A_COLLEAGUE) from exc
    except document_comparison.ComparisonNotPossible as exc:
        raise BusinessRuleRejected(str(exc)) from exc
    if wording and not no_finding:
        assert digest is not None and body.reason is not None
        _decide_wording(guard, contract, change, digest, body.reason)
    written = _current_choice(guard, before, after, row_key)
    if (replaced is not None and written is not None and written.id != replaced.id
            and replaced.decided_by != guard.user_id):
        notifications.notify(guard.db, [replaced.decided_by],
                             notifications.ANSWER_CHANGED_BY_COLLEAGUE, contract,
                             actor_id=guard.user_id)
    if (holder_answer or (wording and no_finding)) and written is not None and (
            replaced is None or written.id != replaced.id):
        # AM-285 r3: never the internal note in the trail
        audit.record(guard.db, action=audit.NEGOTIATION_HOLDER_ANSWERED,
                     entity_type="contract", entity_id=contract.id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     after={"row_key": row_key, "answer": body.answer,
                            "reason": body.reason, "wording_sha256": digest,
                            "from_version_id": str(before.id) if before else None,
                            "to_version_id": str(after.id),
                            "answer_version": written.version_number})
    line = negotiation.answer_line(guard.db, contract, before, after, row_key,
                                   legal_position=guard.sees_legal_position)
    return data({"row_key": row_key, **line,
                 "waiting_for_approval": _waiting(guard, {**change, **line})})


@router.post("/contracts/{contract_id}/changes/formatting/keep-ours", status_code=201)
def keep_ours_on_formatting(contract_id: UUID, body: FormattingKeepOurs,
                            from_version: int | None = _FROM,
                            to_version: int | None = _TO,
                            guard: Guard = Depends(get_guard)) -> dict:
    """"Keep ours" on many formatting-only changes at once (CLM page 3): the deal
    owner's route (`FORMATTING_ONLY`), so the same check as one answer, and ONE
    `write_choices` call — all or none. Every named row must be an unanswered
    formatting-only change of this pair; anything else (a colleague answered one
    first, a legal row smuggled in) refuses the whole request, nothing written."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    _lock(guard, contract)        # M-3: never between a package's read and its write
    listed, before, after = _changes(guard, contract, from_version, to_version)
    if _replied_in(guard.db, after) is not None:
        raise Conflict("our reply to this version is already prepared — its answers are "
                       "the record it was written from; answer the client's next version")
    guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    rows = {c["row_key"]: c for c in listed["changes"]}
    keys = list(dict.fromkeys(body.row_keys))
    for key in keys:
        change = rows.get(key)
        if change is None or change["route_reason"] != negotiation.FORMATTING_ONLY:
            raise BusinessRuleRejected(
                "only formatting-only changes are answered together")
        if _current_choice(guard, before, after, key) is not None:
            raise Conflict(CHANGED_BY_A_COLLEAGUE)
    try:
        document_comparison.write_choices(
            guard.db, (before.id if before else None, None), (after.id, None),
            dict.fromkeys(keys, negotiation.ANSWERS["keep_ours"]), guard.user_id,
            expected=dict.fromkeys(keys, 0))
    except document_comparison.ChoiceChanged as exc:
        raise Conflict(CHANGED_BY_A_COLLEAGUE) from exc
    except document_comparison.ComparisonNotPossible as exc:
        raise BusinessRuleRejected(str(exc)) from exc
    line = negotiation.answer_lines(guard.db, contract, before, after,
                                    legal_position=guard.sees_legal_position)
    return data({"rows": [{"row_key": k, **line(k), "waiting_for_approval": False}
                          for k in keys]})


@router.post("/contracts/{contract_id}/changes/accept", status_code=201)
def accept_by_effect(contract_id: UUID, body: AcceptByEffect,
                     from_version: int | None = _FROM, to_version: int | None = _TO,
                     guard: Guard = Depends(get_guard)) -> dict:
    """"Accept all with no change for us" (`AM-299` r2, narrowed by `AM-317` r2 to
    formatting-only changes):
    the deal owner's routes, so the same check as one answer, and ONE `write_choices`
    call — all or none. Every named row must be an unanswered change of this pair whose
    `effect_for_us` is the one named; anything else (a colleague answered one first, a
    worse-for-us row among them) refuses the whole request, nothing written. Each row
    records who accepted it and, as its reason, the effect; audited once."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    _lock(guard, contract)        # M-3: never between a package's read and its write
    listed, before, after = _changes(guard, contract, from_version, to_version)
    if _replied_in(guard.db, after) is not None:
        raise Conflict("our reply to this version is already prepared — its answers are "
                       "the record it was written from; answer the client's next version")
    guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    rows = {c["row_key"]: c for c in listed["changes"]}
    keys = list(dict.fromkeys(body.row_keys))
    for key in keys:
        change = rows.get(key)
        # AM-317 r2: together only "No change for us" — the same words (formatting
        # only); a better-for-us or fallback figure is answered one by one
        if change is None or change["effect_for_us"] != body.effect \
                or body.effect != negotiation.NEUTRAL:
            raise BusinessRuleRejected(
                "only changes with no change for us — formatting, punctuation or "
                "spacing only — are accepted together; answer every other one by itself")
        if _current_choice(guard, before, after, key) is not None:
            raise Conflict(CHANGED_BY_A_COLLEAGUE)
    reason = EFFECT_REASON[body.effect]
    try:
        document_comparison.write_choices(
            guard.db, (before.id if before else None, None), (after.id, None),
            dict.fromkeys(keys, negotiation.ANSWERS["accept_theirs"]), guard.user_id,
            reason=reason, expected=dict.fromkeys(keys, 0))
    except document_comparison.ChoiceChanged as exc:
        raise Conflict(CHANGED_BY_A_COLLEAGUE) from exc
    except document_comparison.ComparisonNotPossible as exc:
        raise BusinessRuleRejected(str(exc)) from exc
    audit.record(guard.db, action=audit.NEGOTIATION_ACCEPTED_BY_EFFECT,
                 entity_type="contract", entity_id=contract.id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 after={"effect": body.effect, "reason": reason, "row_keys": keys,
                        "from_version_id": str(before.id) if before else None,
                        "to_version_id": str(after.id)})
    line = negotiation.answer_lines(guard.db, contract, before, after,
                                    legal_position=guard.sees_legal_position)
    return data({"rows": [{"row_key": k, **line(k), "waiting_for_approval": False}
                          for k in keys]})


@router.post("/document-versions/{document_version_id}/mark-sent")
def mark_sent(document_version_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Record that one of OUR versions went to the client (`AM-260` r1) — by the owner,
    a collaborator or the Lead (`AM-259` r2), once: a version is sent at one moment, so
    a second call — or a concurrent one — is 409 rather than a moved date (one
    conditional UPDATE decides). The client's own version is never "sent" by us."""
    version = guard.document_version(document_version_id, P.CONTRACT_UPDATE,
                                     negotiable=True)
    if not negotiation.is_ours(version):
        raise BusinessRuleRejected("this is the client's version — record as sent a "
                                   "version we prepared")
    _require_decided(guard, version)
    D = M.DocumentVersion
    marked = guard.db.execute(
        update(D).where(D.id == version.id, D.sent_at.is_(None))
        .values(sent_at=datetime.now(UTC), sent_by=guard.user_id)
        .returning(D.id).execution_options(synchronize_session=False)).first()
    if marked is None:
        raise Conflict("this version is already recorded as sent")
    guard.db.refresh(version)
    audit.record(guard.db, action=audit.DOCUMENT_VERSION_SENT,
                 entity_type="document_version", entity_id=version.id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 after={"sent_at": version.sent_at.isoformat(),
                        "version_number": version.version_number})
    return data(serialize_document_version(version))


# ------------------------------------------------------------- R6: prepare our reply
class ReplyNotReady(Conflict):
    """409 — a change is unanswered, or an accepted one still needs a holder."""

    code = "REPLY_NOT_READY"


class ReplyNeedsWordFile(Conflict):
    """409 — the client's version is not a Word file; a reply is their DOCX marked."""

    code = "REPLY_NEEDS_WORD_FILE"


class ReplyNotApplied(Conflict):
    """409 — some answers cannot be written exactly into the client's file (rule 15).
    ``manual_rows`` lists every one; retried naming exactly those, the reply is
    prepared without them (AB-151)."""

    code = "REPLY_NOT_APPLIED"

    def __init__(self, message: str, manual_rows: list[dict]) -> None:
        super().__init__(message)
        self.extra = {"manual_rows": manual_rows}


def _where(change: dict) -> str:
    """Where a change is, in a reader's words (N17): its clause number; a real heading
    (mixed case, more than one word); else "the opening text" — never a raw first line
    ("AND", "WHEREAS", a title in capitals)."""
    clause = change["clause"]
    if clause["number"]:
        return f"clause {clause['number']}"
    heading = (clause["heading"] or "").strip()
    if len(heading.split()) > 1 and not heading.isupper():
        return heading
    return "the opening text"


def _places(changes: list[dict], limit: int = 8) -> str:
    """The places of these changes, each said once, in order (N17)."""
    seen: list[str] = []
    for c in changes:
        if (where := _where(c)) not in seen:
            seen.append(where)
    return ", ".join(seen[:limit]) + (", …" if len(seen) > limit else "")


def _require_decided(guard: Guard, version: M.DocumentVersion) -> None:
    """`AM-293` r1: our prepared reply never leaves while its Review has an undecided
    point or has not finished (409 REPLY_UNDECIDED with the open points)."""
    gate = negotiation.reply_open_points(guard.db, version)
    if gate is not None:
        raise ReplyUndecided(gate)


def _reply_blockers(changes: list[dict]) -> str | None:
    """What still stops the reply, in plain words — or None."""
    open_ = [c for c in changes if c["answer"] is None]
    undecided = [c for c in changes if c["answer"] is not None
                 and c["answer"]["answer"] == "accept_theirs"
                 and c["route"] == negotiation.HOLDER and not c["holder_accepted"]]
    waiting = [c for c in changes if c["waiting_for_approval"]]       # AM-284 r2
    parts = []
    if open_:
        parts.append(f"{len(open_)} change{'s' if len(open_) != 1 else ''} not answered "
                     f"yet ({_places(open_)})")
    if undecided:
        parts.append(f"{len(undecided)} accepted change"
                     f"{'s need' if len(undecided) != 1 else ' needs'} a Legal Decision "
                     f"({_places(undecided)})")
    if waiting:
        parts.append(f"{len(waiting)} answer{'s' if len(waiting) != 1 else ''} with our "
                     f"wording {'wait' if len(waiting) != 1 else 'waits'} for approval "
                     f"({_places(waiting)})")
    return "; ".join(parts) + "." if parts else None


class PdfNotMade(SecurityError):
    """503 — the worker could not make this PDF (`AM-293` r2): LibreOffice missing or
    failing, or the contract's PDF failing its check. Said plainly; never a PyMuPDF
    copy instead (r3). The Word file stays downloadable."""

    status_code = 503
    code = "PDF_NOT_MADE"


def _review_reply(guard: Guard, version: M.DocumentVersion) -> M.Review | None:
    """Our reply is reviewed like any upload (`AM-251` r4): a Review on the latest
    published snapshot, analysed through the same `dispatch_analysis` as
    ``POST /reviews/{id}/analyze`` — inline without a broker, else queued once this
    request commits. None when nothing is published yet or the caller may not open a
    Review (the upload chain's own two quiet states); the reply stands either way."""
    contract = must_exist(guard.db.get(M.Contract, version.contract_id), "contracts row")
    # AM-288 r2: a lawyer's reply is reviewed too, on their `legal.decision`
    if guard.negotiation_permission(contract, P.REVIEW_CREATE) not in guard.permissions:
        return None
    snapshot = guard.db.execute(
        select(M.ConfigurationSnapshot).order_by(M.ConfigurationSnapshot.created_at.desc(),
                                                 M.ConfigurationSnapshot.id.desc())
        .limit(1)).scalar_one_or_none()
    if snapshot is None:
        return None
    review = open_review(guard, version, snapshot)
    try:
        dispatch_analysis(guard.db, review, actor_id=guard.user_id,
                          request_id=guard.request_id, after_commit=True)
    except AnalysisNotPermitted:
        pass                          # the Review states why, as after any upload
    return review


def _reply_document(guard: Guard, storage: StorageBackend, contract: M.Contract,
                    named_rows: list[str]) -> tuple[bytes, dict]:
    """Our reply's file (R6, `AM-251` r2) and what it was built from — shared by "Prepare
    our reply" and the final copy that applies the same answers (`AM-318`). Every 409 of
    the reply is raised here."""
    versions = list(guard.db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number)).scalars())
    if not versions or (versions[-1].doc_metadata or {}).get("version_role") \
            == "COMPANY_DRAFT":
        raise Conflict("the latest version is already ours — nothing to reply to")
    ours = negotiation.our_previous(versions, versions[-1])
    # AM-302: paper made from our blank template has the template as ours
    template = blank.link(guard.db, contract, versions[-1]) if ours is None else None
    if ours is None and template is None and negotiation.is_ours(versions[-1]):
        raise BusinessRuleRejected("no version of ours comes before the client's — "
                                   "there is nothing of ours to restore")
    # AM-290: no version of ours before the client's paper — the reply is built on it
    listed, before, after = _changes(guard, contract,
                                     ours.version_number if ours else None,
                                     versions[-1].version_number)
    if after.mime_type != DOCX_MIME:
        raise ReplyNeedsWordFile("The reply needs the client's Word file — their "
                                 "version is not a .docx, so it cannot carry our "
                                 "tracked changes.")
    blocked = _reply_blockers(listed["changes"])
    if blocked:
        raise ReplyNotReady(f"The reply cannot be prepared yet: {blocked}")
    source = storage.get(after.storage_key)
    answers = {c["row_key"]: _answer(guard, c["answer"]) for c in listed["changes"]}
    planned = reply_rows(guard.db, before, after, answers, source,
                         theirs_rows=listed["changes"] if before is None else None,
                         template=template)
    failed = {r.row_key: r.error for r in planned if r.error is not None}
    failed |= unplaceable(source, {r.row_key: r.edits for r in planned
                                   if r.error is None})
    # AM-284 r6: a note to the client is a comment where it belongs, or the row is a
    # person's — never dropped, never put on another paragraph (rule 15)
    client_notes = {r.row_key: r.note for r in planned if r.note is not None}
    placed = placeable(source, list(client_notes.values()))
    for key, note in client_notes.items():
        if note not in placed:
            failed.setdefault(key, ReplyError("the note to the client cannot be placed "
                                              "exactly", "ANCHOR_NOT_FOUND"))
    manual: list[dict] = [
        {"row_key": r.row_key, "clause": r.clause,
         "reason": f"{failed[r.row_key]} ({failed[r.row_key].code})"}
        for r in planned if r.row_key in failed]
    named = sorted(named_rows)
    if manual and named != sorted(m["row_key"] for m in manual):
        raise ReplyNotApplied(
            f"{len(manual)} answer{'s' if len(manual) != 1 else ''} cannot be written "
            "into the client's file automatically "
            f"({', '.join(m['clause'] for m in manual[:8])}"
            f"{', …' if len(manual) > 8 else ''}). Prepare the reply without them and "
            "restore them by hand, or accept the client's wording there.", manual)
    if not manual and named:
        raise BusinessRuleRejected("every answer can be written — prepare the reply "
                                   "without naming any change to restore by hand")
    spots = {r.row_key: r.spot for r in planned if r.row_key in failed and r.spot}
    notes = placeable(source, list(spots.values()))
    notes += [n for k, n in client_notes.items() if k not in failed]
    for m in manual:            # a place no paragraph locates exactly is listed only
        m["commented"] = spots.get(m["row_key"]) in notes
    try:
        reply = apply_reply(source, [e for r in planned if r.row_key not in failed
                                     for e in r.edits],
                            when=datetime.now(UTC), notes=notes)
    except ReplyError as exc:                    # pragma: no cover — dry-run above
        raise ReplyNotApplied(f"An answer could not be written into the client's file "
                              f"({exc.code}): {exc}", manual) from exc
    return reply, {"listed": listed, "before": before, "after": after,
                   "answers": answers, "failed": failed, "manual": manual}


@router.post("/contracts/{contract_id}/reply", status_code=201)
def prepare_reply(contract_id: UUID, body: ReplyRequest | None = Body(None),
                  guard: Guard = Depends(get_guard),
                  storage: StorageBackend = Depends(get_storage)) -> dict:
    """Our reply to the client's latest version (R6, `AM-251` r2): their own DOCX with
    our recorded answers as tracked changes by "LeapSwitch Legal", ingested as the next
    version — declared Company draft — and reviewed like any upload (`AM-251` r4),
    against OUR latest version before theirs.

    Refused (409) while a change is unanswered or an accepted change routed to a
    holder is not accepted (`AM-281`); a client PDF cannot carry tracked changes, so it
    is refused too. Where answers cannot be written exactly, 409 REPLY_NOT_APPLIED lists
    every one (`manual_rows`); naming exactly that list in ``manual_rows`` prepares the
    reply with every other answer written and a Word comment at each of those places —
    listed in the response and the audit event, never silently dropped (AB-151). The
    contract row is locked for the request, so two replies never race: the second
    finds the latest version already ours (409)."""
    contract = guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    _lock(guard, contract)
    reply, built = _reply_document(guard, storage, contract,
                                   (body or ReplyRequest()).manual_rows)
    before, after = built["before"], built["after"]
    answers, failed, manual = built["answers"], built["failed"], built["manual"]
    stem = (after.original_filename or "contract").rsplit(".", 1)[0]
    result = ingest_document(guard.db, storage, contract_id=contract.id,
                             uploaded_by=guard.user_id, data=reply,
                             filename=f"{stem} - our reply.docx", declared_mime=DOCX_MIME)
    version = result.document_version
    # client paper first: the client's own "source" is not carried onto our reply
    carried = {k: v for k, v in ((before or after).doc_metadata or {}).items()
               if k in ("source", "counterparty", "effective_date")
               and (before is not None or k != "source")}
    written = {k: a.kind for k, a in answers.items() if k not in failed}
    kept = sum(a == "keep_ours" for a in written.values())
    wording = sum(a == "write_wording" for a in written.values())
    standard = sum(a == "use_standard" for a in written.values())
    version.doc_metadata = {**(version.doc_metadata or {}), **carried,
                            "version_role": "COMPANY_DRAFT", "reply_to": str(after.id),
                            "reply_tracked": kept + wording + standard,
                            "reply_by_hand": [m["clause"] for m in manual]}
    guard.db.flush()
    accepted = sum(a.kind == "accept_theirs" for a in answers.values())
    audit.record(guard.db, action=audit.DOCUMENT_REPLY_PREPARED, entity_type="contract",
                 entity_id=contract.id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"document_version_id": str(version.id),
                        "version_number": version.version_number,
                        "reply_to": str(after.id), "file_hash": version.file_hash,
                        "kept_ours": kept, "accepted_theirs": accepted,
                        "our_wording": wording, "our_standard": standard,
                        "manual_rows": [{k: m[k] for k in ("row_key", "clause")}
                                        for m in manual]})
    dispatch_indexing(guard.db, version.id, request_id=guard.request_id)
    dispatch_pdf(guard.db, version, "reply", request_id=guard.request_id)
    review = _review_reply(guard, version)
    return data({
        "document_version": serialize_document_version(version),
        "review_id": str(review.id) if review else None,
        "kept_ours": kept, "accepted_theirs": accepted, "our_wording": wording,
        "our_standard": standard, "manual_rows": manual,
        "downloads": {"docx": f"/document-versions/{version.id}/content",
                      "pdf": f"/document-versions/{version.id}/reply-pdf"},
        # AM-293: the downloads open once this is null (the reply's own Review decided)
        "open_points": negotiation.reply_open_points(guard.db, version),
    })


def _answer(guard: Guard, a: dict) -> Answer:
    """A listed answer as the builder takes it: our standard's text read from its
    published clause now (`AM-284` r5); the wording with the hash it was stored under
    (r4). Never the internal note (`AM-285` r3)."""
    text = a.get("wording")
    if a["answer"] == "use_standard":
        cv = guard.db.get(M.ClauseVersion, UUID(a["clause_version_id"]))
        text = clause_text(cv) if cv is not None else None
    return Answer(a["answer"], text, a.get("wording_sha256"), a.get("client_note"))


@router.get("/document-versions/{document_version_id}/reply-pdf",
            responses={202: {"description": "the worker is still making the PDF"}})
@router.get("/document-versions/{document_version_id}/pdf",
            responses={202: {"description": "the worker is still making the PDF"}})
def download_pdf(document_version_id: UUID, guard: Guard = Depends(get_guard),
                 storage: StorageBackend = Depends(get_storage)) -> Response:
    """Our prepared reply's, or a created contract's, client PDF — the one the worker
    made by LibreOffice from the stored CLEAN DOCX (`AM-293` r2), served as stored.
    202 ``{"data": {"status": "rendering"}}`` while it is being made (a lost or failed
    render older than `pdf.STALE_S` is dispatched again); 503 PDF_NOT_MADE when it
    could not be. Gated like ``…/content`` (r1)."""
    version = guard.document_version_readable(document_version_id, P.DOCUMENT_DOWNLOAD)
    meta = version.doc_metadata or {}
    kind = "reply" if meta.get("reply_to") else (
        "contract" if guard.db.execute(select(M.ContractDraft.id).where(
            M.ContractDraft.document_version_id == version.id)).first()
        else "final" if meta.get("final_copy_of") else None)     # AM-318
    if kind is None or not storage.exists(version.storage_key):
        raise NotVisible("document content not available")
    _require_decided(guard, version)
    if version.mime_type == PDF_MIME:          # a final copy of the client's own PDF
        name = download_name(guard.db, version, "pdf")
        return Response(content=storage.get(version.storage_key),
                        media_type="application/pdf",
                        headers=attachment_headers(name, "final.pdf"))
    if pdf.stale(pdf.record(version)):
        dispatch_pdf(guard.db, version, kind, request_id=guard.request_id)
    rec = must_exist(pdf.record(version), "the PDF record")
    if rec["status"] == pdf.FAILED:
        raise PdfNotMade(f"The PDF could not be made: {rec['error']}. The Word file "
                         "can still be downloaded.")
    if rec["status"] == pdf.RENDERING:
        return JSONResponse(status_code=202, content=data({"status": "rendering"}),
                            headers={"Retry-After": "3"})
    return Response(content=storage.get(rec["storage_key"]),
                    media_type="application/pdf",
                    headers=attachment_headers(download_name(guard.db, version, "pdf"),
                                               f"{kind}.pdf"))


# ------------------------------------------------- AM-307: the final contract package
class PackageNotReady(Conflict):
    """409 — the final contract cannot be prepared yet; ``blockers`` names every
    reason (`AM-307`, fail closed)."""

    code = "PACKAGE_NOT_READY"

    def __init__(self, message: str, blockers: list[dict]) -> None:
        super().__init__(message)
        self.extra = {"blockers": blockers}


class StalePreview(Conflict):
    """409 — the answers changed since the dry run the caller confirmed."""

    code = "STALE_PREVIEW"


NO_AMENDMENT_TEMPLATE = "No approved amendment template yet."


class NoAmendmentTemplate(Conflict):
    """409 — "Prepare amendment" needs a published AMENDMENT template whose frame Legal
    approved (`AM-309`); none exists, and none is ever authored here (rules 7/21)."""

    code = "NO_AMENDMENT_TEMPLATE"


CHANGES_ONLY, RESTATED = "changes_only", "restated"


class AmendmentTemplateIncomplete(Conflict):
    """409 — the AMENDMENT template lacks a slot the changes-only instrument needs
    (`AM-310`); ``slots`` names each. Nothing is written in its place (rules 7/21)."""

    code = "AMENDMENT_TEMPLATE_INCOMPLETE"

    def __init__(self, message: str, slots: list[str]) -> None:
        super().__init__(message)
        self.extra = {"slots": slots}


def _incomplete(slots: list[str]) -> str:
    return (f"The amendment template lacks {', '.join(slots)}. Legal adds "
            f"{'it' if len(slots) == 1 else 'them'} to the template; LegalMind never "
            "writes them.")


def amendment_template(db) -> M.TemplateVersion | None:
    """The latest PUBLISHED template of type AMENDMENT — its frame words an amendment."""
    T = M.TemplateVersion
    return db.execute(select(T).where(T.doc_type == "AMENDMENT", T.status == "PUBLISHED")
                      .order_by(T.published_at.desc()).limit(1)).scalar_one_or_none()


def _lock(guard: Guard, contract: M.Contract) -> None:
    """The contract row lock every answer and every prepared version takes, so an answer
    is never committed while a reply or package is read and written over it (M-3)."""
    guard.db.execute(select(M.Contract.id).where(M.Contract.id == contract.id)
                     .with_for_update())


def _generated(db, version: M.DocumentVersion | None) -> M.ContractDraft | None:
    return None if version is None else db.execute(select(M.ContractDraft).where(
        M.ContractDraft.document_version_id == version.id)).scalar_one_or_none()


def _prior(db, version: M.DocumentVersion) -> list[dict]:
    """The entries of the final contract ``version`` is — or copies (an amendment's
    first version, `AM-309`) — each with the answer, effect and trace behind it: what a
    later round starts from (`AM-308`). [] for any other version."""
    sc = (version.doc_metadata or {}).get("special_conditions") or {}
    entries, trace = sc.get("entries", []), sc.get("trace", [])
    if len(entries) != len(trace):
        return []          # a record that does not add up: it no longer rebuilds (409)
    out = []
    for e, t in zip(entries, trace, strict=True):
        choice = db.get(M.ComparisonChoice, UUID(t["choice_id"])) \
            if t.get("choice_id") else None
        out.append({**e, "row_key": t["row_key"], "effect": t.get("effect"),
                    "answer": negotiation._SAID.get(choice.choice) if choice else None,
                    "trace": t})
    return out


def _basis(db, draft: M.ContractDraft) -> dict:
    """Our version's template, its pinned rows and its base model (body = template)."""
    tv = must_exist(db.get(M.TemplateVersion, draft.template_version_id),
                    "template_versions row")
    rows = publish.pinned_clauses(db, tv)
    clauses = {k: publish.clause_dict(c) for k, c in rows.items()}
    return {"tv": tv, "rows": rows, "clauses": clauses,
            "base": model_.resolve(publish.template_dict(tv), clauses, draft.values)}


def _derive(guard: Guard, before: M.DocumentVersion, after: M.DocumentVersion,
            listed: dict, basis: dict) -> dict:
    """THE derivation of what the final contract lists (`special_conditions.derive`):
    the dry run reads its entries and blockers, the change list its ``rows`` — never a
    second one. Each side read as its Special Conditions vary it (the change list's own
    reading); the template's text from our version's raw body, which is the template's."""
    db = guard.db
    old, new = (negotiation._units(negotiation.read_clauses(
        db, v.id, effective.effective_clauses)[0]) for v in (before, after))

    def standard(cv_id: str | None) -> str | None:
        cv = db.get(M.ClauseVersion, UUID(cv_id)) if cv_id else None
        return clause_text(cv) if cv is not None else None

    return special_conditions.derive(
        listed["changes"], old, new, negotiation._align(old, new), basis["base"],
        standard, prior=_prior(db, before),
        template=negotiation._units(load_clauses(db, before.id)))


def _in_package(guard: Guard, before: M.DocumentVersion | None,
                after: M.DocumentVersion, listed: dict) -> None:
    """`AM-308`: each change row's ``target {key, number, heading}`` and ``in_package``
    (replace · delete · insert · none · cannot), from `_derive`. The keys are absent —
    never null — where no final contract can be made from this pair: our side not a
    contract made from our template, a tracked-changes round, Special Conditions
    that could not be read, or a template that has none (`AM-316` r7)."""
    draft = _generated(guard.db, before)
    if before is None or draft is None or (before.doc_metadata or {}).get("reply_to") \
            or listed.get("special_conditions_not_applied"):
        return
    basis = _basis(guard.db, draft)
    contract = guard.db.get(M.Contract, before.contract_id)
    if special_conditions.config(basis["tv"]) is None and (
            contract is None or contract.governed_by_contract_id is None):
        return          # AM-316 r7: a template without Annexure A — no final contract
    rows = _derive(guard, before, after, listed, basis)["rows"]
    for change in listed["changes"]:
        change.update(rows.get(change["row_key"], {"target": None, "in_package": "none"}))


def _frame_pin(cfg: dict, version: M.DocumentVersion | None = None) -> dict:
    """The frame a final contract's words come from: the one it recorded, else its
    template's."""
    sc = ((version.doc_metadata or {}) if version else {}).get("special_conditions") or {}
    return sc.get("frame") or cfg.get("frame") or {}


def _package_plan(guard: Guard, contract: M.Contract, form: str = CHANGES_ONLY) -> dict:
    """The dry run of the final contract (`AM-307`): what its Special Conditions would
    list, and every reason it cannot be prepared yet. Nothing written. A later round
    (`AM-308`) answers our previous final contract: its entries carry, this round's
    answers override them, and the new one supersedes it. On an amendment (`AM-310`)
    ``form`` changes_only lists only THIS amendment's changes (the instrument's), and
    ``restatement`` says why Legal might restate the whole contract instead."""
    db = guard.db
    out: dict = {"available": False, "blockers": [], "entries": [], "precedence": None,
                 "entries_sha256": None}

    def stop(code: str, message: str, **extra) -> dict:
        out["blockers"].append({"code": code, "message": message, **extra})
        return out

    amendment_tv = None
    instrument_form = False
    if contract.governed_by_contract_id is not None:        # AM-309: an amendment
        amendment_tv = amendment_template(db)
        if amendment_tv is None:      # said first: nothing else can make one yet
            return stop(NoAmendmentTemplate.code, NO_AMENDMENT_TEMPLATE)
        out["form"] = form
        instrument_form = form == CHANGES_ONLY
        gaps = instrument.missing(db, amendment_tv) if instrument_form else []
        if gaps:
            return stop(AmendmentTemplateIncomplete.code, _incomplete(gaps), slots=gaps)
    versions = list(db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number)).scalars())
    after = versions[-1] if versions else None
    if after is None or negotiation.is_ours(after) or (
            (after.doc_metadata or {}).get("version_role") == FINAL_SIGNED):
        return stop("NOTHING_TO_ANSWER", "The latest version is not the client's — "
                    "there is no returned copy to prepare a final contract from.")
    before = negotiation.our_previous(versions, after)
    meta = (before.doc_metadata or {}) if before else {}
    draft = _generated(db, before)
    if before is None or draft is None:
        return stop("NOT_OUR_TEMPLATE", "Our side is not a contract made from our "
                    "template here — prepare our reply with tracked changes instead.")
    if meta.get("amendment"):
        return stop("AMENDMENT_ROUND", "The client returned the amendment itself — a "
                    "person reads it, or prepare our reply with tracked changes.")
    if meta.get("reply_to"):
        return stop("REDLINE_ROUND", "This deal already went back with tracked changes "
                    "— keep to that: prepare our reply.")
    basis = _basis(db, draft)
    tv, rows, clauses, base = basis["tv"], basis["rows"], basis["clauses"], basis["base"]
    ready = special_conditions.readiness(db, tv)
    if amendment_tv is None and special_conditions.config(tv) is None:
        # AM-316 r7: a template kept without Annexure A (the July 2025 MSA) — agreed
        # changes go back in the body, as tracked changes; no Annexure route is offered
        return stop("NO_ANNEXURE", "This contract's template has no Annexure A — "
                    "prepare our reply with tracked changes.")
    out["blockers"] += [{**m, "code": f"SC_{m['code']}"} for m in ready["missing"]]
    if tv.published_at is None:
        stop("TEMPLATE_NOT_PUBLISHED", "The template this contract was made from was "
             "never published.")
    cfg = special_conditions.config(tv) or {}
    prior = _prior(db, before)
    # our version rebuilds byte for byte — a final contract with the entries it holds
    rebuilt = base if not prior else _resolve_special(
        db, tv, clauses, draft, cfg, _frame_pin(cfg, before), prior)
    if rebuilt is None or model_.model_hash(rebuilt) != draft.model_hash:
        stop("BODY_CHANGED", "Our version no longer rebuilds from its template "
             "byte for byte; a person must look at it.")
    if cfg.get("precedence"):
        row = next((r for (k, _), r in rows.items() if k == cfg["precedence"]), None)
        out["precedence"] = {"clause_key": cfg["precedence"],
                             "number": base["numbers"].get(cfg["precedence"]),
                             "approved": bool(row and row.status == "APPROVED")}
    if _replied_in(db, after) is not None:
        return stop("ROUND_CLOSED", "Our answer to this version is already prepared.")
    if (gap := blanks(db, before)) is not None:
        stop("BLANKS", gap)              # verifier item 4: never a final with a blank
    listed, _, _ = _changes(guard, contract, before.version_number, after.version_number)
    if listed.get("special_conditions_not_applied"):
        return stop("SPECIAL_CONDITIONS_NOT_APPLIED", "The Special Conditions of one "
                    "side could not be read ("
                    f"{'; '.join(listed['special_conditions_not_applied'])}) — prepare "
                    "our reply with tracked changes, or a person reads it.")
    blocked = _reply_blockers(listed["changes"])
    if blocked:
        stop("PACKAGE_NOT_READY", f"The final contract cannot be prepared yet: {blocked}")
    derived = _derive(guard, before, after, listed, basis)
    out["blockers"] += derived["blockers"]
    entries = derived["entries"]
    shown, pins = entries, []
    if amendment_tv is not None:
        from legalmind.api.routers.amendments import _signed_amendments  # circular
        pins = [form, f"{amendment_tv.template_key}@{amendment_tv.version}"]
    if instrument_form:            # AM-310: the instrument lists this amendment's own
        shown = [{**e, "n": n} for n, e in enumerate(
            (e for e in entries if "trace" not in e), 1)]
        kept = {(e["target"]["key"], e.get("new_number")) for e in entries}
        for p in prior:            # back to the template's words: no verb says that
            if (p["target"]["key"], p.get("new_number")) not in kept:
                stop("CANNOT_EXPRESS", f"Clause {p['target']['number']} goes back to "
                     "the template's wording; an amendment cannot say that yet — "
                     "prepare our reply with tracked changes.")
        out["restatement"] = instrument.restatement_reasons(
            len(_signed_amendments(db, contract.governed_by_contract_id)), shown)
    if not shown and not out["blockers"]:
        stop("NO_ENTRIES", "Every change keeps our wording — send our version as it "
             "is, or prepare our reply.")
    out["entries"] = [{k: e[k] for k in ("n", "op", "target", "text", "row_key",
                                         "answer", "effect") if k in e}
                      | ({"new_number": e["new_number"]} if "new_number" in e else {})
                      | ({"carried": True} if "trace" in e else {})
                      for e in shown]
    frame = cfg.get("frame") or {}
    out["entries_sha256"] = special_conditions.entries_sha256(shown, [
        f"{frame.get('clause_key')}@{frame.get('version')}",
        *(f"{k}@{v}" for (k, v) in rows if k == cfg.get("precedence")), *pins])
    out["available"] = not out["blockers"]
    out["_internal"] = {"before": before, "after": after, "draft": draft, "tv": tv,
                        "clauses": clauses, "cfg": cfg, "changes": listed["changes"],
                        "entries": entries, "rows": rows, "frame": frame,
                        "shown": shown,
                        "instrument": amendment_tv if instrument_form else None,
                        "supersedes": str(before.id) if prior else None}
    return out


def _filled(guard: Guard, contract: M.Contract, body: PackageRequest) -> dict:
    """The values only the code knows (`AM-310`): the governing contract's name and
    signing date, this amendment's number; the effective date is the person's."""
    from legalmind.api.routers.amendments import _signed_amendments, _signed_at
    if body.effective_date is None:
        raise PackageNotReady("The amendment cannot be prepared yet.", [{
            "code": "EFFECTIVE_DATE", "message": "Say the date the amendment takes "
                                                 "effect."}])
    parent = must_exist(guard.db.get(M.Contract, contract.governed_by_contract_id),
                        "contracts row")
    return {"governing_agreement": parent.name,
            "governing_signed_on": _signed_at(guard.db, parent.id).date().isoformat(),
            "effective_date": body.effective_date.isoformat(),
            "amendment_number": str(len(_signed_amendments(guard.db, parent.id)) + 1)}


def _resolve_special(db, tv: M.TemplateVersion, clauses: dict, draft: M.ContractDraft,
                     cfg: dict, pin: dict, entries: list[dict]) -> dict | None:
    """The model of a final contract: the template body and these entries in the frame
    ``pin`` names. None where the frame is not on record (fail closed)."""
    frame = special_conditions.frame_row(db, tv, pin)
    if frame is None:
        return None
    try:
        return model_.resolve(publish.template_dict(tv), clauses, draft.values,
                              special={"frame": publish.clause_dict(frame),
                                       "config": cfg, "entries": entries})
    except model_.ModelError:
        return None


def _public_plan(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if not k.startswith("_")}


@router.get("/contracts/{contract_id}/package")
def package_preview(contract_id: UUID, guard: Guard = Depends(get_guard),
                    form: str = Query(CHANGES_ONLY, pattern="^(changes_only|restated)$")
                    ) -> dict:
    """The dry run of "Prepare final contract" (`AM-307`): ``available``, every
    ``blockers[{code, message, row_key?}]``, the ``entries`` the Special Conditions would
    list (in order), the ``precedence`` clause and ``entries_sha256`` — the POST names
    it. Nothing is written. On an amendment (`AM-310`) ``form`` and ``restatement``
    (the reasons Legal might restate the whole contract — a suggestion, never a
    choice made here)."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    return data(_public_plan(_package_plan(guard, contract, form)))


def _trace(guard: Guard, plan: dict) -> list[dict]:
    """The internal record behind each entry (`AM-307` R-7/R-8, SEC-07): the answer row
    it came from and the Legal Decisions or holder answer that let a "Worse for us"
    change stand — ids and hashes only; who, why and notes are joined at read time."""
    db, before, after = guard.db, plan["_internal"]["before"], plan["_internal"]["after"]
    rows = {c["row_key"]: c for c in plan["_internal"]["changes"]}
    out = []
    for e in plan["_internal"]["entries"]:
        if "trace" in e:            # agreed in an earlier round, unchanged since (AM-308)
            out.append(_carried_trace(db, e))
            continue
        change = rows[e["row_key"]]
        choice = _current_choice(guard, before, after, e["row_key"])
        digest = (change.get("answer") or {}).get("wording_sha256")
        decisions = []
        for ev in _their_evaluations(db, change):
            d = effective_decision(db, ev, escalated=is_escalated(db, ev.finding_id))
            if d is not None and _lets_stand(db, ev, d, digest):
                decisions.append(str(d.id))
        # the holder's answer counts only when it IS the current answer (L-2)
        holder = None if choice is None else db.execute(select(M.AuditEvent.id).where(
            M.AuditEvent.action == audit.NEGOTIATION_HOLDER_ANSWERED,
            M.AuditEvent.entity_id == after.contract_id,
            M.AuditEvent.after_state["row_key"].astext == e["row_key"],
            M.AuditEvent.after_state["answer_version"].astext
            == str(choice.version_number))
            .order_by(M.AuditEvent.timestamp.desc()).limit(1)).scalar()
        out.append({"n": e["n"], "target_key": (e["target"] or {}).get("key"),
                    "op": e["op"], "row_key": e["row_key"],
                    "choice_id": str(choice.id) if choice else None,
                    "choice_version": choice.version_number if choice else None,
                    "text_sha256": special_conditions.text_sha256(e["text"] or ""),
                    "effect": e.get("effect"), "decision_ids": decisions,
                    **({"holder_answer_audit_id": str(holder)} if holder else {})})
    return out


def _carried_trace(db, e: dict) -> dict:
    """An entry an earlier final contract agreed, unchanged in this round: its record
    as it was, renumbered — the Legal Decisions it named kept only while each is still
    the EFFECTIVE one on its Evaluation (a later decision there resets it: R-7)."""
    t = {**e["trace"], "n": e["n"]}
    kept = []
    for d_id in t.get("decision_ids", []):
        d = db.get(M.LegalDecision, UUID(d_id))
        ev = db.get(M.Evaluation, d.evaluation_id) if d is not None else None
        now = None if ev is None else effective_decision(
            db, ev, escalated=is_escalated(db, ev.finding_id))
        if now is not None and now.id == d.id:
            kept.append(d_id)
    return {**t, "decision_ids": kept}


def _lets_stand(db, ev: M.Evaluation, d: M.LegalDecision, digest: str | None) -> bool:
    """A decision that lets the entry stand (L-1): an acceptance, or the approval of
    exactly this wording — never a rejection, never another wording's approval."""
    if d.decision_type in _ACCEPTING:
        return True
    return (d.decision_type is DecisionType.APPROVE_CUSTOMIZATION and digest is not None
            and _approves(db, ev, digest))


def _trace_blockers(trace: list[dict], entries: list[dict]) -> list[dict]:
    """`SC_TRACE` (R-7, R-12): every entry comes from an answer, and every entry that
    lets a "Worse for us" change stand has the Legal Decision or the holder's answer
    that accepted it — our standard's own text excepted (it is no concession)."""
    out = []
    for t, e in zip(trace, entries, strict=True):
        if t["choice_id"] is None:
            out.append({"code": "SC_TRACE", "row_key": t["row_key"],
                        "message": f"Entry {t['n']} has no recorded answer."})
        elif (t["effect"] == negotiation.NEGATIVE and e["answer"] != "use_standard"
              and not t["decision_ids"] and "holder_answer_audit_id" not in t):
            out.append({"code": "SC_TRACE", "row_key": t["row_key"],
                        "message": f"Entry {t['n']} is worse for us and no Legal "
                                   "Decision accepted it."})
    return out


@router.post("/contracts/{contract_id}/package", status_code=201)
def prepare_package(contract_id: UUID, body: PackageRequest,
                    guard: Guard = Depends(get_guard),
                    storage: StorageBackend = Depends(get_storage)) -> dict:
    """Prepare the final contract (`AM-307`): the template body exactly as our version
    had it, and every agreed change as one entry of the Special Conditions annexure —
    rendered, preflighted, ingested as our next version (Company draft, ``package_of``
    the client's version), reviewed like any upload, audited
    `contract.package_prepared`. 409 PACKAGE_NOT_READY with ``blockers`` while anything
    stops it, 409 STALE_PREVIEW when the answers moved since the dry run."""
    contract = guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    amendment = contract.governed_by_contract_id is not None
    if amendment and body.form == RESTATED:    # AM-310: Legal's choice, never a default
        guard.permission(P.LEGAL_APPROVE_CUSTOMIZATION)
    _lock(guard, contract)
    plan = _package_plan(guard, contract, body.form)
    if any(b["code"] == NoAmendmentTemplate.code for b in plan["blockers"]):
        raise NoAmendmentTemplate(NO_AMENDMENT_TEMPLATE)
    gap = next((b for b in plan["blockers"]
                if b["code"] == AmendmentTemplateIncomplete.code), None)
    if gap is not None:
        raise AmendmentTemplateIncomplete(gap["message"], gap["slots"])
    if not plan["blockers"]:
        trace = _trace(guard, plan)
        plan["blockers"] += _trace_blockers(trace, plan["_internal"]["entries"])
    if plan["blockers"]:
        raise PackageNotReady("The final contract cannot be prepared yet.",
                              plan["blockers"])
    if plan["entries_sha256"] != body.expected_entries_sha256:
        raise StalePreview("The answers changed since you looked — review the list "
                           "again.")
    i = plan["_internal"]
    tv, draft, after = i["tv"], i["draft"], i["after"]
    built, values = tv, draft.values             # the template the file is made from
    try:
        if i["instrument"] is not None:          # AM-310: the changes-only instrument
            built = i["instrument"]
            values = instrument.values(built, _filled(guard, contract, body),
                                       draft.values)
            model = instrument.build(guard.db, built, values, i["shown"])
        else:
            frame = special_conditions.frame_row(guard.db, tv, i["frame"])
            assert frame is not None
            model = model_.resolve(publish.template_dict(tv), i["clauses"], draft.values,
                                   special={"frame": publish.clause_dict(frame),
                                            "config": i["cfg"], "entries": i["entries"]})
    except model_.ModelError as exc:
        raise PackageNotReady("The final contract cannot be built.",
                              [{"code": "MODEL", "message": str(exc)}]) from exc
    digest = model_.model_hash(model)
    number = 1 + max(v for v in guard.db.execute(select(
        M.DocumentVersion.version_number).where(
        M.DocumentVersion.contract_id == contract.id)).scalars())
    docx = render_contract.render(model, built.assets,
                                  contract_ref=str(contract.id)[:8].upper(),
                                  version_number=number, model_hash=digest)
    found = preflight.check(docx, model=model)
    if found:                # our own rendering is wrong: nothing is stored (rule 15)
        raise PackageNotReady("The final contract failed its checks.",
                              [{"code": f"PREFLIGHT_{p.code}", "message": p.detail}
                               for p in found])
    short = (built.layout or {}).get("short_title") or built.template_key
    kind = "amendment" if built is not tv else "final"
    result = ingest_document(guard.db, storage, contract_id=contract.id,
                             uploaded_by=guard.user_id, data=docx,
                             filename=f"{short} - {kind}.docx", declared_mime=DOCX_MIME)
    version = result.document_version

    def public(entries: list[dict]) -> list[dict]:
        return [{k: e[k] for k in ("n", "op", "target", "text")} | (
            {"new_number": e["new_number"]} if "new_number" in e else {})
            for e in entries]

    record = {"entries": public(i["entries"]), "trace": trace,
              "frame": {k: i["frame"][k] for k in ("clause_key", "version")}}
    if built is not tv:
        # AM-310: the instrument's own changes and their record; the whole contract as
        # amended (``basis``) is what the next amendment starts from — never signed
        own = [{**t, "n": e["n"]} for e, t in zip(
            i["shown"], (t for x, t in zip(i["entries"], trace, strict=True)
                         if "trace" not in x), strict=True)]
        pin = (special_conditions.config(built) or {})["frame"]
        written = {"amendment": {"form": CHANGES_ONLY, "entries": public(i["shown"]),
                                 "trace": own, "frame": pin,
                                 "effective_date": values.get(next(
                                     (v["key"] for v in built.variables
                                      if model_.role(v) == "effective_date"), "")),
                                 "basis": {**record, "draft_id": str(draft.id)}}}
    else:
        written = {"special_conditions": record}
    version.doc_metadata = {
        **(version.doc_metadata or {}),
        **{k: v for k, v in (i["before"].doc_metadata or {}).items()
           if k in ("source", "counterparty", "effective_date")},
        "version_role": "COMPANY_DRAFT", "package_of": str(after.id),
        # AM-308: the final contract it replaces, when this is a later round
        **({"supersedes": i["supersedes"]} if i["supersedes"] else {}), **written}
    guard.db.add(M.ContractDraft(
        contract_id=contract.id, document_version_id=version.id,
        template_version_id=built.id, values=values, model_hash=digest,
        renderer_version=render_contract.RENDERER_VERSION,
        clean_storage_key=version.storage_key, created_by=guard.user_id))
    guard.db.flush()
    audit.record(guard.db, action=audit.CONTRACT_PACKAGE_PREPARED, entity_type="contract",
                 entity_id=contract.id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"document_version_id": str(version.id),
                        "version_number": version.version_number,
                        "package_of": str(after.id), "supersedes": i["supersedes"],
                        "model_hash": digest,
                        **({"form": body.form} if amendment else {}),
                        "renderer_version": render_contract.RENDERER_VERSION,
                        "entries": [[t["n"], t["target_key"], t["op"], t["choice_id"],
                                     t["text_sha256"]] for t in trace]})
    if amendment and body.form == RESTATED:
        audit.record(guard.db, action=audit.CONTRACT_AMENDMENT_RESTATED,
                     entity_type="contract", entity_id=contract.id,
                     actor_id=guard.user_id, request_id=guard.request_id,
                     after={"document_version_id": str(version.id),
                            "governed_by_contract_id": str(
                                contract.governed_by_contract_id)})
    dispatch_indexing(guard.db, version.id, request_id=guard.request_id)
    dispatch_pdf(guard.db, version, "contract", request_id=guard.request_id)
    review = _review_reply(guard, version)
    return data({
        "document_version": serialize_document_version(version),
        "review_id": str(review.id) if review else None,
        "entries": public(i["shown"]),
        "downloads": {"docx": f"/document-versions/{version.id}/content",
                      "pdf": f"/document-versions/{version.id}/pdf"},
        "open_points": negotiation.reply_open_points(guard.db, version)})


# ------------------------------------------------- AM-318: the final clean copy
class FinalCopyNotReady(Conflict):
    """409 — the final copy cannot be prepared yet; ``blockers`` names every reason."""

    code = "FINAL_COPY_NOT_READY"

    def __init__(self, message: str, blockers: list[dict]) -> None:
        super().__init__(message)
        self.extra = {"blockers": blockers}


#: the package routes the final copy serves (`AM-318`): everything the Annexure route
#: (`AM-307`) refuses because of what the deal IS, never because something is open
_FINAL_COPY_ROUTES = {"NOTHING_TO_ANSWER", "NOT_OUR_TEMPLATE", "REDLINE_ROUND",
                      "NO_ANNEXURE", "AMENDMENT_ROUND", "NO_ENTRIES"}


#: a blank left to fill: three or more underscores (verifier item 4, 2026-11-09) — unless
#: filled in on the line itself, the answer written between underscores ("___Pune___",
#: "__8___", "___1st_ day"); "___________are" and "___ months" are still blank
_BLANK = re.compile(r"_{3,}")
_FILLED = re.compile(r"_+[^\W_][^_\s]*_+")


def _is_blank(text: str, m: re.Match) -> bool:
    return not any(f.start() <= m.start() and m.end() <= f.end()
                   for f in _FILLED.finditer(text))


def blanks(db, version: M.DocumentVersion) -> str | None:
    """Every place ``version`` still has a blank to fill, in plain words ("clause 1.4
    (banks at ___ are open)", …) — or None. A final contract never keeps one: it is a
    blocker before "Prepare final contract", whichever route makes it."""
    places: list[str] = []
    for c in load_clauses(db, version.id):
        m = next((m for m in _BLANK.finditer(c.content) if _is_blank(c.content, m)), None)
        if m is None:
            continue
        near = c.content[max(0, m.start() - 30):m.end() + 20].strip()
        where = f"clause {c.section_number}" if c.section_number else "the opening text"
        places.append(f"{where} (…{_BLANK.sub('___', near)}…)")
    if not places:
        return None
    return (f"{len(places)} blank{'s are' if len(places) != 1 else ' is'} still to fill: "
            + "; ".join(places[:8]) + ("; …" if len(places) > 8 else "")
            + ". Fill them in the contract first.")


def _final_plan(guard: Guard, contract: M.Contract) -> dict:
    """The dry run of the final copy (`AM-318`, owner 2026-11-06: the deal cycle ends at
    the final clean copy). Its source is the agreed text: our latest version as the
    client accepted it, or the client's latest version when every change is accepted —
    any other answer goes back to the client as our reply first (REPLY_FIRST). Then every
    tracked change accepted and every comment removed (`drafting.clean`). Nothing
    written."""
    db = guard.db
    out: dict = {"available": False, "blockers": [], "mode": None, "agreed": []}

    def stop(code: str, message: str) -> dict:
        out["blockers"].append({"code": code, "message": message})
        return out

    versions = list(db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract.id)
        .order_by(M.DocumentVersion.version_number)).scalars())
    if not versions:
        return stop("NO_VERSION", "Upload the contract first.")
    latest = versions[-1]
    n = latest.version_number
    if negotiation.final_of(latest.doc_metadata):
        return stop("ALREADY_FINAL", f"Version {n} is already the final contract.")
    if latest.processing_status is not ProcessingStatus.COMPLETED:
        return stop("NOT_READ", f"Version {n} is still being read.")
    out["of_version"] = n
    role = (latest.doc_metadata or {}).get("version_role")
    # ours as prepare_reply reads it: declared Company draft — or the deal's only version
    # of ours, undeclared; anything after a version of ours is the client's round
    alone = negotiation.our_previous(versions, latest) is None
    if role == "COMPANY_DRAFT" or (role is None and alone
                                   and negotiation.is_ours(latest)):
        if (gap := blanks(db, latest)) is not None:
            return stop("BLANKS", gap)
        theirs = next((v for v in versions
                       if str(v.id) == (latest.doc_metadata or {}).get("reply_to")), None)
        if theirs is not None:             # our reply the client accepted: its answers
            prior = negotiation.our_previous(versions, theirs)
            try:
                round_, _, _ = _changes(guard, contract,
                                        prior.version_number if prior else None,
                                        theirs.version_number)
                out["agreed"] = [{"where": _where(c), "answer": c["answer"]["answer"]}
                                 for c in round_["changes"] if c.get("answer")]
            except BusinessRuleRejected:
                pass                       # the list is a courtesy; the copy stands
        out.update(mode="copy", available=True)
        out["_source"] = latest
        return out
    package = _package_plan(guard, contract)
    if not {b["code"] for b in package["blockers"]} & _FINAL_COPY_ROUTES:
        return stop("USE_PACKAGE", "This contract's final copy is made with Annexure A — "
                    "prepare the final contract from the Changes tab.")
    ours = negotiation.our_previous(versions, latest)
    try:
        listed, _, _ = _changes(guard, contract, ours.version_number if ours else None, n)
    except BusinessRuleRejected as exc:
        return stop("NOT_READ", str(exc))
    blocked = _reply_blockers(listed["changes"])
    if blocked:
        return stop("CHANGES", f"The final contract cannot be prepared yet: {blocked}")
    changes = listed["changes"]
    if any(c["answer"]["answer"] != "accept_theirs" for c in changes):
        # a counter-proposal goes back to the client first; the final copy is made of
        # the version the client accepts (verifier, 2026-11-09)
        return stop("REPLY_FIRST", "Some answers keep or propose our wording — "
                    "prepare our reply and send it to the client first. Prepare the "
                    "final contract once they accept it.")
    if (gap := blanks(db, latest)) is not None:
        return stop("BLANKS", gap)
    out["agreed"] = [{"where": _where(c), "answer": c["answer"]["answer"]}
                     for c in changes]
    out.update(mode="copy", available=True)
    out["_source"] = latest
    return out


@router.get("/contracts/{contract_id}/final-copy")
def final_copy_preview(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The dry run of "Prepare final contract" where no Annexure package applies
    (`AM-318`): ``available``, ``blockers[{code, message}]``, ``mode`` (copy),
    ``of_version`` and what was ``agreed`` (each change's place and answer)."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    return data(_public_plan(_final_plan(guard, contract)))


@router.post("/contracts/{contract_id}/final-copy", status_code=201)
def prepare_final_copy(contract_id: UUID, guard: Guard = Depends(get_guard),
                       storage: StorageBackend = Depends(get_storage)) -> dict:
    """Prepare the final clean copy (`AM-318`): the agreed text with every tracked change
    accepted and every comment removed, ingested as our next version (Company draft,
    ``final_copy_of`` its source), reviewed like any upload, audited
    `contract.final_copy_prepared`. Legal then records the decision on the contract on
    it; Sign as is makes the deal Final. 409 FINAL_COPY_NOT_READY with ``blockers``."""
    contract = guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    _lock(guard, contract)
    plan = _final_plan(guard, contract)
    if plan["blockers"]:
        raise FinalCopyNotReady("The final contract cannot be prepared yet.",
                                plan["blockers"])
    source: M.DocumentVersion = plan["_source"]
    raw = storage.get(source.storage_key)
    docx = source.mime_type == DOCX_MIME
    made = clean.clean(raw) if docx else raw
    stem = (source.original_filename or "contract").rsplit(".", 1)[0]
    version = ingest_document(guard.db, storage, contract_id=contract.id,
                              uploaded_by=guard.user_id, data=made,
                              filename=f"{stem} - final.{'docx' if docx else 'pdf'}",
                              declared_mime=DOCX_MIME if docx else PDF_MIME
                              ).document_version
    version.doc_metadata = {
        **(version.doc_metadata or {}),
        **{k: v for k, v in (source.doc_metadata or {}).items()
           if k in ("source", "counterparty", "effective_date")},
        "version_role": "COMPANY_DRAFT", "final_copy_of": str(source.id),
        "final_mode": plan["mode"], "agreed": plan["agreed"]}
    draft = _generated(guard.db, source)
    if draft is not None:        # our template contract, accepted as it was: still ours
        guard.db.add(M.ContractDraft(
            contract_id=contract.id, document_version_id=version.id,
            template_version_id=draft.template_version_id, values=draft.values,
            model_hash=draft.model_hash, renderer_version=draft.renderer_version,
            clean_storage_key=version.storage_key, created_by=guard.user_id))
    guard.db.flush()
    audit.record(guard.db, action=audit.CONTRACT_FINAL_COPY_PREPARED,
                 entity_type="contract", entity_id=contract.id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"document_version_id": str(version.id),
                        "version_number": version.version_number,
                        "final_copy_of": str(source.id), "mode": plan["mode"],
                        "file_hash": version.file_hash, "agreed": len(plan["agreed"])})
    dispatch_indexing(guard.db, version.id, request_id=guard.request_id)
    if docx:
        dispatch_pdf(guard.db, version, "final", request_id=guard.request_id)
    review = _review_reply(guard, version)
    return data({"document_version": serialize_document_version(version),
                 "review_id": str(review.id) if review else None,
                 "downloads": {"docx" if docx else "pdf":
                               f"/document-versions/{version.id}/content",
                               **({"pdf": f"/document-versions/{version.id}/pdf"}
                                  if docx else {})},
                 "open_points": negotiation.reply_open_points(guard.db, version)})


@router.get("/document-versions/{document_version_id}/special-conditions")
def special_conditions_of(document_version_id: UUID,
                          guard: Guard = Depends(get_guard)) -> dict:
    """A final contract's Special Conditions (`AM-307`): the ``entries`` as the client
    reads them, and the ``trace`` behind each — who answered, when, why, the effect and
    the Legal Decisions — joined now; the internal note only with `legal_position.view`
    (the key omitted otherwise, never nulled — SEC-07, `AM-285` r3)."""
    version = guard.document_version_readable(document_version_id, P.DOCUMENT_VIEW)
    meta = version.doc_metadata or {}
    sc = meta.get("special_conditions") or meta.get("amendment")    # AM-310 instrument
    if not sc:
        raise NotVisible("this version has no Special Conditions")
    trace = []
    for t in sc.get("trace", []):
        choice = guard.db.get(M.ComparisonChoice, UUID(t["choice_id"])) \
            if t.get("choice_id") else None
        who = guard.db.get(M.User, choice.decided_by) if choice else None
        trace.append({**{k: v for k, v in t.items() if k != "row_key"},
                      "row_key": t["row_key"],
                      **({"answer": negotiation._SAID[choice.choice],
                          "decided_by": who.name if who else None,
                          "decided_at": choice.created_at.isoformat(),
                          "reason": choice.reason, "client_note": choice.client_note,
                          **({"internal_note": choice.internal_note}
                             if guard.sees_legal_position else {})}
                         if choice else {})})
    return data({"document_version_id": str(version.id),
                 "package_of": (version.doc_metadata or {}).get("package_of"),
                 "entries": sc.get("entries", []), "trace": trace})
