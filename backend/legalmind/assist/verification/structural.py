"""The STRUCTURAL layer of the answer check (P2a, 2026-11-03) — deterministic rules about
how a legal sentence is built, never a pattern for one case.

Precision-mode checking (`verify.judge`) accepts a claim whose words are a subset of its
evidence, so a claim that DROPS a limb of the sentence it restates is invisible to it:
"the Customer may terminate" is every word of "the Customer may terminate if the fees
are unpaid". These checks read the shape instead:

  LIMB     the evidence sentence the claim restates (best alignment) is divided into its
           clauses, and each clause into its operative core and its limbs — conditions,
           exceptions, and the qualifiers reasonable / material / written / prior. A
           claim that restates a clause's core and omits a limb restricting it FAILS
           (CONDITION_DROPPED / EXCEPTION_OMITTED), unless the claim states the act more
           narrowly itself or the limb is restated elsewhere in the answer (`answer`); a
           limb restated with the opposite sense ("unless X" as "if X") FAILS
           (LIMB_REVERSED).
  SCOPE    a universal quantifier (each / every / all / any / either / both) the claim
           puts where the aligned sentence names something narrower FAILS
           (SCOPE_WIDENED).
  PART     a claim divided at a conclusion connective ("; accordingly", "therefore",
           "which means", a semicolon) is read part by part: a part that restates no
           evidence sentence and that the local NLI model does not find entailed FAILS
           (UNSUPPORTED_CONCLUSION) — never accepted because its words occur somewhere.

P2b (2026-11-03): a reversed limb is judged against the claim's BEST-matching limb, and
only between opposite senses; "; (b) …" is an enumeration's next item, never a
conclusion; a leading "On …," / "Following …," is a condition; a claim of two content
words aligns on a near-verbatim run; a word limiting a quantified class ("every PUBLIC
company") deleted is widening; headings, marginal notes and an Act's year never stand
between a sentence and its limbs.

Each check returns PASS, FAIL or UNKNOWN, and never PASS on what it cannot parse. A FAIL
is anchored on a matched evidence sentence (no anchor, no FAIL). `combine` applies the
owner's rule: a FAIL rejects; an UNKNOWN on a sentence with limbs never accepts on its
own — the claim ABSTAINS. Production runs it only when `LEGALMIND_STRUCTURAL_CHECK` says
so (`mode`, default off); `tools.eval_claims` measures it as verifier `hybrid`.
"""
from __future__ import annotations

import difflib
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass

from legalmind.assist.verification import guardrails, verify

PASS, FAIL, UNKNOWN, ABSTAIN = "PASS", "FAIL", "UNKNOWN", "ABSTAIN"

#: Share of a claim part's content words its anchor sentence must carry to be the
#: sentence it restates; share of a clause's core the claim must carry to restate it;
#: a limb is covered at COVERED of its own words and omitted at OMITTED or below.
ALIGN = 0.75
CORE = 0.7
COVERED = 0.6
OMITTED = 0.25


def mode() -> str:
    """off (default) · shadow (logged, never changes a verdict) · on."""
    value = os.environ.get("LEGALMIND_STRUCTURAL_CHECK", "off").strip().lower()
    return value if value in ("off", "shadow", "on") else "off"


@dataclass(frozen=True)
class Check:
    state: str                      # PASS · FAIL · UNKNOWN
    reason: str | None = None       # CONDITION_DROPPED · EXCEPTION_OMITTED · ...
    span: str | None = None         # the evidence text the result is anchored on
    limbs: bool = False             # the anchor sentence carries a limb


# ── words ────────────────────────────────────────────────────────────────────────────

def _stems(text: str) -> set[str]:
    return {verify._stem(w.rstrip(".,")) for w in guardrails._content_words(text)}


def _share(part: set[str], whole: set[str]) -> float:
    return len(part & whole) / len(part) if part else 1.0


def _verbatim(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _tokens(text: str) -> list[str]:
    return [verify._stem(w) for w in re.findall(r"[a-z0-9][a-z0-9'-]*", text.lower())]


# ── limbs ────────────────────────────────────────────────────────────────────────────

_CONDITION = ("only if|if|unless|in the event(?: that| of)?|in case|as long as|"
              "so long as|on condition that|provided(?:,)?(?: however,?)? that|"
              "subject to")
_EXCEPTION = ("except|save(?= as\\b| that\\b| where\\b| for\\b| in\\b)|other than|"
              "excluding|notwithstanding|but not")
#: open a limb only at the head of a sentence or after a punctuation mark — "the State
#: where it sits" is a relative clause, not a condition
_AFTER_MARK = "where|when|whenever|upon|once|after|before|until"
#: open a limb only at the head of a sentence, and only where a comma closes it ("On
#: receipt of the request, X shall …", "Following approval, …")
_HEAD_MARK = "on|following"
_LIMB = re.compile(
    rf"^\s*(?P<h>{_HEAD_MARK})\b(?=[^,;]{{3,200}},)"
    rf"|(?:^|(?<=[,;:(—\u2013]\s)|(?<=[,;:(—\u2013]))\s*(?P<a>{_AFTER_MARK}|{_CONDITION}|"
    rf"{_EXCEPTION})\b|\s(?P<b>{_CONDITION}|{_EXCEPTION})\b", re.I)
_EXCEPTION_RE = re.compile(rf"^(?:{_EXCEPTION})$", re.I)
_QUALIFIER = re.compile(r"\b(reasonable|material|written|prior)\s+(?!to\b|and\b|or\b)"
                        r"(?:(?:written|prior|reasonable|material)\s+)?([a-z]{3,})", re.I)
_ONLY = re.compile(r"\b(?:only|solely|exclusively)\b", re.I)
#: A limb's sense: "unless X" restated as "if X", or "before X" as "after X", keeps every
#: word and reverses the limb.
_SENSE = {**dict.fromkeys(("unless", "except", "save", "other than", "excluding",
                           "but not"), "negative"),
          **dict.fromkeys(("if", "only if", "where", "when", "whenever", "in the event",
                           "in the event that", "in the event of", "in case",
                           "as long as", "so long as", "on condition that"), "positive"),
          **dict.fromkeys(("before", "until"), "earlier"),
          **dict.fromkeys(("after", "upon", "once", "on", "following"), "later")}
_OPPOSITE = {"negative": "positive", "positive": "negative", "earlier": "later",
             "later": "earlier"}


@dataclass(frozen=True)
class Limb:
    kind: str                       # CONDITION_DROPPED · EXCEPTION_OMITTED
    marker: str                     # the words that open it, lower case
    text: str

    def words(self, core: set[str]) -> set[str]:
        """What the limb says that its clause's core does not."""
        return _stems(self.text[len(self.marker):]) - core


def limbs(sentence: str) -> tuple[list[Limb], str]:
    """The sentence's restricting limbs and its core (the sentence without them). A limb
    runs from its marker to the next , ; : or ) at its own depth, or the sentence end."""
    found: list[Limb] = []
    spans: list[tuple[int, int]] = []
    for m in _LIMB.finditer(sentence):
        key = next(k for k in ("h", "a", "b") if m[k])
        word, start = m[key], m.start(key)
        if any(a <= start < b for a, b in spans):
            continue
        depth, end = 0, len(sentence)
        for k in range(start, len(sentence)):
            ch = sentence[k]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    end = k
                    break
                depth -= 1
            elif ch in ",;:" and depth == 0 and k > start + len(word):
                end = k
                break
        kind = "EXCEPTION_OMITTED" if _EXCEPTION_RE.match(word) else "CONDITION_DROPPED"
        found.append(Limb(kind, re.sub(r"\s+", " ", word.lower()),
                          sentence[start:end].strip(" .")))
        spans.append((start, end))
    core = sentence
    for a, b in sorted(spans, reverse=True):
        core = core[:a] + " " + core[b:]
    return found, core


#: Where a sentence divides into clauses a limb restricts one of: a semicolon, a dash.
_SEGMENT = re.compile(r"\s*;\s*|\s+[—\u2013]\s+|\s*—\s*")
SEGMENT_WORDS = 3


def segments(sentence: str) -> list[str]:
    """The sentence's clauses. A piece that is all limb ("Where X is not defined") or a
    fragment ("numerically or qualitatively") belongs to the clause after it."""
    out: list[str] = []
    carry = ""
    for piece in _SEGMENT.split(sentence):
        piece = f"{carry} — {piece}" if carry else piece
        if len(_stems(limbs(piece)[1])) < SEGMENT_WORDS:
            carry = piece
            continue
        out.append(piece)
        carry = ""
    if carry:
        if out:
            out[-1] += " — " + carry
        else:
            out.append(carry)
    return out


def _qualifiers(clause: str) -> list[tuple[str, str, str]]:
    """(qualifier, its noun's stem, the phrase) where the noun is never unqualified."""
    out = []
    for m in _QUALIFIER.finditer(clause):
        rest = clause[:m.start()] + clause[m.end():]
        if not re.search(rf"\b{re.escape(m[2])}\b", rest, re.I):
            out.append((m[1].lower(), verify._stem(m[2].lower()), m.group(0)))
    return out


def _twin(own: set[str], claim_limbs: list[Limb]) -> Limb | None:
    """The claim's limb that restates `own` best — at least COVERED of it — or None."""
    scored = [(_share(own, cl.words(set())), k) for k, cl in enumerate(claim_limbs)]
    best = max(scored, default=None)
    return claim_limbs[best[1]] if best and best[0] >= COVERED else None


def _limb_check(claim: str, anchor: str, answer: Sequence[str]) -> Check:
    """Every limb of the clauses the claim restates is said in the claim (or elsewhere
    in the answer) with the same sense."""
    said = _stems(claim).union(*(_stems(s) for s in answer))
    verbatim = _verbatim(" ".join((claim, *answer)))
    words = set(re.findall(r"[a-z]+", " ".join((claim, *answer)).lower()))
    claim_limbs = limbs(claim)[0]
    narrower = bool(_ONLY.search(claim) and not _ONLY.search(anchor)) or any(
        _share(cl.words(set()), _stems(anchor)) < 0.5 for cl in claim_limbs)
    clauses = [(seg, *limbs(seg)) for seg in segments(anchor)]
    if not any(found or _qualifiers(seg) for seg, found, _ in clauses):
        return Check(PASS)
    restated = [c for c in clauses if _share(_stems(c[2]), said) >= CORE]
    if not restated:
        # the claim restates part of a clause — which limb restricts that part is not
        # something this parse can tell
        return Check(UNKNOWN, span=anchor, limbs=True)
    state = PASS
    for clause, found, core in restated:
        for limb in found:
            own = limb.words(_stems(core))
            if f" {_verbatim(limb.text)} " in f" {verbatim} ":
                continue                        # said word for word, marker and all
            if not own:
                # every word of the limb is also in its clause ("If approved, … after
                # approval"): words cannot tell; a claim with no limb at all dropped it
                if not claim_limbs and not narrower:
                    return Check(FAIL, limb.kind, limb.text, limbs=True)
                state = UNKNOWN
                continue
            got = _share(own, said)
            if got >= COVERED:
                twin = _twin(own, claim_limbs)
                if (twin is not None and twin.marker in _SENSE
                        and limb.marker in _SENSE
                        and _SENSE[twin.marker] == _OPPOSITE[_SENSE[limb.marker]]):
                    return Check(FAIL, "LIMB_REVERSED", limb.text, limbs=True)
                continue
            if got <= OMITTED and not narrower:
                return Check(FAIL, limb.kind, limb.text, limbs=True)
            state = UNKNOWN
        for q, noun, text in _qualifiers(clause):
            if q not in words and noun in said and not narrower:
                return Check(FAIL, "CONDITION_DROPPED", text, limbs=True)
    return Check(state, span=anchor, limbs=True)


# ── scope ────────────────────────────────────────────────────────────────────────────

_UNIVERSAL = frozenset({"each", "every", "all", "any", "either", "both", "whatever",
                        "whoever"})


def _scope_check(part: str, anchor: str) -> Check:
    """A universal quantifier the claim puts where its anchor names something narrower,
    or a word limiting a quantified class ("every public company") the claim deletes."""
    a, b = _tokens(anchor), _tokens(part)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False) \
            .get_opcodes():
        if (op == "delete" and i2 - i1 <= 2 and i1 and j1
                and all(t.isalpha() and t not in guardrails._STOPWORDS for t in a[i1:i2])
                and a[i1 - 1] in _UNIVERSAL and b[j1 - 1] == a[i1 - 1]):
            # "every public company" → "every company": the class lost its limit
            return Check(FAIL, "SCOPE_WIDENED", " ".join(a[i1 - 1:i2 + 1]))
        if op not in ("replace", "insert") or j2 - j1 > 4:
            continue
        if set(b[j1:j2]) & _UNIVERSAL and not set(a[i1:i2]) & _UNIVERSAL:
            return Check(FAIL, "SCOPE_WIDENED", " ".join(a[max(0, i1 - 2):i2 + 2]))
    return Check(PASS)


# ── parts ────────────────────────────────────────────────────────────────────────────

_CONNECTIVE = re.compile(
    r"\s*;\s*(?!\s*(?:and\s+|or\s+)?\(?(?:[a-z]|[ivxl]{1,5}|\d{1,2})\)\s)"
    r"(?:and\s+|so\s+)?(?:(?:accordingly|therefore|thus|hence|consequently|"
    r"as a result|which means(?: that)?)\s*,?\s*)?"
    r"|[,.]?\s+(?:and\s+)?(?:accordingly|therefore|thus|hence|consequently|as a result|"
    r"which means(?: that)?)\b\s*,?\s*"
    r"|,\s+so\s+(?!that\b|long\b|far\b|as\b|much\b)", re.I)
PART_WORDS = 3
#: a claim of ALIGN_WORDS (but fewer than PART_WORDS) content words aligns only where
#: SHORT_RUN of its tokens run through the sentence in order
ALIGN_WORDS = 2
SHORT_RUN = 0.85


def parts(claim: str) -> list[str]:
    """The claim divided at its conclusion connectives; a fragment of fewer than
    PART_WORDS content words joins its neighbour."""
    out: list[str] = []
    short = False
    for piece in _CONNECTIVE.split(claim):
        piece = piece.strip(" ,.")
        if not piece:
            continue
        if out and (short or len(guardrails._content_words(piece)) < PART_WORDS):
            out[-1] += "; " + piece
        else:
            out.append(piece)
        short = len(guardrails._content_words(out[-1])) < PART_WORDS
    return out


#: An excerpt's breadcrumb line ("Legal Constitution L1.15 · 31. … · 31.16 Title") — a
#: wrapped line would otherwise glue it to the first sentence it heads — and a
#: sentence's lead-in label ("System Rule (final): …").
_BREADCRUMB = re.compile(r"^[^\n]*\s·\s[^\n]*\n")
_LABEL = re.compile(
    # a lead-in label with no verb in it ("System Rule (final): …")
    r"^(?![^:]*\b(?:shall|must|may|will|should|can|is|are|states?|includes?|means)\b)"
    r"[A-Z][\w/'()-]*(?: [\w/'()-]+){0,4}:\s+(?=\w)"
    # a statute's marginal note: "12. Effect of registration.—(1)", "… in public. — "
    r"|^(?:\d+[A-Z]?(?:\.\d+)*\.?\s+)?[A-Z][^—\u2013.:;]{2,160}\.\s?[—\u2013]{1,2}\s*"
    # a heading in capitals ("EFFECT OF REGISTRATION (1)") or a reference ("Clause 6.5.4")
    r"|^(?:[A-Z][A-Z,'&-]*\s+){2,}(?=[A-Z(][a-z(0-9])"
    r"|^(?:Clause|Section|Article|Rule|Regulation|Paragraph|Para)\s+\d+[A-Z]?(?:\.\d+)*"
    r"\.?\s+(?=[A-Z])"
    # a list's "(a)" / "(1)" and a bare "3.2"
    r"|^(?:\([a-z0-9]{1,4}\)\s*)+|^\d+[A-Z]?(?:\.\d+)*\.?\s+(?=[A-Z])")


def _unlabel(sentence: str) -> str:
    """The sentence without every heading, label and number that leads it."""
    while (bare := _LABEL.sub("", sentence.strip(), count=1)) != sentence.strip():
        sentence = bare
    return sentence.strip()


#: A split the sentence windows make that is not a sentence end: inside a parenthesis
#: ("(e.g. a volume discount)") or after an abbreviation ("s. 74", "Pvt. Ltd.").
_NOT_AN_END = re.compile(r"(?:\b(?:e\.g|i\.e|etc|viz|cf|No|Nos|s|ss|cl|Art|Rs|Pvt|Ltd|"
                         r"Co|Inc|vs?)|\b[A-Z])\.$")
_PROVISO = re.compile(r"^[\"“]?Provided(?:,)?(?: further| also| however)?,? that\b")


def _sentences(evidence: Sequence[str]) -> list[str]:
    out: list[str] = []
    for text in evidence:
        mine: list[str] = []
        for sent, _ in verify.windows(_BREADCRUMB.sub("", text)):
            # a proviso is a limb of the sentence before it, not a sentence of its own
            if mine and (mine[-1].count("(") > mine[-1].count(")")
                         or _NOT_AN_END.search(mine[-1]) or _PROVISO.match(sent)):
                mine[-1] += " " + sent
            else:
                mine.append(sent)
        out += [_unlabel(s) for s in mine]
    return out


def align(part: str, sentences: Sequence[str]) -> str | None:
    """The evidence sentence the part restates: most of the part's words, then the
    fewest others; None below ALIGN."""
    words = _stems(part)
    if len(words) < ALIGN_WORDS:
        return None
    if len(words) >= PART_WORDS:
        best = max(sentences, default=None,
                   key=lambda s: (_share(words, _stems(s)), -len(_stems(s))))
        return best if best is not None and _share(words, _stems(best)) >= ALIGN else None
    # two content words say too little to pick a sentence by: the claim's own words must
    # run through it in order ("This Agreement may not be modified")
    toks = _tokens(part)
    best, run = None, 0.0
    for sent in sentences:
        got = sum(m.size for m in difflib.SequenceMatcher(
            None, toks, _tokens(sent), autojunk=False).get_matching_blocks()) / len(toks)
        if got > run and words <= _stems(sent):
            best, run = sent, got
    return best if run >= SHORT_RUN else None


def _supported(part: str, evidence: Sequence[str]) -> bool | None:
    """By the NLI model against each excerpt's premise — never by its words occurring
    somewhere in the evidence, the very test a grafted conclusion passes; None when the
    model is unavailable."""
    scored = verify.entailment([(verify.premises(part, text)[0], part)
                                for text in evidence])
    if scored is None:
        return None
    return any(e >= verify.ENTAIL and c < verify.CONTRA for e, c in scored)


#: "The company position is that …", "Under the Act, …" — who says it, which the kind
#: checks verify; the structure checked here is what follows.
_ATTRIBUTION = re.compile(
    r"^(?:under (?:the|this|that|our|your) [^,]{1,60}(?:, \d{4})?,"
    r"|(?:the|our|your) [\w' -]{0,40}?"
    r"(?:position|policy|act|law|agreement|contract|constitution|rule|standard|terms)"
    r" (?:is|states|says|provides|requires) that)\s+", re.I)


# ── the check ────────────────────────────────────────────────────────────────────────

def check(claim: str, evidence: Sequence[str], answer: Sequence[str] = ()) -> Check:
    """`claim` with or without its citation markers; `evidence` the excerpts it cites;
    `answer` the answer's OTHER sentences, where an omitted limb may be restated."""
    claim = _ATTRIBUTION.sub("", verify.content(verify._MARKER.sub("", claim).strip()))
    sents = _sentences(evidence)
    pieces = parts(claim)
    anchors = [align(p, sents) for p in pieces]
    if not any(anchors):
        return Check(UNKNOWN)                    # nothing anchored: not applicable
    unknown: Check | None = None
    for piece, anchor in zip(pieces, anchors, strict=True):
        if anchor is None:
            ok = _supported(piece, evidence)
            if ok is False:
                return Check(FAIL, "UNSUPPORTED_CONCLUSION",
                             next(a for a in anchors if a), limbs=True)
            if ok is None:
                unknown = Check(UNKNOWN, limbs=True)
            continue
        for result in (_scope_check(piece, anchor), _limb_check(claim, anchor, answer)):
            if result.state == FAIL:
                return result
            if result.state == UNKNOWN and result.limbs:
                unknown = unknown or result
    return unknown or Check(PASS)


def combine(accepted: bool, result: Check) -> bool | str:
    """The owner's rule: the existing verifier's rejection stands; a structural FAIL
    rejects; an UNKNOWN on a sentence with limbs never accepts — ABSTAIN."""
    if not accepted or result.state == FAIL:
        return False
    if result.state == UNKNOWN and result.limbs:
        return ABSTAIN
    return True
