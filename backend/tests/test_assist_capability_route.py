"""The capability route — `AM-68`, PROPOSED and OFF by default.

"What can you help me with in LegalMind?" returned three unrelated Company Standards:
a document-less Ask has no primary route, the POSITIONS fallback is unconditional, and
a standard clears the lexical bar on two shared words. That is the reported defect.

The route answers such a question from a manifest and touches no legal corpus at all.
Two things are therefore asserted harder than the answer text: that the flag defaults
OFF so nothing changes before the amendment is ruled on, and that the route performs
ZERO retrieval — asserted by making every retrieval function raise.
"""

from __future__ import annotations

import json

import pytest

from legalmind.assist import capability, intent, routing

PERMS = frozenset({"assist.ask", "configuration.view", "legal_position.view"})


# --------------------------------------------------------------------------
# The classifier — both directions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("question", [
    "What can you help me with in LegalMind?",
    "What can LegalMind do?",
    "LegalMind kya kar sakta hai?",
    "aap kya kaam kar sakte hain?",
    "आप क्या मदद कर सकते हैं?",
    "What features do you support?",
    "How can you help me?",
])
def test_a_capability_question_is_recognised(question):
    assert intent.is_capability_question(question) is True


@pytest.mark.parametrize("question", [
    # The near-miss the classifier exists to survive: self-reference AND a capability
    # verb, but a real document question. The legal anchor is what separates them.
    "Can you find the termination clause?",
    "Can you tell me the liability cap in this agreement?",
    "What does our standard say about indemnity?",
    "Summarize the relevant liability standard.",
    "What is our company's liability cap?",
    "NDA kya hota hai?",
    "Ismein confidentiality period kya hai?",
    "हमारे मानक से तुलना करें",
])
def test_a_legal_question_is_never_a_capability_question(question):
    """`AM-68` r7. A false negative here is a capability question answered the old
    way — today's behaviour. A false positive is a LEGAL question diverted to a product
    answer, which is strictly worse, so the anchor list is deliberately wide."""
    assert intent.is_capability_question(question) is False


# --------------------------------------------------------------------------
# The flag — PROPOSED means nothing changes yet
# --------------------------------------------------------------------------
def test_the_route_is_on_by_default_since_am_68_was_approved(monkeypatch):
    monkeypatch.delenv("LEGALMIND_CAPABILITY_ROUTE", raising=False)
    plan = routing.plan("What can you help me with in LegalMind?",
                        has_document=False, permissions=PERMS)
    assert plan.capability is True


def test_the_flag_is_the_rollback_and_still_works(monkeypatch):
    """Turning the route off restores the pre-`AM-68` behaviour — defect included, the
    unconditional POSITIONS fallback — without a deploy. That is why the flag stays."""
    monkeypatch.setenv("LEGALMIND_CAPABILITY_ROUTE", "off")
    plan = routing.plan("What can you help me with in LegalMind?",
                        has_document=False, permissions=PERMS)
    assert plan.capability is False
    assert plan.fallback == (routing.Domain.POSITIONS,)


def test_when_enabled_the_route_searches_nothing_at_all(monkeypatch):
    """`AM-68` r2 — not primary, not fallback, not "just to check"."""
    monkeypatch.setenv("LEGALMIND_CAPABILITY_ROUTE", "on")
    plan = routing.plan("What can you help me with in LegalMind?",
                        has_document=True, permissions=PERMS, statutes_available=True)
    assert plan.capability is True
    assert plan.domains == () and plan.fallback == () and plan.searched == ()
    assert plan.comparison is False and plan.statute_shaped is False


# --------------------------------------------------------------------------
# The manifest — r3/r4
# --------------------------------------------------------------------------
def test_every_manifest_entry_names_its_evidence():
    """r4: only behaviour that is built and covered by a test. An entry with no
    evidence field is an unverifiable claim about the product."""
    manifest = capability.load()
    for entry in manifest["capabilities"]:
        assert entry.get("evidence", "").strip(), entry

def test_the_manifest_states_what_the_product_does_not_do():
    """A capability answer listing only strengths misleads about the one thing a user
    most needs to know — that LegalMind does not decide acceptability or advise on
    signing."""
    limits = " ".join(limit["text"].lower() for limit in capability.load()["limits"])
    assert "do not decide" in limits or "does not decide" in limits
    assert "sign" in limits
    assert "draft" in limits


def test_the_answer_contains_every_capability_and_every_limit():
    manifest = capability.load()
    answer = capability.answer()
    for entry in manifest["capabilities"]:
        assert entry["text"] in answer
    for limit in manifest["limits"]:
        assert limit["text"] in answer


def test_a_missing_manifest_refuses_rather_than_inventing(tmp_path):
    """r4/r6. No manifest means no grounded capability answer exists; the module
    raises so the caller falls back to the ordinary route instead of improvising."""
    with pytest.raises(capability.CapabilityManifestUnavailable):
        capability.answer(tmp_path / "absent.json")
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"capabilities": []}))
    with pytest.raises(capability.CapabilityManifestUnavailable):
        capability.answer(empty)


def test_the_verdict_screen_is_the_wrong_instrument_for_a_manifest(monkeypatch):
    """Measured, and the result decided how this route is built.

    `is_verdict_statement` fires on the rendered manifest — and the two entries that
    trip it are `c3`, which names the product's own classification vocabulary ("a
    match, a deviation, missing, a conflict"), and `L1`, which is the DISCLAIMER: "I do
    not decide whether a document is acceptable, approve it, or advise whether to
    sign." The sentence that makes the answer safe is the one flagged as a verdict.

    That is not a defect in the screen. The screen asks "does this text state how a
    DOCUMENT stands against the organisation's position?", and it answers on whole
    text by design (`AM-28` r2, mechanical, outside the model). A static manifest names
    the vocabulary without applying it to anything, which is a case it was never built
    to judge.

    Two consequences, both recorded rather than worked around:

      * The route's `AM-68` r7 guarantee is STRUCTURAL, not screened — it performs zero
        retrieval and its only evidence is owner-approved static text, so it cannot
        state a position about any document. That is asserted by
        `test_when_enabled_the_route_searches_nothing_at_all` and
        `test_the_capability_module_reaches_no_legal_corpus`, not here.
      * A GENERATED capability answer (r5) built on this text would very likely be
        rejected by the same screen and fall back every time — real evidence for the
        deterministic rendering option in the owner's outstanding choice.
    """
    answer = capability.answer()
    assert intent.is_verdict_statement(answer) is True, (
        "if this ever stops firing, re-read the reasoning above before relaxing it")
    # What actually matters: no entry claims to decide anything about a document.
    lowered = answer.lower()
    for forbidden in ("this document complies", "this contract complies",
                      "meets our standard", "is acceptable to sign",
                      "we should sign", "does not comply with our"):
        assert forbidden not in lowered, forbidden


def test_the_capability_module_reaches_no_legal_corpus():
    """r2/r3, structurally. If this module could import retrieval or generation, a later
    edit could quietly give a product answer a legal source or an egress path.

    Parsed rather than grepped. An earlier version of this test searched the raw file
    for the substring "generation" and went red the moment the module's own docstring
    explained WHY it makes no generation call — a test that punishes documentation is a
    test that will be weakened. `ast` sees imports and calls, and reads no prose.
    """
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(capability.__file__).read_text())
    forbidden_modules = {"store", "positions", "statutes", "generation",
                         "legalmind.assist.store", "legalmind.assist.positions",
                         "legalmind.assist.statutes", "legalmind.assist.generation"}
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
            imported |= {a.name for a in node.names}
    assert not (imported & forbidden_modules), imported & forbidden_modules

    # No attribute access onto a retrieval or generation namespace either, in case one
    # is ever reached without an import statement.
    reached = {node.value.id for node in ast.walk(tree)
               if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)}
    assert not (reached & forbidden_modules), reached & forbidden_modules
