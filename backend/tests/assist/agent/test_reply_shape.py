"""`AM-235` (2026-10-29): a salesperson asked for an email and got the company's
positions again, word for word, two replies running; the email came on the third
asking, under a "Delta: not comparable" row. Synthetic text, no client named. No
database, no model."""
import pytest

from legalmind.assist.agent import agent
from legalmind.assist.query import presentation
from legalmind.assist.verification import agent_verify as av


@pytest.mark.parametrize("message", [
    "please prepare a email for this", "Draft a reply to the client",
    "please let me know what i should reply to him", "what should we respond",
    "write an email to the customer about the SLA", "mail likh do", "reply bana do",
    "can you compose a short response"])
def test_a_request_to_write_something_to_send_is_read(message):
    shown = presentation.read(message)
    assert shown.write
    assert not shown.document_task          # a reply never narrows what is searched


@pytest.mark.parametrize("message", [
    "please check this document and let me know the below answers",
    "does the draft email mention the cap?", "is your draft reply ok",
    "the customer sent an email asking about credits"])
def test_a_question_about_an_email_is_not_a_request_to_write_one(message):
    assert not presentation.read(message).write


def test_the_turn_is_told_the_draft_is_the_answer():
    assert "WRITE something to send" in agent._final_instruction(
        "en", "please prepare a email for this")
    assert "WRITE something to send" not in agent._final_instruction("en",
                                                                     "What is the cap?")


TERMINATION = ("The termination position for ongoing arrangements is 30 days written "
               "notice for convenience and a 30-day cure period for cause.")
EARLIER = f"The email asks us to confirm four points.\n\n{TERMINATION}"


def _blocks():
    return [{"kind": "reasoning", "text": "Reply confirming nothing yet.", "cites": []},
            {"kind": "sourced", "text": TERMINATION, "cites": ["C6"]},
            {"kind": "sourced", "text": "The back-to-back right is new exposure.",
             "cites": ["C10"]},
            {"kind": "draft", "text": TERMINATION, "cites": []}]


def test_a_point_an_earlier_reply_made_is_not_said_again():
    kept = av.fresh(_blocks(), [EARLIER])
    assert [b["text"][:12] for b in kept] == ["Reply confir", "The back-to-",
                                              TERMINATION[:12]]
    # the opening point and a draft stay, whatever they repeat
    opening = [{"kind": "sourced", "text": TERMINATION, "cites": ["C6"]}]
    assert av.fresh(opening, [EARLIER]) == opening


@pytest.mark.parametrize("flags", [{"again": True}, {"keep_review": True}])
def test_asked_again_or_for_the_whole_situation_every_point_stays(flags):
    assert av.fresh(_blocks(), [EARLIER], **flags) == _blocks()


def test_a_recap_a_recheck_or_the_same_question_asks_again():
    window = [("USER", "What is our termination notice period?"), ("ASSISTANT", "x")]
    assert agent.asks_again("recap the points please", window)
    assert agent.asks_again("are you sure?", window)
    assert agent.asks_again("what is our termination notice period", window)
    assert not agent.asks_again("please prepare a email for this", window)


def _comparison(agreement, standard):
    return {"kind": "sourced", "text": "They differ on what an early exit costs.",
            "compare": {"agreement": agreement, "agreement_cite": "U4",
                        "standard": standard, "standard_cite": "C7"}}


def test_a_difference_code_cannot_measure_shows_no_delta_row():
    lines = av._compare_lines(_comparison("no termination for convenience in the "
                                          "lock-in", "full committed-term value "
                                                     "payable"), {})
    assert "Delta" not in lines and "not comparable" not in lines
    assert lines.endswith("They differ on what an early exit costs.")
    measured = av._compare_lines(_comparison("90 days notice", "30 days notice"), {})
    assert "Delta: 90 days against 30 days" in measured


def test_the_answer_block_cap_never_cuts_the_draft():
    blocks = [{"kind": "sourced", "text": str(n)} for n in range(10)] + [
        {"kind": "draft", "text": "Dear customer"}]
    kept = agent.kept_to(blocks)
    assert kept[-1]["kind"] == "draft" and len(kept) == agent.ANSWER_BLOCKS + 1
