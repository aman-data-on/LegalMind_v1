"""The closing step of a deal — stamp duty, who signed, the signed copy, "Mark signed"
(CLM flow 5 "Final"; `AM-292`, `AM-297`, `AM-276`).

Five routes, each through `Guard` before anything is read (rule 18):

* ``GET  /contracts/{id}/execution`` — the current record (or a pre-fill from the client
  profile and the template answers), what still stops "Mark signed", and the signed
  copy compared with the agreed version. READ traversal.
* ``POST /contracts/{id}/execution`` — start the record (409 once one exists).
* ``PATCH /contracts/{id}/execution`` — change it, naming ``expected_version``.
* ``POST /contracts/{id}/execution/accept-differences`` — a `legal.decision` holder
  accepts the signed copy's differences from the agreed version, with a reason.
* ``POST /contracts/{id}/mark-signed`` — the final row; the signed copy becomes the
  FINAL_SIGNED version and the stage SIGNED follows (`domain.deal_stage`).

APPEND-ONLY (`AM-292` r3): every save is a new row; the current record is the highest
``version_number``, which is the ``expected_version`` a save names. After "Mark signed"
the database refuses any further row (`legalmind_execution_sealed`).

LegalMind asserts NO stamp article, rate or requirement (`AM-292` r2, rules 7 and 21):
the duty is text as the person typed it; "not stamped yet" is the person's choice,
recorded with who acknowledged that the instrument cannot be used in evidence until it
is stamped. Writes are the owner's, a collaborator's or the Lead's (`AM-259` r2) — a
lawyer on a Legal basis on `legal.decision` (`AM-288` r2) — as every negotiation write.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select

from legalmind.analysis import negotiation
from legalmind.analysis.version_comparison import ComparisonNotPossible
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import Conflict
from legalmind.api.schemas import (
    DifferencesAccept,
    ExecutionUpdate,
    ExecutionWrite,
    MarkSigned,
)
from legalmind.api.serializers import serialize_document_version
from legalmind.db import models as M
from legalmind.security import audit
from legalmind.security import permissions as P

router = APIRouter(tags=["execution"], route_class=CommitBeforeResponse)

FINAL_SIGNED = "FINAL_SIGNED"
#: `AM-298`: a contract filed as already signed — no negotiation in LegalMind
SIGNED_OUTSIDE = "SIGNED_OUTSIDE"
_READY = {"SIGN_AS_IS", "SIGN_WITH_CHANGES"}
#: the record's own fields, carried from row to row
FIELDS = ("stamp_method", "stamp_reference", "stamp_state", "duty_paid", "stamped_on",
          "not_stamped_ack_by", "signatories", "seal_used", "witnesses",
          "signed_document_version_id", "differences_accepted_by", "differences_reason",
          "origin")
PARTIES = ("OURS", "CLIENT")
PARTY_WORDS = {"OURS": "us", "CLIENT": "the client"}


class SigningNotReady(Conflict):
    """409 — "Mark signed" is refused; ``blockers`` says every reason, in plain words."""

    code = "SIGNING_NOT_READY"

    def __init__(self, blockers: list[dict]) -> None:
        super().__init__(" ".join(b["message"] for b in blockers))
        self.extra = {"blockers": blockers}


# ------------------------------------------------------------------ reading
def current(db, contract_id: UUID) -> M.Execution | None:
    return db.execute(select(M.Execution).where(M.Execution.contract_id == contract_id)
                      .order_by(M.Execution.version_number.desc()).limit(1)).scalar_one_or_none()


def signed_copy_ids(db, contract_ids: list[UUID]) -> set[UUID]:
    """The signed copies named on each contract's CURRENT record — not yet the agreed
    text's successor, so the stage reads past them until "Mark signed"."""
    out: dict[UUID, UUID | None] = {}
    for cid, vid in db.execute(
            select(M.Execution.contract_id, M.Execution.signed_document_version_id)
            .where(M.Execution.contract_id.in_(contract_ids))
            .order_by(M.Execution.version_number.desc())).tuples():
        out.setdefault(cid, vid)
    return {v for v in out.values() if v is not None}


def _role(v: M.DocumentVersion) -> str | None:
    return (v.doc_metadata or {}).get("version_role")


def negotiated(db, contract_id: UUID, version_id: UUID) -> str | None:
    """Why this contract cannot be FILED as signed (`AM-298` r1) — it was negotiated in
    LegalMind, so only "Mark signed" signs it — or None. Negotiated: an execution record,
    a client's round, a version sent or our reply, an answered change, or a contract
    decision on another version."""
    if current(db, contract_id) is not None:
        return "this contract has a signing record; finish it in Record signing"
    others = list(db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract_id,
        M.DocumentVersion.id != version_id)).scalars())
    ids = [v.id for v in others]
    C = M.ComparisonChoice
    if any(_role(v) == "CLIENT_MODIFIED" or v.sent_at is not None
           or (v.doc_metadata or {}).get("reply_to") for v in others) or (ids and (
            db.execute(select(C.id).where(C.left_version_id.in_(ids)
                                          | C.right_version_id.in_(ids)).limit(1)).first()
            or db.execute(select(M.ContractOutcomeRecord.id).join(
                M.Review, M.Review.id == M.ContractOutcomeRecord.review_id).where(
                M.Review.document_version_id.in_(ids)).limit(1)).first())):
        return ("this contract was negotiated in LegalMind; record the signing in Record "
                "signing — the stamp duty and who signed come first, then Mark signed")
    return None


def file_as_signed(guard: Guard, version: M.DocumentVersion) -> None:
    """`AM-298` r1: the executed copy of a contract signed outside LegalMind, declared
    Final signed — its record starts with the copy alone; the stamp and who signed are
    optional and added later by the owner, who confirms it to make it final."""
    contract = guard.db.get(M.Contract, version.contract_id)
    assert contract is not None
    refused = negotiated(guard.db, contract.id, version.id)
    if refused:
        raise Conflict(refused)
    row = _append(guard, contract, None, {"signed_document_version_id": version.id,
                                          "origin": SIGNED_OUTSIDE})
    _audit(guard, contract, audit.EXECUTION_RECORDED, row, origin=SIGNED_OUTSIDE,
           signed_document_version_id=str(version.id))


def _legacy_signed(db, contract_id: UUID) -> bool:
    """`AM-298` r4: a version declared FINAL_SIGNED before the signing step, with no
    record — signed outside LegalMind, and nothing is required of it."""
    return db.execute(select(M.DocumentVersion.id).where(
        M.DocumentVersion.contract_id == contract_id,
        M.DocumentVersion.doc_metadata["version_role"].astext == FINAL_SIGNED)
        .limit(1)).first() is not None


def _str(value: UUID | None) -> str | None:
    return str(value) if value is not None else None


def agreed(db, contract_id: UUID, signed_copy: UUID | None) -> dict[str, Any]:
    """The agreed version (the latest that is not the signed copy), its latest Review,
    the contract decision on it (none once reopened, `AM-175`) and its open points."""
    versions = [v for v in db.execute(
        select(M.DocumentVersion).where(M.DocumentVersion.contract_id == contract_id)
        .order_by(M.DocumentVersion.version_number)).scalars()
        if v.id != signed_copy and _role(v) != FINAL_SIGNED]
    version = versions[-1] if versions else None
    review = outcome = None
    open_points = 0
    if version is not None:
        review = db.execute(select(M.Review)
                            .where(M.Review.document_version_id == version.id)
                            .order_by(M.Review.created_at.desc(), M.Review.id.desc())
                            .limit(1)).scalar_one_or_none()
    if review is not None:
        outcome = db.execute(select(M.ContractOutcomeRecord)
                             .where(M.ContractOutcomeRecord.review_id == review.id)
                             .order_by(M.ContractOutcomeRecord.version_number.desc())
                             .limit(1)).scalar_one_or_none()
        reopened = review.reopened_at
        if outcome is not None and reopened and reopened > outcome.created_at:
            outcome = None
        open_points = len(db.execute(select(M.Finding.id).where(
            M.Finding.review_id == review.id,
            M.Finding.status.in_(negotiation._UNDECIDED))).all())
    return {"version": version, "review": review,
            "outcome": outcome.outcome.value if outcome else None,
            "open_points": open_points}


def compare(guard: Guard, contract: M.Contract, agreed_version: M.DocumentVersion | None,
            signed_id: UUID | None) -> dict | None:
    """The signed copy against the agreed version, by the negotiation change detection
    (`analysis.negotiation.changes`). Text only for a `document.view` holder."""
    if signed_id is None or agreed_version is None:
        return None
    signed = guard.db.get(M.DocumentVersion, signed_id)
    if signed is None or signed.contract_id != contract.id:
        return None
    base = {"agreed": {"document_version_id": str(agreed_version.id),
                       "version_number": agreed_version.version_number},
            "signed": {"document_version_id": str(signed.id),
                       "version_number": signed.version_number,
                       "file_hash": signed.file_hash}}
    try:
        listed = negotiation.changes(guard.db, contract, agreed_version, signed,
                                     legal_position=False)
    except ComparisonNotPossible as exc:
        return {**base, "status": "NOT_COMPARED", "reason": str(exc), "differences": []}
    text = P.DOCUMENT_VIEW in guard.permissions
    differences = [{"kind": c["kind"], "clause": c["clause"], "page": c["page"],
                    **({"agreed_text": (c["before"] or {}).get("text"),
                        "signed_text": (c["after"] or {}).get("text")} if text else {})}
                   for c in listed["changes"]]
    return {**base, "status": "DIFFERS" if differences else "MATCHES", "reason": None,
            "differences": differences}


def blockers(facts: dict, record: M.Execution | None, comparison: dict | None,
             signed_id: UUID | None) -> list[dict]:
    """Every reason "Mark signed" is refused, in plain words — empty when it may go."""
    out: list[dict] = []

    def no(code: str, message: str) -> None:
        out.append({"code": code, "message": message})

    if facts["outcome"] not in _READY:
        no("NOT_DECIDED", "The contract decision is not “Sign as is” or “Sign after our "
                          "changes”.")
    if facts["open_points"]:
        n = facts["open_points"]
        no("OPEN_POINTS", f"{n} point{'s are' if n != 1 else ' is'} still undecided.")
    if record is None:
        no("NO_RECORD", "Record the stamp duty and who signed first.")
        return out
    if record.stamp_method == "NOT_STAMPED":
        if record.not_stamped_ack_by is None:
            no("STAMP_NOT_ACKNOWLEDGED",
               "Confirm you understand an unstamped contract cannot be used as evidence "
               "until it is stamped.")
    elif not (record.stamp_method and record.stamp_reference and record.stamp_state
              and record.duty_paid):
        no("STAMP_MISSING", "Record how it was stamped: the certificate or stamp paper "
                            "number, the state and the duty paid.")
    for party in PARTIES:
        people = [s for s in record.signatories or [] if s.get("party") == party]
        if not people or not all(s.get("name") and s.get("designation")
                                 and s.get("authority_reference") for s in people):
            no(f"AUTHORITY_MISSING_{party}",
               f"Record who signed for {PARTY_WORDS[party]}: name, designation and their "
               "authority (board resolution or authority letter).")
    if signed_id is None:
        no("NO_SIGNED_COPY", "Upload the signed copy.")
    elif comparison is None:
        no("NO_SIGNED_COPY", "The signed copy is not a version of this contract.")
    elif comparison["status"] != "MATCHES" and not (
            record.differences_accepted_by
            and record.signed_document_version_id == signed_id):
        if comparison["status"] == "NOT_COMPARED":
            no("COPY_NOT_COMPARED",
               "The signed copy could not be compared with the agreed version yet: "
               f"{comparison['reason']}.")
        else:
            n = len(comparison["differences"])
            no("COPY_DIFFERS",
               f"The signed copy differs from the agreed version in {n} "
               f"place{'s' if n != 1 else ''}. Upload the right copy, or a person with "
               "Legal Decision authority accepts the differences with a reason.")
    return out


def _prefill(guard: Guard, contract: M.Contract) -> dict:
    """Signatories from the template answers, then the client profile — a suggestion the
    person confirms, never a record until saved."""
    by_role: dict[str, Any] = {}
    draft = guard.db.execute(select(M.ContractDraft).where(
        M.ContractDraft.contract_id == contract.id)
        .order_by(M.ContractDraft.created_at.desc()).limit(1)).scalar_one_or_none()
    if draft is not None:
        tv = guard.db.get(M.TemplateVersion, draft.template_version_id)
        for var in (tv.variables if tv else None) or []:
            value = (draft.values or {}).get(var.get("key"))
            if isinstance(value, str) and value.strip():
                by_role.setdefault(var.get("role") or var.get("key"), value.strip())
    cp = guard.db.get(M.Counterparty, contract.counterparty_id) \
        if contract.counterparty_id else None

    def person(party: str, prefix: str, name: str | None, designation: str | None,
               authority: str | None) -> dict:
        return {"party": party,
                "name": by_role.get(f"{prefix}_signatory_name") or name,
                "designation": (by_role.get(f"{prefix}_signatory_designation")
                                or designation),
                "authority_reference": by_role.get(f"{prefix}_authority") or authority}

    return {"signatories": [
        person("OURS", "our", None, None, None),
        person("CLIENT", "counterparty", cp.signatory_name if cp else None,
               cp.signatory_designation if cp else None,
               cp.authority_reference if cp else None)]}


def _serialize(record: M.Execution | None) -> dict | None:
    if record is None:
        return None
    return {"version": record.version_number, "origin": record.origin,
            "stamp_method": record.stamp_method,
            "stamp_reference": record.stamp_reference, "stamp_state": record.stamp_state,
            "duty_paid": record.duty_paid,
            "stamped_on": record.stamped_on.isoformat() if record.stamped_on else None,
            "not_stamped_acknowledged": record.not_stamped_ack_by is not None,
            "signatories": record.signatories or [], "seal_used": record.seal_used,
            "witnesses": record.witnesses or [],
            "signed_document_version_id": _str(record.signed_document_version_id),
            "differences_accepted": record.differences_accepted_by is not None,
            "differences_reason": record.differences_reason,
            "comparison": record.comparison,
            "signed_at": record.signed_at.isoformat() if record.signed_at else None,
            "recorded_by": str(record.recorded_by),
            "recorded_at": record.created_at.isoformat()}


def _state(guard: Guard, contract: M.Contract, signed_id: UUID | None = None) -> dict:
    record = current(guard.db, contract.id)
    if record is None and _legacy_signed(guard.db, contract.id):
        return {"execution": None, "blockers": [], "comparison": None, "signed": True,
                "legacy": True}
    if record is not None and record.origin == SIGNED_OUTSIDE:
        # filed as signed: signed already; the record stays editable until confirmed
        return {"execution": _serialize(record), "blockers": [], "comparison": None,
                "signed": True, "confirmed": record.signed_at is not None}
    if record is not None and record.signed_at is not None:
        return {"execution": _serialize(record), "blockers": [], "comparison":
                record.comparison, "signed": True}
    signed_id = signed_id or (record.signed_document_version_id if record else None)
    facts = agreed(guard.db, contract.id, signed_id)
    comparison = compare(guard, contract, facts["version"], signed_id)
    out = {"execution": _serialize(record),
           "agreed": ({"document_version_id": str(facts["version"].id),
                       "version_number": facts["version"].version_number}
                      if facts["version"] else None),
           "decision": facts["outcome"], "open_points": facts["open_points"],
           "comparison": comparison,
           "blockers": blockers(facts, record, comparison, signed_id), "signed": False,
           "can_accept_differences": P.LEGAL_DECISION in guard.permissions}
    if record is None:
        out["prefill"] = _prefill(guard, contract)
    return out


# ------------------------------------------------------------------ writing
def _append(guard: Guard, contract: M.Contract, prior: M.Execution | None,
            changes: dict[str, Any], **extra: Any) -> M.Execution:
    values = {f: getattr(prior, f) for f in FIELDS} if prior else {
        "signatories": [], "witnesses": []}
    values.update(changes)
    row = M.Execution(contract_id=contract.id,
                      version_number=(prior.version_number + 1) if prior else 1,
                      recorded_by=guard.user_id, **values, **extra)
    guard.db.add(row)
    guard.db.flush()
    return row


def _changes(guard: Guard, contract: M.Contract, prior: M.Execution | None,
             body: ExecutionWrite) -> dict[str, Any]:
    sent = body.model_fields_set - {"expected_version"}
    out: dict[str, Any] = {}
    for key in sent - {"not_stamped_acknowledged", "signatories"}:
        out[key] = getattr(body, key)
    if "signatories" in sent:
        out["signatories"] = [s.model_dump(mode="json") for s in body.signatories or []]
    copy_id = body.signed_document_version_id
    if "signed_document_version_id" in sent and copy_id is not None:
        version = guard.db.get(M.DocumentVersion, copy_id)
        if version is None or version.contract_id != contract.id:
            raise Conflict("the signed copy must be a version of this contract")
    method = out.get("stamp_method", prior.stamp_method if prior else None)
    if "not_stamped_acknowledged" in sent:
        # the person who first acknowledged it stays its actor while it stands
        kept = prior.not_stamped_ack_by if prior else None
        out["not_stamped_ack_by"] = ((kept or guard.user_id)
                                     if body.not_stamped_acknowledged else None)
    if method != "NOT_STAMPED":
        out["not_stamped_ack_by"] = None
    elif out.get("not_stamped_ack_by", prior.not_stamped_ack_by if prior else None):
        # not stamped: no stamp details stand beside it
        out.update(stamp_reference=None, duty_paid=None, stamped_on=None)
    if prior is not None and "signed_document_version_id" in out \
            and out["signed_document_version_id"] != prior.signed_document_version_id:
        out.update(differences_accepted_by=None, differences_reason=None)  # a new copy
    return out


def _audit(guard: Guard, contract: M.Contract, action: str, row: M.Execution,
           **after: Any) -> None:
    """Which fields, never a signatory's name or a reference's text (personal data and
    the caller's own words stay in the record, not the audit row)."""
    audit.record(guard.db, action=action, entity_type="contract", entity_id=contract.id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 after={"execution_version": row.version_number,
                        "stamp_method": row.stamp_method, **after})


@router.get("/contracts/{contract_id}/execution")
def get_execution(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_readable(contract_id, P.CONTRACT_VIEW)
    return data(_state(guard, contract))


@router.post("/contracts/{contract_id}/execution", status_code=201)
def start_execution(contract_id: UUID, body: ExecutionWrite | None = Body(None),
                    guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    if current(guard.db, contract.id) is not None:
        raise Conflict("this contract already has an execution record; change it instead")
    if _legacy_signed(guard.db, contract.id):
        raise Conflict("this contract is already signed outside LegalMind")
    body = body or ExecutionWrite()
    row = _append(guard, contract, None, _changes(guard, contract, None, body))
    _audit(guard, contract, audit.EXECUTION_RECORDED, row,
           changed=sorted(body.model_fields_set))
    return data(_state(guard, contract))


@router.patch("/contracts/{contract_id}/execution")
def update_execution(contract_id: UUID, body: ExecutionUpdate,
                     guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    prior = _expect(guard, contract, body.expected_version)
    if prior.origin == SIGNED_OUTSIDE \
            and "signed_document_version_id" in body.model_fields_set \
            and body.signed_document_version_id != prior.signed_document_version_id:
        raise Conflict("a contract filed as signed keeps the copy it was filed with")
    row = _append(guard, contract, prior, _changes(guard, contract, prior, body))
    _audit(guard, contract, audit.EXECUTION_RECORDED, row,
           changed=sorted(body.model_fields_set - {"expected_version"}))
    return data(_state(guard, contract))


def _expect(guard: Guard, contract: M.Contract, expected: int) -> M.Execution:
    # the contract row, locked: two saves at once cannot both read the same version
    guard.db.execute(select(M.Contract.id).where(M.Contract.id == contract.id)
                     .with_for_update())
    prior = current(guard.db, contract.id)
    if prior is None:
        raise Conflict("this contract has no execution record yet")
    if prior.signed_at is not None:
        raise Conflict("this contract is signed; its execution record is final")
    if prior.version_number != expected:
        raise Conflict("the execution record was changed elsewhere; reload it")
    return prior


@router.post("/contracts/{contract_id}/execution/accept-differences")
def accept_differences(contract_id: UUID, body: DifferencesAccept,
                       guard: Guard = Depends(get_guard)) -> dict:
    """A `legal.decision` holder who can read the contract accepts the signed copy's
    differences from the agreed version — for THAT copy only, with a reason."""
    contract = guard.contract_readable(contract_id, P.LEGAL_DECISION)
    if contract.archived_at is not None:
        raise Conflict("this contract is archived; restore it first")
    prior = _expect(guard, contract, body.expected_version)
    if prior.signed_document_version_id is None:
        raise Conflict("upload the signed copy first")
    facts = agreed(guard.db, contract.id, prior.signed_document_version_id)
    comparison = compare(guard, contract, facts["version"],
                         prior.signed_document_version_id)
    if comparison is None or comparison["status"] == "MATCHES":
        raise Conflict("the signed copy matches the agreed version; nothing to accept")
    row = _append(guard, contract, prior, {"differences_accepted_by": guard.user_id,
                                           "differences_reason": body.reason})
    _audit(guard, contract, audit.EXECUTION_DIFFERENCES_ACCEPTED, row,
           signed_document_version_id=str(prior.signed_document_version_id),
           comparison=comparison["status"], differences=len(comparison["differences"]))
    return data(_state(guard, contract))


@router.post("/contracts/{contract_id}/mark-signed")
def mark_signed(contract_id: UUID, body: MarkSigned,
                guard: Guard = Depends(get_guard)) -> dict:
    """The deal is signed (`AM-292` r1): refused (409 SIGNING_NOT_READY, every reason)
    until the decision, the points, the stamp, both authorities and the signed copy
    allow it. The signed copy becomes the FINAL_SIGNED version; the record is final."""
    contract = guard.contract_negotiable(contract_id, P.CONTRACT_UPDATE)
    prior = _expect(guard, contract, body.expected_version)
    signed = guard.db.get(M.DocumentVersion, body.document_version_id)
    if signed is None or signed.contract_id != contract.id:
        raise Conflict("the signed copy must be a version of this contract")
    if prior.origin == SIGNED_OUTSIDE:      # `AM-298` r1: confirming never blocks
        if signed.id != prior.signed_document_version_id:
            raise Conflict("a contract filed as signed keeps the copy it was filed with")
        row = _append(guard, contract, prior, {}, signed_at=datetime.now(UTC))
        _audit(guard, contract, audit.CONTRACT_SIGNED, row, origin=SIGNED_OUTSIDE,
               signed_document_version_id=str(signed.id), file_hash=signed.file_hash)
        return data({**_state(guard, contract),
                     "document_version": serialize_document_version(signed)})
    facts = agreed(guard.db, contract.id, signed.id)
    if facts["version"] is not None \
            and signed.version_number <= facts["version"].version_number:
        raise Conflict("upload the signed copy as a new version after the agreed one")
    comparison = compare(guard, contract, facts["version"], signed.id)
    refused = blockers(facts, prior, comparison, signed.id)
    if refused:
        raise SigningNotReady(refused)
    assert comparison is not None and facts["version"] is not None
    keep = {k: v for k, v in comparison.items() if k != "differences"} | {
        "differences": [{k: d[k] for k in ("kind", "clause", "page")}
                        for d in comparison["differences"]]}
    now = datetime.now(UTC)
    changes = {"signed_document_version_id": signed.id}
    if prior.signed_document_version_id != signed.id:
        changes.update(differences_accepted_by=None, differences_reason=None)
    row = _append(guard, contract, prior, changes, comparison=keep, signed_at=now)
    signed.doc_metadata = {**(signed.doc_metadata or {}), "version_role": FINAL_SIGNED}
    guard.db.flush()
    _audit(guard, contract, audit.CONTRACT_SIGNED, row,
           signed_document_version_id=str(signed.id), file_hash=signed.file_hash,
           agreed_document_version_id=str(facts["version"].id),
           decision=facts["outcome"], comparison=comparison["status"],
           differences_accepted=row.differences_accepted_by is not None)
    return data({**_state(guard, contract),
                 "document_version": serialize_document_version(signed)})
