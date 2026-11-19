"""Batch 2 "cited passage" (AB-217) — the lawyer's view sits on what a point quotes.

* F6 (AM-322 r17): the rows `_whole_sections` adds around a cited clause are SUPPORTING;
  the cited rows stay PRIMARY; CONFLICTING is never touched; the finding-level roll-up
  lets a cited row win; a point is placed on a cited row (an old all-PRIMARY Review
  reads as before).
* F8 (AM-395 rider): our counter-wording is the cited clauses' own text, never a heading.
* F4 (AM-241): our wrong entity is seen in a returned copy that deleted it.
* F7 (R-3 rider): another family's stating clause that states no figure of its own does
  not keep that family's figure alive on the declared family's clauses.
Synthetic wording only (locked 54.6, rule 21); every standard is named by code.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import uuid4

import pytest
from sqlalchemy import select, update

from legalmind.analysis import consistency
from legalmind.analysis import service as S
from legalmind.api import angles
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.mapping.engine import Clause
from legalmind.mapping.service import load_clauses
from tests.legal_regression.test_legal_regression import _findings, _review
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _contract,
    _docx,
    _ingest,
    _mark,
    _run,
    owner,
)

STANDARDS = Path(__file__).resolve().parents[1] / "config" / "company_standards"
DR = "DATA-RESIDENCY-MSA-001"
FILLER = ["1. Services", "1.1 The Provider shall provide the Services described in the "
          "Order.", "2. Fees", "2.1 The fees are stated in the Order."]
SECTION = ["3. Data Protection",
           "3.1 Data residency for India-designated services is maintained within India.",
           "3.2 The Customer is responsible for the lawful collection of the data it "
           "uploads to the Services.",
           "4. Term", "4.1 This Agreement runs for one year from the Effective Date."]


def _relations(db, review, code=DR) -> dict[str, set[str]]:
    """section number -> relationship types, finding level and evaluation level."""
    out: dict[str, set[str]] = {}
    finding = next(f for c, f in db.execute(
        select(M.Requirement.code, M.Finding)
        .join(M.RequirementVersion, M.RequirementVersion.id == M.Finding.requirement_version_id)
        .join(M.Requirement, M.Requirement.id == M.RequirementVersion.requirement_id)
        .where(M.Finding.review_id == review.id)) if c == code)
    for model, key in ((M.FindingEvidence, M.FindingEvidence.finding_id == finding.id),
                       (M.EvaluationEvidence, M.EvaluationEvidence.evaluation_id.in_(
                           select(M.Evaluation.id).where(
                               M.Evaluation.finding_id == finding.id)))):
        for number, rel in db.execute(select(M.DocumentEvidence.section_number,
                                             model.relationship_type)
                                      .join(model, model.evidence_id == M.DocumentEvidence.id)
                                      .where(key)):
            out.setdefault(str(number), set()).add(E.EvidenceRelationshipType(rel).value)
    return out


def _finding_level(db, review) -> dict[str, str]:
    return {str(n): E.EvidenceRelationshipType(r).value for n, r in db.execute(
        select(M.DocumentEvidence.section_number, M.FindingEvidence.relationship_type)
        .join(M.FindingEvidence, M.FindingEvidence.evidence_id == M.DocumentEvidence.id)
        .join(M.Finding, M.Finding.id == M.FindingEvidence.finding_id)
        .where(M.Finding.review_id == review.id))}


def _where(db, review, code=DR):
    got = angles.review_angles(db, review, legal_position=True)["legal"]["items"]
    return next(i["where"] for i in got if i["requirement_code"] == code)


# ------------------------------------------------------------------------------- F6
def test_widened_rows_are_supporting_and_the_point_sits_on_the_cited_clause(build, db):
    review, _ = _review(build, db, [DR], [*FILLER, *SECTION], kind="MSA")
    rel = _relations(db, review)
    assert rel["3.1"] == {"PRIMARY"}
    assert rel["3"] == rel["3.2"] == {"SUPPORTING"}       # added by AM-322 r12
    assert "4.1" not in rel                                # the section still ends at 4
    assert _where(db, review).startswith("Clause 3.1")


def test_the_same_document_twice_reads_the_same_relationships(build, db):
    first, _ = _review(build, db, [DR], [*FILLER, *SECTION], kind="MSA")
    again = M.Review(contract_id=first.contract_id, document_version_id=first.document_version_id,
                     configuration_snapshot_id=first.configuration_snapshot_id,
                     status=E.ReviewStatus.DRAFT, created_by=first.created_by)
    db.add(again); db.flush()
    S.run_analysis(db, again)
    assert _relations(db, again) == _relations(db, first)


def test_our_own_wording_path_is_not_widened(build, db):
    quote = json.loads((STANDARDS / f"{DR}.json").read_text())["configuration"][
        "own_wording_match"]
    review, _ = _review(build, db, [DR], [*FILLER, "11. Data Protection",
                                          "11.5 Cross-Border Data Transfers: " + quote,
                                          "11.6 The Customer keeps its own records."],
                        kind="MSA")
    assert _findings(db, review)[DR]["classification"] == "MATCH"
    assert _relations(db, review) == {"11.5": {"PRIMARY"}}


def test_conflicting_is_never_touched_and_a_cited_row_wins_the_roll_up(build, db,
                                                                       monkeypatch):
    real = S.evaluate

    def twice(evaluator_input):
        # scope A writes every row CONFLICTING first; scope C is the real reading
        # (3.1 PRIMARY, widened 3 and 3.2 SUPPORTING)
        out = real(evaluator_input)
        one = out.evaluations[0]
        return replace(out, evaluations=(
            replace(one, scope_key="A", evidence_relationships=dict.fromkeys(
                one.evidence_relationships, "CONFLICTING")),
            replace(one, scope_key="C")))

    monkeypatch.setattr(S, "evaluate", twice)
    review, _ = _review(build, db, [DR], [*FILLER, *SECTION], kind="MSA")
    by_scope: dict[str, dict[str, str]] = {}
    for scope, number, rel in db.execute(
            select(M.Evaluation.scope_key, M.DocumentEvidence.section_number,
                   M.EvaluationEvidence.relationship_type)
            .join(M.EvaluationEvidence, M.EvaluationEvidence.evaluation_id == M.Evaluation.id)
            .join(M.DocumentEvidence, M.DocumentEvidence.id == M.EvaluationEvidence.evidence_id)
            .join(M.Finding, M.Finding.id == M.Evaluation.finding_id)
            .where(M.Finding.review_id == review.id)):
        by_scope.setdefault(scope, {})[str(number)] = E.EvidenceRelationshipType(rel).value
    assert set(by_scope["A"].values()) == {"CONFLICTING"}
    assert by_scope["C"] == {"3": "SUPPORTING", "3.1": "PRIMARY", "3.2": "SUPPORTING"}
    # the roll-up keeps CONFLICTING (first written), never lowered to SUPPORTING
    assert _finding_level(db, review) == dict.fromkeys(("3", "3.1", "3.2"), "CONFLICTING")


def test_a_supporting_row_is_raised_when_a_later_scope_cites_it(build, db, monkeypatch):
    real = S.persist_evaluation

    def widened_first(db, *, output, **kw):
        # as persisted: scope A the reading (3 and 3.2 SUPPORTING), then scope B
        # citing every row
        one = output.evaluations[0]
        assert "SUPPORTING" in one.evidence_relationships.values()
        return real(db, output=replace(output, evaluations=(
            replace(one, scope_key="A"),
            replace(one, scope_key="B", evidence_relationships=dict.fromkeys(
                one.evidence_relationships, "PRIMARY")))), **kw)

    monkeypatch.setattr(S, "persist_evaluation", widened_first)
    review, _ = _review(build, db, [DR], [*FILLER, *SECTION], kind="MSA")
    assert _finding_level(db, review) == dict.fromkeys(("3", "3.1", "3.2"), "PRIMARY")


def test_an_old_review_that_cites_every_row_reads_as_before(build, db):
    review, _ = _review(build, db, [DR], [*FILLER, *SECTION], kind="MSA")
    db.execute(update(M.FindingEvidence).where(M.FindingEvidence.finding_id.in_(
        select(M.Finding.id).where(M.Finding.review_id == review.id))).values(
        relationship_type=E.EvidenceRelationshipType.PRIMARY))
    db.expire_all()
    # before r17 every row was PRIMARY: the first row read is the section's heading
    assert _where(db, review).startswith("Clause 3,") or _where(db, review) == "Clause 3"


def _pair(build, db, tmp_path, theirs_section):
    from tests.test_hard_test_fixes import _ratified
    if db.scalar(select(M.Requirement).where(M.Requirement.code == DR)) is None:
        _ratified(build, DR)
    c = M.Contract(owner_id=build.owner.id, name="Pair", contract_type="MSA",
                   status=E.ContractStatus.ACTIVE)
    db.add(c); db.flush()
    reviews = []
    for name, paper in (("ours", SECTION), ("theirs", theirs_section)):
        version = _ingest(db, tmp_path, c, _docx(*FILLER, *paper), f"{name}.docx")
        review = M.Review(contract_id=c.id, document_version_id=version.id,
                          configuration_snapshot_id=build.snapshot.id,
                          status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
        db.add(review); db.flush()
        S.run_analysis(db, review)
        reviews.append(review)
    return reviews[1]


def test_a_changed_point_moves_only_to_a_changed_clause_it_cites(build, db, tmp_path):
    # AB-213 D13 kept for the cited rows: only a widened row (3.2) changed → the point
    # stays on what it quotes (3.1), never on the supporting row
    widened_only = [*SECTION[:2], SECTION[2].replace("lawful", "fair"), *SECTION[3:]]
    review = _pair(build, db, tmp_path, widened_only)
    assert _where(db, review).startswith("Clause 3.1")
    # and it is not "the client changed" it: origin reads the same cited rows (r17)
    item = next(i for i in angles.review_angles(db, review, legal_position=True)[
        "legal"]["items"] if i["requirement_code"] == DR)
    assert item.get("origin") == "ALREADY_OURS"
    edited = [*SECTION[:1], SECTION[1].replace("maintained", "kept"), *SECTION[2:]]
    item = next(i for i in angles.review_angles(db, _pair(build, db, tmp_path, edited),
                                                legal_position=True)["legal"]["items"]
                if i["requirement_code"] == DR)
    assert item.get("origin") == "CLIENT_CHANGED" and item["where"].startswith("Clause 3.1")


# ------------------------------------------------------------------------------- F8
def _clause(text, number=None, heading=False):
    return Clause(evidence_id=uuid4(), content=text, section_number=number,
                  is_heading=heading)


def _paper(fees_1: str, fees_2: str) -> list[Clause]:
    return [_clause("6. SERVICES", "6", True),
            _clause("6.1 The Provider shall provide the Services described in the Order.",
                    "6.1"),
            _clause("7. FEES", "7", True),
            _clause(f"7.1 {fees_1}", "7.1"),
            _clause(f"7.2 {fees_2}", "7.2"),
            _clause("7.3 Late payments carry no interest for the first week.", "7.3"),
            _clause("8. TERM", "8", True),
            _clause("8.1 This Agreement runs for one year from the Effective Date.", "8.1")]


def _proposal(ours, theirs, cited_numbers):
    ids = [str(c.evidence_id) for c in theirs if c.section_number in cited_numbers]
    row = {"finding": NS(id="f"), "evidence_ids": ids, "cited_ids": ids}
    return angles._our_clauses(NS(version_number=1), ours, theirs, [row], "MSA").get("f")


def test_our_counter_wording_is_the_cited_clauses_not_their_heading():
    ours = _paper("Fees are invoiced monthly in advance by the Provider.",
                  "Each invoice is payable within thirty days of its date.")
    theirs = _paper("Fees are invoiced monthly in arrears by the Provider.",
                    "Each invoice is payable within sixty days of its date.")
    got = _proposal(ours, theirs, {"7", "7.1", "7.2"})
    assert got is not None and got["kind"] == "OUR_CLAUSE"
    assert got["text"].startswith("7.1 Fees are invoiced monthly in advance")
    assert "7.2 Each invoice is payable within thirty days" in got["text"]
    assert "7. FEES" not in got["text"] and "7.3" not in got["text"]      # not the section
    assert got["section"] == "7.1" and got["label"].endswith("clauses 7.1, 7.2")


def test_a_cited_clause_brings_its_own_sub_clauses_and_a_heading_alone_brings_nothing():
    ours = [_clause("16. INDEMNITY", "16", True),
            _clause("16.1 The Customer shall indemnify the Provider against:", "16.1"),
            _clause("16.1.1 claims arising from the Customer's content; and", "16.1.1"),
            _clause("16.1.2 claims arising from the Customer's unlawful use.", "16.1.2"),
            _clause("16.2 The indemnified party shall notify the other promptly.", "16.2"),
            _clause("17. TERM", "17", True)]
    theirs = [replace(c, evidence_id=uuid4()) for c in ours]
    got = _proposal(ours, theirs, {"16", "16.1"})
    assert got is not None and "16.1.2 claims arising" in got["text"]
    assert "16.2" not in got["text"] and "16. INDEMNITY" not in got["text"]
    assert got["label"].endswith("clause 16.1")
    assert _proposal(ours, theirs, {"16"}) is None       # the next source is quoted


# ------------------------------------------------------------------------------- F4
_SAMPLE = "Leapswitch Sample Services Private Limited"


def test_our_wrong_entity_deleted_by_the_client_is_still_seen(db, owner, tmp_path):
    c = _contract(db, owner)
    theirs = _ingest(db, tmp_path, c, _docx(
        "1. This Agreement is made between LeapSwitch Networks Private Limited and the "
        "Customer.",
        "IN WITNESS WHEREOF the Parties have signed this Agreement.",
        [_run("For "), _mark("del", _SAMPLE, 1),
         _mark("ins", "[the correct contracting entity]", 2)]), "theirs.docx")
    observed = consistency.observe(load_clauses(db, theirs.id), "MSA")["structural"]
    entity = [o for o in observed if o["kind"] == consistency.OUR_ENTITY]
    assert len(entity) == 1 and _SAMPLE in entity[0]["text"]
    assert "in the version we sent" in entity[0]["text"]


def test_our_right_entity_is_never_an_observation_before_or_after_markup():
    right = Clause(evidence_id=uuid4(), content="For [the contracting entity]",
                   marks={"changes": [{"type": "del"}], "comments": [],
                          "original": "For LeapSwitch Networks Pvt. Ltd."})
    assert not [o for o in consistency.observe([right])["structural"]
                if o["kind"] == consistency.OUR_ENTITY]
    wrong_now = Clause(evidence_id=uuid4(), content=f"For {_SAMPLE}")
    assert [o["text"] for o in consistency.observe([wrong_now])["structural"]
            if o["kind"] == consistency.OUR_ENTITY] == [
        f"Our company is named “{_SAMPLE}”, which is not the contracting entity."]


# ------------------------------------------------------------------------------- F7
EXIT_CODES = ["CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001", "TERM-NOTICE-NDA-001"]


def test_an_nda_notice_stated_without_a_figure_does_not_reread_the_msas_figures(build,
                                                                               db):
    # the returned copy's 7.6 says "terminated … notice" with no period: the NDA notice
    # read the MSA's cure figure as its own and disagreed with itself (CONFLICT)
    review, run = _review(build, db, EXIT_CODES, [
        "7. Term and Termination",
        "7.4 This Agreement may be terminated by either party if the other fails to cure "
        "a material breach within fifteen (15) days of written notice.",
        "7.6 Where this Agreement is terminated, the Customer shall give notice of when "
        "it will remove its equipment from the premises."], kind="MSA")
    assert "TERM-NOTICE-NDA-001" not in _findings(db, review)
    reason = next(c for c in run.applicability if c["code"] == "TERM-NOTICE-NDA-001")
    assert reason["outcome"] == "SAME_TOPIC" and "(R-3)" in reason["reason"]


def test_an_nda_notice_that_states_its_own_figure_elsewhere_is_still_measured(build, db):
    # the opposite case: its own words state a period no MSA position reads
    review, run = _review(build, db, EXIT_CODES, [
        "7. Term and Termination",
        "7.4 This Agreement may be terminated by either party if the other fails to cure "
        "a material breach within fifteen (15) days of written notice.",
        "9. Confidentiality",
        "9.1 The confidentiality undertakings end unless earlier terminated by either "
        "party in writing with ninety (90) days' notice."], kind="MSA")
    assert next(c for c in run.applicability
                if c["code"] == "TERM-NOTICE-NDA-001")["outcome"] == "APPLIED"


_TERM_HEADS = ["7. Fees", "7.1 Fees are stated in the Order.", "9. Term"]
_CURE = ("7.4 This Agreement may be terminated by either party if the other fails to cure "
         "a material breach within fifteen (15) days of written notice.")


@pytest.mark.parametrize("heads, notice, cls, cited", [
    # verifier round 1: a period the NDA's configured DAYS reading cannot read is still
    # a figure in its own words — never dropped as "states no figure" (rule 15)
    (_TERM_HEADS,
     "9.1 These undertakings may be terminated by the Customer on two weeks' written "
     "notice.", "UNABLE_TO_EVALUATE", {"9.1"}),
    (_TERM_HEADS,
     "9.1 These undertakings may be terminated by the Customer on one month's written "
     "notice.", "UNABLE_TO_EVALUATE", {"9.1"}),
    (["7. Term and Termination", _CURE, "9. Confidentiality"],
     "9.1 The confidentiality undertakings end unless earlier terminated by either party "
     "in writing with two weeks' notice.", "CONFLICT", {"7.4", "9.1"}),
    # verifier round 2: digits in brackets after the words, and a quarter
    (_TERM_HEADS, "9.1 These undertakings may be terminated by the Customer on one hundred "
     "(100) days' written notice.", "DEVIATION", {"9.1"}),
    (_TERM_HEADS, "9.1 These undertakings may be terminated by the Customer on one "
     "calendar quarter's written notice.", "UNABLE_TO_EVALUATE", {"9.1"}),
    # no figure, but no declared-family position reads 9.1: kept for a person (rule 15)
    (_TERM_HEADS, "9.1 These undertakings may be terminated by the Customer on notice "
     "given within a reasonable time.", "UNABLE_TO_EVALUATE", {"9.1"}),
    (_TERM_HEADS, "9.1 These undertakings may be terminated by the Customer on the notice "
     "stated in clause 7.1 of this Agreement.", "UNABLE_TO_EVALUATE", {"9.1"}),
])
def test_a_period_in_words_is_a_figure_of_its_own(build, db, heads, notice, cls, cited):
    review, _ = _review(build, db, ["CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001",
                                    "DATA-PURGE-MSA-001", "TERM-NOTICE-NDA-001"],
                        [*heads, notice], kind="MSA")
    found = _findings(db, review)["TERM-NOTICE-NDA-001"]
    assert found["classification"] == cls
    assert {s for s, _ in found["cited"]} == cited


@pytest.mark.parametrize("code, paper, where, quote", [
    # verifier round 1: a short cited title places the point; the quote is the first
    # sentence the point read
    (DR, ["3. Data Protection", "3.1 Data residency.", "3.2 Customer Data is stored only "
          "in data centres located in India and is never moved abroad.", *SECTION[3:]],
     "Clause 3.1", "3.2 Customer Data is stored only"),
    ("SUB-PROCESSORS-MSA-001", ["5. Sub-processors", "5.1 Sub-processors.",
                                "5.2 The Provider may engage third parties to process "
                                "Customer Data on giving the Customer prior written "
                                "notice.", "6. Term", "6.1 This Agreement runs for one "
                                "year from the Effective Date."],
     "Clause 5", "5.2 The Provider may engage third parties"),
])
def test_a_short_cited_title_places_the_point_and_a_sentence_is_quoted(build, db, code,
                                                                      paper, where, quote):
    review, _ = _review(build, db, [code], [*FILLER, *paper], kind="MSA")
    got = angles.review_angles(db, review, legal_position=True)["legal"]["items"]
    item = next(i for i in got if i["requirement_code"] == code)
    assert item["where"].startswith(where + ",") or item["where"] == where
    assert item["case"]["contract"]["quote"].startswith(quote)


def test_a_figureless_notice_is_dropped_only_while_the_msa_positions_still_cite_it(build,
                                                                                  db):
    # verifier round 2 (kw_2weeks_nocure): the NDA notice confirms only 7.1, which
    # states no figure; 7.1 stays in front of a person through the MSA's own positions
    review, run = _review(build, db, ["CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001",
                                      "DATA-PURGE-MSA-001", "TERM-NOTICE-NDA-001"], [
        "7. Term and Termination", "7.1 This Agreement may be terminated by either party "
        "for convenience.", "9. Confidentiality", "9.1 These undertakings may be "
        "terminated by the Customer on two weeks' written notice."], kind="MSA")
    found = _findings(db, review)
    assert "TERM-NOTICE-NDA-001" not in found
    assert next(c for c in run.applicability if c["code"] == "TERM-NOTICE-NDA-001")[
        "outcome"] == "SAME_TOPIC"
    assert all("7.1" in {s for s, _ in found[c]["cited"]} for c in (
        "CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001", "DATA-PURGE-MSA-001"))
