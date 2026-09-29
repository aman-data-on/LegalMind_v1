"""Conversational answers over the evidence bundle — roadmap §10, PHASE 10 (`AM-89`).

    result = answer.respond(bundle, question, environment=..., prior_questions=...)

Gemini is the language layer over the PHASE 9 bundle, never the authority layer:

  * It is called only when the bundle is answerable (`evidence.Bundle.answerable`),
    and it sees only `bundle.shown()` — sufficiency, authority, version and
    applicability were decided before it, in code (`AM-88`), and nothing here reopens
    them. An unanswerable bundle gets the deterministic answer below, with no call.
  * Every excerpt is labelled with its KIND (company position · contract · law · the
    company's reading of the law · historical exception) and its citation, so the model
    is told what each source IS rather than left to infer it.
  * The reader's assertions travel as one line marked [A] — "not evidence" — carrying
    the figures no company position states; the missing paper as one line marked [M].
    Neither is an excerpt, and a figure attributed to [A] is attributed, not asserted.
  * Each part of the question travels with its state, so the model answers each part
    as its evidence allows instead of one global yes/no.

After generation, mechanical checks (`check`) — outside the model (`AM-28` r2):
every sentence carries a valid marker; every figure a sentence states is in the text it
cites; no sentence gives a figure no company position states as the company's position;
no compliance verdict. A failure falls back to the deterministic answer — the answer is
never partially shown (`AM-25` r5). Semantic claim verification is PHASE 11's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from legalmind.assist import (
    claim_records,
    contracts,
    evidence,
    generation,
    guardrails,
    intent,
    positions,
    verify,
)
from legalmind.assist import presentation as presentation_mod
from legalmind.assist import query_plan as qp

_KIND_LABEL = {
    qp.COMPANY_POSITION: "COMPANY POSITION (current policy)",
    qp.CONTRACT: "CONTRACT (the document in scope)",
    qp.LAW: "LAW",
    qp.HISTORICAL_EXCEPTION: "HISTORICAL EXCEPTION (a past negotiated deal — NOT current "
                             "policy)",
}
_MARKER = re.compile(r"\[(\d{1,2}|A|M)\]")
_COMBINED_MARKER = re.compile(r"\[((?:\d{1,2}|A|M)(?:\s*,\s*(?:\d{1,2}|A|M))+)\]")
_SUBJECT = re.compile(
    r"\b(?:this|that|these|the|their|your|his|her|client'?s|customer'?s|counterparty'?s|"
    r"signed|executed|proposed|uploaded|attached)\s+(?:\w+\s+)?(?:agreement|contract|"
    r"clause|msa|nda|sla|document|draft|claim|proposal|term sheet|order form)s?\b", re.I)
# A next step that closes a gap ("locate the signed MSA to confirm …") — procedural,
# carrying no legal fact, so [M] may support it (roadmap §10's "what to do").
_NEXT_STEP = re.compile(r"\b(?:locat|verif|confirm|check|review|obtain|consult|refer|"
                        r"escalat|ask|determin|establish|evaluat|assess)\w*", re.I)
# The sentence reports what someone SAID — a reader's figure may appear only so.
_ATTRIBUTED = re.compile(r"\b(?:says?|said|told|claims?|claimed|mentions?|mentioned|"
                         r"asks?|asked|asserts?|asserted|according to|promised|alleged|"
                         r"you|your|client'?s|customer'?s|counterparty'?s|reader'?s|"
                         r"their account)\b", re.I)
# "The important distinction is between X and Y." — a signpost that makes no claim; it
# may stand uncited only while it carries no figure.
_SIGNPOST = re.compile(r"^(?:the )?(?:important |key |main |critical )?distinction "
                       r"(?:is|lies|depends on)\b[^\d]*$", re.I)
_HISTORY_FRAMED = re.compile(r"\b(?:historical|past|previous|earlier|exception|"
                             r"negotiated|old)\b", re.I)
# A historical exception called policy: the §16 safety metric, "current policy
# confused with historical exception = 0".
_POLICY_WORDS = re.compile(r"\b(?:policy|position|current|standard|today|now)\b", re.I)
# "does not set out a 6-month lock-in", "rather than 6 or 12 months": the sentence says
# the figure is ABSENT — which the code has already established (`reader_figures`).
# A comparative ("not more than 6 months") asserts a bound and is never this.
_ABSENT = re.compile(r"\b(?:does ?n[o']t|do ?n[o']t|not|no|never)\b[^.]{0,40}?\b(?:set|"
                     r"state|mention|specify|specifies|provide|include|contain|refer|fix|"
                     r"require|support|establish|say|give|impose|mandate|prescribe)|"
                     r"\bnot (?:stated|mentioned|specified|set out|found)\b|"
                     r"\b(?:rather than|instead of|missing|absent)\b|"
                     r"\bany (?:reference|mention)\b|\bwhether\b|"
                     r"\b(?:cannot|can ?n[o']t|unable to)"
                     r" (?:be )?confirm", re.I)
_COMPARATIVE = re.compile(r"\b(?:more|less|fewer|greater|longer|shorter) than\b|"
                          r"\b(?:up to|at (?:most|least)|exceed\w*|within|maximum|"
                          r"minimum)\b", re.I)
# "Rs." too: "not exceeding Rs. 1,000" split into an uncited "… Rs." and a "1,000 …"
# naming no source, and one uncited sentence sinks the whole answer (s. 74, `AM-107`).
_ABBREVIATION = re.compile(r"\b(?:Pvt|Ltd|Co|Inc|No|s|ss|e\.g|i\.e|viz|cf|vs|Sec|Cl|"
                           r"Art|Para|Rs)\.$", re.I)
_INITIALISM = re.compile(r"(?:\b[A-Z]\.){2,}$")
_NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|does ?n[o']t|cannot|isn't|"
                       r"without|missing|absent|nothing|none|unknown|unconfirmed|"
                       r"unverified|lacks?|rather than|instead of)\b", re.I)


def citation(source: evidence.Source) -> str:
    """How a reader finds the source — never an internal id (`AM-30` t4)."""
    ref = source.ref
    if ref.startswith("CONST:"):
        return f"Legal Constitution L1.10 §{ref[6:]}"
    if ref.startswith("POS:"):
        return f"Company Standard {ref[4:]}"
    if ref.startswith("STAT:"):
        act, _, section = ref[5:].rpartition(":")
        return f"{act}, s. {section}" if section[:1].isdigit() else f"{act}, {section}"
    return "the document in scope"


def label(source: evidence.Source) -> str:
    if source.candidate.authority == "SECONDARY_REFERENCE":
        return "LAW — the company's reading of the law, not the law itself"
    return _KIND_LABEL[source.kind]


@dataclass(frozen=True)
class Payload:
    """What may egress: the question, the labelled evidence, the assertion and missing
    lines, the part states — nothing else (`AM-30` t2 as amended by `AM-89` r2)."""
    evidence: list[str]           # the numbered excerpt texts, [1]..[n]
    kinds: list[str]
    refs: list[str]
    assertion_line: str | None    # [A]
    missing_line: str | None      # [M]
    block: str                    # the rendered prompt body
    #: Figures the reader gave that no company position states (`AM-78`, in code).
    reader_figures: tuple[str, ...] = ()
    #: Every figure the question and the reader's assertions give — the only figures a
    #: sentence may name as ABSENT from the text it cites.
    question_figures: tuple[str, ...] = ()
    #: Each excerpt's authority label (SECONDARY_REFERENCE = the company's reading of
    #: the law) — what the PHASE 11 verifier tells the law from the company's reading by.
    authorities: tuple[str, ...] = ()
    #: PHASE 12: excerpts whose meaning is a heading's ("Acceptable position") — a
    #: sentence restating one says "acceptable" of the position, not of a document.
    framed: tuple[bool, ...] = ()
    #: `AM-107`: each excerpt's place in the answer — PRIMARY · RELATED · HISTORY · LAW.
    layers: tuple[str, ...] = ()


def render(bundle: evidence.Bundle, question: str = "",
           policy: list[str] | None = None) -> Payload:
    shown = bundle.shown()
    # One excerpt per distinct context: several paragraphs of one section share it.
    texts: list[str] = []
    kinds: list[str] = []
    refs: list[str] = []
    auths: list[str] = []
    lines: list[str] = []
    number: dict[str, int] = {}
    for s in shown:
        if s.context in texts:
            number[s.ref] = texts.index(s.context) + 1
            continue
        texts.append(s.context)
        kinds.append(s.kind)
        refs.append(s.ref)
        auths.append(s.candidate.authority)
        number[s.ref] = len(texts)
        lines.append(f"[{len(texts)}] {label(s)} — {citation(s)}\n{s.context}")
    # [A]: the reader's assertions AND the figures their question gives, each with the
    # code's finding of whether a company position states it — so "no 6-month lock-in
    # is stated" is reported, never computed by the model (`AM-78`). A figure the reader
    # gave travels only on this line.
    # `policy`: what the company positions state, claim by claim (`AM-92`) — a source
    # holding a standard position AND historical deals (§31.15) is neither all position
    # nor all history. Without it, a source's own label decides, as before.
    policy_text = policy if policy is not None else [
        s.context for s in shown if s.kind == qp.COMPANY_POSITION]
    figures = tuple(dict.fromkeys(
        [f for a in bundle.assertions for f in a.unstated
         if guardrails.unstated_figures(f, policy_text)]
        + guardrails.unstated_figures(question, policy_text)))
    # Always present (bundle-answer-4): the model cited [A] where none was listed.
    said = [f'The reader asked: "{question}"'] if question else []
    said += [f'Someone asserted: "{a.text}"' for a in bundle.assertions]
    if figures:
        said.append(f"No company position states {', '.join(figures)}.")
    assertion = ("[A] WHAT THE READER SAID OR ASKED — context, NOT evidence, never a "
                 "fact: " + " ".join(said))
    gaps = [p.question for p in bundle.parts
            if p.state in (evidence.INSUFFICIENT, evidence.UNAVAILABLE)]
    missing_parts = []
    if bundle.missing_document:
        missing_parts.append("the signed/controlling agreement is not available here, so "
                             "its actual terms are unknown")
    if gaps:
        missing_parts.append("the available sources do not answer: " + " / ".join(gaps))
    # Always present (bundle-answer-3): the sources never hold more than the excerpts
    # above, and without a line to cite, the model cited a non-existent [M] 21 times to
    # say exactly that. A sentence citing only [M] must state a limitation (`check`).
    missing_parts.append("nothing beyond the excerpts above is available here — no "
                         "other agreement, record or source")
    missing = f"[M] MISSING: {'; '.join(missing_parts)}."
    parts = []
    for i, p in enumerate(bundle.parts, 1):
        cited = sorted({number[s.ref] for s in p.sources
                        if s.supports and s.ref in number})
        by = "".join(f"[{n}]" for n in cited)
        parts.append(f"{i}. {p.question} — {p.state.replace('_', ' ')}"
                     + (f", evidence {by}" if by else ""))
    block = "\n\n".join(lines)
    extra = "\n".join(x for x in (assertion, missing) if x)
    return Payload(texts, kinds, refs, assertion, missing,
                   f"EVIDENCE:\n{block}\n\n{extra}\n\nPARTS OF THE QUESTION:\n"
                   + "\n".join(parts), figures,
                   tuple(guardrails.unstated_figures(
                       " ".join([question, *(a.text for a in bundle.assertions)]), [])),
                   tuple(auths))


@dataclass(frozen=True)
class Answer:
    text: str
    generated: bool
    #: Why a generated answer was not shown — [] when it was, or when none was made.
    failures: list[str]
    refs: list[str]
    kinds: list[str]
    model: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    #: The model's own text, kept whether or not it was shown — so a rejected answer
    #: can be re-checked offline (the Gemini cost guard) rather than regenerated.
    draft: str | None = None
    #: PHASE 11: generation calls made (1, or 2 after one corrective retry), the
    #: verifier's time, and the first draft when a retry replaced it.
    calls: int = 0
    verify_ms: int = 0
    first_draft: str | None = None
    #: PHASE 12: time to build the claim contracts and the conflict map.
    prepare_ms: int = 0
    #: The provider's finishReason for the last generation ("MAX_TOKENS" when cut).
    finish_reason: str | None = None
    #: `AM-107`: the layer of each claim [n] — how the shown answer is grouped.
    layers: tuple[str, ...] = ()


def fallback(bundle: evidence.Bundle) -> str:
    """The deterministic answer: what each supporting source says, by kind, and what is
    missing. Used when nothing is answerable, when generation cannot run, and when a
    generated answer fails a check."""
    if not bundle.answerable:
        out = ["The approved sources available to you do not answer this."]
    else:
        out = [f"{label(s)} — {citation(s)}: {s.candidate.text}" for s in bundle.shown()]
    for a in bundle.assertions:
        if a.unstated:
            out.append(f"No company position states {', '.join(a.unstated)}; that figure "
                       "is the reader's account, not a verified term.")
    if bundle.missing_document:
        out.append("The signed agreement is not available here, so its actual terms "
                   "cannot be confirmed.")
    return "\n".join(out)


def _figure_key(figure: str) -> tuple[str, str]:
    """"6 months" and "6-month" are one figure."""
    number, _, unit = figure.partition(" ")
    return guardrails._NUMBER_WORDS.get(number, number), guardrails._norm(unit)


def _bounded(claim: str, figure: str) -> bool:
    """A comparative in the few words before the figure ("not more than 6 months")."""
    at = claim.lower().find(figure.split()[0])
    return at >= 0 and bool(_COMPARATIVE.search(claim[max(0, at - 30):at]))


# A statement about the evidence set's LIMITS, never about what a source says.
_ABOUT_SOURCES = re.compile(r"\b(?:provided|available|supplied) (?:materials?|sources?|"
                            r"excerpts?|information|evidence)\b[^.]{0,40}\b(?:only|not|no|"
                            r"do ?n[o']t|does ?n[o']t)\b", re.I)


def _covered(claim: str, payload: Payload) -> bool:
    """The gap sentence's SUBJECT words (what it says is unconfirmed) are largely the
    words of one shown claim: that claim answers it."""
    m = _LIMIT.search(claim)
    subject = claim[:m.start()] if m else claim
    # The subject up to the verb ("… is not confirmed"): a copula before the negation
    # ends it, so "the available sources" after it never dilutes the words.
    subject = re.split(r"\b(?:is|are|was|were|remains?|has|have)\s*$", subject.strip())[0]
    need = guardrails._content_words(subject) - {"specific", "provided", "material",
                                                 "exact", "actual", "precise"}
    if len(need) < 3:
        return False
    return any(len(need & guardrails._content_words(e)) / len(need) >= 0.6
               for e in payload.evidence)


_LIMIT = re.compile(r"\b(?:cannot|can ?n[o']t|unable to|does not|do not|did not|is not|"
                    r"are not|was not|remains? un)\s*(?:be\s+)?(?:confirm|verif|determin|"
                    r"establish|state|specify|say|address)\w*", re.I)


def is_context(sentence: str, question_figures: tuple[str, ...]) -> bool:
    """A sentence the entailment model cannot judge and the mechanical checks own
    (PHASE 11, `AM-90`): a signpost, one citing only [A]/[M], or one naming a READER'S
    figure as absent ("the position does not state 6 months [1]") — no text entails
    what it does not say, and `check` has already proved the figure is not there."""
    marks = set(_MARKER.findall(sentence))
    claim = _MARKER.sub("", sentence)
    if not any(m.isdigit() for m in marks) or _SIGNPOST.match(claim.strip("- ")):
        return True
    if _ABOUT_SOURCES.search(claim):         # "the provided materials only cover …"
        return True
    # A stated GAP that also cites what it looked at: "The available sources cannot
    # confirm what indemnity customers owe [1][2][M]" — nothing to entail.
    if marks & {"M", "A"} and _LIMIT.search(claim):
        return True
    asked = {_figure_key(f) for f in question_figures}
    return bool(_ABSENT.search(claim)) and any(
        _figure_key(f) in asked for f in guardrails.unstated_figures(claim, []))


def _sentences(body: str) -> list[str]:
    """Sentences, rejoined where the split fell after an abbreviation ("Pvt. Ltd.",
    "s. 74") — a company name split in two read as two uncited claims — after a dotted
    initialism ("G.S.R. 843(E)" became "G.S.R; 843(E)" on screen, `AM-104`), or inside
    an open parenthesis (`AM-103` r2's rule for records)."""
    out: list[str] = []
    for piece in (p.strip() for p in guardrails._SENTENCES.split(body) if p.strip()):
        if out and (_ABBREVIATION.search(out[-1]) or _INITIALISM.search(out[-1])
                    or out[-1].count("(") > out[-1].count(")")):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return out


def check(text: str, payload: Payload, bundle: evidence.Bundle,
          restated: frozenset[str] = frozenset()) -> list[str]:
    """The mechanical post-generation checks. [] means the answer may be shown.
    `restated` — sentences that are the code's own restatement of a claim
    (`is_verbalisation`): approved source text, never a verdict."""
    failures: list[str] = []
    body = (text or "").strip()
    if not body or body.upper().startswith("NOT FOUND"):
        return ["the model declined"]
    unstated = set(payload.reader_figures)
    for sentence in _sentences(body):
        marks = _MARKER.findall(sentence)
        if not marks:
            if not _SIGNPOST.match(sentence.strip("- ")):
                failures.append(f"no citation: {sentence[:80]!r}")
            continue
        cited: list[str] = []
        cited_kinds: set[str] = set()
        for m in marks:
            if m == "A" and payload.assertion_line:
                cited.append(payload.assertion_line)
            elif m == "M" and payload.missing_line:
                cited.append(payload.missing_line)
            elif m.isdigit() and 1 <= int(m) <= len(payload.evidence):
                cited.append(payload.evidence[int(m) - 1])
                cited_kinds.add(payload.kinds[int(m) - 1])
            else:
                failures.append(f"citation [{m}] does not exist")
        policy = qp.COMPANY_POSITION in cited_kinds
        claim = _MARKER.sub("", sentence)
        # [M] supports only a statement of what is NOT known — never a fact.
        if set(marks) == {"M"} and not (_NEGATION.search(claim)
                                        or _NEXT_STEP.search(claim)):
            failures.append(f"a fact cited only to what is missing: {sentence[:80]!r}")
        # … and never of something the shown claims DO state (run 9, E-04: "the time
        # frame is not confirmed by the available sources [M]" beside s.29A(1)'s twelve
        # months). A subject the claims cover cannot be called unconfirmed.
        if set(marks) == {"M"} and _LIMIT.search(claim) and _covered(claim, payload):
            failures.append(f"calls unconfirmed what a shown claim states: "
                            f"{sentence[:80]!r}")
        # A figure is a number WITH its unit (`AM-78`'s own rule) — "§14" or "section
        # 73" is a reference, and flagging it failed every answer that cited a section.
        extra = guardrails.unstated_figures(claim, cited)
        if extra and (_ABSENT.search(claim) or _ATTRIBUTED.search(claim)):
            # A figure the READER gave may be named as absent from the text this
            # sentence cites — `extra` already proves it is absent there — but never
            # inside a comparative that would assert a bound ("not more than 6 months").
            asked = {_figure_key(u) for u in payload.question_figures}
            extra = [f for f in extra
                     if _figure_key(f) not in asked or _bounded(claim, f)]
        if extra:
            failures.append(f"figure {extra} not in the cited text: {sentence[:80]!r}")
        # A figure no company position states, said of the position without negation —
        # citing [A] beside it does not launder it ("our policy is 6 months [1][A]").
        # Number WITH unit (`AM-78`): "Section 12" does not state "12 months" (GT-03).
        if policy and not _NEGATION.search(claim) and any(
                not guardrails.unstated_figures(f, [claim]) for f in unstated):
            failures.append(f"a reader's figure stated as the position: "
                            f"{sentence[:80]!r}")
        # [A] alone never makes a reader's figure a fact: it is attributed or negated.
        if set(marks) <= {"A", "M"} and not (_ATTRIBUTED.search(claim)
                                             or _NEGATION.search(claim)) and any(
                _figure_key(f) in {_figure_key(q) for q in payload.question_figures}
                for f in guardrails.unstated_figures(claim, [])):
            failures.append(f"a reader's figure stated as fact: {sentence[:80]!r}")
        if cited_kinds == {qp.HISTORICAL_EXCEPTION} and _POLICY_WORDS.search(claim) \
                and not (_NEGATION.search(claim) or _HISTORY_FRAMED.search(claim)):
            failures.append(f"a historical exception stated as policy: "
                            f"{sentence[:80]!r}")
        # A verdict needs something to judge: a contract excerpt, the reader's claim, or
        # an agreement the sentence names. Describing what the position itself calls
        # unacceptable (Constitution §24.4) is the position, not a verdict (`AM-89` r4).
        restating_frame = bool(payload.framed) and qp.CONTRACT not in cited_kinds and \
            "A" not in marks and any(m.isdigit() and 1 <= int(m) <= len(payload.framed)
                                     and payload.framed[int(m) - 1] for m in marks)
        # Likewise a sentence that IS the cited record's words (a whole sub-section, a
        # §14 paragraph on ss.73/74): approved source text judges no document.
        words = guardrails._content_words(claim)
        # The kind's attribution ("Historically (a past negotiated deal, not current
        # policy)") is the answer naming its source, not a word of the claim (H-03).
        own = guardrails._content_words(" ".join([*cited, *contracts.SAY.values()]))
        restating_text = qp.CONTRACT not in cited_kinds and "A" not in marks and \
            bool(words) and len(words & own) / len(words) >= VERBATIM
        judged = qp.CONTRACT in cited_kinds or "A" in marks or _SUBJECT.search(claim)
        if intent.is_verdict_statement(claim) and judged and not (
                restating_frame or restating_text or sentence in restated):
            failures.append(f"compliance verdict: {sentence[:80]!r}")
    return failures


def verify_answer(text: str, payload: Payload, bundle: evidence.Bundle,
                  cs: list[contracts.Contract] | None = None) -> tuple[list[str], str]:
    """Both layers, fail closed: PHASE 10's mechanical checks, then PHASE 11's claim
    verifier (`assist/verify.py`), which also assigns the citations. Returns (failures,
    the answer with the verifier's citations)."""
    sentences = _sentences(text)
    by_n = {c.n: c for c in cs or []}
    restated = frozenset(s for s in sentences if (cited := [
        by_n[int(m)] for m in _MARKER.findall(s) if m.isdigit() and int(m) in by_n])
        and len(cited) == 1 and is_verbalisation(s, cited[0]))
    failures = check(text, payload, bundle, restated)
    if failures:
        return failures, text
    flags = [is_context(s, payload.question_figures) or s in restated for s in sentences]
    if cs:
        # PHASE 12: a sentence that restates its cited contract nearly verbatim is
        # decided by the deterministic contract checks below (conditions, modality,
        # negation, scope, frame, kind); the entailment model is for paraphrase. It
        # called a verbatim restatement of Section 74 "contradicted" six times.
        by_n = {c.n: c for c in cs}
        for i, sent in enumerate(sentences):
            cited = [by_n[int(m)] for m in _MARKER.findall(sent)
                     if m.isdigit() and int(m) in by_n]
            words = guardrails._content_words(_MARKER.sub("", sent))
            own = set().union(set(), *(guardrails._content_words(c.text) for c in cited))
            if cited and words and len(words & own) / len(words) >= VERBATIM:
                flags[i] = True
    result = verify.check_answer(
        text, payload.evidence, payload.kinds,
        list(payload.authorities or [""] * len(payload.evidence)), sentences, flags)
    if result.failures or not cs:
        return result.failures, result.text
    # PHASE 12: each sentence held to the contracts it (now correctly) cites.
    by_n = {c.n: c for c in cs}
    contract_failures = []
    preceding: list[str] = []
    for paragraph in re.split(r"\n\s*\n", result.text):
        carried: frozenset[tuple] = frozenset()   # never across a paragraph break
        for sentence in _sentences(paragraph):
            cited = [by_n[int(m)] for m in _MARKER.findall(sentence)
                     if m.isdigit() and int(m) in by_n]
            if not cited:
                preceding.append(sentence)
                carried = frozenset()
                continue
            found = contracts.check(sentence, cited, " ".join(preceding), carried)
            preceding.append(sentence)
            # Only an attributed sentence hands its attribution on.
            attributed = not any(f.startswith(("source kind not named",
                                               "drops the frame", "drops the scope"))
                                 for f in found)
            carried = (frozenset(contracts.attribution(c) for c in cited)
                       if attributed else frozenset())
            contract_failures += _context_filtered(sentence, found, payload)
    return contract_failures, result.text


def _context_filtered(sentence: str, found: list[str], payload: Payload) -> list[str]:
    # A context sentence ("the position does not state 6 months [1]") is not a
    # restatement, so grounding, conditions and modality do not apply to it — but
    # which SOURCE it speaks for always does (roadmap §13: never blended).
    if is_context(sentence, payload.question_figures):
        return [f for f in found if f.startswith(contracts.KIND_FAILURES)]
    return found


# ---- shaped answers (`AM-108`) ---------------------------------------------------
_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")
_BULLET = re.compile(r"^\s*[-•*]\s+")
#: A short answer's ceiling before one corrective regeneration is asked for.
SHORT_WORDS = 90


def split_table(text: str) -> tuple[str, str]:
    """(the prose, the pipe table) of an answer — the table's lines in order, the
    rest joined; "" when there is no table."""
    lines = (text or "").split("\n")
    table = [x.strip() for x in lines if _TABLE_ROW.match(x)]
    prose = [x.strip() for x in lines if not _TABLE_ROW.match(x) and x.strip()]
    return "\n".join(prose), "\n".join(table)


def _cells(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


def table_sentences(table: str) -> list[str]:
    """Each data row as ONE sentence for verification — "<item> — <header>: <cell>;
    …" carrying the row's markers — so a table is held to the same checks as prose:
    the header names the source kind, every cell is checked against the claims the
    row cites. Rows without markers are sentences with no citation, and fail."""
    rows = [r for r in table.split("\n") if r.strip() and not _TABLE_RULE.match(r)]
    if len(rows) < 2:
        return []
    header = _cells(rows[0])
    out = []
    for row in rows[1:]:
        cells = _cells(row)
        marks = "".join(f"[{m}]" for m in dict.fromkeys(_MARKER.findall(row)))
        body = "; ".join(f"{header[j] if j < len(header) else ''}: "
                         f"{_unstop(_MARKER.sub('', c).strip()).strip()}"
                         for j, c in enumerate(cells[1:], 1) if c.strip())
        label = _MARKER.sub("", cells[0]).strip() if cells else ""
        out.append(f"{label} — {body} {marks}.".replace(" .", "."))
    return out


def rebuild_table(table: str, verified: list[str]) -> str:
    """The table with each row's markers replaced by its verified sentence's — the
    verifier assigns citations, and the table must show the ones it assigned."""
    rows = [r for r in table.split("\n") if r.strip()]
    out: list[str] = []
    i = 0
    for row in rows:
        if _TABLE_RULE.match(row) or (i == 0 and not out):
            out.append(row)            # the header, and any rule line
            if not _TABLE_RULE.match(row):
                i = 0
            continue
        cells = [" ".join(_MARKER.sub("", c).split()) for c in _cells(row)]
        marks = "".join(f"[{m}]" for m in dict.fromkeys(
            _MARKER.findall(verified[i]))) if i < len(verified) else ""
        if cells and marks:
            cells[-1] = f"{_unstop(cells[-1]).rstrip()} {marks}".strip()
        out.append("| " + " | ".join(cells) + " |")
        i += 1
    return "\n".join(out)


def trim_bullets(text: str, count: int | None) -> str:
    """At most `count` bullet lines — the reader asked for five, the model wrote six.
    Every bullet was verified on its own, so dropping the extra loses nothing that was
    promised; fewer than asked are kept as they are, since the evidence sets the
    number, not the request."""
    if not count:
        return text
    out, seen = [], 0
    for line in (text or "").split("\n"):
        if _BULLET.match(line):
            seen += 1
            if seen > count:
                continue
        out.append(line)
    return "\n".join(out)


def _with_table(text: str, verify, repair_cell=None) -> tuple[list[str], str]:
    """Verify an answer that holds a table: each row as a sentence. A row that fails
    and cites exactly one claim is repaired to that claim's own words (`repair_cell`,
    `AM-91` r6's rule for a sentence); a row that still fails is left out. The table
    stands when at least one row is verified, rebuilt with the verifier's markers; a
    lead-in around it stands only if it verifies on its own. Nothing unverified is
    ever shown; a table with no verified row fails closed."""
    prose, table = split_table(text)
    if not table:
        return verify(text)
    rows = [r for r in table.split("\n") if r.strip() and not _TABLE_RULE.match(r)]
    header, data = rows[0], rows[1:]
    if not data:
        return ["a table with no rows"], text
    kept: list[str] = []
    verified: list[str] = []
    for row in data:
        sentence = table_sentences("\n".join([header, row]))[0]
        failures, shown = verify(sentence)
        if failures and repair_cell is not None:
            cited = [m for m in dict.fromkeys(_MARKER.findall(row)) if m.isdigit()]
            if len(cited) == 1 and (own := repair_cell(int(cited[0]))):
                cells = _cells(row)
                cells[-1] = f"{_unstop(own)} [{cited[0]}]."
                row = "| " + " | ".join(cells) + " |"
                sentence = table_sentences("\n".join([header, row]))[0]
                failures, shown = verify(sentence)
        if failures:
            continue
        kept.append(row)
        verified.append(_sentences(shown)[-1] if _sentences(shown) else sentence)
    if not kept:
        return ["no table row verified"], text
    rebuilt = rebuild_table("\n".join([header, *kept]), verified)
    if not prose:
        return [], rebuilt
    # The words around the table stand only if they verify on their own: a lead-in
    # that cites every row ("The contract sets out six termination clauses [1]…[6]")
    # restates none of them and fails; the verified table answers without it.
    lead_failures, lead = verify(prose)
    return [], (f"{lead}\n\n{rebuilt}" if not lead_failures else rebuilt)


#: PHASE 11: one corrective generation when verification fails, then fail closed.
REPAIR = True
#: PHASE 12 (`AM-91` r6): a sentence that fails a check and cites approved contracts is
#: replaced by those contracts' own verbalisation before any regeneration.
SENTENCE_REPAIR = True


#: A restatement continuing the previous one's attribution (`AM-109`).
CONTINUED = "It also states: "


def verbalise(c: contracts.Contract, hint: str | None = None,
              continued: bool = False) -> str:
    """An approved contract as a sentence: its kind, frame, scope and the source's own
    words, cited. It passes every check by construction.

    `hint` — the failing sentence this replaces (PHASE 13, `AM-94`): the body is then
    the SMALLEST run of the record's own sentences that covers the hint and still
    passes every contract check — conditions, frame, scope, modality, kind — growing a
    sentence at a time, the whole record when nothing smaller passes. Measured live
    2026-09-27: whole-record repairs were 60–95% of the words a reader saw (an 831-word
    statute Schedule for one failing sentence); a paraphrase is never made."""
    if hint:
        pieces = _record_sentences(c.text)
        if len(pieces) > 1:
            # Grow by what the hint says first, then by what the checks will ask for
            # — the record's own conditions and exceptions — so a condition that lives
            # in another sentence is reached before an unrelated one.
            words = guardrails._content_words(hint)
            asked = set().union(set(), *(guardrails._content_words(x)
                                        for x in (*c.conditions, *c.exceptions)))
            ranked = sorted(range(len(pieces)), key=lambda i: (
                -len(words & guardrails._content_words(pieces[i])),
                -len(asked & guardrails._content_words(pieces[i])), i))
            chosen: set[int] = set()
            for i in ranked:
                chosen.add(i)
                said = _verbalise(c, " ".join(pieces[j] for j in sorted(chosen)))
                if not contracts.check(said, [c]):
                    return _continue(said, c) if continued else said
    said = _verbalise(c, c.text)
    return _continue(said, c) if continued else said


def _continue(said: str, c: contracts.Contract) -> str:
    """The same restatement with its attribution carried from the sentence before."""
    return CONTINUED + said[len(f"{_lead(c)} states: "):]


def _record_sentences(text: str) -> list[str]:
    """A record's own sentences; a statute's semicolon-separated items count as
    sentences too, so one item can answer for a whole Schedule. Never split inside
    parentheses or after an ellipsis, and never a piece with no words: §13's "(CERT-In
    logs 180 days; KYC … 5 years)" was cut in half, and a quote's "..." became a
    sentence of its own that passed every check with nothing in it (2026-09-27)."""
    text = text.strip()
    out, start = [], 0
    for m in re.finditer(r"(?<=[.!?;])\s+(?=[A-Z(\[\u2018\u201c\"'])", text):
        before = text[:m.start()]
        if before.count("(") > before.count(")") or before.endswith(".."):
            continue
        out.append(text[start:m.start()])
        start = m.end()
    out.append(text[start:])
    return [x.strip() for x in out if re.search(r"\w", x)]


def _lead(c: contracts.Contract) -> str:
    """The claim's attribution — kind, frame, scope, referent — every part approved."""
    lead = contracts.SAY[c.kind]
    if c.frame:
        lead += f" ({c.frame})"
    scope = [x.replace(contracts._SCOPE_TAG, "") for x in c.conditions
             if contracts._SCOPE_TAG in x]
    if c.scope:
        scope.insert(0, f"for {c.scope.replace('_', ' ')} agreements")
    if scope:
        lead += ", " + ", ".join(scope) + ","
    if c.referent:
        lead += f" (on {c.referent})"
    return lead


def _tail(c: contracts.Contract) -> str:
    tail = ""
    if c.exceptions_text:
        tail += "; subject to these exceptions: " + "; ".join(
            x.rstrip(".") for x in _sentences(c.exceptions_text))
    if c.temporal:
        t = c.temporal.rstrip(".")
        tail += (" (repealed — historical, not current law)" if t == "REPEALED"
                 else f" ({t})" if re.search(r"not yet in force|commenc", t, re.I)
                 else f" (in force: {t})")
    if c.antecedents:
        tail += " (" + "; ".join(f"{said} being {meant}"
                                 for said, meant in c.antecedents) + ")"
    return tail


def is_verbalisation(sentence: str, c: contracts.Contract) -> bool:
    """The sentence is exactly the code's restatement of `c` (`verbalise`): its own
    attribution, then a run of the record's own sentences in order, then its own notes.
    Such a sentence is approved source text — the entailment model called 20 of 553 of
    them unsupported or contradicted, so a draft citing one could never be repaired
    (golden C-04, A-01, D-04 fell back, 2026-09-27). Anything else, however alike, is
    judged as a paraphrase."""
    end = f"{_tail(c)} [{c.n}]."
    lead = next((x for x in (f"{_lead(c)} states: ", CONTINUED)
                 if sentence.startswith(x)), None)
    if lead is None or not sentence.endswith(end):
        return False
    # Word for word — the repair rejoins the record's sentences with "; ", and a hinted
    # repair takes only some of them: the body must be whole record sentences, in the
    # record's order, and nothing else. A negation is a word, so none can differ.
    words = re.findall(r"\w+", sentence[len(lead):len(sentence) - len(end)])
    at = 0
    for piece in _record_sentences(c.text):
        own = re.findall(r"\w+", piece)
        if own and words[at:at + len(own)] == own:
            at += len(own)
    return bool(words) and at == len(words)


def _unstop(sentence: str) -> str:
    """The sentence without its full stop — never an ellipsis ("… solicit ...")."""
    return sentence[:-1] if sentence.endswith(".") and not sentence.endswith("..") \
        else sentence


def _verbalise(c: contracts.Contract, text: str) -> str:
    body = "; ".join(_unstop(x) for x in _sentences(text.strip()))
    # A quote that opens mid-passage ("... The cap applies mutually") reads as a
    # broken sentence once it follows "states:" (`AM-109`).
    body = re.sub(r"^\s*(?:\.{3}|…)\s*", "", body)
    return f"{_lead(c)} states: {body}{_tail(c)} [{c.n}]."


def repair_sentences(text: str, payload: Payload, bundle: evidence.Bundle,
                     cs: list[contracts.Contract]) -> str | None:
    """Every sentence that fails, replaced by the verbalisation of the contracts it
    cites — or None when a failing sentence cites no contract (nothing approved to put
    in its place). A failing sentence that cites only OPTIONAL context (`AM-107`: a
    related source, or history or law the question did not ask for) is left out instead
    — pasting that record's text beside the direct answer is what buried it. No
    unverified sentence survives: what is shown is either verified or the approved
    source text itself."""
    by_n = {c.n: c for c in cs}
    verdicts = [(sentence, verify_answer(sentence, payload, bundle, cs)[0])
                for sentence in _sentences(text)]
    # One excerpt per contract, however many failing sentences cite it — grown to
    # cover all of them together, so a claim is never restated three times.
    hints: dict[int, list[str]] = {}
    for sentence, failures in verdicts:
        if failures:
            for m in dict.fromkeys(_MARKER.findall(sentence)):
                if m.isdigit() and int(m) in by_n:
                    hints.setdefault(int(m), []).append(sentence)
    out: list[str] = []
    done: set[int] = set()
    voice: tuple | None = None       # the attribution the last restatement named
    for sentence, failures in verdicts:
        if not failures:
            out.append(sentence)
            # A verified sentence speaking for one voice hands it on, like a repair.
            spoken = {contracts.attribution(by_n[int(m)])
                      for m in _MARKER.findall(sentence)
                      if m.isdigit() and int(m) in by_n}
            voice = spoken.pop() if len(spoken) == 1 and not _BULLET.match(sentence) \
                else None
            continue
        cited = [int(m) for m in dict.fromkeys(_MARKER.findall(sentence))
                 if m.isdigit() and int(m) in by_n]
        if not cited:
            return None
        if all(by_n[n].optional for n in cited):
            continue          # optional context it could not say faithfully: left out
        dash = "- " if _BULLET.match(sentence) else ""
        for n in cited:
            if n not in done:
                done.add(n)
                same = not dash and voice == contracts.attribution(by_n[n])
                out.append(dash + verbalise(by_n[n], " ".join(hints[n]), continued=same))
                voice = contracts.attribution(by_n[n])
    return ("\n" if any(_BULLET.match(x) for x in out) else " ").join(out)
#: PHASE 12 (`AM-91`): Gemini verbalises claim contracts instead of raw evidence.
CONTRACTS = True
#: Share of a sentence's content words drawn from its cited contracts above which it
#: is a restatement, decided by the deterministic contract checks.
VERBATIM = 0.8


def contract_payload(bundle: evidence.Bundle, question: str, db=None
                     ) -> tuple[Payload, list[contracts.Contract]]:
    """The payload with the approved claim contracts as its numbered evidence — each
    [n] is one contract's exact span — and the parts renumbered to them."""
    cs = contracts.build(bundle, question, db)
    if not cs:
        return render(bundle, question), []
    base = render(bundle, question, _position_texts(bundle, db))
    by_ref: dict[str, list[int]] = {}
    for c in cs:
        by_ref.setdefault(c.ref, []).append(c.n)
    parts = []
    for i, p in enumerate(bundle.parts, 1):
        nums = sorted({n for s in p.sources if s.supports for n in by_ref.get(s.ref, [])})
        parts.append(f"{i}. {p.question} — {p.state.replace('_', ' ')}"
                     + (", claims " + "".join(f"[{n}]" for n in nums) if nums else ""))
    extra = "\n".join(x for x in (base.assertion_line, base.missing_line) if x)
    block = (contracts.render(cs, contracts.relations(cs)) + f"\n\n{extra}\n\n"
             "PARTS OF THE QUESTION:\n" + "\n".join(parts))
    return Payload([c.text for c in cs], [c.plan_kind for c in cs], [c.ref for c in cs],
                   base.assertion_line, base.missing_line, block, base.reader_figures,
                   base.question_figures, tuple(c.authority for c in cs),
                   tuple(bool(c.frame and contracts._frame(c.frame)) for c in cs),
                   tuple(c.layer for c in cs)), cs


def _position_texts(bundle: evidence.Bundle, db) -> list[str]:
    """What the company positions in the bundle state: every position claim of a
    source that has structured records, and the whole text of one that does not."""
    out: list[str] = []
    for s in bundle.shown():
        units = claim_records.units(db, s) if db is not None else None
        if units is not None:
            out += [u.text for u in units
                    if contracts._kind_of_record(u) == contracts.POSITION]
        elif s.kind == qp.COMPANY_POSITION:
            out.append(s.context)
    return out


def contract_fallback(bundle: evidence.Bundle, cs: list[contracts.Contract],
                      figures: tuple[str, ...] = ()) -> str:
    """The fixed grounded answer from the contracts: each claim with its kind and
    citation, kinds kept apart, then what is asserted and what is missing. `figures`
    are the reader's figures no position claim states — the payload's own finding."""
    if not cs:
        return fallback(bundle)
    return "\n".join([f"{contracts.SAY[c.kind]} — {c.citation}: {c.text}" for c in cs]
                     + _layer_lines(bundle, figures, marked=False))


def _layer_lines(bundle: evidence.Bundle, figures: tuple[str, ...], *,
                 marked: bool) -> list[str]:
    """Roadmap §13: what the reader claimed and what is missing, each said as itself —
    fixed wording, never the model's."""
    out = []
    # In the fixed answer, as before: only what someone ASSERTED. Beside a generated
    # answer: every figure the reader gave that no position claim states.
    claimed = list(figures) if marked else [
        f for f in figures if any(f in a.unstated for a in bundle.assertions)]
    if claimed:
        out.append(f"No company position states {', '.join(claimed)}; that figure is "
                   "the reader's account, not a verified term" + (" [A]." if marked
                                                                   else "."))
    if bundle.missing_document:
        out.append("The signed agreement is not available here, so its actual terms "
                   "cannot be confirmed" + (" [M]." if marked else "."))
    return out


#: The provider's finishReason when the output cap cut the text.
_CUT = "MAX_TOKENS"
_LAST_MARKED = re.compile(r"(?:\[(?:\d{1,2}|A|M)\])+[.!?]?")


def complete(text: str, finish_reason: str | None, payload: Payload,
             bundle: evidence.Bundle) -> str:
    """A generated answer made whole before it is checked (roadmap §13).

    Cut at the output cap, its unfinished last sentence is dropped — an unfinished
    sentence is not a claim, and every sentence before it is still checked. A reader's
    figure or a missing agreement the answer never mentions is then said in the fixed
    wording, so no answer shown can omit either layer.

    A combined marker is split first: "[2, A]" read as no citation at all and sank a
    correct answer (live, H-01, `AM-104`); each marker is still checked on its own."""
    text = _COMBINED_MARKER.sub(
        lambda m: "".join(f"[{x.strip()}]" for x in m.group(1).split(",")), text or "")
    # A "sentence" that is only markers ("… [3]. [M]") states nothing and cites nothing a
    # repair could restate; left in, it sank a verified s. 74 answer (`AM-107`).
    text = re.sub(r"(?<=[.!?\]])\s+(?:\[(?:\d{1,2}|A|M)\]\s*)+$", "", text.rstrip())
    if finish_reason == _CUT:
        ends = list(_LAST_MARKED.finditer(text))
        if ends:
            text = text[:ends[-1].end()]
    # Only beside a real answer — one that ends a sentence and states a cited claim. An
    # empty or unfinished text is left exactly as it is, so it still fails closed: an
    # appended line must never lend its marker to an unfinished, uncited fragment.
    if not re.search(r"\[\d{1,2}\]", text) or text.rstrip()[-1:] not in ".!?]":
        return text
    needed = []
    lines = _layer_lines(bundle, payload.reader_figures, marked=True)
    if payload.reader_figures and "[A]" not in text:
        needed += [x for x in lines if x.endswith("[A].")]
    if bundle.missing_document and "[M]" not in text:
        needed += [x for x in lines if x.endswith("[M].")]
    return " ".join([text.rstrip(), *needed]) if needed else text


def respond(bundle: evidence.Bundle, question: str, *, environment: str,
            prior_questions: tuple[str, ...] = (), request_id: str | None = None,
            generate=None, repair=None, db=None) -> Answer:
    """`generate` / `repair` are injectable (the offline evaluation passes stubs); the
    defaults are the single egress seam, `generation.generate_bundle_answer` and
    `generation.generate_bundle_repair`."""
    import functools
    import time

    if not bundle.answerable:
        return Answer(fallback(bundle), False, [], [], [])
    cs: list[contracts.Contract] = []
    t_prep = time.perf_counter()
    if CONTRACTS:
        payload, cs = contract_payload(bundle, question, db)
    else:
        payload = render(bundle, question)
    fixed = (contract_fallback(bundle, cs, payload.reader_figures) if cs
             else fallback(bundle))
    prepare_ms = int((time.perf_counter() - t_prep) * 1000)
    try:
        positions.screen_for_egress(payload.evidence)     # `AM-67` r7, now for all kinds
    except positions.PositionEgressRefused as exc:
        return Answer(fixed, False, [f"egress screen: {exc}"], payload.refs,
                      payload.kinds)
    call = generate or (generation.generate_contract_answer if cs
                        else generation.generate_bundle_answer)
    fix = repair or (functools.partial(generation.generate_bundle_repair,
                                       template=generation.CONTRACT_PROMPT_TEMPLATE)
                     if cs else generation.generate_bundle_repair)
    shape = bundle.presentation
    described = shape.describe()

    def checked(draft: str) -> tuple[list[str], str]:
        """Verified as prose, or row by row when the draft holds a table; then the
        shape the reader asked for is enforced in code — extra bullets cut, a short
        answer that ran long sent back once. Never the other way round: no shape ever
        admits a sentence verification refused."""
        by_n = {c.n: c for c in cs}
        failures, shown = _with_table(
            draft, lambda t: verify_answer(t, payload, bundle, cs),
            repair_cell=lambda n: by_n[n].text if n in by_n else None)
        if not failures:
            shown = trim_bullets(shown, shape.count)
        return failures, shown

    try:
        result = call(question, payload.block, environment=environment,
                      prior_questions=prior_questions, request_id=request_id,
                      presentation=described)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        return Answer(fixed, False, [f"generation: {exc}"], payload.refs,
                      payload.kinds)
    t0 = time.perf_counter()
    text = complete(result.text, result.finish_reason, payload, bundle)
    failures, shown = checked(text)
    verify_ms = (time.perf_counter() - t0) * 1000
    calls, first, latency = 1, None, result.latency_ms
    tokens = [result.prompt_tokens or 0, result.output_tokens or 0]
    if failures and cs and SENTENCE_REPAIR and not split_table(text)[1]:
        t0 = time.perf_counter()
        repaired = repair_sentences(text, payload, bundle, cs)
        if repaired is not None:
            failures, shown = checked(repaired)
        verify_ms += (time.perf_counter() - t0) * 1000
    # A verified answer that is longer than the reader asked for is sent back once;
    # if the second attempt fails verification, the first — verified — is shown.
    verified_first = shown if not failures else None
    if not failures and shape.length == presentation_mod.SHORT \
            and len(_MARKER.sub("", shown).split()) > SHORT_WORDS:
        failures = [f"longer than asked: {len(shown.split())} words for a short answer"]
    if failures and REPAIR:
        try:
            second = fix(question, payload.block, result.text, failures,
                         environment=environment, prior_questions=prior_questions,
                         request_id=request_id, presentation=described)
        except (generation.GenerationRefused, generation.GenerationUnavailable):
            second = None
        if second is not None:
            calls, first = 2, result.text
            latency = (latency or 0) + (second.latency_ms or 0)
            tokens = [tokens[0] + (second.prompt_tokens or 0),
                      tokens[1] + (second.output_tokens or 0)]
            t0 = time.perf_counter()
            failures, shown = checked(
                complete(second.text, second.finish_reason, payload, bundle))
            verify_ms += (time.perf_counter() - t0) * 1000
            result = second
            if failures and verified_first is not None:
                failures, shown = [], verified_first
        elif verified_first is not None:
            failures, shown = [], verified_first
    return Answer(shown if not failures else fixed, not failures,
                  failures, payload.refs, payload.kinds, result.model, latency,
                  tokens[0], tokens[1], result.text, calls, int(verify_ms), first,
                  prepare_ms, result.finish_reason, payload.layers)
