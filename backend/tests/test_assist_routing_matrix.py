"""The GENERAL LAW routing frontier, pinned as a regression.

Routing is measured on its own here — no retrieval, no provider, no database. Labels
come from the ratified dataset's OWN `category` field, so nothing legal is invented:

    category == STATUTE   -> the question asks for a rule or a source -> GENERAL_LAW
    category == CONTRACT  -> the question is about the reader's paper -> DOCUMENT

Two small sets are added here rather than to the dataset, because they are routing
fixtures and not evaluation material: the question shapes the owner named on
2026-09-21, and adversarial negatives built by putting statutory vocabulary onto the
reader's own paper. Neither carries a legal answer or an anchor.

THE HARD PROPERTY IS THE SECOND ASSERTION. `statute_shaped` makes STATUTES a primary
domain AND drops `require_semantic` in the fall-through, and `require_semantic` is what
keeps 44 of the 54 contract questions out of the statute corpus. Recall may be traded;
a false STATUTE route may not.
"""
import json
import pathlib

from legalmind.assist.intent import is_statute_question

DATASET = pathlib.Path(__file__).parent / "assist_eval" / "questions_draft.json"

# The shapes the owner named: a general legal rule is being asked for, not an opinion
# on a particular document.
OWNER_POSITIVES = (
    "Is restraint of trade valid in India?",
    "What does Indian law say about indemnity?",
    "What is the legal rule for liquidated damages?",
    "Under Indian law, can a company indemnify its own directors?",
)
# Statutory vocabulary on the reader's own paper. Every one of these must stay OUT of
# the statute lane, including the two that name Indian law explicitly.
ADVERSARIAL_NEGATIVES = (
    "Is our liability cap enforceable?",
    "Are we liable for indirect losses under this agreement?",
    "What penalties does the contract impose on us?",
    "Is this clause valid?",
    "Does this agreement comply with Indian law?",
    "Is the indemnity in our MSA legally binding under Indian law?",
    "Which clause covers breach of the agreement?",
    "Is the termination clause in my document enforceable?",
    "What does our standard say about governing law?",
    "Is the notice period in this contract valid?",
)
# Measured 2026-09-21. The classifier reached 0.333 before the signal work and 24 of 27
# after, with the false-STATUTE count still zero. Written as the exact fraction, not a
# rounded decimal, so the floor is the measurement rather than a value just above it.
RECALL_FLOOR = 24 / 27


def _cases():
    questions = json.loads(DATASET.read_text())["questions"]
    for q in questions:
        if q.get("category") == "STATUTE":
            yield q["id"], q["question"], True
        elif q.get("category") == "CONTRACT":
            yield q["id"], q["question"], False
    for i, text in enumerate(OWNER_POSITIVES, 1):
        yield f"OWN-{i}", text, True
    for i, text in enumerate(ADVERSARIAL_NEGATIVES, 1):
        yield f"ADV-{i}", text, False


def test_no_document_question_is_ever_routed_to_the_statute_corpus():
    """The hard safety property. Zero, not "few"."""
    wrong = [(qid, text) for qid, text, want in _cases()
             if not want and is_statute_question(text)]
    assert wrong == [], f"document/position questions routed to the law: {wrong}"


def test_general_law_recall_does_not_regress():
    positives = [(qid, text) for qid, text, want in _cases() if want]
    routed = [qid for qid, text in positives if is_statute_question(text)]
    recall = len(routed) / len(positives)
    assert recall >= RECALL_FLOOR, (
        f"GENERAL_LAW recall {recall:.3f} < {RECALL_FLOOR}; "
        f"not routed: {[q for q, _ in positives if q not in routed]}")


def test_the_owner_named_shapes_all_route():
    for text in OWNER_POSITIVES:
        assert is_statute_question(text), text


def test_the_three_conservative_cases_stay_conservative():
    """Q-43, Q-48 and Q-52 are deliberately NOT routed: the only signals that would
    catch them are a legal-subject vocabulary (matches 63 of 64 document questions),
    a penalty-relation word (breaks 5), or "standard", which is a POSITION noun. All
    three already answer through the fall-through, so the router gives up nothing."""
    questions = {q["id"]: q["question"]
                 for q in json.loads(DATASET.read_text())["questions"]}
    for qid in ("Q-43", "Q-48", "Q-52"):
        assert not is_statute_question(questions[qid]), qid
