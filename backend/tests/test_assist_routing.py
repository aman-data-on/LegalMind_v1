"""The source router — authorization first, question shape second, no user selector."""
from legalmind.assist.routing import Domain, plan, positions_permitted, refusal_text
from legalmind.security import permissions as P

USER = frozenset({P.ASSIST_ASK, P.LEGAL_POSITION_VIEW})      # a Department User (AB-12)
LEAD = frozenset({P.ASSIST_ASK, P.CONFIGURATION_VIEW})
NOPOS = frozenset({P.ASSIST_ASK})
NONE = frozenset()


def test_a_document_question_searches_only_the_document():
    r = plan("What is the termination notice period?", has_document=True, permissions=USER)
    assert r.domains == (Domain.DOCUMENT,) and not r.comparison


def test_a_position_question_adds_the_positions_domain_when_permitted():
    r = plan("What is our standard liability cap?", has_document=True, permissions=USER)
    assert r.domains == (Domain.DOCUMENT, Domain.POSITIONS)


def test_a_department_user_and_a_lead_are_both_permitted_positions():
    assert positions_permitted(USER) and positions_permitted(LEAD)


def test_without_a_position_permission_the_domain_is_never_a_candidate():
    r = plan("What is our standard liability cap?", has_document=True, permissions=NOPOS)
    assert Domain.POSITIONS not in r.domains
    # and the refusal wording is the same as for a plain document question (AM-25 r7)
    assert refusal_text(r) == refusal_text(
        plan("What is the notice period?", has_document=True, permissions=NOPOS))


def test_without_assist_ask_nothing_is_a_candidate():
    r = plan("What is our standard liability cap?", has_document=True, permissions=NONE)
    assert r.domains == ()


def test_a_comparison_question_is_the_evaluators_and_also_a_position_question():
    r = plan("Compare this against company standards.", has_document=True, permissions=USER)
    assert r.comparison and r.domains == (Domain.DOCUMENT, Domain.POSITIONS)


def test_a_comparison_without_a_document_is_not_a_comparison():
    r = plan("Compare this against company standards.", has_document=False, permissions=USER)
    assert not r.comparison and r.domains == (Domain.POSITIONS,)


def test_a_statute_question_is_recorded_but_statutes_are_not_a_candidate_until_ratified():
    r = plan("What does Section 138 of the NI Act say?", has_document=True, permissions=USER)
    assert r.statute_shaped and Domain.STATUTES not in r.domains
    assert "not yet part of this installation's approved sources" in refusal_text(r)
    r2 = plan("What does Section 138 say?", has_document=True, permissions=USER,
              statutes_available=True)
    assert Domain.STATUTES in r2.domains


def test_refusal_wording_names_only_what_was_searched():
    assert refusal_text(plan("x?", has_document=True, permissions=NOPOS)).startswith(
        "Information not found in the selected document.")
    assert "approved positions" in refusal_text(
        plan("what is our policy on x?", has_document=True, permissions=USER))
    assert refusal_text(plan("Who are the parties?", has_document=False,
                             permissions=USER)).startswith("No document is attached")


def test_the_plan_is_deterministic():
    a = plan("What is our policy?", has_document=True, permissions=USER)
    b = plan("What is our policy?", has_document=True, permissions=frozenset(USER))
    assert a == b
