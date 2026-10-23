"""D1 (owner, 2026-10-07): a numbered list asked about as a whole is answered point by
point and counted — a 17-point e-mail had been answered on 4 to 6 points. Synthetic text
only (rule 21); a scripted model, so no test spends a call."""
from __future__ import annotations

import json

from legalmind.assist import service
from legalmind.assist.agent import agent, points, tools
from tests.assist.agent.test_assist_agent import PERMS, Scripted

LIST = ("Dear team, our requested changes to the MSA:\n\n"
        "1. Contract Term — reduce the minimum term to six months.\n"
        "2. Early Termination — allow exit on 30 days' notice\n"
        "   without any early termination fee.\n"
        "3. Auto-Renewal — remove automatic renewal.\n"
        "4. Payment Terms — 45 days from invoice.\n"
        "5. Governing Law — the courts of Mumbai.\n\n"
        "Regards, a customer")


def test_a_numbered_list_is_read_with_its_continuations_and_titles():
    found = points.enumerate_points(LIST)
    assert [p.n for p in found] == [1, 2, 3, 4, 5]
    assert found[1].title == "Early Termination"
    assert "without any early termination fee" in found[1].text       # continued line
    assert points.enumerate_points("1. One thing.\n2. Another.") == []    # too short


def test_which_points_a_question_asks_about():
    found = points.enumerate_points(LIST)
    assert len(points.asked(found, "Which of these conflict with our standards?")) == 5
    assert [p.n for p in points.asked(found, "answer points 2 to 4")] == [2, 3, 4]
    assert [p.n for p in points.asked(found, "answer points 1, 3 and 5")] == [1, 3, 5]
    assert points.asked(found, "Does the indemnity survive termination?") == []
    for yes in ("Answer each point.", "Which of them conflict with our standard?",
                "What about every request?", "Compare all of them with our standards.",
                "How do these compare with the MSA?"):
        assert len(points.asked(found, yes)) == 5, yes


def test_a_question_that_only_shares_a_word_with_the_list_is_not_about_it():
    """Two documents in one chat: an MSA and an attached NDA whose 15 clauses are
    numbered. "Which of the two has the longer period?" took the NDA's clauses for
    points to answer (2026-10-08)."""
    nda = "\n".join(f"{n}. Clause {n} — the receiving party shall do thing {n}."
                    for n in range(1, 16))
    found = points.enumerate_points(nda)
    assert len(found) == 15
    for no in ("Which of the two has the longer confidentiality period?",
               "Which of the agreements is mutual?",
               "Does each party owe the same notice?",
               "Is every payment due within 30 days?",
               "Any of the exceptions apply here?",
               "What does the attached agreement say about confidentiality, and what "
               "does the MSA say?"):
        assert points.asked(found, no) == [], no


def _blocks(*ns):
    return json.dumps({"analysis": "", "assessment": "n/a", "blocks": [
        {"kind": "reasoning", "point": n, "text": f"On point {n}, no ratified standard "
         "addresses this request directly."} for n in ns]})


class Pages(Scripted):
    """Answers the first page with points 1–3, the follow-up for the missing ones with
    point 4 only — point 5 is never answered, so it must be named."""

    def __init__(self):
        super().__init__()
        self.answers = [_blocks(1, 2, 3), _blocks(4)]

    def turn(self, *a, **k):
        super().turn(*a, **k)                       # recorded, as every fake call is
        return agent.generation.TurnResult(
            text=self.answers.pop(0) if self.answers else _blocks(), model="fake-model",
            prompt_version="x", payload_sha256="0" * 64, latency_ms=1, prompt_tokens=1,
            output_tokens=1, model_version="v", parts=({"text": "x"},), function_calls=())


def test_every_asked_point_is_answered_or_named_and_the_reply_counts_them(db, user):
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    p = Pages()
    t = agent.run_turn(p, ctx, LIST + "\n\nWhich of these conflict with our standards?")
    assert p.seen and all(s["tools"] is None for s in p.seen)       # no decision step
    sent = json.dumps(p.seen[0]["contents"])
    assert "THE USER'S NUMBERED POINTS" in sent and "5. Governing Law" in sent
    assert p.seen[0]["answer_tokens"] == agent.POINTS_ANSWER_TOKENS
    assert "points:4/5" in t.flags                            # requested 5, answered 4
    text = t.text()
    assert text.startswith("Your message lists 5 points; 4 are answered below")
    assert "**1. Contract Term**" in text and "**4. Payment Terms**" in text
    assert text.index("**1. Contract Term**") < text.index("**4. Payment Terms**")
    assert "Not answered in this reply: 5. Governing Law" in text      # named, not lost


def test_an_ordinary_question_after_a_list_is_answered_as_before(db, user):
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    p = Scripted()
    t = agent.run_turn(p, ctx, "What is our standard early termination position?")
    assert not t.point_titles and not any(f.startswith("points:") for f in t.flags)


def test_a_floor_in_points_mode_names_every_asked_point(db, user):
    """D1 + D2: when nothing could be answered, the reply says why and lists every point."""
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    t = agent.run_turn(Scripted(fail_final=True), ctx,
                       LIST + "\n\nWhich of these conflict with our standards?")
    text = t.text()
    assert t.outcome == "floor" and "could not be reached just now" in text
    assert "Not answered in this reply: 1. Contract Term" in text and "5. Governing Law" in text


def test_an_agreements_own_sections_are_not_the_readers_points():
    """An attached addendum's section headings were answered as "your message lists 7
    points" (2026-10-14): numbered sections over 1.1, 1.2 … are an agreement, not
    requests. Synthetic text (rule 21)."""
    outline = ("1. DEFINITIONS\n1.1 Terms have their meaning.\n1.2 Headings are labels.\n"
               "2. TERM\n2.1 The term is one year.\n3. PAYMENT\n3.1 Fees are monthly.\n"
               "4. NOTICES\n4.1 Notice is by email.\n")
    assert points.enumerate_points(outline) == []
    assert len(points.enumerate_points(LIST)) == 5                   # a request list stays


# 2026-10-14, a live conversation (synthetic stand-ins here, rule 21): a sales manager
# attached our own proposal, whose "Additional Details" are numbered 1-5, and pasted the
# client's e-mail — three UNNUMBERED asks, then "Please confirm on the above points."
# The e-mail's asks went unread and the quote's five terms were answered instead.
ASKS = ("With your mentioned SLA & Support please let us know what will be the SLA "
        "Breach Penalty clause ?",
        "Uptime mentioned is 99.99% for a single year.",
        "Need acceptance on termination: If our customer terminates the service with us "
        "we will also terminate the same with Leapswitch with a notice period of 45 days.")
EMAIL = ("I have shared this proposal of dedicated Servers and now client asked me about "
         "below points on email\n\nDear Swapnil,\n\n \n\n" + "\n".join(ASKS)
         + "\n\nPlease confirm on the above points.")
QUOTE_TERMS = ("Additional Details:\n"
               "1. This quotation is valid for a contract period of Two (2) years.\n"
               "2. The scope of services is limited to the items in this quotation.\n"
               "3. Items not stated in the quotation are outside the scope.\n"
               "4. Pricing may be revised on written communication and acceptance.\n"
               "5. This quotation is valid for thirty (30) days from issuance.\n")


def test_unnumbered_asks_the_message_points_at_are_the_points():
    found = points.enumerate_points(EMAIL)
    assert [p.text for p in found] == list(ASKS)
    assert found[2].title == "Need acceptance on termination"
    assert len(points.asked(found, EMAIL)) == 3
    following = "Please answer the following points:\n" + "\n".join(ASKS)
    assert [p.text for p in points.enumerate_points(following)] == list(ASKS)


def test_bulleted_asks_are_the_points():
    bulleted = "\n".join("• " + a for a in ASKS) + "\nPlease confirm on the above points."
    assert [p.text for p in points.enumerate_points(bulleted)] == list(ASKS)
    assert [p.text for p in points.enumerate_points(
        "\n".join("- " + a for a in ASKS))] == list(ASKS)


def test_prose_is_never_split_into_points():
    prose = ("Our customer wants a longer notice period.\nThey also asked about credits."
             "\nAnd about uptime.")
    assert points.enumerate_points(prose) == []                      # no reference
    assert points.enumerate_points("Two lines.\nOnly two.\n\nSee the above points.") == []
    long = "\n".join(f"Line {n} of a long paragraph." for n in range(20))
    assert points.enumerate_points(long + "\n\nPlease confirm on the above points.") == []


def test_an_uploaded_files_numbered_terms_are_never_the_readers_points(db, user):
    from tests.assist.agent.test_assist_attachments import _add
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    _add(db, conversation_id=conv, data=QUOTE_TERMS.encode(), kind="FILE",
         filename="quote.txt", mime="text/plain")
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    t = agent.run_turn(Scripted(), ctx, EMAIL)
    assert sorted(t.point_titles) == [1, 2, 3]
    assert t.point_titles[2].startswith("Uptime mentioned is 99.99%")
    assert not any("quotation" in title for title in t.point_titles.values())
    # a question about the file's own list still reads it as the document, not as asks
    t2 = agent.run_turn(Scripted(), ctx, "Which of these terms should we change?")
    assert not t2.point_titles


def test_a_long_pasted_list_is_still_the_readers_points(db, user):
    from tests.assist.agent.test_assist_attachments import _add
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    _add(db, conversation_id=conv, data=LIST.encode(), kind="PASTE")
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    t = agent.run_turn(Scripted(), ctx, "Please answer each point.")
    assert sorted(t.point_titles) == [1, 2, 3, 4, 5]


def test_points_from_the_message_are_sent_whole_and_never_restated_as_material(db, user):
    """The model saw "1. With your mentioned SLA & Support please let us know what will
    be the" — the 70-character title — and was told to restate each point "citing the
    material", so it cited the attached quote for the e-mail's own words."""
    from tests.assist.agent.test_assist_attachments import _add
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    _add(db, conversation_id=conv, data=QUOTE_TERMS.encode(), kind="FILE",
         filename="quote.txt", mime="text/plain")
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    p = Scripted()
    agent.run_turn(p, ctx, EMAIL)
    sent = json.dumps([s["contents"] for s in p.seen], ensure_ascii=False)
    assert "what will be the SLA Breach Penalty clause ?" in sent
    assert "do not restate it and never cite a file for it" in sent
    assert "user_stated, citing the material" not in sent


def test_points_from_a_paste_are_still_restated_citing_it(db, user):
    from tests.assist.agent.test_assist_attachments import _add
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    _add(db, conversation_id=conv, data=LIST.encode(), kind="PASTE")
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    p = Scripted()
    agent.run_turn(p, ctx, "Please answer each point.")
    sent = json.dumps([s["contents"] for s in p.seen], ensure_ascii=False)
    assert "user_stated, citing the material" in sent


def test_a_restated_message_point_is_never_shown(db, user):
    """Told not to, the model still restated each e-mail ask and cited the attached
    quote for it — twice per point, 1 run in 2 (2026-10-14). A point from the message
    has no restatement to show: it is answered, or named as not answered."""
    from tests.assist.agent.test_assist_attachments import _add
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    _add(db, conversation_id=conv, data=QUOTE_TERMS.encode(), kind="FILE",
         filename="quote.txt", mime="text/plain")
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    final = json.dumps({"analysis": "", "assessment": "n/a", "blocks": [
        {"kind": "user_stated", "point": n, "cites": [],
         "text": f"Your customer asked about point {n} in their e-mail."}
        for n in (1, 2, 3)] + [
        {"kind": "reasoning", "point": 1, "cites": [],
         "text": "On point 1, no ratified standard addresses this request directly."}]})
    t = agent.run_turn(Scripted(final=final), ctx, EMAIL)
    text = t.text()
    assert "Your customer asked about point" not in text
    assert "points:1/3" in t.flags
    assert "Not answered in this reply: 2. Uptime mentioned is 99.99%" in text


class SlowPages(Pages):
    """The first page took longer than the turn has left (D7, `AM-184`)."""

    def turn(self, *a, **k):
        r = super().turn(*a, **k)
        return agent.dataclasses.replace(r, latency_ms=10 * 60 * 1000)


def test_no_re_ask_starts_without_time_for_a_call_as_long_as_the_last(db, user):
    """A re-ask that starts with 2 s left gets FINAL_MIN_S (30 s) and runs the turn past
    the client's 150 s; it now starts only with as much time left as the call before it
    took — the rule the lean pages already follow — and what is missing is named."""
    conv = service.create_conversation(db, user_id=user.id, contract_id=None)
    ctx = tools.ToolContext.open(db, user_id=user.id, permissions=PERMS,
                                 conversation_id=conv)
    p = SlowPages()
    t = agent.run_turn(p, ctx, LIST + "\n\nWhich of these conflict with our standards?")
    assert len(p.seen) == 1                                   # no second call
    assert "points:3/5" in t.flags and "points:no_time" in t.flags
    assert "Not answered in this reply: 4. Payment Terms; 5. Governing Law" in t.text()
