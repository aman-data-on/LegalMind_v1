"""The ⚖️ Legal and 💼 Business angles on a Review, and its counter-proposals (AM-152).

Owner, 2026-10-16: a customer's MOU waived the lock-in on a ₹90,84,000 one-year contract,
and the review said nothing about the money. A reader needs three things before a lawyer
does: the risks that cost the most, what the contract commits in rupees, and what to send
back. Everything here is BUILT BY CODE from what the engine already decided:

* the Legal angle is the Findings themselves (the evaluator's classifications, untouched);
* the Business angle restates each deviation of a commercial pillar in money, from the
  document's own stated fee and term (`extraction.commercial`, cited) — arithmetic on two
  figures, in fixed words, never a classification and never generated;
* a counter-proposal is the Constitution's own drafting language for the finding's
  section, quoted verbatim from the ingested Constitution (`knowledge_items`) and labelled
  as the Constitution labels it — never drafted here (rules 7 and 21).

A standard's own value (a legal position) is said only to a reader holding
`legal_position.view`; otherwise it is omitted, never blanked (LEGAL-02, SEC-07).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.knowledge import constitution
from legalmind.db import models as M
from legalmind.extraction import commercial
from legalmind.mapping.service import load_clauses

#: The deviations a reader acts on, worst first in the reader's own words.
_ACTION = ("DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE")
#: The five commercial pillars (`commercial_pillar`), in the order a business reader
#: weighs them when two carry no figure.
_PILLAR_ORDER = ("EARLY-TERM-RESTRICTION", "CONVENIENCE-NOTICE", "LIABILITY",
                 "PAYMENT-PERIOD", "CURE-PERIOD")


def _stem(code: str) -> str:
    return code.rsplit("-", 2)[0] if code.count("-") >= 2 else code


def _rows(db: DBSession, review: M.Review) -> list[dict[str, Any]]:
    """Each Finding with its requirement code, pinned standard, first Evaluation and
    first evidence row — read once."""
    out = []
    for f in db.execute(select(M.Finding).where(M.Finding.review_id == review.id)
                        ).scalars().all():
        rv = db.get(M.RequirementVersion, f.requirement_version_id)
        req = db.get(M.Requirement, rv.requirement_id) if rv else None
        pinned = M.ConfigurationSnapshotItem
        item = db.execute(select(pinned).where(
            pinned.snapshot_id == review.configuration_snapshot_id,
            pinned.requirement_version_id == f.requirement_version_id)).scalars().first()
        cs = db.get(M.CompanyStandardVersion, item.company_standard_version_id) if item \
            else None
        ev = db.execute(select(M.Evaluation).where(M.Evaluation.finding_id == f.id)
                        .order_by(M.Evaluation.created_at, M.Evaluation.id)
                        ).scalars().first()
        evidence = db.execute(
            select(M.DocumentEvidence).join(
                M.FindingEvidence, M.FindingEvidence.evidence_id == M.DocumentEvidence.id)
            .where(M.FindingEvidence.finding_id == f.id)
            .order_by(M.DocumentEvidence.page_number, M.DocumentEvidence.start_offset)
        ).scalars().first()
        linked = M.FindingEvidence
        evidence_ids = [str(e) for e in db.execute(
            select(linked.evidence_id).where(linked.finding_id == f.id)).scalars().all()]
        out.append({"finding": f, "code": req.code if req else "",
                    "evidence_ids": evidence_ids,
                    "title": ((rv.description if rv else None)
                              or (req.code if req else "")),
                    "standard": (cs.configuration if cs else None) or {},
                    "classification": f.classification.value,
                    "actual": (ev.actual_value if ev else None) or {},
                    "expected": (ev.expected_value if ev else None) or {},
                    "evidence": evidence})
    return out


def _where(row) -> str | None:
    e = row["evidence"]
    if e is None:
        return None
    parts = [f"§{e.section_number}" if e.section_number else None, e.section_title,
             f"page {e.page_number}" if e.page_number is not None else None]
    return " · ".join(p for p in parts if p) or None


def _days_money(fee: float | None, days: float) -> str | None:
    return commercial.rupees(fee * days / 30) if fee else None


def _days(actual: dict) -> str:
    """The unit a period finding states — working days are never calendar days
    (AM-154), so a working-day figure is said as one and never costed as days."""
    return "working days" if actual.get("cap_unit") == "WORKING_DAYS" else "days"


def _outside(actual: dict, standard: dict) -> str | None:
    """The first stated place the standard does not allow, in the document's words."""
    allowed = set(standard.get("allowed_values") or ())
    known = {w: k for k, ws in (standard.get("recognised_values") or {}).items()
             for w in ws}
    return next((v for v in actual.get("values") or ()
                 if known.get(v.lower()) not in allowed), None)


def _point(row, facts: commercial.CommercialFacts, notice_days: str | None,
           legal_position: bool) -> dict[str, Any] | None:
    """One business point for one actionable Finding, or None when its subject carries
    no business consequence the document's own figures can state."""
    stem, cls = _stem(row["code"]), row["classification"]
    actual, expected = row["actual"], row["expected"]
    fee, value = facts.fee_per_month, facts.committed_value
    preferred = expected.get("preferred") if legal_position else None
    have = actual.get("cap_value")
    headline = body = money = None
    amount = None
    if stem == "EARLY-TERM-RESTRICTION" and cls in ("DEVIATION", "MISSING"):
        term = (f"the {facts.term_months}-month term" if facts.term_months
                else "the committed term")
        headline = ("No exit charge on a fixed-term contract" if actual.get("presence")
                    == "WAIVED" else "Early exit is not charged anywhere in the contract")
        notice = f", on {notice_days}' notice" if notice_days else ""
        body = (f"The customer can leave before {term} ends without paying for the "
                f"rest of the term{notice}.")
        if value:
            amount = value
            money = (f"Up to {commercial.rupees(value)} of committed fees is not secured "
                     f"({commercial.rupees(fee or 0)} a month for {facts.term_months} "
                     f"months{', excluding GST' if facts.excludes_gst else ''}).")
    elif stem == "CONVENIENCE-NOTICE" and cls == "DEVIATION" and have is not None:
        headline = (f"The customer can end the contract on {have:g} {_days(actual)}' "
                    "notice")
        body = (f"Our standard is {preferred:g} days." if preferred is not None else None)
        if fee and _days(actual) == "days":
            # ranked by the shortfall only for a reader who may see the standard: the
            # figure would otherwise disclose it (SEC-07); never a default in its place
            amount = (fee * max(preferred - have, 0) / 30 if preferred is not None
                      else None)
            money = (f"Notice now protects about {_days_money(fee, have)} of fees"
                     + (f", against {_days_money(fee, preferred)} at {preferred:g} days."
                        if preferred is not None else "."))
    elif stem == "LIABILITY" and cls == "DEVIATION" and have is not None:
        headline = f"Liability is capped at {have:g} months of fees"
        body = (f"Our standard is {preferred:g} months." if preferred is not None
                else None)
        if fee:
            amount = fee * have
            money = (f"Cap is about {commercial.rupees(fee * have)}"
                     + (f", against {commercial.rupees(fee * preferred)} at our "
                        f"{preferred:g} months." if preferred is not None else "."))
    elif stem == "CURE-PERIOD" and cls == "DEVIATION" and have is not None:
        headline = f"A breach can be cured within {have:g} {_days(actual)}"
        body = (f"Our standard is {preferred:g} days." if preferred is not None else None)
    elif stem == "DISPUTE-VENUE" and cls == "DEVIATION":
        place = _outside(actual, row["standard"])
        headline = f"Disputes would be heard in {place or 'another city'}"
        body = ("Outside our venue: travel, local counsel and time cost on every dispute."
                if legal_position else None)
    elif stem == "CONF-SURVIVAL" and cls == "DEVIATION" and have is not None:
        headline = f"Confidentiality lasts {have:g} years after the contract"
        body = None
        if preferred is not None:
            body = (f"Our standard is {preferred:g} years: "
                    + ("a longer duty on our people and systems." if have > preferred
                       else "our information is protected for less time."))
    else:
        return None
    return {"finding_id": str(row["finding"].id), "requirement_code": row["code"],
            "headline": headline, "body": body, "money": money, "rupees": amount,
            "where": _where(row), "evidence_ids": row["evidence_ids"]}


def _proposals(db: DBSession, sections: set[str]) -> dict[str, dict[str, str]]:
    """The current Constitution's drafting language per section, verbatim; where the
    section has none, its Company Position — said to be so (never drafted here)."""
    if not sections:
        return {}
    version = constitution.CURRENT_VERSION
    prefix = f"Legal Constitution {version} · "
    rows = db.execute(text(f"""
        SELECT ki.section_path, ki.breadcrumb, ki.content
          FROM "{config.assist_schema()}".knowledge_items ki
         WHERE ki.kind = 'PARAGRAPH' AND ki.status = 'CURRENT'
           AND ki.breadcrumb LIKE :p AND ki.section_path = ANY(:s)
         ORDER BY ki.section_path, ki.ordinal"""),
        {"p": prefix + "%", "s": sorted(sections)}).all()
    out: dict[str, dict[str, str]] = {}
    def heading(crumb: str, name: str) -> str | None:
        # the Constitution's own heading, word for word (AM-152 r7)
        return next((" ".join(h.replace("*", "").split()) for h in crumb.split(" · ")
                     if name in h), None)

    for kind, name, note in (("DRAFTING_LANGUAGE", "Drafting Notes", ""),
                             ("COMPANY_POSITION", "Company Position",
                              " (no approved clause wording exists for it)")):
        for section, crumb, content in rows:
            words = " ".join((content or "").replace("*", "").split())
            if section not in out and words and (head := heading(crumb, name)):
                out[section] = {"section": section, "kind": kind,
                                "label": f"Constitution §{section} — {head}{note}",
                                "text": words}
    return out


def review_angles(db: DBSession, review: M.Review, *, legal_position: bool) -> dict:
    rows = _rows(db, review)
    facts = commercial.read(load_clauses(db, review.document_version_id))
    notice = next((f'{r["actual"]["cap_value"]:g} {_days(r["actual"])}' for r in rows
                   if _stem(r["code"]) == "CONVENIENCE-NOTICE"
                   and r["actual"].get("cap_value") is not None), None)
    actionable = [r for r in rows if r["classification"] in _ACTION]
    points = [p for r in actionable if (p := _point(r, facts, notice, legal_position))]

    def rank(p):
        stem = _stem(p["requirement_code"])
        order = _PILLAR_ORDER.index(stem) if stem in _PILLAR_ORDER else len(_PILLAR_ORDER)
        return (-(p["rupees"] or 0), order, p["requirement_code"])

    points.sort(key=rank)
    sections = {str((r["standard"].get("constitution") or {}).get("section"))
                for r in actionable if (r["standard"].get("constitution") or {})
                .get("section")} if legal_position else set()
    by_section = _proposals(db, sections)
    proposals = {}
    for r in actionable:
        section = str((r["standard"].get("constitution") or {}).get("section") or "")
        if section in by_section and r["classification"] in ("DEVIATION", "MISSING"):
            proposals[str(r["finding"].id)] = by_section[section]
    return {
        "commercial": {
            "fee_per_month": facts.fee_per_month, "fee_text": facts.fee_text,
            "term_months": facts.term_months, "term_text": facts.term_text,
            "committed_value": facts.committed_value,
            "excludes_gst": facts.excludes_gst,
            "committed_value_text": (commercial.rupees(facts.committed_value)
                                     if facts.committed_value else None)},
        "business": points,
        "top_risks": points[:3],
        "legal": {"actionable": len(actionable),
                  "matching": sum(r["classification"] == "MATCH" for r in rows),
                  # each finding a person must act on, with the clauses it read — so an
                  # answer that cites a clause can show that clause's findings (AM-152)
                  "items": [{"finding_id": str(r["finding"].id),
                             "requirement_code": r["code"], "title": r["title"],
                             "classification": r["classification"],
                             "waived": (r["actual"].get("presence") == "WAIVED"),
                             "where": _where(r), "evidence_ids": r["evidence_ids"]}
                            for r in actionable]},
        "counter_proposals": proposals,
    }
