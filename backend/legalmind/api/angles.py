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
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session as DBSession

from legalmind import config
from legalmind.analysis import change_triage, consistency, reading
from legalmind.analysis.client_changes import client_changes
from legalmind.analysis.service import _review_document_type
from legalmind.assist.knowledge import constitution
from legalmind.db import models as M
from legalmind.domain.document_types import DOCUMENT_TYPES
from legalmind.domain.enforceability import note_for
from legalmind.domain.enums import FindingStatus
from legalmind.evaluation.constitution_boundaries import constitution_prohibition_for
from legalmind.evaluation.user_status import _requirement_title, group_ids
from legalmind.extraction import commercial, parties
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
#: An obligation verb — the words before it say who is bound.
_OBLIGATION = re.compile(r"\b(?:shall|must|will|agrees?\s+to|undertakes?\s+to)\b", re.I)
_BOTH = re.compile(r"\b(?:each|either)\s+party'?s?\b|\bboth\s+parties\b|"
                   r"\beach\s+of\s+the\s+parties\b|\bthe\s+parties'\s", re.I)


_CUSTOMER_TYPES = parties.CUSTOMER_TYPES


def _stem(code: str) -> str:
    return code.rsplit("-", 2)[0] if code.count("-") >= 2 else code


#: Clauses read together (owner, 2026-10-21, Step 2): leaving is also what it costs, and
#: a cap is read with what it excludes and what escapes it. Each finding in a group shows
#: the others' clauses, verbatim — context for a person, never a verdict.
_CLUSTERS = ({"CONVENIENCE-NOTICE": "the notice to leave",
              "EARLY-TERM-RESTRICTION": "early exit and what it costs"},
             {"LIABILITY": "the liability cap", "LIAB-EXCLUSIONS": "losses excluded",
              "LIAB-CARVEOUTS": "claims outside the cap",
              "DATA-LOSS-EXCLUSION": "the data-loss exclusion"})


def _related(row, rows: list[dict], clauses: list, facts: commercial.CommercialFacts,
             ) -> list[dict[str, Any]]:
    """The other clauses of this finding's group, each once, with clause and page — and,
    for a way out, the prepaid-refund sentence the document states."""
    group = next((g for g in _CLUSTERS if _stem(row["code"]) in g), None)
    if group is None:
        return []
    seen = set(row["evidence_ids"])
    out = []

    def add(evidence_id, clause, page, text, relation):
        if str(evidence_id) not in seen:
            seen.add(str(evidence_id))
            out.append({"evidence_id": str(evidence_id), "clause": clause, "page": page,
                        "text": " ".join((text or "").split()), "relation": relation})

    for other in rows:
        e = other.get("passage") or other["evidence"]
        # only a clause the review found: a MISSING or unread finding's passage is the
        # nearest text, not the clause (MSA2: "shall not exceed 4 hours" is no cap)
        if (other is not row and e is not None and _stem(other["code"]) in group
                and other["classification"] in ("MATCH", "DEVIATION", "CONFLICT")):
            add(e.id, e.section_number, e.page_number, e.content,
                group[_stem(other["code"])])
            # every clause that finding rests on, not only the one it shows first: a
            # waiver read in the notice clause hid "no early termination charges"
            for c in clauses:
                if str(c.evidence_id) in other["evidence_ids"]:
                    add(c.evidence_id, c.section_number, c.page_number, c.content,
                        group[_stem(other["code"])])
    if "EARLY-TERM-RESTRICTION" in group and facts.refund_evidence:
        refund = next((c for c in clauses if c.evidence_id == facts.refund_evidence),
                      None)
        if refund is not None:
            add(refund.evidence_id, refund.section_number, refund.page_number,
                facts.refund_text, "prepaid fees on leaving")
    return out


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
    sections: dict = defaultdict(list)     # every clause a finding read, in order
    body: dict = {}             # the first passage that is a sentence, not a title
    linked: dict = defaultdict(list)
    fe, de = M.FindingEvidence, M.DocumentEvidence
    for fid, e in db.execute(
            select(fe.finding_id, de).join(de, de.id == fe.evidence_id)
            .where(fe.finding_id.in_(ids))
            .order_by(de.page_number, de.start_offset, de.id)):
        first.setdefault(fid, e)
        if e.section_number and e.section_number not in sections[fid]:
            sections[fid].append(e.section_number)
        if len((e.content or "").split()) >= 8:        # a sentence, never a title line
            body.setdefault(fid, e)
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
                    "evidence": first.get(f.id),
                    "passage": body.get(f.id) or first.get(f.id),
                    "sections": sections[f.id]})
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
    """The evidence's sentences (`parties.sentences`)."""
    evidence = row["evidence"]
    return parties.sentences(evidence.content if evidence else "")


def _figure(actual: dict) -> re.Pattern | None:
    return parties.figure(actual)


def _cap_subjects(row) -> list[tuple[str, str]]:
    return parties.cap_subjects(_sentences_of(row))


def _whose_cap(row) -> str | None:
    """Whose liability the measured cap limits (`parties.cap_party`)."""
    roles = (row.get("document_type") or "") in _CUSTOMER_TYPES - {""}
    return parties.cap_party(_sentences_of(row), row.get("actual") or {}, roles)


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
        # AM-156 R7: a cap's rupees only when it binds both sides — what LeapSwitch can
        # owe AND recover; a one-way or unsaid cap carries no figure (review, 2026-10-21)
        if fee and facts.missing is None and whose == "both":
            money = f"About {commercial.rupees(fee * have)} either way."
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
            "risk": risk, "where": _where(row), "evidence_ids": row["evidence_ids"],
            **_enforceability(row["code"], legal_position)}


def _enforceability(code: str, legal_position: bool) -> dict:
    """The note quotes the Constitution, so it is position text: OMITTED for a reader
    without the positions permission (SEC-07, LEGAL-02), never nulled."""
    return {"enforceability": note_for(code)} if legal_position else {}


#: AM-156 — the action a reader takes on a Finding, in the Constitution's own terms
#: (§24.3, §24.4, §25.1): never "reject", never "approved"; a person always decides.
ACCEPT = "Accept — it matches our position"
SEND_WORDING = "Send our wording; accepting the difference is a Legal decision"
NO_WORDING = "Legal decides — no approved wording exists for this point"
MUST_CHANGE = ("Must change before signing — only an authorised approver may grant an "
               "exception (Constitution §25.1)")
READ_IT = "A person must read this clause before it can be relied on"
#: AM-159 — a point the document states more than once, differently (locked 45C.2), and a
#: point the Constitution defines no boundary for (§23.4: "must not infer or invent a
#: boundary").
CONFLICT_DECIDE = ("The document states this point more than once, differently — a "
                   "person decides which governs")
FAVOURABLE = ("Differs from our standard in our favour — a person confirms it; do not "
              "send our wording, which would ask the other side for less")
UNDEFINED = "Legal decides — the Constitution defines no boundary for this point (§23.4)"


def _in_our_favour(row) -> bool:
    """AM-165: the measured value sits on the side of the standard the standard itself
    names as LeapSwitch's (`favourable_direction`), in the same unit — never inferred."""
    standard, actual = row.get("standard") or {}, row.get("actual") or {}
    direction, preferred = standard.get("favourable_direction"), standard.get("preferred")
    value = actual.get("cap_value")
    if (direction not in ("LOWER", "HIGHER") or not isinstance(preferred, (int, float))
            or not isinstance(value, (int, float))
            or actual.get("cap_unit") != standard.get("unit")):
        return False
    return value < preferred if direction == "LOWER" else value > preferred


def action(row, has_wording: bool) -> str:
    cls = row["classification"]
    if cls == "MATCH":
        return ACCEPT
    if cls in ("DEVIATION", "MISSING", "CONFLICT") and constitution_prohibition_for(
            row["code"], row["actual"]):
        return MUST_CHANGE                  # an unlimited limb in a conflict is still one
    if cls == "DEVIATION" and _in_our_favour(row):
        return FAVOURABLE
    if cls in ("DEVIATION", "MISSING"):
        return SEND_WORDING if has_wording else NO_WORDING
    if cls == "CONFLICT":
        return CONFLICT_DECIDE
    number = row["evidence"].section_number if row.get("evidence") is not None else None
    return f"A person must read clause {number} before it can be relied on" if number \
        else READ_IT                        # where it is, page and title, shows apart


#: What the review RECOMMENDS a person do, in the owner's four words (2026-10-21, Step 3).
#: A recommendation, never a decision: only an authorised reviewer records one, and the
#: system never recommends "Reject" (Constitution §24.3/§25.1).
ACCEPT_WORDS = "Accept"
EXCEPTION_WORDS = "Accept as an exception — a person decides"
REVISE_WORDS = "Request revised wording"
NOT_NEGOTIABLE_WORDS = ("Request revised wording — not negotiable "
                        "(Constitution §24.4, §25.1)")
LEGAL_REVIEW_WORDS = "Seek legal review"


def recommend(action_text: str, uncertain: bool = False) -> str:
    if uncertain:
        return LEGAL_REVIEW_WORDS
    return {ACCEPT: ACCEPT_WORDS, FAVOURABLE: EXCEPTION_WORDS, SEND_WORDING: REVISE_WORDS,
            MUST_CHANGE: NOT_NEGOTIABLE_WORDS}.get(action_text, LEGAL_REVIEW_WORDS)


def _amount(value: Any, unit: Any) -> str | None:
    """A measured quantity in words: 15 DAYS -> "15 days", 2 PERCENT_PER_MONTH ->
    "2 percent per month"."""
    if not isinstance(value, (int, float)) or not unit:
        return None
    return f"{value:g} {str(unit).lower().replace('_', ' ')}"


def _gap(r, legal_position: bool) -> str:
    """The deviation in one line, from the evaluation's own values. The standard's value
    only for a reader who may see positions (SEC-07)."""
    cls, actual, expected = r["classification"], r["actual"], r["expected"]
    ours = _amount(expected.get("preferred"), expected.get("unit")) if legal_position \
        else None
    theirs = _amount(actual.get("cap_value"), actual.get("cap_unit"))
    where = _clauses(r.get("sections") or [])
    if actual.get("reason") == "APPLICABILITY_UNCERTAIN":
        # say what the clause DOES state, then the question (owner, 2026-10-23: a
        # "needs a decision" names exactly what a person decides)
        found = (f"{where[0].upper()}{where[1:]} "
                 f"{'state' if where.startswith('clauses') else 'states'} no figure for "
                 "this" if where else "No figure for this in the document")
        return (found + (f"; our standard: {ours}" if ours else "")
                + " — written for another type of document: Legal to confirm it applies")
    if cls == "MATCH":
        return "Matches our standard"
    if cls == "MISSING":
        return "No clause on this point" + (f"; our standard: {ours}" if ours else "")
    if cls == "CONFLICT":
        # what each statement says, and where — the reader sees why at once
        said = _stated(actual.get("caps") or [])
        return ("The contract states this more than once, differently"
                + (f": {said}" if said else "") + (f" ({where})" if where else "")
                + " — which governs is for a person to decide")
    if cls == "DEVIATION":
        if actual.get("values"):            # a categorical position: the places named
            allowed = [str(v).replace("_", " ").title()
                       for v in r["standard"].get("allowed_values") or ()]
            return (f"{', '.join(actual['values'])} in the contract"
                    + (f"; our standard: {' or '.join(allowed)}"
                       if legal_position and allowed else ""))
        if actual.get("cap_party") in ("ours", "theirs"):
            whose = "LeapSwitch" if actual["cap_party"] == "ours" else "the counterparty"
            return f"The cap binds only {whose}; our standard is a mutual cap"
        if actual.get("cap_status") == "UNLIMITED":
            return "Liability is not capped for at least some claims"
        if actual.get("presence") == "WAIVED":
            return "The clause waives our position"
        if actual.get("presence") == "TOO_BROAD":   # AM-154: indirect loss, lost profits,
            return "Broader than our standard"         # or our control of the defence
        if actual.get("presence") == "RESTATED":    # Constitution §31.11
            return ("The order states its own terms instead of referring to the "
                    "governing MSA")
        if actual.get("presence") == "TOO_NARROW":  # G-F: limited to the causes it lists
            return ("Narrower than our standard — the exclusion covers only the causes "
                    "it lists, not our own operational error")
        if theirs:
            return f"{theirs} in the contract" + (f" vs our {ours}" if ours else "")
        return "Differs from our standard"
    return _unread(actual, theirs, where)


#: A cap or period basis in a reader's words — what the contract counts.
_BASIS_WORDS = {"FEES_PAID": "fees paid", "FEES_PAID_FOR_AFFECTED_SERVICES":
                "fees for the affected services"}


#: Why a found clause was not compared, in the reader's words — the same reasons the
#: finding card states (`findingLanguage.ts` UNREADABLE_WORDS), never "not readable".
_UNREAD = {"NO_FIGURE_STATED": "Clause found, but it states no figure",
           "MODEL_UNVERIFIED": "Clause found; no figure in its words could be confirmed",
           "PLACEHOLDER": ("Not filled in — the figure is blank or in brackets and "
                           "must be agreed"),
           "NEGATED": ("Clause found; it says the period does not apply or is not "
                       "required — read it"),
           "NO_VALUE_STATED": "Clause found, but it names no place",
           "PAID_IN_ADVANCE": ("Payment is taken in advance — there is no invoice period "
                               "to compare with ours")}


def _clauses(numbers: list[str]) -> str:
    shown = [n.rstrip(".") for n in numbers[:4]]
    return ("" if not shown else ("clause " if len(shown) == 1 else "clauses ")
            + ", ".join(shown))


def _stated(caps: list[dict]) -> str:
    """The different things a contract says on one point, in its own units."""
    out = []
    # one fixed order, whatever order the evaluation stored them in: smallest first
    for cap in sorted(caps, key=lambda c: (c.get("cap_status") == "UNLIMITED",
                                           c.get("cap_value") or 0)):
        words = ("unlimited" if cap.get("cap_status") == "UNLIMITED"
                 else _amount(cap.get("cap_value"), cap.get("cap_unit")))
        if words and words not in out:
            out.append(words)
    return " and ".join(out) if len(out) > 1 else ""


def _unread(actual: dict, theirs: str | None, where: str = "") -> str:
    reason = actual.get("reason")
    if reason in _UNREAD:
        return _UNREAD[reason]
    if reason in ("SEVERAL_FIGURES", "FIGURE_NOT_READ"):
        figures = list(actual.get("candidates") or ())
        if len(figures) == 1:
            return (f"The clause states {figures[0]}, which could not be compared with "
                    "our standard — a person reads it")
        return ("The clause states " + (", ".join(figures) or "several figures")
                + "; which one is this term needs a person")
    if actual.get("presence") == "INDETERMINATE" or not actual:
        # several passages touch the point, none plainly states it (the mapping kept
        # them all rather than pick one — Step 28 r6)
        return ((f"Several passages touch this ({where}), but none clearly states it"
                 if "," in where else
                 f"The contract touches this in {where}, but does not clearly state it"
                 if where else
                 "No passage clearly states this")
                + " — a person reads " + ("them" if where else "the contract"))
    if theirs:
        # the figure is read; what it is FOR differs from, or is not confirmed as, what
        # we measure (owner, 2026-10-23: no jargon — say what a person checks)
        basis = actual.get("cap_basis")
        if basis:
            return (f"{theirs} in the contract, counted on a different basis from ours "
                    f"({_BASIS_WORDS.get(basis, str(basis).lower().replace('_', ' '))})"
                    " — a person compares them")
        return (f"{theirs} in the contract, but the clause does not say it is counted "
                "the way our standard counts it — a person compares them")
    return "The clause could not be identified with certainty — a person reads it"


def _case(r, item: dict, point: dict | None, source: dict | None,
          legal_position: bool) -> dict[str, Any]:
    """One finding as a careful reviewer states it (owner, 2026-10-21, Step 3): what the
    contract says, what our standard says and where it comes from, the gap, the business
    impact the figures support, the related clauses, and the recommended action. Built by
    code from the evaluation, the evidence and the Constitution; no model writes it."""
    passage = r.get("passage") or r["evidence"]
    c = r["standard"].get("constitution") or {}
    standard: dict[str, Any] = {"section": c.get("section"), "topic": c.get("topic")}
    if legal_position:
        standard["value"] = _amount(r["expected"].get("preferred"),
                                    r["expected"].get("unit"))
        if source:
            standard["source"] = {"label": source["label"], "quote": source["text"]}
    return {
        "contract": None if r["classification"] == "MISSING" or passage is None else {
            "quote": " ".join((passage.content or "").split()),
            "clause": passage.section_number, "page": passage.page_number},
        "standard": standard,
        "gap": _gap(r, legal_position),
        "business": ({"headline": point["headline"], "body": point["body"],
                      "money": point["money"]} if point else None),
        "related": item["related"],
        "recommendation": recommend(item["action"], r["actual"].get("reason")
                                    == "APPLICABILITY_UNCERTAIN"),
    }


def _action_rank(text: str) -> int:
    """Must change first, then send our wording, then what a person decides or reads."""
    return 0 if text == MUST_CHANGE else 1 if text == SEND_WORDING else 2


#: what a person does with an observation (AM-159); a precedence rule is information
_OBSERVATION_ACTION = {
    consistency.RENEWAL_TWO_WAYS: CONFLICT_DECIDE,
    consistency.SUBJECT_TO: "A person reads these clauses together",
    consistency.PRECEDENCE: None,
    consistency.NO_NONPAYMENT_REMEDY: UNDEFINED,
    consistency.OUR_DETAILS: "Correct our own details before signing",
    consistency.UPTIME_TWO_WAYS: "State one uptime commitment, as our SLA does",
}


def recommendation(items: list[dict], observed: dict, measured: int,
                   decided: int = 0) -> str | None:
    """AM-160 — one line, computed from the actions above and nothing else: a
    recommendation an authorised person decides on (§24.3, §25.1), never a score, a level
    or a decision of the system's own. With nothing measured there is nothing to
    recommend — no line at all, whatever was observed (no claim about our positions)."""
    if not measured:
        return None
    def n(count: int, word: str) -> str:
        return f"{count} {word}{'s' * (count != 1)}"
    if decided and not items:
        # AM-179 (2026-10-22): every point a person had to act on is decided — the
        # recommendation no longer counts them; what follows is the contract decision
        return (f"Every point is decided ({n(decided, 'point')}); the decision on the "
                "contract follows (§24.3).")
    must = sum(i["action"] == MUST_CHANGE for i in items)
    change = sum(i["action"] == SEND_WORDING for i in items)   # NO_WORDING: decide
    decide = len(items) - must - change + sum(
        o.get("action") is not None for o in observed["structural"])
    tail = f"; a person must decide or read {n(decide, 'point')} first" if decide else ""
    if must:
        more = f", and {n(change, 'other change')} proposed" if change else ""
        return (f"Recommendation: do not sign as drafted — {n(must, 'point')} must "
                f"change before signing{more}{tail}. Only an authorised approver may "
                "grant an exception (§25.1).")
    if change:
        return (f"Recommendation: sign after {n(change, 'change')}{tail}. An authorised "
                "person decides (§24.3).")
    # a deviation with no approved wording still differs from our positions (review r27)
    differ = sum(i.get("classification") in ("DEVIATION", "MISSING") for i in items)
    if decide and differ:
        return (f"Recommendation: a person must decide or read {n(decide, 'point')} "
                f"before signing; {n(differ, 'point')} "
                f"{'differs' if differ == 1 else 'differ'} from our positions with no "
                "approved wording to send.")
    if decide:
        return ("Recommendation: no point differs from our positions, but a person must "
                f"decide or read {n(decide, 'point')} before signing.")
    return ("No point differs from our positions — a person still reviews before final "
            "sign-off (§25.2).")


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


_TYPES = {t.upper() for t in DOCUMENT_TYPES}


def review_angles(db: DBSession, review: M.Review, *, legal_position: bool) -> dict:
    rows = _rows(db, review)
    document_type = _review_document_type(db, review)
    for r in rows:
        r["document_type"] = document_type     # whose roles "provider"/"customer" name
    clauses = load_clauses(db, review.document_version_id)
    facts = commercial.read(clauses)
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
    by_finding = {p["finding_id"]: p for p in points}
    items = sorted(({"finding_id": str(r["finding"].id), "requirement_code": r["code"],
                     "title": r["title"], "classification": r["classification"],
                     "waived": (r["actual"].get("presence") == "WAIVED"),
                     "action": action(r, wording.get(str(r["finding"].id), {})
                                      .get("kind") == "DRAFTING_LANGUAGE"),
                     "where": _where(r), "evidence_ids": r["evidence_ids"],
                     "related": _related(r, rows, clauses, facts),
                     **_enforceability(r["code"], legal_position)} for r in actionable),
                   key=lambda item: (_action_rank(item["action"]),
                                     item["requirement_code"], item["finding_id"]))
    # AM-179: one item per POINT, carrying whether a person decided it; the open list
    # and the recommendation read only what is still undecided
    groups = group_ids(db, [review.id], legal_position=legal_position)
    seen: set[str] = set()
    one_per_point = []
    for item in items:
        group = groups.get(UUID(item["finding_id"]), item["finding_id"])
        if group in seen:
            continue
        seen.add(group)
        item["group_id"] = group
        one_per_point.append(item)
    items = one_per_point
    rows_by_id = {str(r["finding"].id): r for r in actionable}
    resolved = {str(r["finding"].id) for r in actionable
                if r["finding"].status is FindingStatus.RESOLVED}
    for p in points:
        p["decided"] = p["finding_id"] in resolved
    for item in items:
        r = rows_by_id[item["finding_id"]]
        item["decided"] = item["finding_id"] in resolved
        section = str((r["standard"].get("constitution") or {}).get("section") or "")
        item["case"] = _case(r, item, by_finding.get(item["finding_id"]),
                             by_section.get(section), legal_position)
    observed = consistency.observe(clauses, document_type)
    # what the client changed, each change beside the standard that measured its clause
    measured: dict[str, list[str]] = {}
    for r in rows:
        for e in r["evidence_ids"]:
            name = _requirement_title(r["code"], None, _TYPES)
            if name not in measured.setdefault(str(e), []):
                measured[str(e)].append(name)
    # the kept model reading is read only for a marked-up copy — an unmarked one has none
    marked = any((c.marks or {}).get("changes") for c in clauses)
    changes = client_changes(clauses, measured,
                             change_triage.read_back(db, review.document_version_id)
                             if marked else {},
                             legal_position=legal_position,
                             vendor=document_type == "VENDOR_AGREEMENT")
    for item in observed["structural"]:
        item["action"] = _OBSERVATION_ACTION.get(item["kind"])
        if not legal_position:
            del item["basis"]               # the Constitution's words (SEC-07: omitted)
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
                  # answer that cites a clause can show that clause's findings (AM-152);
                  # what must change first, then what to send, then what a person
                  # decides or reads (AM-159 D)
                  "items": items},
        # what a careful reader notices across the document — never a Finding (AM-159)
        "observations": observed,
        "recommendation": recommendation([i for i in items if not i["decided"]], observed,
                                         len(rows),
                                         decided=sum(i["decided"] for i in items)),
        # the lawyer's second read, its own label, never a Finding (AM-162); absent
        # when the document was never read
        **({"reading": got} if (got := reading.read(
            db, review.document_version_id,
            {str(e) for r in rows for e in r["evidence_ids"]})) else {}),
        "counter_proposals": proposals,
        **({"client_changes": changes} if changes else {}),
    }
