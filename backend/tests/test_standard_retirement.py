"""Retirement — AM-65 (owner, 2026-09-14).

Seven standards the current Constitution does not define are withdrawn from
active review. The owner's four requirements, each asserted here:

    do not use them in active reviews      -> never enters a new snapshot
    do not show them as approved           -> the API says `retired`
    preserve their historical record       -> old Findings still resolve
    mark them clearly                      -> the marker is in the file

The mechanism is `Requirement.status = DEPRECATED`, the locked Step 29
configuration lifecycle value that has existed since the initial migration and
that publish already filters on. No migration, no new enum member, no deletion:
a deleted row would break every Finding that cites it (`serialize_finding`
resolves the requirement by version id and would emit nulls).
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from legalmind.api.serializers import serialize_finding
from legalmind.db import models as M
from legalmind.domain import enums as E
from legalmind.evaluation.constitution_block import (
    RETIRED_MARKER,
    is_retired,
    retired_block_error,
)
from legalmind.evaluation.corpus import RATIFIED_STANDARDS_DIR
from tests.conftest import make_evaluation, make_finding, make_user

PAYLOADS = {p.stem: json.loads(p.read_text())
            for p in RATIFIED_STANDARDS_DIR.glob("*.json")}
RETIRED = sorted(c for c, d in PAYLOADS.items() if is_retired(d))
ACTIVE = sorted(c for c, d in PAYLOADS.items() if not is_retired(d))


def _import(db):
    from tools.import_ratified_standards import import_standards
    actor = make_user(db)
    import_standards(db, actor_email=actor.email)
    db.flush()
    return actor


def test_the_importer_deprecates_every_retired_standard(db):
    _import(db)
    for code in RETIRED:
        req = db.execute(select(M.Requirement)
                         .where(M.Requirement.code == code)).scalars().one()
        assert req.status is E.ConfigStatus.DEPRECATED, code
    # and leaves the rest exactly as it found them
    for code in ACTIVE:
        req = db.execute(select(M.Requirement)
                         .where(M.Requirement.code == code)).scalars().one()
        assert req.status is not E.ConfigStatus.DEPRECATED, code


def test_a_retired_standard_keeps_its_versions_so_history_survives(db):
    """Its Requirement, versions and company standard rows are all still there —
    retirement withdraws it from future reviews, it does not erase the past."""
    _import(db)
    for code in RETIRED:
        req = db.execute(select(M.Requirement)
                         .where(M.Requirement.code == code)).scalars().one()
        versions = db.execute(select(M.RequirementVersion)
                              .where(M.RequirementVersion.requirement_id == req.id)).scalars().all()
        assert versions, code
        standards = db.execute(
            select(M.CompanyStandardVersion)
            .where(M.CompanyStandardVersion.requirement_version_id.in_([v.id for v in versions]))
        ).scalars().all()
        assert standards, code


def test_a_retired_requirement_never_enters_a_new_snapshot(api, db, seeded):
    """The rule the owner asked for: not used in active reviews."""
    import legalmind.security.permissions as P
    from tests.conftest import grant_role, sign_in
    admin = make_user(db)
    grant_role(db, admin, P.ROLE_DEPARTMENT_LEAD)
    sign_in(api, db, admin)
    _import(db)

    response = api.post("/api/v1/configuration/publish",
                        json={"requirement_codes": ACTIVE})
    assert response.status_code == 201, response.text
    snapshot_id = response.json()["data"]["id"]

    pinned = db.execute(
        select(M.Requirement.code)
        .join(M.RequirementVersion, M.RequirementVersion.requirement_id == M.Requirement.id)
        .join(M.ConfigurationSnapshotItem,
              M.ConfigurationSnapshotItem.requirement_version_id == M.RequirementVersion.id)
        .where(M.ConfigurationSnapshotItem.snapshot_id == snapshot_id)
    ).scalars().all()
    assert set(pinned) & set(RETIRED) == set()
    assert set(pinned) == set(ACTIVE)


def test_publishing_a_retired_code_is_refused_rather_than_reactivating_it(api, db, seeded):
    import legalmind.security.permissions as P
    from tests.conftest import grant_role, sign_in
    admin = make_user(db)
    grant_role(db, admin, P.ROLE_DEPARTMENT_LEAD)
    sign_in(api, db, admin)
    _import(db)

    refused = api.post("/api/v1/configuration/publish",
                       json={"requirement_codes": [RETIRED[0]]})
    assert refused.status_code == 422, refused.text
    assert "retired" in refused.text and "AM-65" in refused.text
    req = db.execute(select(M.Requirement)
                     .where(M.Requirement.code == RETIRED[0])).scalars().one()
    assert req.status is E.ConfigStatus.DEPRECATED


def test_a_finding_written_before_the_retirement_still_reads_and_says_retired(
        db, owner_and_finding):
    """Preserve the historical record — and do not show it as approved.

    The Finding's own rows are untouched (rule 17); `retired` is read from the
    requirement's CURRENT status, so a Finding whose snapshot predates the
    retirement still tells the reader the standard behind it was withdrawn.
    """
    finding, requirement = owner_and_finding
    before = serialize_finding(db, finding, legal_position=True)
    assert before["requirement"]["retired"] is False
    assert before["classification"]

    requirement.status = E.ConfigStatus.DEPRECATED
    db.flush()

    after = serialize_finding(db, finding, legal_position=True)
    assert after["requirement"]["retired"] is True
    # Nothing else moved: the legal record is the same record.
    assert after["classification"] == before["classification"]
    assert after["requirement"]["code"] == before["requirement"]["code"]
    assert after["evaluations"] == before["evaluations"]
    assert after["evidence"] == before["evidence"]


@pytest.fixture
def owner_and_finding(db, review, requirement_version):
    finding = make_finding(db, review, requirement_version)
    make_evaluation(db, finding)
    requirement = db.execute(
        select(M.Requirement)
        .where(M.Requirement.id == requirement_version.requirement_id)).scalars().one()
    return finding, requirement


def test_a_malformed_retirement_is_refused_at_import(tmp_path):
    """A retirement without its reason is not a record (rule 21's discipline)."""
    good = dict(PAYLOADS[RETIRED[0]])
    assert retired_block_error(good) is None

    for broken, expect in (
        ({**good, "retired": {**good["retired"], "marker": "retired"}}, "marker"),
        ({**good, "retired": {**good["retired"], "reason": ""}}, "reason"),
        ({**good, "retired": "yes"}, "not an object"),
    ):
        problem = retired_block_error(broken)
        assert problem and expect in problem, broken["retired"]


def test_the_marker_is_the_owners_exact_words():
    assert RETIRED_MARKER == "RETIRED — NOT PRESENT IN CURRENT CONSTITUTION"
    for code in RETIRED:
        assert PAYLOADS[code]["retired"]["marker"] == RETIRED_MARKER, code
