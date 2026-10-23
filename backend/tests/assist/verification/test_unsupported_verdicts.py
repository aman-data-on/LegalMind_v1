"""No acceptance and no "practice" the sources do not state (enterprise-readiness plan
D5(a), T4; `AM-181`). Production 2026-10-22, verbatim shapes: "accepting a 45-day notice
period from your customer is acceptable for ongoing arrangements"; "A 30-day quote
validity window is standard commercial practice"; "a 10-working-day dispute window and
fixed 12-month pricing align closely with commercial practice". None of our sources
says what commercial practice is, and whether to accept is a person's decision."""
import pytest

from legalmind.assist.verification import agent_verify as av

CONST = av.Evidence("C1", "Either party may terminate for convenience on 30 days' "
                    "written notice.", "§13", None, False, "constitution")
PRACTICE = av.Evidence("C2", "Under prevailing industry practice, renewal notices are "
                       "sent 30 days ahead.", "§31.9", None, False, "constitution")


def _codes(text, cites=("C1",), kind="sourced"):
    shown = {"C1": CONST, "C2": PRACTICE}
    return [x.check for x in av.verify([{"kind": kind, "text": text, "cites": list(cites)}],
                                       shown, document_selected=False, assessment="n/a")
            if x.check == "P13"]


@pytest.mark.parametrize("text", [
    "Accepting a 45-day notice period from your customer is acceptable for ongoing "
    "arrangements.",
    "A 30-day quote validity window is standard commercial practice.",
    "A 10-working-day dispute window and fixed 12-month pricing align closely with "
    "commercial practice.",
    "This is in line with industry standards.",
])
def test_an_unsupported_acceptance_or_practice_claim_is_refused(text):
    assert _codes(text) == ["P13"]


@pytest.mark.parametrize(("text", "cites"), [
    # a person decides: open, not a verdict
    ("Whether a 45-day notice is acceptable for this deal is a Legal decision.", ("C1",)),
    # the practice is what the cited record itself states
    ("Under prevailing industry practice, renewal notices are sent 30 days ahead.",
     ("C2",)),
    ("Either party may terminate for convenience on 30 days' written notice.", ("C1",)),
])
def test_an_open_question_or_a_stated_practice_is_not_a_verdict(text, cites):
    assert _codes(text, cites) == []


# ------------------------------------------------------------------- drafts (D5b, T6)
SLA = av.Evidence("C5", "Monthly uptime below 99.9% earns a 15% service credit; below "
                  "99.0%, 40%.", "Leapswitch Service Level Agreement · Service Credits",
                  None, False, "constitution")


def _draft_codes(text, conversation=frozenset()):
    return [x.check for x in av.verify(
        [{"kind": "draft", "text": text, "cites": []}], {"C5": SLA},
        document_selected=False, assessment="n/a", conversation_figures=conversation)
        if x.check == "V19"]


def test_a_draft_states_no_figure_that_no_source_and_no_reader_gave():
    # every figure from the shown SLA record: fine
    assert _draft_codes("Dear team, below 99.9% uptime a 15% credit applies, and below "
                        "99.0%, 40%.") == []
    # the reader's own figure from an earlier turn: fine
    assert _draft_codes("Dear team, we note your request for 45 days' notice.",
                        frozenset({"45"})) == []
    # a figure from nowhere: the draft would promise it to the client
    assert _draft_codes("Dear team, we confirm a 25% service credit and 60 days' "
                        "notice.") == ["V19"]


def test_a_date_a_clause_number_a_phone_or_a_ticket_is_not_a_promised_figure():
    assert _draft_codes("Dear team, on 20 October 2026 we reviewed Clause 7.2 and section "
                        "13 (Ticket 816661). Call +91 98200 00000 by 5 pm.") == []
    assert _draft_codes("Dear team, we can offer ₹2,750 for setup within 7 working "
                        "days.") == ["V19"]


def test_settle_says_why_it_dropped_each_block():
    """G25: 26 blocks of a 16-point answer were dropped and the turn log said nothing."""
    bad = {"kind": "general", "text": "Generally, notice is given.", "cites": ["C5"],
           "point": 4}
    good = {"kind": "sourced", "text": "Monthly uptime below 99.9% earns a 15% service "
            "credit.", "cites": ["C5"], "point": 6}
    reasons: list[str] = []
    out, dropped = av.settle([bad, good], {"C5": SLA}, [], document_selected=False,
                             reasons=reasons)
    assert dropped >= 1 and reasons and reasons[0].startswith("4:")
    assert "V5" in reasons[0]
