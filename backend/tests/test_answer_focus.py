"""`AM-107` — the answer leads with the directly applicable position, and every other
layer is kept apart (owner, 2026-09-28).

"What does our Constitution say about early termination? Please give the applicable
company standard …" was answered with §31.2's fixed-term MSA rule, §13's non-fixed-term
rules, a Distribution standard, the Vendor standard, the incident register, Companies Act
s. 466 and the Constitution's reading of the Contract Act, three claims each, in one
paragraph. The evidence was right; the ANSWER SELECTION had no notion of a direct answer.
These pin it: one source per asked kind leads, another family's rule never enters,
history and law the question did not ask for stay out or apart, a record is claimed a
sentence at a time, and the shown answer is laid out direct answer → related →
historical → law → sources, word for word as verified.

Deterministic: no reranker model (lexical order), no Gemini (stubs), no database.
"""
import uuid

import pytest

from legalmind.assist import answer, contracts, evidence, generation, service, verify
from legalmind.assist import query_plan as qp
from legalmind.assist.retrieval import Candidate

OBSERVED = ("What does our Constitution say about early termination? Please give the "
            "applicable company standard and cite the relevant Constitution section.")

# The Constitution's own words (L1.10 §31.2, §13), quoted as the sources state them.
S31_2 = ("Established Company Position: No early exit is permitted from a confirmed "
         "fixed-term commitment. If the customer exits before the end of the committed "
         "term, the full remaining committed-term value is payable.\n"
         "[historical evidence, not current policy] A review of actual signed MSAs found "
         "that two reviewed agreements contain a different 30-day/no-penalty exit "
         "structure.\nApplicable Document Types: MSA")
S13 = ("Either party may terminate for convenience with 30 days' written notice. "
       "Termination for cause requires a 30-day cure period after written notice of the "
       "breach.")
DISTRIBUTION = ("COMPLIANCE-TERMINATION-POST-DISTRIBUTION_AGREEMENT-001 §31.10 Termination "
                "(Distribution Agreement) LegalMind Rule: should follow the Constitution's "
                "general Termination position as a reference point, including a capped "
                "customer-transition period.")
S466 = ("The persons holding the offices of Chairman and Members of the Company Law Board "
        "shall vacate their offices on the constitution of the Tribunal.")
S74 = ("When a contract has been broken, if a sum is named in the contract as the amount "
       "to be paid in case of such breach, the party complaining of the breach is "
       "entitled to receive reasonable compensation not exceeding the amount so named. "
       "Exception.—When any person enters into any bail-bond, he shall be liable, upon "
       "breach of the condition, to pay the whole sum mentioned therein. "
       "Illustrations (a) A contracts with B to pay B Rs. 1,000, if he fails to pay B "
       "Rs. 500 on a given day.")
READING_74 = ("[the company's reading of the law] Section 74 permits a contract to "
              "stipulate a sum payable on breach, but where that sum is by way of penalty, "
              "only reasonable compensation is recoverable.")


def _src(ref, context, kind, relevance, *, domain="CONSTITUTION",
         authority="COMPANY_CONSTITUTION", named=False):
    c = Candidate(domain, ref, uuid.uuid4(), context, 0.0, authority, "CURRENT")
    return evidence.Source(kind, c, context, relevance, True, None, named)


def _bundle(question, lanes, *sources, assertions=()):
    part = evidence.Part(question, lanes, evidence.SUPPORTED, sources)
    return evidence.Bundle((part,), sources, assertions, False)


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    from legalmind.assist import rerank
    monkeypatch.setattr(rerank, "scores_many", lambda *a, **k: None)   # lexical order


def _observed_bundle():
    return _bundle(
        OBSERVED, (qp.COMPANY_POSITION,),
        _src("CONST:31.2", S31_2, qp.COMPANY_POSITION, 6.5),
        _src("POS:COMPLIANCE-TERMINATION-POST-DISTRIBUTION_AGREEMENT-001", DISTRIBUTION,
             qp.COMPANY_POSITION, -0.1, domain="POSITIONS"),
        _src("STAT:Companies Act, 2013:466", S466, qp.LAW, -1.6, domain="STATUTES",
             authority="PRIMARY_LAW"),
        _src("CONST:13", S13, qp.COMPANY_POSITION, 4.4))


def test_the_fixed_term_msa_position_is_the_direct_answer():
    """The observed question: §31.2 leads, alone as the direct answer."""
    cs = contracts.build(_observed_bundle(), OBSERVED)
    assert cs[0].ref == "CONST:31.2" and cs[0].layer == contracts.PRIMARY
    assert {c.ref for c in cs if c.layer == contracts.PRIMARY} == {"CONST:31.2"}
    assert any("No early exit is permitted" in c.text for c in cs if c.n <= 2)


def test_another_familys_rule_and_an_unasked_off_topic_statute_never_enter():
    refs = {c.ref for c in contracts.build(_observed_bundle(), OBSERVED)}
    assert not any("DISTRIBUTION_AGREEMENT" in r for r in refs)      # another family
    assert "STAT:Companies Act, 2013:466" not in refs                 # far off topic


def test_non_fixed_term_termination_is_related_optional_and_brief():
    """§13 — the non-fixed-term rules — is related context: one claim, optional."""
    cs = [c for c in contracts.build(_observed_bundle(), OBSERVED) if c.ref == "CONST:13"]
    assert len(cs) == 1 and cs[0].layer == contracts.RELATED and cs[0].optional


def test_a_non_fixed_term_question_leads_with_section_13_and_takes_no_other_history():
    question = ("What is our position on terminating an ongoing, non-fixed-term "
                "arrangement for convenience?")
    b = _bundle(question, (qp.COMPANY_POSITION,),
                _src("CONST:13", S13, qp.COMPANY_POSITION, 7.0),
                _src("CONST:31.2", S31_2, qp.COMPANY_POSITION, 3.0))
    cs = contracts.build(b, question)
    assert cs[0].ref == "CONST:13" and cs[0].layer == contracts.PRIMARY
    # §31.2's past deals are §31.2's context, never §13's.
    assert not [c for c in cs if c.layer == contracts.HISTORY_LAYER]


def test_a_historical_question_keeps_history_as_its_own_asked_layer():
    question = ("An old signed MSA we have says 30 days notice and no penalty for early "
                "exit. Is that our current policy?")
    b = _bundle(question, (qp.COMPANY_POSITION, qp.HISTORICAL_EXCEPTION),
                _src("CONST:31.2", S31_2, qp.COMPANY_POSITION, 5.0))
    cs = contracts.build(b, question)
    history = [c for c in cs if c.layer == contracts.HISTORY_LAYER]
    assert history and all(c.status == "HISTORICAL" and not c.optional for c in history)
    assert cs[0].layer == contracts.PRIMARY and cs[0].kind == contracts.POSITION


def test_unasked_history_is_one_optional_claim_beside_its_own_position():
    cs = contracts.build(_observed_bundle(), OBSERVED)
    history = [c for c in cs if c.layer == contracts.HISTORY_LAYER]
    assert len(history) == 1 and history[0].ref == "CONST:31.2" and history[0].optional


def test_a_distribution_question_is_answered_by_the_distribution_standard():
    question = "What does our Constitution say about terminating a Distribution Agreement?"
    b = _bundle(question, (qp.COMPANY_POSITION,),
                _src("CONST:31.2", S31_2, qp.COMPANY_POSITION, 3.0),
                _src("POS:COMPLIANCE-TERMINATION-POST-DISTRIBUTION_AGREEMENT-001",
                     DISTRIBUTION, qp.COMPANY_POSITION, 2.0, domain="POSITIONS"))
    cs = contracts.build(b, question)
    assert cs[0].ref.endswith("DISTRIBUTION_AGREEMENT-001")
    assert "CONST:31.2" not in {c.ref for c in cs}         # an MSA-only rule is not it


def test_a_question_about_the_law_is_answered_by_the_statute_it_names():
    question = "What does section 74 of the Indian Contract Act provide?"
    b = _bundle(question, (qp.LAW,),
                _src("CONST:14", READING_74, qp.LAW, 5.6,
                     authority="SECONDARY_REFERENCE"),
                _src("STAT:Indian Contract Act, 1872:74", S74, qp.LAW, 4.5,
                     domain="STATUTES", authority="PRIMARY_LAW", named=True))
    cs = contracts.build(b, question)
    assert cs[0].ref == "STAT:Indian Contract Act, 1872:74"
    assert cs[0].layer == contracts.PRIMARY                   # the law IS the answer
    assert [c.layer for c in cs if c.ref == "CONST:14"] == [contracts.RELATED]


def test_several_relevant_sources_one_direct_answer_and_the_law_apart():
    question = ("A client says their signed MSA mentions 6 months of compensation for "
                "early termination. What does our Constitution say, and what does the "
                "Indian Contract Act allow?")
    b = _bundle(question, (qp.COMPANY_POSITION, qp.LAW, qp.HISTORICAL_EXCEPTION),
                _src("CONST:31.2", S31_2, qp.COMPANY_POSITION, 6.0),
                _src("STAT:Indian Contract Act, 1872:74", S74, qp.LAW, 3.0,
                     domain="STATUTES", authority="PRIMARY_LAW"),
                _src("CONST:13", S13, qp.COMPANY_POSITION, 3.5))
    cs = contracts.build(b, question)
    assert {c.ref for c in cs if c.layer == contracts.PRIMARY} == {"CONST:31.2"}
    law = [c for c in cs if c.layer == contracts.LAW_LAYER]
    assert law and not any(c.optional for c in law)           # asked for: kept, apart
    assert {c.ref for c in cs} >= {"CONST:31.2", "STAT:Indian Contract Act, 1872:74",
                                   "CONST:13"}                # multi-source survives


def test_a_record_is_claimed_a_sentence_at_a_time():
    pieces = contracts.pieces(
        "74. Compensation for breach.—When a contract has been broken, the party is "
        "entitled to reasonable compensation. Exception.—When any person enters into any "
        "bail-bond, he shall be liable to pay the whole sum. This is the same position "
        "stated in Section 14.")
    assert pieces[0].startswith("74. Compensation")           # "74." kept with its rule
    assert pieces[1].startswith("Exception.—")                # its own modality
    assert pieces[1].endswith("stated in Section 14.")        # "This …" kept with it


def test_the_shown_answer_is_laid_out_by_layer_word_for_word():
    text = ("Under §31.2 no early exit is permitted [1]. Historically two deals differed "
            "[3]. Additionally, under §13 either party may terminate on notice [2]. "
            "The law caps a penalty at reasonable compensation [4].")
    shown = service._layered(text, ("PRIMARY", "RELATED", "HISTORY", "LAW"))
    blocks = shown.split("\n\n")
    assert blocks[0] == "Under §31.2 no early exit is permitted [1]."
    assert blocks[1:] == [
        "Also relevant", "Under §13 either party may terminate on notice [2].",
        "Historical context — past negotiated deals, not current policy",
        "Historically two deals differed [3].",
        "Legal background", "The law caps a penalty at reasonable compensation [4]."]


def test_a_sentence_restating_the_question_is_left_out_unless_it_carries_a_claim():
    shown = service._layered("The reader asked about early exit. No early exit [1]. "
                             "The reader asked whether 6 months holds [A].",
                             ("PRIMARY",))
    assert shown.startswith("No early exit [1].") and "[A]" in shown
    # Its only [A], but nothing of the reader's to answer: left out too.
    bare = service._layered("The reader asked about data breach notification [A]. "
                            "The Board acts on an intimation [1].", ("PRIMARY",))
    assert bare == "The Board acts on an intimation [1]."


def test_an_optional_sentence_that_fails_is_dropped_and_a_direct_one_is_repaired(
        monkeypatch):
    monkeypatch.setattr(verify, "check_answer",
                        lambda text, *a, **k: verify.Result(True, text, [], []))
    monkeypatch.setattr(answer, "REPAIR", False)
    b = _observed_bundle()
    _, cs = answer.contract_payload(b, OBSERVED)
    direct = next(c.n for c in cs if c.layer == contracts.PRIMARY)
    related = next(c.n for c in cs if c.optional)
    # Both drop their claim's strength ("may" → "must"): the related one is left out,
    # the direct one is replaced by the approved text itself.
    draft = (f"The company position is that a customer must exit early freely [{direct}]. "
             f"The company position is that either party must terminate on notice "
             f"[{related}].")

    def generate(*_a, **_k):
        return generation.GenerationResult(draft, "m", "v", "", 5, 100, 20, None)
    shown = answer.respond(b, OBSERVED, environment="test", generate=generate)
    assert shown.generated
    assert "must terminate on notice" not in shown.text
    assert "must exit early freely" not in shown.text


def test_a_marker_only_tail_and_a_rupee_amount_never_become_uncited_sentences():
    assert answer._sentences("B may recover not exceeding Rs. 1,000 as reasonable [1].") \
        == ["B may recover not exceeding Rs. 1,000 as reasonable [1]."]
    payload = answer.Payload([], [], [], None, None, "")
    b = evidence.Bundle((), (), (), False)
    assert answer.complete("A rule [1]. [M]", None, payload, b) == "A rule [1]."


# DPDP Act 2023 s. 2 and s. 27, as the corpus holds them (abridged to three definitions).
DPDP_S2 = ("(r) “notification” means a notification published in the Official Gazette;\n"
           "(t) “personal data” means any data about an individual who is identifiable;\n"
           "(u) “personal data breach” means any unauthorised processing of personal "
           "data;\n(y) “she” in relation to an individual includes the reference to such "
           "individual irrespective of gender;")
DPDP_S27 = ("(a) on receipt of an intimation of personal data breach under sub-section (6) "
            "of section 8, to direct any urgent remedial or mitigation measures in the "
            "event of a personal data breach.")


def _dpdp(question, monkeypatch):
    """Through the records path production uses — a statute is claimed one record
    sentence at a time (`claim_records.units`)."""
    import dataclasses

    from legalmind.assist import claim_records
    monkeypatch.setattr(claim_records, "units", lambda db, src: [
        claim_records.Unit(line, "PRIMARY_LAW", "CURRENT")
        for line in src.candidate.text.split("\n")])
    s2 = _src("STAT:Digital Personal Data Protection Act, 2023:2", DPDP_S2, qp.LAW, 3.8,
              domain="STATUTES", authority="PRIMARY_LAW")
    s2 = dataclasses.replace(s2, candidate=dataclasses.replace(s2.candidate,
                                                              note="Definitions"))
    s27 = _src("STAT:Digital Personal Data Protection Act, 2023:27", DPDP_S27, qp.LAW,
               3.0, domain="STATUTES", authority="PRIMARY_LAW")
    return contracts.build(_bundle(question, (qp.LAW,), s2, s27), question, db=object())


def test_a_definitions_section_does_not_lead_a_question_about_what_the_law_requires(
        monkeypatch):
    """DPDP s. 2 led "data breach notification" with the definitions of "notification"
    and "she" (browser, 2026-09-29)."""
    claims = _dpdp("What does the DPDP Act say about personal data breach notification?",
                   monkeypatch)
    assert claims[0].ref.endswith(":27")
    defined = " ".join(c.text for c in claims if c.ref.endswith(":2"))
    assert "“she”" not in defined and "“personal data”" not in defined


def test_a_meaning_question_is_answered_by_the_definition_of_its_own_term(monkeypatch):
    claims = _dpdp("What does personal data breach mean under the DPDP Act?", monkeypatch)
    assert claims[0].ref.endswith(":2") and "“personal data breach”" in claims[0].text
    assert not any("“personal data”" in c.text or "“she”" in c.text for c in claims)
