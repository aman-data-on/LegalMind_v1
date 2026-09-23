"""A one-lexeme rescue may not be presented as a relevant Company Standard.

THE DEFECT, measured on the live corpus 2026-09-23 across 22 realistic questions.
Nine came back with a ratified standard introduced as "the organization's approved
position relevant to this question" when nothing relevant had been found:

    "what's the weather in pune"            -> GOVERNING-LAW-DISPUTE-VENDOR_AGREEMENT-001
    "how long do I have to file an appeal"  -> CONF-SURVIVAL-NDA-001
    "draft me an NDA"                       -> CONF-SURVIVAL-NDA-001

"Weather in pune" reached the governing-law standard through `pune` — a real venue
lexeme in a real standard. The relax pass admits a chunk sharing ONE lexeme, and
`positions.search_positions` states its own premise for doing so: it is "the right
trade when the reader is asking the organization about its own paper". Nothing
enforced that premise, so the rescue ran for every question.

WHAT WAS NOT DONE, and why. Gating the lane on "strict floor OR calibrated gate" was
tried first and REVERTED: it broke `test_positions_natural_language`, because "Explain
our termination standard." shares exactly one lexeme (`termin`) with every termination
chunk and the rescue is the whole reason it is answerable (2026-09-16). That test
stubs the embedder precisely so a provisioned model cannot mask the regression — and
it did mask it in a live check, which is why the test exists and the live check is not
enough.

So the strict floor, the calibrated gate and `AM-76` r4 are all untouched. What
changed is that the rescue now runs only where its own premise holds.
"""
from __future__ import annotations

import pathlib

from legalmind.assist import routing, service, understanding
from legalmind.security import permissions as P

PERMS = frozenset({P.ASSIST_ASK, P.CONTRACT_VIEW, P.FINDING_VIEW,
                   P.LEGAL_POSITION_VIEW, P.CONFIGURATION_VIEW})


def _route(question: str, *, has_document: bool = False):
    return routing.plan(question, has_document=has_document, permissions=PERMS,
                        statutes_available=True,
                        statute_jurisdictions=frozenset({"IN"}))


def test_the_rescue_runs_for_a_question_about_our_own_paper():
    """Its stated premise, and the 2026-09-16 case it exists for."""
    for question in ("Explain our termination standard.",
                     "What is our termination standard?",
                     "What does our standard say about termination?",
                     "what is our standard confidentiality period"):
        assert service._relax_allowed(_route(question)), question


def test_the_rescue_is_withheld_where_the_premise_does_not_hold():
    """The three live failures. None of them asks the organization about its paper,
    and each reached a ratified standard through a single shared lexeme."""
    for question in ("what's the weather in pune",
                     "how long do I have to file an appeal",
                     "draft me an NDA"):
        assert not service._relax_allowed(_route(question)), question


def test_a_statute_shaped_question_still_withholds_it():
    """The pre-existing condition is preserved, not replaced: the rescue was already
    wrong for a question about the law (2026-09-21)."""
    assert not service._relax_allowed(_route("What does section 43A of the IT Act say?"))


def test_the_strict_floor_and_the_calibrated_gate_are_untouched():
    """The fix is a policy decision about when a RESCUE applies. It introduces no
    constant, and it does not touch retrieval's own floors — asserted directly so the
    rule cannot drift into an invented threshold."""
    source = pathlib.Path(service.__file__).read_text()
    assert "allow_relax=_relax_allowed(route)" in source
    positions_src = pathlib.Path(understanding.__file__).parent.joinpath(
        "positions.py").read_text()
    assert "if not rows and allow_relax:" in positions_src        # unchanged
    assert "gate_is_open(False, scores)" in positions_src          # unchanged


def test_authorization_is_unchanged():
    """The rescue decision runs after authorization and never widens it: a caller
    without the Domain A permissions gets no position domain at all."""
    route = routing.plan("what is our standard confidentiality period",
                         has_document=False, permissions=frozenset({P.ASSIST_ASK}),
                         statutes_available=True,
                         statute_jurisdictions=frozenset({"IN"}))
    assert routing.Domain.POSITIONS not in route.domains
    assert routing.Domain.POSITIONS not in route.fallback


# --------------------------------------------------------------------------
# 2026-09-23, second half: the STRICT floor on generic words.
#
# "what does Indian law say about penalty clauses" cleared the two-lexeme floor on
# `indian` + `law` and was answered from a governing-law and a GST standard. It is not
# one case: six law-only questions in the 76-case matrix were answered the same way,
# and with a document open "who are the parties to this agreement?" was answered from
# a Partner Agreement notice position on `parti` + `agreement`. Two rules, each the
# mirror of one the code already had — neither is a threshold, a stoplist or a patch.
# --------------------------------------------------------------------------
LAW_QUESTIONS = (
    ("what does Indian law say about penalty clauses", False),
    ("Is a contract with a minor valid under Indian law?", False),
    ("What is the punishment for breach of confidentiality by an intermediary?", False),
    ("What does the Income-tax Act, 1961 say about TDS on professional fees?", False),
    ("Is this enforceable under Indian law?", True),
    ("What does Indian law say about this confidentiality clause?", True),
    ("does this NDA follow Indian data protection law", True),
)


def test_a_standard_is_no_fallback_for_a_question_about_the_law():
    """Rule 1, the foreign-law rule generalised: a Company Standard states what the
    organization will accept, never what the law says — Indian law no more than
    Delaware law."""
    for question, has_document in LAW_QUESTIONS:
        route = _route(question, has_document=has_document)
        assert routing.Domain.POSITIONS not in route.domains, question
        assert routing.Domain.POSITIONS not in route.fallback, question


def test_questions_about_our_own_position_keep_the_positions():
    """The cases that must not regress, including a law question that ALSO asks
    for our position — the genuine both-domains question."""
    for question in ("What's our stance on auto renewal?",
                     "Explain our termination standard.",
                     "What does our Constitution say about partner agreements?",
                     "What's our standard confidentiality period?",
                     "What does Indian law say about our liability cap?"):
        assert routing.Domain.POSITIONS in _route(question).domains, question
    for question in ("liability cap??", "termination clause", "notice period?"):
        route = _route(question, has_document=True)
        assert routing.Domain.POSITIONS in route.fallback, question


def test_behind_a_chosen_source_a_position_needs_semantic_evidence(
        db, user, tmp_path):
    """Rule 2, `statutes.search_statutes`'s `require_semantic` mirrored: when the
    positions stand behind the document or the statutes, sharing lexemes is not
    relevance, and without a gated vector neighbour Domain A counts as silent. The
    primary route is never held to it — asking about our position IS the signal."""
    from legalmind.assist import positions
    from tests.test_assist_ask import _ratified_positions
    _ratified_positions(db, user, tmp_path)
    question = "how must widgets be handled with care?"
    no_vector = lambda _q: None  # noqa: E731
    assert positions.search_positions(db, query=question, permissions=PERMS,
                                      embed_query=no_vector)
    assert positions.search_positions(db, query=question, permissions=PERMS,
                                      embed_query=no_vector,
                                      require_semantic=True) == []


def test_is_this_ok_for_us_is_the_evaluators_question_and_a_permission_is_not():
    """`AM-77` r4. It had been answered with three MSA positions on the lexeme `msa`."""
    from legalmind.assist import intent
    assert intent.is_comparison_question("is this MSA ok for us")
    assert intent.is_comparison_question("is this contract OK for us?")
    assert not intent.is_comparison_question("is it ok for us to terminate early?")
    assert not intent.is_comparison_question("is it okay if we pay late?")
