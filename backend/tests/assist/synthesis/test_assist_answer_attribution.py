"""`AM-109` — attribution is stated once per paragraph for the same claims: a
following sentence citing only claims the previous sentence already attributed need
not repeat "The company position (Liability — …), for MSA agreements, states:". Every
other check still applies to it, and a new source is always named."""
from legalmind.assist.synthesis import contracts


def _pos(n, text, scope="MSA", frame="Liability — Company Position (final, closed)"):
    return contracts.Contract(n=n, ref=f"POS:X-{n}", citation="Company Standard X",
                              kind=contracts.POSITION, status="CURRENT", text=text,
                              subject="", action="", object="", modality="STATEMENT",
                              negated=False, conditions=(), exceptions=(), scope=scope,
                              frame=frame)


CAP = _pos(1, "The cap applies mutually to both parties.")
EXCL = _pos(1, "Indirect and consequential damages are excluded for both parties.")


def test_a_sentence_repeating_the_same_claims_need_not_re_attribute():
    bare = "It also excludes indirect and consequential damages for both parties [1]."
    assert any("source kind not named" in f for f in contracts.check(bare, [EXCL]))
    assert not any(f.startswith(("source kind not named", "drops the frame",
                                 "drops the scope"))
                   for f in contracts.check(bare, [EXCL], carried=frozenset({contracts.attribution(CAP)})))


def test_a_carried_sentence_is_still_held_to_everything_else():
    wrong = "It also must never exclude indirect damages for either party [1]."
    found = contracts.check(wrong, [EXCL], carried=frozenset({contracts.attribution(CAP)}))
    assert found and not any(f.startswith("source kind not named") for f in found)


def test_a_new_source_is_always_named():
    other = _pos(2, "Indirect and consequential damages are excluded for both parties.",
                 scope="TOS")
    bare = "It also excludes indirect and consequential damages for both parties [2]."
    assert any("source kind not named" in f
               for f in contracts.check(bare, [other], carried=frozenset({contracts.attribution(CAP)})))


def test_a_repeated_restatement_continues_its_attribution():
    from legalmind.assist.synthesis import answer
    quoted = _pos(2, "... The cap applies mutually to both parties.")
    first = answer.verbalise(CAP)
    later = answer.verbalise(quoted, continued=True)
    assert first.startswith("The company position (Liability")
    assert later == "It also states: The cap applies mutually to both parties [2]."
    assert answer.is_verbalisation(later, quoted)
    assert not contracts.check(later, [quoted],
                               carried=frozenset({contracts.attribution(quoted)}))
    # …but not where nothing carried it: a bare continuation must still attribute.
    assert any("source kind not named" in f for f in contracts.check(later, [quoted]))


def test_a_temporal_status_is_said_once_for_the_same_record():
    """DPDP s. 27's "(… NOT YET IN FORCE …)" closed each of its three sentences
    (browser, 2026-09-29): it is part of the voice, so it is carried like the lead."""
    import dataclasses

    from legalmind.assist.synthesis import answer
    note = "clause (d) NOT YET IN FORCE — commences 13 November 2026"
    a = dataclasses.replace(CAP, temporal=note)
    b = dataclasses.replace(EXCL, n=2, temporal=note)
    first, later = answer.verbalise(a), answer.verbalise(b, continued=True)
    assert note in first and note not in later
    assert answer.is_verbalisation(later, b)
    assert not contracts.check(later, [b], carried=frozenset({contracts.attribution(a)}))
    # A record with a different status is a different voice: it is said again.
    other = dataclasses.replace(b, temporal=None)
    assert contracts.attribution(other) != contracts.attribution(a)
