"""The answer-integrity screens, pinned — what a cited answer is allowed to say.

Two independent audits (2026-09-22) found the same hole from opposite directions:
`verify_answer` measured whether the cited text COULD be the source of a sentence,
and nothing measured whether it says the same thing. Against real contract
language it admitted a changed cap, a flipped negation, a dropped carve-out, a
swapped party and an invented figure — three of them at a PERFECT overlap of
1.00, because dropping words only shrinks the numerator.

A floor sweep settled that this is structural rather than calibration: at a floor
of 1.00 — which refuses every paraphrase and would end the product — three false
claims still passed. So the screens here compare a claim against its best-aligned
evidence SENTENCE, and they are measured on both sides:

  * 15 claim transformations over real clause language: 13 decided correctly.
  * 54 answers this system actually generated and shipped: 3 refused, and a
    4th refusal was a TRUE catch — an answer claiming "three years / five lakh
    rupees" whose cited IT Act s.72 chunk says two years and one lakh.

The two transformations still admitted (a dropped carve-out, a swapped party)
need to know which words attach to which. Every lexical proxy measured for them
cost far more true answers than it caught false ones, and they are pinned below
as KNOWN so that closing one flips a visible test rather than passing silently.
"""
import pytest

from legalmind.assist import guardrails

CAP = ("17.2 Limitation of Liability. The total liability of either party arising out of "
       "or in connection with this Agreement shall not exceed the total fees paid by the "
       "Customer in the twelve (12) months preceding the claim, except in the case of "
       "death or bodily injury caused by negligence.")
NOTICE = ("7.1 Termination for convenience. Either party may terminate this Agreement by "
          "giving thirty (30) days written notice to the other party.")


@pytest.mark.parametrize("claim,chunks", [
    # Quantity — the family that carries the legal content of a cap or a period.
    ("Total liability shall not exceed the total fees paid in the twenty-four months "
     "preceding the claim [1].", [CAP]),
    ("Either party may terminate this Agreement by giving ninety (90) days written "
     "notice [1].", [NOTICE]),
    ("Either party may terminate by giving thirty days written notice and paying a fee "
     "of fifty lakh rupees [1].", [NOTICE]),
    ("Total liability shall not exceed the total fees paid in the twelve years preceding "
     "the claim [1].", [CAP]),
    # Polarity — the same words, the opposite law.
    ("Total liability does exceed the total fees paid in the twelve months preceding the "
     "claim [1].", [CAP]),
    ("Either party may not terminate this Agreement by giving thirty days written "
     "notice [1].", [NOTICE]),
    # Modality — a permission reported as an obligation.
    ("Either party must terminate this Agreement by giving thirty days written "
     "notice [1].", [NOTICE]),
])
def test_a_claim_its_evidence_does_not_support_is_refused(claim, chunks):
    """Each of these passed verification before 2026-09-22 and would have reached a
    reader as a cited, "verified" answer."""
    assert not guardrails.verify_answer(claim, chunks).passed


@pytest.mark.parametrize("claim,chunks", [
    ("Total liability shall not exceed the total fees paid in the twelve months "
     "preceding the claim [1].", [CAP]),
    # A paraphrase legitimately drops the negation: "shall not exceed X" -> "capped at
    # X". Comparing whole-sentence polarity refused 25 of 54 real answers on exactly
    # this shape, which is why polarity is scoped to the shared predicate.
    ("Liability is capped at twelve months of fees paid before the claim [1].", [CAP]),
    ("Either party may terminate this Agreement [1].", [NOTICE]),
    ("Either party may terminate and total liability shall not exceed the fees paid in "
     "twelve months [1][2].", [CAP, NOTICE]),
    # A reference is not a quantity: the year of an Act and a clause number live
    # elsewhere in the cited text.
    ("Disputes under Clause 17.2 are referred to arbitration under the Arbitration and "
     "Conciliation Act, 1996 [1].",
     ["Disputes under Clause 17.2 of this Agreement are referred to arbitration seated in "
      "Mumbai under the Arbitration and Conciliation Act, 1996."]),
    # "No," opens a direct answer; it does not negate the first content word.
    ("No, Service Credits represent your exclusive remedy for any service disruption [1].",
     ["The Service Credits described herein represent your exclusive remedy for any "
      "service disruptions or other issues during your term."]),
    # "shall have the right to" is an obligation word carrying a PERMISSION.
    ("Leapswitch can deny you access to the Designated Customer Area [1].",
     ["If the Customer fails to settle all dues, Leapswitch shall have the right to deny "
      "access to the Designated Customer Area."]),
    # A condition makes lexical polarity meaningless in both directions.
    ("However, it will not renew if either party gives written notice of non-renewal [1].",
     ["This Agreement shall renew automatically unless either party gives written notice "
      "of non-renewal at least thirty (30) days before the end of the term."]),
])
def test_an_answer_its_evidence_does_support_still_passes(claim, chunks):
    """The screens only ever widen a refusal (F-4), but a screen that refuses correct
    answers is not safe, it is broken. Measured: 3 false refusals in 54 real answers."""
    assert guardrails.verify_answer(claim, chunks).passed


@pytest.mark.parametrize("known_gap,claim,chunks", [
    ("a dropped carve-out reads as an absolute cap",
     "The total liability of either party shall not exceed the total fees paid in the "
     "twelve months preceding the claim [1].", [CAP]),
    ("a swapped party keeps every content word",
     "The total liability of the Customer alone shall not exceed the total fees paid in "
     "the twelve months preceding the claim [1].", [CAP]),
])
def test_the_two_transformations_lexical_screening_cannot_reach(known_gap, claim, chunks):
    """DOCUMENTED GAP, not an endorsement. These need to know which words attach to
    which; every lexical proxy measured for them refused more true answers than it
    caught false ones. If one is ever closed, this test fails and is deleted — that
    is the point of pinning it."""
    assert guardrails.verify_answer(claim, chunks).passed, known_gap


def test_polarity_is_read_off_the_raw_sentence_not_the_content_words():
    """The mechanism, so a future refactor cannot quietly undo it: `not`, `no`, `may`,
    `must` and `shall` are STOPWORDS, so a check built on `_content_words` alone cannot
    see polarity at all. That is the whole defect in one assertion."""
    for operator in ("not", "no", "may", "must", "shall"):
        assert not guardrails._content_words(operator)


def test_negation_reaches_its_verb_but_not_the_following_noun():
    """"shall not exceed the total fees" negates `exceed`, never `total`. A wider
    window refused 21 of 54 real answers; no window at all missed "is not allowed to
    undertake"."""
    words = guardrails._words("shall not exceed the total fees")
    assert guardrails._negated(words, words.index("exceed"))
    assert not guardrails._negated(words, words.index("total"))
    periphrastic = guardrails._words("is not allowed to undertake advertising")
    assert guardrails._negated(periphrastic, periphrastic.index("undertake"))


# --------------------------------------------------------------------------
# Domain C: what may be SERVED as law, as opposed to what is stored.
# --------------------------------------------------------------------------

def _statute(db, title: str, sections: list[tuple[str, int]]) -> None:
    """One synthetic Act, `sections` as (number, how many chunks)."""
    import uuid

    from sqlalchemy import text as sql

    from legalmind import config
    schema = config.assist_schema()
    sid = uuid.uuid4()
    db.execute(sql(f'INSERT INTO "{schema}".statutes (id, official_title, act_number_year,'
                   " jurisdiction, source, source_ref, as_amended_date, file_sha256,"
                   " supplied_by, supplied_at) VALUES (:i, :t, 'Act No. 0 of 2099',"
                   " 'TEST', 'synthetic', 'none', 'n/a', :h, 'test', now())"),
               {"i": sid, "t": title, "h": uuid.uuid4().hex * 2})
    n = 0
    for number, count in sections:
        for _ in range(count):
            n += 1
            db.execute(sql(f'INSERT INTO "{schema}".statute_chunks (id, statute_id,'
                           " section_number, ordinal, content, chunking_algorithm_version)"
                           " VALUES (:i, :s, :n, :o, :c, 'test')"),
                       {"i": uuid.uuid4(), "s": sid, "n": number, "o": n,
                        "c": "Every synthetic handler shall handle every synthetic widget "
                             "with synthetic care and record the synthetic outcome."})
    db.flush()


def _sections(db, query: str) -> list[str]:
    from legalmind.assist import statutes as st
    from legalmind.security import permissions as perms
    return [h.section_number for h in st.search_statutes(
        db, query=query, permissions=frozenset({perms.ASSIST_ASK}), embed_query=lambda q: None)]


def test_a_repealed_act_is_not_served_as_current_law(db):
    """`AM-71`'s shape, applied to statutes: a superseded source must be excluded from
    the lexical AND the vector path, "both, or it returns through the one left
    unfiltered". A repealed section served as current law is the citation a reader
    would rely on without re-checking."""
    _statute(db, "The Synthetic Widgets Act, 2099", [("1", 1)])
    _statute(db, "The Synthetic Widgets Act, 1899 (REPEALED — historical)", [("1", 1)])
    assert _sections(db, "handler shall record the outcome with care")  # the live Act answers
    from legalmind.assist import statutes as st
    from legalmind.security import permissions as perms
    hits = st.search_statutes(db, query="handler shall record the outcome with care",
                              permissions=frozenset({perms.ASSIST_ASK}),
                              embed_query=lambda q: None)
    assert all("REPEALED" not in h.official_title for h in hits)


def test_a_repealed_act_stays_reachable_when_the_question_names_it(db):
    """The corpus holds repealed Acts deliberately (Constitution §4.1/§28.4.2), so the
    exclusion is read-side and history stays reachable exactly where `AM-71` leaves it
    reachable — when the question names that Act."""
    _statute(db, "The Synthetic Widgets Act, 1899 (REPEALED — historical)", [("1", 1)])
    from legalmind.assist import statutes as st
    from legalmind.security import permissions as perms
    hits = st.search_statutes(db, query="the Synthetic Widgets Act, 1899",
                              permissions=frozenset({perms.ASSIST_ASK}),
                              embed_query=lambda q: None)
    assert any("REPEALED" in h.official_title for h in hits)


def test_a_section_holding_a_whole_act_is_never_cited(db):
    """A section that holds hundreds of chunks is not a section — it is the parser
    failing to find the next boundary, and everything after it is stored under one
    fabricated number. Measured on the real corpus: CPC "s. 316" held 157 chunks and
    was returned as a citable section; Income-tax "s. 659" held 1,099.

    The parser is the fix; this keeps a known-bad label off a citation until it lands.
    """
    from legalmind.assist import statutes as st
    _statute(db, "The Synthetic Widgets Act, 2099",
             [("1", 1), ("659", st.MAX_CHUNKS_PER_SECTION + 1)])
    assert "659" not in _sections(db, "handler shall record the outcome with care")
    assert "1" in _sections(db, "handler shall record the outcome with care")


def test_one_repeal_predicate_governs_both_retrieval_paths(db, monkeypatch):
    """`AM-71` requires the exclusion on the lexical AND the vector path — "both, or
    it returns through the one left unfiltered". Satisfying that with the rule written
    twice reintroduces the same risk one level down: an edit to one path leaves the
    other serving repealed law, and nothing fails.

    The lexical half is asserted BEHAVIOURALLY on purpose. An earlier version of this
    test checked that the canonical predicate appeared in the lexical SQL, and it was
    VACUOUS: the ORDER BY also uses the predicate, so reverting the WHERE clause to a
    hardcoded literal still passed. Neutralising the helper and requiring repealed
    material to actually come back cannot be satisfied that way.
    """
    from legalmind.assist import statutes as st

    _statute(db, "The Synthetic Widgets Act, 2099", [("1", 1)])
    _statute(db, "The Synthetic Widgets Act, 1899 (REPEALED — historical)", [("1", 1)])
    question = "handler shall record the outcome with care"

    def titles():
        return [h.official_title for h in st.search_statutes(
            db, query=question, permissions=frozenset({_ask()}),
            embed_query=lambda q: None)]

    assert not any("REPEALED" in t for t in titles()), "repealed law served as current"

    # LEXICAL — neutralise the one predicate; the exclusion must collapse with it.
    # A predicate that never matches, not the constant `false` — a bare constant is a
    # positional reference in ORDER BY and Postgres rejects it.
    never = "official_title LIKE '%__NOTHING_MATCHES_THIS__%'"
    monkeypatch.setattr(st, "_repealed_sql", lambda column="s.official_title": never)
    assert any("REPEALED" in t for t in titles()), \
        "the LEXICAL path does not depend on _repealed_sql"

    # VECTOR — the same helper, and it is the only use of it in that query.
    sentinel = "official_title LIKE '%__SABOTAGED__%'"
    monkeypatch.setattr(st, "_repealed_sql", lambda column="s.official_title": sentinel)
    captured: list[str] = []
    real = st.sql_text
    monkeypatch.setattr(st, "sql_text", lambda s: (captured.append(s), real(s))[1])
    st._vector_neighbours(db, "handler care", limit=5,
                          embed_query=lambda q: ([0.0] * 384, "test-model"))
    vector = [s for s in captured if "statute_chunk_embeddings" in s]
    assert vector, "the vector query was not captured"
    assert sentinel in vector[0], "the VECTOR path does not depend on _repealed_sql"


def test_no_second_copy_of_the_repeal_predicate_exists():
    """The duplication this replaced was found in a validation pass, not by a test.
    A literal `LIKE '%REPEALED%'` anywhere outside the one helper is that bug coming
    back, so it is asserted against directly."""
    import pathlib

    from legalmind.assist import statutes as st

    source = pathlib.Path(st.__file__).read_text()
    body = "\n".join(line for line in source.splitlines()
                     if not line.lstrip().startswith(("#", "--")))
    assert body.count("LIKE '%{_REPEALED_MARKER}%'") == 1, "the helper is the one copy"
    assert "LIKE '%REPEALED%'" not in body, "a hardcoded repeal predicate came back"


def _ask():
    from legalmind.security import permissions as perms
    return perms.ASSIST_ASK
