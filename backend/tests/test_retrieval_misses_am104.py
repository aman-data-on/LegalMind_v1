"""`AM-104` — the remaining golden retrieval misses, each localized to its stage and
fixed there (roadmap §6/§7/§9/§14). Every test here failed on the code before it."""
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text as sql

from legalmind import config
from legalmind.assist.knowledge import statutes as st
from legalmind.assist.query import query_plan, routing
from legalmind.assist.retrieval import retrieval
from legalmind.assist.retrieval.retrieval import Candidate
from legalmind.assist.synthesis import answer, claim_records, contracts
from legalmind.security import permissions as perms

DPDP = "The Digital Personal Data Protection Act, 2023"
ASK = frozenset({perms.ASSIST_ASK})


def _act(db, title: str, sections: list[tuple[str, str, str]], status="CURRENT"):
    """(number, marginal note, content) per section, one chunk each."""
    schema = config.assist_schema()
    sid = uuid.uuid4()
    db.execute(sql(f'INSERT INTO "{schema}".statutes (id, official_title, act_number_year,'
                   " jurisdiction, source, source_ref, as_amended_date, file_sha256,"
                   " supplied_by, supplied_at, status) VALUES (:i, :t, 'Act No. 0 of 2099',"
                   " 'TEST', 'synthetic', 'none', 'n/a', :h, 'test', now(), :st)"),
               {"i": sid, "t": title, "h": uuid.uuid4().hex * 2, "st": status})
    ids = {}
    for n, (number, note, content) in enumerate(sections, 1):
        ids[number] = uuid.uuid4()
        db.execute(sql(f'INSERT INTO "{schema}".statute_chunks (id, statute_id,'
                       " section_number, marginal_note, ordinal, content,"
                       " chunking_algorithm_version) VALUES (:i, :s, :n, :m, :o, :c, 'test')"),
                   {"i": ids[number], "s": sid, "n": number, "m": note, "o": n, "c": content})
    db.flush()
    return ids


def _search(db, query, limit=3):
    return [(h.official_title, h.section_number) for h in st.search_statutes(
        db, query=query, permissions=ASK, limit=limit, embed_query=lambda q: None)]


# --- H-01: a source counts once per ranked list ---------------------------------------

def test_a_source_counts_once_per_list_not_once_per_repeat(monkeypatch):
    """§18's four sub-headings share one section number; summing each repeat's
    reciprocal rank put four long sections above §4.1 (golden H-01)."""
    def fake(db, domain, query, **_):
        mk = lambda ref: Candidate(domain, ref, uuid.uuid4(), "", 0.0)  # noqa: E731
        return [mk("CONST:4.1"), mk("CONST:18"), mk("CONST:18"), mk("CONST:18")] \
            if domain == retrieval.CONSTITUTION else []
    monkeypatch.setattr(retrieval, "_search", fake)
    q = "Under which Companies Act was Leapswitch incorporated?"
    plan = query_plan.plan(q)
    route = routing.plan(q, has_document=False, permissions=frozenset(
        {"assist.ask", "legal_position.view"}), statutes_available=True)
    pool = retrieval.candidates(None, plan, route, permissions=frozenset(
        {"assist.ask", "legal_position.view"}), embed_query=lambda _q: None)
    assert [c.ref for c in pool.by_domain["CONSTITUTION"]][:2] == ["CONST:4.1", "CONST:18"]


# --- D-01: a part that names its own topic keeps it -----------------------------------

def test_a_question_part_is_searched_under_its_own_topic():
    plan = query_plan.plan("Our liability cap does not apply to indemnity obligations. "
                           "What indemnity do customers owe us?")
    (sub,) = plan.sub_questions
    assert sub.query.startswith("indemnification"), sub.query
    # …and a part that names none still inherits the question's.
    plan = query_plan.plan("What is our early termination position? Does it specify "
                           "6 months?")
    assert all(s.query.startswith(plan.sub_questions[0].query.split()[0])
               for s in plan.sub_questions)


# --- E-03 / L-03: section titles count; version before relevance ----------------------

def test_a_section_title_counts_and_the_named_acts_own_words_order_nothing(db):
    """s. 27 of the Contract Act says "restrained" in its text and "restraint of trade"
    in its title; "contract" matches every section of the Act it names (E-03)."""
    filler = [(str(n), "Contracts", "A contract under this Act is a contract, and a "
                                    "binding one.") for n in range(1, 8)]
    _act(db, "The Synthetic Contract Act, 2099", [*filler, (
        "27", "Agreement in restraint of trade, void",
        "Every agreement by which any one is restrained from exercising a lawful "
        "profession, trade or business of any kind, is to that extent void.")])
    hits = _search(db, "Is a restraint like that valid under the Synthetic Contract Act?")
    assert hits[0][1] == "27", hits


def test_a_repealed_act_does_not_outrank_the_current_one_on_its_section_titles(db):
    """Once titles counted, s. 293 of the REPEALED 1956 Act ("Restrictions on powers
    of Board") outranked s. 179 of the 2013 Act for "the Companies Act" (L-03)."""
    _act(db, "The Synthetic Companies Act, 2099",
         [("179", "Powers of Board", "The Board of Directors of a company shall be "
                                     "entitled to exercise all such powers.")])
    _act(db, "The Synthetic Companies Act, 1999 (REPEALED — test)",
         [("293", "Restrictions on powers of Board", "The Board of directors of a "
                                                     "public company shall not exercise "
                                                     "the powers of the Board.")],
         status="REPEALED")
    hits = _search(db, "What does the Synthetic Companies Act say about the powers of "
                       "the Board?")
    assert hits[0] == ("The Synthetic Companies Act, 2099", "179"), hits


# --- F-05: a Schedule the section cites is its context --------------------------------

def test_a_schedule_naming_the_section_back_joins_its_context(db):
    ids = _act(db, "The Synthetic Data Act, 2099", [
        ("33", "Penalties", "33. Penalties.—(1) The Board may impose such monetary "
                            "penalty specified in the Schedule."),
        ("34", "Crediting", "34. All sums realised by way of penalties shall be "
                            "credited to the Consolidated Fund."),
        ("The Schedule", None, "THE SCHEDULE [See section 33 (1)] 1. Breach of "
                               "security safeguards. May extend to two hundred and fifty "
                               "crore rupees."),
        ("The Second Schedule", None, "THE SECOND SCHEDULE [See section 12] Forms.")])
    context = st.expand_section(db, ids["33"])
    assert "two hundred and fifty crore" in context
    assert "[Cross-reference: The Schedule]" in context
    assert "SECOND SCHEDULE" not in context, "a Schedule that names another section"
    assert "two hundred" not in st.expand_section(db, ids["34"]), "s. 34 cites none"


# --- O-04: an agency's short name, spelled out ----------------------------------------

def test_cert_in_is_searched_and_scored_by_the_name_the_act_gives_it(db):
    _act(db, "The Synthetic Technology Act, 2099", [
        ("1", "Short title", "This Act may be called the Synthetic Technology Act."),
        ("70B", "Indian Computer Emergency Response Team to serve as national agency",
         "The Indian Computer Emergency Response Team shall serve as the national "
         "agency for incident response.")])
    assert _search(db, "What does the Synthetic Technology Act say about CERT-In's "
                       "role?")[0][1] == "70B"
    assert st.with_agency_names("CERT-In's role?") == \
        "CERT-In (indian computer emergency response team)'s role?"
    assert st.with_agency_names("no agency here") == "no agency here"


# --- `section-5`: the Bill's Statement of Objects and Reasons is not law --------------

def test_the_statement_of_objects_and_reasons_is_cut_from_the_act():
    act = "1. Short title.—" + "x " * 300 + "\nSTATEMENT OF OBJECTS AND REASONS\nWhy."
    assert "OBJECTS" not in st.strip_end_matter(act)
    early = "STATEMENT OF OBJECTS AND REASONS\n" + "1. Short title.—" + "x " * 300
    assert st.strip_end_matter(early) == early, "only in the closing quarter"


_DOCS = Path(config.source_material_dir()) / "Indian_Laws_and_Acts"


@pytest.mark.skipif(not (_DOCS / "DPDP_Act_2023_indiacode.pdf").exists(),
                    reason="source material not present")
def test_the_dpdp_schedule_no_longer_carries_the_bills_statement():
    chunks = st.chunk_statute_text(st._pdf_text(_DOCS / "DPDP_Act_2023_indiacode.pdf"))
    schedule = " ".join(c.content for c in chunks if "Schedule" in c.section_number)
    assert "fifty crore" in schedule and "OBJECTS AND REASONS" not in schedule


# --- §14: commencement is not statutory text -----------------------------------------

def test_dpdp_penalties_are_not_yet_in_force_until_13_may_2027():
    before = date(2026, 9, 27)
    assert st.commencement(DPDP, "33", today=before) == \
        "NOT YET IN FORCE — commences 13 May 2027 (the date Constitution §28.2 states; " \
        "the company's reading, not the Act's text)"
    assert st.commencement(DPDP, "The Schedule", today=before).startswith("NOT YET")
    assert st.commencement(DPDP, "33", today=date(2027, 5, 13)) is None
    assert st.commencement(DPDP, "8", today=before) is None, "unnumbered: not inferred"
    assert st.commencement(DPDP, "6", "2", today=before) is None
    assert st.commencement(DPDP, "6", today=before).startswith("sub-section (9) NOT YET")
    assert st.commencement(DPDP, "27", "1", today=before).startswith("clause (d) NOT YET")


def test_every_commencement_quote_is_the_constitutions_own_words():
    import json
    constitution = (Path(__file__).resolve().parents[2] / "docs/02-legal-domain/"
                    "LEGAL_CONSTITUTION_L1.10.md").read_text()
    entries = json.loads(st._COMMENCEMENT.read_text())["entries"]
    assert entries
    for e in entries:
        assert e["quote"] in constitution, e["quote"][:60]
        assert "13 May 2027" in e["quote"] or "Section 6(9) and Section 27(1)(d)" in \
            e["quote"]


def test_a_not_yet_commenced_section_says_so_in_its_context_and_its_claims(db):
    ids = _act(db, DPDP, [("33", "Penalties", "33. Penalties.—(1) If the Board "
                                              "determines that breach of the provisions "
                                              "of this Act is significant, it may impose "
                                              "such monetary penalty specified in the "
                                              "Schedule.")])
    if st.commencement(DPDP, "33") is None:
        pytest.skip("13 May 2027 has passed")
    assert "[Commencement: NOT YET IN FORCE — commences 13 May 2027" in \
        st.expand_section(db, ids["33"])
    units = claim_records._statute(db, ids["33"])
    assert units and all(u.temporal and "13 May 2027" in u.temporal for u in units)


def test_the_readers_note_states_the_date_as_the_constitutions_not_the_acts():
    status = st.commencement(DPDP, "33", today=date(2026, 9, 28))
    c = contracts.Contract(n=1, ref="STAT:x:33", citation="DPDP Act s. 33(1)",
                           kind=contracts.LAW, status="CURRENT",
                           text="The Board may impose such monetary penalty specified in "
                                "the Schedule.", subject="", action="", object="",
                           modality="MAY", negated=False, conditions=(), exceptions=(),
                           scope=None, temporal=status)
    tail = answer._tail(c)
    assert tail == f" ({status})" and "the date Constitution §28.2 states" in tail
    assert "in force:" not in tail
    assert contracts._verbatim("The Board may impose such monetary penalty specified in "
                               "the Schedule" + tail + ".", c)
    assert not contracts.check(answer.verbalise(c), [c])


def test_a_commencement_status_keeps_its_dotted_section_reference():
    """"(Section 28.2.1)" was cut at its first dot to "(Section 28" — read as the Act's
    s. 28 in two run-9 sentences (F-05). A sentence's own full stop still ends it."""
    row = ("| Current Legal Status | NOT YET IN FORCE — Section 33 and the Schedule "
           "commence 13 May 2027 (Section 28.2.1). The underlying obligation |")
    assert claim_records._TEMPORAL.search(row).group(0).endswith("(Section 28.2.1)")
    assert claim_records._TEMPORAL.search(
        "commences 13 May 2027. Next sentence.").group(0) == "commences 13 May 2027"


def _law(text, temporal=None, citation="Digital Personal Data Protection Act, 2023, s. 33(2)"):
    return contracts.Contract(n=1, ref="STAT:x:33", citation=citation, kind=contracts.LAW,
                              status="CURRENT", text=text, subject="", action="",
                              object="", modality="STATEMENT", negated=False,
                              conditions=(), exceptions=(), scope=None, temporal=temporal)


def test_a_word_that_happens_to_be_effective_is_not_a_commencement():
    """s. 33(2)'s own "proportionate and effective" passed as its commencement (J-04)."""
    c = _law("(f) whether the monetary penalty to be imposed is proportionate and "
             "effective.", temporal=st.commencement(DPDP, "33", today=date(2026, 9, 28)))
    s = ("Under the law, the Board shall have regard to whether the monetary penalty to "
         "be imposed is proportionate and effective [1].")
    assert any("temporal status" in f for f in contracts.check(s, [c]))
    assert not any("temporal status" in f for f in contracts.check(
        s.replace(" [1].", ", which is not yet in force [1]."), [c]))


def test_a_section_a_sentence_names_must_be_one_its_claims_name():
    """"commencing 13 May 2027 under Section 28" for the Constitution's "(Section
    28.2.1)" reads as the Act's s. 28 (run 9, F-05)."""
    c = _law("The Board may impose a monetary penalty up to 250 crore rupees.",
             temporal="NOT YET IN FORCE — commences 13 May 2027 (Section 28.2.1)",
             citation="Legal Constitution L1.10 §28.2")
    wrong = "Under the law, the Board may impose up to 250 crore, commencing 13 May " \
            "2027 under Section 28 [1]."
    assert any("section 28 is not" in f for f in contracts.check(wrong, [c]))
    assert not any("is not one its cited" in f for f in contracts.check(
        wrong.replace("Section 28 ", "Section 28.2.1 "), [c]))


@pytest.mark.parametrize("opening", [
    "29A. Time limit for arbitral award.— 3 [(1) The award shall be made within a period "
    "of twelve months from the completion of pleadings.",
    "2. Definitions. — (1) In this Act, unless the context otherwise requires, words "
    "have these meanings.",
    "100. (1) Every person shall pay tax on the income so computed under this Act."])
def test_sub_section_one_is_a_claim_whatever_precedes_it(db, opening):
    """219 sections lost sub-section (1): a space or footnote after the title's dash, or
    a title in the margin, read it as a bare title (run 9, E-04: s. 29A's twelve months)."""
    ids = _act(db, "The Synthetic Arbitration Act, 2099", [
        ("29A", "Time limit", opening + "\n(2) A second sub-section of five words or more.")])
    units = claim_records._statute(db, ids["29A"])
    assert [u.citation_suffix for u in units][:2] == ["(1)", "(2)"], units


def test_a_sentence_that_stops_at_its_modal_is_not_a_claim():
    """"the Receiving Party shall not, directly or indirectly [4]." lost "solicit" and
    passed as a verbatim prefix of the record (run 9, C-04)."""
    c = _law("During the term and for two (2) years after it, the Receiving Party shall "
             "not, directly or indirectly, solicit any employee of the Disclosing Party.",
             citation="Legal Constitution L1.10 §15")
    cut = ("The law states that during the term and for two (2) years after it, the "
           "Receiving Party shall not, directly or indirectly [1].")
    assert any("stops at its modal" in f for f in contracts.check(cut, [c]))
    assert not any("stops at its modal" in f for f in contracts.check(
        cut.replace("indirectly [1]", "indirectly, solicit any employee of the "
                    "Disclosing Party [1]"), [c]))


def test_a_dotted_initialism_or_an_open_parenthesis_does_not_end_a_sentence():
    """"(G.S.R. 843(E) …)" was split after "G.S.R." and shown as "G.S.R; 843(E)" (live,
    O-05)."""
    got = answer._sentences("Notified on 13 November 2025 (G.S.R. 843(E) for the Act and "
                            "G.S.R. 846(E) for the Rules). A second sentence here.")
    assert got == ["Notified on 13 November 2025 (G.S.R. 843(E) for the Act and G.S.R. "
                   "846(E) for the Rules).", "A second sentence here."]


def test_a_combined_marker_is_read_as_its_markers():
    """"[2, A]" read as no citation and sank a correct answer (live, H-01)."""
    bundle = answer.evidence.Bundle((), (), (), False)
    payload = answer.Payload([], [], [], None, None, "")
    assert "[2][A]" in answer.complete("It may have been so [2, A].", "STOP", payload,
                                       bundle)


def test_sub_section_one_is_shown_without_the_prints_footnote_marker(db):
    ids = _act(db, "The Synthetic Arbitration Act, 2099", [(
        "29A", "Time limit", "29A. Time limit for arbitral award.— 3 [(1) The award shall "
        "be made within twelve months from the completion of pleadings.]\n(2) A second "
        "sub-section of five words or more.")])
    first = claim_records._statute(db, ids["29A"])[0]
    assert first.text.startswith("(1) The award") and "]" not in first.text, first.text


def test_an_exception_phrase_does_not_swallow_the_rules_modal():
    """"other than international commercial arbitration shall be made …" removed s.
    29A(1)'s "shall", and "the tribunal shall make the award" failed as a modality
    change (live, E-04)."""
    rule = ("(1) The award in matters other than international commercial arbitration "
            "shall be made by the arbitral tribunal within twelve months: Provided that "
            "the award in international commercial arbitration may be made sooner.")
    assert contracts.modality(rule) == ("MANDATORY", False)
