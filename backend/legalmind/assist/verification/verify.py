"""Semantic claim verification — roadmap §11–§12, PHASE 11 (`AM-90`).

    result = verify.check_answer(text, payload)

The PHASE 10 checks (`answer.check`) are mechanical: markers, figures, attribution,
negation, history wording, verdicts. They cannot see that a sentence says something its
cited text does not. This module reads each claim against the evidence with a LOCAL
entailment model (an NLI cross-encoder, provisioned and checksum-verified exactly like
the reranker; nothing leaves the machine, `AM-30` t1) and decides, per claim:

  SUPPORTED     an excerpt — or the claim's cited excerpts read together — entails it
  CONTRADICTED  a cited excerpt contradicts it and none entails it
  UNSUPPORTED   nothing shown entails it
  CONTEXT       the claim cites only [A]/[M] — user context or a stated gap, which the
                mechanical checks own (a user figure is context, never evidence)

and assigns the CITATIONS itself: a claim keeps only the cited excerpts that entail it,
and a claim the model cited to a nearby excerpt is re-cited to the shown excerpt that
does entail it (never to another kind than the claim names). One claim that is not
SUPPORTED, or that attributes content to the wrong kind of source ("the law says …" from
the company's own reading of the law), fails the whole answer — fail closed, never a
partly verified answer (`AM-25` r5). Outside the generating model (`AM-28` r2): this
module imports no prompt and no generation code.
"""
from __future__ import annotations

import logging
import math
import re
import threading
from dataclasses import dataclass

from legalmind import config
from legalmind.assist.ingestion.onnx_backend import OnnxCrossEncoderBackend, model_root
from legalmind.assist.query import query_plan as qp
from legalmind.assist.verification import guardrails
from legalmind.observability.logs import log_event

#: Entailment probability a claim needs from its evidence; contradiction probability at
#: which a cited excerpt is said to contradict it. Calibrated on the annotated PHASE 10
#: claims (`tests/assist_eval/verification_eval_2026-09-25.json`).
ENTAIL = 0.5
CONTRA = 0.6
#: Sentences joined into one premise per excerpt (by content-word overlap), its cap,
#: and the deterministic polarity/modality screen (`guardrails`, `AM-76`) on top.
PREMISE_SENTENCES = 4
PREMISE_CHARS = 1600
POLARITY = True
#: A second route to SUPPORTED when entailment is not confident: the claim's content
#: words mostly present in its cited premise, and no contradiction. Every polarity,
#: modality, deontic, clause and kind check still applies after it. None = off.
LEXICAL: float | None = 0.6
#: STRICT: a claim entailment cannot confirm fails. Otherwise (precision mode) only
#: positive evidence of an error fails it — a contradiction, a polarity or obligation
#: shift, a kind error, an unevidenced figure, a verdict — or grounding below GROUNDED
#: (the claim's words are mostly not in its evidence: likely invented).
STRICT = False
GROUNDED = 0.34
_LABELS = ("contradiction", "entailment", "neutral")     # the provisioned head's order

_MARKER = re.compile(r"\[(\d{1,2}|A|M)\]")
# The LAW as the source of the claim: "under Indian law", or a law, an Act or its
# section as the SUBJECT of a legal verb ("the Act provides …", "Section 74 permits …").
# Naming an Act a clause chooses ("arbitration under the Arbitration and Conciliation
# Act 1996") is not presenting the Act as the source. Case matters: "act" the verb.
_LAW_SOURCE = re.compile(
    r"(?i:^\W*under (?:indian )?law\b)|\b(?:[Tt]he law|[Ss]tatute|the statute|"
    r"[A-Z][A-Za-z()]*(?: [A-Za-z()]+){0,8} Act(?:,? \d{4})?|[Ss]ections? \d+\w*"
    r"(?:(?: and|,|\u2013|-) ?\d+\w*)*(?: of the [A-Za-z ()]+ Act(?:,? \d{4})?)?)"
    r"(?: itself)?,? (?:says|say|provides|provide|states|state|requires|require|"
    r"permits|permit|entitles|entitle|allows|allow|prohibits|prohibit|mandates|"
    r"treats|treat|makes|make|specifies|specify|defines|define)\b")
_READING = re.compile(r"\b(?:reading|reads|read by|interpret\w*|understand\w*|view|"
                      r"explain\w*|legal validation)\b", re.I)
_CONTRACT_SAYS = re.compile(r"\b(?:the|your|this|their|signed|executed) (?:contract|"
                            r"agreement) (?:says|states|provides|specifies)\b", re.I)
# Deontic strength (PHASE 11): "should"/"may" reported as "must" is an overstatement the
# entailment model accepts (0.64 of "may"→"must" perturbations passed it).
_STRONG = re.compile(r"\b(?:must|shall|is required|are required|required to|mandatory|"
                     r"obliged|obligat\w+)\b", re.I)
_WEAK = re.compile(r"\b(?:should|may|can|could|consider\w*|recommended|appropriate)\b",
                   re.I)

_lock = threading.Lock()
_backend: OnnxCrossEncoderBackend | None = None
_failed = False


def _load() -> OnnxCrossEncoderBackend | None:
    global _backend, _failed
    if _backend is not None or _failed:
        return _backend
    with _lock:
        if _backend is None and not _failed:
            repo, rev = config.nli_model_repo(), config.nli_model_revision()
            try:
                _backend = OnnxCrossEncoderBackend(
                    model_root() / repo.replace("/", "__") / rev)
            except Exception as exc:
                _failed = True
                log_event("assist.verify.unavailable", level=logging.WARNING,
                          operational_failure=True, reason=type(exc).__name__,
                          model=f"{repo}@{rev}")
    return _backend


def reset_for_tests() -> None:
    global _backend, _failed
    _backend, _failed = None, False


_memo: dict[tuple[str, str], tuple[float, float]] = {}


def entailment(pairs: list[tuple[str, str]]) -> list[tuple[float, float]] | None:
    """(entailment, contradiction) probability per (premise, claim); None when the
    model is not available — the caller fails closed. Pairs already scored during the
    current `check_answer` are not scored again (its first stage is batched)."""
    backend = _load()
    if backend is None:
        return None
    todo = [p for p in dict.fromkeys(pairs) if p not in _memo]
    for p, row in zip(todo, backend.pair_logits(todo), strict=True):
        top = max(row)
        exp = [math.exp(x - top) for x in row]
        total = sum(exp)
        _memo[p] = (exp[_LABELS.index("entailment")] / total,
                    exp[_LABELS.index("contradiction")] / total)
    return [_memo[p] for p in pairs]


_HISTORY_LABEL = "[historical evidence, not current policy]"
_READING_LABEL = "[the company's reading of the law]"
# A line break that is not the end of a sentence, a paragraph, a list item or a label:
# statute text is hard-wrapped mid-sentence, and splitting on it fed the model broken
# fragments (s. 179 read as three half-sentences, entailment 0.001).
_WRAP = re.compile(r"(?<![.:;!?|])[ \t]*\n(?![ \t]*(?:\n|[-*•(\[|]|\d+[.)]))")


def windows(text: str) -> list[tuple[str, str | None]]:
    """Sentences of an excerpt in order, each with the label its paragraph carries —
    a Constitution section mixes current policy, the company's reading of the law and
    historical evidence, and a claim's kind is the kind of the SENTENCE supporting it."""
    out: list[tuple[str, str | None]] = []
    for line in (x.strip() for x in _WRAP.sub(" ", text).split("\n")):
        if not line:
            continue
        label = (_HISTORY_LABEL if line.startswith(_HISTORY_LABEL)
                 else _READING_LABEL if line.startswith(_READING_LABEL) else None)
        out += [(s, label) for s in guardrails._SENTENCES.split(line) if s.strip()]
    return out or [(text, None)]


def _ranked(claim: str, text: str) -> list[tuple[int, tuple[str, str | None]]]:
    words = guardrails._content_words(claim)
    sents = windows(text)
    return sorted(enumerate(sents),
                  key=lambda kv: -len(words & guardrails._content_words(kv[1][0])))


def premises(claim: str, text: str) -> list[str]:
    """The passages the entailment model reads for one excerpt: the claim's
    best-overlapping sentences JOINED in document order (a legal paraphrase draws on
    several sentences — one-sentence windows rejected 48% of supported claims), and the
    two best sentences on their own."""
    ranked = _ranked(claim, text)
    top = sorted(k for k, _ in ranked[:PREMISE_SENTENCES])
    sents = windows(text)
    joined = " ".join(_said(*sents[k]) for k in top)[:PREMISE_CHARS]
    return [joined] + [_said(sent, label)[:PREMISE_CHARS]
                       for _, (sent, label) in ranked[:2] if len(top) > 1]


def _said(sentence: str, label: str | None) -> str:
    """A sentence with the kind its paragraph is labelled as, stated for the model — a
    Constitution section mixes the company's reading of the law and history into its
    policy text, and the section's own frame would mislabel them."""
    if label is None or sentence.startswith(label):
        return sentence
    lead = {_HISTORY_LABEL: "Historically, not as current policy:",
            _READING_LABEL: "In the company's reading of the law:"}[label]
    return f"{lead} {sentence}"


def support_kinds(claim: str, text: str, kind: str, authority: str) -> set[str]:
    """The kinds of the two sentences that best carry the claim."""
    labelled = _HISTORY_LABEL in text or _READING_LABEL in text   # a Constitution section
    out = set()
    for _, (_, label) in _ranked(claim, text)[:2]:
        if label == _HISTORY_LABEL or (not labelled and kind == qp.HISTORICAL_EXCEPTION):
            out.add("HISTORY")
        elif label == _READING_LABEL or (not labelled
                                          and authority == "SECONDARY_REFERENCE"):
            out.add("READING")
        else:
            out.add({qp.LAW: "LAW", qp.CONTRACT: "CONTRACT"}.get(kind, "POSITION"))
    return out


@dataclass(frozen=True)
class Judgement:
    sentence: str
    verdict: str                      # SUPPORTED · CONTRADICTED · UNSUPPORTED · CONTEXT
    cited: tuple[int, ...]            # what the model cited
    citations: tuple[int, ...]        # what the verifier assigns (SUPPORTED only)
    entail: float
    contra: float
    kind_error: str | None = None
    reason: str | None = None


#: What each kind of source IS, stated at the head of its premise. A claim says "the
#: company position permits …"; its excerpt never names itself, and without this the
#: model scored such a claim neutral (entailment 0.16 against the very clause). It also
#: lets the model see a kind being misattributed ("the law says" against the company's
#: own reading).
_KIND_FRAME = {qp.COMPANY_POSITION: "The company position states:",
               qp.CONTRACT: "The contract states:",
               qp.LAW: "The law states:",
               qp.HISTORICAL_EXCEPTION: "A past negotiated exception, not current "
                                        "policy, stated:"}
_READING_FRAME = "The company's reading of the law states:"
_DISCOURSE = re.compile(r"^(?:yes|no|additionally|furthermore|further|moreover|similarly|"
                        r"also|"
                        r"in contrast|however|as a result|regarding [^,]{0,40}|in short|"
                        r"specifically|importantly|finally)\s*,\s*", re.I)


def frame(kind: str, authority: str) -> str:
    return _READING_FRAME if authority == "SECONDARY_REFERENCE" else _KIND_FRAME[kind]


def content(claim: str) -> str:
    """The claim without its list dash or leading discourse word — never its
    attribution, which is part of what is verified."""
    text = claim.strip(" -")
    text = _DISCOURSE.sub("", text)
    return text[:1].upper() + text[1:]


# Where a compound claim divides: "X, while Y", "X; Y", "X, though Y". A clause shorter
# than CLAUSE_WORDS is a fragment, not a claim, and is not read on its own.
_CLAUSES = re.compile(r";\s+|,\s+(?:and|but|while|whereas|though|although|however)\s+|"
                      r"\s+(?:whereas|while|though|although)\s+", re.I)
CLAUSE_WORDS = 6
#: A clause of an otherwise entailed claim is contradicted only when the model is sure.
CLAUSE_CONTRA = 0.9
NEG_SCOPE = 8


def clauses(claim: str) -> list[str]:
    parts = [p.strip(" ,.") for p in _CLAUSES.split(content(claim))]
    parts = [p for p in parts if len(p.split()) >= CLAUSE_WORDS]
    return parts if len(parts) > 1 else []


def _nli(jobs: list[tuple[object, str, str]]) -> dict | None:
    """One batched call: {key: (entailment, contradiction)} as the max over its pairs."""
    probs = entailment([(p, h) for _, p, h in jobs])
    if probs is None:
        return None
    out: dict = {}
    for (key, _, _), (e, c) in zip(jobs, probs, strict=True):
        pe, pc = out.get(key, (0.0, 0.0))
        out[key] = (max(pe, e), max(pc, c))
    return out


def judge(sentence: str, evidence: list[str], kinds: list[str],
          authorities: list[str], *, context: bool = False) -> Judgement:
    """`context` — the caller's mechanical finding that the sentence reports an ABSENCE
    ("the position does not state 6 months") or a gap: entailment cannot confirm what a
    text does not say, and the figure check already proved it (`answer.check`).

    Staged, cheapest first: (1) the whole claim against each cited excerpt's joined
    premise — most supported claims end here; (2) only if that fails: single-sentence
    premises, the cited excerpts read together, and every CLAUSE entailed on its own;
    (3) only if everything cited fails: the other shown excerpts (a mis-citation). A
    compound claim that passes is then read clause by clause for a contradiction — a
    negated clause inside a broadly entailed sentence is still a false claim."""
    marks = _MARKER.findall(sentence)
    cited = tuple(int(m) for m in marks if m.isdigit() and 1 <= int(m) <= len(evidence))
    claim = _MARKER.sub("", sentence).strip(" -")
    if not cited or context:
        return Judgement(sentence, "CONTEXT", (), (), 0.0, 0.0)
    frames = [frame(k, a) for k, a in zip(kinds, authorities, strict=True)]
    hyp = content(claim)

    def joined(i: int, text: str = claim) -> str:
        return f"{frames[i - 1]} {premises(text, evidence[i - 1])[0]}"

    scored = _nli([(i, joined(i), hyp) for i in cited])
    if scored is None:
        return Judgement(sentence, "UNSUPPORTED", cited, (), 0.0, 0.0,
                         reason="verifier unavailable")
    kept = tuple(i for i in cited if scored[i][0] >= ENTAIL)
    parts = clauses(claim)
    if not kept:                                              # stage 2
        jobs: list[tuple[object, str, str]] = [
            (i, f"{frames[i - 1]} {p}", hyp)
            for i in cited for p in premises(claim, evidence[i - 1])[1:]]
        if len(cited) > 1:
            both = " ".join(joined(i) for i in cited)[:PREMISE_CHARS * 2]
            jobs.append(("together", both, hyp))
        jobs += [(("clause", k, i), joined(i, part), part)
                 for k, part in enumerate(parts) for i in cited]
        more = _nli(jobs) or {}
        for key, val in more.items():
            if isinstance(key, int):
                scored[key] = (max(scored[key][0], val[0]), max(scored[key][1], val[1]))
        kept = tuple(i for i in cited if scored[i][0] >= ENTAIL)
        if not kept and more.get("together", (0.0, 0.0))[0] >= ENTAIL:
            kept = cited
        if not kept and parts and all(
                max(more.get(("clause", k, i), (0.0, 0.0))[0] for i in cited) >= ENTAIL
                for k in range(len(parts))):
            kept = cited
    if not kept and LEXICAL is not None:      # a faithful paraphrase keeps its words
        words = guardrails._content_words(claim)
        for i in cited:
            premise = premises(claim, evidence[i - 1])[0]
            share = len(words & guardrails._content_words(premise)) / max(1, len(words))
            if share >= LEXICAL and scored[i][1] < CONTRA:
                kept = (*kept, i)
    if not kept:                                              # stage 3
        others = [i for i in range(1, len(evidence) + 1) if i not in cited]
        alt = _nli([(i, joined(i), hyp) for i in others]) or {}
        good = [i for i in others if alt[i][0] >= ENTAIL]
        if good:
            kept = (max(good, key=lambda i: alt[i][0]),)
            scored[kept[0]] = alt[kept[0]]
    worst_con = max(scored.get(i, (0.0, 0.0))[1] for i in cited)
    if not kept and not STRICT and worst_con < CONTRA \
            and _grounding(claim, cited, evidence) >= GROUNDED:
        # PRECISION MODE: entailment is merely unsure (neutral) about a claim whose
        # words are in its cited evidence — not evidence of an error. Keep it; every
        # check below still runs on it.
        kept = cited
    if not kept:
        verdict = "CONTRADICTED" if worst_con >= CONTRA else "UNSUPPORTED"
        return Judgement(sentence, verdict, cited, (), max(scored[i][0] for i in cited),
                         worst_con)
    best_ent = max(scored[i][0] for i in kept)
    if parts:                                   # a negated clause inside a compound
        each = _nli([(k, joined(i, part), part)
                     for k, part in enumerate(parts) for i in kept]) or {}
        if any(c >= CLAUSE_CONTRA and e < ENTAIL for e, c in each.values()):
            return Judgement(sentence, "CONTRADICTED", cited, (), best_ent, worst_con,
                             reason="a clause its evidence contradicts")
    shifted = _aligned_shift(claim, " ".join(
        " ".join(s for s, _ in windows(evidence[i - 1])) for i in kept))
    if shifted:
        return Judgement(sentence, "CONTRADICTED", cited, (), best_ent, worst_con,
                         reason=shifted)
    if POLARITY:
        shift = guardrails._entailment_failure(
            claim, guardrails._content_words(claim),
            [evidence[i - 1] for i in kept], quantities=False)
        if shift:
            return Judgement(sentence, "CONTRADICTED", cited, (), best_ent, worst_con,
                             reason=shift)
    kind = _kind_error(claim, set().union(*(
        support_kinds(claim, evidence[i - 1], kinds[i - 1], authorities[i - 1])
        for i in kept)))
    return Judgement(sentence, "SUPPORTED", cited, kept, best_ent, worst_con, kind)


_TOKEN = re.compile(r"[a-z']+")
_NEG_WORDS = frozenset({"not", "no", "never", "cannot", "can't", "don't", "doesn't",
                        "isn't", "aren't", "won't", "nor", "without"})
_AUX = frozenset({"be", "been", "is", "are", "was", "were", "have", "has", "had", "to",
                  "the", "a", "an", "any", "its", "their", "also", "only", "then"})
_STRONG_WORDS = frozenset({"must", "shall", "required", "mandatory", "obliged"})
_WEAK_WORDS = frozenset({"should", "may", "can", "could", "might"})


def _stem(word: str) -> str:
    """"applies", "applying", "applied" → "apply"; "terminated" → "termi". A 5-letter
    prefix alone split "apply" from "applies" (PHASE 11: a negated cap slipped by)."""
    for suffix, repl in (("ies", "y"), ("ied", "y"), ("ing", ""), ("ed", ""),
                         ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)] + repl
            break
    return word[:5]


def _governed(tokens: list[str], i: int) -> tuple[str, set[str]] | None:
    """The content word a modal or negation at `i` governs — "must be terminated"
    governs "terminated" (stemmed to 5 letters, so "terminate" matches) — and the
    words just after it, which pick out WHICH use of that verb the claim reports."""
    for j in range(i + 1, min(len(tokens), i + 5)):
        t = tokens[j]
        if t not in _AUX and t not in _NEG_WORDS and len(t) > 2:
            return _stem(t), {x for x in tokens[j + 1:j + 4] if x not in _AUX}
    return None


def _aligned_shift(claim: str, evidence: str) -> str | None:
    """Polarity and obligation, scoped to the verb the claim and its evidence share
    (PHASE 11). `guardrails` already refuses a claim asserting what the evidence
    negates; this adds the two directions it does not see: the claim NEGATING what the
    evidence asserts ("payments are not due" against "payments are due within 21
    days"), and a permission or advice reported as an OBLIGATION ("may be terminated"
    reported as "must be terminated"). A verb the evidence never uses is left to
    entailment."""
    ct = _TOKEN.findall(claim.lower())
    sentences = [_TOKEN.findall(s.lower()) for s in guardrails._SENTENCES.split(evidence)]
    for i, t in enumerate(ct):
        governed = _governed(ct, i) if t in _NEG_WORDS | _STRONG_WORDS else None
        if governed is None:
            continue
        word, after = governed
        # Only the evidence's uses of the verb that the claim is reporting — the ones
        # sharing the words after it ("may be made AS EXPEDITIOUSLY" is not "shall be
        # made BY THE TRIBUNAL"; "carve-outs include …" is not "does not include a
        # separate multiplier"). A verb the evidence never uses that way is left to
        # entailment.
        uses = [(set(et[max(0, k - NEG_SCOPE):k]), set(et[max(0, k - 5):k]),
                 bool(set(et[k + 1:k + 4]) & after))
                for et in sentences for k, x in enumerate(et) if _stem(x) == word]
        spots = [(wide, near) for wide, near, aligned in uses if aligned]
        if t in _NEG_WORDS and spots and all(not wide & _NEG_WORDS for wide, _ in spots):
            return "the claim negates what its evidence asserts"
        # An obligation falls back to EVERY modal-governed use when none aligns — "may"
        # reported as "must" is the costlier error, and the modal filter below already
        # sets aside a noun ("Termination for cause").
        before = [near for _, near in spots] or [near for _, near, _ in uses]
        # Only the occurrences a modal governs: "Termination for cause" is a noun.
        moded = [b for b in before if b & (_WEAK_WORDS | _STRONG_WORDS)]
        if t in _STRONG_WORDS and moded and all(not b & _STRONG_WORDS for b in moded):
            return "an obligation the evidence only permits or advises"
    return None


def _grounding(claim: str, cited: tuple[int, ...], evidence: list[str]) -> float:
    """The share of the claim's content words found in its best cited premise."""
    words = guardrails._content_words(claim)
    shares = [len(words & guardrails._content_words(premises(claim, evidence[i - 1])[0]))
              / max(1, len(words)) for i in cited]
    return max(shares, default=0.0)


def _kind_error(claim: str, kinds: set[str]) -> str | None:
    """The claim names a kind of source its supporting sentences are not (roadmap §9)."""
    names_law = bool(_LAW_SOURCE.search(claim)) and not _READING.search(claim)
    if names_law and not kinds & {"LAW", "READING"}:
        return "a company position stated as the law"
    if names_law and "LAW" not in kinds:
        return "the company's reading of the law stated as the law"
    if kinds == {"HISTORY"} and re.search(
            r"\b(?:current|today|now|our policy|company position)\b", claim, re.I) \
            and not re.search(r"\b(?:historical|past|previous|earlier|exception|"
                              r"negotiated|not current)\b", claim, re.I):
        return "a historical exception stated as current policy"
    if _CONTRACT_SAYS.search(claim) and "CONTRACT" not in kinds:
        return "a company position stated as the contract"
    return None


@dataclass(frozen=True)
class Result:
    ok: bool
    text: str                          # the answer with the verifier's citations
    judgements: list[Judgement]
    failures: list[str]


def check_answer(text: str, evidence: list[str], kinds: list[str],
                 authorities: list[str], sentences: list[str],
                 context: list[bool] | None = None) -> Result:
    flags = context or [False] * len(sentences)
    _memo.clear()
    # Stage 1 for every claim in ONE batched call — per-claim calls of 1–3 pairs left
    # the CPU threads idle (11 calls an answer).
    frames = [frame(k, a) for k, a in zip(kinds, authorities, strict=True)]
    first = []
    for sent, ctx in zip(sentences, flags, strict=True):
        claim = _MARKER.sub("", sent).strip(" -")
        for m in {int(x) for x in _MARKER.findall(sent) if x.isdigit()}:
            if not ctx and 1 <= m <= len(evidence):
                first.append((f"{frames[m - 1]} {premises(claim, evidence[m - 1])[0]}",
                              content(claim)))
    if first and entailment(first) is None:
        return Result(False, text, [], ["verifier unavailable"])
    judgements = [judge(s, evidence, kinds, authorities, context=c)
                  for s, c in zip(sentences, flags, strict=True)]
    _memo.clear()
    failures = []
    out = text
    for j in judgements:
        if j.verdict in ("UNSUPPORTED", "CONTRADICTED"):
            failures.append(f"claim {j.verdict.lower()} by its evidence: "
                            f"{j.sentence[:80]!r}")
        elif j.kind_error:
            failures.append(f"{j.kind_error}: {j.sentence[:80]!r}")
        elif j.verdict == "SUPPORTED" and j.citations != j.cited:
            lines = "".join(f"[{m}]" for m in _MARKER.findall(j.sentence)
                            if not m.isdigit())
            body = _MARKER.sub("", j.sentence).rstrip()
            tail = "".join(f"[{n}]" for n in j.citations) + lines
            ending = body[-1] if body[-1:] in ".!?" else ""
            fixed = f"{body[:-1] if ending else body} {tail}{ending}".replace("  ", " ")
            out = out.replace(j.sentence, fixed, 1)
    return Result(not failures, out, judgements, failures)
