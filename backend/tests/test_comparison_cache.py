"""P2 "stop recalculating" (full-stack audit 2026-11-23). The pure part of a comparison
(BE-2/BE-3) and the template publish check's verdict (BE-9) are kept per process under a
hash of everything they read; findings, answers, decisions and routes are read live on
every call. Every text here is synthetic; none is a position (rule 21)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import event, select

from legalmind.analysis import negotiation
from legalmind.api import serializers
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.conftest import sign_in
from tests.test_deal_brief import _deal, _get
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    _changes,
    _contract,
    _first,
    _review,
    _url,
    owner,
)
from tests.test_version_comparison import _version


def _pair_of(db, c) -> tuple[M.DocumentVersion, M.DocumentVersion]:
    versions = sorted(db.scalars(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == c.id)), key=lambda v: v.version_number)
    return negotiation.our_previous(versions, versions[-1]), versions[-1]


def _builds(monkeypatch) -> list[int]:
    """Counts how often the pure part is built (a cache miss)."""
    made: list[int] = []
    core = negotiation._core

    def counted(*args, **kwargs):
        made.append(1)
        return core(*args, **kwargs)
    monkeypatch.setattr(negotiation, "_core", counted)
    return made


def test_the_same_inputs_give_byte_identical_output_with_and_without_the_cache(
        api, db, owner, tmp_path):
    """Rule 9 for the projection: cold (built now) and hot (kept) are byte-identical for
    a reader of positions and for one without — the kept part holds nothing a reader's
    permissions change (rule 18), so the second reader never sees the first one's view."""
    c, theirs, _, _ = _deal(api, db, owner, tmp_path)
    ours, _ = _pair_of(db, c)

    def listed(legal: bool, counting: bool = False) -> str:
        return json.dumps(negotiation.changes(db, c, ours, theirs, legal_position=legal,
                                              counting=counting), default=str)
    cold = {}
    for legal in (True, False):
        negotiation._CORE.clear()
        cold[legal] = listed(legal)
    negotiation._CORE.clear()
    hot = {legal: listed(legal) for legal in (True, False, True)}
    assert hot == cold and len(negotiation._CORE) == 2          # one core, one display
    # counting leaves out only the display-only parts
    counted = json.loads(listed(True, counting=True))
    full = json.loads(cold[True])
    assert "notes_for_legal" not in counted and "notes_for_legal" in full
    for row in full["changes"]:
        row.pop("lawyer")
    del full["notes_for_legal"]
    assert counted == full


def test_answers_reviews_and_decisions_are_read_live_on_a_hot_cache(
        api, db, owner, tmp_path, monkeypatch):
    c, theirs, review, lawyer = _deal(api, db, owner, tmp_path)
    sign_in(api, db, owner)
    first = _changes(api, c)
    made = _builds(monkeypatch)
    # an answer posted between two reads is on the second
    row = next(r for r in first["changes"] if r["route"] == negotiation.OWNER)
    assert api.post(_url(c, row["row_key"]), json=_first("accept_theirs")).status_code == 201
    second = {r["row_key"]: r for r in _changes(api, c)["changes"]}
    assert second[row["row_key"]]["answer"]["answer"] == "accept_theirs"
    assert _get(api, f"/contracts/{c.id}")["counts"]["changes_left"] \
        == sum(r["answer"] is None for r in second.values())
    # a new Review of the client's version: its Findings are the ones read
    held = next(r for r in first["changes"] if r["review"]["after"])
    db.add(M.Review(contract_id=c.id, document_version_id=theirs.id,
                    configuration_snapshot_id=review.configuration_snapshot_id,
                    status=E.ReviewStatus.ANALYSIS_COMPLETE, created_by=owner.id,
                    created_at=review.created_at.replace(year=review.created_at.year + 1)))
    db.flush()
    third = {r["row_key"]: r for r in _changes(api, c)["changes"]}
    assert held["review"]["after"] and third[held["row_key"]]["review"]["after"] == []
    assert made == []                                         # all from the kept part


def test_a_new_version_a_reprocess_or_a_config_publish_is_a_new_key(db, owner):
    c = _contract(db, owner)
    ours = _version(db, c, 1, [("9", "Liability", "9. Liability is capped at 12 months.")])
    theirs = _version(db, c, 2, [("9", "Liability", "9. Liability is capped at 3 months.")])

    def key(before, after) -> str:
        return negotiation._core_key(db, before, after, None, False,
                                     negotiation.load_clauses(db, before.id),
                                     negotiation.load_clauses(db, after.id))
    first = key(ours, theirs)
    assert key(ours, theirs) == first                          # the same inputs
    # a configuration publish
    db.add(M.ConfigurationSnapshot(snapshot_hash=uuid.uuid4().hex, created_by=owner.id,
                                   created_at=datetime.now(UTC) + timedelta(minutes=1)))
    db.flush()
    published_now = key(ours, theirs)
    assert published_now != first
    # a reprocess: a newer completed run of the client's version reads other words
    run = M.DocumentProcessingRun(
        document_version_id=theirs.id, run_type=E.ProcessingRunType.PARSE,
        status=E.ProcessingRunStatus.COMPLETED, processor_version="test",
        started_at=datetime.now(UTC))
    db.add(run)
    db.flush()
    db.add(M.DocumentEvidence(
        document_version_id=theirs.id, processing_run_id=run.id, page_number=1,
        section_number="9", section_title="Liability",
        content="9. Liability is capped at 6 months.",
        source_type=E.EvidenceSourceType.NATIVE_TEXT, start_offset=0, end_offset=10))
    db.flush()
    assert key(ours, theirs) != published_now
    [row] = negotiation.changes(db, c, ours, theirs, legal_position=True)["changes"]
    assert row["after"]["text"] == "9. Liability is capped at 6 months."
    # a new client version is another pair
    newest = _version(db, c, 3, [("9", "Liability", "9. Liability is capped at 6 months.")])
    assert key(ours, newest) != key(ours, theirs)


def test_a_change_list_issues_as_many_statements_for_nine_rows_as_for_three(
        api, db, owner):
    """BE-6: the pair's answers and the client's decisions are read once per list, not
    once per row."""
    def statements(n: int) -> int:
        c = _contract(db, owner)
        ours = _version(db, c, 1, [(str(k), "Fees", f"{k}. Fees are due in {k} days.")
                                   for k in range(1, n + 1)])
        theirs = _version(db, c, 2, [(str(k), "Fees", f"{k}. Fees are due in {k + 30} "
                                      "days.") for k in range(1, n + 1)])
        ours.doc_metadata = {"version_role": "COMPANY_DRAFT"}
        theirs.doc_metadata = {"version_role": "CLIENT_MODIFIED"}
        # every other row measured (an undecided deviation), the rest unmeasured
        _review(db, theirs, [(k, E.FindingClassification.DEVIATION,
                              E.RuleOutcome.UNACCEPTABLE) for k in range(0, n, 2)])
        _changes(api, c)                                          # warm: same path
        seen: list[str] = []

        def record(*args):
            seen.append(args[2])
        conn = db.connection()
        event.listen(conn, "before_cursor_execute", record)
        try:
            listed = _changes(api, c)
        finally:
            event.remove(conn, "before_cursor_execute", record)
        assert len(listed["changes"]) == n
        assert all(r["route"] == negotiation.HOLDER and not r["holder_accepted"]
                   for r in listed["changes"])
        return len(seen)
    assert statements(9) == statements(3)


def test_a_finding_list_read_ahead_is_the_finding_read_one_by_one(api, db, owner,
                                                                    tmp_path):
    """DB-7: the page's Findings read in one query per kind say exactly what each read
    alone says — escalation, Evaluations, requirement, Constitution, evidence, decision."""
    _, _, review, lawyer = _deal(api, db, owner, tmp_path)
    finding = db.scalars(select(M.Finding).where(M.Finding.review_id == review.id)).one()
    db.add(M.Escalation(finding_id=finding.id, raised_by=owner.id, reason="look again"))
    db.flush()
    rows = list(db.scalars(select(M.Finding).where(M.Finding.review_id == review.id)))
    ahead = serializers.read_ahead(db, rows)
    for legal in (True, False):
        one = [serializers.serialize_finding(db, f, legal_position=legal) for f in rows]
        page = [serializers.serialize_finding(db, f, legal_position=legal, ahead=ahead)
                for f in rows]
        assert json.dumps(page, default=str) == json.dumps(one, default=str)
    assert page[0]["escalated"] is True
