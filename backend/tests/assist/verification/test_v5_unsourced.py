"""V5 (`AM-220`): an answer that cites nothing never states what our sources say. The
two failures are C26's turns 10 and 34 (2026-10-27); the passes are what the rule must
leave alone. No database, no model."""
from legalmind.assist.verification import agent_verify as av

CONST16 = av.Evidence("C16", "Late payments attract interest at 2% per month.", "§16", None,
                      False, "constitution")


def v5(blocks, shown=None, readers=frozenset()):
    return [x.detail for x in av.verify(blocks, shown or {"C16": CONST16},
                                        document_selected=False, assessment="n/a",
                                        reader_figures=readers) if x.check == "V5"]


def reasoning(text):
    return {"kind": "reasoning", "text": text, "cites": []}


def test_a_follow_up_answered_from_memory_with_no_citation_fails():
    assert v5([reasoning("Which rate sales should quote depends on the governing "
                         "agreement: quote 5% per month after 5 days for online TOS "
                         "customers, and 2% per month for custom MSA agreements.")])
    assert v5([reasoning("Both positions align in capping maximum financial liability at "
                         "a year of fees and excluding indirect damages.")])


def test_the_same_sentence_beside_a_cited_record_is_the_allowed_lead():
    lead = reasoning("The rate depends on the agreement: 2% per month for an MSA, which "
                     "both positions treat alike.")
    cited = {"kind": "sourced", "text": "Late payments attract interest at 2% per month.",
             "cites": ["C16"]}
    assert v5([lead, cited]) == []


def test_what_is_missing_the_readers_own_figure_and_a_fixed_reply_pass():
    assert v5([reasoning("Our existing policy documents and Constitution do not state a "
                         "force majeure termination period for MSA agreements.")]) == []
    assert v5([reasoning("You asked for a 45-day payment cycle; that needs Legal.")],
              readers=frozenset({"45"})) == []
    assert v5([{"kind": "prerouted", "text": "I review contracts against our approved "
                "positions and standards.", "cites": []}]) == []
