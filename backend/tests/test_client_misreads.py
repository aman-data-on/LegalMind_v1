"""Batch 6 "client misreads" (2026-11-20) — what a client's markup was misread as.

* Fix 2 (AM-322 r11 / 45D rider): a client's rewrite of a clause our version FOUND, in
  words the configured terms do not name, is UNRESOLVED on their clause, never MISSING —
  followed version by version by its text, never its number alone; a clause they deleted
  or replaced stays MISSING; only counterparty versions are guarded (round 2: D4–D7).
* Fix 3 (AM-381 r2 rider): TOO_BROAD records why — LeapSwitch gives an indemnity
  (OUR_INDEMNITY) or AM-154's breadth (BREADTH) — and says so; PRESENCE-v2.
* Fix 4 (AM-224 r1 rider): a deleted list item names its actor in its parent's lead-in.
* Fix 5 (AM-322 r12 rider): only a mapping that FOUND its clause (CONFIRMED) is widened to
  the whole section; a weak UNRESOLVED cites its own scored rows.
Synthetic wording only (locked 54.6, rule 21); every standard is named by code.
"""
from __future__ import annotations

import re
from contextlib import contextmanager

import pytest
from sqlalchemy import select

from legalmind.analysis import negotiation
from legalmind.analysis import service as S
from legalmind.api import angles
from legalmind.db import models as M
from legalmind.domain import enums as E
from tests.legal_regression.test_legal_regression import _findings
from tests.test_analysis import build, storage  # noqa: F401 — fixtures
from tests.test_hard_test_fixes import _ratified
from tests.test_negotiation import (  # noqa: F401 — `owner` is a fixture
    W,
    _docx,
    _ingest,
    _mark,
    _run,
    owner,
)

DR = "DATA-RESIDENCY-MSA-001"
FILLER = ["1. Services", "1.1 The Provider shall provide the Services described in the "
          "Order.", "2. Fees", "2.1 The fees are stated in the Order."]
OURS = [*FILLER, "9. Data Protection",
        "9.3 Cross-Border Data Transfers: If Personal Data is transferred outside India, "
        "the Provider shall ensure the transfer is lawful.",
        "9.4 The Customer is responsible for the data it uploads."]
REWRITE = "9.3 The Provider shall keep all customer records on servers located in India " \
          "and shall not move them abroad without consent."


def _round(build, db, tmp_path, *versions: tuple[str, list[str]], code: str = DR):
    """One contract, its versions in order (name → role, as `_ingest` declares it), and
    a Review of the last; returns (review, run)."""
    _ratified(build, code)
    contract = M.Contract(owner_id=build.owner.id, name="Lineage", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    for name, paragraphs in versions:
        version = _ingest(db, tmp_path, contract, _docx(*paragraphs), f"{name}.docx")
    review = M.Review(contract_id=contract.id, document_version_id=version.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review)
    db.flush()
    return review, S.run_analysis(db, review)


def _lineage(run) -> list[str]:
    return [d for o in run.outcomes for d in o.diagnostics if d.startswith("lineage:")]


#: the client's rewrite of our 9.3 under tracked changes — the redline's own wording
#: before its marks is ours, so the change list pairs it by that text (D5)
TRACKED = [f'<w:r {W}><w:t xml:space="preserve">9.3 </w:t></w:r>',
           _mark("del", OURS[5].removeprefix("9.3 "), 1),
           _mark("ins", REWRITE.removeprefix("9.3 "), 2)]


def _ours_id(db, review, number=1):
    return db.execute(select(M.DocumentVersion.id).where(
        M.DocumentVersion.contract_id == review.contract_id,
        M.DocumentVersion.version_number == number)).scalar_one()


def test_a_client_rewrite_of_our_clause_is_read_never_missing(build, db, tmp_path):
    review, run = _round(build, db, tmp_path, ("ours", OURS),
                         ("theirs", [*OURS[:5], TRACKED, OURS[6]]))
    found = _findings(db, review)[DR]
    assert found["classification"] == "UNABLE_TO_EVALUATE"
    assert {s for s, _ in found["cited"]} == {"9.3"}
    outcome = next(o for o in run.outcomes if o.requirement_code == DR)
    assert outcome.mapping_state == "UNRESOLVED"
    [line] = _lineage(run)
    assert "clause 9.3 was found for this requirement" in line
    assert str(_ours_id(db, review)) in line
    # the same inputs again: the same reading (rule 9)
    again = M.Review(contract_id=review.contract_id,
                     document_version_id=review.document_version_id,
                     configuration_snapshot_id=review.configuration_snapshot_id,
                     status=E.ReviewStatus.DRAFT, created_by=review.created_by)
    db.add(again)
    db.flush()
    assert _lineage(S.run_analysis(db, again)) == [line]
    assert _findings(db, again)[DR] == found


def test_a_clause_the_client_deleted_is_still_missing(build, db, tmp_path):
    review, _ = _round(build, db, tmp_path, ("ours", OURS),
                       ("theirs", [*OURS[:5], OURS[6]]))
    assert _findings(db, review)[DR]["classification"] == "MISSING"


@pytest.mark.parametrize("other", [REWRITE, "9.3 The Customer shall pay a storage fee "
                                           "for archived backups."])
def test_an_unrelated_clause_under_our_number_is_still_missing(build, db, tmp_path,
                                                              other):
    """D5: sharing only the number is not lineage — an untracked clause on another
    subject at 9.3 (or a rewrite with no words in common) reads as our clause deleted."""
    review, run = _round(build, db, tmp_path, ("ours", OURS),
                         ("theirs", [*OURS[:5], other, OURS[6]]))
    assert _findings(db, review)[DR]["classification"] == "MISSING"
    assert not _lineage(run)


def test_our_own_version_is_never_touched(build, db, tmp_path):
    # our reply rewrites the clause itself: absence on our own paper stays MISSING
    review, run = _round(build, db, tmp_path, ("ours", OURS),
                         ("theirs", [*OURS[:5], TRACKED, OURS[6]]),
                         ("reply", [*OURS[:5], REWRITE, OURS[6]]))
    assert _findings(db, review)[DR]["classification"] == "MISSING"
    assert not _lineage(run)


def test_a_signed_copy_is_not_guarded(build, db, tmp_path):
    """D7: only a counterparty version (CLIENT_MODIFIED, or the counterparty's paper)."""
    _ratified(build, DR)
    contract = M.Contract(owner_id=build.owner.id, name="Signed", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    _ingest(db, tmp_path, contract, _docx(*OURS), "ours.docx")
    signed = _ingest(db, tmp_path, contract, _docx(*OURS[:5], TRACKED, OURS[6]),
                     "signed.docx")
    signed.doc_metadata = {**(signed.doc_metadata or {}), "version_role": "FINAL_SIGNED"}
    review = M.Review(contract_id=contract.id, document_version_id=signed.id,
                      configuration_snapshot_id=build.snapshot.id,
                      status=E.ReviewStatus.DRAFT, created_by=build.owner.id)
    db.add(review)
    db.flush()
    run = S.run_analysis(db, review)
    assert _findings(db, review)[DR]["classification"] == "MISSING"
    assert not _lineage(run)


def test_a_rewrite_we_accepted_is_traced_back_to_the_version_that_found_it(build, db,
                                                                         tmp_path):
    """D6: v1 ours (the configured words) → v2 theirs (tracked rewrite) → v3 our reply
    accepting it → v4 theirs, unchanged. v3 found nothing; v1 did, and the clause is
    followed v1 → v2 (its tracked original) → v3 → v4 (same words)."""
    review, run = _round(build, db, tmp_path, ("ours", OURS),
                         ("theirs", [*OURS[:5], TRACKED, OURS[6]]),
                         ("reply", [*OURS[:5], REWRITE, OURS[6]]),
                         ("t", [*OURS[:5], REWRITE, OURS[6]]))
    assert _findings(db, review)[DR]["classification"] == "UNABLE_TO_EVALUATE"
    [line] = _lineage(run)
    assert str(_ours_id(db, review, 1)) in line


def test_a_weak_hit_on_our_side_is_no_lineage(build, db, tmp_path):
    """D4: our version only touched the requirement weakly (UNRESOLVED, an alias in a
    force-majeure clause); its rewrite is no clause of ours that carried the position."""
    theirs = [WEAK[0], WEAK[1], WEAK[2],
              "14.1 Neither party is liable for delays caused by events beyond its control.",
              WEAK[4], WEAK[5], "20.1 Other providers may be used.", WEAK[7]]
    review, run = _round(build, db, tmp_path, ("ours", WEAK), ("theirs", theirs), code=SP)
    assert _findings(db, review)[SP]["classification"] == "MISSING"
    assert not _lineage(run)


# ------------------------------------------------------------------------------ fix 5
SP = "SUB-PROCESSORS-MSA-001"
WEAK = ["8. Data", "8.2 The Provider may appoint subprocessors after fourteen days' notice.",
        "14. Force Majeure", "14.1 Neither party is liable for delays caused by failures "
        "of third-party service providers.", "14.2 The affected party shall give notice.",
        "20. General", "20.1 Third-party service providers may be used.",
        "20.2 This Agreement is the entire agreement."]


def test_a_weak_unresolved_hit_cites_only_its_own_rows(build, db, tmp_path):
    theirs = [*WEAK[:-1], "20.2 This Agreement and the Order are the entire agreement."]
    review, run = _round(build, db, tmp_path, ("ours", WEAK), ("theirs", theirs), code=SP)
    found = _findings(db, review)[SP]
    assert found["classification"] == "UNABLE_TO_EVALUATE"
    assert {s for s, _ in found["cited"]} == {"14.1", "20.1"}     # never all of 14 and 20
    contract = db.get(M.Contract, review.contract_id)
    before, after = sorted(db.execute(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == contract.id)).scalars(),
        key=lambda v: v.version_number)
    [row] = negotiation.changes(db, contract, before, after, legal_position=True)["changes"]
    assert row["clause"]["number"] == "20.2"
    assert SP not in {f["requirement_code"] for f in row["review"]["after"]}


# ------------------------------------------------------------------------------ fix 3
IND = "INDEMNITY-MSA-001"
CUSTOMER_INDEMNITY = ("10.1 The Customer shall indemnify the Provider against third-party "
                      "claims arising from the Customer's content.")


def _indemnity(build, db, tmp_path, *paragraphs: str):
    review, _ = _round(build, db, tmp_path, ("ours", ["10. Indemnification",
                                                      CUSTOMER_INDEMNITY]),
                       ("theirs", ["10. Indemnification", *paragraphs]), code=IND)
    evaluation = db.execute(select(M.Evaluation).join(M.Finding).where(
        M.Finding.review_id == review.id)).scalars().one()
    item = next(i for i in angles.review_angles(db, review, legal_position=True)[
        "legal"]["items"] if i["requirement_code"] == IND)
    return evaluation, item


def test_an_indemnity_we_give_is_named_as_ours_not_broader(build, db, tmp_path):
    evaluation, item = _indemnity(
        build, db, tmp_path, CUSTOMER_INDEMNITY,
        "10.2 LeapSwitch shall indemnify the Customer against third-party claims of "
        "intellectual property infringement.")
    assert evaluation.classification is E.FindingClassification.DEVIATION
    assert evaluation.actual_value == {"presence": "TOO_BROAD", "cause": "OUR_INDEMNITY"}
    assert evaluation.evaluator_version == "PRESENCE-v2"
    assert "only the Customer indemnifies (AM-381 r2)" in " ".join(evaluation.result["explanation"])
    assert "LeapSwitch gives an indemnity; our standard has only the Customer's" in str(item)


def test_a_breadth_phrase_keeps_todays_words(build, db, tmp_path):
    evaluation, item = _indemnity(
        build, db, tmp_path, CUSTOMER_INDEMNITY.replace(
            "content.", "content, including indirect and consequential losses."))
    assert evaluation.actual_value == {"presence": "TOO_BROAD", "cause": "BREADTH"}
    assert "broader than the position (AM-154)" in " ".join(evaluation.result["explanation"])
    assert "Broader than our standard" in str(item)


# ------------------------------------------------------------------------------ fix 4
def test_a_deleted_list_item_is_read_after_its_parents_lead_in(build, db, tmp_path):
    ours = ["12. Indemnity",
            "12.2 The Buyer shall indemnify the Provider against claims arising from:",
            "12.2.1. any breach of law by the Buyer;",
            "12.2.2. any breach of the acceptable use policy by the Buyer."]
    contract = M.Contract(owner_id=build.owner.id, name="Lead-in", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    before = _ingest(db, tmp_path, contract, _docx(*ours), "ours.docx")
    after = _ingest(db, tmp_path, contract, _docx(*ours[:3]), "theirs.docx")
    [row] = negotiation.changes(db, contract, before, after, legal_position=True)["changes"]
    assert (row["kind"], row["clause"]["number"]) == ("DELETED", "12.2.2")
    assert [r["reason"] for r in row["triage"]["reasons"]] == ["Removes a duty of the client"]


# ------------------------------------------------- round 2 D1: two reader generations
@contextmanager
def _v11_reader(monkeypatch):
    """Ingest as `legalmind-ingest-v11` read: none of batch 6's numbering/heading rules."""
    from legalmind.ingestion import parsing
    from legalmind.ingestion import service as ingestion
    with monkeypatch.context() as m:
        m.setattr(parsing, "_glued", lambda stripped: None)
        m.setattr(parsing, "_LONG_DOTTED", re.compile(r"(?!)"))
        m.setattr(parsing, "styled_heading", lambda *a: False)
        m.setattr(ingestion, "PROCESSOR_VERSION", "legalmind-ingest-v11")
        yield


LIST = ["4.1. The provider may suspend if:", "4.1.1. a threat;",
        "4.1.2. suspension required by law or by a binding direction of a competent "
        "authority" + ", and the provider shall restore the service promptly once the "
        "grounds cease" * 2 + ";", "4.2. Fees remain payable."]


def test_two_reader_generations_are_compared_as_one(build, db, tmp_path, monkeypatch):
    """D1: our MSA read before ingest-v12 (its long 4.1.2 unnumbered, glued to 4.1.1),
    the client's after: the same words list nothing; one real change lists one row."""
    contract = M.Contract(owner_id=build.owner.id, name="Mixed", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    with _v11_reader(monkeypatch):
        ours = _ingest(db, tmp_path, contract, _docx(*LIST), "ours.docx")
    assert db.scalar(select(M.DocumentEvidence.section_number).where(
        M.DocumentEvidence.document_version_id == ours.id,
        M.DocumentEvidence.content.startswith("4.1.2."))) is None    # as v11 stored it
    same = _ingest(db, tmp_path, contract, _docx(*LIST), "theirs.docx")
    assert negotiation.changes(db, contract, ours, same, legal_position=True)[
        "changes"] == []
    changed = _ingest(db, tmp_path, contract, _docx(*LIST[:3], [
        _run("4.2. Fees remain payable"), _mark("ins", " within 30 days", 1), _run(".")]),
        "t.docx")
    rows = negotiation.changes(db, contract, ours, changed, legal_position=True)["changes"]
    assert [(r["kind"], r["clause"]["number"]) for r in rows] == [("MODIFIED", "4.2")]


def test_an_acceptance_on_a_mixed_pair_is_carried_as_on_one_reader(api, db, owner,
                                                                    tmp_path, monkeypatch):
    """D1 and carry (AM-299 r3): our version read by v11, the client's and our reply by
    v12 — the accepted change is carried exactly as on one reader. (Where the client's
    version is the OLDER reading and the old reader glued the accepted clause to its
    neighbour, the reply's unit text differs and nothing is carried: fail closed.)"""
    from legalmind.analysis.negotiation import carry_acceptances
    from tests.test_negotiation import _contract as contract_
    from tests.test_negotiation import _first, _url
    from tests.test_negotiation import _review as review_
    from tests.test_negotiation_carry import _point, _prepared, _theirs_rv
    from tests.test_negotiation_wording import OURS as CAP_OURS
    from tests.test_negotiation_wording import THEIRS as CAP_THEIRS
    c = contract_(db, owner)
    with _v11_reader(monkeypatch):
        _ingest(db, tmp_path, c, _docx(CAP_OURS), "ours.docx")
    theirs = _ingest(db, tmp_path, c, _docx(CAP_THEIRS), "theirs.docx")
    review = review_(db, theirs, [(0, E.FindingClassification.DEVIATION,
                                   E.RuleOutcome.ACCEPTABLE)])
    [change] = negotiation.changes(db, c, *sorted(db.scalars(select(M.DocumentVersion).where(
        M.DocumentVersion.contract_id == c.id)), key=lambda v: v.version_number),
        legal_position=True)["changes"]
    assert api.post(_url(c, change["row_key"]),
                    json=_first("accept_theirs")).status_code == 201
    reply, reply_review = _prepared(api, db, c)
    finding, _ = _point(db, reply_review, _theirs_rv(db, review), reply)
    assert carry_acceptances(db, reply_review) == 1
    assert finding.status is E.FindingStatus.RESOLVED


def test_diff_talk_compares_two_readers_as_one(build, db, tmp_path, monkeypatch):
    """R2-3: Diff-Talk's /comparisons reads the older version of a mixed pair as the
    newer one reads (a Heading-1 "Execution" over a table the v11 reader left inside
    clause 9): the same file twice is unchanged throughout."""
    from legalmind.analysis import document_comparison as dc
    from legalmind.analysis import reader_generation
    from tests.test_negotiation import _with_table
    contract = M.Contract(owner_id=build.owner.id, name="Diff", contract_type="MSA",
                          status=E.ContractStatus.ACTIVE)
    db.add(contract)
    db.flush()
    data = _with_table(["9.4. Counterparts: This agreement may be signed in counterparts."],
                       "For the Provider Name: ___")
    with _v11_reader(monkeypatch):
        ours = _ingest(db, tmp_path, contract, data, "ours.docx")
    theirs = _ingest(db, tmp_path, contract, data, "theirs.docx")
    older = reader_generation.older(db, ours.id, theirs.id)
    # the newer side is today's reader (v13 since batch 8: highlights, metadata only)
    assert older == (ours.id, 11, reader_generation.HIGHLIGHTS_FROM)
    def shape(side):
        return [(c["ref"], c["title"], len(c["evidence_ids"])) for c in side["clauses"]]
    new = dc.version_side(db, contract, theirs)
    assert shape(dc.version_side(db, contract, ours)) != shape(new)   # v11's own reading
    reread = dc.version_side(db, contract, ours, reread=older[1:])
    assert shape(reread) == shape(new)
    got = dc.compare(reread, new)
    assert got["summary"]["UNCHANGED"] == len(got["clauses"])
