"""The RAG framework A/B benchmark: frozen inputs, resolvable expectations, and the
scorer's safety checks. No database, no model, no LlamaIndex — CI-safe."""
import json

from tools import rag_ab_run as ab

CASES = {c["id"]: c for c in json.loads(ab.FROZEN["single_turn"].read_text())["cases"]}
DOCQ = {q["id"]: q for q in json.loads(ab.FROZEN["document_lane"].read_text())["questions"]
        if q["category"] == "CONTRACT"}
CONVS = json.loads(ab.FROZEN["conversations"].read_text())["conversations"]
KINDS = set(json.loads(ab.FROZEN["conversations"].read_text())["turn_kinds"])


def test_the_inputs_are_the_frozen_ones():
    ab.check_frozen()


def test_every_expectation_resolves_to_ratified_material():
    for conv in CONVS:
        for t in conv["turns"]:
            assert t["kind"] in KINDS, t
            assert ("from_case" in t) + ("doc_case" in t) <= 1, t
            if "from_case" in t:
                assert t["from_case"] in CASES, t
            for q in t.get("doc_case", []):
                assert q in DOCQ and DOCQ[q]["document"] == conv["document"], t
            if t["kind"] == "expert_review":
                assert t.get("reason") and "from_case" not in t and "doc_case" not in t
            if "gold" in t:                      # authored slots must cite real cases
                assert t.get("basis") and t["gold"]


class _Resolve(dict):
    def __init__(self, texts):
        super().__init__(texts)
        self.repealed = {"Companies Act, 1956"}
        self.chunk_doc = {"DOC:x": "v1", "DOC:y": "v2"}

    def __call__(self, ref):
        return self.get(ref, "")


def _turn(**kw):
    return {"q": "What is our early termination position?", "kind": "answer",
            "gold": [["POS:EARLY"]], "must_not": ["POS:LIAB"], "answer": {}, **kw}


def _score(t, text, cited, prior=frozenset(), scope=None, **res):
    r = _Resolve(res)
    return ab.score_turn(t, {"text": text, "answered": True, "cited": cited,
                             "shown": cited}, set(prior), [], r, scope)


def test_a_wrong_source_and_a_foreign_document_are_caught():
    out = _score(_turn(), "The cap is twelve months of fees [1]. Clause 3 says so [2].",
                 ["POS:LIAB", "DOC:y"], scope="v1",
                 **{"POS:LIAB": "twelve months of fees", "DOC:y": "Clause 3"})
    assert out["wrong_source_cited"] == ["POS:LIAB"]
    assert out["foreign_document"] == ["DOC:y"]
    assert out["cites_gold"] is False and out["citation_precision"] == 0.0


def test_a_figure_its_citation_does_not_carry_is_unsupported():
    out = _score(_turn(), "The customer owes 6 months of fees [1].", ["POS:EARLY"],
                 **{"POS:EARLY": "the remainder of the term"})
    assert out["unsupported_figure"]
    assert _score(_turn(), "The client says it is 6 months, which the position does not "
                           "state [1].", ["POS:EARLY"],
                  **{"POS:EARLY": "x"})["unsupported_figure"] == []


def test_a_must_not_state_figure_is_a_contradiction_unless_negated_or_attributed():
    t = _turn(answer={"must_not_state_as_policy": ["6 months"]})
    assert _score(t, "Our policy is 6 months [1].", ["POS:EARLY"])["contradictions"]
    assert not _score(t, "The position does not set 6 months [1].",
                      ["POS:EARLY"])["contradictions"]


def test_verdict_language_counts_only_in_the_answers_own_voice():
    assert _score(_turn(), "This clause complies with our standard [1].",
                  ["POS:EARLY"])["verdicts"]
    assert not _score(_turn(), "The vendor must remain compliant with law [1].",
                      ["POS:EARLY"], **{"POS:EARLY": "must remain compliant with law"}
                      )["verdicts"]


def test_refusal_social_and_citation_request_turns():
    assert _score(_turn(kind="refuse", gold=[]), "x [1].", ["POS:A"])["false_admission"]
    assert _score(_turn(kind="social", gold=[]), "Hello.", [])["answered_from_corpus"] \
        is False
    assert _score(_turn(kind="cites_prior", gold=[]), "See [1].", ["POS:A"],
                  prior={"POS:A"})["cites_prior_ok"] is True


def test_a_repealed_act_cited_for_current_law_is_flagged():
    out = _score(_turn(gold=[["STAT:Companies Act, 2013:179"]], must_not=[]),
                 "The Board may act [1].", ["STAT:Companies Act, 1956:291"])
    assert out["non_current_cited"] == ["STAT:Companies Act, 1956:291"]


def test_a_marker_after_the_full_stop_belongs_to_the_sentence_before():
    assert ab._sentences("Notice is 30 days. [2] The cap is fees [1].") == [
        "Notice is 30 days. [2]", "The cap is fees [1]."]


def test_a_figure_the_cited_source_states_is_not_a_contradiction():
    t = _turn(answer={"must_not_state_as_policy": ["24 months"]})
    assert not _score(t, "A proposal of 24 months is negotiable [1].", ["POS:EARLY"],
                      **{"POS:EARLY": "a longer cap period, such as 18 or 24 months, "
                                      "is negotiable"})["contradictions"]
