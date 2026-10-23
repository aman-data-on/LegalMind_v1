"""What our sources do not state is said plainly, with who confirms it (enterprise-
readiness plan D4, T10; `AM-182`). The model only CHOOSES the owner from a closed list;
the words are fixed configuration (Intercom/Copilot practice: handoff text is never
model-written). Pure functions — no database, no model."""
from legalmind.assist.agent import agent
from legalmind.assist.verification import agent_verify


def test_the_owner_survives_normalising_only_from_the_closed_list():
    out = agent_verify.normalise([
        {"kind": "next_step", "text": "Our documents do not state the setup fee.",
         "cites": [], "owner": "SALES", "point": 4},
        {"kind": "next_step", "text": "x", "cites": [], "owner": "the CEO"}])
    assert out[0]["owner"] == "SALES" and "owner" not in out[1]


def test_code_writes_who_confirms_and_sums_it_up_by_point():
    blocks = [
        {"kind": "sourced", "text": "Credits are 5% below 99.9%.", "cites": ["C1"],
         "point": 6},
        {"kind": "next_step", "text": "Our documents do not state the setup fee.",
         "cites": [], "owner": "SALES", "point": 4},
        {"kind": "next_step", "text": "Our documents do not state an RPO or RTO.",
         "cites": [], "owner": "OPERATIONS", "point": 2},
        {"kind": "reasoning", "text": "A 60-day exit departs from our 30 days.",
         "cites": [], "owner": "LEGAL", "point": 10}]
    out = agent.with_owners(blocks, points_asked=True)
    owners = agent.OWNERS
    assert out[1]["text"].endswith(owners["SALES"])
    assert out[2]["text"].endswith(owners["OPERATIONS"])
    assert out[3]["text"].endswith(owners["LEGAL"])
    assert out[0]["text"] == "Credits are 5% below 99.9%."
    summary = out[-1]
    assert summary["kind"] == "next_step" and summary["text"] == (
        "Before you reply: Sales team — point 4 · Solutions/Operations team — point 2 · "
        "Legal decides — point 10.")
    # no owner anywhere: nothing added
    assert agent.with_owners(blocks[:1], points_asked=True) == blocks[:1]


def test_an_unowned_not_stated_block_gets_its_owner_from_the_readers_point():
    """Gemini left "owner" empty on every block in 3 of 3 runs (2026-10-22); a block
    that says our documents do not state the point gets the owner the point's own words
    name — a price to Sales, a technical commitment to Operations — or none."""
    texts = {2: "Disaster recovery - confirm a committed RPO of 1 hour and RTO of 4 hours",
             4: "Load balancer and one-time cost - what the setup cost covers",
             9: "Term - 12 months from acceptance"}
    blocks = [
        {"kind": "reasoning", "cites": [], "point": 2,
         "text": "Our documents do not state an RPO or RTO commitment."},
        {"kind": "reasoning", "cites": [], "point": 4,
         "text": "No record states what the one-time setup cost covers."},
        {"kind": "reasoning", "cites": [], "point": 9,
         "text": "Our documents do not state this term."},
        {"kind": "sourced", "cites": ["C1"], "point": 2,
         "text": "Backups are the customer's responsibility."}]
    out = agent.with_owners(blocks, points_asked=True, point_texts=texts)
    assert out[0]["text"].endswith(agent.OWNERS["OPERATIONS"])
    assert out[1]["text"].endswith(agent.OWNERS["SALES"])
    assert out[2]["text"] == blocks[2]["text"]          # nothing names an owner
    assert out[3]["text"] == blocks[3]["text"]          # a sourced claim is not a gap


def test_an_uncited_not_stated_block_is_reasoning_not_a_failed_sourced_claim():
    """DeepSeek wrote "our documents do not state …" as kind "sourced" with no cites; V1
    dropped every such block and 5 of 17 points were lost (final eval, 2026-10-23). A
    sentence saying no record states something claims nothing from a record."""
    blocks = [{"kind": "sourced", "cites": [], "point": 2,
               "text": "Our documents do not state an RPO or RTO commitment."},
              {"kind": "sourced", "cites": [], "point": 3,
               "text": "Backups are daily."},
              {"kind": "sourced", "cites": ["C1"], "point": 4,
               "text": "Our documents do not state the setup fee."}]
    out = agent.uncited_gaps_as_reasoning(blocks)
    assert [b["kind"] for b in out] == ["reasoning", "sourced", "sourced"]
