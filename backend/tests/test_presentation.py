"""`AM-108` — the reader's instruction shapes the answer; it never shapes the evidence.

"Give me a short summary", "Summarize this in 5 bullet points", "List only the
termination clauses", "Explain this in simple language", "What are the key risks?",
"Put the termination clauses in a table", "… without comparing it to our standard":
before this, every one of the document-wide ones refused (nothing to search for), the
negated comparison went to the evaluator, and no format was ever read.

Deterministic: no reranker (lexical), no Gemini (stubs), no database.
"""
import uuid

import pytest

from legalmind.assist import (
    answer,
    contracts,
    evidence,
    generation,
    intent,
    service,
    verify,
)
from legalmind.assist import presentation as pr
from legalmind.assist import query_plan as qp
from legalmind.assist.retrieval import Candidate


@pytest.fixture(autouse=True)
def no_models(monkeypatch):
    from legalmind.assist import rerank
    monkeypatch.setattr(rerank, "scores_many", lambda *a, **k: None)
    monkeypatch.setattr(verify, "check_answer",
                        lambda text, *a, **k: verify.Result(True, text, [], []))
    monkeypatch.setattr(answer, "REPAIR", False)


# ---- reading the instruction ---------------------------------------------------------

@pytest.mark.parametrize("question, task, shape, count, length, register, topic", [
    ("Give me a short summary.", pr.SUMMARY, pr.PROSE, None, pr.SHORT, None, ""),
    ("Summarize this in 5 bullet points.", pr.SUMMARY, pr.BULLETS, 5, None, None, ""),
    ("List only the termination clauses.", pr.LIST, pr.BULLETS, None, None, None,
     "termination clauses"),
    ("Explain this in simple language.", pr.EXPLAIN, pr.PROSE, None, None, pr.SIMPLE, ""),
    ("Explain the liability clause in simple language.", pr.EXPLAIN, pr.PROSE, None, None,
     pr.SIMPLE, "liability clause"),
    ("What are the key risks?", pr.RISKS, pr.BULLETS, None, None, None, ""),
    ("Put the termination clauses in a table", pr.LIST, pr.TABLE, None, None, None,
     "termination clauses"),
    ("What does our Constitution say about early termination?", pr.ANSWER, pr.PROSE,
     None, None, None, "does say early termination"),
])
def test_the_instruction_is_read_from_the_readers_words(question, task, shape, count,
                                                        length, register, topic):
    p = pr.read(question)
    assert (p.task, p.shape, p.count, p.length, p.register, p.topic) == (
        task, shape, count, length, register, topic)


def test_a_plain_question_is_no_instruction_and_a_task_with_no_topic_is_document_wide():
    assert not pr.read("What is the liability cap?").is_instruction
    assert pr.read("Give me a short summary.").document_wide
    assert not pr.read("List only the termination clauses.").document_wide
    assert pr.read("List only the termination clauses.").document_task


def test_without_comparing_keeps_the_question_off_the_evaluator():
    q = "Tell me what the agreement says about liability, without comparing it to our standard."
    assert not intent.is_comparison_question(q)
    assert pr.read(q).no_comparison
    assert intent.is_comparison_question("Compare this agreement with our Constitution.")
    assert intent.is_comparison_question("Does this MSA comply with our standard?")


def test_a_document_task_searches_the_document_alone():
    plan = qp.plan("List only the termination clauses.", has_document=True)
    assert plan.lanes == {qp.CONTRACT}
    assert plan.sub_questions[0].query.endswith("termination clauses")
    plan = qp.plan("Give me a short summary.", has_document=True)
    assert plan.presentation.document_wide and plan.lanes == {qp.CONTRACT}
    # … unless the reader brings the organization in.
    plan = qp.plan("List the termination clauses and our position on each.",
                   has_document=True)
    assert qp.COMPANY_POSITION in plan.lanes
    # Without a document the instruction narrows nothing.
    plan = qp.plan("Give me a short summary of our liability position.", has_document=False)
    assert qp.CONTRACT not in plan.lanes


def test_a_follow_up_keeps_its_own_instruction_not_the_anchors():
    resolved = "Put the termination clauses in a table. And how much notice would we have to give?"
    plan = qp.plan(resolved, has_document=True,
                   instruction="And how much notice would we have to give?")
    assert plan.presentation.shape == pr.PROSE and not plan.presentation.document_task
    assert qp.plan(resolved, has_document=True).presentation.shape == pr.TABLE


# ---- document-wide claims -------------------------------------------------------------

CLAUSES = {
    "7.1": "Term: This Agreement shall commence on the Service Commencement Date and "
           "shall remain in force for the committed term stated in the order form.",
    "17.2": "Monetary Cap on Liability: The total aggregate liability of Leapswitch "
            "shall not exceed the fees paid for the services in the six months before "
            "the claim.",
    "2.1": "Words of any gender are deemed to include those of the other gender and "
           "words in the singular include the plural.",
}


def _doc(ref, text):
    c = Candidate("DOCUMENT", f"DOC:{ref}", uuid.uuid4(), text, 1.0, "DOCUMENT")
    return evidence.Source(qp.CONTRACT, c, text, None, True, None)


def _bundle(question, *sources, has_document=True):
    plan = qp.plan(question, has_document=has_document)
    part = evidence.Part(question, tuple(sorted(plan.lanes)), evidence.SUPPORTED, sources)
    return evidence.Bundle((part,), sources, (), False, plan.presentation)


def test_a_summary_claims_one_operative_sentence_per_section_topical_first():
    b = _bundle("Give me a short summary.", *(_doc(k, v) for k, v in CLAUSES.items()))
    cs = contracts.build(b, "Give me a short summary.")
    assert [c.ref for c in cs] == ["DOC:7.1", "DOC:17.2", "DOC:2.1"]
    assert all(c.layer == contracts.PRIMARY and c.kind == contracts.CONTRACT for c in cs)
    assert cs[1].text.startswith("Monetary Cap on Liability")


def test_a_short_summary_is_given_four_claims_at_most():
    many = {f"{i}.1": f"Clause {i}: The Customer shall do the {i}th thing required under "
            f"this Agreement within the stated period." for i in range(3, 12)}
    b = _bundle("Give me a short summary.", *(_doc(k, v) for k, v in many.items()))
    assert len(contracts.build(b, "Give me a short summary.")) == 4
    b = _bundle("Give me a summary.", *(_doc(k, v) for k, v in many.items()))
    assert len(contracts.build(b, "Give me a summary.")) == 8


def test_key_risks_take_only_the_sections_the_organization_holds_a_position_on():
    b = _bundle("What are the key risks?", *(_doc(k, v) for k, v in CLAUSES.items()))
    assert {c.ref for c in contracts.build(b, "What are the key risks?")} == {
        "DOC:7.1", "DOC:17.2"}


def test_a_list_of_clauses_never_claims_a_company_position():
    pos = Candidate("CONSTITUTION", "CONST:13", uuid.uuid4(),
                    "Either party may terminate for convenience with 30 days' notice.",
                    1.0, "COMPANY_CONSTITUTION")
    b = _bundle("List only the termination clauses.", _doc("7.1", CLAUSES["7.1"]),
                evidence.Source(qp.COMPANY_POSITION, pos, pos.text, 5.0, True, None))
    assert {c.ref for c in contracts.build(b, "List only the termination clauses.")} == {
        "DOC:7.1"}


# ---- shaped answers, verified as prose ---------------------------------------------

TABLE = ("| Clause | What the agreement says |\n|---|---|\n"
         "| Term | The agreement runs for the committed term [1]. |\n"
         "| Liability | Liability is capped at six months' fees [2]. |")


def test_a_table_is_verified_row_by_row_and_rebuilt_with_the_verified_markers():
    rows = answer.table_sentences(TABLE)
    assert rows == [
        "Term — What the agreement says: The agreement runs for the committed term [1].",
        "Liability — What the agreement says: Liability is capped at six months' fees [2]."]
    rebuilt = answer.rebuild_table(TABLE, [rows[0].replace("[1]", "[3]"), rows[1]])
    assert "| Term | The agreement runs for the committed term [3] |" in rebuilt
    assert "[2] |" in rebuilt


def test_a_lead_in_that_fails_is_dropped_while_the_verified_table_stands():
    failures, shown = answer._with_table(
        "Six clauses govern exit [1][2].\n\n" + TABLE,
        lambda t: (["drops a condition"] if t.startswith("Six") else [], t))
    assert not failures and shown.startswith("| Clause |") and "Six clauses" not in shown


def test_a_failing_row_is_repaired_to_its_claim_or_dropped_and_the_rest_stand():
    def verify(t):
        return (["not grounded"] if "six months" in t and "fees paid" not in t
                else [], t)
    # Row 2 fails as written; repaired to claim [2]'s own words it passes.
    failures, shown = answer._with_table(TABLE, verify,
                                         repair_cell=lambda n: "Liability is capped at "
                                         "the fees paid in six months." if n == 2 else None)
    assert not failures and "the fees paid in six months [2]" in shown
    # Without a repair it is dropped; row 1 stands.
    failures, shown = answer._with_table(TABLE, verify)
    assert not failures and "| Term |" in shown and "Liability" not in shown
    # No row verified: fail closed.
    failures, shown = answer._with_table(TABLE, lambda t: (["bad"], t))
    assert failures == ["no table row verified"]


def test_bullets_are_trimmed_to_the_number_asked_never_padded():
    six = "\n".join(f"- Point {i} [1]." for i in range(1, 7))
    assert answer.trim_bullets(six, 5).count("- ") == 5
    assert answer.trim_bullets(six, None).count("- ") == 6
    assert answer.trim_bullets("- Only one [1].", 5).count("- ") == 1


def test_layered_keeps_bullet_lines_as_lines():
    shown = service._layered("- The term is fixed [1].\n- Liability is capped [2].",
                             ("PRIMARY", "PRIMARY"))
    assert shown == "- The term is fixed [1].\n- Liability is capped [2]."
    shown = service._layered("Direct [1].\n\n" + TABLE, ("PRIMARY", "PRIMARY"))
    assert shown.startswith("Direct [1].\n\n| Clause |")


def test_the_prompt_carries_the_presentation_and_the_shape_is_enforced_in_code():
    b = _bundle("Summarize this in 5 bullet points.",
                *(_doc(k, v) for k, v in CLAUSES.items()))
    seen = {}

    def generate(question, block, **kw):
        seen["presentation"] = kw.get("presentation")
        draft = "\n".join(f"- The contract states {t.split(':')[-1].strip()[:-1]} "
                          f"[{i}]." for i, t in enumerate(CLAUSES.values(), 1)) \
            + "\n- The contract states the same again [1].\n- And again [2].\n- More [3]."
        return generation.GenerationResult(draft, "m", "v", "", 5, 100, 20, None)
    out = answer.respond(b, "Summarize this in 5 bullet points.", environment="test",
                         generate=generate)
    assert "as bullet points, exactly 5 of them" in seen["presentation"]
    assert out.generated and out.text.count("\n- ") + out.text.startswith("- ") == 5


def test_a_short_answer_that_runs_long_is_sent_back_once_then_the_verified_one_shown(
        monkeypatch):
    monkeypatch.setattr(answer, "REPAIR", True)
    b = _bundle("Give me a short summary.", *(_doc(k, v) for k, v in CLAUSES.items()))
    long = " ".join(f"The contract states: {t.rstrip('.')} [{i}]."
                    for i, t in enumerate(CLAUSES.values(), 1)) * 2
    calls = []

    def generate(question, block, **kw):
        calls.append("first")
        return generation.GenerationResult(long, "m", "v", "", 5, 100, 20, None)

    def repair(question, block, draft, failures, **kw):
        calls.append(failures[0][:17])
        short = f"The contract states: {CLAUSES['7.1'].rstrip('.')} [1]."
        return generation.GenerationResult(short, "m", "v", "", 5, 100, 20, None)
    out = answer.respond(b, "Give me a short summary.", environment="test",
                         generate=generate, repair=repair)
    assert calls == ["first", "longer than asked"]
    assert out.generated and out.text.startswith("The contract states: Term:")
    assert len(out.text.split()) < 40


def test_a_long_verified_answer_beats_a_short_unverified_one(monkeypatch):
    """The second draft fails a check: the first — verified, merely long — is shown."""
    monkeypatch.setattr(answer, "REPAIR", True)
    b = _bundle("Give me a short summary.", *(_doc(k, v) for k, v in CLAUSES.items()))
    long = (" ".join(f"The contract states: {t.rstrip('.')} [{i}]."
                     for i, t in enumerate(CLAUSES.values(), 1)) + " ") * 2

    def generate(question, block, **kw):
        return generation.GenerationResult(long, "m", "v", "", 5, 100, 20, None)

    def repair(question, block, draft, failures, **kw):
        return generation.GenerationResult("The contract states that the term is "
                                           "fixed [1].", "m", "v", "", 5, 100, 20, None)
    out = answer.respond(b, "Give me a short summary.", environment="test",
                         generate=generate, repair=repair)
    assert out.generated and out.text == long.strip()
