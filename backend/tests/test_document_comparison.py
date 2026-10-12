"""Diff-Talk — two documents side by side, clause by clause (owner, 2026-10-12): a
stored version or a website document on either side. Text only: 33.16's line holds —
no verdict of any kind."""

from __future__ import annotations

import datetime
from types import SimpleNamespace as NS

import pytest

from legalmind.analysis.document_comparison import align, version_clauses
from legalmind.assist.knowledge import published
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.conftest import grant_role, make_user, sign_in
from tests.test_version_comparison import _version

V1 = "/api/v1"
FEES = "Fees are billed monthly in advance and are payable within fifteen days of invoice."
CANCEL = "Either party may cancel the service by giving thirty days written notice."
LAW = "These terms are governed by the laws of India and the courts of Pune."
REFUND = "Domain name services are not refundable once the domain has been registered."


def _u(text, ref=None):
    return {"ref": ref, "title": ref, "text": text}


def test_clauses_pair_by_text_whatever_the_numbering_and_order():
    source = [_u(FEES, "1"), _u(CANCEL, "2"), _u(REFUND, "3"), _u(LAW, "4")]
    client = [_u(LAW, "9"),                                   # moved to the front
              _u(FEES.replace("fifteen", "forty-five"), "1"),  # wording changed
              _u(CANCEL, "2"),
              _u("The customer may audit the provider's data centre once a year.", "3")]
    rows = align(source, client)
    got = [(r["status"], r["moved"], (r["left"] or {}).get("ref"),
            (r["right"] or {}).get("ref")) for r in rows]
    assert got == [("UNCHANGED", True, "4", "9"),
                   ("CHANGED", False, "1", "1"),
                   ("UNCHANGED", False, "2", "2"),
                   ("ADDED", False, None, "3"),
                   ("REMOVED", False, "3", None)]         # absent, after its source neighbour
    for row in rows:                                       # 33.16: no verdict, ever
        assert set(row) == {"status", "moved", "left", "right"}


def test_a_clause_cut_into_numbered_pieces_is_one_clause_not_many_additions():
    source = [_u(FEES), _u(f"Exclusions. {CANCEL} {LAW} {REFUND}"), _u(REFUND + " " + FEES)]
    client = [_u(FEES), _u(f"1. {CANCEL}"), _u(f"2. {LAW}"), _u(f"3. {REFUND}"),
              _u(REFUND + " " + FEES)]
    statuses = [r["status"] for r in align(source, client)]
    assert statuses == ["UNCHANGED", "CHANGED", "UNCHANGED"]


def test_a_clause_reworded_under_the_same_heading_still_pairs():
    source = [{"ref": "7", "title": "7. Late Fees",
               "text": "Invoices unpaid for more than five days attract a late fee of two "
                       "percent per month on the outstanding amount."},
              _u(CANCEL)]
    client = [_u(CANCEL), {"ref": None, "title": "Late Fees",
               "text": "A late fee applies to overdue invoices: two percent of the amount "
                       "outstanding, charged every month."}]
    rows = align(source, client)
    assert [r["status"] for r in rows] == ["UNCHANGED", "CHANGED"]
    assert rows[1]["left"]["ref"] == "7"
    assert sum(r["moved"] for r in rows) == 1   # two swapped clauses: one of them moved


def test_a_genuinely_added_clause_beside_a_matched_one_is_never_folded_away():
    source = [_u(FEES), _u(CANCEL)]
    client = [_u(FEES), _u("The provider shall maintain cyber insurance of ten crore."),
              _u(CANCEL)]
    assert [r["status"] for r in align(source, client)] == ["UNCHANGED", "ADDED",
                                                            "UNCHANGED"]


def test_contract_rows_group_by_top_level_clause_and_ignore_cross_reference_numbers():
    rows = [NS(id=i, section_number=n, section_title=t, page_number=1, content=c,
               evidence_metadata={"heading": True} if t == "Late Fees" else {})
            for i, (n, t, c) in enumerate([
                (None, None, "Opening words."), ("4", "Payment", "4. Payment"),
                ("4.1", "Billing", "4.1 billed monthly"), (None, None, "page two text"),
                ("19", "CERT-In", "19. CERT-In"),
                ("70", "B(6)", "Section 70B(6) of the Information Technology Act"),
                ("20", "Links", "20. Links"),
                (None, "Late Fees", "Late Fees / overdue invoices"),   # unnumbered heading
                (None, None, "two percent per month")])]
    got = [(c["ref"], c["text"].replace("\n", " / ")) for c in version_clauses(rows)]
    assert got == [(None, "Opening words."),
                   ("4", "4. Payment / 4.1 billed monthly / page two text"),
                   ("19", "19. CERT-In / Section 70B(6) of the Information Technology Act"),
                   ("20", "20. Links"),
                   (None, "Late Fees / overdue invoices / two percent per month")]


# ---------------------------------------------------------------- the endpoint
PAGE = ("<html><body><div class='container'><h1>Leapswitch Terms of Service</h1>"
        f"<p>{' '.join([FEES] * 40)}</p><h2>5. Cancellations</h2><p>{CANCEL}</p>"
        f"<h2>22. Governing Law</h2><p>{LAW}</p></div><div id='footer'>x</div>"
        "</body></html>")
TOS = next(p for p in published.POLICIES if p.key == "TOS-leapswitch")


@pytest.fixture
def approved_tos(db, tmp_path, monkeypatch):
    monkeypatch.setenv("LEGALMIND_SOURCE_MATERIAL_DIR", str(tmp_path))
    published.ingest(db, TOS, PAGE, read_on=datetime.date(2026, 10, 9))


def _contract(db, owner, contract_type="TOS"):
    c = M.Contract(owner_id=owner.id, name="Client TOS", contract_type=contract_type,
                   status=E.ContractStatus.ACTIVE)
    db.add(c)
    db.flush()
    return c


def _signed_in(api, db, user):
    grant_role(db, user, "USER")
    sign_in(api, db, user)


def test_a_document_compares_with_a_website_document(api, db, seeded, user, approved_tos):
    _signed_in(api, db, user)
    listed = api.get(f"{V1}/comparisons/website-documents").json()["data"]
    assert [d["key"] for d in listed] == ["TOS-leapswitch"]          # only what is loaded
    v = _version(db, _contract(db, user), 1, [
        (None, None, " ".join([FEES] * 40)),
        ("1", "Governing Law", f"1. Governing Law {LAW.replace('Pune', 'Mumbai')}"),
        ("2", "Cancellations", f"2. Cancellations {CANCEL}")])
    r = api.get(f"{V1}/comparisons", params={"left": "TOS-leapswitch", "right": str(v.id)})
    assert r.status_code == 200, r.text
    body = r.json()["data"]
    assert body["left"]["kind"] == "WEBSITE" and body["left"]["url"] == TOS.url
    assert body["right"] == {"kind": "DOCUMENT", "title": "Client TOS",
                             "contract_id": str(v.contract_id),
                             "document_version_id": str(v.id), "version_number": 1,
                             "filename": "v1.pdf", "unread_pages": []}
    assert body["summary"]["MOVED"] == 1
    assert [c["status"] for c in body["clauses"]] == ["UNCHANGED", "CHANGED", "UNCHANGED"]
    for word in ("approved", "classification", "rule_outcome", "user_status", "finding",
                 "decision"):
        assert word not in r.text.lower(), word                      # 33.16, plain text


def test_two_uploaded_documents_of_any_type_compare(api, db, seeded, user):
    """An uploaded MSA against a client's MSA — no website copy needed (owner: a
    plain left-against-right comparison)."""
    _signed_in(api, db, user)
    ours = _version(db, _contract(db, user, "MSA"), 1, [("1", "Law", f"1. {LAW}"),
                                                        ("2", "Cancel", f"2. {CANCEL}")])
    theirs = _version(db, _contract(db, user, "MSA"), 1, [("1", "Law", f"1. {LAW}")])
    r = api.get(f"{V1}/comparisons", params={"left": str(ours.id), "right": str(theirs.id)})
    assert r.status_code == 200, r.text
    assert [c["status"] for c in r.json()["data"]["clauses"]] == ["UNCHANGED", "REMOVED"]


def test_a_document_the_caller_cannot_read_is_not_found(api, db, seeded, user,
                                                        approved_tos):
    _signed_in(api, db, user)
    stranger = make_user(db)
    theirs = _version(db, _contract(db, stranger), 1, [("1", "A", LAW)])
    for ref in (str(theirs.id), "00000000-0000-0000-0000-000000000000", "not-a-key"):
        r = api.get(f"{V1}/comparisons", params={"left": "TOS-leapswitch", "right": ref})
        assert r.status_code == 404, (ref, r.text)                    # SEC-07


def test_refusals_say_why(api, db, seeded, user):
    _signed_in(api, db, user)
    v = _version(db, _contract(db, user), 1, [("1", "A", LAW)])
    empty = _version(db, _contract(db, user), 1, [])
    cases = [({"left": "SLA-leapswitch", "right": str(v.id)}, "not available"),
             ({"left": str(v.id), "right": str(v.id)}, "two different"),
             ({"left": str(v.id), "right": str(empty.id)}, "no extracted text")]
    for params, words in cases:
        r = api.get(f"{V1}/comparisons", params=params)
        assert r.status_code == 422 and words in r.text, (params, r.text)


def test_print_headers_and_icon_glyphs_are_not_wording_differences():
    """A browser-printed PDF carries the page URL/date on every page and icon-font
    glyphs (U+E90C) — neither is the client's wording (found 2026-10-12)."""
    header = "https://leapswitch.com/terms-of-service.php\n{}/9"   # counter on its own line
    rows = [NS(id=i, section_number=n, section_title=t, page_number=i + 1,
               content=f"{header.format(i + 1)}\n{c}", evidence_metadata={})
            for i, (n, t, c) in enumerate([("1", "Fees", f"1. Fees {FEES}"),
                                           ("2", "Cancel", f"2. Cancel {CANCEL}"),
                                           ("3", "Law", f"3. Law {LAW}")])]
    clauses = version_clauses(rows)
    assert all("leapswitch.com" not in c["text"] and "" not in c["text"]
               for c in clauses)
    source = [_u(f"1. Fees {FEES}"), _u(f"2. Cancel {CANCEL}"), _u(f"3. Law {LAW}")]
    assert [r["status"] for r in align(source, clauses)] == ["UNCHANGED"] * 3


def test_a_google_docs_export_is_split_at_its_own_clause_numbers():
    """The owner's MSA (2026-10-12): a zero-width space after every number ("4.\\u200b")
    left the parser numbering nothing, one row per PAGE — and 10 clauses were reported
    missing. Each row is split at its own top-level clause lines; sub-clauses, a page
    number and a list restarting at 1 never start one; a short word on its own line
    on several pages ("Agreement.") is wording, not a printed header."""
    pages = [
        "1.\u200b\nDEFINITIONS\n1.1.\u200b Fees mean the fees.\nunder this\nAgreement.\n2\n",
        "2.\u200b\nPAYMENT\n2.1.\u200b Pay monthly under this\nAgreement.\n1.\u200b a list item\n3\n",
        "3.\u200b\nTERM\n3.1.\u200b One year under this\nAgreement.\n4\n",
    ]
    rows = [NS(id=i, section_number=None, section_title=None, page_number=i + 1,
               content=c, evidence_metadata={}) for i, c in enumerate(pages)]
    clauses = version_clauses(rows)
    assert [(c["ref"], c["title"]) for c in clauses if c["ref"]] == [
        ("1", "DEFINITIONS"), ("2", "PAYMENT"), ("3", "TERM")]
    assert all(c["text"].count("Agreement.") == 1 for c in clauses if c["ref"])
    assert "a list item" in next(c for c in clauses if c["ref"] == "2")["text"]
    assert "4.1.This" not in "".join(c["text"] for c in clauses)


def test_schedules_and_the_signature_block_are_their_own_parts():
    """A Schedule the client added and a renamed signing entity must not read as
    "21. General Provisions changed" (owner's MSA, 2026-10-12)."""
    rows = [NS(id=0, section_number=None, section_title=None, page_number=1,
               evidence_metadata={}, content=(
                   "1.\nGENERAL PROVISIONS\n1.1. Notices go by email.\n"
                   "Schedule 1 sets out the fees.\n"
                   "SCHEDULE A DATA HOSTING AND EXIT\n1. Backups are kept 30 days.\n"
                   "IN WITNESS WHEREOF the Parties have signed.\nBy: Leapswitch"))]
    got = [(c["ref"], c["title"]) for c in version_clauses(rows)]
    assert got == [("1", "GENERAL PROVISIONS"),
                   (None, "SCHEDULE A DATA HOSTING AND EXIT"), (None, "Signatures")]
    texts = [c["text"] for c in version_clauses(rows)]
    assert "Schedule 1 sets out the fees." in texts[0]       # wording, not a heading
    assert "1. Backups" in texts[1]                         # a schedule's own "1."


def test_the_two_openings_are_counterparts_however_worded():
    source = [_u("This Dedicated Server agreement sets the guidelines for our services."),
              _u(f"1. Fees {FEES}", "1")]
    client = [_u("Brochure. CloudPe outlines availability terms for customers today."),
              _u(f"1. Fees {FEES}", "1")]
    assert [(r["status"], bool(r["left"]), bool(r["right"])) for r in align(source, client)] \
        == [("CHANGED", True, True), ("UNCHANGED", True, True)]


def test_pages_without_text_are_named_never_silently_skipped(api, db, seeded, user):
    """The owner's MSA: page 19 had no text (it was blank) — the screen names it."""
    _signed_in(api, db, user)
    ours = _version(db, _contract(db, user, "MSA"), 1, [("1", "Law", f"1. {LAW}")])
    theirs = _version(db, _contract(db, user, "MSA"), 1, [("1", "Law", f"1. {LAW}")])
    for row in db.query(M.DocumentEvidence).filter_by(document_version_id=theirs.id):
        row.page_number = 1
    db.add(M.DocumentEvidence(
        document_version_id=theirs.id,
        processing_run_id=db.query(M.DocumentProcessingRun).filter_by(
            document_version_id=theirs.id).one().id,
        page_number=3, content="3. Notice", source_type=E.EvidenceSourceType.NATIVE_TEXT,
        start_offset=500, end_offset=509))
    theirs.extraction_status = E.ExtractionStatus.PARTIAL
    db.query(M.DocumentProcessingRun).filter_by(document_version_id=theirs.id).one() \
        .run_metadata = {"pages_total": 3}
    db.flush()
    r = api.get(f"{V1}/comparisons", params={"left": str(ours.id), "right": str(theirs.id)})
    assert r.status_code == 200, r.text
    assert r.json()["data"]["right"]["unread_pages"] == [2]
    assert r.json()["data"]["left"]["unread_pages"] == []
