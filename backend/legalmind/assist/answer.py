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
    contracts,
    evidence,
    generation,
    guardrails,
    intent,
    positions,
    verify,
)
from legalmind.assist import query_plan as qp

_KIND_LABEL = {
    qp.COMPANY_POSITION: "COMPANY POSITION (current policy)",
    qp.CONTRACT: "CONTRACT (the document in scope)",
    qp.LAW: "LAW",
    qp.HISTORICAL_EXCEPTION: "HISTORICAL EXCEPTION (a past negotiated deal — NOT current "
                             "policy)",
}
_MARKER = re.compile(r"\[(\d{1,2}|A|M)\]")
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
_ABBREVIATION = re.compile(r"\b(?:Pvt|Ltd|Co|Inc|No|s|ss|e\.g|i\.e|viz|cf|vs|Sec|Cl|"
                           r"Art|Para)\.$", re.I)
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


def render(bundle: evidence.Bundle, question: str = "") -> Payload:
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
    policy_text = [s.context for s in shown if s.kind == qp.COMPANY_POSITION]
    figures = tuple(dict.fromkeys(
        [f for a in bundle.assertions for f in a.unstated]
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


_LIMIT = re.compile(r"\b(?:cannot|can ?n[o']t|unable to|does not|do not|did not)\s+"
                    r"(?:be\s+)?(?:confirm|verif|determin|establish|state|specify|say|"
                    r"address)\w*", re.I)


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
    "s. 74") — a company name split in two read as two uncited claims."""
    out: list[str] = []
    for piece in (p.strip() for p in guardrails._SENTENCES.split(body) if p.strip()):
        if out and _ABBREVIATION.search(out[-1]):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    return out


def check(text: str, payload: Payload, bundle: evidence.Bundle) -> list[str]:
    """The mechanical post-generation checks. [] means the answer may be shown."""
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
        if policy and not _NEGATION.search(claim) and any(
                f.split()[0] in guardrails._quantities(claim) for f in unstated):
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
        if intent.is_verdict_statement(claim) and not restating_frame and (
                qp.CONTRACT in cited_kinds or "A" in marks or _SUBJECT.search(claim)):
            failures.append(f"compliance verdict: {sentence[:80]!r}")
    return failures


def verify_answer(text: str, payload: Payload, bundle: evidence.Bundle,
                  cs: list[contracts.Contract] | None = None) -> tuple[list[str], str]:
    """Both layers, fail closed: PHASE 10's mechanical checks, then PHASE 11's claim
    verifier (`assist/verify.py`), which also assigns the citations. Returns (failures,
    the answer with the verifier's citations)."""
    failures = check(text, payload, bundle)
    if failures:
        return failures, text
    sentences = _sentences(text)
    flags = [is_context(s, payload.question_figures) for s in sentences]
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
    all_cited = []
    for sentence in _sentences(result.text):
        cited = [by_n[int(m)] for m in _MARKER.findall(sentence)
                 if m.isdigit() and int(m) in by_n]
        all_cited.append(cited)
        if cited and not is_context(sentence, payload.question_figures):
            contract_failures += contracts.check(sentence, cited)
    return contract_failures, result.text


#: PHASE 11: one corrective generation when verification fails, then fail closed.
REPAIR = True
#: PHASE 12 (`AM-91` r6): a sentence that fails a check and cites approved contracts is
#: replaced by those contracts' own verbalisation before any regeneration.
SENTENCE_REPAIR = True


def verbalise(c: contracts.Contract) -> str:
    """An approved contract as a sentence: its kind, frame, scope and the source's own
    words, cited. It passes every check by construction."""
    lead = contracts.SAY[c.kind]
    if c.frame:
        lead += f" ({c.frame})"
    scope = [x.replace(contracts._SCOPE_TAG, "") for x in c.conditions
             if contracts._SCOPE_TAG in x]
    if c.scope:
        scope.insert(0, f"for {c.scope.replace('_', ' ')} agreements")
    if scope:
        lead += ", " + ", ".join(scope) + ","
    body = re.sub(r"(?<=[.!?])\s+", "; ", c.text.strip().rstrip("."))
    return f"{lead} states: {body} [{c.n}]."


def repair_sentences(text: str, payload: Payload, bundle: evidence.Bundle,
                     cs: list[contracts.Contract]) -> str | None:
    """Every sentence that fails, replaced by the verbalisation of the contracts it
    cites — or None when a failing sentence cites no contract (nothing approved to put
    in its place). No unverified sentence survives: what is shown is either verified or
    the approved source text itself."""
    by_n = {c.n: c for c in cs}
    out = []
    for sentence in _sentences(text):
        failures, _ = verify_answer(sentence, payload, bundle, cs)
        if not failures:
            out.append(sentence)
            continue
        cited = [by_n[int(m)] for m in dict.fromkeys(_MARKER.findall(sentence))
                 if m.isdigit() and int(m) in by_n]
        if not cited:
            return None
        out += [verbalise(c) for c in cited if verbalise(c) not in out]
    return " ".join(out)
#: PHASE 12 (`AM-91`): Gemini verbalises claim contracts instead of raw evidence.
CONTRACTS = True
#: Share of a sentence's content words drawn from its cited contracts above which it
#: is a restatement, decided by the deterministic contract checks.
VERBATIM = 0.8


def contract_payload(bundle: evidence.Bundle, question: str
                     ) -> tuple[Payload, list[contracts.Contract]]:
    """The payload with the approved claim contracts as its numbered evidence — each
    [n] is one contract's exact span — and the parts renumbered to them."""
    base = render(bundle, question)
    cs = contracts.build(bundle, question)
    if not cs:
        return base, []
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
                   tuple(bool(c.frame and contracts._frame(c.frame)) for c in cs)), cs


def contract_fallback(bundle: evidence.Bundle, cs: list[contracts.Contract]) -> str:
    """The fixed grounded answer from the contracts: each claim with its kind and
    citation, kinds kept apart, then what is asserted and what is missing."""
    if not cs:
        return fallback(bundle)
    out = [f"{contracts.SAY[c.kind]} — {c.citation}: {c.text}" for c in cs]
    tail = fallback(bundle).split("\n")
    return "\n".join(out + [t for t in tail if t.startswith(("No company position",
                                                           "The signed agreement"))])


def respond(bundle: evidence.Bundle, question: str, *, environment: str,
            prior_questions: tuple[str, ...] = (), request_id: str | None = None,
            generate=None, repair=None) -> Answer:
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
        payload, cs = contract_payload(bundle, question)
    else:
        payload = render(bundle, question)
    fixed = contract_fallback(bundle, cs) if cs else fallback(bundle)
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
    try:
        result = call(question, payload.block, environment=environment,
                      prior_questions=prior_questions, request_id=request_id)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        return Answer(fixed, False, [f"generation: {exc}"], payload.refs,
                      payload.kinds)
    t0 = time.perf_counter()
    failures, shown = verify_answer(result.text, payload, bundle, cs)
    verify_ms = (time.perf_counter() - t0) * 1000
    calls, first, latency = 1, None, result.latency_ms
    tokens = [result.prompt_tokens or 0, result.output_tokens or 0]
    if failures and cs and SENTENCE_REPAIR:
        t0 = time.perf_counter()
        repaired = repair_sentences(result.text, payload, bundle, cs)
        if repaired is not None:
            failures, shown = verify_answer(repaired, payload, bundle, cs)
        verify_ms += (time.perf_counter() - t0) * 1000
    if failures and REPAIR:
        try:
            second = fix(question, payload.block, result.text, failures,
                         environment=environment, prior_questions=prior_questions,
                         request_id=request_id)
        except (generation.GenerationRefused, generation.GenerationUnavailable):
            second = None
        if second is not None:
            calls, first = 2, result.text
            latency = (latency or 0) + (second.latency_ms or 0)
            tokens = [tokens[0] + (second.prompt_tokens or 0),
                      tokens[1] + (second.output_tokens or 0)]
            t0 = time.perf_counter()
            failures, shown = verify_answer(second.text, payload, bundle, cs)
            verify_ms += (time.perf_counter() - t0) * 1000
            result = second
    return Answer(shown if not failures else fixed, not failures,
                  failures, payload.refs, payload.kinds, result.model, latency,
                  tokens[0], tokens[1], result.text, calls, int(verify_ms), first,
                  prepare_ms)
