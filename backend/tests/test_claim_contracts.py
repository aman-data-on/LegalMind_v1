"""Roadmap PHASE 12 / `AM-91`: claim contracts, the conflict map, and the checks that
hold each generated sentence to the contracts it cites. Deterministic — no model."""
import uuid

from legalmind.assist.query import query_plan as qp
from legalmind.assist.retrieval import evidence
from legalmind.assist.retrieval.retrieval import Candidate
from legalmind.assist.synthesis import contracts

SECTION = (
    "Legal Constitution L1.10 · 13. Termination & Suspension\n"
    "Company Position:\n\n"
    "Either party may terminate for convenience with 30 days' written notice. "
    "This section governs ongoing, non-fixed-term arrangements.\n\n"
    "[the company's reading of the law] Section 74 permits a stipulated sum, but where "
    "that sum is by way of penalty, only reasonable compensation is recoverable.\n\n"
    "[historical evidence, not current policy] [Customer A] MSA Cl. 5.2 allowed a "
    "6-month renewal period for that customer only.\n\n"
    "Drafting Notes for Counsel — Illustrative Clause Language (not yet in any signed "
    "contract):\n\n"
    "Either Party may terminate this Agreement immediately without notice for "
    "non-payment.\n")


def _source(text=SECTION, ref="CONST:13", authority="COMPANY_CONSTITUTION"):
    c = Candidate("CONSTITUTION", ref, uuid.uuid4(), text, 0.0, authority, "CURRENT")
    return evidence.Source(qp.COMPANY_POSITION, c, text, 5.0, True, None)


def test_each_sentence_takes_its_own_kind_and_drafting_is_never_a_claim():
    got = contracts.statements(_source())
    kinds = {s[:40]: k for s, k in got}
    assert any(k == contracts.POSITION and s.startswith("Either party may terminate")
               for s, k in kinds.items())
    assert contracts.READING in kinds.values()
    assert contracts.HISTORY in kinds.values()
    assert not any("immediately without notice" in s for s, _ in got), \
        "illustrative drafting ('not yet in any signed contract') is not a position"
    assert any("Cl. 5.2" in s for s, _ in got), "an abbreviation does not split a claim"


def test_a_contract_records_modality_negation_conditions_and_section_scope():
    c = contracts._contract(1, _source(), "Either party may terminate for convenience "
                                         "with 30 days' written notice.", contracts.POSITION)
    assert c.modality == "PERMITTED" and not c.negated
    assert any("ongoing, non-fixed-term" in x for x in c.conditions), \
        "a section's stated scope travels with every claim drawn from it"
    no = contracts._contract(2, _source(), "The Customer shall have no right to "
                                          "terminate before the expiry of the Term.",
                             contracts.POSITION)
    assert no.modality == "PROHIBITED" and no.negated
    assert any("before the expiry" in x for x in no.conditions)


def _c(n, text, kind=contracts.POSITION, scope=None, status="CURRENT"):
    mod, neg = contracts.modality(text)
    s, a, o = contracts._parts(text)
    return contracts.Contract(n, f"CONST:{n}", f"§{n}", kind, status, text, s, a, o,
                              mod, neg,
                              tuple(m.group(0).strip()
                                    for m in contracts._CONDITION.finditer(text)),
                              (), scope)


RENEW = _c(1, "Agreements with a fixed Initial Term automatically renew for successive "
              "terms, unless either party gives written notice of non-renewal.")
MAY = _c(2, "Either party may terminate for convenience with 30 days' written notice.")
READ = _c(3, "Section 74 limits recovery to reasonable compensation where the sum is by "
             "way of penalty.", contracts.READING)
HIST = _c(4, "One past customer agreement allowed a 6-month renewal period.",
          contracts.HISTORY, status="HISTORICAL")


def test_a_dropped_condition_fails():
    bad = contracts.check("The company position is that agreements automatically "
                          "renew for successive terms [1].", [RENEW])
    assert any("drops a condition" in f for f in bad)
    ok = contracts.check("The company position is that agreements with a fixed Initial "
                         "Term automatically renew for successive terms unless either "
                         "party gives written notice of non-renewal [1].", [RENEW])
    assert ok == []


def test_a_strengthened_or_weakened_modality_fails():
    must = contracts.check("The company position is that either party must terminate "
                           "for convenience with 30 days' written notice [2].", [MAY])
    assert any("modality permitted → mandatory" in f for f in must)
    assert contracts.check("The company position is that either party may terminate "
                           "for convenience with 30 days' written notice [2].", [MAY]) == []


def test_a_lost_or_added_negation_fails():
    bad = contracts.check("The company position is that either party may not terminate "
                          "for convenience with 30 days' written notice [2].", [MAY])
    assert bad, "a permission turned into a prohibition"


def test_the_companys_reading_is_never_the_law_and_is_always_named():
    unnamed = contracts.check("Recovery is limited to reasonable compensation where the "
                              "sum is by way of penalty [3].", [READ])
    assert any("source kind not named" in f for f in unnamed)
    as_law = contracts.check("The law provides, in the company's reading of the law, "
                             "that recovery is limited where the sum is by way of "
                             "penalty [3].", [READ])
    assert not any("law stated from" in f for f in as_law)
    assert any("law stated from" in f for f in contracts.check(
        "The Indian Contract Act provides that recovery is limited where the sum is by "
        "way of penalty [3].", [READ]))


def test_history_is_never_current_and_kinds_are_never_blended_unnamed():
    assert any("stated as current" in f for f in contracts.check(
        "The current renewal period is 6 months [4].", [HIST]))
    blended = contracts.check("The company position is that either party may terminate "
                              "for convenience with 30 days' written notice, and a "
                              "6-month renewal period applies [2][4].", [MAY, HIST])
    assert any("Historically" in f for f in blended), "history must be named as such"


def test_the_conflict_map_separates_layers_and_flags_same_kind_disagreement():
    a = _c(5, "The customer must give 30 days' written notice before terminating the "
              "agreement for convenience.", scope="MSA")
    b = _c(6, "The customer must give 60 days' written notice before terminating the "
              "agreement for convenience.", scope="MSA")
    c = _c(7, "The customer must give 30 days' written notice before terminating the "
              "agreement for convenience.", contracts.READING)
    rels = {(r.a, r.b): r.kind for r in contracts.relations([a, b, c])}
    assert rels[(5, 6)] == "CONFLICT", "same kind and scope, different figure"
    assert rels[(5, 7)] == "SEPARATE_LAYER", "policy and the reading of law are layers"
    other_scope = _c(8, "The customer must give 60 days' written notice before "
                        "terminating the agreement for convenience.", scope="TOS")
    assert not [r for r in contracts.relations([a, other_scope]) if r.kind == "CONFLICT"], \
        "an MSA position and a TOS position do not conflict"


FRAMED = ("Legal Constitution L1.10 · 13. Termination\n"
          "Acceptable Position:\n\n"
          "A counterparty accepting the 30-day export window with the statutory "
          "carve-outs stated.\n\n"
          "Unacceptable: An uncapped liability term, or a cap applying to only one party.\n")


def test_a_governing_heading_frames_its_claim_and_must_be_said():
    rows = contracts._statements(_source(FRAMED))
    frames = {s[:20]: f for s, _, _, f in rows}
    assert "Acceptable position" in frames.values() and "Unacceptable" in frames.values()
    c = contracts._contract(1, _source(FRAMED), rows[0][0], contracts.POSITION, rows[0][3])
    assert any("drops the frame" in f for f in contracts.check(
        "The company position states that a counterparty accepts the 30-day export "
        "window with the statutory carve-outs [1].", [c]))
    assert not any("drops the frame" in f for f in contracts.check(
        "The company position treats as acceptable a counterparty accepting the 30-day "
        "export window with the statutory carve-outs [1].", [c]))


def test_a_fragment_keeps_its_referent():
    src = _source("Legal Constitution L1.10 · 3. X\nPosition:\n\nThe duty applies to the "
                  "provider of the service. It is recorded because the reader may ask "
                  "about their own duties.\n")
    sents = contracts.statements(src)
    assert len(sents) == 1 and "It is recorded" in sents[0][0]


def test_a_document_type_scope_must_be_said():
    tos = contracts.Contract(1, "POS:X-TOS-001", "Company Standard X-TOS-001",
                             contracts.POSITION, "CURRENT", "Services renew for the same "
                             "billing period.", "", "", "", "STATEMENT", False, (), (), "TOS")
    assert any("drops the scope" in f for f in contracts.check(
        "The company position is that services renew for the same billing period [1].",
        [tos]))
    assert not any("drops the scope" in f for f in contracts.check(
        "Under the Terms of Service, the company position is that services renew for the "
        "same billing period [1].", [tos]))


def test_a_company_position_is_never_called_the_companys_reading():
    assert any("called the company's reading" in f for f in contracts.check(
        "The company's reading of the law is that either party may terminate for "
        "convenience with 30 days' written notice [2].", [MAY]))


def test_an_inline_illustrative_clause_in_a_standard_is_never_a_position():
    # `AM-92`'s known limitation, closed in PHASE 13: standard-file chunks carry their
    # drafting text inline after "[Illustrative clause:]"; run 9 showed it as the
    # company position three times (D-01, I-04, N-03).
    text = ("LIABILITY-MSA-001 §9 Liability — Company Position (final, closed) (MSA) the "
            "standard 12-month liability cap applies unless a specific agreement approved "
            "by the company expressly provides otherwise. The cap applies mutually to both "
            "parties. [Illustrative clause:] the aggregate liability of either Party shall "
            "not exceed the total fees paid or payable by Customer in the twelve (12) months "
            "immediately preceding the event giving rise to the claim.")
    got = [s for s, _, _, _ in contracts._statements(_source(text, "POS:LIABILITY-MSA-001",
                                                               "COMPANY_STANDARD"))]
    assert any("12-month liability cap" in s for s in got)
    assert not any("aggregate liability of either Party" in s for s in got)


def test_the_noun_obligation_is_not_a_mandatory_modal():
    """Run-9 E-02: "the vendor should provide ... flow-down obligations" was read as
    mandatory, so "the position requires a vendor to provide" passed as its restatement."""
    text = ("The vendor should provide security commitments and data-protection "
            "flow-down obligations no less protective than the company's position.")
    assert contracts.modality(text)[0] == "ADVISORY"
    assert contracts.modality("The vendor is obligated to notify the company.")[0] == \
        "MANDATORY"
    c = _c(3, text)
    assert any("modality advisory →" in f for f in contracts.check(
        "The company position requires the vendor to provide security commitments and "
        "data-protection flow-down obligations no less protective than the company's "
        "position [3].", [c]))
