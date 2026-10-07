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
