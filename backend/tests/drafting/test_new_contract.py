"""S5 — New contract: the client's legal fields, the issuing brand, brand-scoped
standards (`AM-286`, `AM-287`) and the drafts API (questionnaire → answers saved before
v1 → preview → v1 COMPANY_DRAFT reviewed). The STRUCTURAL placeholder template and
synthetic data only (rule 21)."""

import uuid

import pytest

from legalmind.analysis.service import run_analysis
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.drafting import library
from legalmind.security import permissions as P
from tests.conftest import grant_role, make_user, sign_in
from tests.test_analysis import PRESENCE_MAPPING, Builder
from tools import import_template as T

V1 = "/api/v1"
GOVERNING = ["1. Governing Law", "This Agreement is governed by the laws of Ruritania."]


# ---------------------------------------------------------------- fixtures
@pytest.fixture
def staff(db, seeded):
    person = make_user(db)
    grant_role(db, person, P.ROLE_USER)
    return person


@pytest.fixture
def published(db, api, user, seeded, placeholder, monkeypatch):
    """The placeholder template published through the S4 path."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    T.import_rows(db, *placeholder, actor_id=user.id)
    tv = db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.STRUCTURAL").one()
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


# ---------------------------------------------------------------- AM-286
def test_counterparty_legal_fields_round_trip_with_format_checks(db, api, staff):
    sign_in(api, db, staff)
    bad = api.post(f"{V1}/counterparties", json={"name": "Synthetic Client",
                                                 "pan": "ABC", "gstin": "nope",
                                                 "cin_or_llpin": "X1"})
    assert bad.status_code == 422
    assert {f["field"] for f in bad.json()["error"]["fields"]} == {"pan", "gstin",
                                                                 "cin_or_llpin"}
    made = api.post(f"{V1}/counterparties", json={
        "name": "Synthetic Client", "entity_type": "Private limited company",
        "cin_or_llpin": "u72900mh2010ptc123456", "pan": "ABCDE1234F",
        "gstin": "27ABCDE1234F1Z5", "registered_office": "1 Synthetic Road",
        "signatory_name": "Synthetic Signer", "signatory_designation": "Director"})
    assert made.status_code == 201, made.text
    body = made.json()["data"]
    assert body["cin_or_llpin"] == "U72900MH2010PTC123456" and body["pan"] == "ABCDE1234F"
    assert "notice_email" not in body                   # omitted, never nulled
    llp = api.patch(f"{V1}/counterparties/{body['id']}",
                    json={"cin_or_llpin": "AAB-1234", "notice_email": "n@example.test"})
    assert llp.status_code == 200, llp.text
    assert llp.json()["data"]["cin_or_llpin"] == "AAB-1234"
    assert api.get(f"{V1}/counterparties/{body['id']}").json()["data"][
        "notice_email"] == "n@example.test"


def test_a_contract_carries_its_issuing_entity(db, api, staff):
    sign_in(api, db, staff)
    assert api.post(f"{V1}/contracts", json={"name": "x", "issuing_entity": "OTHER"}
                    ).status_code == 422
    made = api.post(f"{V1}/contracts", json={"name": "x", "issuing_entity": "CLOUDPE"})
    assert made.json()["data"]["issuing_entity"] == "CLOUDPE"
    cid = made.json()["data"]["id"]
    moved = api.patch(f"{V1}/contracts/{cid}", json={"issuing_entity": "LEAPSWITCH"})
    assert moved.json()["data"]["issuing_entity"] == "LEAPSWITCH"
    assert db.query(M.AuditEvent).filter_by(action="contract.issuing_entity_set",
                                            entity_id=uuid.UUID(cid)).count() == 1


# ---------------------------------------------------------------- AM-287 r3
@pytest.fixture
def build(db, tmp_path):
    from legalmind.ingestion.storage import LocalFilesystemStorage
    return Builder(db, LocalFilesystemStorage(tmp_path / "objects"), make_user(db))


def _scoped(build, brand):
    build.requirement("GOVLAW-BRAND", E.EvaluatorType.PRESENCE, mapping=PRESENCE_MAPPING,
                      standard={"applicability": "REQUIRED", "expected_presence": "PRESENT",
                                **({"brand": brand} if brand else {})})


@pytest.mark.parametrize(("standard", "contract", "expected"), [
    (None, None, E.FindingClassification.MATCH),                # unchanged
    ("LEAPSWITCH", "LEAPSWITCH", E.FindingClassification.MATCH),
    ("LEAPSWITCH", "CLOUDPE", None),                            # never the other brand
    ("LEAPSWITCH", None, E.FindingClassification.UNABLE_TO_EVALUATE),  # Needs a decision
])
def test_a_brand_scoped_standard_applies_only_to_its_brand(build, db, standard, contract,
                                                          expected):
    _scoped(build, standard)
    review = build.review(GOVERNING)
    db.get(M.Contract, review.contract_id).issuing_entity = contract
    db.flush()
    run = run_analysis(db, review)
    entry = next(a for a in run.applicability if a["code"] == "GOVLAW-BRAND")
    if expected is None:
        assert entry["outcome"] == "NOT_APPLICABLE" and "CLOUDPE" in entry["reason"]
        assert run.findings_created == 0
        return
    finding = db.get(M.Finding, run.outcomes[0].finding_id)
    assert finding.classification is expected
    if contract is None and standard:
        assert "brand not recorded" in entry["reason"]


def test_an_absent_brand_scoped_clause_on_an_unbranded_contract_is_not_minted(build, db):
    _scoped(build, "CLOUDPE")
    review = build.review(["1. Payment", "Fees are payable within 30 days."])
    run = run_analysis(db, review)
    entry = next(a for a in run.applicability if a["code"] == "GOVLAW-BRAND")
    assert entry["outcome"] == "NOT_APPLICABLE" and "not recorded" in entry["reason"]
    assert run.findings_created == 0


# ---------------------------------------------------------------- drafts API
def _start(api, tv, **extra):
    return api.post(f"{V1}/drafts", json={"template_version_id": str(tv.id), **extra})


def test_only_a_published_template_is_offered_or_used(db, api, user, seeded, placeholder,
                                                     staff):
    T.import_rows(db, *placeholder, actor_id=user.id)
    tv = db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.STRUCTURAL").one()
    sign_in(api, db, staff)
    assert api.get(f"{V1}/templates/published").json()["data"] == []
    assert _start(api, tv).status_code == 404                  # a DRAFT is invisible
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_DECISION_AUTHORITY)
    grant_role(db, lawyer, P.ROLE_USER)
    sign_in(api, db, lawyer)
    refused = _start(api, tv)
    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "TEMPLATE_NOT_PUBLISHED"


def test_questionnaire_lists_every_field_and_condition(db, api, published, staff):
    sign_in(api, db, staff)
    [q] = api.get(f"{V1}/templates/published", params={"doc_type": "OTHER"}).json()["data"]
    assert api.get(f"{V1}/templates/published", params={"brand": "CLOUDPE"}
                   ).json()["data"] == []
    by_key = {x["key"]: x for x in q["questions"]}
    assert by_key["count_value"]["range"] == [1, 12] and by_key["count_value"]["class"] == "M"
    assert by_key["option_value"]["allowed"] == ["Option 1", "Option 2"]
    assert by_key["clause_d_value"]["when"] == {"==": [{"var": "include_clause_d"}, True]}
    assert by_key["party_one_name"]["locked_value"] and by_key["effective_date"]["label"]
    schedule_b = next(a for a in q["annexures"] if a["key"] == "SCHEDULE_B")
    assert schedule_b["when"] == {"==": [{"var": "include_schedule_b"}, True]}


def test_a_draft_is_saved_versioned_and_owner_scoped(db, api, published, staff):
    sign_in(api, db, staff)
    made = _start(api, published, answers={"count_value": 3})
    assert made.status_code == 201, made.text
    draft = made.json()["data"]
    assert draft["version"] == 0
    assert {"field": "effective_date", "problem": "is required"} in draft["problems"]
    url = f"{V1}/drafts/{draft['id']}"
    ok = api.patch(url, json={"answers": {"count_value": 4}, "expected_version": 0})
    assert ok.status_code == 200 and ok.json()["data"]["version"] == 1
    assert api.patch(url, json={"answers": {}, "expected_version": 0}).status_code == 409
    other = make_user(db)
    grant_role(db, other, P.ROLE_USER)
    sign_in(api, db, other)
    hidden, absent = api.get(url), api.get(f"{V1}/drafts/{uuid.uuid4()}")
    assert hidden.status_code == absent.status_code == 404
    assert api.get(f"{url}/preview").status_code == 404
    assert api.post(f"{url}/create", json={"expected_version": 1}).status_code == 404
    assert api.get(f"{V1}/drafts").json()["data"] == []


def test_preview_marks_each_value_and_stands_in_for_missing_ones(db, api, published, staff):
    sign_in(api, db, staff)
    draft = _start(api, published, answers={"count_value": 7}).json()["data"]
    shown = api.get(f"{V1}/drafts/{draft['id']}/preview").json()["data"]
    assert "effective_date" in shown["missing"] and shown["model"] is not None
    runs = [r for b in _walk(shown["model"]) for r in b.get("runs") or [] if "var" in r]
    assert {"t": "7", "var": "count_value"} in runs
    assert "values" not in shown["model"]


def _walk(node):
    if isinstance(node, list):
        for x in node:
            yield from _walk(x)
    elif isinstance(node, dict):
        yield node
        for x in node.values():
            yield from _walk(x)


def test_a_missing_mandatory_field_is_named(db, api, published, staff, answers):
    sign_in(api, db, staff)
    partial = {k: v for k, v in answers.items() if k != "party_two_signatory"}
    draft = _start(api, published, answers=partial).json()["data"]
    refused = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    assert refused.status_code == 422
    assert refused.json()["error"]["problems"] == [
        {"field": "party_two_signatory", "problem": "is required"}]


def test_create_makes_v1_company_draft_reviewed_and_prefills_the_next(
        db, api, published, staff, answers):
    sign_in(api, db, staff)
    client = api.post(f"{V1}/counterparties", json={"name": "Synthetic Client"}).json()["data"]
    draft = _start(api, published, counterparty_id=client["id"], answers=answers
                   ).json()["data"]
    made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    assert made.status_code == 201, made.text
    out = made.json()["data"]
    contract = db.get(M.Contract, uuid.UUID(out["contract_id"]))
    assert (contract.owner_id, contract.counterparty_id, contract.contract_type) == (
        staff.id, uuid.UUID(client["id"]), published.doc_type)
    [version] = db.query(M.DocumentVersion).filter_by(contract_id=contract.id).all()
    assert version.version_number == 1
    assert version.doc_metadata["version_role"] == "COMPANY_DRAFT"
    generated = db.query(M.ContractDraft).filter_by(document_version_id=version.id).one()
    assert generated.template_version_id == published.id
    assert generated.model_hash == out["model_hash"]
    assert generated.values["count_value"] == answers["count_value"]
    assert out["review_id"] is not None
    assert db.get(M.Review, uuid.UUID(out["review_id"])).document_version_id == version.id
    assert db.get(M.DraftAnswers, uuid.UUID(draft["id"])) is None      # AM-265 d4
    again = _start(api, published, counterparty_id=client["id"]).json()["data"]
    assert again["answers"]["count_value"] == answers["count_value"]   # last contract
    assert again["answers"]["party_two_name"] == "Synthetic Client"    # the profile wins
    assert "party_one_name" not in again["answers"]                     # locked: not carried
    assert {"party_two_name", "count_value"} <= set(again["prefilled"])


def test_a_deals_own_figure_is_never_carried_from_another_deal():
    """AM-324 r2: a variable marked "prefill": false (the liability months) is answered
    afresh on every deal — never filled from the client's previous contract."""
    from legalmind.api.routers.drafts import prefill_keys
    assert prefill_keys([{"key": "client_name"}, {"key": "our_name", "locked_value": "X"},
                         {"key": "liability_months", "prefill": False},
                         {"key": "effective_date", "type": "date"}]) == {"client_name"}


def test_client_profile_fields_prefill_the_importers_client_questions(db, published):
    """All ten legal fields (`AM-286` r1), by the variable's ROLE — a key such as the
    placeholder's ``party_two_cin`` is filled when its role is ``counterparty_cin``."""
    from legalmind.api.routers import drafts

    profile = {"legal_name": "Synthetic Private Limited", "entity_type": "LLP",
               "cin_or_llpin": "AAB-1234", "pan": "ABCDE1234F", "gstin": "27ABCDE1234F1Z5",
               "registered_office": "1 Synthetic Road", "notice_address": "2 Notice Road",
               "notice_email": "n@example.test", "signatory_name": "Synthetic Signer",
               "signatory_designation": "Director", "authority_reference": "Board, 1 Jan"}
    cp = M.Counterparty(name="Synthetic", created_by=published.created_by, **profile)
    roles = list(drafts.CLIENT_FIELDS)
    tv = M.TemplateVersion(template_key="SYN", variables=[
        *({"key": f"k{i}", "role": r} for i, r in enumerate(roles)),
        {"key": "our_name", "locked_value": "x"}])
    db.add(cp)
    db.flush()

    class _G:
        def __init__(self):
            self.db = db
            self.user_id = published.created_by
            self.permissions = frozenset()
            self.department_id = None

    got = drafts.prefill(_G(), tv, cp)
    assert got == {f"k{i}": profile[drafts.CLIENT_FIELDS[r][0]]
                   for i, r in enumerate(roles)}


def test_every_question_reads_in_words_and_says_where_it_comes_from(db, api, published,
                                                                    staff):
    sign_in(api, db, staff)
    [q] = api.get(f"{V1}/templates/published").json()["data"]
    by_key = {x["key"]: x for x in q["questions"]}
    assert by_key["party_two_cin"]["label"] == "Client's CIN or LLPIN"
    assert by_key["party_two_cin"]["profile_field"] == "cin_or_llpin"
    assert by_key["party_two_cin"]["group"] == "Client" and by_key["party_two_cin"]["help"]
    assert by_key["party_one_signatory"]["group"] == "Our company"
    assert not [x["label"] for x in q["questions"] if "_" in x["label"]]


def test_the_check_before_create_names_the_points_for_legal_and_keeps_nothing(
        db, api, published, staff, answers, monkeypatch):
    from legalmind.drafting import publish

    sign_in(api, db, staff)
    draft = _start(api, published, answers={"count_value": 3}).json()["data"]
    url = f"{V1}/drafts/{draft['id']}/check"
    assert api.get(url).json()["data"] == {"ready": False, "points": []}
    api.patch(f"{V1}/drafts/{draft['id']}", json={"answers": answers, "expected_version": 0})
    monkeypatch.setattr(publish, "_findings", lambda *a, **k: [
        ("GOV-1", "MATCH", "Governing law", False, False),
        ("CONF-1", "MISSING", "Confidentiality", False, True),
        ("PAY-1", "DEVIATION", "Payment period", True, False),   # Acceptable there: B8
        ("LIAB-1", "DEVIATION", "Liability", True, True)])       # favoured, still Legal's
    before = db.query(M.Contract).count()
    shown = api.get(url).json()["data"]
    assert shown["ready"] and shown["points"] == [
        {"code": "CONF-1", "name": "Confidentiality", "classification": "MISSING"},
        {"code": "LIAB-1", "name": "Liability", "classification": "DEVIATION"}]
    assert db.query(M.Contract).count() == before


def test_the_real_check_runs_the_engine_in_a_rolled_back_savepoint(db, api, published,
                                                                  staff, answers):
    sign_in(api, db, staff)
    draft = _start(api, published, answers=answers).json()["data"]
    before = (db.query(M.Contract).count(), db.query(M.Review).count())
    shown = api.get(f"{V1}/drafts/{draft['id']}/check")
    assert shown.status_code == 200, shown.text and shown.json()["data"]["ready"]
    assert (db.query(M.Contract).count(), db.query(M.Review).count()) == before


SOFFICE = __import__("os").environ.get(
    "LEGALMIND_SOFFICE", "/root/legalmind-clm-local/lo/root/opt/libreoffice26.2/program/soffice")


@pytest.mark.skipif(not __import__("os").path.exists(SOFFICE), reason="no LibreOffice")
def test_create_records_the_libreoffice_pdf(db, api, published, staff, answers,
                                            monkeypatch):
    monkeypatch.setenv("LEGALMIND_SOFFICE", SOFFICE)
    sign_in(api, db, staff)
    draft = _start(api, published, answers=answers).json()["data"]
    made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    assert made.status_code == 201, made.text
    # AM-293 r2: made by the worker job (inline here, no broker), recorded on v1
    version = db.get(M.DocumentVersion,
                     uuid.UUID(made.json()["data"]["document_version_id"]))
    rec = version.doc_metadata["pdf"]
    assert rec["status"] == "READY" and rec["kind"] == "contract"
    assert rec["libreoffice_version"].startswith("LibreOffice ")
    got = api.get(f"{V1}{made.json()['data']['pdf']}")
    assert got.status_code == 200 and got.content.startswith(b"%PDF")
    assert __import__("hashlib").sha256(got.content).hexdigest() == rec["pdf_sha256"]


# ---------------------------------------------------------------- AM-316
@pytest.fixture
def named(db, api, user, seeded, placeholder, monkeypatch):
    """The placeholder published with a name and purpose in its catalogue."""
    monkeypatch.delenv("LEGALMIND_SOFFICE", raising=False)
    template, clauses = placeholder
    template["source"]["catalogue"] = {"name": "Placeholder — Original", "purpose": "A test."}
    template["source"]["known_points"] = []
    template["content_hash"] = T.template_hash(template, clauses)
    T.import_rows(db, template, clauses, actor_id=user.id)
    tv = db.query(M.TemplateVersion).filter_by(template_key="PLACEHOLDER.STRUCTURAL").one()
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=user.id))
    lawyer = make_user(db)
    grant_role(db, lawyer, P.ROLE_LEGAL_DECISION_AUTHORITY)
    db.flush()
    sign_in(api, db, lawyer)
    for pin in library.pins(tv):
        api.post(f"{V1}/templates/{tv.id}/clauses/{pin['clause_key']}/approve")
    assert api.post(f"{V1}/templates/{tv.id}/publish").status_code == 200
    return tv, lawyer


def test_a_template_names_itself_and_legal_alone_recommends_it(db, api, named, staff,
                                                               answers):
    tv, lawyer = named
    sign_in(api, db, staff)
    [card] = api.get(f"{V1}/templates/published",
                     params={"template_key": tv.template_key}).json()["data"]
    assert (card["name"], card["purpose"], card["known_points"], card["recommended"]) == (
        "Placeholder — Original", "A test.", [], False)
    assert card["published_at"]
    assert api.get(f"{V1}/templates/published",
                   params={"template_key": "NO.SUCH"}).json()["data"] == []
    [summary] = api.get(f"{V1}/templates").json()["data"]
    assert "source_file" not in summary and summary["name"] == card["name"]
    # recommending is Legal's (a 403 for sales); audited; unset again
    assert api.post(f"{V1}/templates/{tv.id}/recommend",
                    json={"recommended": True}).status_code == 403
    sign_in(api, db, lawyer)
    done = api.post(f"{V1}/templates/{tv.id}/recommend", json={"recommended": True})
    assert done.status_code == 200 and done.json()["data"]["recommended"] is True
    assert db.query(M.AuditEvent).filter_by(action="template.recommended").count() == 1
    sign_in(api, db, staff)
    assert api.get(f"{V1}/templates/published").json()["data"][0]["recommended"] is True
    # the contract carries the template it was made from, and is named by it
    client = api.post(f"{V1}/counterparties", json={"name": "Synthetic Client"}).json()["data"]
    draft = _start(api, tv, counterparty_id=client["id"], answers=answers).json()["data"]
    made = api.post(f"{V1}/drafts/{draft['id']}/create", json={"expected_version": 0})
    detail = api.get(f"{V1}/contracts/{made.json()['data']['contract_id']}").json()["data"]
    assert detail["name"] == "Placeholder — Original — Synthetic Client"
    assert detail["made_from"] == {"template_key": tv.template_key, "version": tv.version,
                                   "doc_type": tv.doc_type, "brand": tv.brand,
                                   "name": "Placeholder — Original"}
    blank = api.get(f"{V1}/templates/{tv.template_key}/blank")
    assert "Placeholder" in blank.headers["content-disposition"]
    sign_in(api, db, lawyer)
    api.post(f"{V1}/templates/{tv.id}/recommend", json={"recommended": False})
    assert api.get(f"{V1}/templates").json()["data"][0]["recommended"] is False


def test_a_withdrawn_template_offers_nothing_and_awaiting_one_is_seen_not_used(
        db, api, named, staff, answers, user, placeholder):
    tv, lawyer = named
    sign_in(api, db, staff)
    client = api.post(f"{V1}/counterparties", json={"name": "Synthetic Client"}).json()["data"]
    made = api.post(f"{V1}/drafts/{_start(api, tv, counterparty_id=client['id'], answers=answers).json()['data']['id']}/create",
                    json={"expected_version": 0}).json()["data"]
    assert api.post(f"{V1}/templates/{tv.id}/withdraw", json={"reason": "x"}).status_code == 403
    sign_in(api, db, lawyer)
    out = api.post(f"{V1}/templates/{tv.id}/withdraw", json={"reason": "Not approved yet"})
    assert out.status_code == 200 and out.json()["data"]["status"] == "RETIRED"
    sign_in(api, db, staff)
    assert api.get(f"{V1}/templates/published").json()["data"] == []
    assert _start(api, tv).status_code == 404                # retired: never used again
    # the contract made from it keeps it
    detail = api.get(f"{V1}/contracts/{made['contract_id']}").json()["data"]
    assert detail["made_from"]["version"] == tv.version
    # a next version marked awaiting approval: listed and downloadable as a draft, not used
    template, clauses = placeholder
    template["version"] = 2
    template["source"]["catalogue"] = {"name": "Placeholder", "awaiting_approval": True}
    template["content_hash"] = T.template_hash(template, clauses)
    T.import_rows(db, template, clauses, actor_id=user.id)
    nxt = db.query(M.TemplateVersion).filter_by(template_key=tv.template_key, version=2).one()
    [row] = [t for t in api.get(f"{V1}/templates").json()["data"] if t["version"] == 2]
    assert row["awaiting_approval"] is True and row["status"] == "DRAFT"
    assert api.get(f"{V1}/templates/{nxt.id}").status_code == 200
    copy = api.get(f"{V1}/templates/{nxt.id}/review-copy")
    assert copy.status_code == 200, copy.text
    assert _start(api, nxt).status_code == 404
