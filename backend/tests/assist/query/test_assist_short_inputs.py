"""Short, vague and ungrounded inputs (`AM-118`, owner 2026-10-07): each gets one honest
line and no model call, and each rule leaves the case beside it alone. No database, no
model — the pre-router and its helpers are pure."""
import pathlib

from legalmind.assist import service
from legalmind.assist.agent import attachments
from legalmind.assist.query import capability, conversational


def _route(q, *, prior=False, document=False, material=False):
    return service.preroute(q, has_prior=prior, has_document=document,
                            has_material=material)


def test_hi_is_one_line_and_the_same_line_every_time():
    first, second = _route("hi"), _route("Hi!")
    assert first == second == "Hello. What can I help you with today?"
    assert "Company Standards" not in first and "statutes" not in first


def test_how_can_you_help_is_the_short_brief_not_a_model_call():
    assert _route("how can you help me?") == capability.answer()
    assert len(_route("how can you help me?").splitlines()) == 1


def test_a_question_about_their_own_agreement_asks_for_it_when_none_is_here():
    reply = _route("Is my liability cap enforceable?")
    assert reply is not None and "paste the liability clause" in reply
    assert "don't have that agreement" in reply
    # With the agreement in the chat, or material pasted, the question is answered.
    assert _route("Is my liability cap enforceable?", document=True) is None
    assert _route("Is my liability cap enforceable?", material=True) is None
    # "Our" is the company's standard, and is answered from it.
    assert _route("What is our liability cap?") is None
    # "This agreement" may point at an earlier turn; "my" never has a source here.
    assert _route("Is this agreement enforceable?", prior=True) is None
    assert _route("What is my notice period?", prior=True) is not None


def test_a_vague_intent_gets_one_clarifying_question_and_a_specific_one_does_not():
    reply = _route("I want to talk with someone about a dispute.")
    assert reply is not None and reply.count("?") == 1
    assert _route("I have a payment dispute with a client") is None
    assert _route("I want to talk about the termination clause") is None
    assert _route("Can we terminate for convenience?", document=True) is None


def test_a_pasted_clause_is_material_whether_or_not_a_question_comes_with_it():
    clause = ("13.1 The total liability of the provider on all claims of any kind, "
              "whether based on contract, indemnity, warranty or tort, resulting from "
              "or connected with this Agreement or the Services, shall not exceed the "
              "fees paid in the three months before the claim. 13.2 Neither party is "
              "liable for indirect, special, incidental or consequential damages, lost "
              "profits or lost data, even if advised of their possibility, and these "
              "limits apply notwithstanding any failure of essential purpose.")
    assert attachments.carries_material(clause)
    assert attachments.split_paste(clause) == ("", clause)
    assert attachments.carries_material(clause + "\n\nIs this cap enforceable?")
    assert attachments.split_paste(clause + "\n\nIs this cap enforceable?")[0] == \
        "Is this cap enforceable?"
    # A question that is all question stays a question.
    assert not attachments.carries_material("Is the liability cap in this agreement "
                                            "enforceable?")
    assert not attachments.carries_material("Please check whether " + clause)


def test_the_fixed_lines_state_no_legal_content():
    for line in (conversational.REPLY[conversational.Social.GREETING],
                 conversational.needs_document("liability"),
                 conversational.vague_intent("I want to talk about a dispute")):
        lowered = line.lower()
        assert not any(w in lowered for w in ("enforceable", "complies", "12 months",
                                              "cap is", "you must"))


def test_the_brief_cites_only_entries_the_manifest_holds():
    manifest = capability.load(pathlib.Path(capability.MANIFEST_PATH))
    assert set(manifest["brief"]["evidence"]) <= {c["id"] for c in manifest["capabilities"]}
