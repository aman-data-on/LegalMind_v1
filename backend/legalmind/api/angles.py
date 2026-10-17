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
from collections import defaultdict
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.analysis.service import _review_document_type
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
#: A cap verb — the words before it are the sentence's subject. A carve-out after it
#: ("…, provided that such cap shall not apply to Leapswitch's liability …") is not, and
#: a negated one ("is not capped", "including but not limited to") states no cap (r29).
_CAP_VERB = re.compile(r"\b(?:exceed|capped|limited\s+to|restricted\s+to)\b|\bmaximum\s+"
                       r"(?:aggregate\s+)?liabilit\w*[^.;]{0,40}?\bshall\s+be\b", re.I)
#: An obligation verb — the words before it say who is bound.
_OBLIGATION = re.compile(r"\b(?:shall|must|will|agrees?\s+to|undertakes?\s+to)\b", re.I)
_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
                 15: "fifteen", 18: "eighteen", 24: "twenty-four", 30: "thirty",
                 36: "thirty-six", 45: "forty-five", 60: "sixty", 90: "ninety"}
_UNIT_WORD = {"MONTHS": "month", "YEARS": "year", "DAYS": "day", "WORKING_DAYS": "day",
              "WEEKS": "week"}
_AMOUNT_WORDS = r"(?:(?:total|aggregate|maximum|entire|cumulative|overall)\s+)*liabilit"
_BOTH = re.compile(r"\b(?:each|either)\s+party'?s?\b|\bboth\s+parties\b|"
                   r"\beach\s+of\s+the\s+parties\b|\bthe\s+parties'\s", re.I)
#: The party a liability noun names — "Leapswitch's total liability", "the liability of
#: either Party". The LAST one before the cap verb is the cap's; a carve-out naming
#: "either party's obligations" earlier names no liability (r30).
_LIABLE = re.compile(
    r"\b(?:(?P<both>(?:each|either|neither)\s+party'?s?|both\s+parties'?|the\s+parties'|"
    r"each\s+of\s+the\s+parties'?)|(?P<ours>leapswitch|cloudpe|(?:service\s+)?provider|"
    r"supplier)'?s?|(?P<theirs>customer|client|partner)'?s?)\s+" + _AMOUNT_WORDS +
    r"|\bliabilit\w*\s+of\s+(?:the\s+)?(?:(?P<both2>each|either|both|neither)\s+part(?:y|ies)|"
    r"(?P<ours2>leapswitch|cloudpe|(?:service\s+)?provider|supplier)|"
    r"(?P<theirs2>customer|client|partner))\b", re.I)


#: The document types where the counterparty is a customer of LeapSwitch's services.
_CUSTOMER_TYPES = frozenset({"MSA", "TOS", "SLA", "ORDER_FORM", "OTHER", "AMENDMENT", ""})


def _stem(code: str) -> str:
    return code.rsplit("-", 2)[0] if code.count("-") >= 2 else code


def _governing(evaluations: list, classification) -> Any:
    """The scope that gave the Finding its classification (the roll-up's winner), so a
    business point never states a MATCH scope's figure for a DEVIATION Finding."""
    return next((e for e in evaluations if e.classification == classification),
                evaluations[0] if evaluations else None)


def _rows(db: DBSession, review: M.Review) -> list[dict[str, Any]]:
    """Each Finding with its requirement code, pinned standard, governing Evaluation and
    first evidence row — five queries for the whole Review, never one per Finding."""
    findings = db.execute(select(M.Finding).where(M.Finding.review_id == review.id)
                          ).scalars().all()
    ids = [f.id for f in findings]
    rv_ids = {f.requirement_version_id for f in findings}
    versions = {rv.id: (rv, req) for rv, req in db.execute(
        select(M.RequirementVersion, M.Requirement)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.RequirementVersion.id.in_(rv_ids))).all()}
    pinned, cs = M.ConfigurationSnapshotItem, M.CompanyStandardVersion
    standards: dict[Any, dict] = {}
    for rv_id, configuration in db.execute(
            select(pinned.requirement_version_id, cs.configuration)
            .join(cs, cs.id == pinned.company_standard_version_id)
            .where(pinned.snapshot_id == review.configuration_snapshot_id,
                   pinned.requirement_version_id.in_(rv_ids))).all():
        standards[rv_id] = configuration
    evaluations: dict = defaultdict(list)
    for ev in db.execute(select(M.Evaluation).where(M.Evaluation.finding_id.in_(ids))
                         .order_by(M.Evaluation.scope_key, M.Evaluation.id)).scalars():
        evaluations[ev.finding_id].append(ev)
    first: dict = {}
    linked: dict = defaultdict(list)
    fe, de = M.FindingEvidence, M.DocumentEvidence
    for fid, e in db.execute(
            select(fe.finding_id, de).join(de, de.id == fe.evidence_id)
            .where(fe.finding_id.in_(ids))
            .order_by(de.page_number, de.start_offset, de.id)):
        first.setdefault(fid, e)
        linked[fid].append(str(e.id))
    out = []
    for f in findings:
        rv, req = versions.get(f.requirement_version_id, (None, None))
        ev = _governing(evaluations[f.id], f.classification)
        out.append({"finding": f, "code": req.code if req else "",
                    "evidence_ids": linked[f.id],
                    "title": ((rv.description if rv else None)
                              or (req.code if req else "")),
                    "standard": standards.get(f.requirement_version_id) or {},
                    "classification": f.classification.value,
                    "actual": (ev.actual_value if ev else None) or {},
                    "expected": (ev.expected_value if ev else None) or {},
                    "evidence": first.get(f.id)})
    return out


def _where(row) -> str | None:
    e = row["evidence"]
    if e is None:
        return None
    # the document's own number, never an added sign (owner, 2026-09-10)
    parts = [e.section_number or None, e.section_title,
             f"page {e.page_number}" if e.page_number is not None else None]
    return " · ".join(p for p in parts if p) or None


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


def _sentences_of(row) -> list[str]:
    """The evidence's sentences, with typographic apostrophes made plain ("Party’s")."""
    evidence = row["evidence"]
    text = ((evidence.content if evidence else "") or "").replace("\u2019", "'").replace(
        "\u2018", "'")
    return re.split(r"(?<=[.;])\s+(?!\d)", text)


def _figure(actual: dict) -> re.Pattern | None:
    """The measured figure as a period in the document's words — "six (6) months",
    "12-month", and 24 months as "two (2) years" — never a bare number ("Clause 24")."""
    have, unit = actual.get("cap_value"), (actual.get("cap_unit") or "MONTHS").upper()
    if not isinstance(have, (int, float)) or have != int(have) or unit not in _UNIT_WORD:
        return None
    forms = [(int(have), _UNIT_WORD[unit])]
    if unit == "MONTHS" and have and have % 12 == 0:
        forms.append((int(have) // 12, "year"))
    if unit == "YEARS":
        forms.append((int(have) * 12, "month"))         # "twenty-four (24) months"
    return re.compile("|".join(
        rf"\b(?:{n}|{_NUMBER_WORDS.get(n, '_')})\b\)?[\s-]*(?:\(\s*\d+\s*\)[\s-]*)?"
        rf"(?:working\s+|calendar\s+)?{u}s?\b" for n, u in forms), re.I)


def _cap_subjects(row) -> list[tuple[str, str]]:
    """(sentence, subject) for each sentence that states a cap — "shall not exceed", "in
    no event … exceed", "limited to", "capped" — never a negated "limited"/"capped"
    ("is not capped", "shall not be limited to", "but not limited to")."""
    out = []
    for sentence in _sentences_of(row):
        for m in _CAP_VERB.finditer(sentence):
            if (m.group(0).lower() == "exceed"
                    or not re.search(r"\bnot\s+(?:be\s+|been\s+)?$", sentence[:m.start()],
                                     re.I)):
                out.append((sentence, sentence[:m.start()]))
                break
    return out


_OURS_WORD = r"(?:leapswitch|cloudpe|(?:service\s+)?provider|supplier)"
_THEIRS_WORD = r"(?:customer|client|partner)"


def _party(m: re.Match, roles: bool) -> str | None:
    """The side a liability noun names. A role ("the Service Provider", "the Customer")
    is LeapSwitch's or the counterparty's only on a customer-service document; on a
    vendor or partner agreement LeapSwitch may be either, so only its name counts
    (r32)."""
    if m.group("both") or m.group("both2"):
        return "both"
    if ours := (m.group("ours") or m.group("ours2")):
        return "ours" if roles or re.match(r"leapswitch|cloudpe", ours, re.I) else None
    return "theirs" if roles else None


def _whose_cap(row) -> str | None:
    """Whose liability the measured cap limits — "both", "ours", "theirs" — from the
    last liability noun before the cap verb in the sentence that holds the measured
    figure (the only cap sentence, when none does); None when the words do not say."""
    figure = _figure(row.get("actual") or {})
    roles = (row.get("document_type") or "") in _CUSTOMER_TYPES - {""}
    caps = _cap_subjects(row)
    measured = ([c for c in caps if figure and figure.search(c[0])]
                or (caps if len(caps) == 1 else []))
    whose = set()
    for _, subject in measured:
        parties = {_party(m, roles) for m in _LIABLE.finditer(subject)}
        # two parties' liability named before one cap, or the other side named anywhere
        # before it ("Leapswitch's liability, excluding the Customer's …", "of the
        # Customer and/or LeapSwitch"): the words do not say whose (r31, r32, r34)
        side = next(iter(parties)) if len(parties) == 1 else None
        other = {"theirs": _OURS_WORD, "ours": _THEIRS_WORD}.get(side or "")
        joint = other and re.search(rf"\b{other}\b", subject, re.I)
        whose.add(None if side is None or joint else side)
    return next(iter(whose)) if len(whose) == 1 else None


_ONE_PARTY = re.compile(r"\b(?:customer|client|partner|leapswitch|cloudpe|provider|"
                        r"supplier|vendor|recipient|receiving\s+party|disclosing\s+party)\b",
                        re.I)


def _mutual(row) -> bool:
    """Whether the measured obligation binds both parties: in the sentence that carries
    the measured figure, the obligation's own subject — the words just before its verb
    ("…, the Receiving Party shall" is one-way though "either party" ends the clause) —
    names both parties, or "the parties" with "each" or "mutual" (r30)."""
    figure = _figure(row.get("actual") or {})
    for sentence in _sentences_of(row):
        m = _OBLIGATION.search(sentence)
        if not m or not (figure and figure.search(sentence)):
            continue
        subject = re.split(r"[,;:]", sentence[:m.start()])[-1]
        parties = re.search(r"\bthe\s+parties\b", subject, re.I)
        both = _BOTH.search(subject)
        if both and _ONE_PARTY.search(subject, both.end()):
            continue        # "by either Party the obligations of the Customer": one-way
        if both or (parties and re.search(
                r"\bof\s+the\s+parties\b|\beach\b|\bmutual", sentence, re.I)):
            return True
    return False


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
        # no deduction for the notice: days are not a fraction of a month (AM-62), so
        # "up to" the whole committed value is the only figure the words support
        if facts.committed_value is not None:
            amount = facts.committed_value
            money = (f"Up to {commercial.rupees(facts.committed_value)} of committed "
                     f"fees is not secured ({commercial.rupees(fee or 0)} a month for "
                     f"{facts.term_months} months"
                     f"{', excluding GST' if facts.excludes_gst else ''}).")
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
                "ours": "It limits what LeapSwitch can owe.",
                "theirs": "It limits what LeapSwitch can recover; LeapSwitch's own "
                          "liability is not capped by this sentence."}.get(
            whose or "", "Read the clause for whose liability it limits.") + (
            f" Our standard is {preferred:g} months." if preferred is not None else "")
        if fee and facts.missing is None:
            amount_text = commercial.rupees(fee * have)
            money = (f"About {amount_text} either way." if whose == "both"
                     else f"About {amount_text}.")
    elif stem == "LIABILITY" and cls == "DEVIATION" and actual.get("cap_status") == \
            "UNLIMITED":
        # uncapped is information like a cap (AM-156 r3): no ₹ figure, never ranked. A
        # clause that also states a cap makes only some claims unlimited (a carve-out)
        # "not capped" only when the clause states no cap and no period to cap by (r31)
        partly = bool(_cap_subjects(row)) or bool(re.search(
            r"\b(?:months?|years?|(?:more|greater)\s+than|in\s+excess\s+of|exceeding|"
            r"maximum|up\s+to)\b", " ".join(_sentences_of(row)), re.I))
        headline = ("This clause makes liability unlimited for at least some claims"
                    if partly else "Liability is not capped in this clause")
        body = (("It states unlimited liability; any cap it also states does not reach "
                 "those claims." if partly else
                 "The clause sets no ceiling on what can be owed under it.")
                + (f" Our standard is {preferred:g} months." if preferred is not None
                   else ""))
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
        # "both parties" only when the obligation's subject proves it; otherwise nothing
        # is said about who is bound — never "the clause does not say" (r34)
        mutual = "Both parties keep each other's information secret for that long"
        standard = (f"our standard is {preferred:g} years." if preferred is not None
                    else "")
        body = ((f"{mutual}; {standard}" if standard else f"{mutual}.") if _mutual(row)
                else (standard[:1].upper() + standard[1:]) or None)
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
        taken = set(out)        # drafting language found: never also its position
        for section, crumb, content in rows:
            words = " ".join((content or "").replace("*", "").split())
            if section in taken or not words or not (head := heading(crumb, name)):
                continue
            if section in out:      # every paragraph under the heading, in order
                out[section]["text"] += "\n\n" + words
            else:
                out[section] = {"section": section, "kind": kind,
                                "label": f"Constitution §{section} — {head}{note}",
                                "text": words}
    return out


def review_angles(db: DBSession, review: M.Review, *, legal_position: bool) -> dict:
    rows = _rows(db, review)
    document_type = _review_document_type(db, review)
    for r in rows:
        r["document_type"] = document_type     # whose roles "provider"/"customer" name
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
