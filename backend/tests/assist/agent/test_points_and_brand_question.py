"""The reader's list is answered whole, found again on a follow-up, and a brand that only
the reader can settle is asked for once (enterprise-readiness plan P2: D3, D4, T9, T12;
`AM-202`). Pure functions — no database, no model."""
from __future__ import annotations

from legalmind.assist.agent import agent, points

EMAIL = ("1. Scope (compute) - LeapSwitch to confirm the billing basis.\n"
         "2. Disaster recovery - LeapSwitch to confirm a committed RPO and RTO.\n"
         "3. Backup - LeapSwitch to confirm daily backups.\n"
         "4. Term - 12 months from acceptance, renewed automatically.")


# --------------------------------------------------- a pasted list IS the question
def test_a_message_that_is_only_a_list_asks_about_every_point():
    """Saba's 16 points were answered as points only because point 13 happened to say
    "changes" (an `_ABOUT_THEM` cue). A pasted list with no cue word was not."""
    listed = points.enumerate_points(EMAIL)
    assert len(listed) == 4
    assert points.asked(listed, EMAIL) == []                 # no cue word in it
    assert agent.asked_points_for(listed, EMAIL, own=True) == listed
    # a question that merely contains a short list still needs a cue
    question = ("Our standard says 30 days. The client wants:\n1. 60 days\n2. 45 days\n"
                "3. 90 days\n\nWhat is the market norm, and why does our MSA differ from "
                "the client's long explanation of how its procurement works internally?")
    assert agent.asked_points_for(points.enumerate_points(question), question,
                                  own=True) == []


# ----------------------------------------------- the list from an earlier turn (G7)
def test_answer_points_9_and_10_finds_the_list_in_an_earlier_message():
    window = [("USER", EMAIL), ("ASSISTANT", "Your message lists 4 points; 2 are …")]
    listed = agent.list_from_window(window)
    assert [p.n for p in listed] == [1, 2, 3, 4]
    assert [p.n for p in points.asked(listed, "answer points 3 and 4")] == [3, 4]
    assert agent.list_from_window([("USER", "what is the late fee?")]) == []


# ----------------------------------------------------- the brand only the reader knows
def test_the_company_name_alone_asks_which_brand_once():
    assert agent.needs_brand_question(EMAIL, [], brand=None, document_selected=False)
    # a brand named, a document selected, or a brand set by an earlier turn: no question
    assert not agent.needs_brand_question(EMAIL + "\nThis is for CloudPe.", [],
                                          brand="CloudPe", document_selected=False)
    assert not agent.needs_brand_question(EMAIL, [], brand=None, document_selected=True)
    # no mention of the company at all: a general question, answered for both brands
    assert not agent.needs_brand_question("what is our late fee?", [], brand=None,
                                          document_selected=False)
    # asked once: never again straight after the question
    asked = [("USER", EMAIL), ("ASSISTANT", agent.BRAND_QUESTION)]
    assert not agent.needs_brand_question(EMAIL, asked, brand=None,
                                          document_selected=False)
    assert "CloudPe or Leapswitch" in agent.BRAND_QUESTION
    # mid-conversation: earlier turns answered for both brands, so a fixed question now
    # is the T18 defect (production replay 2026-10-23)
    answered = [("USER", "what is the termination notice?"), ("ASSISTANT", "30 days.")]
    assert not agent.needs_brand_question(EMAIL, answered, brand=None,
                                          document_selected=False)


def test_the_readers_answer_to_the_brand_question_answers_their_earlier_message():
    window = [("USER", EMAIL), ("ASSISTANT", agent.BRAND_QUESTION)]
    assert agent.resumed_by_brand("cloudpe", window) == (EMAIL, "CloudPe")
    assert agent.resumed_by_brand("its for the leapswitch dedicated servers", window) == (
        EMAIL, "Leapswitch")
    # not an answer to the question: the turn stands as asked
    assert agent.resumed_by_brand("what is the late fee?", window) is None
    assert agent.resumed_by_brand("cloudpe", [("USER", EMAIL)]) is None


# ------------------------------------------------------------ lettered sub-points (D3)
def test_a_points_lettered_asks_are_read_and_the_uncovered_ones_named():
    """The 16-point email's sub-asks — 1(b) public IP, 4(d) data in India — were covered
    by one generic line each, or not at all (audit, 2026-10-22)."""
    text = ("Scope - LeapSwitch to confirm: (a) the billing basis; (b) whether public IP "
            "is included; (c) pricing for additional storage.")
    assert points.sub_items(text) == ["a", "b", "c"]
    assert points.sub_items("Term - 12 months from acceptance.") == []
    listed = [points.Point(1, "Scope", text), points.Point(9, "Term", "Term - 12 months.")]
    blocks = [{"kind": "sourced", "point": 1, "cites": ["C1"],
               "text": "(a) Billing is monthly in advance."},
              {"kind": "reasoning", "point": 1, "cites": [],
               "text": "(c) Our documents do not state storage pricing."}]
    assert points.uncovered_subs(listed, blocks) == ["1(b)"]
    assert "1(b)" in points.uncovered_line(["1(b)"])


def test_a_plain_question_or_email_naming_the_company_is_not_asked_which_brand():
    """P2 run, 2026-10-22: the brand question fired on "what is the late fee on overdue
    invoices for leapswitch?" and on a client's MSA email — on all three models. A short
    question naming Leapswitch means the brand; an email that is not a list of asks or a
    proposal is answered, both brands labelled (CLAMBER: models — and rules — over-ask)."""
    from legalmind.assist.knowledge import published
    assert published.reader_brands(
        "what is the late fee on overdue invoices for leapswitch?") == {"Leapswitch"}
    assert published.reader_brands("Termination \u2013 LeapSwitch to confirm the charges") == set()
    email = ("Client email below, pls check what they want: Dear team, we reviewed the "
             "MSA. Please confirm that LEAPSWITCH ACCEPTS UNLIMITED LIABILITY. Also we need "
             "30 days notice for any price change and a monthly invoice. Regards")
    assert not agent.needs_brand_question(email, [], brand=None, document_selected=False)
    proposal = "LeapSwitch to confirm the hourly and monthly pricing in the proposal."
    assert agent.needs_brand_question(proposal, [], brand=None, document_selected=False)


def test_blocks_without_a_point_number_are_given_one_in_the_readers_order():
    """DeepSeek answered all 16 points in order but set no "point" field, so the count
    read 0 of 16 (P2 run, 2026-10-22). Code places each unnumbered block on the point
    its words match, never moving backwards; one with no match stays on the last."""
    asked = [points.Point(1, "Scope", "Scope - billing basis, public IP, storage pricing"),
             points.Point(2, "Disaster recovery", "Disaster recovery - RPO, RTO, DR drills"),
             points.Point(3, "Backup", "Backup - daily backups, immutable copy")]
    blocks = [{"kind": "reasoning", "text": "Our documents do not state the billing basis "
               "or storage pricing."},
              {"kind": "sourced", "text": "For MSA agreements, the position is …",
               "cites": ["C8"]},
              {"kind": "reasoning", "text": "Our documents do not state an RPO, RTO or DR "
               "drills."},
              {"kind": "reasoning", "text": "No daily backups or immutable copy are stated."},
              {"kind": "next_step", "text": "Sales team to confirm.", "point": 1}]
    out = points.assign_points(blocks, asked)
    assert [b.get("point") for b in out] == [1, 1, 2, 3, 1]


def test_a_list_that_names_both_brands_is_never_asked_which_brand():
    """Harder case C16, all three models (2026-10-23): a list naming "cloudpe VM" and
    "leapswitch dedicated server" was asked "CloudPe or Leapswitch?" — the reader had
    already said, for each point. Naming a brand at all settles the question."""
    both = ("client ke 4 sawal hai pls point wise batao\n1. cloudpe VM ka uptime kya hai\n"
            "2. leapswitch dedicated server ka service credit kitna milega\n"
            "3. dono me late fee kitni hai\n4. data kitne din tak rakhte ho exit ke baad")
    assert not agent.needs_brand_question(both, [], brand=None, document_selected=False)


def test_a_short_answer_never_costs_a_point():
    """Harder case C18: "answer in 2 lines only but cover all of these" (10 points) —
    DeepSeek answered 2 of 10, Bonsai 0; Gemini, told by our own code "The user asked for 2
    2 bullet points", wrote two blocks of five points each, both rejected (`AM-205`, 2026-10-26).
    The limit shortens each point, never their number — and code says so in so many words."""
    ask = "answer in 2 lines only but cover all of these"
    said = agent._final_instruction("en", ask, points=True)
    assert "exactly 2" not in said
    assert "limits each point, never their number" in said
    assert "exactly 2 of them." in agent._final_instruction("en", ask)  # no list: as asked
