"""Batch 7 (AB-220) — client details before drafting: the ten-item checklist, the server
gate on an MSA/NDA, the client record as the one source (spec §5), the GST certificate
(filed, replaced, read for a person to confirm), the GST/MCA tick, and our CIN locked by
the import tool. Synthetic data only (rule 21): made-up but well-formed identifiers, the
STRUCTURAL placeholder template, and a certificate PDF built in the test."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalmind.db import models as M
from legalmind.drafting import client_details as CD
from legalmind.drafting import library
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tools import import_template as T

V1 = "/api/v1"
#: synthetic identifiers, shaped as the real ones (state 27 = Maharashtra)
PAN = "AAACZ9999Q"
GSTIN = f"27{PAN}1ZU"               # its check character right (round 2, D7)
CIN = "U72900MH2016PTC999999"
OFFICE = "Unit 9, Synthetic Park, Pune, Maharashtra 411001"
FULL = {"legal_name": "Zeta Synthetic Private Limited", "registered_office": OFFICE,
        "registered_email": "accounts@zeta.example.test", "cin_or_llpin": CIN,
        "gstin": GSTIN, "pan": PAN, "line_of_business": "synthetic widget services",
        "signatory_name": "Synthetic Signer", "signatory_designation": "Director",
        "signatory_email": "signer@zeta.example.test"}


# ---------------------------------------------------------------- helpers
def certificate_pdf(lines: list[str]) -> bytes:
    """A one-page PDF with a text layer, laid out as Form GST REG-06 labels its lines."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    for n, line in enumerate(lines):
        page.insert_text((48, 72 + 18 * n), line, fontsize=10)
    return doc.tobytes()


REG06 = ["Form GST REG-06", "Registration Certificate", f"Registration Number : {GSTIN}",
         "1. Legal Name ZETA SYNTHETIC PRIVATE LIMITED", "2. Trade Name, if any ZETA",
         "3. Constitution of Business Private Limited Company",
         "4. Address of Principal Place of Business Unit 9, Synthetic Park,",
         "Pune, Maharashtra, 411001", "5. Date of Liability 01/07/2017"]


def _tv(variables=None, parties=None, doc_type="MSA"):
    return SimpleNamespace(doc_type=doc_type, variables=variables or [],
                           layout={"parties": parties or []})


def _client(**fields):
    base = dict.fromkeys(("legal_name", "registered_office", "registered_email", "cin_or_llpin", "gstin", "pan", "line_of_business", "signatory_name", "signatory_designation", "signatory_email", "country", "gst_certificate", "details_verified_at"))
    return SimpleNamespace(**{**base, "name": "Zeta", **fields})


def _status(found):
    return {i["n"]: i["status"] for i in found["items"]}


# ---------------------------------------------------------------- unit: the checks
def test_the_ten_items_and_the_india_rule():
    tv = _tv([{"key": "effective_date", "type": "date"}])
    blank = CD.checklist(tv, {}, _client())
    assert [i["n"] for i in blank["items"]] == list(range(1, 11))
    assert set(_status(blank).values()) == {"missing"}             # country blank: India
    assert blank["verify_needed"] and not blank["ready"]
    abroad = CD.checklist(tv, {}, _client(country="Germany"))
    assert {n: s for n, s in _status(abroad).items() if n in (4, 9, 10)} == {
        4: "not_needed", 9: "not_needed", 10: "not_needed"}
    assert not abroad["verify_needed"]
    assert CD.checklist(_tv(doc_type="OTHER"), {}, None) == {
        "applies": False, "ready": True, "items": [], "warnings": []}


def test_a_complete_record_with_the_tick_is_ready():
    tv = _tv([{"key": "effective_date", "type": "date"}])
    cert = {"filename": "gst.pdf"}
    found = CD.checklist(tv, {"effective_date": "2026-11-23"},
                         _client(**FULL, gst_certificate=cert))
    assert set(_status(found).values()) == {"done"} and not found["ready"]  # no tick yet
    ticked = _client(**FULL, gst_certificate=cert, details_verified_at=datetime.now(UTC))
    assert CD.checklist(tv, {"effective_date": "2026-11-23"}, ticked)["ready"]


def test_the_pan_inside_the_gstin_must_be_the_clients_pan():
    found = CD.checklist(_tv(), {}, _client(**{**FULL, "pan": "AAACY1111Q"}))
    gst = next(i for i in found["items"] if i["n"] == 9)
    assert gst["status"] == "fix" and gst["problem"] == "pan_mismatch"


@pytest.mark.parametrize(("office", "code"), [
    ("1 Synthetic Road, Bengaluru, Karnataka 560001", "state_differs"),
    ("1 Synthetic Road, Somewhere 000000", "state_unreadable"),
])
def test_the_gstin_state_is_compared_with_the_address(office, code):
    found = CD.checklist(_tv(), {}, _client(**{**FULL, "registered_office": office}))
    assert [w["code"] for w in found["warnings"]] == [code]
    assert next(i for i in found["items"] if i["n"] == 9)["status"] == "done"  # a warning


def test_the_last_state_named_is_the_address_state():
    assert CD.state_codes("Plot 1, Delhi Road, Pune, Maharashtra 411001") == {"27"}
    assert CD.state_codes("Bhubaneswar, Orissa") == {"21"}
    assert CD.state_codes("Hyderabad, Andhra Pradesh") == {"28", "37"}


def test_a_cin_before_2013_warns_about_the_act_wording():
    parties = [{"incorporation": "under the Companies Act, 1956 … {our_cin}"},
               {"incorporation": "a company incorporated under the Companies Act, 2013 "
                                 "… {counterparty_cin}"}]
    old = {**FULL, "cin_or_llpin": "U72900MH2010PTC999999"}
    found = CD.checklist(_tv(parties=parties), {}, _client(**old))
    assert found["warnings"] == [{"code": "act_wording", "item": 4, "year": 2010}]
    assert CD.checklist(_tv(parties=parties), {}, _client(**FULL))["warnings"] == []


def test_a_legal_name_unlike_the_certificates_warns():
    cert = {"filename": "gst.pdf", "read": {"legal_name": "OTHER SYNTHETIC LIMITED"}}
    found = CD.checklist(_tv(), {}, _client(**FULL, gst_certificate=cert))
    assert [w["code"] for w in found["warnings"]] == ["name_differs"]


def test_client_facts_are_read_from_the_record_on_a_gated_template_only():
    variables = [{"key": "client_name", "role": "counterparty_name"},
                 {"key": "client_cin", "role": "counterparty_cin"},
                 {"key": "blank_2", "label": "Customer's line of business"},
                 {"key": "deal", "label": "Deal"}]
    stale = {"client_name": "Old Copy Ltd", "client_cin": "U00000MH2000PTC000000",
             "blank_2": "old words", "deal": "kept"}
    got = CD.effective_answers(_tv(variables), stale, _client(**FULL))
    assert got == {"client_name": FULL["legal_name"], "client_cin": CIN,
                   "blank_2": FULL["line_of_business"], "deal": "kept"}
    # nothing on the record: asked again, never kept from the older copy (the name falls
    # back to the client's own name, as the prefill always did)
    assert CD.effective_answers(_tv(variables), stale, _client()) == {
        "client_name": "Zeta", "deal": "kept"}
    assert CD.effective_answers(_tv(variables, doc_type="OTHER"), stale,
                                _client(**FULL)) == stale


# ---------------------------------------------------------------- unit: the certificate
def test_a_certificate_is_read_by_its_own_labels():
    text = CD.certificate_text(certificate_pdf(REG06), "application/pdf")
    assert CD.read_certificate(text) == {
        "gstin": GSTIN, "pan": PAN, "state": "Maharashtra",
        "legal_name": "ZETA SYNTHETIC PRIVATE LIMITED", "trade_name": "ZETA",
        "registered_office": "Unit 9, Synthetic Park, Pune, Maharashtra, 411001"}


@pytest.mark.parametrize("data", [
    certificate_pdf(["A letter that is not a certificate", "Nothing labelled here"]),
    b"%PDF-1.4 damaged",
    b"\x89PNG\r\n\x1a\n not really an image",
])
def test_a_certificate_that_cannot_be_read_gives_nothing(data):
    kind = "image/png" if data.startswith(b"\x89PNG") else "application/pdf"
    assert CD.read_certificate(CD.certificate_text(data, kind)) == {}


def test_a_label_without_its_closing_label_reads_nothing():
    cut = [line for line in REG06 if "Date of Liability" not in line]
    read = CD.read_certificate(" ".join(cut))
    assert "registered_office" not in read and read["gstin"] == GSTIN


# ---------------------------------------------------------------- unit: our CIN (§4)
def test_the_import_tool_locks_a_declared_variable(placeholder):
    template = placeholder[0]
    template["layout"]["check_values"]["party_one_cin"] = "x"
    assert T.lock_values(template, ["party_one_cin=U30007PN2010PTC137171"]) == [
        "locked party_one_cin"]
    var = next(v for v in template["variables"] if v["key"] == "party_one_cin")
    assert var["locked_value"] == "U30007PN2010PTC137171"
    assert "party_one_cin" not in template["layout"]["check_values"]
    for bad in ("nobody=1", "party_one_cin", "party_one_cin= ", "party_one_cin={x}"):
        with pytest.raises(T.ImportRefused):
            T.lock_values(template, [bad])


def test_an_answer_overriding_our_locked_value_is_refused(placeholder):
    from legalmind.drafting import model as model_
    template = placeholder[0]
    T.lock_values(template, ["party_one_cin=U30007PN2010PTC137171"])
    answers = {**template["layout"]["check_values"], "party_one_cin": "U00000MH2000PTC000000"}
    with pytest.raises(model_.ModelError) as refused:
        model_.validate(template["variables"], answers)
    assert {"field": "party_one_cin", "problem": "is fixed by our standard and cannot be "
            "changed here"} in refused.value.problems
    answers["party_one_name"] = "Another Company Limited"          # our name, likewise
    with pytest.raises(model_.ModelError) as again:
        model_.validate(template["variables"], answers)
    assert {p["field"] for p in again.value.problems} == {"party_one_cin", "party_one_name"}


# ---------------------------------------------------------------- the certificate never leaves
def test_the_certificate_is_read_only_by_the_client_profile_code():
    """Spec §1: never exported to anything client-bound — only the profile's own router,
    the serializer (name/size/date only), this module and the record name it."""
    root = Path(__file__).resolve().parents[2] / "legalmind"
    allowed = {"api/routers/counterparties.py", "api/serializers.py", "db/models.py",
               "security/audit.py",                     # the action's name only
               "drafting/client_details.py"}
    found = {str(p.relative_to(root)) for p in root.rglob("*.py")
             if re.search(r"gst_certificate", p.read_text(encoding="utf-8"))}
    assert found <= allowed, found - allowed


# ---------------------------------------------------------------- API
@pytest.fixture
def staff(db, seeded):
    person = make_user(db)
    grant_role(db, person, P.ROLE_USER)
    return person


@pytest.fixture
def msa(db, api, user, seeded, placeholder, monkeypatch):
    """The placeholder published as an MSA, with Legal's line-of-business fill-in field."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    template = placeholder[0]
    template.update(template_key="PLACEHOLDER.MSA", doc_type="MSA")
    template["variables"].append({"key": "blank_2", "type": "text", "group": "Deal",
                                  "class": "M", "label": "Customer's line of business"})
    template["layout"]["check_values"]["blank_2"] = "synthetic widget services"
    T.import_rows(db, template, placeholder[1], actor_id=user.id)
    tv = db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.MSA").one()
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_DECISION_AUTHORITY)
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        assert api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve"
                        ).status_code == 200
    done = api.post(f"{V1}/templates/{tv.id}/publish")
    assert done.status_code == 200, done.text
    return db.get(M.TemplateVersion, uuid.UUID(done.json()["data"]["id"]))


def _deal_answers(answers):
    """This deal's own answers only — every client fact comes from the record."""
    client_keys = {"party_two_name", "party_two_office", "party_two_cin",
                   "party_two_signatory", "party_two_designation", "party_two_email", "party_two_authority"}
    return {k: v for k, v in answers.items() if k not in client_keys}


def _upload(api, client_id, data=None, kind="application/pdf", name="gst.pdf"):
    return api.post(f"{V1}/counterparties/{client_id}/gst-certificate",
                    content=data if data is not None else certificate_pdf(REG06),
                    headers={"Content-Type": kind, "X-Filename": name})


def test_the_gate_lists_what_is_missing_then_generates_once_complete_and_checked(
        db, api, msa, staff, answers):
    sign_in(api, db, staff)
    client = api.post(f"{V1}/counterparties", json={"name": "Zeta"}).json()["data"]
    draft = api.post(f"{V1}/drafts", json={
        "template_version_id": str(msa.id), "counterparty_id": client["id"],
        "answers": _deal_answers(answers)}).json()["data"]
    url = f"{V1}/drafts/{draft['id']}"
    refused = api.post(f"{url}/create", json={"expected_version": 0})
    assert refused.status_code == 409, refused.text
    err = refused.json()["error"]
    assert err["code"] == "CLIENT_DETAILS_INCOMPLETE" and err["unverified"] is True
    assert [m["n"] for m in err["missing"]] == [2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert api.post(f"{V1}/counterparties/{client['id']}/details-verified"
                    ).status_code == 409                          # nothing to check yet

    assert api.patch(f"{V1}/counterparties/{client['id']}", json=FULL).status_code == 200
    filed = _upload(api, client["id"])
    assert filed.status_code == 201, filed.text
    shown = api.get(f"{url}/client-details").json()["data"]
    assert set(_status(shown).values()) == {"done"} and shown["verified"] is None
    assert shown["questions"] == sorted(["party_two_name", "party_two_office", "party_two_authority",
                                         "party_two_cin", "party_two_signatory",
                                         "party_two_designation", "party_two_email",
                                         "blank_2"])
    still = api.post(f"{url}/create", json={"expected_version": 0})
    assert still.status_code == 409 and still.json()["error"]["missing"] == []

    ticked = api.post(f"{V1}/counterparties/{client['id']}/details-verified")
    assert ticked.status_code == 200 and ticked.json()["data"]["details_verified_at"]
    assert db.query(M.AuditEvent).filter_by(
        action="counterparty.details_verified", entity_id=uuid.UUID(client["id"])).count() == 1
    assert api.get(f"{url}/client-details").json()["data"]["verified"]["by"] == staff.name

    # changing the GSTIN clears the tick and blocks again
    moved = api.patch(f"{V1}/counterparties/{client['id']}",
                      json={"gstin": f"29{PAN}1Z5"})
    assert "details_verified_at" not in moved.json()["data"]
    again = api.post(f"{url}/create", json={"expected_version": 0})
    assert again.status_code == 409 and again.json()["error"]["unverified"] is True
    api.patch(f"{V1}/counterparties/{client['id']}", json={"gstin": GSTIN})
    api.post(f"{V1}/counterparties/{client['id']}/details-verified")

    made = api.post(f"{url}/create", json={"expected_version": 0})
    assert made.status_code == 201, made.text
    values = db.query(M.ContractDraft).filter_by(
        contract_id=uuid.UUID(made.json()["data"]["contract_id"])).one().values
    # the contract printed the record — one source, typed once
    assert (values["party_two_name"], values["party_two_cin"], values["party_two_email"],
            values["blank_2"]) == (FULL["legal_name"], CIN, FULL["signatory_email"],
                                   FULL["line_of_business"])


def test_a_returning_client_needs_no_client_typing(db, api, msa, staff, answers):
    sign_in(api, db, staff)
    client = api.post(f"{V1}/counterparties", json={"name": "Zeta", **FULL}).json()["data"]
    _upload(api, client["id"])
    api.post(f"{V1}/counterparties/{client['id']}/details-verified")
    draft = api.post(f"{V1}/drafts", json={
        "template_version_id": str(msa.id), "counterparty_id": client["id"],
        "answers": _deal_answers(answers)}).json()["data"]
    assert draft["problems"] == []                         # nothing left for the client
    shown = api.get(f"{V1}/drafts/{draft['id']}/client-details").json()["data"]
    assert shown["ready"] is True
    assert api.post(f"{V1}/drafts/{draft['id']}/create",
                    json={"expected_version": 0}).status_code == 201


def test_the_certificate_is_filed_replaced_audited_and_read_for_confirmation(
        db, api, staff):
    sign_in(api, db, staff)
    client = api.post(f"{V1}/counterparties", json={"name": "Zeta", **FULL}).json()["data"]
    cid = client["id"]
    assert _upload(api, cid, b"plain words", "text/plain", "gst.txt").status_code == 422
    assert _upload(api, cid, certificate_pdf(REG06), "image/png").status_code == 422
    first = _upload(api, cid).json()["data"]
    cert = first["gst_certificate"]
    assert set(cert) == {"filename", "mime_type", "size_bytes", "uploaded_at", "read"}
    assert cert["read"]["gstin"] == GSTIN                       # shown, never saved here
    api.post(f"{V1}/counterparties/{cid}/details-verified")
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 64
    second = _upload(api, cid, png, "image/png", "gst.png").json()["data"]
    assert second["gst_certificate"]["filename"] == "gst.png"
    assert "read" not in second["gst_certificate"]              # unreadable: nothing
    assert "details_verified_at" not in second                  # a new file clears it
    events = db.query(M.AuditEvent).filter_by(
        action="counterparty.gst_certificate_set", entity_id=uuid.UUID(cid)).all()
    assert len(events) == 2 and events[1].before_state["filename"] == "gst.pdf"
    assert events[1].after_state["details_verified"] == "cleared"
    got = api.get(f"{V1}/counterparties/{cid}/gst-certificate")
    assert got.status_code == 200 and got.content == png
    stored = db.get(M.Counterparty, uuid.UUID(cid)).gst_certificate
    assert "storage_key" in stored and "storage_key" not in str(
        api.get(f"{V1}/counterparties/{cid}").json())


def test_registered_and_signatory_emails_are_checked(db, api, staff):
    sign_in(api, db, staff)
    bad = api.post(f"{V1}/counterparties", json={"name": "Zeta", "registered_email": "x",
                                                 "signatory_email": "y@"})
    assert {f["field"] for f in bad.json()["error"]["fields"]} == {"registered_email",
                                                                 "signatory_email"}


def test_out_of_scope_is_the_same_404(db, api, msa, staff, answers):
    sign_in(api, db, staff)
    cid = api.post(f"{V1}/counterparties", json={"name": "Zeta"}).json()["data"]["id"]
    draft = api.post(f"{V1}/drafts", json={"template_version_id": str(msa.id),
                                           "counterparty_id": cid}).json()["data"]
    other = make_user(db)
    grant_role(db, other, P.ROLE_USER)
    sign_in(api, db, other)
    for call in (lambda c: api.get(f"{V1}/counterparties/{c}/gst-certificate"),
                 lambda c: api.post(f"{V1}/counterparties/{c}/details-verified"),
                 lambda c: _upload(api, c)):
        hidden, absent = call(cid), call(uuid.uuid4())
        assert hidden.status_code == absent.status_code == 404
        assert hidden.json() == {**absent.json(), "error": {
            **absent.json()["error"], "request_id": hidden.json()["error"]["request_id"]}}
    assert api.get(f"{V1}/drafts/{draft['id']}/client-details").status_code == 404


# ---------------------------------------------------------------- review follow-ups
def test_reads_say_fill_differs_or_same_and_counts_are_nine_and_the_check():
    cert = {"filename": "gst.pdf", "read": {"gstin": GSTIN, "pan": PAN,
                                            "legal_name": "ZETA SYNTHETIC PRIVATE LIMITED",
                                            "registered_office": "Somewhere else, Pune"}}
    client = _client(**{**FULL, "pan": None, "legal_name": "Zeta Synthetic Private Limited"},
                     gst_certificate=cert)
    found = CD.checklist(_tv(), {}, client)
    assert {r["field"]: r["state"] for r in found["reads"]} == {
        "gstin": "same", "pan": "fill", "legal_name": "same", "registered_office": "differs"}
    assert found["counts"] == {"done": 9, "needed": 9} and found["client_ready"] is False
    abroad = CD.checklist(_tv(), {}, _client(country="France"))
    assert abroad["counts"] == {"done": 0, "needed": 6}


def test_the_tick_confirms_unconfirmed_reads_and_a_refused_tick_keeps_nothing(db, api, staff):
    sign_in(api, db, staff)
    typed = {k: v for k, v in FULL.items() if k not in ("gstin", "pan", "legal_name",
                                                         "registered_office")}
    cid = api.post(f"{V1}/counterparties", json={"name": "Zeta", **typed}).json()["data"]["id"]
    cut = [line for line in REG06 if "Principal Place" not in line]   # no address read
    _upload(api, cid, certificate_pdf(cut))
    refused = api.post(f"{V1}/counterparties/{cid}/details-verified")
    assert refused.status_code == 409                       # the address is still missing
    db.expire_all()
    assert db.get(M.Counterparty, uuid.UUID(cid)).gstin is None     # nothing kept
    api.patch(f"{V1}/counterparties/{cid}", json={"registered_office": OFFICE})
    ticked = api.post(f"{V1}/counterparties/{cid}/details-verified").json()["data"]
    assert (ticked["gstin"], ticked["pan"], ticked["legal_name"]) == (
        GSTIN, PAN, "ZETA SYNTHETIC PRIVATE LIMITED")
    event = db.query(M.AuditEvent).filter_by(action="counterparty.details_verified",
                                             entity_id=uuid.UUID(cid)).one()
    assert event.after_state["confirmed_reads"] == {           # D7: the values, PAN too
        "gstin": GSTIN, "pan": PAN, "legal_name": "ZETA SYNTHETIC PRIVATE LIMITED"}
    assert (event.after_state["gstin"], event.after_state["pan"]) == (GSTIN, PAN)  # attested
    listed = api.get(f"{V1}/counterparties").json()["data"]
    assert next(c for c in listed if c["id"] == cid)["details_missing"] == 0
    assert api.get(f"{V1}/counterparties/{cid}").json()["data"]["details_missing"] == 0


def test_the_card_says_who_may_edit_and_fill_ins_come_from_the_last_deal(
        db, api, msa, staff, answers):
    sign_in(api, db, staff)
    client = api.post(f"{V1}/counterparties", json={"name": "Zeta", **FULL}).json()["data"]
    _upload(api, client["id"])
    api.post(f"{V1}/counterparties/{client['id']}/details-verified")
    first = api.post(f"{V1}/drafts", json={
        "template_version_id": str(msa.id), "counterparty_id": client["id"],
        "answers": _deal_answers(answers)}).json()["data"]
    shown = api.get(f"{V1}/drafts/{first['id']}/client-details").json()["data"]
    assert shown["can_edit"] is True and shown["client_ready"] is True
    assert shown["tick_ready"] is True
    assert api.post(f"{V1}/drafts/{first['id']}/create",
                    json={"expected_version": 0}).status_code == 201
    again = api.post(f"{V1}/drafts", json={"template_version_id": str(msa.id),
                                           "counterparty_id": client["id"]}).json()["data"]
    # the deal's own fill-ins come back from the client's last deal; the date never does
    assert again["answers"]["count_value"] == answers["count_value"]
    assert "effective_date" not in again["answers"]


# ---------------------------------------------------------------- round 2 (verifier D1–D8)
@pytest.mark.parametrize(("country", "india"), [
    (None, True), ("", True), ("India", True), ("New Delhi, India", True), ("Inida", True),
    ("N/A", True), ("-", True), ("IN-MH", True), ("Indiana, USA", True),   # unrecognised
    ("NA", True), ("Namibia", False),             # "NA" is "not applicable", not a code
    ("Germany", False), ("DE", False), ("deu", False), ("United States", False),
    ("United States of America", False), ("Singapore", False),
])
def test_only_a_recognised_other_country_is_abroad(country, india):
    assert CD.is_india(_client(country=country)) is india


def test_the_gstin_check_character_is_verified():
    assert CD.gstin_valid(GSTIN) and CD.gstin_valid("27AABCL8707F1ZI")    # a published one
    assert not CD.gstin_valid(f"27{PAN}1Z5") and not CD.gstin_valid("nope")


def test_the_reader_takes_the_block_nearest_its_registration_line():
    footer = ["Legal Name EVIL CORP Trade Name x"]                    # not numbered
    other = "29AAACZ9999Q1ZQ"
    read = CD.read_certificate(" ".join([*footer, f"Registration Number : {other}", *REG06]))
    assert read["legal_name"] == "ZETA SYNTHETIC PRIVATE LIMITED" and read["gstin"] == GSTIN
    bad = CD.read_certificate(" ".join(REG06).replace(GSTIN, f"27{PAN}1Z5"))
    assert "gstin" not in bad and "pan" not in bad and bad["gstin_unreadable"] == "true"
    assert bad["legal_name"] == "ZETA SYNTHETIC PRIVATE LIMITED"
    assert CD.read_certificate(" ".join(footer)) == {}


def test_reading_is_bounded_in_pages_and_pixels():
    import struct
    import time
    import zlib
    huge = (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
            + struct.pack(">IIBBBBB", 20000, 20000, 8, 0, 0, 0, 0) + b"\0" * 4
            + struct.pack(">I", 0) + b"IDAT" + zlib.compress(b"") + b"\0" * 4)
    started = time.monotonic()
    assert CD.certificate_text(huge, "image/png") == ""                  # 400 MP: not drawn
    assert time.monotonic() - started < 1
    import fitz
    doc = fitz.open()
    for n in range(60):
        doc.new_page().insert_text((48, 72), f"page {n + 1} words")
    text = CD.certificate_text(doc.tobytes(), "application/pdf")
    assert "page 2 words" in text and "page 3 words" not in text          # two pages only


def test_a_cin_year_before_2014_warns():
    parties = [{"incorporation": "under the Companies Act, 2013 … {counterparty_cin}"}]
    for year, warns in ((2013, True), (2014, False)):
        cin = f"U72900MH{year}PTC999999"
        found = CD.checklist(_tv(parties=parties), {}, _client(**{**FULL, "cin_or_llpin": cin}))
        assert bool(found["warnings"]) is warns, year


def test_the_tick_needs_a_recorded_legal_name():
    no_name = _client(**{**FULL, "legal_name": None}, gst_certificate={"filename": "g.pdf"})
    assert CD.record_gaps(no_name) == [0]
    assert CD.checklist(_tv(), {}, no_name)["tick_ready"] is False


def test_a_drafts_old_typed_answer_is_offered_where_the_record_is_empty():
    variables = [{"key": "client_email", "role": "counterparty_signatory_email"},
                 {"key": "client_name", "role": "counterparty_name"}]
    answers = {"client_email": "old@zeta.example.test", "client_name": "Typed Name"}
    found = CD.checklist(_tv(variables), answers, _client(legal_name="Zeta Synthetic Pvt Ltd"))
    assert found["draft_values"] == {"signatory_email": "old@zeta.example.test"}


def test_our_cin_lock_must_be_a_cin(placeholder):
    with pytest.raises(T.ImportRefused):
        T.lock_values(placeholder[0], ["party_one_cin=AAB-1234"])      # an LLPIN: refused


def test_the_next_version_from_the_published_one_keeps_everything_but_the_lock(
        db, msa, user):
    lines = T.next_version_locked(db, "PLACEHOLDER.MSA",
                                  ["party_one_cin=U30007PN2010PTC137171"], actor_id=user.id)
    assert lines[-1] == "DRAFT template PLACEHOLDER.MSA@2 from published @1"
    made = db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.MSA",
                                                 version=2).one()
    assert made.status == "DRAFT"
    for field in ("layout", "clauses", "annexures", "assets", "doc_type", "brand"):
        assert getattr(made, field) == getattr(msa, field), field
    changed = [(a, b) for a, b in zip(msa.variables, made.variables, strict=True) if a != b]
    assert changed == [(next(v for v in msa.variables if v["key"] == "party_one_cin"),
                        {**next(v for v in msa.variables if v["key"] == "party_one_cin"),
                         "locked_value": "U30007PN2010PTC137171"})]
    assert made.source["based_on"]["version"] == 1
    again = T.next_version_locked(db, "PLACEHOLDER.MSA",
                                  ["party_one_cin=U30007PN2010PTC137171"], actor_id=user.id)
    assert again[-1].startswith("unchanged template PLACEHOLDER.MSA@2")    # idempotent


def test_a_certificate_too_large_is_refused_in_mb(db, api, staff, monkeypatch):
    monkeypatch.setattr(CD, "MAX_CERTIFICATE_MB", 0)
    from legalmind.api.routers import counterparties as R
    monkeypatch.setattr(R, "_CERTIFICATE_RULE", "Use a PDF, JPG or PNG under 0 MB, "
                        "whose contents match its type.")
    sign_in(api, db, staff)
    cid = api.post(f"{V1}/counterparties", json={"name": "Zeta"}).json()["data"]["id"]
    refused = _upload(api, cid)
    assert refused.status_code == 422 and " MB" in refused.json()["error"]["message"]


def test_the_frontend_country_list_is_the_iso_list():
    """D2: the card's and the client form's Country choices are a copy of the data file."""
    import json
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[3]
    copy = root / "frontend" / "src" / "lib" / "countries.ts"
    if not copy.exists():
        pytest.skip("frontend tree not present in this checkout")
    data = json.loads((root / "backend" / "config" / "iso3166_non_india.json").read_text())
    names = re.findall(r'^  "(.+)",$', copy.read_text(), re.M)
    assert names[0] == "India" and len(names) == len(set(names))
    assert set(names[1:]) == {c["names"][0] for c in data["countries"]}


def test_published_templates_say_which_questions_the_card_owns(db, api, msa, staff):
    """Benchmark 6: step 1 previews only this deal's questions — the server names the rest."""
    sign_in(api, db, staff)
    got = next(t for t in api.get(f"{V1}/templates/published").json()["data"]
               if t["id"] == str(msa.id))
    assert "party_two_cin" in got["client_questions"]
    assert "blank_2" in got["client_questions"]           # Legal's line-of-business fill-in
    assert "effective_date" not in got["client_questions"]


def test_a_client_just_added_says_what_it_still_needs(db, api, staff):
    """Step 1's panel: a new client is never "on file" (the create reply carries the count)."""
    sign_in(api, db, staff)
    made = api.post(f"{V1}/counterparties", json={"name": "Zeta"}).json()["data"]
    assert made["details_missing"] == 9
