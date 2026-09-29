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


def test_an_exceptions_paragraph_names_the_position_it_qualifies(records):
    # Run 9 replay (A-01): "shorter notice or immediate action may be appropriate …"
    # said alone read as a general rule; it qualifies Service Discontinuation only.
    exc = [u for u in claim_records.units(records, _const(records, "31.14"))
           if u.heading and u.heading[-1] == "C. Exceptions"]
    assert exc and all(u.referent and u.referent.startswith("Service Discontinuation")
                       for u in exc)


def test_a_lead_in_that_announces_the_positions_is_not_a_claim(records):
    # Run 9 replay (GT-09): "The stakeholder has approved the following approach …"
    # was restated as a position; the lettered sub-parts after it are the positions.
    us = claim_records.units(records, _const(records, "31.14"))
    assert not any("approved the following approach" in u.text for u in us)
    assert any(u.heading[-1] == "A. MSA / Customer" for u in us), "the sub-parts stay"


def _framed():
    return _contract(ref="CONST:15", citation="§15", kind=contracts.POSITION,
                     modality="STATEMENT", negated=True,
                     text="NOT DEFINED beyond the confirmed position.",
                     frame="Negotiable / Approval Required",
                     referent="Section 15 (Confidentiality & Intellectual Property)")


def _payload(c, monkeypatch, figures=()):
    import dataclasses
    monkeypatch.setattr(contracts, "build", lambda *a, **k: [c])
    cand = Candidate("CONSTITUTION", c.ref, uuid.uuid4(), c.text, 0.0,
                     "COMPANY_CONSTITUTION")
    src = evidence.Source(qp.COMPANY_POSITION, cand, c.text, 5.0, True, None)
    part = evidence.Part("q", (qp.COMPANY_POSITION,), evidence.SUPPORTED, (src,))
    bundle = evidence.Bundle((part,), (src,), (), False)
    payload, _ = answer.contract_payload(bundle, "What is our position?")
    return dataclasses.replace(payload, reader_figures=figures), bundle


def test_the_code_restating_an_approved_claim_is_always_verifiable(monkeypatch):
    """2026-09-27 (golden C-04, A-01, D-04 fell back): the code's own restatement of 20
    of 553 approved claims failed verification, so no repair could ever succeed. The
    exact restatement is approved source text: the deterministic checks decide it."""
    from legalmind.assist import verify
    c = _framed()
    payload, bundle = _payload(c, monkeypatch)
    assert payload.evidence[0] == c.text, "the verifier's evidence stays the claim text"
    seen = {}
    monkeypatch.setattr(verify, "check_answer", lambda text, *a: seen.setdefault(
        "flags", a[-1]) and verify.Result(True, text, [], []))
    answer.verify_answer(answer.verbalise(c), payload, bundle, [c])
    assert seen["flags"] == [True], "a verbatim restatement is not the model's to judge"


def test_a_status_note_is_not_the_claims_negation():
    """The repair's own "(in force: NOT YET IN FORCE — … (Section 28))" or "(repealed —
    historical, not current law)" before the full stop is not the claim's polarity."""
    for status in ("NOT YET IN FORCE — commences 13 May 2027 (Section 28)", "REPEALED"):
        c = _contract(temporal=status)
        assert not contracts.check(answer.verbalise(c), [c]), status


def test_a_section_number_is_not_the_readers_figure(monkeypatch):
    """GT-03: "Section 12" is not "12 months" — a number counts with its unit."""
    c = _contract(kind=contracts.POSITION, modality="STATEMENT",
                  text="Retention follows Section 12 for 5 years.")
    payload, bundle = _payload(c, monkeypatch, figures=("12 months",))
    ok = "The company position states: retention follows Section 12 for 5 years [1]."
    assert not any("reader's figure" in f for f in answer.check(ok, payload, bundle))
    bad = "The company position is 12 months [1]."
    assert any("reader's figure" in f for f in answer.check(bad, payload, bundle))


def test_an_ellipsis_never_ends_a_sentence_of_a_claim():
    """C-04: the ratified quote "shall not, directly or indirectly ... solicit ..." was
    cut at the ellipsis and the answer shown lost the verb it prohibits."""
    from legalmind.assist import guardrails
    quote = "The Party shall not, directly or indirectly ... solicit ... Next sentence."
    assert guardrails._SENTENCES.split(quote) == [
        "The Party shall not, directly or indirectly ... solicit ... Next sentence."]
    c = _contract(kind=contracts.POSITION, modality="PROHIBITED",
                  text="The Party shall not, directly or indirectly ... solicit ...")
    assert answer.verbalise(c).endswith("solicit ... [1].")


def test_only_the_codes_exact_restatement_is_trusted():
    """A sentence that repeats a claim's attribution but says something else is judged
    as a paraphrase — echoing long frame and scope labels must never skip the model
    (a looser word-overlap test let four labelled-bad drafts through, 2026-09-27)."""
    c = _framed()
    assert answer.is_verbalisation(answer.verbalise(c), c)
    lead = answer.verbalise(c).split(" states: ")[0]
    assert not answer.is_verbalisation(f"{lead} states: everything is negotiable [1].", c)
    assert not answer.is_verbalisation(
        answer.verbalise(c).replace("NOT DEFINED", "DEFINED"), c)


def test_a_record_splits_only_between_its_own_sentences():
    """§13's "(CERT-In logs 180 days; KYC … 5 years)" was cut in half, and a quote's
    "..." became a sentence of its own that passed every check with nothing in it."""
    assert answer._record_sentences(
        "Kept 30 days (logs 180 days; KYC 5 years). Next one. ... More text.") == [
        "Kept 30 days (logs 180 days; KYC 5 years).", "Next one. ... More text."]


def test_a_hinted_restatement_is_trusted_only_word_for_word():
    """A hinted repair takes some of a record's sentences — a statute's semicolon items
    among them — and the exact-string test did not recognise it (12 of 508 failed)."""
    c = _contract(kind=contracts.POSITION, modality="STATEMENT",
                  text="Logs are kept for 180 days; Records are kept for 5 years. "
                       "Data is deleted after 30 days.")
    hinted = answer.verbalise(c, "records are kept for 5 years")
    assert "180" not in hinted, "the hint chose one item, not the whole record"
    assert answer.is_verbalisation(hinted, c)
    assert not answer.is_verbalisation(hinted.replace("are kept", "are not kept"), c)
