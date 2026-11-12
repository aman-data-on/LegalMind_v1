"""New contract (slice S5): a PUBLISHED template, a person's answers, v1 reviewed.

* ``GET /templates/published`` — the published templates with their questionnaire
  (`AM-282` r4 / `AM-283`: nothing else is used for a client).
* ``POST /drafts`` · ``GET /drafts`` · ``GET/PATCH /drafts/{id}`` — answers saved on the
  server before v1 (`AM-265` d1): the owner's only, a 404 to anyone else (d2), a stale
  ``expected_version`` is 409.
* ``GET /drafts/{id}/preview`` — the resolved model with every filled value's run tagged
  with its field (``{"t", "var"}``); a field still missing stands in as ``[label]`` and
  is listed in ``missing``.
* ``POST /drafts/{id}/create`` — render → preflight → contract + v1 ``COMPANY_DRAFT``
  through ``ingest_document`` → ``contract_drafts`` row → a Review on the latest snapshot,
  analysed like any upload. The answers are consumed in the same transaction (d4).

No legal logic here: a value the variable admits but our standard does not is rendered as
typed, and the engine's Finding routes that point to Legal (rule 18; zero tolerance).
"""

from __future__ import annotations

import os
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected, Conflict
from legalmind.api.routers.contracts import create_contract
from legalmind.api.routers.counterparties import _readable, _readable_contracts
from legalmind.api.routers.negotiation import _review_reply
from legalmind.api.schemas import Body, ContractCreate
from legalmind.api.storage import get_storage
from legalmind.db import models as M
from legalmind.db.lookup import must_exist
from legalmind.drafting import model as model_
from legalmind.drafting import preflight, publish, render_contract
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.storage import StorageBackend
from legalmind.ingestion.validation import DOCX_MIME
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.errors import NotVisible
from legalmind.worker.dispatch import dispatch_indexing, dispatch_pdf

router = APIRouter(tags=["drafts"], route_class=CommitBeforeResponse)

#: AM-265 d3's "N days after the last edit" — N is not fixed by the record
TTL_DAYS = int(os.environ.get("LEGALMIND_DRAFT_TTL_DAYS", "30"))
#: a variable's role (`model.role`; the importer's client-side keys) ← the Client
#: Profile's legal fields (`AM-286` r1, all ten); only where the template declares it
CLIENT_FIELDS = {"counterparty_name": ("legal_name", "name"),
                 "counterparty_entity_type": ("entity_type",),
                 "counterparty_cin": ("cin_or_llpin",),
                 "counterparty_pan": ("pan",),
                 "counterparty_gstin": ("gstin",),
                 "counterparty_registered_office": ("registered_office",),
                 "counterparty_notice_address": ("notice_address",),
                 "counterparty_notice_email": ("notice_email",),
                 "counterparty_signatory_name": ("signatory_name",),
                 "counterparty_signatory_designation": ("signatory_designation",),
                 "counterparty_authority": ("authority_reference",)}
#: the form's groups by role, so every template asks the client first, ours last
_ROLE_GROUPS = (("counterparty_", "Client"), ("our_", "Our company"))
_QUESTION_KEYS = ("type", "class", "allowed", "range", "when", "locked_value")


_SMALL_WORDS = frozenset({"a", "an", "and", "as", "at", "by", "for", "in", "of", "on",
                          "or", "the", "to", "with"})


def readable_title(title: str) -> str:
    """A template's ALL-CAPITALS title ("MASTER SERVICES AGREEMENT") in title case for the
    contract's generated name; a single word ("NDA") or mixed case stays as written. Only
    the name we make — a name a person typed is stored and shown as typed."""
    if len(title.split()) < 2 or title != title.upper() or not re.search("[A-Z]", title):
        return title
    return re.sub("[a-z][\\w\u2019']*",
                  lambda m: m[0] if m.start() and m[0] in _SMALL_WORDS
                  else m[0][0].upper() + m[0][1:], title.lower())


class TemplateNotPublished(Conflict):
    code = "TEMPLATE_NOT_PUBLISHED"


class DraftInvalid(BusinessRuleRejected):
    code = "DRAFT_INVALID"

    def __init__(self, problems: list[dict[str, str]]) -> None:
        super().__init__(f"The contract cannot be created yet: {len(problems)} "
                         f"field{'s' if len(problems) != 1 else ''} to fix.")
        self.extra = {"problems": problems}


class DraftCreate(Body):
    template_version_id: UUID
    counterparty_id: UUID | None = None
    answers: dict[str, Any] = Field(default_factory=dict, max_length=300)


class DraftUpdate(Body):
    answers: dict[str, Any] = Field(max_length=300)
    expected_version: int = Field(ge=0)


class DraftCreateContract(Body):
    expected_version: int = Field(ge=0)
    name: str | None = Field(default=None, min_length=1, max_length=500)


# ---------------------------------------------------------------- templates
def _question(v: dict[str, Any]) -> dict[str, Any]:
    r = model_.role(v)
    group = next((g for prefix, g in _ROLE_GROUPS if r.startswith(prefix)), None)
    profile = CLIENT_FIELDS.get(r)
    return {"key": v["key"], "label": model_.label(v), "role": r,
            **{k: v[k] for k in _QUESTION_KEYS if k in v},
            **({"group": group or v["group"]} if group or v.get("group") else {}),
            **({"help": h} if (h := model_.help_text(v)) else {}),
            **({"profile_field": profile[0]} if profile else {})}


def questionnaire(db: DBSession, tv: M.TemplateVersion,
                  recommended: set[str]) -> dict[str, Any]:
    """The template's fields as the form asks them; an annexure's condition with it
    (the DPA annexure where a template has one — never added here); its name, purpose,
    known points and Legal's recommendation (`AM-316`)."""
    return {"id": str(tv.id), "template_key": tv.template_key, "version": tv.version,
            "doc_type": tv.doc_type, "brand": tv.brand,
            "title": (tv.layout or {}).get("title"),
            **publish.card(db, tv, recommended),
            "questions": [_question(v) for v in tv.variables],
            "annexures": [{"key": a["key"], "title": a.get("title"),
                           "when": a.get("when")} for a in tv.annexures]}


@router.get("/templates/published")
def published_templates(doc_type: str | None = Query(None, max_length=32),
                        brand: str | None = Query(None, max_length=32),
                        template_key: str | None = Query(None, max_length=64),
                        guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.CONTRACT_CREATE)
    stmt = select(M.TemplateVersion).where(M.TemplateVersion.status == "PUBLISHED")
    if doc_type:
        stmt = stmt.where(M.TemplateVersion.doc_type == doc_type)
    if brand:
        stmt = stmt.where(M.TemplateVersion.brand == brand)
    if template_key:
        stmt = stmt.where(M.TemplateVersion.template_key == template_key)
    rows = guard.db.execute(stmt.order_by(M.TemplateVersion.template_key)).scalars()
    recommended = publish.recommended_keys(guard.db)
    return data([questionnaire(guard.db, tv, recommended) for tv in rows])


def _published(guard: Guard, template_version_id: UUID) -> M.TemplateVersion:
    """A PUBLISHED version, else 409 — a version this caller may not see is a 404."""
    tv = guard.db.get(M.TemplateVersion, template_version_id)
    if tv is None or (tv.status != "PUBLISHED"
                      and P.LEGAL_APPROVE_CUSTOMIZATION not in guard.permissions):
        raise NotVisible("template not found")
    if tv.status != "PUBLISHED":
        raise TemplateNotPublished("only a published template is used for a client "
                                   f"(this version is {tv.status})")
    return tv


# ---------------------------------------------------------------- drafts
def prefill_keys(variables: list[dict[str, Any]]) -> set[str]:
    """The variables a returning client's answers may fill: not locked, not marked
    ``"prefill": false``, and never the deal's own effective date (`AM-326` r3)."""
    return {v["key"] for v in variables
            if "locked_value" not in v and v.get("prefill", True)
            and model_.role(v) != "effective_date"}


def prefill(guard: Guard, tv: M.TemplateVersion,
            counterparty: M.Counterparty) -> dict[str, Any]:
    """A returning client's answers: its latest contract generated from the same
    template key (readable by the caller), then its profile's legal fields — only keys
    this template declares, never a locked one, and never one the template marks
    ``"prefill": false`` (a deal's own figure — the liability months — is answered afresh
    on every deal, `AM-324` r2)."""
    open_keys = prefill_keys(tv.variables)
    roles = {model_.role(v): v["key"] for v in tv.variables if v["key"] in open_keys}
    latest = guard.db.execute(
        select(M.ContractDraft.values)
        .join(M.TemplateVersion,
              M.TemplateVersion.id == M.ContractDraft.template_version_id)
        .join(M.Contract, M.Contract.id == M.ContractDraft.contract_id)
        .where(M.TemplateVersion.template_key == tv.template_key,
               M.Contract.counterparty_id == counterparty.id,
               M.Contract.id.in_(
                   _readable_contracts(guard).with_only_columns(M.Contract.id)))
        .order_by(M.ContractDraft.created_at.desc()).limit(1)
    ).scalar_one_or_none() or {}
    values = {k: v for k, v in latest.items() if k in open_keys}
    for r, fields in CLIENT_FIELDS.items():
        found = next(filter(None, (getattr(counterparty, f) for f in fields)), None)
        if r in roles and found:
            values[roles[r]] = found
    return values


def problems(tv: M.TemplateVersion, answers: dict[str, Any]) -> list[dict[str, str]]:
    try:
        model_.validate(tv.variables, answers)
    except model_.ModelError as exc:
        return exc.problems
    return []


def _serialize(d: M.DraftAnswers, tv: M.TemplateVersion) -> dict[str, Any]:
    return {"id": str(d.id), "version": d.version, "template_version_id": str(tv.id),
            "template_status": tv.status,
            "counterparty_id": str(d.counterparty_id) if d.counterparty_id else None,
            "answers": d.answers, "problems": problems(tv, d.answers),
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            "expires_at": d.expires_at.isoformat()}


def _clauses(guard: Guard, tv: M.TemplateVersion) -> dict[tuple[str, int], dict]:
    return {k: publish.clause_dict(c)
            for k, c in publish.pinned_clauses(guard.db, tv).items()}


def _template(guard: Guard, row: M.DraftAnswers) -> M.TemplateVersion:
    return must_exist(guard.db.get(M.TemplateVersion, row.template_version_id),
                      "template_versions row")


def _own(guard: Guard, draft_id: UUID, *, lock: bool = False) -> M.DraftAnswers:
    guard.permission(P.CONTRACT_CREATE)
    stmt = select(M.DraftAnswers).where(M.DraftAnswers.id == draft_id,
                                        M.DraftAnswers.owner_id == guard.user_id)
    row = guard.db.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
    if row is None:
        raise NotVisible("draft not found")
    return row


@router.post("/drafts", status_code=201)
def create_draft(body: DraftCreate, guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.CONTRACT_CREATE)
    tv = _published(guard, body.template_version_id)
    answers = dict(body.answers)
    if body.counterparty_id is not None:
        client = _readable(guard, body.counterparty_id)
        answers = {**prefill(guard, tv, client), **answers}
    now = datetime.now(UTC)
    row = M.DraftAnswers(template_version_id=tv.id, counterparty_id=body.counterparty_id,
                         answers=answers, owner_id=guard.user_id,
                         created_by=guard.user_id,
                         expires_at=now + timedelta(days=TTL_DAYS))
    guard.db.add(row)
    guard.db.flush()
    return data(_serialize(row, tv)
                | {"prefilled": sorted(set(answers) - set(body.answers))})


@router.get("/drafts")
def list_drafts(guard: Guard = Depends(get_guard)) -> dict:
    guard.permission(P.CONTRACT_CREATE)
    rows = guard.db.execute(
        select(M.DraftAnswers, M.TemplateVersion)
        .join(M.TemplateVersion,
              M.TemplateVersion.id == M.DraftAnswers.template_version_id)
        .where(M.DraftAnswers.owner_id == guard.user_id,
               M.DraftAnswers.expires_at > datetime.now(UTC))
        .order_by(M.DraftAnswers.updated_at.desc())).all()
    return data([_serialize(d, tv) for d, tv in rows])


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    row = _own(guard, draft_id)
    return data(_serialize(row, _template(guard, row)))


@router.patch("/drafts/{draft_id}")
def update_draft(draft_id: UUID, body: DraftUpdate,
                 guard: Guard = Depends(get_guard)) -> dict:
    row = _own(guard, draft_id, lock=True)
    if row.version != body.expected_version:
        raise Conflict("these answers were changed elsewhere; reload them")
    now = datetime.now(UTC)
    row.answers, row.version = body.answers, row.version + 1
    row.updated_at, row.expires_at = now, now + timedelta(days=TTL_DAYS)
    guard.db.flush()
    return data(_serialize(row, _template(guard, row)))


def _stand_in(var: dict[str, Any]) -> Any:
    """A value that passes the field's own checks, shown as missing in the preview."""
    kind = var.get("type", "text")
    if var.get("allowed"):
        return var["allowed"][0]
    # an email stand-in on the reserved .invalid domain (RFC 2606): never deliverable
    return {"bool": False, "int": (var.get("range") or [1])[0] or 1,
            "date": "2000-01-01", "email": "signatory@example.invalid"}.get(
        kind, f"[{model_.label(var)}]")


@router.get("/drafts/{draft_id}/preview")
def preview_draft(draft_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    row = _own(guard, draft_id)
    tv = _template(guard, row)
    clauses = _clauses(guard, tv)
    declared = {v["key"]: v for v in tv.variables}
    answers, missing = dict(row.answers), list[str]()
    found = problems(tv, answers)
    for _ in range(len(declared) + 1):     # a C field appears once its condition holds
        try:
            model = model_.resolve(publish.template_dict(tv), clauses, answers,
                                   mark=True)
            break
        except model_.ModelError as exc:
            fixable = [p["field"] for p in exc.problems if p["field"] in declared
                       and p["field"] not in missing and "locked_value" not in
                       declared[p["field"]]]
            if not fixable:
                return data({"model": None, "missing": missing,
                             "problems": exc.problems})
            for key in fixable:
                answers[key] = _stand_in(declared[key])
                missing.append(key)
    model.pop("values", None)
    return data({"model": model, "missing": missing, "problems": found})


@router.get("/drafts/{draft_id}/check")
def check_draft(draft_id: UUID, guard: Guard = Depends(get_guard)) -> dict:
    """Before Create: the points our review will send to Legal, read by the publish
    gate's own engine check (`publish.engine_findings`: recognition off, no model, a
    savepoint always rolled back) on the draft as rendered now. Nothing is kept and
    nothing is decided; the Review made at Create is the record (rule 13)."""
    row = _own(guard, draft_id)
    tv = _template(guard, row)
    try:
        model = model_.resolve(publish.template_dict(tv), _clauses(guard, tv),
                               row.answers)
    except model_.ModelError:
        return data({"ready": False, "points": []})
    docx = render_contract.render(model, tv.assets, contract_ref="CHECK",
                                  version_number=1, model_hash=model_.model_hash(model))
    found = publish.engine_findings(guard.db, docx, tv, actor_id=guard.user_id,
                                    request_id=guard.request_id)
    return data({"ready": True, "version": row.version, "points": [
        {"code": code, "name": name, "classification": cls}
        # B8: exactly what the Review made at Create sends to Legal — the same analysis's
        # workflow state, never a second rule (a favourable deviation is Acceptable there)
        for code, cls, name, _, to_legal in sorted(found, key=lambda f: f[2])
        if to_legal]})


@router.post("/drafts/{draft_id}/create", status_code=201)
def create_from_draft(draft_id: UUID, body: DraftCreateContract,
                      guard: Guard = Depends(get_guard),
                      storage: StorageBackend = Depends(get_storage)) -> dict:
    row = _own(guard, draft_id, lock=True)
    guard.permission(P.DOCUMENT_UPLOAD)
    if row.version != body.expected_version:
        raise Conflict("these answers were changed elsewhere; reload them")
    tv = _template(guard, row)
    if tv.status != "PUBLISHED":
        raise TemplateNotPublished(f"this template version is {tv.status} now; start "
                                   "again from the published one")
    clauses = _clauses(guard, tv)
    try:
        model = model_.resolve(publish.template_dict(tv), clauses, row.answers)
    except model_.ModelError as exc:
        raise DraftInvalid(exc.problems) from exc
    digest = model_.model_hash(model)
    layout = tv.layout or {}
    title = layout.get("title") or tv.template_key
    # AM-316: two MSAs for one client are told apart by the template's name
    named = readable_title((tv.source or {}).get("catalogue", {}).get("name") or title)
    counterparty = (guard.db.get(M.Counterparty, row.counterparty_id)
                    if row.counterparty_id else None)
    made = create_contract(ContractCreate(
        name=body.name or (f"{named} — {counterparty.name}" if counterparty else named),
        contract_type=tv.doc_type, counterparty_id=row.counterparty_id,
        issuing_entity=publish.issuing_entity(tv.brand)),  # type: ignore[arg-type]
        guard)["data"]
    contract = must_exist(guard.db.get(M.Contract, UUID(made["id"])), "contracts row")
    docx = render_contract.render(model, tv.assets,
                                  contract_ref=str(contract.id)[:8].upper(),
                                  version_number=1, model_hash=digest)
    # AM-293 r2: no LibreOffice in this request — the worker makes the client PDF from
    # the stored DOCX (its page totals filled, the PDF checks run there, fail closed)
    found = preflight.check(docx, model=model)
    if found:                # our own rendering is wrong: nothing is stored (rule 15)
        raise DraftInvalid([{"field": f"preflight {p.code}", "problem": p.detail}
                            for p in found])
    result = ingest_document(guard.db, storage, contract_id=contract.id,
                             uploaded_by=guard.user_id, data=docx,
                             filename=f"{layout.get('short_title') or title}.docx",
                             declared_mime=DOCX_MIME)
    version = result.document_version
    version.doc_metadata = {**(version.doc_metadata or {}), "source": "ORGANIZATION",
                            "version_role": "COMPANY_DRAFT"}
    generated = M.ContractDraft(
        contract_id=contract.id, document_version_id=version.id,
        template_version_id=tv.id,
        values=model["values"], model_hash=digest,
        renderer_version=render_contract.RENDERER_VERSION,
        clean_storage_key=version.storage_key,   # the PDF is recorded on the version
        created_by=guard.user_id)
    guard.db.add(generated)
    guard.db.delete(row)                                       # AM-265 d4
    guard.db.flush()
    audit.record(guard.db, action=audit.CONTRACT_GENERATED, entity_type="contract",
                 entity_id=contract.id, actor_id=guard.user_id,
                 request_id=guard.request_id,
                 after={"document_version_id": str(version.id),
                        "template_version_id": str(tv.id), "model_hash": digest,
                        "renderer_version": render_contract.RENDERER_VERSION})
    dispatch_indexing(guard.db, version.id, request_id=guard.request_id)
    dispatch_pdf(guard.db, version, "contract", request_id=guard.request_id)
    review = _review_reply(guard, version)
    return data({"contract_id": str(contract.id), "document_version_id": str(version.id),
                 "review_id": str(review.id) if review else None, "model_hash": digest,
                 "pdf": f"/document-versions/{version.id}/pdf"})
