"""Changes after signing — an Amendment is its own contract record (`AM-267`, built
under `AM-309`; research R-9, design §6).

* ``POST /contracts/{id}/amendments`` — start an AMENDMENT of a SIGNED contract: a new
  contract record, the same client, ``governed_by_contract_id`` the parent (the database
  trigger holds the rule whoever writes it: parent signed, never an amendment, the same
  non-null client). Its first version is a copy of the agreed final contract — the
  latest signed amendment's, else the parent's — when that is ours and its signed copy
  matched it; otherwise it starts empty and the amendment's text is uploaded. Its own
  Review, execution record and stamp follow as for any contract (R-11). Audited
  `contract.amendment_created`.
* "Prepare amendment" is ``POST /contracts/{amendment}/package``: it needs a published
  AMENDMENT template whose frame Legal approved — none exists, so 409
  NO_AMENDMENT_TEMPLATE. None is ever authored here (rules 7/21). Since `AM-310` it
  makes the CHANGES-ONLY instrument (`drafting.instrument`); the whole contract
  restated is Legal's explicit choice.
* ``GET /contracts/{id}/effective`` — the signed contract's effective text, each signed
  amendment applied in signing order, the original kept beside it (R-9). Fail closed: an
  amendment that cannot be read leaves the current text unstated, with the reason.

Parent and children are reached through the READ traversal; an unreadable one is
omitted, never nulled (`AM-267` r3, SEC-07).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError

from legalmind.analysis import negotiation
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import Conflict
from legalmind.api.routers import execution
from legalmind.api.schemas import AmendmentCreate
from legalmind.api.serializers import serialize_contract, serialize_document_version
from legalmind.api.storage import get_storage
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import (
    effective,
    instrument,
    publish,
    render_contract,
    special_conditions,
)
from legalmind.drafting import model as model_
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import StorageBackend
from legalmind.ingestion.validation import DOCX_MIME
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import require_contract_readable
from legalmind.security.errors import NotVisible
from legalmind.worker.dispatch import dispatch_indexing

router = APIRouter(tags=["amendments"], route_class=CommitBeforeResponse)

AMENDMENT = "AMENDMENT"
#: why an amendment starts empty — one sentence whatever the cause (SEC-07)
NOT_COPIED = ("Nothing was copied: the agreed text in force is not one LegalMind can "
              "copy for you — upload the amendment's text.")
#: why the current text is not stated past an amendment the caller cannot read —
#: one sentence, naming nothing about it (SEC-07)
NOT_STATED = ("The current text is not stated: the agreed text in force is not one "
              "LegalMind can read for you.")


#: the governed-by trigger's SQLSTATEs (restrict_violation, check_violation) and prefix
_TRIGGER_CODES = {"23001", "23514"}
_TRIGGER_PREFIX = "contracts: "


def refusal(exc: DBAPIError) -> str:
    """The governed-by trigger's own words (its first line), for a 409. Any other
    database error is re-raised as it was — never a 409 carrying Postgres text."""
    first = str(exc.orig).split("\n")[0]
    if getattr(exc.orig, "pgcode", None) not in _TRIGGER_CODES \
            or not first.startswith(_TRIGGER_PREFIX):
        raise exc
    return first.removeprefix(_TRIGGER_PREFIX)


def _readable(guard: Guard, contract_id: UUID | None) -> M.Contract | None:
    if contract_id is None:
        return None
    try:
        return require_contract_readable(guard.db, guard.user_id, contract_id)
    except NotVisible:
        return None


def _signed_at(db, contract_id: UUID) -> Any:
    """When the contract was signed — its sealed execution record, or (`AM-298` r4) a
    version declared FINAL_SIGNED before the signing step (then the version's time)."""
    record = execution.current(db, contract_id)
    if record is not None and record.signed_at is not None:
        return record.signed_at
    return db.execute(select(M.DocumentVersion.created_at).where(
        M.DocumentVersion.contract_id == contract_id,
        M.DocumentVersion.doc_metadata["version_role"].astext == execution.FINAL_SIGNED)
        .order_by(M.DocumentVersion.version_number.desc()).limit(1)).scalar()


def _final_signed(db, contract_id: UUID) -> M.DocumentVersion | None:
    return db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract_id,
        M.DocumentVersion.doc_metadata["version_role"].astext == execution.FINAL_SIGNED)
        .order_by(M.DocumentVersion.version_number.desc()).limit(1)).scalar()


def _children(db, parent_id: UUID) -> list[M.Contract]:
    """The parent's AMENDMENTS — an order form it governs is not one."""
    return list(db.execute(select(M.Contract).where(
        M.Contract.governed_by_contract_id == parent_id,
        M.Contract.contract_type == AMENDMENT)
        .order_by(M.Contract.created_at, M.Contract.id)).scalars())


def _signed_amendments(db, parent_id: UUID) -> list[tuple[M.Contract, Any]]:
    """The parent's signed amendments in signing order — every one, readable or not:
    the text in force does not depend on who reads it."""
    signed = [(a, at) for a in _children(db, parent_id)
              if (at := _signed_at(db, a.id)) is not None]
    return sorted(signed, key=lambda x: x[1])


def _agreed(db, contract_id: UUID) -> M.DocumentVersion | None:
    """The agreed final contract a signing closed — only when it is ours (a template
    draft) and the signed copy matched it; else None (nothing copied or applied)."""
    record = execution.current(db, contract_id)
    if record is None or record.signed_at is None \
            or record.differences_accepted_by is not None:
        return None
    version = execution.agreed(db, contract_id, record.signed_document_version_id)[
        "version"]
    if version is None or db.execute(select(M.ContractDraft.id).where(
            M.ContractDraft.document_version_id == version.id)).first() is None:
        return None
    return version


def relations(guard: Guard, contract: M.Contract) -> dict[str, Any]:
    """``governed_by`` (the readable parent) and ``amendments`` (the readable children)
    for ``GET /contracts/{id}`` — an unreadable one omitted, never nulled (r3)."""
    out: dict[str, Any] = {}
    parent = _readable(guard, contract.governed_by_contract_id)
    if parent is not None:
        out["governed_by"] = {"id": str(parent.id), "name": parent.name,
                              "contract_type": parent.contract_type}
    out["amendments"] = [
        {"id": str(a.id), "name": a.name, "status": a.status.value,
         "signed": _signed_at(guard.db, a.id) is not None,
         "archived": a.archived_at is not None}
        for a in _children(guard.db, contract.id) if _readable(guard, a.id) is not None]
    return out


@router.post("/contracts/{contract_id}/amendments", status_code=201)
def create_amendment(contract_id: UUID, body: AmendmentCreate | None = Body(None),
                     guard: Guard = Depends(get_guard),
                     storage: StorageBackend = Depends(get_storage)) -> dict:
    """Start an amendment of this signed contract (`AM-309`). 404 when the contract is
    out of the caller's read scope; 409 — with the reason — when it is not signed, is an
    amendment itself, is archived, or has no client linked."""
    from legalmind.api.routers.contracts import _require_linkable  # circular at import
    from legalmind.api.routers.negotiation import _review_reply  # circular at import

    db = guard.db
    parent = guard.contract_readable(contract_id, P.CONTRACT_VIEW)
    guard.permission(P.CONTRACT_CREATE)
    if parent.archived_at is not None:
        raise Conflict("this contract is archived; restore it to amend it")
    if parent.governed_by_contract_id is not None or parent.contract_type == AMENDMENT:
        raise Conflict("an amendment amends the signed contract, never another "
                       "amendment — start it from the contract")
    if _signed_at(db, parent.id) is None:
        raise Conflict("only a signed contract is amended — until it is signed, change "
                       "it in its own negotiation")
    if parent.counterparty_id is None:
        raise Conflict("this contract has no client linked — an amendment is with the "
                       "same client, so link it first")
    guard.permission(P.CONTRACT_UPDATE)          # naming who the deal is with (AB-13 r5)
    _require_linkable(guard, parent.counterparty_id)
    execution._lock(guard, parent)               # two starts at once: the second waits
    for open_ in _children(db, parent.id):
        if open_.archived_at is None and _signed_at(db, open_.id) is None:
            # SEC-07: named only to a caller who can read it
            which = (f"“{open_.name}”" if _readable(guard, open_.id) is not None
                     else "an amendment of this contract")
            raise Conflict(f"{which} is still open — sign or archive it before "
                           "starting another")
    signed = _signed_amendments(db, parent.id)
    source = signed[-1][0] if signed else parent  # the text in force now
    # SEC-07: the text in force may be an amendment this caller cannot read. Then nothing
    # is copied, and every reason is said in ONE sentence, so the reply never tells
    # whether an amendment the caller cannot see exists (never an older text instead).
    base = _agreed(db, source.id) if _readable(guard, source.id) is not None else None
    amendment = M.Contract(
        owner_id=guard.user_id,
        name=(body.name if body and body.name else f"Amendment to {parent.name}"),
        contract_type=AMENDMENT, counterparty_id=parent.counterparty_id,
        issuing_entity=parent.issuing_entity, status=E.ContractStatus.DRAFT,
        governed_by_contract_id=parent.id)
    try:
        with db.begin_nested():
            db.add(amendment)
            db.flush()
    except DBAPIError as exc:              # the trigger's own refusal (a race): said so
        raise Conflict(refusal(exc)) from exc
    version = _copy(guard, storage, amendment, base) if base is not None else None
    audit.record(db, action=audit.CONTRACT_AMENDMENT_CREATED, entity_type="contract",
                 entity_id=amendment.id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"governed_by_contract_id": str(parent.id),
                        "counterparty_id": str(parent.counterparty_id),
                        "copied_from_version_id": str(base.id) if base else None,
                        "document_version_id": str(version.id) if version else None})
    if version is not None:
        _review_reply(guard, version)
    return data({**serialize_contract(amendment), **relations(guard, amendment),
                 "document_version": (serialize_document_version(version)
                                      if version else None),
                 **({"starts_empty": NOT_COPIED} if version is None else {})})


def _as_amended(db, amendment: M.Contract, record: dict
                ) -> tuple[bytes, M.ContractDraft, str] | None:
    """`AM-310`: after a changes-only amendment the text in force is no single signed
    file — the contract's template with every agreed entry (the instrument's ``basis``
    record), rendered as a final contract would be. None where it cannot be rebuilt."""
    draft = db.get(M.ContractDraft, UUID(record["draft_id"]))
    tv = db.get(M.TemplateVersion, draft.template_version_id) if draft else None
    frame = special_conditions.frame_row(db, tv, record["frame"]) if tv else None
    if draft is None or tv is None or frame is None:
        return None
    clauses = {k: publish.clause_dict(c)
               for k, c in publish.pinned_clauses(db, tv).items()}
    try:
        model = model_.resolve(publish.template_dict(tv), clauses, draft.values, special={
            "frame": publish.clause_dict(frame), "entries": record["entries"],
            "config": special_conditions.config(tv) or {}})
    except model_.ModelError:
        return None
    digest = model_.model_hash(model)
    return render_contract.render(model, tv.assets,
                                  contract_ref=str(amendment.id)[:8].upper(),
                                  version_number=1, model_hash=digest), draft, digest


def _copy(guard: Guard, storage: StorageBackend, amendment: M.Contract,
          base: M.DocumentVersion) -> M.DocumentVersion | None:
    """The amendment's v1: the agreed final contract's own file, as our Company draft,
    ``copy_of`` it, with its Special Conditions record and its template draft — so it
    reads as the effective text it is, and a later round starts from its entries. After
    a changes-only amendment (`AM-310`) it is the contract as amended, rebuilt."""
    db = guard.db
    meta = base.doc_metadata or {}
    if meta.get("amendment"):
        basis = meta["amendment"]["basis"]
        made = _as_amended(db, amendment, basis)
        if made is None:
            return None
        data, draft, digest = made
        sc: dict[str, Any] | None = {k: basis[k] for k in ("entries", "trace", "frame")}
        name, mime = "as amended.docx", DOCX_MIME
    else:
        draft = db.execute(select(M.ContractDraft).where(
            M.ContractDraft.document_version_id == base.id)).scalar_one()
        data, digest, name = storage.get(base.storage_key), draft.model_hash, \
            base.original_filename
        sc, mime = meta.get("special_conditions"), base.mime_type
    version = ingest_document(
        db, storage, contract_id=amendment.id, uploaded_by=guard.user_id,
        data=data, filename=name, declared_mime=mime).document_version
    version.doc_metadata = {
        **(version.doc_metadata or {}),
        **{k: meta[k] for k in ("source", "counterparty", "effective_date") if k in meta},
        **({"special_conditions": sc} if sc else {}),
        "version_role": "COMPANY_DRAFT", "copy_of": str(base.id)}
    db.add(M.ContractDraft(
        contract_id=amendment.id, document_version_id=version.id,
        template_version_id=draft.template_version_id, values=draft.values,
        model_hash=digest, renderer_version=render_contract.RENDERER_VERSION
        if meta.get("amendment") else draft.renderer_version,
        clean_storage_key=version.storage_key, created_by=guard.user_id))
    db.flush()
    dispatch_indexing(db, version.id, request_id=guard.request_id)
    return version


def _public(unit: dict) -> dict[str, Any]:
    return {"number": unit["number"], "heading": unit["heading"], "text": unit["text"]}


def _beside(original: list[dict], current: list[dict],
            steps: list[tuple[str | None, set]]) -> dict[str, Any]:
    """The current clauses, each one an amendment changed with its ``original`` text
    (null where it was added), and the ``removed`` ones — paired as the change list
    pairs them (`negotiation._align`), never by number alone (schedules repeat them).
    A changed or removed clause names ``by`` the amendment that made it so: the first
    applied step whose text holds (or, removed, no longer holds) it — only when the
    caller can read that amendment (SEC-07), else the key is absent."""
    def by(unit: dict, present: bool) -> dict[str, str]:
        key = (unit["number"], unit["text"])
        who = next((c for c, held in steps if (key in held) == present), None)
        return {"by": who} if who else {}
    clauses, removed = [], []
    for i, j, _ in negotiation._align(original, current):
        if j is None:
            assert i is not None
            removed.append({**_public(original[i]), **by(original[i], False)})
            continue
        was = original[i]["text"] if i is not None else None
        clauses.append({**_public(current[j]),
                        **({"original": was, **by(current[j], True)}
                           if was != current[j]["text"] else {})})
    return {"clauses": clauses, "removed": removed}


@router.get("/contracts/{contract_id}/effective")
def effective_text(contract_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """The contract as it stands (R-9): the signed copy read as its Special Conditions
    vary it (``original``), then each signed amendment in signing order (``current``),
    every clause the amendments changed carrying its ``original`` text beside it.

    An amendment applies only when its first version is a copy of the agreed text in
    force before it and its own signed copy reads APPLIED; anything else stops the chain
    — ``current.read`` NOT_APPLIED with the reason, its clauses absent (rule 15). An
    amendment's own id answers for its contract. 409 before the contract is signed."""
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    if contract.governed_by_contract_id is not None:
        contract = guard.contract_readable(contract.governed_by_contract_id,
                                           P.DOCUMENT_VIEW)
    db = guard.db
    signed = _final_signed(db, contract.id)
    if signed is None:
        raise Conflict("this contract is not signed yet — its text is its latest version")
    clauses, read, reason = effective.effective_clauses(db, signed.id)
    units = negotiation._units(clauses)
    original = {"document_version_id": str(signed.id),
                "version_number": signed.version_number, "read": read,
                **({"reason": reason} if reason else {}),
                "clauses": [_public(u) for u in units]}
    in_force = _agreed(db, contract.id)
    current: dict[str, Any] = (
        {"read": read, "units": units}
        if read in (effective.NONE, effective.APPLIED)
        else {"read": read, "reason": reason})
    listed = []
    steps: list[tuple[str | None, set]] = []     # each applied amendment's text, in order
    for amendment, at in _signed_amendments(db, contract.id):
        if _readable(guard, amendment.id) is None:
            # SEC-07 / rule 15: an amendment the caller cannot read is never applied for
            # them — the chain stops here, in one sentence that says nothing about it
            if current.get("units") is not None:
                current = {"read": effective.NOT_APPLIED, "reason": NOT_STATED}
            continue
        final = _final_signed(db, amendment.id)
        first = db.execute(select(M.DocumentVersion).where(
            M.DocumentVersion.contract_id == amendment.id)
            .order_by(M.DocumentVersion.version_number).limit(1)).scalar()
        why = None
        if current.get("units") is None:
            why = "the text in force before it could not be read"
        elif final is None:
            why = "its signed copy is not on record"
        elif in_force is None or first is None or \
                (first.doc_metadata or {}).get("copy_of") != str(in_force.id):
            why = "it was not made from the text in force before it"
        else:
            agreed = _agreed(db, amendment.id)
            changes = (agreed.doc_metadata or {}).get("amendment") if agreed else None
            if changes is not None:      # AM-310: its changes, on the text in force
                try:
                    current = {"read": effective.APPLIED, "units": instrument.apply(
                        current["units"], changes["entries"])}
                    in_force = agreed
                except ValueError as exc:
                    why = str(exc)
            else:
                got, status, reason = effective.effective_clauses(db, final.id)
                if status != effective.APPLIED:
                    why = reason or "its Special Conditions could not be read"
                else:
                    current = {"read": status, "units": negotiation._units(got)}
                    in_force = agreed
        if why is None:
            steps.append((str(amendment.id),
                          {(u["number"], u["text"]) for u in current["units"]}))
        if why is not None and current.get("units") is not None:
            current = {"read": effective.NOT_APPLIED,
                       "reason": f"Amendment “{amendment.name}”: {why}."}
        listed.append({"contract_id": str(amendment.id), "name": amendment.name,
                       "signed_at": at.isoformat(),
                       "document_version_id": str(final.id) if final else None,
                       "applied": why is None})
    if current.get("units") is not None:
        current = {"read": current["read"], **_beside(units, current.pop("units"), steps)}
    return data({"contract_id": str(contract.id), "original": original,
                 "amendments": listed, "current": current})
