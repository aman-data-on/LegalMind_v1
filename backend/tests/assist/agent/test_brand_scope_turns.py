"""The brand a turn answers for is decided in code, once, and holds everywhere — search,
earlier turns' evidence and the verifier (enterprise-readiness plan D1/D2, `AM-181`).

Production 2026-10-22: a client's email said "LeapSwitch to confirm" fourteen times about
a CloudPe cloud proposal. "LeapSwitch" there is the COMPANY (Leapswitch Networks runs
both brands), so the first answer searched only Leapswitch policies; the reader then
asked for "the cloudpe product" and the earlier turn's Leapswitch records (C7, C15, C34)
were re-offered from the ledger and cited again. No database, no model.
"""
from __future__ import annotations

from uuid import uuid4

import pytest

from legalmind.assist.agent import agent, ledger, tools
from legalmind.assist.knowledge import published
from legalmind.assist.verification import agent_verify


# ---------------------------------------------------------------- the reader's brand
@pytest.mark.parametrize(("text", "brands"), [
    ("can you fetch the above details & reframe the answer as per the cloudpe product ?",
     {"CloudPe"}),
    ("what is the service credit for downtime under the leapswitch sla?", {"Leapswitch"}),
    ("after how many days of non payment can we suspend a leapswitch customer?",
     {"Leapswitch"}),
    ("LeapSwitch Dedicated Server SLA penalty", {"Leapswitch"}),
    # the company, not the brand: "LeapSwitch to confirm", "caused by LeapSwitch"
    ("1. Scope - LeapSwitch to confirm the billing basis. 15. Liability - costs caused "
     "by LeapSwitch to be recoverable.", set()),
    ("Leapswitch Networks Pvt. Ltd. and the client agree", set()),
    ("compare the cloudpe sla and the leapswitch sla", {"CloudPe", "Leapswitch"}),
    ("what is our uptime commitment?", set()),
    # the product names the brand: each brand's own published SLA lists its products
    ("I have shared this proposal of dedicated Servers; LeapSwitch to confirm the SLA",
     {"Leapswitch"}),
    ("client needs 4 GPU compute instances and two virtual machines", {"CloudPe"}),
])
def test_a_brand_is_read_from_the_readers_words_never_from_the_company_name(text, brands):
    assert published.reader_brands(text) == brands


def test_the_turn_takes_the_brand_of_this_message_else_the_conversations_latest():
    window = [("USER", "what is the service credit under the leapswitch sla?"),
              ("ASSISTANT", "Under the Leapswitch SLA … CloudPe is not discussed.")]
    assert agent.brand_from_words("and for cloudpe?", window) == "CloudPe"
    assert agent.brand_from_words("what about the claim window?", window) == "Leapswitch"
    # two brands named is a comparison: both brands' policies, no single brand
    assert agent.brand_from_words("compare cloudpe and leapswitch sla", window) is None
    # an assistant's words never set the brand — only the reader's
    assert agent.brand_from_words("why?", [("ASSISTANT", "the CloudPe SLA says …")]) is None


# ---------------------------------------------------------- earlier turns' evidence
def _ctx(brand):
    return tools.ToolContext(None, uuid4(), frozenset({"assist.ask"}), uuid4(), None,  # type: ignore[arg-type]
                             brand=brand, brand_decided=True)


def test_an_earlier_turns_record_of_the_other_brand_is_not_offered_again(monkeypatch):
    monkeypatch.setattr(ledger, "refetch", lambda *a, **k: [
        ledger.Fetched("C7", "current", "CERT-In …", "CONST:x", "APPROVED_COMPANY_DOCUMENT",
                       "Leapswitch Terms of Service · 19. CERT-In Compliance"),
        ledger.Fetched("C13", "current", "§12 …", "CONST:12", "COMPANY_CONSTITUTION", "§12"),
        ledger.Fetched("C40", "current", "99.9% …", "CONST:y", "APPROVED_COMPANY_DOCUMENT",
                       "CloudPe Service Level Agreement · Commitment")])
    got = tools.get_evidence(_ctx("CloudPe"),
                             tools.GetEvidenceArgs(evidence_ids=["C7", "C13", "C40"]))
    states = {e.evidence_id: (e.state, e.text is not None) for e in got.evidence}
    assert states == {"C7": ("unavailable", False), "C13": ("current", True),
                      "C40": ("current", True)}


class _Reg:
    def __init__(self):
        self.adopted: list[str] = []
        self.shown: dict = {}

    def adopt(self, key, *_a):
        self.adopted.append(key)


def test_a_stale_record_is_shown_as_stale_and_never_made_citable():
    result = tools.ToolResult(tool="get_evidence", evidence=(
        tools.EvidenceRecord(evidence_id="C3", state="stale", ref="CONST:3", text="old",
                             authority="COMPANY_CONSTITUTION", location="§3"),
        tools.EvidenceRecord(evidence_id="C4", state="current", ref="CONST:4", text="now",
                             authority="COMPANY_CONSTITUTION", location="§4")))
    reg = _Reg()
    out = agent._present(result, reg)  # type: ignore[arg-type]
    assert reg.adopted == ["C4"]
    stale = next(e for e in out["evidence"] if e["evidence_id"] == "C3")
    assert stale["state"] == "stale" and stale["text"] is None


# ------------------------------------------------------------------- the verifier
def _ev(key, label):
    return agent_verify.Evidence(key, "Credits are 5% below 99.9%.", label, label, False,
                                 "constitution")


def test_the_verifier_refuses_a_citation_of_the_other_brands_published_policy():
    shown = {"C1": _ev("C1", "Leapswitch Service Level Agreement · Service Credits"),
             "C2": _ev("C2", "CloudPe Service Level Agreement · Issuance of Service Credits")}
    blocks = [{"kind": "sourced", "text": "Credits are 5% below 99.9%.", "cites": ["C1"]},
              {"kind": "sourced", "text": "Credits are 5% below 99.9%.", "cites": ["C2"]}]
    found = agent_verify.brand_violations(blocks, shown, brand="CloudPe")
    assert [(v.block, v.check) for v in found] == [(0, "P14")]
    assert agent_verify.brand_violations(blocks, shown, brand=None) == []


def test_the_reply_says_which_brand_it_answers_for():
    t = agent.TurnResult(blocks=[{"kind": "reasoning", "text": "An answer.", "cites": []}],
                         assessment="n/a", outcome="answered", registry=None,
                         brand="CloudPe")
    assert t.text().startswith("Answering for CloudPe: ")
    t.brand = None
    assert not t.text().startswith("Answering for")
