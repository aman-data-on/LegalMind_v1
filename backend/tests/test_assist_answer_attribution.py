"""`AM-109` — attribution is stated once per paragraph for the same claims: a
following sentence citing only claims the previous sentence already attributed need
not repeat "The company position (Liability — …), for MSA agreements, states:". Every
other check still applies to it, and a new source is always named."""
from legalmind.assist import contracts


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
    from legalmind.assist import answer
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
