"""`AM-109` — social turns in Ask: recognised, answered in fixed wording, never
retrieved against, and never read as a follow-up to the previous legal question."""
import pytest

from legalmind.assist.query import capability
from legalmind.assist.query import conversational as c
from legalmind.assist.query.conversational import Social


@pytest.mark.parametrize("q, want", [
    ("hi", Social.GREETING), ("Hello LegalMind!", Social.GREETING),
    ("hi there", Social.GREETING), ("Good morning", Social.GREETING),
    ("namaste", Social.GREETING), ("thanks", Social.THANKS),
    ("Thanks so much, team", Social.THANKS), ("shukriya", Social.THANKS),
    ("ok got it", Social.ACK), ("theek hai", Social.ACK),
    ("thanks, bye", Social.FAREWELL), ("thanks and bye", Social.FAREWELL),
    ("who are you?", Social.IDENTITY), ("help", Social.IDENTITY),
])
def test_a_turn_that_is_only_social_is_recognised(q, want):
    assert c.kind(q) == want


@pytest.mark.parametrize("q", [
    "hi, what is our liability cap?", "What is our liability cap?",
    "help me with the NDA", "Thanks — and for NDAs?", "Later amendments to clause 5?",
    "what can you do about the termination clause?", "ok", ])
def test_a_question_is_never_taken_for_small_talk(q):
    if q == "ok":
        assert c.kind(q) is Social.ACK
    else:
        assert c.kind(q) is None, q


@pytest.mark.parametrize("q, core", [
    ("Hi, what is our liability cap?", "What is our liability cap?"),
    ("Hi there, can you explain clause 7?", "Can you explain clause 7?"),
    ("Thanks — and for NDAs?", "And for NDAs?"),
    ("Great, and what about NDAs?", "And what about NDAs?"),
    ("OK, what is the cure period?", "What is the cure period?"),
    ("What is the notice period, thanks?", "What is the notice period?"),
    ("help me with the NDA", "Help me with the NDA"),
    ("Later amendments to clause 5?", "Later amendments to clause 5?"),
    ("Fine print in clause 3?", "Fine print in clause 3?"),
])
def test_a_social_lead_is_stripped_and_the_question_kept(q, core):
    assert c.strip_social(q) == core


def test_every_reply_states_no_legal_content():
    for text in c.REPLY.values():
        assert not any(w in text.lower() for w in ("month", "cap ", "liable", "shall"))


# --- through the service: no retrieval, no follow-up -------------------------------

PERMS = frozenset({"assist.ask", "legal_position.view"})


@pytest.fixture()
def no_retrieval(monkeypatch):
    """Every retrieval entry point raises: a social turn must reach none of them."""
    from legalmind.assist.knowledge import positions, statutes
    from legalmind.assist.query import routing
    from legalmind.assist.retrieval import retrieval

    def boom(*a, **k):
        raise AssertionError("a social turn reached retrieval")
    for mod, name in ((routing, "plan"), (positions, "search_positions"),
                      (statutes, "search_statutes"), (retrieval, "candidates")):
        monkeypatch.setattr(mod, name, boom)


def _ask(db, user, question, conv=None):
    from legalmind.assist import service
    conv = conv or service.create_conversation(db, user_id=user.id, contract_id=None)
    return conv, service.ask(db, conversation_id=conv, question=question,
                             document_version_id=None, permissions=PERMS,
                             request_id="req-social")


def test_hi_is_greeted_and_searches_nothing(db, user, no_retrieval):
    _, out = _ask(db, user, "hi")
    assert out.answer_state.value == "ANSWERED" and out.domains == ()
    assert out.text == c.REPLY[Social.GREETING]


def test_thanks_after_a_legal_question_does_not_re_answer_it(db, user, no_retrieval):
    """Before `AM-109`, "thanks" was a one-word follow-up and re-ran the previous
    question ("<prior question> thanks")."""
    from legalmind.assist import service
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    service._persist_turn(db, conv, 1, "USER", "What is our liability cap?")
    service._persist_turn(db, conv, 2, "ASSISTANT", "An earlier answer.")
    _, out = _ask(db, user, "thanks", conv)
    assert out.text == c.REPLY[Social.THANKS]


def test_who_are_you_is_answered_by_the_capability_manifest(db, user, no_retrieval):
    _, out = _ask(db, user, "who are you?")
    # The manifest's brief since `AM-118` r2; the full list is one request away.
    assert out.text == capability.answer()


def test_a_greeting_before_a_question_leaves_the_question_to_route(db, user,
                                                                    monkeypatch):
    from legalmind.assist.query import routing
    seen = []

    def spy(question, **k):
        seen.append(question)
        raise RuntimeError("stop here")
    monkeypatch.setattr(routing, "plan", spy)
    with pytest.raises(RuntimeError):
        _ask(db, user, "Hi, what is our liability cap?")
    assert seen == ["What is our liability cap?"]


def test_a_social_turn_is_not_a_prior_question(db, user):
    from legalmind.assist import service
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    for n, q in enumerate(["What is our liability cap?", "thanks", "Hi, and for NDAs?"]):
        service._persist_turn(db, conv, n + 1, "USER", q)
    last = service._persist_turn(db, conv, 9, "USER", "and the notice?")
    assert [q for _, q in service._prior_questions(db, conv, last)] == [
        "What is our liability cap?", "And for NDAs?"]


def test_a_document_type_is_a_scope_once_a_topic_is_named():
    """"What is our liability cap? and for NDAs?" is about liability for NDAs; reading
    "NDA" as Confidentiality answered the NDA survival period (`AM-109`)."""
    from legalmind.assist.query import planner, query_plan
    assert planner.topics_in("What is our liability cap? and for NDAs?") == {"Liability"}
    assert planner.topics_in("What is our NDA position?") == {
        "Confidentiality & Intellectual Property"}
    plan = query_plan.plan("What is our liability cap? and for NDAs?",
                           prior=("What is our liability cap?",))
    assert all(s.query.startswith("limitation of liability") for s in plan.sub_questions)


@pytest.mark.parametrize("q, off", [
    ("write me a poem about the sea", True), ("Write me a poem about contracts.", True),
    ("What is the weather in Pune today?", True), ("tell me a joke", True),
    ("give me a recipe for dal", True), ("Draft a termination clause", False),
    ("Can you write a summary of the NDA?", False), ("cooking the books clause", False),
    ("story of the parties in clause 2", False),
    ("tell me the story behind the indemnity clause", False),
    ("What is the liability cap in this agreement?", False)])
def test_an_out_of_scope_request_is_told_the_scope_and_a_legal_one_never(q, off):
    assert c.off_scope(q) is off


def test_an_out_of_scope_request_is_refused_without_a_search(db, user, no_retrieval):
    """The poem inherited "Confidentiality" from an earlier "and for NDAs?" and was
    answered from §15 (browser, 2026-09-29)."""
    _, out = _ask(db, user, "write me a poem about the sea")
    assert out.text == c.SCOPE_REPLY and out.answer_state.value == "NO_EVIDENCE_RETRIEVED"


def test_a_scope_word_in_an_earlier_turn_hands_down_no_topic():
    from legalmind.assist.query import query_plan
    plan = query_plan.plan("and what is the amount?",
                           prior=("What is our liability cap?", "and for NDAs?"))
    assert plan.topic == "Liability"


def test_a_chat_is_titled_by_its_first_real_question():
    from legalmind.api.routers.assist import _chat_title
    assert _chat_title(["hi", "Hi, what is our liability cap?"]) == \
        "What is our liability cap?"
    assert _chat_title(["thanks"]) == "thanks"          # only social: kept as asked
    assert _chat_title([]) is None and _chat_title(None) is None


@pytest.mark.parametrize("q, vague", [
    ("what about it?", True), ("tell me more", True), ("why?", True),
    ("and that?", True), ("what does it say", True),
    ("what about clause 7?", False), ("summarise it", False),
    ("what is the liability cap?", False),
    # 2026-09-29, live, first turn and no document: a request for a view on nothing.
    ("what is you take on this ?", True), ("your view on this", True),
    ("thoughts?", True), ("what is your opinion on it", True),
    ("your view on the liability cap", False), ("what do you think of clause 7?", False),
])
def test_a_question_with_no_subject_is_recognised(q, vague):
    from legalmind.assist.query import intent
    assert intent.has_no_subject(q) is vague


@pytest.mark.parametrize("q", ["what about it?", "what is you take on this ?"])
def test_a_first_turn_with_no_subject_is_asked_what_it_means(db, user, no_retrieval, q):
    _, out = _ask(db, user, q)
    assert out.text == c.REPLY[Social.UNCLEAR] and out.domains == ()


@pytest.mark.parametrize("q", ["tell me more", "what is you take on this ?"])
def test_the_same_words_after_a_question_are_a_follow_up(db, user, q):
    from legalmind.assist import service
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    service._persist_turn(db, conv, 1, "USER", "What is our liability cap?")
    service._persist_turn(db, conv, 2, "ASSISTANT", "An earlier answer.")
    _, out = _ask(db, user, q, conv)
    assert out.text != c.REPLY[Social.UNCLEAR]
