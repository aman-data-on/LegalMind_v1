"""Roadmap PHASE 12 / `AM-92`: claim contracts built from the structured source records.

Regression cases named by the owner after the first PHASE 12 checkpoint: the DPDP
"NOT YET IN FORCE (13 May 2027)" status, §31.14's exception list and headings, a
statute proviso's clause range, a sub-section's proviso not spliced onto the next,
"this position"'s antecedent, a Purpose line never a position, and source kinds. The
Constitution cases read the real Constitution records (`constitution.ingest`); the
statute cases a synthetic Act with the same structure (no statute text enters the repo).
"""
import uuid
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import text as sql

from legalmind import config
from legalmind.assist import answer, claim_records, constitution, contracts, evidence
from legalmind.assist import query_plan as qp
from legalmind.assist.retrieval import Candidate


@pytest.fixture
def records(db):
    constitution.ingest(db)
    return db


def _const(db, section: str):
    item = db.execute(sql(f'SELECT id FROM "{config.assist_schema()}".knowledge_items '
                          "WHERE section_path = :s AND kind = 'PARAGRAPH' LIMIT 1"),
                      {"s": section}).scalar()
    return NS(ref=f"CONST:{section}", candidate=NS(item_id=item))


def test_every_dpdp_penalty_carries_its_not_yet_in_force_status(records):
    penalties = [u for u in claim_records.units(records, _const(records, "28.2"))
                 if u.text.startswith("Legal Consequence / Penalty")]
    assert penalties, "the entries' penalty rows are claims"
    for u in penalties:
        assert u.temporal and "NOT YET IN FORCE" in u.temporal and "13 May 2027" in \
            u.temporal, u.text[:60]
        assert u.heading and u.heading[-1].startswith("Entry:"), "its entry heading"
    assert not any(u.text.startswith(("Recommended Legal Mind Response",
                                      "Counsel Validation"))
                   for u in claim_records.units(records, _const(records, "28.2"))), \
        "advice to the reader or to Counsel is not a claim"


def test_the_3114_exception_list_belongs_to_its_group_only(records):
    us = claim_records.units(records, _const(records, "31.14"))
    planned = next(u for u in us if u.heading[-1].startswith("A. Planned Full Service"))
    assert planned.heading[0].startswith("Service Discontinuation"), "group heading kept"
    assert planned.exceptions and "Shorter notice or immediate action" in \
        planned.exceptions and "force majeure" in planned.exceptions, "the full list"
    control = [u for u in us if "Change of Ownership / Control" in " ".join(u.heading)]
    assert control and not any(u.exceptions for u in control), \
        "another group's exceptions never attach"


def test_this_position_names_its_antecedent(records):
    this = next(u for u in claim_records.units(records, _const(records, "31.14"))
                if u.text.startswith("This position"))
    assert this.referent and this.referent.startswith("Service Discontinuation")


def test_a_purpose_line_and_drafting_are_never_positions_and_scope_travels(records):
    us = claim_records.units(records, _const(records, "13"))
    assert not any(u.text.startswith("Governs exit risk") for u in us), "Purpose"
    assert not any("Either Party may terminate this Agreement" in u.text for u in us), \
        "illustrative drafting"
    position = next(u for u in us if u.text.startswith("Either party may terminate"))
    assert any("non-fixed-term" in s for s in position.scope)
    framed = next(u for u in us if u.text.startswith("A counterparty accepting"))
    assert framed.frame == "Acceptable Position"


def test_source_kinds_come_from_each_record(records):
    kinds = {contracts._kind_of_record(u)
             for u in claim_records.units(records, _const(records, "31.14"))}
    assert contracts.HISTORY in kinds and contracts.POSITION in kinds
    reading = {contracts._kind_of_record(u)
               for u in claim_records.units(records, _const(records, "28.2"))}
    assert reading == {contracts.READING}, "§28.2 is the company's reading of the law"


STATUTE = (
    "9. Powers of the synthetic board.—(1) The board may exercise every synthetic "
    "power.\n"
    "(3) The board shall exercise the following powers by resolution, namely:—\n"
    "(a) to issue synthetic tokens;\n(d) to borrow synthetic credit;\n"
    "(f) to lend synthetic credit:\n"
    "Provided that the board may delegate the powers specified in clauses (d) to (f) "
    "to a committee.\n"
    "(4) Nothing in this section shall apply to synthetic\n"
    "1. Subs. by Act 7 of 2098, s. 3, for certain words.\n"
    "2. For synthetic limitation, see the Synthetic Limitation Act.\n"
    "42\n"
    "trusts:\n"
    "Provided that the Government may amend the list of synthetic trusts.\n")


def _synthetic_statute(db, status="CURRENT"):
    schema = config.assist_schema()
    sid, cid = uuid.uuid4(), uuid.uuid4()
    db.execute(sql(f'INSERT INTO "{schema}".statutes (id, official_title, act_number_year,'
                   " jurisdiction, source, source_ref, as_amended_date, file_sha256,"
                   " supplied_by, supplied_at, status) VALUES (:i, 'The Synthetic Boards "
                   "Act, 2099', 'Act No. 0 of 2099', 'TEST', 'synthetic', 'none', 'n/a', "
                   ":h, 'test', now(), :st)"), {"i": sid, "h": uuid.uuid4().hex * 2,
                                                  "st": status})
    db.execute(sql(f'INSERT INTO "{schema}".statute_chunks (id, statute_id, '
                   "section_number, marginal_note, ordinal, content, "
                   "chunking_algorithm_version) VALUES (:i, :s, '9', 'Powers of the "
                   "synthetic board', 0, :c, 'test')"), {"i": cid, "s": sid, "c": STATUTE})
    db.flush()
    return NS(ref="STAT:Synthetic Boards Act, 2099:9", candidate=NS(item_id=cid))


def test_a_proviso_stays_with_its_subsection_and_keeps_its_range(db):
    us = claim_records.units(db, _synthetic_statute(db))
    three = next(u for u in us if u.citation_suffix == "(3)")
    four = next(u for u in us if u.citation_suffix == "(4)")
    assert "clauses (d) to (f)" in three.text and "(a) to issue" in three.text
    assert "amend the list of synthetic trusts" in four.text
    assert "amend the list" not in three.text, "(4)'s proviso is never spliced onto (3)"
    assert three.frame == "Powers of the synthetic board"
    assert "synthetic trusts:" in four.text and "Subs. by Act" not in four.text \
        and "see the Synthetic" not in four.text, "page-foot notes are not the law"
    assert three.referent == "Synthetic Boards Act, 2099", "'this Act' is named"


def test_a_repealed_act_is_never_current_law(db):
    us = claim_records.units(db, _synthetic_statute(db, "REPEALED"))
    assert all(u.status == "REPEALED" and u.temporal == "REPEALED" for u in us)
    c = _contract(kind=contracts.LAW, temporal="REPEALED", text=us[0].text)
    assert any("temporal status" in f for f in contracts.check(
        f"The law states: {us[0].text} [1].", [c]))
    assert not any("temporal status" in f for f in contracts.check(
        answer.verbalise(c), [c])), "the repair says it is repealed"


def test_antecedents_outside_the_group_are_resolved(records):
    matching = next(u for u in claim_records.units(records, _const(records, "14"))
                    if "Scope of Application above" in u.text)
    assert matching.referent.startswith("Scope of Application: This section applies")
    confirmed = next(u for u in claim_records.units(records, _const(records, "15"))
                     if "beyond the confirmed position" in u.text)
    assert confirmed.referent.startswith("Section 15 (Confidentiality"), "the section's topic"


def test_that_sum_and_the_amount_stated_above_resolve_in_the_records_words(records):
    # Run 7 (GT-01, GT-13, J-01, N-04): §14's legal basis copied without what they mean.
    basis = next(u for u in claim_records.units(records, _const(records, "14"))
                 if "where that sum is by way of penalty" in u.text)
    assert dict(basis.antecedents) == {
        "that sum": "a sum payable on breach",
        "the contractual amount stated above": "the full committed-term value"}
    c = _contract(ref="CONST:14", text=basis.text, modality="STATEMENT",
                  antecedents=basis.antecedents)
    lost = [
        "In the company's reading of the law, where that sum is by way of penalty, the "
        "complaining party is entitled to reasonable compensation not exceeding the "
        "stipulated amount [1].",
        "In the company's reading of the law, the contractual amount stated above is the "
        "company's required commercial position [1]."]
    for sentence in lost:
        assert any("antecedent of" in f for f in contracts.check(sentence, [c])), sentence
    assert not any("antecedent of" in f for f in contracts.check(
        "In the company's reading of the law, where a sum payable on breach is by way of "
        "penalty, that sum is a ceiling [1].", [c]))
    assert not any("antecedent of" in f for f in contracts.check(
        answer.verbalise(c), [c])), "the repair names both, in the records' words"


def test_a_lettered_sub_part_keeps_only_its_own_document_type(records):
    # Run 7 (D-02): "A. MSA / Customer" and "C. Distribution Agreement" were each scoped
    # to the whole group's "MSA, Vendor Agreement, Distribution Agreement".
    us = [u for u in claim_records.units(records, _const(records, "31.14"))
          if "Change of Ownership / Control" in u.heading[0]]
    msa = next(u for u in us if u.heading[-1] == "A. MSA / Customer")
    dist = next(u for u in us if u.heading[-1] == "C. Distribution Agreement")
    assert msa.scope == ("MSA agreements",)
    assert dist.scope == ("Distribution Agreement agreements",)


def test_a_historical_deal_inherits_no_current_document_type_scope(records):
    # Run 7 (GT-00): past renewal deals were said to be "applicable only to MSA and
    # structurally applicable to Partner Agreement …" — the current position's scope.
    us = claim_records.units(records, _const(records, "31.15"))
    history = [u for u in us if u.authority == "HISTORICAL_EXCEPTION"]
    assert history and all(not u.scope for u in history)
    assert any(u.scope for u in us if u.authority != "HISTORICAL_EXCEPTION"), \
        "the current position keeps its own"


def _contract(**kw):
    base = {"n": 1, "ref": "CONST:28.2", "citation": "§28.2", "kind": contracts.READING,
            "status": "CURRENT", "text": "Legal Consequence / Penalty: the Board may "
            "impose a penalty up to 200 crore.", "subject": "", "action": "",
            "object": "", "modality": "PERMITTED", "negated": False, "conditions": (),
            "exceptions": (), "scope": None}
    base.update(kw)
    return contracts.Contract(**base)


def test_the_contract_checks_hold_status_antecedent_and_exceptions():
    dated = _contract(temporal="NOT YET IN FORCE — commences 13 May 2027")
    assert any("temporal status" in f for f in contracts.check(
        "In the company's reading of the law, the Board may impose a penalty up to 200 "
        "crore [1].", [dated]))
    assert not any("temporal status" in f for f in contracts.check(
        "In the company's reading of the law, the Board may impose a penalty up to 200 "
        "crore, not yet in force until 13 May 2027 [1].", [dated]))
    this = _contract(kind=contracts.POSITION, modality="STATEMENT",
                     text="This position is separate from the suspension provisions.",
                     referent="Service Discontinuation & Material Scope Changes")
    assert any("not resolved" in f for f in contracts.check(
        "The company position is that this position is separate from the suspension "
        "provisions [1].", [this]))
    listed = _contract(kind=contracts.POSITION, modality="STATEMENT",
                       text="Provide 30 days' advance notice.",
                       exceptions_text="Shorter notice may be appropriate for security.")
    assert any("exceptions" in f for f in contracts.check(
        "The company position is to provide 30 days' advance notice [1].", [listed]))


def test_repair_uses_only_the_records_own_words():
    c = _contract(kind=contracts.POSITION, modality="STATEMENT", text="Provide 30 days' "
                  "advance notice.", exceptions_text="Shorter notice may be appropriate "
                  "for security.", temporal=None, referent="Service Discontinuation",
                  frame="A. Planned Full Service Discontinuation / Retirement")
    said = answer.verbalise(c)
    assert "Provide 30 days' advance notice" in said
    assert "Shorter notice may be appropriate for security" in said
    assert said.endswith("[1].")
    assert contracts.check(said, [c]) == [], "a repaired sentence passes by construction"


def test_the_records_path_builds_contracts_with_their_fields(records):
    src = _const(records, "28.2")
    cand = Candidate("CONSTITUTION", "CONST:28.2", src.candidate.item_id, "x", 0.0,
                     "SECONDARY_REFERENCE", "CURRENT", (qp.LAW,))
    source = evidence.Source(qp.LAW, cand, "x", 5.0, True, None)
    part = evidence.Part("What is the DPDP penalty?", (qp.LAW,), evidence.SUPPORTED,
                         (source,))
    bundle = evidence.Bundle((part,), (source,), (), False)
    cs = contracts.build(bundle, "What is the maximum DPDP penalty?", records)
    assert cs and all(c.from_records for c in cs)
    assert any(c.temporal and "13 May 2027" in c.temporal for c in cs)
