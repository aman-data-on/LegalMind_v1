"""Near-duplicate versions share a version group — Ask plan 1.13 (2026-10-01).

Measured on the real corpus first: copies and revisions of one agreement sit at 0.82–1.0
word-shingle Jaccard and unrelated documents below 0.10 — but two DIFFERENT clients'
agreements on one template scored 1.0. So text alone never groups: candidates are the
same contract's versions, or another contract's linked to the SAME counterparty. All
fixtures are synthetic (rule 21).
"""
from legalmind.assist import version_groups
from legalmind.assist.indexing import index_document_version
from legalmind.db import models as M
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.validation import DOCX_MIME
from tests.test_assist_ask import storage  # noqa: F401  (fixture)
from tests.test_assist_indexing import _ingested
from tests.test_ingestion import build_docx

TEMPLATE = [
    "1. Definitions",
    "Partner means the reseller appointed under this agreement for the territory.",
    "2. Appointment",
    "The provider appoints the partner as a non-exclusive reseller of the services.",
    "3. Fees",
    "The partner pays the fees in the order form within thirty days of invoice.",
    "4. Term",
    "This agreement continues for twelve months and renews unless either party objects.",
]
OTHER = ["1. Confidentiality", "Each party keeps the other's information secret for "
         "five years after disclosure, save as required by law."]


def _counterparty(db, user, name):
    c = M.Counterparty(name=name, created_by=user.id)
    db.add(c)
    db.flush()
    return c


def _version(db, storage, user, paragraphs, counterparty=None, contract=None):
    if contract is None:
        v = _ingested(db, storage, user, paragraphs)
    else:                                          # a second version of one contract
        v = ingest_document(db, storage, contract_id=contract, uploaded_by=user.id,
                            data=build_docx(paragraphs), filename="msa-v2.docx",
                            declared_mime=DOCX_MIME).document_version
    if counterparty is not None:
        db.get(M.Contract, v.contract_id).counterparty_id = counterparty.id
    db.flush()
    index_document_version(db, v.id)
    return v


def _group(db, v):
    group = version_groups.group_of(db, v.id)
    assert group is not None, "indexing assigns every version a group"
    return group


def test_two_versions_of_one_contract_share_a_group(db, storage, user):
    a = _version(db, storage, user, TEMPLATE)
    b = _version(db, storage, user, [*TEMPLATE, "5. Notices", "Notices go by email."],
                 contract=a.contract_id)
    assert _group(db, a) == _group(db, b)


def test_copies_filed_under_one_counterparty_share_a_group(db, storage, user):
    acme = _counterparty(db, user, "Placeholder Client A")
    a = _version(db, storage, user, TEMPLATE, counterparty=acme)
    b = _version(db, storage, user, TEMPLATE, counterparty=acme)
    assert a.contract_id != b.contract_id and _group(db, a) == _group(db, b)


def test_one_template_for_two_counterparties_is_two_agreements(db, storage, user):
    a = _version(db, storage, user, TEMPLATE, counterparty=_counterparty(db, user, "Client A"))
    b = _version(db, storage, user, TEMPLATE, counterparty=_counterparty(db, user, "Client B"))
    assert _group(db, a) != _group(db, b)


def test_identical_text_with_no_counterparty_is_not_grouped(db, storage, user):
    a = _version(db, storage, user, TEMPLATE)
    b = _version(db, storage, user, TEMPLATE)
    assert _group(db, a) != _group(db, b)


def test_a_different_document_for_the_same_counterparty_is_its_own_group(
        db, storage, user):
    acme = _counterparty(db, user, "Placeholder Client A")
    a = _version(db, storage, user, TEMPLATE, counterparty=acme)
    b = _version(db, storage, user, OTHER, counterparty=acme)
    assert _group(db, a) != _group(db, b)


def test_similarity_is_shingle_jaccard():
    s = version_groups.shingles("a b c d e f")
    assert version_groups.similarity(s, s) == 1.0
    assert version_groups.similarity(s, version_groups.shingles("v w x y z")) == 0.0
