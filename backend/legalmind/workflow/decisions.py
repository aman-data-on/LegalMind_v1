"""Legal Decision service — locked Step 31 (as amended by AM-2/AM-5/AM-6),
AB-1.1, AM-12, AM-15, Step 47 SEC-05, SEC-09.

Three locked properties are enforced here rather than trusted:

* **A decision resolves exactly ONE Evaluation** and never implicitly disposes
  of another under the same Finding (AB-1.1). The API has no Finding-level
  decision entry point, and neither does this service.
* **Supersession is append-only** (Step 31 r14). There is no update path: a
  change creates a new version, and prior rows are immutable — enforced by a
  database trigger, so no code path can revise history.
* **The current decision is the highest version** (Step 31 r20, N-1 Option C).
  Derived, never flagged, so it cannot drift.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from legalmind import notifications
from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.domain.enums import DecisionType, FindingStatus
from legalmind.evaluation import workflow as _workflow
from legalmind.evaluation.workflow import (
    DECISION_CARRIED_FORWARD,
    carried_forward,
    derive_finding_status,
    effective_decision,
    evaluation_requires_decision,
    own_contract,
    second_person_needed,
)
from legalmind.evaluation.workflow import (
    requires_second_person as requires_second_person_for,
)
from legalmind.observability.logs import log_event
from legalmind.observability.metrics import decision_wait_seconds
from legalmind.security import audit as A
from legalmind.security import permissions as P
from legalmind.security.authorization import require_review_visible
from legalmind.security.errors import Forbidden
from legalmind.security.resolver import has_permission
from legalmind.workflow.errors import (
    SecondPersonNotConfigured,
    SecondPersonRequired,
    VersionConflict,
)
from legalmind.workflow.escalation import is_escalated
from legalmind.workflow.review_lifecycle import (
    REOPENING_DECISIONS,
    reopen_if_finished,
    require_writable,
)

# Locked Step 23 / 47.5 — APPROVE_CUSTOMIZATION needs the additional grant.
_EXTRA_PERMISSION = {
    DecisionType.APPROVE_CUSTOMIZATION: P.LEGAL_APPROVE_CUSTOMIZATION,
}


@dataclass(frozen=True)
class DecisionRecorded:
    decision: M.LegalDecision
    finding_status: str
    is_effective: bool


def record_decision(
    db: DBSession,
    *,
    actor_id: UUID,
    evaluation_id: UUID,
    decision_type: DecisionType,
    justification: str,
    expected_version: int | None = None,
    requires_second_person: bool = False,
    request_id: str | None = None,
) -> DecisionRecorded:
    """Record a Legal Decision against one scoped Evaluation.

    Authorization order follows locked 43.23: object scope first, then operation
    permission — so a caller who cannot see the object gets 404 regardless of
    their permissions and the response never reveals existence.
    """
    evaluation = db.get(M.Evaluation, evaluation_id)
    if evaluation is None:
        from legalmind.security.errors import NotVisible
        raise NotVisible("evaluation not found")

    finding = db.get(M.Finding, evaluation.finding_id)
    if finding is None:
        # QA-086: deleted under us (the contract's cascade committed between the two
        # reads) — the same 404 as any object that is not there, never a 500
        from legalmind.security.errors import NotVisible
        raise NotVisible("evaluation not found")
    # The CALL is the authorization check — it raises `NotVisible` (→ 404) when the
    # Review is out of scope. Its return value is deliberately unused; binding it to a
    # name suggested the check was a lookup, which is the opposite of the point.
    require_review_visible(db, actor_id, finding.review_id)

    # SEC-02/SEC-05 — legal.decision is only ever an EXPLICIT grant; no bypass
    # reaches it, so a Super Admin without it cannot decide by any route.
    if not has_permission(db, actor_id, P.LEGAL_DECISION):
        _audit_denied(db, actor_id, evaluation_id, request_id)
        raise Forbidden("missing permission: legal.decision")

    extra = _EXTRA_PERMISSION.get(decision_type)
    if extra and not has_permission(db, actor_id, extra):
        _audit_denied(db, actor_id, evaluation_id, request_id)
        raise Forbidden(f"missing permission: {extra}")

    if not (justification or "").strip():
        # Locked Step 31 r11. The database also enforces NOT NULL (AM-15); this
        # rejects whitespace-only text, which the column cannot.
        raise Forbidden("a justification is required for every Legal Decision")

    # QA-044: the standard decides whether a second approval is needed; a request that
    # asks for one the standard does not require would resolve differently from what it
    # reports, so it is refused rather than half-honoured
    # AM-289 r1 (reverses AM-170 O2): a decision on one's own contract needs a second,
    # different holder — the same co-signature as the standard's flag (AM-240 r1)
    second = (requires_second_person_for(db, evaluation)
              or own_contract(db, evaluation, actor_id))
    if requires_second_person and not second:
        raise SecondPersonNotConfigured(
            "second-person approval is set on the standard (requires_second_person), "
            "not per request; this standard does not require it")

    # AM-178: an archived contract or a superseded version takes no decision (409)
    review = must_exist(db.get(M.Review, finding.review_id), "reviews row",
                        finding.review_id)
    require_writable(db, review)

    next_version = _next_version(db, evaluation_id)
    if expected_version is not None and expected_version + 1 != next_version:
        raise VersionConflict(
            f"expected to write version {expected_version + 1}, "
            f"but version {next_version} is next")

    decision = M.LegalDecision(
        finding_id=finding.id,
        evaluation_id=evaluation_id,
        decision_type=decision_type,
        justification=justification,
        decided_by=actor_id,
        version_number=next_version,
        # the moment itself, not the transaction's start: an escalation raised between
        # two decisions must order before the later one (AM-175)
        created_at=datetime.now(UTC),
    )
    try:
        # The UNIQUE(evaluation_id, version_number) constraint is the real
        # concurrency guarantee (AM-12); surface it as 409, not a 500 — under a
        # savepoint, so the request's earlier writes (its audit) survive (AM-177)
        with db.begin_nested():
            db.add(decision)
            db.flush()
    except IntegrityError as exc:
        raise VersionConflict(
            "another decision was recorded concurrently for this Evaluation"
        ) from exc

    effective = decision_is_effective(db, evaluation_id, requires_second_person=second)

    # SEC-09 — every decision is auditable (Step 31 r19). Append-only.
    A.record(db, action=A.LEGAL_DECISION_RECORDED,
             entity_type="evaluation", entity_id=evaluation_id, actor_id=actor_id,
             request_id=request_id,
             after={"decision_type": decision_type.value,
                    "version_number": next_version,
                    "is_effective": effective,
                    # the reason travels with the event (AB-100, owner 2026-10-21): an
                    # auditor reads why from the trail itself, not only from the row
                    "justification": justification,
                    # where it belongs, readable from the trail alone (AB-103)
                    "finding_id": str(finding.id), "review_id": str(review.id),
                    "document_version_id": str(review.document_version_id)})

    # an escalated finding stays where escalation put it — the same derivation the
    # lifecycle and escalation use (review, 2026-10-21)
    status = derive_finding_status(db, finding,
                                   escalated=is_escalated(db, finding.id))
    finding.status = status
    db.flush()
    if decision_type in REOPENING_DECISIONS:          # AM-175: a point needs work again
        reopen_if_finished(db, review, cause=f"decision {decision_type.value}",
                           actor_id=actor_id, request_id=request_id)

    # Locked 53.5 — "decision throughput and age". The wait is derived from two
    # timestamps the schema already carries. Deliberately WITHOUT `decision_type`:
    # 53.5 asks for throughput and age, and a disposition is closer to the internal
    # legal position LEGAL-02 protects than a count is.
    if effective:   # AM-273 m3 — a first signature of two has decided nothing yet
        notifications.decision_recorded(db, finding, review, actor_id=actor_id)

    log_event("legal.decision_recorded", request_id=request_id,
              evaluation_id=str(evaluation_id),
              version_number=next_version,
              is_effective=effective,
              waited_seconds=decision_wait_seconds(evaluation.created_at,
                                                   decision.created_at),
              signal="decision.outstanding_age")

    return DecisionRecorded(decision=decision, finding_status=status.value,
                            is_effective=effective)


def _next_version(db: DBSession, evaluation_id: UUID) -> int:
    current = db.execute(
        select(func.max(M.LegalDecision.version_number))
        .where(M.LegalDecision.evaluation_id == evaluation_id)
    ).scalar()
    return (current or 0) + 1


def decision_history(db: DBSession, evaluation_id: UUID) -> list[M.LegalDecision]:
    """Full version chain, oldest first. Nothing is ever removed."""
    return list(db.execute(
        select(M.LegalDecision)
        .where(M.LegalDecision.evaluation_id == evaluation_id)
        .order_by(M.LegalDecision.version_number)
    ).scalars().all())


def decision_is_effective(db: DBSession, evaluation_id: UUID, *,
                          requires_second_person: bool) -> bool:
    """Whether the current decision disposes of the Evaluation.

    ``REQUEST_CLARIFICATION`` never disposes (locked Step 31 r10).

    **Second-person approval (locked Step 31 r15, F-2).** r15 permits a
    Requirement to "require independent second-person approval for consequential
    contract-specific decisions" but does not specify the mechanism. Implemented
    here as co-signature within the append-only version chain: the current
    decision and the one immediately preceding it must share a ``decision_type``
    and have DIFFERENT actors. This needs no schema change and keeps the
    append-only guarantee intact — an alternative ``co_signed_by`` column would
    amend locked 42.17.
    """
    chain = decision_history(db, evaluation_id)
    if not chain:
        return False
    current = chain[-1]
    if current.decision_type is DecisionType.REQUEST_CLARIFICATION:
        return False
    if not requires_second_person:
        return True
    if len(chain) < 2:
        return False
    previous = chain[-2]
    return (previous.decision_type is current.decision_type
            and previous.decided_by != current.decided_by)


def require_effective_decision(db: DBSession, evaluation_id: UUID, *,
                               requires_second_person: bool) -> None:
    if not decision_is_effective(
            db, evaluation_id, requires_second_person=requires_second_person):
        raise SecondPersonRequired(
            "an independent second approval by a different authorized user is "
            "required before this decision takes effect")


def _audit_denied(db: DBSession, actor_id: UUID, evaluation_id: UUID,
                  request_id: str | None) -> None:
    A.record(db, action=A.AUTHZ_PERMISSION_DENIED, entity_type="evaluation",
             entity_id=evaluation_id, actor_id=actor_id, request_id=request_id)


def outstanding_decisions(db: DBSession) -> dict[str, object]:
    """Locked 53.5's other decision signal — "Reviews stuck in `DECISION_REQUIRED`".

    A query, not a stored counter: Finding status is derived (Step 30 r16), so a
    materialized "stuck count" would be a second source of truth for something the
    database can answer directly.

    Nothing emits this on a timer, deliberately. Locked 53.6 leaves the monitoring
    stack and alert thresholds NOT YET SPECIFIED, so inventing a scheduler and a
    threshold would be inventing the operational decision. It is available for an
    operator command or for whichever backend is eventually chosen; the per-decision
    half of the signal is emitted where a decision is recorded, which needs no timer.
    """
    count, oldest = db.execute(
        select(func.count(), func.min(M.Finding.created_at))
        .where(M.Finding.status == FindingStatus.DECISION_REQUIRED)
    ).one()
    return {"signal": "decision.outstanding_age",
            "outstanding": count,
            "oldest_created_at": oldest.isoformat() if oldest else None}


# ------------------------------------------- `AM-284` / `AM-293`: carried onto our reply
#: how an APPROVE_CUSTOMIZATION carries the wording it approves (`AM-284` r2)
_WORDING_TAG = re.compile(r"\[our wording sha256:([0-9a-f]{64})\]")
#: decisions that let a wording stand — the only ones carried (`AM-250` r2, `AM-284`)
_CARRIED = {DecisionType.ACCEPT_DEVIATION, DecisionType.NOT_APPLICABLE_TO_CONTRACT,
            DecisionType.APPROVE_CUSTOMIZATION}


def wording_tag(digest: str) -> str:
    """How a Legal Decision carries the wording it approves (`AM-284` r2)."""
    return f"[our wording sha256:{digest}]"


def reader_justification(text: str) -> str:
    """LA-4: the reason as a reader sees it — the wording tag in plain words. The stored
    justification (and so the audit record and `AM-284` matching) keeps the hash."""
    return _WORDING_TAG.sub("(our approved wording)", text)


def _text_hash(text: str) -> str:
    """Spacing ignored, nothing else: a changed word is changed wording (rule 15)."""
    return hashlib.sha256(" ".join(text.split()).encode()).hexdigest()


def _read(db: DBSession, review_id: UUID
          ) -> dict[UUID, tuple[M.Evaluation, UUID, list[tuple[UUID, str]]]]:
    """Each Evaluation of the Review with its requirement and the evidence rows it read
    (id, text)."""
    rows = db.execute(
        select(M.Evaluation, M.RequirementVersion.requirement_id,
               M.DocumentEvidence.id, M.DocumentEvidence.content)
        .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
        .join(M.RequirementVersion,
              M.RequirementVersion.id == M.Finding.requirement_version_id)
        .outerjoin(M.EvaluationEvidence,
                   M.EvaluationEvidence.evaluation_id == M.Evaluation.id)
        .outerjoin(M.DocumentEvidence,
                   M.DocumentEvidence.id == M.EvaluationEvidence.evidence_id)
        .where(M.Finding.review_id == review_id)
        .order_by(M.Evaluation.id, M.DocumentEvidence.start_offset)).all()
    out: dict[UUID, tuple[M.Evaluation, UUID, list[tuple[UUID, str]]]] = {}
    for ev, requirement_id, evidence_id, content in rows:
        texts = out.setdefault(ev.id, (ev, requirement_id, []))[2]
        if content is not None:
            texts.append((evidence_id, content))
    return out


def _hash_rows(texts: list[str], anywhere: bool = False) -> str:
    """The rows' texts in the document's order — or, for a final contract
    (``anywhere``), sorted: its Special Conditions hold a varied clause after the body
    (`AM-307`). A tracked reply keeps the order (L-3)."""
    return _text_hash("\n".join(sorted(texts) if anywhere else texts))


def _evaluated(db: DBSession, review_id: UUID, anywhere: bool = False
               ) -> list[tuple[M.Evaluation, UUID, str]]:
    """Each Evaluation of the Review with its requirement and the hash of the text it
    read; a MISSING one reads nothing, so it matches only another that reads nothing."""
    return [(ev, r, _hash_rows([t for _, t in rows], anywhere))
            for ev, r, rows in _read(db, review_id).values()]


def carry_decisions(db: DBSession, review: M.Review, *,
                    request_id: str | None = None) -> int:
    """Carry forward onto our reply's own Review the decisions already made on the
    client's version it replied to (`AM-284` r2, `AM-293` r1) — the industry-standard
    carry-forward, so a reply is not re-decided point by point. Returns how many.

    Only for a Review of a version whose ``doc_metadata.reply_to`` names the client's
    version. An Evaluation of ours still DECISION_REQUIRED, with no decision yet, takes
    the client version's EFFECTIVE decision (`effective_decision`: co-signed where the
    second person was needed, not before an active escalation) on the SAME requirement
    when the text it reads is the same (spacing aside):

    * ACCEPT_DEVIATION / NOT_APPLICABLE_TO_CONTRACT — the client's text, unchanged;
    * APPROVE_CUSTOMIZATION — the wording whose SHA-256 the decision carries.

    The carried row is a Legal Decision of the same type, ``decided_by`` the original
    decider (who must still hold the right), justification "Carried from version N —
    same wording: …", audited `decision.carried` with the original's id; a co-signed
    original is carried as both signatures, in order. Never ACCEPTABLE — the engine's
    outcome is untouched. Anything not matched exactly — changed text, two different
    decisions for one text, a decider without the right — stays undecided (rule 15).
    Idempotent: an Evaluation already holding a decision is never written again."""
    version = db.get(M.DocumentVersion, review.document_version_id)
    meta = (version.doc_metadata or {}) if version else {}
    # the client's version answered (AM-307) and — a later final contract or an
    # amendment's copy (AM-308/AM-309) — our final contract it carries on from, where an
    # entry left unchanged reads the very text its decision was made on
    named = [(meta.get("reply_to") or meta.get("package_of"), True),
             (meta.get("supersedes") or meta.get("copy_of"), False)]
    found_in: list[tuple[M.DocumentVersion, M.Review, bool]] = []
    for vid, client in named:
        source = db.get(M.DocumentVersion, UUID(vid)) if vid else None
        prior = None if source is None else db.execute(
            select(M.Review).where(M.Review.document_version_id == source.id)
            .order_by(M.Review.created_at.desc()).limit(1)).scalar()
        if source is not None and prior is not None:
            found_in.append((source, prior, client))
    if not found_in:
        return 0
    sources: dict[tuple[UUID, str], set[tuple[UUID, ...]]] = {}
    chains: dict[tuple[UUID, ...], list[M.LegalDecision]] = {}
    origin: dict[tuple[UUID, ...], M.DocumentVersion] = {}
    anywhere = bool(meta.get("package_of") or meta.get("copy_of"))
    for theirs, prior, client in found_in:
        _sources(db, theirs, prior, client, anywhere, sources, chains, origin)
    carried = 0
    for ev, requirement_id, text in _evaluated(db, review.id, anywhere):
        found = sources.get((requirement_id, text), set())
        finding = db.get(M.Finding, ev.finding_id)
        if (len(found) != 1 or finding is None
                or finding.status is not FindingStatus.DECISION_REQUIRED
                or _next_version(db, ev.id) > 1
                or not evaluation_requires_decision(
                    classification=ev.classification, rule_outcome=ev.rule_outcome,
                    requirement_required=True, escalated=False)):
            continue
        key = next(iter(found))
        chain = chains[key]
        if not all(has_permission(db, x.decided_by, P.LEGAL_DECISION) and (
                (extra := _EXTRA_PERMISSION.get(x.decision_type)) is None
                or has_permission(db, x.decided_by, extra)) for x in chain):
            continue
        for n, original in enumerate(chain, start=1):
            db.add(M.LegalDecision(
                finding_id=finding.id, evaluation_id=ev.id,
                decision_type=original.decision_type, decided_by=original.decided_by,
                version_number=n, created_at=datetime.now(UTC),
                justification=(f"Carried from version {origin[key].version_number} — "
                               f"same wording: {original.justification}")))
            db.flush()
            A.record(db, action=A.DECISION_CARRIED, entity_type="evaluation",
                     entity_id=ev.id, actor_id=None, request_id=request_id,
                     after={"decision_type": original.decision_type.value,
                            "version_number": n, "decided_by": str(original.decided_by),
                            "carried_from_decision_id": str(original.id),
                            "carried_from_version_id": str(origin[key].id),
                            "finding_id": str(finding.id), "review_id": str(review.id)})
        finding.status = derive_finding_status(db, finding)
        carried += 1
    db.flush()
    return carried


def _sources(db: DBSession, theirs: M.DocumentVersion, prior: M.Review, client: bool,
             anywhere: bool, sources: dict[tuple[UUID, str], set[tuple[UUID, ...]]],
             chains: dict[tuple[UUID, ...], list[M.LegalDecision]],
             origin: dict[tuple[UUID, ...], M.DocumentVersion]) -> None:
    """The decisions ``prior`` (the Review of ``theirs``) can carry, by (requirement,
    text read). On the client's version our wording is matched by its hash; on our own
    final contract the wording IS the text its Evaluation read."""
    read = _read(db, prior.id)
    for ev, requirement_id, text in _evaluated(db, prior.id, anywhere):
        d = effective_decision(db, ev, escalated=is_escalated(db, ev.finding_id))
        if d is None or d.decision_type not in _CARRIED:
            continue
        chain = [d]
        if second_person_needed(db, ev, d.decided_by):
            chain = [decision_history(db, ev.id)[d.version_number - 2], d]
        if client and d.decision_type is DecisionType.APPROVE_CUSTOMIZATION:
            digests = {m for x in chain for m in _WORDING_TAG.findall(x.justification)}
            wordings = db.execute(select(
                M.ComparisonChoice.wording, M.ComparisonChoice.row_key).where(
                M.ComparisonChoice.right_version_id == theirs.id,
                M.ComparisonChoice.wording_sha256.in_(digests))).all()
            texts = {_hash_rows([w], anywhere) for w, _ in wordings if w}
            # the clause the wording replaced, among the other rows the Evaluation read
            # (the row key's last part: the client clause's first evidence row)
            for w, row_key in wordings:
                at = row_key.rsplit("|", 1)[-1]
                if w and at in {str(e) for e, _ in read[ev.id][2]}:
                    texts.add(_hash_rows([w if str(e) == at else t
                                          for e, t in read[ev.id][2]], anywhere))
        else:
            texts = {text}
        key = tuple(x.id for x in chain)
        chains[key] = chain
        origin[key] = theirs
        for t in texts:
            sources.setdefault((requirement_id, t), set()).add(key)


# ------------------------------------------- `AM-317` r7: decided once per deal
def _signatures(db: DBSession, review: M.Review
                ) -> dict[UUID, tuple[UUID, UUID | None, tuple]]:
    """Each Finding of the Review -> (requirement version, company standard version,
    what it read): per Evaluation its scope, classification, rule outcome and the hash
    of the text it read — spacing ignored, nothing else (`_text_hash`)."""
    standards: dict[UUID, UUID | None] = dict(db.execute(select(
        M.ConfigurationSnapshotItem.requirement_version_id,
        M.ConfigurationSnapshotItem.company_standard_version_id).where(
        M.ConfigurationSnapshotItem.snapshot_id == review.configuration_snapshot_id)
        ).tuples().all())
    rows: dict[UUID, list[tuple]] = {}
    for ev, _, texts in _read(db, review.id).values():
        rows.setdefault(ev.finding_id, []).append(
            (ev.scope_key or "", ev.classification.value,
             ev.rule_outcome.value if ev.rule_outcome else "",
             _hash_rows([t for _, t in texts])))
    out = {}
    for finding in db.execute(select(M.Finding).where(
            M.Finding.review_id == review.id)).scalars():
        rv = finding.requirement_version_id
        out[finding.id] = (rv, standards.get(rv), tuple(sorted(rows.get(finding.id, []))))
    return out


def _decided(db: DBSession, finding: M.Finding) -> dict | None:
    """What stands on an earlier Finding, re-checked NOW at every hop (`AM-321` r1):
    the Finding must derive RESOLVED and not be escalated; if it holds Legal Decisions of
    its own, they are what stands — its latest effective decision on every Evaluation
    that needs one must be an ACCEPT_DEVIATION / NOT_APPLICABLE_TO_CONTRACT /
    APPROVE_CUSTOMIZATION by a decider still holding the right (a later REJECT, a
    clarification or an escalation on this version replaces or breaks what came before);
    only a Finding with no decision of its own may stand on a carry, and then the
    ORIGINAL Finding is checked again the same way, so a decision since withdrawn,
    superseded, escalated or by a decider who lost the right carries nothing."""
    if is_escalated(db, finding.id) \
            or derive_finding_status(db, finding) is not FindingStatus.RESOLVED:
        return None
    own = db.execute(select(M.LegalDecision.id).where(
        M.LegalDecision.finding_id == finding.id).limit(1)).first() is not None
    if not own:
        carried = carried_forward(db, finding.id)
        origin = db.get(M.Finding, UUID(carried["from_finding_id"])) \
            if carried and carried.get("from_finding_id") else None
        return _decided(db, origin) if origin is not None and origin.id != finding.id \
            else None
    escalated = is_escalated(db, finding.id)
    decisions = []
    for ev in db.execute(select(M.Evaluation).where(
            M.Evaluation.finding_id == finding.id)).scalars():
        if not evaluation_requires_decision(
                classification=ev.classification, rule_outcome=ev.rule_outcome,
                requirement_required=True, escalated=escalated):
            continue
        d = effective_decision(db, ev, escalated)
        if d is None or d.decision_type not in _CARRIED \
                or not has_permission(db, d.decided_by, P.LEGAL_DECISION):
            return None
        decisions.append(d)
    if not decisions or len({d.decision_type for d in decisions}) != 1:
        return None
    review = db.get(M.Review, finding.review_id)
    version = db.get(M.DocumentVersion, review.document_version_id) if review else None
    return {"decision_ids": [str(d.id) for d in decisions],
            "decision_type": decisions[-1].decision_type.value,
            "decided_by": str(decisions[-1].decided_by),
            "decided_at": decisions[-1].created_at.isoformat(),
            "from_version_number": version.version_number if version else None,
            "from_finding_id": str(finding.id)}


def _carry_stands(db: DBSession, finding: M.Finding) -> bool:
    """`AM-326` r1: a carried point is decided only while its ORIGINAL decision stands now
    (`_decided` on the Finding it was carried from — every earlier hop re-checked)."""
    carried = carried_forward(db, finding.id)
    origin = db.get(M.Finding, UUID(carried["from_finding_id"])) \
        if carried and carried.get("from_finding_id") else None
    return origin is not None and origin.id != finding.id \
        and _decided(db, origin) is not None


_workflow.CARRY_STANDS = _carry_stands        # derive_finding_status reads it (AM-326 r1)


def refresh_carried(db: DBSession) -> int:
    """`AM-326` r1: the stored status of every carried point, derived again — a chain
    that no longer stands (the decider lost `legal.decision`, a later REJECT or escalation
    on an earlier version) puts the point back in Legal's queue and To-do, and a chain
    that stands again takes it out. Run after a role or permission change and when a
    To-do is read. Returns how many changed.

    ponytail: one pass over every carried Finding; scope it to the changed user's
    decisions if the carried set grows into the tens of thousands."""
    changed = 0
    ids = db.execute(select(M.AuditEvent.entity_id).where(
        M.AuditEvent.action == DECISION_CARRIED_FORWARD,
        M.AuditEvent.entity_type == "finding")).scalars().all()
    for finding in db.execute(select(M.Finding).where(
            M.Finding.id.in_(set(ids)))).scalars():
        status = derive_finding_status(db, finding,
                                       escalated=is_escalated(db, finding.id))
        if status is not finding.status:
            finding.status = status
            changed += 1
    if changed:
        db.flush()
    return changed


def standing_decision(db: DBSession, finding: M.Finding) -> dict | None:
    """`AM-324` r1: what Legal decision stands on ``finding`` NOW — the one check both the
    carry (`carry_forward`) and every use of a carried decision (a carried acceptance,
    `AM-323` r2) run, so they cannot diverge: `_decided`, every hop re-checked at the
    moment of use (in effect, not superseded, no escalation on any hop, the decider
    still holding `legal.decision`)."""
    return _decided(db, finding)


def _requirement(db: DBSession, requirement_version_id: UUID) -> UUID | None:
    rv = db.get(M.RequirementVersion, requirement_version_id)
    return rv.requirement_id if rv else None


def carry_forward(db: DBSession, review: M.Review, *,
                  request_id: str | None = None) -> int:
    """`AM-317` r7 (owner, 2026-11-09, option a; amends Step 26 r10/r12): a point Legal
    decided on an earlier version of the SAME contract stays decided on this one when
    the Finding reads byte-identical text (spacing aside — `_text_hash`) against the
    SAME requirement and company standard version, with the same classification and
    rule outcome. The nearest earlier version holding the point is compared; if it was
    itself carried, the original decision is what is referenced. Recorded as one
    `decision.carried_forward` audit row per Finding (actor none — code did it), naming
    the original decision(s), decider and version; no Legal Decision is written, the
    classification is untouched (never MATCH), and the derived status reads RESOLVED
    until the point is escalated. Anything that differs — a word, the standard, the
    outcome, an undecided or clarification-pending earlier point — stays open
    (rule 15). Idempotent. Returns how many."""
    version = db.get(M.DocumentVersion, review.document_version_id)
    if version is None:
        return 0
    earlier = [(v, r) for v in db.execute(
        select(M.DocumentVersion).where(
            M.DocumentVersion.contract_id == version.contract_id,
            M.DocumentVersion.version_number < version.version_number)
        .order_by(M.DocumentVersion.version_number.desc())).scalars()
        if (r := db.execute(select(M.Review).where(M.Review.document_version_id == v.id)
                            .order_by(M.Review.created_at.desc()).limit(1)).scalar())]
    if not earlier:
        return 0
    mine = _signatures(db, review)
    theirs = [(v, _signatures(db, r)) for v, r in earlier]
    carried = 0
    for finding_id, (rv, standard, read) in mine.items():
        finding = db.get(M.Finding, finding_id)
        if (finding is None or finding.status is not FindingStatus.DECISION_REQUIRED
                or carried_forward(db, finding_id) is not None
                or is_escalated(db, finding_id)
                or db.execute(select(M.LegalDecision.id).where(
                    M.LegalDecision.finding_id == finding_id).limit(1)).first()):
            continue
        point = _requirement(db, rv)
        prior = next(((fid, sig) for _, sigs in theirs for fid, sig in sigs.items()
                      if _requirement(db, sig[0]) == point), None)   # nearest holding it
        if prior is None or prior[1] != (rv, standard, read):
            continue
        earlier_finding = db.get(M.Finding, prior[0])
        origin = _decided(db, earlier_finding) if earlier_finding else None
        if origin is None:
            continue
        A.record(db, action=A.DECISION_CARRIED_FORWARD, entity_type="finding",
                 entity_id=finding_id, actor_id=None, request_id=request_id,
                 after={**origin, "carried_via_finding_id": str(prior[0]),
                        "review_id": str(review.id),
                        "requirement_version_id": str(rv),
                        "company_standard_version_id": str(standard) if standard
                        else None,
                        "same_text": "byte-identical after spacing normalisation"})
        finding.status = derive_finding_status(db, finding)
        carried += 1
    db.flush()
    return carried
