"""UX Batch 1 slice C — points truth (2026-11-11).

(d) "In our favour" is the evaluator's recorded rule outcome (AM-239 r1, AM-303) and
nothing else: a DEVIATION the approved favourable rule accepted. A MATCH is not, and an
UNABLE_TO_EVALUATE lower cap (AM-301, owner decision 7) is not. Ask reads the same word;
the report lists favour points in their own section. (g) A CATEGORICAL standard saved
without its allowed values is refused at save. (b) A Points passage names a repeated
clause number by its own words. Leftover: a deleted sub-clause sits under its parent's
group on the returned copy. Synthetic structure only — no legal conclusion (rule 21).
"""

from __future__ import annotations

import uuid

from legalmind.analysis import negotiation as N
from legalmind.api.export_render import build_export_model
from legalmind.api.serializers import serialize_finding
from legalmind.assist.service import _findings_for_standards
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.mapping.engine import Clause
from legalmind.security import permissions as P
from tests.conftest import make_evaluation, make_finding, sign_in
from tests.test_api_resources import V1, _legal_admin

C, R = E.FindingClassification, E.RuleOutcome


def _point(db, review, rv, cls, e_cls, outcome):
    """One Finding on its own requirement version (one Finding per version a Review)."""
    rv = M.RequirementVersion(requirement_id=rv.requirement_id,
                              version_number=uuid.uuid4().int % 10**6,
                              name="Point", evaluator_type=rv.evaluator_type,
                              created_by=review.created_by)
    db.add(rv)
    db.flush()
    finding = make_finding(db, review, rv, classification=cls)
    make_evaluation(db, finding, classification=e_cls, rule_outcome=outcome)
    return finding


def test_in_our_favour_is_the_recorded_rule_outcome_only(db, review, requirement_version):
    favour = _point(db, review, requirement_version, C.DEVIATION, C.DEVIATION, R.ACCEPTABLE)
    match = _point(db, review, requirement_version, C.MATCH, C.MATCH, R.ACCEPTABLE)
    lower_cap = _point(db, review, requirement_version, C.UNABLE_TO_EVALUATE,
                       C.UNABLE_TO_EVALUATE, R.ACCEPTABLE)
    against = _point(db, review, requirement_version, C.DEVIATION, C.DEVIATION,
                     R.UNACCEPTABLE)
    said = {f.id: serialize_finding(db, f, legal_position=True)
            for f in (favour, match, lower_cap, against)}
    assert said[favour.id]["in_our_favour"] is True
    assert said[favour.id]["user_status"] == "ACCEPTABLE"
    assert [said[f.id]["in_our_favour"] for f in (match, lower_cap, against)] == \
        [False, False, False]
    assert said[lower_cap.id]["user_status"] == "NEEDS_DECISION"    # decision 7 stays open


def test_ask_reads_the_rule_outcome_too(db, review, requirement_version):
    _point(db, review, requirement_version, C.DEVIATION, C.DEVIATION, R.ACCEPTABLE)
    code = db.get(M.Requirement, requirement_version.requirement_id).code
    found = _findings_for_standards(db, review.document_version_id, {code},
                                    frozenset({P.FINDING_VIEW}))
    assert found[code]["user_status"] == "ACCEPTABLE"


def test_the_report_lists_favour_points_apart_from_matches():
    def point(n, favour):
        return {"id": f"f{n}", "requirement": {"code": f"R-{n}", "name": f"Point {n}"},
                "user_status": "ACCEPTABLE", "in_our_favour": favour, "evidence": []}
    findings = [point(1, False), point(2, True), point(3, False)]
    blocks = build_export_model(
        contract={"name": "C"}, version={}, review={},
        report={"user_status_counts": {"ACCEPTABLE": 3}}, findings=findings,
        exported_at="2026-11-11T10:00:00")
    heads = [b.text for b in blocks if b.kind == "h2"]
    assert "Matches our standards (2)" in heads and "In our favour (1)" in heads
    assert any(b.text.endswith("on 3 points: 2 match; 1 in our favour.") for b in blocks)


def _categorical(api, db):
    admin = _legal_admin(db)
    sign_in(api, db, admin)
    rid = api.post(f"{V1}/requirements", json={"code": f"CAT-{uuid.uuid4().hex[:4]}"}) \
        .json()["data"]["id"]
    standard = {"document_type": "MSA", "allowed_values": ["A"],
                "recognised_values": {"A": ["alpha"]}}
    made = api.post(f"{V1}/requirements/{rid}/versions", json={
        "name": "Seat", "evaluator_type": "CATEGORICAL", "company_standard": standard,
        "mapping_rules": {"exact_phrase": ["seat"], "confirm_threshold": 5},
        "evaluation_rules": {}})
    assert made.status_code == 201, made.text
    return rid, standard


def test_a_categorical_standard_without_allowed_values_is_refused_at_save(api, db, seeded):
    rid, standard = _categorical(api, db)
    url = f"{V1}/requirements/{rid}/standard"
    dropped = {k: v for k, v in standard.items() if k != "allowed_values"}
    assert api.post(url, json={"company_standard": dropped, "reason": "x"}).status_code == 422
    kept = api.post(url, json={"company_standard": standard, "reason": "unchanged"})
    assert kept.status_code == 201
    assert kept.json()["data"]["versions"][-1]["company_standard"]["allowed_values"] == ["A"]


def _clauses(rows):
    return [Clause(uuid.uuid4(), text, number, None, 1, heading)
            for text, number, heading in rows]


def test_a_repeated_number_names_its_passages_and_a_unique_one_does_not():
    rows = _clauses([("2. Fees are invoiced.", "2", False), ("3. Term.", "3", False),
                     ("2. Early exit is restricted.", "2", False)])
    names = N.unit_names(rows)
    assert names == {str(rows[0].evidence_id): "Fees are invoiced",
                     str(rows[2].evidence_id): "Early exit is restricted"}


def test_a_deleted_sub_clause_groups_under_its_parents_twin():
    """Slice A re-verify LOW: the parent's words changed and its 2.2 was deleted — the
    deleted row (our side) and the reworded parent (theirs) are one group, keyed by the
    unit, never by its words."""
    old = N._units(_clauses([("2. Fees are invoiced.", "2", False),
                             ("2.1 Invoices monthly.", "2.1", False),
                             ("2.2 Late fee applies.", "2.2", False),
                             ("3. Term.", "3", False), ("2. Exit.", "2", False)]))
    new = N._units(_clauses([("2. Fees are billed.", "2", False),
                             ("2.1 Invoices monthly.", "2.1", False),
                             ("3. Term.", "3", False), ("2. Exit.", "2", False)]))
    twin = {i: j for i, j, _ in N._align(old, new) if i is not None and j is not None}
    assert twin[0] == 0                                    # the reworded parent pairs
    deleted = N.row_clause(old[2], None, old, new, twin)
    parent = N.row_clause(old[0], new[0], old, new, twin)
    assert deleted["group"]["key"] == parent["group"]["key"] == new[0]["evidence_ids"][0]
    assert deleted["group"]["name"] == "Fees are billed"
    # a deleted row whose parent went too keeps its own unit
    alone = N.row_clause(old[2], None, old, new, {})
    assert alone["group"]["key"] == old[0]["evidence_ids"][0]
