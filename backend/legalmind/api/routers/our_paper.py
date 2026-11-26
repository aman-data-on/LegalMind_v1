"""Lawyer judgement P1 (`AM-476`): "What it replaces in our paper".

* ``GET /contracts/{id}/our-paper[?version_number=n]`` — every reference the client's
  version makes into our MSA, Terms of Service, SLA or AUP, each with the client's
  sentence and our own words from the pinned version of our document, or the reason it
  could not be looked up (fail closed). Read under the READ traversal (SEC-07: one 404).
* ``POST /contracts/{id}/our-paper/msa`` — Legal's pick of which MSA the paper means,
  only when no signed MSA with this client and no deal template names one (M1). An
  append-only audit event is the record; the latest one is the pick.

Pinning (M1/M2). The MSA: the MSA signed (or final) with this client — the contract this
one is governed by first, else the client's other signed MSA (`prior_paper.papers`, read
rule checked before any text); else the template the deal was drafted from; else Legal's
pick; else WHICH_MSA, with how many of the client's titled references fit each candidate
(a hint, never a pick). A "Version 2" in the client's text is never a key. Each
published policy: the stored `knowledge_sources` row in force on the document's own
date (its opening rows, else its upload date) for the contract's brand — never the live
page, never the other brand's — with BASE_CHANGED_SINCE when the newest stored version
words the clause differently.

Information only (rules 7/10/13): never a Finding, a route, an effect, an answer, the
automatic acceptance, a deal-brief count or a Legal Decision — nothing that makes one
reads this module (the leak tests assert it). No direction or effect words; the one
marker is a phrase quoted from our own text.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text

from legalmind import config
from legalmind.analysis import consistency, our_paper
from legalmind.api import prior_paper
from legalmind.api.deps import CommitBeforeResponse, Guard, get_guard
from legalmind.api.envelope import data
from legalmind.api.errors import BusinessRuleRejected
from legalmind.api.schemas import OurPaperPick
from legalmind.assist.knowledge import published
from legalmind.db import models as M
from legalmind.drafting import blank
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import load_clauses
from legalmind.security import audit
from legalmind.security import permissions as P
from legalmind.security.authorization import can_read_contract
from legalmind.security.errors import Forbidden, NotVisible

router = APIRouter(tags=["negotiation"], route_class=CommitBeforeResponse)

PICKED = "our_paper.msa_picked"
#: S3: a reader without `legal.decision` sees this many rows, then "N more for Legal"
SALES_ROWS = 5
_BRANDS = {"LEAPSWITCH": "Leapswitch", "CLOUDPE": "CloudPe"}


def _template_base(db, tv: M.TemplateVersion) -> dict[str, Any]:
    title = (tv.layout or {}).get("title") or "MSA"
    return {"label": f"{title} — template version {tv.version}", "how": "TEMPLATE",
            "file": f"template {tv.template_key} v{tv.version}",
            "sha256": tv.content_hash,
            "date": (tv.published_at or tv.created_at).date().isoformat(),
            "units": our_paper.msa_units(blank.our_side(db, tv)[0]), "paragraphs": [],
            "ref": {"template_version_id": str(tv.id)}}


def _paper_base(db, paper: dict) -> dict[str, Any]:
    v, c = paper["version"], paper["contract"]
    return {"label": f"{c.name} — {paper['kind'].lower()} copy", "how": "PRIOR_PAPER",
            "file": v.original_filename, "sha256": v.file_hash,
            "date": paper["at"].isoformat(),
            "units": our_paper.msa_units(load_clauses(db, v.id)), "paragraphs": [],
            "ref": {"contract_id": str(c.id)}}


def _signed_msas(guard: Guard, contract: M.Contract) -> list[dict]:
    """The client's signed or final MSAs this reader may read: the one this contract is
    governed by first."""
    papers = [p for p in prior_paper.papers(guard, contract)
              if p["contract"].contract_type == "MSA"]
    parent = contract.governed_by_contract_id
    return sorted(papers, key=lambda p: p["contract"].id != parent)


def _templates(db, contract: M.Contract) -> list[M.TemplateVersion]:
    """The MSA template(s) the deal was drafted from — this contract's or its parent's."""
    ids = [i for i in (contract.id, contract.governed_by_contract_id) if i]
    return list(db.execute(select(M.TemplateVersion).join(
        M.ContractDraft, M.ContractDraft.template_version_id == M.TemplateVersion.id)
        .where(M.ContractDraft.contract_id.in_(ids), M.TemplateVersion.doc_type == "MSA")
        .distinct()).scalars())


def _event(db, contract_id: UUID) -> M.AuditEvent | None:
    return db.execute(select(M.AuditEvent).where(
        M.AuditEvent.action == PICKED, M.AuditEvent.entity_id == contract_id)
        .order_by(M.AuditEvent.timestamp.desc()).limit(1)).scalar_one_or_none()


def _pick(db, contract_id: UUID) -> dict | None:
    event = _event(db, contract_id)
    return None if event is None else event.after_state


def _choices(guard: Guard, contract: M.Contract, refs: list[dict]) -> dict[str, Any]:
    candidates = _candidates(guard, contract)
    return {"choices": [{"label": c["label"], **c["ref"],
                         **{k: c[k] for k in ("file", "sha256", "date")}}
                        for c in candidates],
            "fingerprint": our_paper.fingerprint(refs, candidates)}


def _picked(guard: Guard, contract: M.Contract, base: dict, refs: list[dict]) -> dict:
    """Legal's pick, with who made it and when (round 2: shown, and changeable)."""
    event = _event(guard.db, contract.id)
    assert event is not None
    who = guard.db.get(M.User, event.actor_id) if event.actor_id else None
    return {**base, "how": "LEGAL_PICK", "hint": _choices(guard, contract, refs),
            "picked": {"by": who.name if who else None,
                       "by_you": event.actor_id == guard.user_id,
                       "on": event.timestamp.date().isoformat()}}


def _candidates(guard: Guard, contract: M.Contract) -> list[dict]:
    """Every MSA Legal may pick: our MSA templates (published or retired) and the client's
    signed or final MSAs."""
    db = guard.db
    tvs = db.execute(select(M.TemplateVersion).where(
        M.TemplateVersion.doc_type == "MSA",
        M.TemplateVersion.status.in_(("PUBLISHED", "RETIRED")))
        .order_by(M.TemplateVersion.template_key, M.TemplateVersion.version)).scalars()
    return [*(_template_base(db, tv) for tv in tvs),
            *(_paper_base(db, p) for p in _signed_msas(guard, contract))]


def msa(guard: Guard, contract: M.Contract, refs: list[dict]) -> dict[str, Any]:
    db = guard.db
    signed = _signed_msas(guard, contract)
    parent = [p for p in signed if p["contract"].id == contract.governed_by_contract_id]
    if parent or len(signed) == 1:
        return _paper_base(db, (parent or signed)[0])
    templates = _templates(db, contract) if not signed else []
    if len(templates) == 1:
        return _template_base(db, templates[0])
    picked = _pick(db, contract.id)
    if picked:
        if tv_id := picked.get("template_version_id"):
            tv = db.get(M.TemplateVersion, UUID(tv_id))
            if tv is not None:
                return _picked(guard, contract, _template_base(db, tv), refs)
        other = db.get(M.Contract, UUID(picked.get("contract_id") or str(contract.id)))
        paper = next((p for p in signed if other is not None
                      and p["contract"].id == other.id), None)
        if paper is not None:
            return _picked(guard, contract, _paper_base(db, paper), refs)
    return {"unresolved": our_paper.WHICH_MSA, "hint": _choices(guard, contract, refs)}


def _read(db, period: dict) -> dict:
    items = db.execute(text(
        f'SELECT kind, clause, content FROM "{config.assist_schema()}".knowledge_items '
        "WHERE source_id = :s ORDER BY ordinal"),
        {"s": period["source_id"]}).tuples().all()
    units, paragraphs = our_paper.policy_units(list(items))
    return {"label": f"{period['title']} as published on {period['started_on']}",
            "file": period["source_file"], "sha256": period["file_sha256"],
            "date": period["started_on"].isoformat(), "units": units,
            "paragraphs": paragraphs}


def policy(db, doc: str, brand: str | None, on) -> dict[str, Any]:
    """M2 / `AM-477`: the stored version in force on the document's date, for this brand
    only (`published.version_on`)."""
    if brand is None:
        return {"unresolved": our_paper.NO_BRAND}
    found = next((p for p in published.POLICIES if p.key == f"{doc}-{brand.lower()}"),
                 None)
    got = published.version_on(db, found.source_type, on) if found else {}
    if not got.get("pinned"):
        earliest = got.get("earliest")
        return {"unresolved": our_paper.NO_STORED_COPY, "hint": {
            "on": on.isoformat(), "earliest": earliest.isoformat() if earliest else None}}
    out = _read(db, got["pinned"])
    if got["newer"]:
        out["newer"] = _read(db, got["newer"])
    return out


def _brand(db, contract: M.Contract, version: M.DocumentVersion) -> str | None:
    return _BRANDS.get(contract.issuing_entity or "") or \
        published.document_brand(db, version.id)


def view(guard: Guard, contract: M.Contract, version: M.DocumentVersion) -> dict:
    db = guard.db
    clauses: list[Clause] = load_clauses(db, version.id)
    refs = consistency.paper_references(clauses)
    said = our_paper.document_date(clauses)
    on = said or version.created_at.date()
    out: dict[str, Any] = {"version_number": version.version_number,
                           "on": on.isoformat(),
                           "on_from": "DOCUMENT" if said else "UPLOAD", "rows": []}
    if not refs:
        return out
    docs = {r["doc"] for r in refs}
    brand = _brand(db, contract, version) if docs - {"MSA"} else None
    bases = {d: msa(guard, contract, refs) if d == "MSA" else policy(db, d, brand, on)
             for d in docs}
    rows = our_paper.resolve(refs, bases)
    legal = P.LEGAL_DECISION in guard.permissions
    for row in rows:
        row.pop("pin", None)                # said once per document, in `pins`
        if row["doc"] == "MSA" and not legal:
            row.pop("hint", None)           # the MSA choices are Legal's pick only
    # file and SHA-256 are Legal's detail; the label and date are everyone's
    shown = ("label", "date", "how", "unresolved", "picked") + (
        ("file", "sha256") if legal else ())
    out["pins"] = {d: {k: v for k, v in b.items()
                       if k in shown or (k == "hint" and (legal or d != "MSA"))}
                   for d, b in bases.items()}
    overrides = our_paper.overridden(rows)
    out["overrides_count"] = len(overrides)
    out["overrides_by_doc"] = {d: n for d in consistency.PAPER_DOCS
                               if (n := sum(o.split(" ")[0] == d for o in overrides))}
    if legal:
        out["overrides"] = overrides        # round 2: sales receives the count only
    msa_pin = bases.get("MSA", {})
    out["can_pick"] = legal and (msa_pin.get("unresolved") == our_paper.WHICH_MSA
                                 or msa_pin.get("how") == "LEGAL_PICK")
    if not legal and len(rows) > SALES_ROWS:
        # S3: the replaced clauses first, then the rest, in the document's order
        order = sorted(range(len(rows)), key=lambda i: (
            rows[i]["status"] != our_paper.RESOLVED
            or rows[i]["verb"] not in our_paper.OVERRIDES, i))
        keep = sorted(order[:SALES_ROWS])
        out["more_for_legal"] = len(rows) - SALES_ROWS
        rows = [rows[i] for i in keep]
    out["rows"] = rows
    return out


def _version(guard: Guard, contract: M.Contract, number: int | None) -> M.DocumentVersion:
    versions = list(guard.db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract.id)).scalars())
    found = next((v for v in versions if v.version_number == number), None) \
        if number is not None else max(versions, key=lambda v: v.version_number,
                                       default=None)
    if found is None:
        raise NotVisible("document version not found")
    return found


@router.get("/contracts/{contract_id}/our-paper")
def our_paper_view(contract_id: UUID, version_number: int | None = Query(None, ge=1),
                   guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    if not config.our_paper_enabled():
        raise NotVisible("not found")
    return data(view(guard, contract, _version(guard, contract, version_number)))


@router.post("/contracts/{contract_id}/our-paper/msa", status_code=201)
def pick_msa(contract_id: UUID, body: OurPaperPick,
             guard: Guard = Depends(get_guard)) -> dict:
    contract = guard.contract_readable(contract_id, P.DOCUMENT_VIEW)
    if not config.our_paper_enabled():
        raise NotVisible("not found")
    if P.LEGAL_DECISION not in guard.permissions:
        raise Forbidden("Legal picks which MSA the client's paper refers to.")
    db = guard.db
    if body.template_version_id is not None:
        tv = db.get(M.TemplateVersion, body.template_version_id)
        if tv is None or tv.doc_type != "MSA" \
                or tv.status not in ("PUBLISHED", "RETIRED"):
            raise BusinessRuleRejected("not a published or retired MSA template")
    else:
        other = db.get(M.Contract, body.contract_id)
        if other is None or not can_read_contract(db, guard.user_id, other) or not any(
                p["contract"].id == other.id for p in _signed_msas(guard, contract)):
            raise BusinessRuleRejected("not a signed or final MSA with this client")
    after = {k: str(v) for k, v in body.model_dump().items() if v is not None}
    audit.record(db, action=PICKED, entity_type="contract", entity_id=contract.id,
                 actor_id=guard.user_id, request_id=guard.request_id,
                 before=_pick(db, contract.id), after=after)
    return data(after)
