"""Lawyer judgement P1 (`AM-476`): references into our paper, looked up in the pinned
version of our document, failing closed. Pure functions; every text here is synthetic
and states no position of ours (rule 21) — "our" clauses are placeholders.
"""
from __future__ import annotations

import pathlib
import re
import uuid
from datetime import date

from legalmind.analysis import consistency, our_paper
from legalmind.assist.knowledge import published
from legalmind.mapping.engine import Clause

ROOT = pathlib.Path(__file__).resolve().parents[1] / "legalmind"


def _clauses(*rows: str) -> list[Clause]:
    """Rows as the parser gives them: a leading number is the row's clause number."""
    return [Clause(evidence_id=uuid.uuid4(), content=r,
                   section_number=(m := re.match(r"(\d+(?:\.\d+)*)\.?\s", r)) and m.group(1))
            for r in rows]


def _refs(*rows: str) -> list[tuple]:
    return [(r["source"], r["doc"], r["number"] or r["described"], r["verb"])
            for r in consistency.paper_references(_clauses(*rows))]


def test_numbered_forms_lists_and_inversions():
    got = _refs("1. Status",
                "1.1 This replaces MSA clauses 17.2, 17.3 and 17.7 and section 13 of "
                "the Terms of Service.",
                "1.2 Credits are set off despite MSA clause 8.4 (no set-off).",
                "1.3 AUP §5 and Service Level Agreement section 2 apply.",
                "1.4 MSA clause 15.3 is subject to this clause.",
                "1.5 Doing so is not a breach of MSA clause 9.6(a) or 13.3 (changes).")
    assert got == [
        ("1.1", "MSA", "17.2", "REPLACES"), ("1.1", "MSA", "17.3", "REPLACES"),
        ("1.1", "MSA", "17.7", "REPLACES"), ("1.1", "TOS", "13", "REPLACES"),
        ("1.2", "MSA", "8.4", "DESPITE"), ("1.3", "AUP", "5", "REFERS"),
        ("1.3", "SLA", "2", "REFERS"), ("1.4", "MSA", "15.3", "SUBJECT_TO"),
        ("1.5", "MSA", "9.6", "REFERS"), ("1.5", "MSA", "13.3", "REFERS")]
    titled = consistency.paper_references(_clauses(
        "1. A", "1.1 This replaces MSA clause 7.3 (renewal and 30 days' notice)."))
    assert titled[0]["title"] == "renewal and 30 days' notice"


def test_described_references_and_what_is_not_a_reference():
    got = _refs("1. A", "1.1 The provision of the SLA under which credits lapse on "
                "termination does not apply. The statement in the SLA that credits are "
                "the exclusive remedy does not limit clause 2.")
    assert got == [("1.1", "SLA", "credits lapse", "DOES_NOT_APPLY"),
                   ("1.1", "SLA", "exclusive remedy", "REFERS")]
    # its own clauses, a statute, a whole document: none is a reference into our paper
    assert _refs("1. A", "1.1 Clause 5 of this Agreement and section 5 of the Act apply.",
                 "1.2 Clause 3 of this Master Services Agreement applies.",
                 "1.3 Credits are as per the SLA; subject to the Terms of Service.") == []


MSA = {"label": "MSA template version 2", "file": "t", "sha256": "a" * 64,
       "date": "2026-01-01", "paragraphs": [], "units": {
           "7": {"title": "TERM", "text": "7. TERM"},
           "7.3": {"title": "Renewal", "text": "Renews for six (6) months; thirty (30) "
                   "days' notice."},
           "8.4": {"title": None, "text": "Paid without any deduction, set-off or "
                   "counter claim."},
           "17.7": {"title": None, "text": "Not more than the fees paid in the ________ "
                    "months preceding the claim."}}}


def _row(text: str, bases: dict) -> dict:
    return our_paper.resolve(consistency.paper_references(_clauses("1. A", text)),
                             bases)[0]


def test_lookup_quotes_our_text_with_a_quoted_marker_and_the_pin():
    row = _row("1.1 Set off despite MSA clause 8.4.", {"MSA": MSA})
    assert row["status"] == our_paper.RESOLVED and row["verb"] == "DESPITE"
    assert row["ours"]["quote"].startswith("Paid without")
    assert row["markers"] == ["without any deduction, set-off"]
    assert row["pin"] == {"label": "MSA template version 2", "file": "t",
                          "sha256": "a" * 64, "date": "2026-01-01"}
    top = _row("1.1 This replaces MSA clause 7.", {"MSA": MSA})
    assert "Renews for six" in top["ours"]["quote"]       # a top-level number: 7.x too


def test_fails_closed_with_its_reason():
    assert _row("1.1 MSA clause 99.1 applies.", {"MSA": MSA})["status"] == \
        our_paper.POINTS_NOWHERE
    # the client's title is a summary: words and numbers, never the string (N2)
    assert _row("1.1 This replaces MSA clause 7.3 (six-month renewal and 30 days' "
                "notice).", {"MSA": MSA})["status"] == our_paper.RESOLVED
    assert _row("1.1 This replaces MSA clause 7.3 (limitation of liability).",
                {"MSA": MSA})["status"] == our_paper.TITLE_MISMATCH
    assert _row("1.1 This replaces MSA clause 7.3 (renewal and 60 days' notice).",
                {"MSA": MSA})["status"] == our_paper.TITLE_MISMATCH
    which = {"MSA": {"unresolved": our_paper.WHICH_MSA}}
    assert _row("1.1 MSA clause 7.3 applies.", which)["status"] == our_paper.WHICH_MSA
    assert "ours" not in _row("1.1 MSA clause 7.3 applies.", which)
    nobrand = {"TOS": {"unresolved": our_paper.NO_BRAND}}
    assert _row("1.1 Section 5 of the Terms of Service applies.", nobrand)["status"] \
        == our_paper.NO_BRAND
    blank = _row("1.1 This replaces MSA clause 17.7.", {"MSA": MSA})
    assert blank["status"] == our_paper.RESOLVED and blank["blank"].startswith("________")


def _policy(day: date, text: str) -> dict:
    units, paragraphs = our_paper.policy_units([
        ("SECTION", "Terms", "Terms"), ("SECTION", "5. Refunds", "5. Refunds"),
        ("PARAGRAPH", None, text), ("SECTION", "Scope", "Scope"),
        ("PARAGRAPH", None, "More words.")])
    return {"label": f"Terms as published on {day}", "file": "f", "sha256": str(day),
            "source_id": text, "date": day.isoformat(), "started_on": day,
            "units": units, "paragraphs": paragraphs}


def test_policy_is_the_stored_copy_in_force_on_the_documents_date():
    old = _policy(date(2026, 10, 9), "Placeholder A is not refundable.")
    new = _policy(date(2026, 11, 2), "Placeholder B.")
    got = published.in_force([old, new], date(2026, 10, 20))
    assert got["pinned"] is old and got["newer"] is new
    row = _row("1.1 Despite section 5 of the Terms of Service, it is refunded.",
               {"TOS": {**got["pinned"], "newer": got["newer"]}})
    assert row["ours"]["quote"] == "Placeholder A is not refundable. More words."
    assert row["markers"] == ["not refundable"]
    assert row["changed_since"]["date"] == "2026-11-02"          # BASE_CHANGED_SINCE
    assert published.in_force([old, new], date(2026, 11, 5))["newer"] is None
    early = published.in_force([old, new], date(2026, 10, 5))
    assert early["pinned"] is None and early["earliest"] == date(2026, 10, 9)
    # A → B → A: B's period stands; A again only from its second start
    again = {**old, "started_on": date(2026, 11, 20)}
    assert published.in_force([old, new, again], date(2026, 11, 10))["pinned"] is new
    assert published.in_force([old, new, again], date(2026, 11, 25))["pinned"] is again


def test_described_reference_matches_by_wording_or_points_nowhere():
    sla = {"label": "SLA", "units": {}, "paragraphs": [
        "Placeholder credits are nullified as of the termination date.",
        "Placeholder credits are your exclusive remedy."]}
    rows = our_paper.resolve(consistency.paper_references(_clauses(
        "1. A", "1.1 The provision of the SLA under which credits lapse does not "
        "apply.")), {"SLA": sla})
    assert rows[0]["ours"]["quote"].endswith("nullified as of the termination date.")
    sla["paragraphs"] = ["Placeholder words."]
    assert our_paper.resolve(consistency.paper_references(_clauses(
        "1. A", "1.1 The provision of the SLA under which credits lapse does not "
        "apply.")), {"SLA": sla})[0]["status"] == our_paper.POINTS_NOWHERE


def test_document_date_fingerprint_and_the_brief_line():
    assert our_paper.document_date(_clauses("Addendum", "Draft, 5 October 2026")) == \
        date(2026, 10, 5)
    assert our_paper.document_date(_clauses("effective as of 16th day of October, "
                                            "2026")) == date(2026, 10, 16)
    assert our_paper.document_date(_clauses("as of ____ day of ____, 2025")) is None
    refs = consistency.paper_references(_clauses(
        "1. A", "1.1 This replaces MSA clause 7.3 (renewal and 30 days' notice)."))
    other = {**MSA, "label": "other", "units": {"7.3": {"title": "Fees", "text": "Fees."}}}
    assert [(f["label"], f["fits"], f["of"]) for f in our_paper.fingerprint(
        refs, [MSA, other])] == [("MSA template version 2", 1, 1), ("other", 0, 1)]
    rows = our_paper.resolve(refs, {"MSA": MSA})
    assert our_paper.overridden(rows) == ["MSA 7.3"]


def test_no_direction_or_effect_words_in_what_is_shown():
    """Rule 7 / M5: the rows carry quotes, numbers, verbs and reasons only."""
    rows = our_paper.resolve(consistency.paper_references(_clauses(
        "1. A", "1.1 This replaces MSA clauses 7.3 and 8.4.")), {"MSA": MSA})
    said = repr(rows).lower()
    for word in ("favour", "worse", "better", "risk", "helps", "hurts", "onto",
                 "away from", "acceptable"):
        assert word not in said


def test_nothing_that_decides_reads_our_paper():
    """M7, by construction: only the read-only route and the offline harness import the
    resolver or the cross-document parser — never the evaluator, a change list, a
    route, the effect rule, the brief's counts or Ask."""
    users = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py")
             if re.search(r"\bour_paper\b|\bpaper_references\b", p.read_text())}
    assert users == {"analysis/our_paper.py", "analysis/consistency.py",
                     "api/routers/our_paper.py", "api/app.py"}
    assert "paper_references" not in (ROOT / "analysis/consistency.py").read_text() \
        .split("def observe(")[1].split("\ndef ")[0]


def test_a_verb_binds_to_the_references_own_clause_never_the_sentence():
    """Round 2 (verifier blocker): a verb elsewhere in the sentence is not this
    reference's; unsure is REFERS."""
    assert _refs(
        "5. A",
        "5.1 The Customer shall comply with MSA clause 6, and the price list in Annex B "
        "replaces the old rate card.",
        "5.2 MSA clause 9 remains in full force; the late fee in clause 3 of this Addendum "
        "does not apply to disputed invoices.",
        "5.3 Despite the delay, the Provider shall meet MSA clause 5.1 (delivery).",
        "5.4 MSA clause 9.2 remains in full force and is not replaced.",
        "5.5 The right under MSA clause 13.2 includes these uses.") == [
        ("5.1", "MSA", "6", "REFERS"), ("5.2", "MSA", "9", "REFERS"),
        ("5.3", "MSA", "5.1", "REFERS"), ("5.4", "MSA", "9.2", "REFERS"),
        ("5.5", "MSA", "13.2", "REFERS")]
    assert _refs(
        "6. A", "6.1 This Schedule supersedes paragraphs 3.2 and 3.5 of the SLA.",
        "6.2 MSA clause 10.2 (Cap) is hereby deleted and replaced with the following.",
        "6.3 This replaces the 60 days in MSA clause 18.3, and MSA clauses 18.4 and 21.2 "
        "are subject to this clause.",
        "6.4 Credits are refunded despite MSA clauses 5.6 and 8.1 and section 5 of the "
        "Terms of Service.") == [
        ("6.1", "SLA", "3.2", "REPLACES"), ("6.1", "SLA", "3.5", "REPLACES"),
        ("6.2", "MSA", "10.2", "REPLACES"), ("6.3", "MSA", "18.3", "REPLACES"),
        ("6.3", "MSA", "18.4", "SUBJECT_TO"), ("6.3", "MSA", "21.2", "SUBJECT_TO"),
        ("6.4", "MSA", "5.6", "DESPITE"), ("6.4", "MSA", "8.1", "DESPITE"),
        ("6.4", "TOS", "5", "DESPITE")]


def test_the_documents_own_date_never_a_deadline_or_another_documents():
    assert our_paper.document_date(_clauses("Fees", "Pay by 31 December 2026.")) is None
    assert our_paper.document_date(_clauses(
        "Addendum to the MSA dated 1 January 2024, effective as of 10 November 2026")) \
        == date(2026, 11, 10)
    assert our_paper.document_date(_clauses("Addendum to the MSA dated 1 January 2024."))\
        is None
