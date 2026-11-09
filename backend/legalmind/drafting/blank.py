"""The blank template — a PUBLISHED template's approved text with every field left as a
visible placeholder, to be filled outside LegalMind (owner, 2026-11-04: a salesperson
opens it in Google Docs, fills the client's details and sends it).

Rendered by `render_contract` from `model.resolve(blank=True)`: the same house style,
every field a highlighted "[Client's legal name]", each conditional part kept with a
bracketed note, no content controls. The footer carries the template ID
``LM-TPL-<key>-v<version>-<model hash[:8]>`` — `ID` finds it again when the paper
comes back (`link`). Nothing is composed here (rule 21).
"""

from __future__ import annotations

import io
import re
import uuid
from typing import Any
from uuid import UUID

import docx
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from legalmind.analysis import document_comparison as dc
from legalmind.analysis import negotiation
from legalmind.db import models as M
from legalmind.db.lookup import latest_completed_run_id
from legalmind.drafting import model as model_
from legalmind.drafting import publish, render_contract
from legalmind.ingestion import parsing
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import PAGE_FURNITURE, load_clauses

#: the template ID in a returned copy's text (footer, or anywhere a PDF put it)
ID = re.compile(r"LM-TPL-(?P<key>[A-Z0-9][A-Z0-9._-]*?)-v(?P<version>\d+)-"
                r"(?P<hash>[0-9a-f]{6,8})\b")


def blank_model(db: DBSession, tv: M.TemplateVersion) -> dict[str, Any]:
    rows = publish.pinned_clauses(db, tv)
    return model_.resolve(publish.template_dict(tv),
                          {k: publish.clause_dict(c) for k, c in rows.items()}, {},
                          blank=True)


#: the review copy's header — a DRAFT's full text, on every page of the download only
#: (owner, 2026-11-04; worded by the owner 2026-11-09, `AM-316` r6)
REVIEW_HEADER = "DRAFT — NOT FOR USE WITH A CLIENT. For management approval."
BLANK, REVIEW = "blank", "review"


def _ref(tv: M.TemplateVersion, kind: str) -> str:
    """The footer ID's reference: ``TPL-<key>`` on the blank (what `ID` links back),
    ``REVIEW-<key>`` on a review copy (never linked: it is not for a client)."""
    return f"{'TPL' if kind == BLANK else 'REVIEW'}-{tv.template_key}"


def identifier(tv: M.TemplateVersion, model: dict[str, Any], kind: str = BLANK) -> str:
    return render_contract.doc_id(_ref(tv, kind), tv.version, model_.model_hash(model))


def demo_label(tv: M.TemplateVersion) -> str | None:
    """A hand-published local demo copy's label ("DEMO — not approved by Legal"), which
    the hand-publish script keeps in ``source.label``; any other label is not a demo's."""
    label = (tv.source or {}).get("label")
    return label if isinstance(label, str) and label.startswith("DEMO") else None


def render(db: DBSession, tv: M.TemplateVersion,
           kind: str = BLANK) -> tuple[bytes, dict[str, Any]]:
    """The blank (or review copy's) DOCX and its model."""
    model = blank_model(db, tv)
    docx = render_contract.render(model, tv.assets, contract_ref=_ref(tv, kind),
                                  version_number=tv.version,
                                  model_hash=model_.model_hash(model), blank=True,
                                  header_note=REVIEW_HEADER if kind == REVIEW
                                  else demo_label(tv))
    return docx, model


def placeholders(model: Any) -> set[str]:
    """Every placeholder text the blank model shows."""
    return {n["t"] for n in model_._walk(model) if n.get("ph")
            and not n["t"].startswith(model_.NOTE_OPEN)}


# ------------------------------------------- when the paper comes back (`AM-302`)
#: ponytail: (template version id, content hash) -> our side. A linked version is
#: PUBLISHED or RETIRED, frozen by its trigger, so an entry never goes stale; bounded by
#: the number of template versions.
_SIDE: dict[tuple[UUID, str], tuple[list[Clause], set[str], set[str]]] = {}


def our_side(db: DBSession, tv: M.TemplateVersion
             ) -> tuple[list[Clause], set[str], set[str]]:
    """Our side of a returned blank: its rows as the parser reads the blank file (each
    note dropped, page furniture out), the placeholder texts it shows, and the
    comparison text of every row of an optional part (deleting one is what its note
    asks for, so it is not a change)."""
    key = (tv.id, tv.content_hash)
    if key not in _SIDE:
        data, model = render(db, tv)
        # parsed as a filled copy is, its notes deleted: the parser reads a row by its
        # neighbours, so dropping the note rows after parsing would read differently
        document = docx.Document(io.BytesIO(data))
        for p in list(document.paragraphs):
            if p.text.startswith(model_.NOTE_OPEN):
                p._p.getparent().remove(p._p)
        out = io.BytesIO()
        document.save(out)
        rows = [Clause(evidence_id=uuid.uuid5(tv.id, f"blank-{i}"), content=s.content,
                       section_number=s.section_number, section_title=s.section_title,
                       page_number=s.page_number,
                       is_heading=bool(s.metadata.get("heading")))
                for i, s in enumerate(parsing.parse_docx(out.getvalue()).segments)
                if s.metadata.get("part") not in PAGE_FURNITURE]
        optional = {dc._norm(_said(n)) for part in [*model["body"], *model["schedules"]]
                    if part.get("note") for n in model_._walk(part)}
        _SIDE[key] = (rows, placeholders(model), optional - {""})
    return _SIDE[key]


def _said(node: dict) -> str:
    """A model node's words as its row reads them (title, defined term, text)."""
    runs = node.get("runs")
    term = node.get("term")
    return "".join([node["title"] if isinstance(node.get("title"), str) else "",
                    f"“{term}” " if isinstance(term, str) else "",
                    model_.text_of(runs) if isinstance(runs, list) else ""])


def link(db: DBSession, contract: M.Contract,
         version: M.DocumentVersion) -> dict[str, Any] | None:
    """The published (or since retired) template a version was made from, as
    `negotiation.changes` takes it: by the template ID its text carries, else by
    structure — a template of the contract's type whose top-level clause headings it
    carries (four in five, at least five), the most identical clauses breaking a tie.
    None: neither."""
    run_id = latest_completed_run_id(db, version.id)
    if run_id is None:
        return None
    linked = select(M.TemplateVersion).where(
        M.TemplateVersion.status.in_(("PUBLISHED", "RETIRED")))
    found = next((m for c in db.execute(select(M.DocumentEvidence.content).where(
        M.DocumentEvidence.processing_run_id == run_id)).scalars()
        if (m := ID.search(c or ""))), None)
    tv: M.TemplateVersion | None = None
    how = "id"
    if found:
        tv = db.execute(linked.where(
            M.TemplateVersion.template_key == found["key"],
            M.TemplateVersion.version == int(found["version"]))).scalar_one_or_none()
    elif contract.contract_type:
        how = "structure"
        theirs = negotiation._units(load_clauses(db, version.id))
        heads = {dc._norm(u["heading"] or "") for u in theirs} - {""}
        texts = {dc._norm(u["text"]) for u in theirs}
        best: tuple[float, int] | None = None
        for candidate in db.execute(linked.where(
                M.TemplateVersion.doc_type == contract.contract_type)).scalars():
            ours = negotiation._units(our_side(db, candidate)[0])
            titles = {dc._norm(u["heading"] or "") for u in ours
                      if u["number"] and "." not in u["number"]} - {""}
            if len(titles) < 5:
                continue
            score = (len(titles & heads) / len(titles),
                     sum(dc._norm(u["text"]) in texts for u in ours))
            if score[0] >= 0.8 and (best is None or score > best):
                best, tv = score, candidate
    if tv is None:
        return None
    rows, fields, optional = our_side(db, tv)
    return {"template_version": tv, "clauses": rows, "fields": fields,
            "optional": optional, "note_open": model_.NOTE_OPEN,
            "said": said(db, tv, how)}


def said(db: DBSession, tv: M.TemplateVersion, how: str) -> dict[str, Any]:
    """What the Changes page says of the template a returned copy was made from."""
    current = db.execute(select(M.TemplateVersion.version).where(
        M.TemplateVersion.template_key == tv.template_key,
        M.TemplateVersion.status == "PUBLISHED")).scalar_one_or_none()
    older = current is not None and current > tv.version
    return {"template_key": tv.template_key, "version": tv.version,
            "title": (tv.layout or {}).get("title"), "how": how,
            "current_version": current, "older": older,
            "message": (f"Made from an older template (v{tv.version}); the current one "
                        f"is v{current}.") if older else None}
