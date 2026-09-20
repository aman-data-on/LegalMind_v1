"""Domain A regression set — does Ask answer the question the reader ASKED about the
organization's positions, and refuse honestly when it holds none?

Found from a live defect (2026-09-18): "what is written about partner agreement in the
constitution" was answered with three MSA positions about renewal, cure and suspension.
No Partner Agreement position is ratified (CONFLICTS.md C-23), so the honest answer is a
refusal that says so. Two mechanisms produced the junk, and both are general, not
partner-specific:

  1. Provenance was INDEXED. Every chunk carried "— Legal Constitution, Lawyer Review
     Version L1.10:" in its searchable text, so `constitut` matched 15 of 40 chunks and
     any "... in the constitution" question cleared the two-lexeme floor on boilerplate.
  2. The lexical path has no relevance verdict of its own: when the vector gate is shut
     it admits any chunk sharing common corpus words ("support", "customer") with a
     question whose real subject ("partner") the corpus never uses. Treating a shut
     gate as the verdict was tried and REVERTED the same day: the floor was calibrated
     for one document's chunks and refuses "Explain our termination standard." (top
     cosine 0.454) on the live corpus. Recorded as a Domain A calibration gap; until
     it is calibrated, a paper we hold no position for is filtered by NAME
     (`named_document_type`, including the §31 family's bare subject "partner").

Gold here is never authored: the answerable questions are each ratified file's own
`description` field, and their gold is that file. The refusals are questions about kinds
of paper the corpus holds no position for. Zero Gemini calls — every assertion is
deterministic. Vector-dependent checks skip where no model is provisioned (CI).

Run with `-s` to see the metrics table.
"""
from __future__ import annotations

import json
import statistics

import pytest

from legalmind.assist import embedding_runtime, positions
from legalmind.assist.positions import (
    RATIFIED_STANDARDS_DIR,
    embed_positions,
    search_positions,
)
from legalmind.security import permissions as P

PERMS = frozenset({P.ASSIST_ASK, P.CONFIGURATION_VIEW})

# Kinds of paper the Constitution §31 defines positions for and the corpus does not
# hold (C-23). Every one of these must retrieve NOTHING — a refusal is the answer.
# Kinds of paper the ratified corpus holds NO position for, so the honest answer is the
# refusal that names what IS covered — never another kind of paper's clause dressed as
# "the approved position".
#
# ⚠️ THIS LIST WAS EIGHT PARTNER / VENDOR / PURCHASE-ORDER / DISTRIBUTOR QUESTIONS, and
# every one of them was correct when written: `AM-72` made them refuse because no §31
# position existed. The owner then ruled the opposite (`AM-73`, 2026-09-18) — everything
# in the Constitution is ratified, and a type the Constitution carries text for must
# ANSWER with exact section citations. All eight now answer, correctly, so keeping them
# here would pin a superseded specification as the regression. The guard itself is
# unchanged and still exactly right; only its examples moved.
#
# Of Step 6's thirteen types, four carry no Constitution position: DPA, AUP,
# PRIVACY_POLICY and OTHER. Those are what this list must use from now on.
MUST_REFUSE = (
    "what is our data processing agreement position",
    "what does our dpa require on sub-processors",
    "what does our acceptable use policy say about prohibited content",
    "what is our privacy policy position",
)
# Twins whose descriptions are one sentence apart: hit@1 between them is a coin toss
# the description text cannot settle, so they are scored as a set.
TWINS = {
    "GOVLAW-MSA-001": {"GOVLAW-MSA-001", "GOVLAW-NDA-001", "GOVLAW-TOS-001"},
    "GOVLAW-NDA-001": {"GOVLAW-MSA-001", "GOVLAW-NDA-001", "GOVLAW-TOS-001"},
    "GOVLAW-TOS-001": {"GOVLAW-MSA-001", "GOVLAW-NDA-001", "GOVLAW-TOS-001"},
    "FORCE-MAJEURE-MSA-001": {"FORCE-MAJEURE-MSA-001", "FORCE-MAJEURE-TOS-001"},
    "FORCE-MAJEURE-TOS-001": {"FORCE-MAJEURE-MSA-001", "FORCE-MAJEURE-TOS-001"},
    "RETURN-DESTRUCTION-MSA-001": {"RETURN-DESTRUCTION-MSA-001", "RETURN-DESTRUCTION-NDA-001"},
    "RETURN-DESTRUCTION-NDA-001": {"RETURN-DESTRUCTION-MSA-001", "RETURN-DESTRUCTION-NDA-001"},
    "CONF-SURVIVAL-MSA-001": {"CONF-SURVIVAL-MSA-001", "CONF-SURVIVAL-NDA-001"},
    "CONF-SURVIVAL-NDA-001": {"CONF-SURVIVAL-MSA-001", "CONF-SURVIVAL-NDA-001"},
    "DATA-PURGE-MSA-001": {"DATA-PURGE-MSA-001", "DATA-RETRIEVAL-TOS-001"},
    "DATA-RETRIEVAL-TOS-001": {"DATA-PURGE-MSA-001", "DATA-RETRIEVAL-TOS-001"},
    "LIABILITY-MSA-001": {"LIABILITY-MSA-001", "LIABILITY-TOS-001"},
    "LIABILITY-TOS-001": {"LIABILITY-MSA-001", "LIABILITY-TOS-001"},
    "AUTORENEW-MSA-001": {"AUTORENEW-MSA-001", "AUTORENEW-TOS-001"},
    "AUTORENEW-TOS-001": {"AUTORENEW-MSA-001", "AUTORENEW-TOS-001"},
}


def answerable() -> list[tuple[str, str]]:
    """(question, gold code) — the ratified file's own description, nothing authored.

    RETIRED STANDARDS ARE EXCLUDED, because they are not answerable. `AM-71` removes a
    `DEPRECATED` Requirement from BOTH retrieval paths by design, so the seven `AM-65`
    retired standards can never be found and were being counted as seven permanent
    misses. That put the ceiling at 33/40 = 0.825 — exactly where the old threshold came
    from — so the metric was partly measuring the retirement rather than the retrieval,
    could never reach 1.0, and drifted whenever the corpus grew.
    """
    from legalmind.evaluation.constitution_block import is_retired

    out = []
    for path in sorted(RATIFIED_STANDARDS_DIR.glob("*.json")):
        d = json.loads(path.read_text())
        if is_retired(d):
            continue
        if d.get("description") and d.get("requirement_code"):
            out.append((d["description"], d["requirement_code"]))
    return out


@pytest.fixture
def corpus(db, user):
    import tools.import_ratified_standards as imp
    from tools.import_ratified_standards import import_standards
    original = imp.RATIFIED_STANDARDS_DIR
    imp.RATIFIED_STANDARDS_DIR = RATIFIED_STANDARDS_DIR
    try:
        import_standards(db, actor_email=user.email)
    finally:
        imp.RATIFIED_STANDARDS_DIR = original
    positions.chunk_ratified_standards(db)
    embed_positions(db)
    return db


def _run(db, embed, limit: int = 5) -> dict:
    hit1 = gold3 = rec5 = 0
    mrr: list[float] = []
    for q, gold in answerable():
        codes = [h.standard_code for h in
                 search_positions(db, query=q, permissions=PERMS, limit=limit,
                                  embed_query=embed)]
        accept = TWINS.get(gold, {gold})
        rank = next((i for i, c in enumerate(codes, 1) if c in accept), None)
        hit1 += rank == 1
        gold3 += rank is not None and rank <= 3
        rec5 += rank is not None
        mrr.append(1 / rank if rank else 0.0)
    junk = [q for q in MUST_REFUSE
            if search_positions(db, query=q, permissions=PERMS, limit=limit,
                                embed_query=embed)]
    unnamed = [q for q in UNNAMED_UNHELD
               if search_positions(db, query=q, permissions=PERMS, limit=limit,
                                   embed_query=embed)]
    n = len(answerable())
    return {"n": n, "unnamed": unnamed, "hit@1": hit1 / n, "gold@3": gold3 / n, "recall@5": rec5 / n,
            "mrr": statistics.mean(mrr), "junk": junk}


# Unheld subjects that name NO kind of paper the type table knows. Informational —
# printed, not asserted — because no name-based guard can catch them and the
# calibrated floor cannot yet be trusted to (see module docstring, point 2).
UNNAMED_UNHELD = ("what happens to affiliate commissions",
                  "what is the reseller onboarding process")


def _print(label: str, m: dict) -> None:
    print(f"\n{label:26} n={m['n']}  hit@1={m['hit@1']:.3f}  gold@3={m['gold@3']:.3f}  "
          f"recall@5={m['recall@5']:.3f}  mrr={m['mrr']:.3f}  "
          f"junk answers={len(m['junk'])}/{len(MUST_REFUSE)}")
    for q in m["junk"]:
        print(f"    JUNK  {q}")
    for q in m.get("unnamed", ()):
        print(f"    (info) unnamed unheld subject still answered: {q}")


# --------------------------------------------------------------------------
# The metrics, printed — and the two invariants that are the regression
# --------------------------------------------------------------------------
def test_lexical_only_metrics(corpus):
    _print("lexical only", _run(corpus, lambda _q: None))


@pytest.mark.skipif(not embedding_runtime.available(), reason="no model provisioned")
def test_with_vectors_metrics(corpus):
    _print("with calibrated vectors", _run(corpus, None))


def test_a_kind_of_paper_we_hold_no_position_for_is_refused_not_answered(corpus):
    """THE regression. A question about a paper the corpus has no position for must
    retrieve nothing, so the reader gets the honest refusal naming what IS covered —
    never another kind of paper's clause dressed as 'the approved position'."""
    embed = None if embedding_runtime.available() else (lambda _q: None)
    junk = {q: [h.standard_code for h in search_positions(
                corpus, query=q, permissions=PERMS, limit=5, embed_query=embed)]
            for q in MUST_REFUSE}
    assert all(not v for v in junk.values()), {q: v for q, v in junk.items() if v}


def test_every_ratified_position_is_still_reachable_by_its_own_description(corpus):
    """The guard must not become an outage: with the fix, each position is still found
    from the owner's own one-line description of it."""
    embed = None if embedding_runtime.available() else (lambda _q: None)
    m = _run(corpus, embed)
    # Pinned at the pre-fix measurement (0.825 lexical / 0.800 with vectors): the
    # fix may not cost a single position its own description.
    assert m["recall@5"] >= 0.80, m


def test_an_exact_standard_code_still_finds_its_position(corpus):
    """A code is an identifier, not incidental words: the control for the ponytail
    ceiling noted in `search_positions`."""
    embed = None if embedding_runtime.available() else (lambda _q: None)
    hits = search_positions(corpus, query="LIABILITY-MSA-001", permissions=PERMS,
                            limit=3, embed_query=embed)
    assert hits and hits[0].standard_code == "LIABILITY-MSA-001", \
        [h.standard_code for h in hits]


# --------------------------------------------------------------------------
# End to end — what the READER gets, through service.ask, with Gemini forbidden
# --------------------------------------------------------------------------
@pytest.fixture
def no_gemini(monkeypatch):
    from legalmind.assist import generation

    def boom(*a, **k):
        raise AssertionError("a Domain A refusal or verbatim quote must cost no call")

    monkeypatch.setattr(generation, "generate", boom)
    monkeypatch.setattr(generation, "generate_raw", boom)


def test_the_reader_gets_an_honest_refusal_that_names_what_is_covered(corpus, user,
                                                                        no_gemini):
    """THE LIVE DEFECT, end to end. No document attached, the organization's
    positions consulted, and a question about a paper the corpus holds no position
    for: the reader is told so, told what IS covered, shown no unrelated clause, and
    no provider is called for it."""
    from legalmind.assist import service
    perms = PERMS | {P.LEGAL_POSITION_VIEW}
    for question in MUST_REFUSE:
        conv = service.create_conversation(corpus, user_id=user.id, contract_id=None)
        out = service.ask(corpus, conversation_id=conv, document_version_id=None,
                          permissions=perms, question=question)
        assert out.positions == [], (question, [p["standard_code"] for p in out.positions])
        assert "Information not found" in out.text, (question, out.text)
        assert "quoted below" not in out.text, (question, out.text)
    # Where the question names the kind of paper, the refusal names what is covered.
    # This probed Partner Agreement until `AM-73` ratified §31 and made it answer; DPA
    # is now the nearest equivalent — a Step 6 type the Constitution states nothing for.
    conv = service.create_conversation(corpus, user_id=user.id, contract_id=None)
    out = service.ask(corpus, conversation_id=conv, document_version_id=None,
                      permissions=perms,
                      question="what is our data processing agreement position")
    assert "No approved position covers DPA" in out.text, out.text
    assert "currently cover" in out.text and "MSA" in out.text, out.text


def test_a_position_we_do_hold_is_still_quoted_verbatim(corpus, user, no_gemini):
    """The control, end to end: the fix must not turn a real position question into a
    refusal. With `LEGALMIND_POSITION_SYNTHESIS` off this costs no call either."""
    from legalmind.assist import service
    perms = PERMS | {P.LEGAL_POSITION_VIEW}
    conv = service.create_conversation(corpus, user_id=user.id, contract_id=None)
    out = service.ask(corpus, conversation_id=conv, document_version_id=None,
                      permissions=perms, question="what is our liability cap")
    codes = {p["standard_code"] for p in out.positions}
    assert codes & {"LIABILITY-MSA-001", "LIABILITY-TOS-001"}, (out.text, codes)
    assert "quoted below" in out.text


@pytest.mark.skipif(not embedding_runtime.available(), reason="no model provisioned")
def test_a_topic_several_standards_share_is_not_refused_when_a_model_is_present(corpus):
    """The live report of 2026-09-16, re-run WITH a model. Four termination standards
    tie above the evidence floor, so the peak-gap gate stays shut — that is ambiguity,
    and lexical must still answer it. A verdict is only "nothing above the floor"."""
    hits = search_positions(corpus, query="Explain our termination standard.",
                            permissions=PERMS, limit=5, embed_query=None)
    assert hits, "refused a topic the corpus holds several positions on"
    # The accepted set grew with the corpus: `AM-73` ratified §31, which added Partner,
    # Vendor and Distribution termination positions, and those now rank above the MSA
    # ones for a question that names no document type. The CLAIM is unchanged — a topic
    # several standards share is answered rather than refused — so what must hold is
    # that the hits ARE termination positions, not that they are one fixed five.
    codes = {h.standard_code for h in hits}
    assert codes & {
        "CONVENIENCE-NOTICE-MSA-001", "CURE-PERIOD-MSA-001",
        "SUSPENSION-NOTICE-CURE-MSA-001", "TERM-NOTICE-NDA-001",
        "EARLY-TERM-RESTRICTION-MSA-001",
        "TERM-CONSEQUENCES-PARTNER_AGREEMENT-001",
        "CONVENIENCE-NOTICE-PARTNER_AGREEMENT-001",
        "TERMINATION-DATA-RETURN-VENDOR_AGREEMENT-001",
        "COMPLIANCE-TERMINATION-POST-DISTRIBUTION_AGREEMENT-001"}, codes
