"""The Ask pre-router in a conversation — the enterprise test record
`docs/08-testing/ASK_PREROUTE_TEST.md`, case for case (live, 2026-10-22).

A reader pasted a client's 16-point list, got an answer, then asked twice: "can you fetch
the above details & reframe the answer as per the cloudpe product ?". Both times the
pre-router replied with the product brief in 4–7 ms, with no search and no model call,
because `intent.is_capability_question` reads the message alone.

The messages are written the way the production log's readers write: lower case, no
punctuation, "u", "pls", fragments, Roman Hinglish, and no Devanagari, which no reader
has typed. The IDs match the record's table; the "why" of each failure is its §6.
"""
from __future__ import annotations

import pytest

from legalmind.assist import service

FIRST = {"has_prior": False, "has_document": False, "has_material": False,
         "prior_offer": False}
# The live chat: an answer given, the reader's paste in it, no contract, and the answer
# ended on an offer ('Ask "answer points 9, 10"').
MID = {"has_prior": True, "has_document": False, "has_material": True,
       "prior_offer": True}

REACHES_THE_ANSWER = [
    ("F1", "can you fetch the above details & reframe the answer as per the cloudpe product ?"),
    ("F2", "can you do same for cloudpe"),
    ("F3", "can you give me same answer but for cloudpe product"),
    ("F4", "client asking same for cloudpe can you check"),
    ("O1", "can u also ans point 9 n 10"),
    ("O2", "ok can you do that"),
    ("T1", "can you write mail to client for above"),
    ("T2", "can you make it short"),
    ("T3", "can you put this in table"),
    ("T4", "please draft a email"),
    ("H1", "isko cloudpe ke hisab se kar sakte ho kya"),
    ("H2", "aap ye cloudpe ke liye bana sakte ho"),
    ("H3", "tum isme kya help kar sakte ho"),
    ("H4", "same cheez cloudpe ke liye batao"),
    ("S1", "ok thanks can you do for cloudpe also"),
    ("S2", "hi can you check point 15 again"),
    ("U1", "not sure what to tell client can you help"),
    ("U2", "can you help"),
    ("U3", "what can you do with this"),
    ("R1", "CAN YOU REFRAME FOR CLOUDPE"),
    ("R2", "can you pls do it 4 cloudpe"),
    # mid-conversation even a real product question is the model's to read — it calls
    # `show_capabilities` when it is one (`AM-200` r1)
    ("M1", "what else can you do"),
]

GETS_A_FIXED_REPLY = [
    ("C1", FIRST, "what can you do"),
    ("C2", FIRST, "legalmind kya kar sakta hai"),
    ("C3", FIRST, "how can you help me"),
    ("C4", FIRST, "who are you"),
    ("C5", FIRST, "what are you capable of"),
    ("X1", MID, "tell me a joke"),
    ("X2", FIRST, "whats the weather in pune today"),
]


@pytest.mark.parametrize(("case", "message"), REACHES_THE_ANSWER,
                         ids=[c[0] for c in REACHES_THE_ANSWER])
def test_a_follow_up_mid_task_reaches_the_answer_path(case, message):
    assert service.preroute(message, **MID) is None, case


@pytest.mark.parametrize(("case", "ctx", "message"), GETS_A_FIXED_REPLY,
                         ids=[c[0] for c in GETS_A_FIXED_REPLY])
def test_a_question_about_the_product_or_off_topic_gets_a_fixed_reply(case, ctx, message):
    assert service.preroute(message, **ctx) is not None, case


def test_a_general_task_outside_ask_is_left_to_the_model():
    """X3: a fixed-word list for every task Ask is not for would refuse "the code of
    conduct clause"; the model declines it instead (record §6 R-7)."""
    assert service.preroute("write me a python script", **FIRST) is None
