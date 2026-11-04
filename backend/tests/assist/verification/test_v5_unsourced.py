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


#: the Leapswitch TOS §8 KYC record, as the turn showed it
KYC = av.Evidence("C9", "For Indian Customers: Identity verification is conducted through "
                  "Digio, a certified digital KYC provider. For International Customers: "
                  "Identity verification is conducted through Stripe Identity using a "
                  "valid government-issued photo ID and live selfie.", "§8", None, False,
                  "constitution")
TOS7 = av.Evidence("C43", "Invoices overdue for more than 5 days will be charged a late "
                   "fee/interest of up to 5% per month on the outstanding balance.", "§7",
                   None, False, "constitution")


def test_a_record_restated_in_hinglish_with_no_citation_fails():
    """Q-5 (C26 run 3, 2026-11-02): no figure, no "our policy" — the record's names."""
    found = v5([reasoning("Nahi, KYC step ko skip nahi kiya ja sakta, chahe customer "
                          "kitni bhi jaldi me ho."),
                reasoning("Agar customer urgent activation chahta hai, toh unhe Digio "
                          "(Indian customers ke liye) ya Stripe Identity (international "
                          "customers ke liye) ke zariye KYC verification turant complete "
                          "karne ko kahein, kyunki system verification ke bina service "
                          "activate karne ki permission nahi deta.")], {"C9": KYC})
    assert any("restates C9" in x for x in found)


def test_a_late_fee_restated_with_no_citation_fails():
    assert v5([reasoning("Agar MSA standard (2% per month) apply hota hai, toh 3 mahine "
                         "ka total interest 6% hoga. Agar published TOS (up to 5% per "
                         "month) apply hota hai, toh 15% tak ho sakta hai.")],
              {"C16": CONST16, "C43": TOS7}, readers=frozenset({"3"}))


def test_the_record_restated_and_cited_passes():
    assert v5([{"kind": "sourced", "cites": ["C9"], "text": "For Indian customers, "
                "identity verification is conducted through Digio."},
               reasoning("Unhe Digio ya Stripe Identity se KYC turant complete karne ko "
                         "kahein.")], {"C9": KYC}) == []


def test_not_stated_a_hypothesis_and_the_readers_words_pass_beside_a_record():
    shown = {"C9": KYC}
    assert v5([reasoning("Our documents do not state whether KYC through Digio or "
                         "Stripe Identity can be expedited.")], shown) == []
    assert v5([reasoning("Hamare documents me Digio ya Stripe Identity ka urgent KYC "
                         "specified nahi hai.")], shown) == []
    assert v5([reasoning("If the customer completes KYC through Digio or Stripe "
                         "Identity, Operations can activate the service.")], shown) == []
    # the reader's figures are theirs: "5 days" and "5%" restate the question
    assert v5([reasoning("You asked whether 5 days at 5% can be waived; that needs "
                         "Legal.")], {"C43": TOS7}, readers=frozenset({"5"})) == []


def test_a_first_word_a_party_or_a_word_every_record_carries_is_not_a_restatement():
    """Independent review of Q-5: these named a record's "However", "Customer" and
    "LeapSwitch", and went to repair."""
    record = av.Evidence("C1", "However, LeapSwitch shall notify the Customer. This "
                         "applies to the Customer under Indian law.", "§1", None, False,
                         "constitution")
    other = av.Evidence("C2", "Indian law governs this Agreement.", "§2", None, False,
                        "constitution")
    third = av.Evidence("C3", "The Customer shall comply with Indian law.", "§3", None,
                        False, "constitution")
    shown = {"C1": record, "C2": other, "C3": third}
    for sentence in ("However, This depends on what the Customer signed.",
                     "LeapSwitch would need to check with the Customer first.",
                     "In general Indian contract law, a Customer may claim damages "
                     "under Section 73."):
        assert v5([reasoning(sentence)], shown) == [], sentence


def test_general_law_beside_one_or_two_records_is_not_a_restatement():
    """Second review of Q-5: nouns of law ("Indian", "Agreement", "Section") and a bare
    section number are the general-law explanation, not a record restated."""
    law = av.Evidence("C1", "Indian law governs this Agreement.", "§1", None, False,
                      "constitution")
    other = av.Evidence("C2", "Payments are due in 21 days.", "§2", None, False,
                        "constitution")
    varied = reasoning("In general, under Indian law an Agreement can be varied only "
                       "in writing.")
    # "under Indian law" uncited is the existing authority check's; not a restatement
    assert not [x for x in v5([varied], {"C1": law}) if "restates" in x]
    assert not [x for x in v5([varied], {"C1": law, "C2": other}) if "restates" in x]
    statute = av.Evidence("S1", "Indian Contract Act, 1872, Section 73: compensation for "
                          "loss or damage caused by breach of contract.", "s. 73", None,
                          False, "statutes")
    assert v5([reasoning("In general Indian contract law, a Customer may claim damages "
                         "under Section 73.")], {"S1": statute}) == []


def test_the_readers_own_material_is_not_a_record_to_cite():
    mail = av.Evidence("U1", "Client: we want KYC waived, Digio is too slow.", None, None,
                       False, "attachments")
    assert v5([reasoning("The client says KYC through Digio is too slow.")],
              {"U1": mail}) == []


def test_a_general_block_is_not_told_to_cite():
    """Code review of PR #244: a general block may cite nothing (V5), so "cite the
    record" could not be followed; general law is not our position."""
    assert v5([{"kind": "general", "cites": [], "text": "Interest typically runs at 18% "
                "per annum under general commercial practice."}]) == []


def test_settle_judges_the_lead_on_the_blocks_that_survive():
    """Code review of PR #244: an uncited lead beside cited blocks that are themselves
    dropped is an answer that cites nothing (as C5.3 for the document)."""
    lead = reasoning("Both positions align in capping liability at a year of fees.")
    bad = {"kind": "sourced", "text": "Late payments attract interest at 9% per month.",
           "cites": ["C16"]}
    shown = {"C16": CONST16}
    found = av.verify([lead, bad], shown, document_selected=False, assessment="n/a")
    kept, _ = av.settle([lead, bad], shown, found, document_selected=False)
    assert lead not in kept
