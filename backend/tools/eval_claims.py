"""P1 — a typed claim set built from REAL source text, and a scorer for any verifier.

    python3 -m tools.eval_claims build [--out DIR]          # DB read-only + legal-docs
    python3 -m tools.eval_claims score [--verifier production|hybrid|module:fn]
                                       [--split dev heldout unseen] [--out DIR]

Every item is (claim, cited evidence, label). The evidence is the FULL clause, with its
heading, its parent/sibling/child text, the definitions of the terms it uses and the text
of a clause it cross-refers to, where those exist. Nothing is written by hand: a
positive is the clause's own operative sentence under a fixed template; a negative is
the same sentence perturbed by CODE, one class per item (`CLASSES`), and a perturbation
that cannot be applied cleanly is skipped with its reason recorded — never forced.

Splits are by SOURCE DOCUMENT (no document in two splits):
  dev      the Legal Constitution L1.15 — the source PHASE 11's verifier was tuned on
  heldout  the nine statutes PHASE 11's claim sets cited (seen by p11, not by this dev)
  unseen   statutes p11 never cited, the current published website policies and three
           real contracts (second-tranche executed MSA, MSA draft round, executed NDA) —
           no verifier pattern was tuned on any of them
Items carrying a hard-case tag (`TAGS`) form the ADVERSARIAL subset, scored separately.

Zero Gemini, zero paid calls: the production verifier is the local NLI judge plus the
mechanical checks, exactly as `tools.eval_verification` runs them. Artefacts go to
/root/.legalmind/bench-cache/ (never git); counterparty names in real contracts are
redacted before any text is used, and the build refuses to write if one survives.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

CACHE = pathlib.Path("/root/.legalmind/bench-cache")
LEGAL_DOCS = pathlib.Path("/root/Legalmind.v1/legal-docs")

FAITHFUL = "FAITHFUL"
NEGATIVE = ("OVERSTATED", "REVERSED", "CONDITION_DROPPED", "EXCEPTION_OMITTED",
            "SCOPE_WIDENED", "NUMBER_CHANGED", "UNSUPPORTED_CONCLUSION")
CLASSES = (FAITHFUL, *NEGATIVE)
RARE = ("CONDITION_DROPPED", "EXCEPTION_OMITTED", "SCOPE_WIDENED", "NUMBER_CHANGED")
TAGS = ("modal_far", "double_negative", "nested_exception", "cross_reference",
        "defined_term")

# ── sentences ────────────────────────────────────────────────────────────────────────

_ABBREV = re.compile(r"(?:\b(?:Pvt|Ltd|No|Nos|s|ss|Rs|Co|Sr|cl|Art|viz|etc|i\.e|e\.g|"
                     r"w\.e\.f|Inc|Corp|Govt|Dept|vs|v)\.|\b[A-Z]\.)$")
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"“(A-Z])")
_JUNK = re.compile(r"w\.e\.f\.|\b(?:Ins|Subs|Omitted|omitted)\.? by\b|notifn|Gazette|"
                   r"\bvide\b|\|\s|http|www\.|@|^\W*$|~|--|\s[^\w\s(\[\"“]{2,}",
                   re.I)                    # the last three: OCR debris in a scanned Act
_LEAD_NUM = re.compile(r"^\s*(?:\d+[A-Z]?(?:\.\d+)*\.?|\([a-z0-9ivx]+\)|[a-z]\))[\s\u200b]*")
#: A statute's "12. Marginal note.\u2014(1)", an inline "CHIEF EXECUTIVE (1)" heading and a
#: paper's "Right to Erasure:" lead-in label \u2014 none of them part of the statement.
_CAPS_HEAD = re.compile(r"^(?:[A-Z][A-Z,'&-]+\s+){2,}(?:\(\d+\)\s*)?(?=[A-Z][a-z])")
_STAT_HEAD = re.compile(r"^[\"\u201c]?(?:\d+[A-Z]*\.\s*)?[A-Z][^\u2014\u2013.:;]{2,160}\.?"
                        r"\s*[\u2014\u2013]{1,2}\s*(?:\(\d+\)\s*)?")
_LABEL = re.compile(r"^[A-Z][\w/'()-]*(?: [\w/'()-]+){0,5}:\s+(?=\w)")
_MODAL = re.compile(r"\b(?:shall|must|may|will|should|cannot|is entitled|are entitled|"
                    r"is required|are required|means)\b")
_NEG_WORD = re.compile(r"\b(?:not|no|never|neither|nor|without|cannot|unless)\b|n't\b|"
                       r"\bnon-", re.I)
_EXCEPTION_WORD = re.compile(r"\b(?:except|save|provided(?:,)?(?: however,?)? that|"
                             r"subject to|unless|other than|excluding|notwithstanding)\b",
                             re.I)


def clean(text: str) -> str:
    text = re.sub("[\u200b­]", "", text).replace("\\", "")
    text = re.sub(r"\*+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def sentences(text: str) -> list[str]:
    """The text's sentences, rejoined after an abbreviation ("Pvt. Ltd.", "s. 74")."""
    out: list[str] = []
    for piece in _SPLIT.split(clean(text)):
        if out and _ABBREV.search(out[-1]):
            out[-1] += " " + piece
        else:
            out.append(piece)
    return out


def operative(sentence: str) -> bool:
    """A sentence worth restating: one complete statement with a legal verb in it."""
    words = sentence.split()
    return (8 <= len(words) <= 60 and bool(_MODAL.search(sentence))
            and sentence[-1:] in ".;" and not _JUNK.search(sentence)
            and sum(w.isupper() and len(w) > 2 for w in words) < len(words) / 3)


def statement(sentence: str) -> str:
    """The sentence as a claim: its own numbering and list punctuation removed."""
    s = _LEAD_NUM.sub("", _CAPS_HEAD.sub("", _STAT_HEAD.sub("", sentence))).strip()
    s = _LABEL.sub("", s)
    s = re.sub(r"\s+\d{1,3}\.$", "", s)                # a trailing footnote number
    s = re.sub(r"[;,]\s*(?:and|or)?\s*$", ".", s).rstrip(";").strip()
    if not s.endswith("."):
        s += "."
    return s[:1].upper() + s[1:]


# ── positives ────────────────────────────────────────────────────────────────────────

_FUNCTION_LEAD = frozenset(re.findall(r"\w+", """the a an any all each every no none if where when whenever while
    in upon on at by from with within under after before during to for as subject such
    this these those that there it its they their neither nothing notwithstanding unless
    save except whoever without should"""))
#: Wording swaps that keep the meaning — "shall"→"must" only before an action verb (a
#: "shall mean"/"shall be deemed" is not an obligation and is never touched).
_LEX = [(r"\bprior to\b", "before"), (r"\bpursuant to\b", "under"),
        (r"\bin accordance with\b", "in line with"), (r"\bforthwith\b", "immediately"),
        (r"\bupon\b", "on"), (r"\bcommence(s?)\b", r"begin\1"),
        (r"\bin the event that\b", "if"), (r"\bin respect of\b", "regarding"),
        (r"\bshould\b", "ought to"),
        (r"\bshall(?= (?:not )?(?:pay|provide|give|notify|maintain|keep|ensure|take|use|"
         r"comply|inform|furnish|deliver|return|destroy|indemnify|defend|protect|submit|"
         r"file|make|bear|refund|retain|disclose|hold|raise|issue|send|obtain|"
         r"implement|report|cooperate|remove)\b)", "must")]


def faithful(sentence: str, lead: str) -> list[tuple[str, str]]:
    s = statement(sentence)
    first = s.split(" ", 1)[0]
    body = s[0].lower() + s[1:] if first.lower() in _FUNCTION_LEAD else s
    out = [("attributed", f"{lead} {body}")]
    lex = s
    for pat, rep in _LEX:
        lex = re.sub(pat, rep, lex)
    if lex != s:
        out.append(("reworded", lex))
    return out


# ── negatives — one meaning change each, or a recorded reason why not ────────────────

_PARTY = (r"Customer|Client|Company|Provider|Service Provider|Supplier|Vendor|Partner|"
          r"Distributor|Licensee|Licensor|Receiving Party|Disclosing Party|Recipient|"
          r"User|Subscriber|LeapSwitch|Leapswitch|CloudPe|You|We|you|we")
_MUTUAL = re.compile(r"\b(?:each|either|both|neither) part(?:y|ies)\b|\bthe parties\b",
                     re.I)
_WORD_NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
             "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
             "twenty": 20, "thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90,
             "hundred": 100}
_UNIT = (r"(?:calendar |business |working )?(?:days?|months?|years?|hours?|minutes?|"
         r"weeks?)|%|per ?cent|percent|times")
_NUMBER = re.compile(
    rf"(?:\b(?:{'|'.join(_WORD_NUM)})(?:[- ]\w+)? )?\(?(?P<n>\d+(?:\.\d+)?)\)?"
    rf"\s*(?P<unit>{_UNIT})\b|(?<![\w(])(?P<w>{'|'.join(_WORD_NUM)}) (?P<wu>{_UNIT})\b"
    rf"|(?P<cur>Rs\.? ?|₹ ?|INR ?)(?P<m>\d[\d,]*)", re.I)
_SWAP_UNIT = {"day": "month", "month": "year", "year": "month", "hour": "day",
              "week": "month", "minute": "hour"}
_CONCLUSIONS = [
    (r"terminat", "breach of this provision entitles the other party to terminate the "
                  "arrangement immediately and without notice."),
    (r"void|enforce", "this provision is therefore void and cannot be enforced."),
    (r"compensat|damages", "any failure to comply entitles the affected party to "
                           "compensation of three times the fees paid."),
    (r"imprison|offence|criminal", "a breach of this provision is a criminal offence "
                                   "punishable with imprisonment."),
]


def _sub_first(pattern: str, repl: str, s: str, flags: int = 0) -> str | None:
    out = re.sub(pattern, repl, s, count=1, flags=flags)
    return out if out != s else None


def _overstated(s: str) -> tuple[str | None, str]:
    if re.search(r"\b(?:may|should|can|could) not\b|\bcannot\b", s):
        return None, "modal already negated — 'may not'→'must not' is not an overstatement"
    if re.search(r"\bas (?:the case )?may be\b|\bmay be prescribed\b", s) and \
            len(re.findall(r"\bmay\b", s)) == 1:
        return None, "only 'may' is idiomatic ('as may be prescribed')"
    for op, pat, rep in (("may_must", r"\bmay(?! be prescribed)(?! be,)\b", "must"),
                         ("should_must", r"\bshould\b", "must"),
                         ("can_must", r"\bcan\b", "must"),
                         ("entitled_obliged", r"\b(is|are) entitled to\b",
                          r"\1 obliged to"),
                         ("up_to_exactly", r"\bup to\b", "exactly"),
                         ("not_exceeding_exactly", r"\bnot exceeding\b", "exactly"),
                         ("some_all", r"\bsome\b", "all"),
                         ("reasonable_efforts_guarantee",
                          r"\b(?:commercially )?reasonable efforts to\b",
                          "an absolute guarantee to")):
        if op == "may_must" and re.search(r"\bas (?:the case )?may be\b", s):
            out = _sub_first(r"\bmay\b(?! be\b)", rep, s)
        else:
            out = _sub_first(pat, rep, s)
        if out:
            return out, op
    return None, "no permissive or bounded wording to overstate"


def _reversed(s: str) -> list[tuple[str, str]]:
    out = []
    removal = (("drop_not", r"\b(shall|may|must|will|does|do|is|are|can) not\b", r"\1"),
               ("cannot_can", r"\bcannot\b", "can"),
               ("no_longer", r"\bno longer\b", "still"))
    if _NEG_WORD.search(s):
        for op, pat, rep in removal:
            if (t := _sub_first(pat, rep, s)):
                out.append((op, t))
                break
    else:
        for op, pat, rep in (("insert_not", r"\b(shall|may|must|will|should)\b(?! be "
                              r"prescribed)", r"\1 not"),
                             ("insert_not_is", r"\b(is|are)\b(?! to\b)", r"\1 not"),
                             ("means_not", r"\bmeans\b", "does not mean")):
            if (t := _sub_first(pat, rep, s)):
                out.append((op, t))
                break
    for op, pat, rep in (("unless_if", r"\bunless\b", "if"),
                         ("at_least_most", r"\bat least\b", "at most"),
                         ("at_most_least", r"\bat most\b", "at least"),
                         ("not_less_more", r"\bnot less than\b", "not more than"),
                         ("not_more_less", r"\bnot more than\b", "not less than"),
                         ("before_after", r"\bbefore\b", "after"),
                         ("prior_after", r"\bprior to\b", "after")):
        if (t := _sub_first(pat, rep, s)):
            out.append((op, t))
            break
    return out


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def _drop_lead(s: str, lead: str) -> tuple[str, str] | None:
    """A leading limb, only where what follows its comma opens the main clause ("When
    X which, under section 134, would …" is cut mid-relative and refused)."""
    m = re.match(rf"^(?:{lead})\b[^,]{{8,220}},\s*(?P<rest>.+)$", s)
    if m and _MODAL.search(m["rest"]) and len(m["rest"].split()) >= 6 and (
            m["rest"][0].isupper() or m["rest"].split()[0] in _SUBJECT):
        return _cap(m["rest"]), s[:m.start("rest")]
    return None


#: A sentence never ends on one of these — a cut that leaves "Whoever abets any offence
#: shall." took the main verb with the limb, which is garbage, not a dropped limb.
_DANGLING = frozenset(re.findall(r"\w+", """shall may must will be been is are to as the of
    and or by a an for with in on not that which who whom treated deemed remain remains
    become becomes made kept except save unless provided if"""))
_SUBJECT = frozenset(re.findall(r"\w+", """the a an such any it he she they we you each
    every no neither all this that these those its their his her"""))


def _whole(head: str) -> bool:
    return (bool(_MODAL.search(head)) and len(head.split()) >= 6
            and head.split()[-1].lower().strip(",;:") not in _DANGLING)


def _drop_tail(s: str, tail: str) -> tuple[str, str] | None:
    """A limb at the end of the sentence, or one set off by commas in its middle."""
    # "where"/"when" without a comma is a relative clause ("the State where …"), not a
    # condition — only the words in `bare` open a limb without one.
    bare = r"if|only if|in the event(?: that| of)?|in case|except|save|provided|unless|" \
           r"other than|excluding"
    m = re.search(rf"(?P<cut>(?:[,:;]\s+(?:{tail})|\s+(?:{bare}))\b.+?)(?P<end>[.;]?)$", s)
    if m and not re.match(rf"[,:;]?\s+(?:{tail})\b", m["cut"]):
        m = None
    if m and len(m["cut"].split()) >= 4 and "," not in m["cut"][1:]:
        head = s[:m.start("cut")].rstrip(" ,;:")
        if _whole(head):
            return head + ".", m["cut"]
    m = re.search(rf",\s+(?:{tail})\b[^,]{{8,200}},\s+(?!and\b|or\b)", s)
    if m and m.group(0).count("(") == m.group(0).count(")"):
        out = s[:m.start()] + " " + s[m.end():]
        if _whole(s[:m.start()]) or _MODAL.search(s[m.end():]):
            return out, m.group(0)
    return None


def _condition_dropped(s: str) -> tuple[str | None, str]:
    lead = r"If|Where|When|Whenever|In the event(?: that| of)?|In case|Upon|On|Once|After"
    if (r := _drop_lead(s, lead)):
        return r[0], "lead_condition"
    tail = (r"if|where|when|whenever|in the event(?: that| of)?|in case|only if|"
            r"as long as|so long as|on condition that")
    if (r := _drop_tail(s, tail)):
        return r[0], "tail_condition"
    return None, "no separable condition limb"


def _exception_omitted(s: str) -> tuple[str | None, str]:
    if (r := _drop_lead(s, r"Subject to|Save as|Save|Except|Other than|Excluding")):
        return r[0], "lead_exception"
    tail = (r"except|save|provided(?:,)?(?: however,?)? that|unless|other than|"
            r"excluding|subject to")
    if (r := _drop_tail(s, tail)):
        return r[0], "tail_exception"
    t = re.sub(r"\s*\((?:other than|except|excluding|save)[^)]{6,}\)", "", s, count=1)
    if t != s:
        return t, "parenthetical_exception"
    return None, "no separable exception limb"


def _scope_widened(s: str) -> tuple[str | None, str]:
    if not _MUTUAL.search(s):
        t = _sub_first(rf"(?<![/\w])(?:[Tt]he |[Aa]n? )?(?:{_PARTY})(?![/\w])(?= (?:shall|must|may|"
                       r"will|agrees|is|are|can|should)\b)", "each party", s)
        if t:
            return _cap(t), "party_to_each_party"
    for op, pat, rep in (
            ("qualifier_to_all", r"\b(?:the )?(?:specific|particular|relevant|affected|"
                                 r"applicable) (Services?|services?|data|information|"
                                 r"Products?|products?)\b", r"all \1"),
            ("class_to_every", r"\b(?:a|an|any|every|the) (?:listed|private|public|small|"
                               r"foreign|one person|government|specified|registered|"
                               r"significant social media|social media|banking) "
                               r"(company|intermediary|entity)\b", r"every \1"),
            ("such_to_any", r"\bsuch (person|company|intermediary|party|services?|"
                            r"customer|notice|claim)\b", r"any \1")):
        if (t := _sub_first(pat, rep, s)):
            return t, op
    return None, "no narrowed party, service or class to widen"


def _numbers(s: str) -> list[tuple[str, str]]:
    m = _NUMBER.search(s)
    if not m:
        return []
    if m["cur"]:
        amount = int(m["m"].replace(",", ""))
        return [("amount", s[:m.start()] + f"{m['cur']}{amount * 2 + 1:,}" + s[m.end():])]
    n: int | float
    if m["w"]:
        n, unit = _WORD_NUM[m["w"].lower()], m["wu"]
    else:
        n, unit = float(m["n"]) if "." in m["n"] else int(m["n"]), m["unit"]
    new = round(n - 1, 2) if isinstance(n, float) else (n * 2 + 1 if n < 1000 else n * 2)
    out = [("figure", f"{s[:m.start()]}{new} {unit}{s[m.end():]}".replace(" %", "%"))]
    base = re.sub(r"s$", "", unit.split()[-1].lower())
    if base in _SWAP_UNIT:
        swapped = re.sub(rf"\b{base}", _SWAP_UNIT[base], unit, count=1)
        out.append(("unit", s[:m.start()] + m.group(0).replace(unit, swapped)
                    + s[m.end():]))
    return out


def _conclusion(s: str, evidence: str) -> tuple[str | None, str]:
    k = int(hashlib.sha256(s.encode()).hexdigest(), 16)
    for i in range(len(_CONCLUSIONS)):
        stem, text = _CONCLUSIONS[(k + i) % len(_CONCLUSIONS)]
        if not re.search(stem, evidence, re.I):
            return f"{s.rstrip('.')}; accordingly, {text}", f"conclusion_{stem[:8]}"
    return None, "every conclusion template's subject is in the evidence"


def perturb(sentence: str, evidence: str) -> tuple[list[tuple[str, str, str]],
                                                   list[tuple[str, str]]]:
    """(class, op, claim) for every perturbation that applies, and (class, reason) for
    every class that does not."""
    s = statement(sentence)
    made: list[tuple[str, str, str]] = []
    skipped: list[tuple[str, str]] = []

    def one(cls: str, result: tuple[str | None, str]) -> None:
        text, why = result
        if text and text != s:
            made.append((cls, why, text))
        else:
            skipped.append((cls, why))
    one("OVERSTATED", _overstated(s))
    rev = _reversed(s)
    made += [("REVERSED", op, t) for op, t in rev]
    if not rev:
        skipped.append(("REVERSED", "no modal, copula or polarity word to reverse"))
    one("CONDITION_DROPPED", _condition_dropped(s))
    one("EXCEPTION_OMITTED", _exception_omitted(s))
    one("SCOPE_WIDENED", _scope_widened(s))
    nums = _numbers(s)
    made += [("NUMBER_CHANGED", op, t) for op, t in nums]
    if not nums:
        skipped.append(("NUMBER_CHANGED", "no figure with a unit"))
    one("UNSUPPORTED_CONCLUSION", _conclusion(s, evidence))
    return made, skipped


def tags(sentence: str, roles: Iterable[str]) -> list[str]:
    s = statement(sentence)
    out = []
    if re.search(r"\b(?:shall|may|must|will)\b(?: not)?(?:\s*,|\s+(?:within|upon|at|on|"
                 r"by|forthwith|promptly|immediately|in|not later|from time|subject|"
                 r"where|if|unless|after|before|during|for)\b)", s):
        out.append("modal_far")
    if len(_NEG_WORD.findall(s)) >= 2:
        out.append("double_negative")
    if len(_EXCEPTION_WORD.findall(s)) >= 2:
        out.append("nested_exception")
    roles = set(roles)
    if "xref" in roles:
        out.append("cross_reference")
    if "definition" in roles:
        out.append("defined_term")
    return out


# ── units → items ────────────────────────────────────────────────────────────────────

@dataclass
class Unit:
    doc: str                 # redacted document id
    family: str              # constitution · statute · policy · contract
    ref: str                 # where in the document
    heading: str
    text: str                # the clause itself
    kind: str                # COMPANY_POSITION · LAW · CONTRACT
    authority: str
    lead: str                # the attribution a faithful restatement opens with
    context: list[tuple[str, str]] = field(default_factory=list)   # (role, text)


_DEF = re.compile(r"[\"“\u2018']([A-Z][\w\s/&-]{1,40}?)[\"”\u2019']\s*(?:\([^)]*\)\s*)?"
                  r"(?:shall\s+)?(?:means?|has the meaning|includes?)\b[^.;]{5,400}[.;]")
_XREF = re.compile(r"\b(?:subject to|under|in accordance with|as per|referred to in|"
                   r"as set out in)\s+(?:the provisions of\s+)?(?:Clause|clause|Section|"
                   r"section|Article)\s+(\d+[A-Z]?(?:\.\d+)*)", re.I)


def definitions(full_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for m in _DEF.finditer(clean(full_text)):
        out.setdefault(m.group(1).strip(), m.group(0))
    return out


def attach(unit: Unit, defs: dict[str, str], resolve: Callable[[str], str | None]) -> None:
    """Definitions of the terms the clause uses, and the clause it cross-refers to."""
    for term, text in sorted(defs.items()):
        if len(unit.context) < 8 and re.search(rf"\b{re.escape(term)}\b", unit.text) \
                and text not in unit.text:
            unit.context.append(("definition", text))
    for ref in dict.fromkeys(_XREF.findall(unit.text)):
        if (target := resolve(ref)) and target not in unit.text:
            unit.context.append(("xref", f"[{ref}] {target}"))


def _key(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)


_LIMITER = re.compile(r"^\W*(?:Provided|However|Notwithstanding|Except|Save|Nothing in|"
                      r"This (?:shall|does|will) not apply|The foregoing (?:shall|does) not|"
                      r"Explanation)\b")


def items_for(units: list[Unit], split: str, per_doc: int,
              seen: set[str]) -> tuple[list[dict], list[dict]]:
    """At most `per_doc` operative sentences per document, chosen by a stable hash; every
    sentence gives its faithful restatements and each perturbation that applies. The
    classes few sentences admit (`RARE`) are topped up from up to 3×`per_doc` further
    sentences — each with its own faithful restatements, so a sentence carrying a
    condition or an exception is measured for false rejection too."""
    by_doc: dict[str, list[tuple[int, Unit, str, bool]]] = defaultdict(list)
    for u in units:
        sents = sentences(u.text)
        for k, sent in enumerate(sents):
            if operative(sent) and (norm := statement(sent).lower()) not in seen:
                seen.add(norm)
                # a proviso in the NEXT sentence limits this one: restating it alone
                # would itself omit an exception, so it is never labelled faithful
                limited = k + 1 < len(sents) and bool(_LIMITER.match(sents[k + 1]))
                by_doc[u.doc].append((_key(u.doc, u.ref, sent), u, sent, limited))
    items: list[dict] = []
    skips: list[dict] = []
    for doc in sorted(by_doc):
        ranked = sorted(by_doc[doc], key=lambda t: t[0])[:per_doc * 4]
        for rank, (_, u, sent, limited) in enumerate(ranked):
            extra = rank >= per_doc
            evidence = [{"role": "clause", "text": f"{u.heading}\n{clean(u.text)}".strip(),
                         "kind": u.kind, "authority": u.authority}]
            evidence += [{"role": role, "text": clean(text)[:6000], "kind": u.kind,
                          "authority": u.authority} for role, text in u.context]
            whole = " ".join(e["text"] for e in evidence)
            tg = tags(sent, (role for role, _ in u.context))
            base = {"split": split, "doc": u.doc, "family": u.family, "unit": u.ref,
                    "source_sentence": statement(sent), "evidence": evidence, "tags": tg}
            negs, skipped = perturb(sent, whole)
            if extra:
                negs = [n for n in negs if n[0] in RARE]
                if not negs:
                    continue
                skipped = []
            if limited:
                skipped.append((FAITHFUL, "the next sentence is a proviso limiting it"))
            rows = [] if limited else [(FAITHFUL, op, t) for op, t in faithful(sent, u.lead)]
            rows += negs
            for cls, op, text in rows:
                items.append({**base, "id": f"{split}:{u.doc}:{u.ref}:{_key(sent) % 10**6}"
                                            f":{cls}:{op}",
                              "claim": text, "label": cls, "op": op})
            skips += [{"split": split, "doc": u.doc, "unit": u.ref, "class": cls,
                       "reason": why, "sentence": statement(sent)}
                      for cls, why in skipped]
    return items, skips


# ── sources (read-only) ──────────────────────────────────────────────────────────────

P11_STATUTES = ("Negotiable Instruments", "Information Technology Act", "Indian Contract",
                "Central Goods and Services", "Arbitration and Conciliation",
                "Digital Personal Data Protection Act", "Companies Act, 2013",
                "Companies Act, 1956", "Bharatiya Sakshya")
CONTRACTS = {"MSA-GRP-2026-07-30.pdf": "contract:msa-executed-2026-07",
             "MSA-Feb.pdf": "contract:msa-template-draft-round-2",
             "NDA.pdf": "contract:nda-executed-2026-06"}
_SKIP_CONST = re.compile(r"Drafting Notes|Source of Truth|· Status|Illustrative", re.I)


def _db():
    import psycopg2  # type: ignore[import-untyped]
    url = next(line.split("=", 1)[1].strip().strip("\"'")
               for line in pathlib.Path("/root/.legalmind.env").read_text().splitlines()
               if line.startswith("LEGALMIND_DATABASE_URL="))
    url = re.sub(r"^postgresql\+\w+://", "postgresql://", url)
    return psycopg2.connect(url, options="-c default_transaction_read_only=on")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def knowledge_units(cur, version: str, family: str, doc: str, kind: str,
                    lead: str) -> list[Unit]:
    cur.execute("select i.id, i.parent_id, i.kind, i.authority, i.content, i.breadcrumb, "
                "i.cross_references, i.section_path from assist.knowledge_items i "
                "join assist.knowledge_sources s on s.id = i.source_id "
                "where s.version = %s order by i.ordinal", (version,))
    rows = cur.fetchall()
    kids: dict = defaultdict(list)
    for r in rows:
        kids[r[1]].append(r)
    full = "\n".join(r[4] for r in rows if r[4])
    defs = definitions(full)
    position = {r[7]: r[4] for r in rows if r[2] == "PARAGRAPH" and r[4]
                and (r[5] or "").endswith("Company Position")}
    units = []
    for rid, parent, k, auth, content, crumb, xrefs, _path in rows:
        if k != "PARAGRAPH" or not content or "|" in content or _SKIP_CONST.search(
                crumb or ""):
            continue
        u = Unit(doc, family, _slug(crumb or "") + f":{str(rid)[:8]}", crumb or "",
                 content, kind, auth, lead)
        sib = "\n".join(r[4] for r in kids[parent] if r[0] != rid and r[4])
        if sib:
            u.context.append(("sibling", sib))
        for x in xrefs or []:
            if position.get(x):
                u.context.append(("xref", f"[Section {x}] {position[x]}"))
        attach(u, defs, lambda _ref: None)
        units.append(u)
    return units


def statute_units(cur, statute_id: str) -> tuple[str, list[Unit]]:
    cur.execute("select s.official_title, c.section_number, c.sub_section, "
                "c.marginal_note, c.content from assist.statute_chunks c join "
                "assist.statutes s on s.id = c.statute_id where s.id = %s "
                "order by c.ordinal", (statute_id,))
    rows = cur.fetchall()
    title = re.split(r" \(REPEALED| — ", rows[0][0])[0].removeprefix("The ")
    doc = "statute:" + _slug(title)
    by_section: dict[str, list[str]] = defaultdict(list)
    for _, sec, _sub, _note, content in rows:
        by_section[sec].append(content)
    defs = definitions("\n".join(by_section.get("2", [])))
    units = []
    for i, (_, sec, sub, note, content) in enumerate(rows):
        u = Unit(doc, "statute", f"s{sec}{f'({sub})' if sub else ''}#{i}",
                 f"{title} · section {sec} · {note or ''}", content, "LAW", "STATUTE",
                 f"Under the {title},")
        sib = "\n".join(c for c in by_section[sec] if c != content)
        if sib:
            u.context.append(("sibling", sib[:6000]))
        attach(u, defs, lambda ref: "\n".join(by_section.get(ref, []))[:6000] or None)
        units.append(u)
    return doc, units


#: A name in a real contract's preamble: a company suffix, or "the brand X".
_NAME = re.compile(r"((?:[A-Z][\w&.-]*[ \t]+){1,5})(?:Pvt\.?|Private|Limited|Ltd\.?|"
                   r"LLP|LLC|Inc\.?|Corporation|Corp\.?|GmbH|PLC|Pte)\b|"
                   r"brand[ \t]+([A-Z][\w-]+)|"
                   r"(?:between|BETWEEN|Between)[ \t]+((?:[A-Z][\w&.-]*[ \t]+){0,4}"
                   r"[A-Z][\w&.-]*)[ \t]*,")
_OURS = re.compile(r"leap\s*switch|cloudpe", re.I)
_GENERIC = {"The", "A", "An", "And", "AND", "BETWEEN", "Between", "Networks", "Private",
            "Limited", "Technologies", "Technology", "Solutions", "Services", "Systems",
            "India", "Company", "Pvt", "Ltd", "PVT", "LTD", "Disclosing", "Receiving", "Party", "Customer"}
_PERSONAL = re.compile(r"\bAttn\b|Attention|\b\d{6}\b|@|\bM(?:r|s|rs)\. ")
_SIGNATURE = re.compile(r"IN WITNESS|Signature|Name\s*:|Designation|Authori[sz]ed "
                        r"Signatory|For and on behalf", re.I)


def counterparty_names(preamble: str) -> list[str]:
    """The counterparty's name and each distinctive word of it, from the preamble."""
    names = set()
    for m in _NAME.finditer(preamble):
        words = [w.strip(".,") for w in
                 (m.group(1) or m.group(2) or m.group(3) or "").split()]
        words = [w for w in words if w not in _GENERIC]
        if words and not _OURS.search(" ".join(words)):
            names.add(" ".join(words))
            names.update(w for w in words if len(w) >= 3)
    return sorted(names, key=len, reverse=True)


def redact(text: str, names: list[str]) -> str:
    for n in names:
        text = re.sub(rf"\b{re.escape(n)}\b", "[COUNTERPARTY]", text)
    return text


def segment_units(rows: list[tuple[str | None, str]], doc: str, family: str = "contract",
                  kind: str = "CONTRACT", lead: str = "Under the agreement,",
                  ) -> tuple[list[Unit], list[str]]:
    """Units from a parsed document's (section number, text) rows — the parser's own
    numbering, never generated. The rows before the first numbered one are the
    preamble: its names are collected for redaction and the preamble itself is never
    used. A document the parser numbered nowhere is read row by row, its first five
    rows searched for names."""
    first = next((i for i, (n, _) in enumerate(rows) if n), None)
    pre = rows[:first] if first is not None else rows[:5]
    names = counterparty_names("\n".join(t for _, t in pre))
    numbered: list[list] = []
    for i, (num, content) in enumerate(rows[first or 0:]):
        if _SIGNATURE.search(content):
            break
        text = redact(_LEAD_NUM.sub("", content.strip()), names)
        if first is None:
            numbered.append([f"p{i}", text])
        elif num:
            numbered.append([num, text])
        elif numbered:
            numbered[-1][1] += "\n" + text
    # a notice address or a named person is never kept, not even as context
    numbered = [x for x in numbered if not _PERSONAL.search(x[1])]
    by_num = dict(numbered)
    defs = definitions("\n".join(t for _, t in numbered))
    units = []
    for i, (num, text) in enumerate(numbered):
        u = Unit(doc, family, f"cl{num}#{i}", f"Clause {num}", text, kind, kind, lead)
        parent = num.rsplit(".", 1)[0] if "." in num else None
        if parent and by_num.get(parent):
            u.context.append(("parent", by_num[parent]))
        children = "\n".join(t for n, t in numbered if n.startswith(num + "."))
        if children:
            u.context.append(("child", children[:6000]))
        attach(u, defs, lambda ref: by_num.get(ref))
        units.append(u)
    return units, names


def pdf_rows(path: pathlib.Path) -> list[tuple[str | None, str]]:
    from legalmind.ingestion import parsing
    return [(s.section_number, s.content)
            for s in parsing.parse_pdf(path.read_bytes(), ocr=False).segments]


def contract_units(path: pathlib.Path, doc: str) -> tuple[list[Unit], list[str]]:
    return segment_units(pdf_rows(path), doc)


def _sources() -> tuple[dict[str, list[Unit]], list[str]]:
    """The dev / heldout / unseen units, and the counterparty names found on the way."""
    splits: dict[str, list[Unit]] = {"dev": [], "heldout": [], "unseen": []}
    names: list[str] = []
    with _db() as conn:
        cur = conn.cursor()
        splits["dev"] += knowledge_units(cur, "L1.15", "constitution",
                                         "constitution:L1.15", "COMPANY_POSITION",
                                         "The company position is that")
        cur.execute("select id, official_title from assist.statutes order by 2")
        for sid, title in cur.fetchall():
            seen_p11 = any(title.startswith("The " + t) for t in P11_STATUTES)
            _, units = statute_units(cur, sid)
            splits["heldout" if seen_p11 else "unseen"] += units
        cur.execute("select s.version, s.title from assist.knowledge_sources s where "
                    "s.source_type like 'PUBLISHED_%%' and s.status = 'CURRENT'")
        for version, title in sorted(cur.fetchall()):
            splits["unseen"] += knowledge_units(cur, version, "policy",
                                                "policy:" + _slug(title),
                                                "COMPANY_POSITION",
                                                f"Under the {title},")
    for fname, doc in CONTRACTS.items():
        units, found = contract_units(LEGAL_DOCS / fname, doc)
        splits["unseen"] += units
        names += found
    return splits, names


def _redact_units(units: Iterable[Unit], names: list[str]) -> None:
    # A counterparty named in a contract may be named elsewhere too (the Constitution's
    # historical exceptions name one) — redacted in every source, not only its own.
    for u in units:
        u.text = redact(u.text, names)
        u.context = [(role, redact(text, names)) for role, text in u.context]


CAPS = {"constitution": 160, "statute": 22, "policy": 18, "contract": 45}


def _emit(split: str, units: list[Unit], seen: set[str], names: list[str],
          out_dir: pathlib.Path | None) -> tuple[dict, dict]:
    """The split's items (written only when `out_dir` is given), refusing to write if a
    counterparty name survived; returns its manifest and skip-count entries."""
    items: list[dict] = []
    skips: list[dict] = []
    for family in ("constitution", "statute", "policy", "contract"):
        fam = [u for u in units if u.family == family]
        if fam:
            got, sk = items_for(fam, split, CAPS[family], seen)
            items += got
            skips += sk
    if out_dir is not None:
        blob = json.dumps(items) + json.dumps(skips)
        leaked = [n for n in names if re.search(rf"\b{re.escape(n)}\b", blob)]
        if leaked:
            masked = [f"{n[0]}…({len(n)})" for n in leaked]   # never the name itself
            raise SystemExit(f"refusing to write {split}: {len(leaked)} counterparty "
                             f"name(s) survived redaction: {masked}")
        (out_dir / f"p1_claims_{split}.json").write_text(json.dumps(items, indent=1))
        (out_dir / f"p1_skips_{split}.json").write_text(json.dumps(skips, indent=1))
    entry = {"docs": sorted({i["doc"] for i in items}), "items": len(items),
             "by_class": dict(Counter(i["label"] for i in items)),
             "adversarial": sum(bool(i["tags"]) for i in items),
             "by_tag": dict(Counter(t for i in items for t in i["tags"]))}
    return entry, dict(Counter(f"{s['class']}: {s['reason']}" for s in skips))


def build(out_dir: pathlib.Path) -> dict:
    splits, names = _sources()
    _redact_units((u for units in splits.values() for u in units), names)
    manifest: dict = {"splits": {}, "skips": {}}
    seen: set[str] = set()
    for split, units in splits.items():
        manifest["splits"][split], manifest["skips"][split] = _emit(
            split, units, seen, names, out_dir)
    docs = [set(v["docs"]) for v in manifest["splits"].values()]
    assert not (docs[0] & docs[1] or docs[0] & docs[2] or docs[1] & docs[2])
    (out_dir / "p1_manifest.json").write_text(json.dumps(manifest, indent=1))
    return manifest


#: The FRESH split for one final run (coordinator, 2026-11-03): real documents in no
#: earlier split. MSA-GRP is already in `unseen`, so it is not here, and its
#: byte-identical production upload is skipped by hash.
UNSEEN2_PDFS = {"MSA.pdf": ("contract:msa-template-v2-2025-07", "contract",
                            "Under the agreement,"),
                "MSA-original.pdf": ("contract:msa-template-original", "contract",
                                     "Under the agreement,")}
for _brand, _title in (("leapswitch", "Leapswitch"), ("cloudpe", "CloudPe")):
    for _kind, _name in (("TOS", "Terms of Service"), ("SLA", "Service Level Agreement"),
                         ("AUP", "Acceptable Usage Policy"),
                         ("PRIVACY", "Privacy Policy")):
        UNSEEN2_PDFS[f"{_kind}-{_brand}.pdf"] = (
            f"policy-pdf:{_kind.lower()}-{_brand}", "policy",
            f"Under the {_title} {_name},")


def _db_names(cur) -> list[str]:
    """Every name the counterparty records hold — over-redaction is the safe side."""
    cur.execute("select name, legal_name, primary_contact_name, legal_contact_name "
                "from counterparties")
    out: set[str] = set()
    for row in cur.fetchall():
        for value in filter(None, row):
            if _OURS.search(value):
                continue
            out.add(value.strip())
            out.update(w.strip(".,()") for w in value.split()
                       if len(w.strip(".,()")) >= 4 and w.strip(".,()") not in _GENERIC)
    return sorted(out, key=len, reverse=True)


def _title_names(cur, corpus: str) -> list[str]:
    """Words of the uploads' contract titles and filenames that the corpus never uses in
    lower case — a client's name, which a title carries even where the preamble regex
    and the counterparty records both miss it (two clients did, on the first run)."""
    cur.execute("select c.name, v.original_filename from contracts c "
                "join document_versions v on v.contract_id = c.id")
    lower = set(re.findall(r"\b[a-z][a-z&]+\b", corpus))
    out = set()
    for row in cur.fetchall():
        for value in filter(None, row):
            for w in re.findall(r"[A-Za-z][A-Za-z&]{2,}", value):
                if w[0].isupper() and w.lower() not in lower and w not in _GENERIC and not _OURS.search(w):
                    out.add(w)
    return sorted(out, key=len, reverse=True)


def build_unseen2(out_dir: pathlib.Path) -> dict:
    """`unseen2`, deduplicated against EVERY operative sentence of dev / heldout /
    unseen (sampled or not), sharing no document with them. The earlier splits' files
    are never rewritten; their documents are re-derived only to fill `seen`, and the
    build stops if they no longer match the manifest."""
    splits, names = _sources()
    used = {hashlib.sha256((LEGAL_DOCS / f).read_bytes()).hexdigest() for f in CONTRACTS}
    fresh: list[Unit] = []
    for fname, (doc, family, lead) in UNSEEN2_PDFS.items():
        kind = "CONTRACT" if family == "contract" else "COMPANY_POSITION"
        units, found = segment_units(pdf_rows(LEGAL_DOCS / fname), doc, family, kind,
                                     lead)
        fresh += units
        names += found
        used.add(hashlib.sha256((LEGAL_DOCS / fname).read_bytes()).hexdigest())
    uploads = 0
    with _db() as conn:
        cur = conn.cursor()
        names += _db_names(cur)
        cur.execute("select distinct on (v.file_hash) v.id, v.file_hash from "
                    "document_versions v order by v.file_hash, v.created_at")
        for vid, file_hash in cur.fetchall():
            if file_hash in used:
                continue
            cur.execute("select section_number, content from document_evidence where "
                        "document_version_id = %s order by start_offset nulls last, id",
                        (vid,))
            rows = [(n, c) for n, c in cur.fetchall() if c]
            units, found = segment_units(rows, f"upload:{file_hash[:12]}")
            fresh += units
            names += found
            uploads += 1
        corpus = "\n".join(u.text for units in [*splits.values(), fresh] for u in units)
        names += _title_names(cur, corpus)
    names = sorted(set(names), key=len, reverse=True)
    _redact_units([u for units in splits.values() for u in units] + fresh, names)
    seen: set[str] = set()
    manifest = json.loads((out_dir / "p1_manifest.json").read_text())
    for split, units in splits.items():           # fills `seen` only — nothing written
        entry, _ = _emit(split, units, seen, names, None)
        if entry["docs"] != manifest["splits"][split]["docs"]:
            raise SystemExit(f"{split} no longer rebuilds to its recorded documents")
    entry, skipped = _emit("unseen2", fresh, seen, names, out_dir)
    earlier = set().union(*(set(v["docs"]) for k, v in manifest["splits"].items()
                            if k != "unseen2"))
    assert not set(entry["docs"]) & earlier, "unseen2 shares a document with a split"
    entry["uploads_read"] = uploads
    manifest["splits"]["unseen2"] = entry
    manifest["skips"]["unseen2"] = skipped
    (out_dir / "p1_manifest.json").write_text(json.dumps(manifest, indent=1))
    return {"unseen2": entry, "skips": skipped}


# ── scoring ──────────────────────────────────────────────────────────────────────────

#: True accepts, False rejects, ABSTAIN neither (the structural layer could not parse a
#: sentence with limbs) — counted on its own, never as an acceptance or a rejection.
ABSTAIN = "ABSTAIN"
Verdict = bool | str
Verifier = Callable[[dict], Verdict]


def production(item: dict) -> bool:
    """The shipped claim check: `verify.judge` (local NLI, polarity, obligation and kind
    checks) AND the mechanical `answer.check` — a claim is accepted only if both pass."""
    from legalmind.assist.retrieval import evidence as evidence_mod
    from legalmind.assist.synthesis import answer
    from legalmind.assist.verification import verify
    texts = [e["text"] for e in item["evidence"]]
    kinds = [e["kind"] for e in item["evidence"]]
    auths = [e["authority"] for e in item["evidence"]]
    sentence = f"{item['claim'].rstrip('.')} [1]."
    j = verify.judge(sentence, texts, kinds, auths,
                     context=answer.is_context(sentence, ()))
    if j.verdict == "UNSUPPORTED" and j.reason == "verifier unavailable":
        raise RuntimeError("the NLI model is not available — a baseline without it "
                           "would score every claim rejected")
    semantic = j.verdict == "CONTEXT" or (j.verdict == "SUPPORTED" and not j.kind_error)
    if not semantic:
        return False
    payload = answer.Payload(texts, kinds, [str(n) for n in range(1, len(texts) + 1)],
                             None, None, "", (), ())
    return not answer.check(sentence, payload, evidence_mod.Bundle((), (), (), False))


def hybrid(item: dict) -> Verdict:
    """`production` and the deterministic structural layer (`structural.check`) combined
    by the owner's rule (`structural.combine`): a structural FAIL rejects, an UNKNOWN on
    a sentence with limbs ABSTAINS."""
    from legalmind.assist.verification import structural
    return structural.combine(production(item), structural.check(
        item["claim"], [e["text"] for e in item["evidence"]]))


def load_verifier(spec: str) -> Verifier:
    if spec in ("production", "hybrid"):
        return {"production": production, "hybrid": hybrid}[spec]
    module, _, fn = spec.partition(":")
    return getattr(importlib.import_module(module), fn)


def score(items: list[dict], verifier: Verifier) -> dict:
    """Per class: how many the verifier ACCEPTED, and how many it ABSTAINED on, of how
    many — an accepted negative is a miss; for FAITHFUL `rejected` counts only the
    claims it REJECTED (an abstention is reported apart, never as either)."""
    def table(rows: list[tuple[dict, Verdict]]) -> dict:
        out = {}
        for cls in CLASSES:
            got = [v for it, v in rows if it["label"] == cls]
            out[cls] = {"accepted": sum(v is True for v in got), "n": len(got),
                        "abstained": sum(v == ABSTAIN for v in got)}
        f = out[FAITHFUL]
        f["rejected"] = f["n"] - f["accepted"] - f["abstained"]
        return out

    def verdict(it: dict) -> Verdict:
        v = verifier(it)
        return v if v == ABSTAIN else bool(v)
    rows = [(it, verdict(it)) for it in items]
    failures = [{"id": it["id"], "class": it["label"], "op": it["op"],
                 "claim": it["claim"], "evidence_id": f"{it['doc']}#{it['unit']}",
                 "tags": it["tags"], "verdict": v}
                for it, v in rows
                if v == ABSTAIN or (v is True) != (it["label"] == FAITHFUL)]
    by_op: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for it, v in rows:
        by_op[f"{it['label']}:{it['op']}"][0] += v is True
        by_op[f"{it['label']}:{it['op']}"][1] += 1
    return {"all": table(rows),
            "adversarial": table([r for r in rows if r[0]["tags"]]),
            "by_family": {f: table([r for r in rows if r[0]["family"] == f])
                          for f in sorted({it["family"] for it in items})},
            "by_tag": {t: table([r for r in rows if t in r[0]["tags"]]) for t in TAGS},
            "by_op_accepted": {k: {"accepted": a, "n": n}
                               for k, (a, n) in sorted(by_op.items())},
            "failures": failures}


_NAMES = {"OVERSTATED": "overstated accepted", "REVERSED": "reversed accepted",
          "CONDITION_DROPPED": "condition-dropped accepted",
          "EXCEPTION_OMITTED": "exception-omitted accepted",
          "SCOPE_WIDENED": "scope-widened accepted",
          "NUMBER_CHANGED": "number-changed accepted",
          "UNSUPPORTED_CONCLUSION": "unsupported conclusion accepted",
          FAITHFUL: "faithful falsely rejected"}


def _cell(t: dict, cls: str) -> str:
    c = t[cls]
    k = c["rejected"] if cls == FAITHFUL else c["accepted"]
    return f"{k}/{c['n']}" if c["n"] else "—"


def markdown(results: dict[str, dict], verifier: str) -> str:
    splits = list(results)
    head = " | ".join(f"{s} | {s} adversarial" for s in splits)
    lines = [f"# P1 claim-check baseline — verifier `{verifier}`", "",
             "Counts are exact: misses / denominator (lower is better everywhere).", "",
             f"| metric | {head} |", "|---|" + "---|" * (2 * len(splits))]
    for cls in (*NEGATIVE, FAITHFUL):
        cells = " | ".join(f"{_cell(results[s]['all'], cls)} | "
                           f"{_cell(results[s]['adversarial'], cls)}" for s in splits)
        lines.append(f"| {_NAMES[cls]} | {cells} |")
    if any(results[s]["all"][c].get("abstained") for s in splits for c in CLASSES):
        lines += ["", "Abstained (neither accepted nor rejected) / denominator:", "",
                  f"| class | {head} |", "|---|" + "---|" * (2 * len(splits))]
        for cls in (*NEGATIVE, FAITHFUL):
            lines.append(f"| {cls} | " + " | ".join(
                f"{results[s][t][cls].get('abstained', 0)}/{results[s][t][cls]['n']}"
                for s in splits for t in ("all", "adversarial")) + " |")
    for s in splits:
        lines += ["", f"## {s} — by source family", "",
                  "| metric | " + " | ".join(results[s]["by_family"]) + " |",
                  "|---|" + "---|" * len(results[s]["by_family"])]
        for cls in (*NEGATIVE, FAITHFUL):
            lines.append(f"| {_NAMES[cls]} | " + " | ".join(
                _cell(t, cls) for t in results[s]["by_family"].values()) + " |")
        lines += ["", f"### {s} — failures ({len(results[s]['failures'])})", ""]
        lines += [f"- `{f['class']}:{f['op']}`"
                  f"{' ABSTAIN' if f.get('verdict') == ABSTAIN else ''}"
                  f" `{f['evidence_id']}` — {f['claim'][:220]}"
                  for f in results[s]["failures"]]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", default=str(CACHE))
    b2 = sub.add_parser("build-unseen2")
    b2.add_argument("--out", default=str(CACHE))
    s = sub.add_parser("score")
    s.add_argument("--verifier", default="production")
    s.add_argument("--split", nargs="+", default=["dev", "heldout", "unseen"])
    s.add_argument("--set", default=str(CACHE))
    s.add_argument("--out", default=str(CACHE / "p1_baseline"))
    args = ap.parse_args()
    if args.cmd == "build":
        print(json.dumps(build(pathlib.Path(args.out)), indent=1))
        return 0
    if args.cmd == "build-unseen2":
        print(json.dumps(build_unseen2(pathlib.Path(args.out)), indent=1))
        return 0
    verifier = load_verifier(args.verifier)
    results = {}
    for split in args.split:
        items = json.loads((pathlib.Path(args.set) / f"p1_claims_{split}.json").read_text())
        results[split] = score(items, verifier)
        print(split, json.dumps(results[split]["all"]), flush=True)
    pathlib.Path(args.out + ".json").write_text(json.dumps(results, indent=1))
    pathlib.Path(args.out + ".md").write_text(markdown(results, args.verifier))
    return 0


if __name__ == "__main__":
    sys.exit(main())
