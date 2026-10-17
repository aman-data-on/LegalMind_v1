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

import re
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.assist.knowledge import constitution
from legalmind.db import models as M
from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for
from legalmind.extraction import commercial
from legalmind.mapping.service import load_clauses

#: The deviations a reader acts on, worst first in the reader's own words.
_ACTION = ("DEVIATION", "MISSING", "CONFLICT", "UNABLE_TO_EVALUATE")
#: The points a business reader weighs as risks, in the order they weigh them when two
#: carry no figure. A liability cap, the confidentiality term and the payment period are
#: information, never ranked as a ₹ risk: a mutual cap also limits what LeapSwitch can
#: recover, and which way the others cut depends on the deal (AM-156 R7).
_PILLAR_ORDER = ("EARLY-TERM-RESTRICTION", "CONVENIENCE-NOTICE", "CURE-PERIOD",
                 "AUTORENEW", "DISPUTE-VENUE")
#: Whose liability a cap sentence limits, from its own subject (review, 2026-10-17): a
#: "neither party … indirect" sentence or "mutually agreed" elsewhere is not a mutual cap.
#: The words of a cap sentence BEFORE its cap verb — its subject. A carve-out after it
#: ("…, provided that such cap shall not apply to Leapswitch's liability …") is not.
_CAP_SUBJECT = re.compile(
    r"([^.;]*?)\b(?:shall\s+not\s+exceed|(?:is|are|be|shall\s+be)?\s*capped|"
    r"(?:is|are|be|shall\s+be)?\s*limited\s+to)\b", re.I)
_AMOUNT_WORDS = r"(?:(?:total|aggregate|maximum|entire|cumulative|overall)\s+)*liabilit"
_BOTH = re.compile(r"\b(?:each|either)\s+party'?s?\b|\bboth\s+parties\b|"
                   r"\beach\s+of\s+the\s+parties\b|\bthe\s+parties'\s", re.I)
_OURS = re.compile(r"\b(?:leapswitch|cloudpe|(?:service\s+)?provider|supplier)'?s?\s+"
                   + _AMOUNT_WORDS, re.I)
_THEIRS = re.compile(r"\b(?:customer|client|partner)'?s?\s+" + _AMOUNT_WORDS, re.I)


#: The document types where the counterparty is a customer of LeapSwitch's services.
_CUSTOMER_TYPES = frozenset({"MSA", "TOS", "SLA", "ORDER_FORM", "OTHER", "AMENDMENT", ""})


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
    # the document's own number, never an added sign (owner, 2026-09-10)
    parts = [e.section_number or None, e.section_title,
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


def _whose_cap(row) -> str | None:
    """Whose liability the measured cap limits — "both", "ours", "theirs" — from the
    cap sentence's own subject; None when the words do not say."""
    evidence = row["evidence"]
    for subject in _CAP_SUBJECT.findall((evidence.content if evidence else "") or ""):
        if _BOTH.search(subject):
            return "both"
        if _OURS.search(subject):
            return "ours"
        if _THEIRS.search(subject):
            return "theirs"
    return None


def _mutual(row) -> bool:
    """Whether the measured clause binds both parties, by its own subject."""
    evidence = row["evidence"]
    return bool(evidence is not None and _BOTH.search(evidence.content or ""))


def _point(row, facts: commercial.CommercialFacts, notice: tuple[float, str] | None,
           legal_position: bool) -> dict[str, Any] | None:
    """One business point for one actionable Finding, or None when its subject carries
    no business consequence the document's own words can state. Built by code from the
    Finding and the document's own figures; a ₹ figure only under AM-156 R1/R2."""
    stem, cls = _stem(row["code"]), row["classification"]
    actual, expected = row["actual"], row["expected"]
    fee = facts.fee_per_month
    preferred = expected.get("preferred") if legal_position else None
    have = actual.get("cap_value")
    headline = body = money = None
    amount = None
    risk = stem in _PILLAR_ORDER
    if stem == "EARLY-TERM-RESTRICTION" and cls in ("DEVIATION", "MISSING"):
        term = (f"the {facts.term_months}-month term" if facts.term_months
                else "the committed term")
        headline = ("No exit charge on a fixed-term contract" if actual.get("presence")
                    == "WAIVED" else "Early exit is not charged anywhere in the contract")
        on = f" on {notice[0]:g} {notice[1]}' notice" if notice else ""
        body = (f"The customer can leave before {term} ends{on} and owe nothing more "
                "for the rest of the term.")
        calendar = notice[0] if notice and notice[1] == "days" else None
        left = commercial.not_committed(facts, calendar) if (calendar or not notice) \
            else None
        if left is not None and facts.committed_value is not None:
            amount = left
            money = (f"Up to {commercial.rupees(left)} of the "
                     f"{commercial.rupees(facts.committed_value)} contract is not "
                     f"committed ({commercial.rupees(fee or 0)} a month for "
                     f"{facts.term_months} months"
                     f"{', excluding GST' if facts.excludes_gst else ''}"
                     f"{f', less {calendar:g} days of notice' if calendar else ''}).")
        elif facts.missing:
            money = f"No figure is shown: {facts.missing}."
        if facts.refund_text:
            body += f" Prepaid fees: “{facts.refund_text}”"
    elif stem == "CONVENIENCE-NOTICE" and cls == "DEVIATION" and have is not None:
        # notice is planning time, not money: the money is in the early-exit point
        partner = (row["standard"].get("document_type") or "") not in _CUSTOMER_TYPES
        headline = (f"The {'agreement' if partner else 'customer'} can end "
                    f"{'' if partner else 'the contract '}on {have:g} {_days(actual)}' "
                    "notice")
        body = ("That is the time LeapSwitch has to plan for the end of the relationship"
                if partner else
                "That is the time LeapSwitch has to plan for the end — redeploy the "
                "capacity and stop the costs behind it"
                + (f"; our standard is {preferred:g} days." if preferred is not None
                   else "."))
    elif stem == "LIABILITY" and cls == "DEVIATION" and have is not None:
        whose = _whose_cap(row)
        who = {"both": "Each party's liability", "ours": "LeapSwitch's liability",
               "theirs": "The customer's liability"}.get(whose or "", "Liability")
        headline = f"{who} is capped at {have:g} months of fees"
        body = {"both": "It limits what LeapSwitch can owe — and equally what LeapSwitch "
                        "can recover from the customer.",
                "ours": "It limits what LeapSwitch can owe; the clause caps no one else.",
                "theirs": "It limits what LeapSwitch can recover; LeapSwitch's own "
                          "liability is not capped by this sentence."}.get(
            whose or "", "The clause does not say whose liability the cap limits.") + (
            f" Our standard is {preferred:g} months." if preferred is not None else "")
        if fee and facts.missing is None:
            amount_text = commercial.rupees(fee * have)
            money = (f"About {amount_text} either way." if whose == "both"
                     else f"About {amount_text}.")
    elif stem == "CURE-PERIOD" and cls == "DEVIATION" and have is not None:
        headline = f"A breach can be cured within {have:g} {_days(actual)}"
        body = ("The party in breach has that long after notice to fix it before the "
                "other may terminate — for a provider, the time to fix a service "
                "problem" + (f"; our standard is {preferred:g} days." if preferred
                             is not None else "."))
    elif stem == "AUTORENEW" and cls == "MISSING" and facts.term_months:
        headline = "The contract does not say how much notice ends it at term-end"
        body = ("Without it, renewal or exit at the end of the term is unclear"
                + (f"; our standard is {preferred:g} days before the term ends."
                   if preferred is not None else "."))
    elif stem == "DISPUTE-VENUE" and cls == "DEVIATION":
        place = _outside(actual, row["standard"])
        headline = f"Disputes would be heard in {place or 'another city'}"
        body = ("Outside our venue: travel, local counsel and time cost on every dispute."
                if legal_position else None)
    elif stem == "CONF-SURVIVAL" and cls == "DEVIATION" and have is not None:
        headline = f"Confidentiality lasts {have:g} years after the contract"
        body = (("Both parties keep each other's information secret for that long"
                 if _mutual(row) else "The clause does not say it binds both parties")
                + (f"; our standard is {preferred:g} years." if preferred is not None
                   else "."))
    elif stem == "PAYMENT-PERIOD" and cls == "DEVIATION" and have is not None:
        headline = f"Invoices are payable within {have:g} {_days(actual)}"
        body = ("A shorter period means LeapSwitch is paid sooner; a longer one waits "
                "longer for cash" + (f"; our standard is {preferred:g} days."
                                     if preferred is not None else "."))
    else:
        return None
    return {"finding_id": str(row["finding"].id), "requirement_code": row["code"],
            "headline": headline, "body": body, "money": money, "rupees": amount,
            "risk": risk, "where": _where(row), "evidence_ids": row["evidence_ids"]}


#: AM-156 — the action a reader takes on a Finding, in the Constitution's own terms
#: (§24.3, §24.4, §25.1): never "reject", never "approved"; a person always decides.
ACCEPT = "Accept — it matches our position"
SEND_WORDING = "Send our wording; accepting the difference is a Legal decision"
NO_WORDING = "Legal decides — no approved wording exists for this point"
MUST_CHANGE = ("Must change before signing — only an authorised approver may grant an "
               "exception (Constitution §25.1)")
READ_IT = "A person must read this clause before it can be relied on"


def action(row, has_wording: bool) -> str:
    cls = row["classification"]
    if cls == "MATCH":
        return ACCEPT
    if cls in ("DEVIATION", "MISSING"):
        if constitution_prohibition_for(row["code"], row["actual"]):
            return MUST_CHANGE
        return SEND_WORDING if has_wording else NO_WORDING
    return READ_IT


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
    notice = next(((r["actual"]["cap_value"], _days(r["actual"])) for r in rows
                   if _stem(r["code"]) == "CONVENIENCE-NOTICE"
                   and r["actual"].get("cap_value") is not None), None)
    actionable = [r for r in rows if r["classification"] in _ACTION]
    points = [p for r in actionable if (p := _point(r, facts, notice, legal_position))]

    def rank(p):
        stem = _stem(p["requirement_code"])
        order = _PILLAR_ORDER.index(stem) if stem in _PILLAR_ORDER else len(_PILLAR_ORDER)
        return (not p["risk"], -(p["rupees"] or 0), order, p["requirement_code"])

    points.sort(key=rank)
    sections = {str((r["standard"].get("constitution") or {}).get("section"))
                for r in actionable if (r["standard"].get("constitution") or {})
                .get("section")}
    by_section = _proposals(db, sections)
    wording: dict[str, dict[str, str]] = {}
    for r in actionable:
        section = str((r["standard"].get("constitution") or {}).get("section") or "")
        if section in by_section and r["classification"] in ("DEVIATION", "MISSING"):
            wording[str(r["finding"].id)] = by_section[section]
    # the action is the same for every reader; only the wording is position-gated (SEC-07)
    proposals = wording if legal_position else {}
    return {
        "commercial": {
            "fee_per_month": facts.fee_per_month, "fee_text": facts.fee_text,
            "term_months": facts.term_months, "term_text": facts.term_text,
            "committed_value": facts.committed_value,
            "excludes_gst": facts.excludes_gst,
            "committed_value_text": (commercial.rupees(facts.committed_value)
                                     if facts.committed_value else None),
            # why no value is shown, in the reader's words (AM-156 R1)
            "missing": facts.missing},
        "business": points,
        "top_risks": [p for p in points if p["risk"]][:3],
        "legal": {"actionable": len(actionable),
                  "matching": sum(r["classification"] == "MATCH" for r in rows),
                  # each finding a person must act on, with the clauses it read — so an
                  # answer that cites a clause can show that clause's findings (AM-152)
                  "items": [{"finding_id": str(r["finding"].id),
                             "requirement_code": r["code"], "title": r["title"],
                             "classification": r["classification"],
                             "waived": (r["actual"].get("presence") == "WAIVED"),
                             "action": action(r, wording.get(str(r["finding"].id), {})
                                              .get("kind") == "DRAFTING_LANGUAGE"),
                             "where": _where(r), "evidence_ids": r["evidence_ids"]}
                            for r in actionable]},
        "counter_proposals": proposals,
    }
