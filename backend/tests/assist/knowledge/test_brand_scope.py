"""A document is answered with its OWN brand's published policies (C-19, Constitution §4:
"must never silently substitute a Leapswitch document or rule for a CloudPe one").

Found 2026-10-16 on the live site: a CloudPe SLA's "99.2% uptime — what credit?" answer
carried Leapswitch's 15/40/100 schedule beside CloudPe's 5/10/20. The brand is read from
the document's own words, never stored; with no brand it is both, labelled, as before.
Synthetic text only (rule 21)."""
from __future__ import annotations

from legalmind.assist.ingestion import indexing
from legalmind.assist.knowledge import constitution, published
from legalmind.assist.query import query_plan, routing
from legalmind.assist.retrieval import retrieval
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.ingestion.service import ingest_document
from legalmind.ingestion.validation import DOCX_MIME
from tests.assist.knowledge.test_published_policies import (  # noqa: F401  (fixture)
    CLOUDPE,
    DAY,
    LEAPSWITCH,
    PERMS,
    SLA_CP,
    SLA_LS,
    material,
)
from tests.test_ingestion import build_docx


def test_the_brand_rule_reads_who_a_text_is_about():
    # measured shapes: a CloudPe page names its operator a few times
    assert published.brand_of({"CloudPe": 28, "Leapswitch": 4}) == "CloudPe"
    assert published.brand_of({"CloudPe": 1, "Leapswitch": 33}) == "Leapswitch"
    assert published.brand_of({"CloudPe": 0, "Leapswitch": 2}) == "Leapswitch"  # an NDA
    assert published.brand_of({"CloudPe": 0, "Leapswitch": 0}) is None          # neither
    assert published.brand_of({"CloudPe": 10, "Leapswitch": 6}) is None         # both
    assert published.named_brand("What does the Cloud Pe SLA give?") == "CloudPe"
    assert published.named_brand("Compare CloudPe and Leapswitch credits") is None
    assert set(published.source_types("CloudPe")) == {
        p.source_type for p in published.POLICIES if p.brand == "CloudPe"}
    assert published.source_types() == published.SOURCE_TYPES


def _published(db):
    constitution.ingest(db)
    published.ingest(db, SLA_LS, LEAPSWITCH, read_on=DAY)
    published.ingest(db, SLA_CP, CLOUDPE, read_on=DAY)


def test_the_search_keeps_one_brands_policies_when_asked(db, material):
    _published(db)
    query = "service credit support request sixty days"
    kinds = {h.source_type for h in constitution.search(
        db, query=query, permissions=PERMS, embed_query=lambda q: None)}
    assert {SLA_LS.source_type, SLA_CP.source_type} <= kinds        # unscoped: both
    scoped = {h.source_type for h in constitution.search(
        db, query=query, permissions=PERMS, embed_query=lambda q: None, brand="CloudPe")}
    assert SLA_CP.source_type in scoped and SLA_LS.source_type not in scoped


def _document(db, user, storage, words: str):
    contract = M.Contract(owner_id=user.id, name="SLA", contract_type="SLA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    version = ingest_document(db, storage, contract_id=contract.id, uploaded_by=user.id,
                              data=build_docx([words]), filename="sla.docx",
                              declared_mime=DOCX_MIME).document_version
    indexing.index_document_version(db, version.id)
    return version


def test_a_cloudpe_document_is_answered_with_cloudpe_policies_only(
        db, user, tmp_path, material):
    from legalmind.ingestion.storage import LocalFilesystemStorage
    _published(db)
    storage = LocalFilesystemStorage(str(tmp_path / "objects"))
    cloudpe = _document(db, user, storage, "1. CloudPe Service Level Agreement. CloudPe "
                        "is a brand operated by Leapswitch Networks. CloudPe customers "
                        "receive service credits as CloudPe sets out below.")
    plain = _document(db, user, storage, "1. Service credits are as set out below for "
                      "every service the provider offers under this agreement.")
    assert published.document_brand(db, cloudpe.id) == "CloudPe"
    assert published.document_brand(db, plain.id) is None
    question = "What service credit applies at 99.2% uptime?"
    plan = query_plan.plan(question, has_document=True, prior=(), instruction=question)
    route = routing.RoutePlan(comparison=False, domains=(routing.Domain.POSITIONS,),
                              statute_shaped=False)

    def published_kinds(version):
        pool = retrieval.candidates(db, plan, route, permissions=PERMS,
                                    document_version_id=version.id, rescue=False,
                                    embed_query=lambda q: None)
        return {c.ref.split(":")[1] for c in pool.by_domain.get(retrieval.CONSTITUTION, [])
                if c.ref.startswith("PUB:")}
    assert published_kinds(cloudpe) == {SLA_CP.source_type}      # never Leapswitch's
    assert SLA_LS.source_type in published_kinds(plain)           # no brand: both, as before
