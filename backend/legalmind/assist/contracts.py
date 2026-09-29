"""Claim contracts and the evidence/conflict map — roadmap §13, PHASE 12 (`AM-91`).

    contracts = contracts.build(bundle, question)
    relations = contracts.relations(contracts)

PHASE 11 left one class of error it could not see: a generated sentence that drops a
legal condition, strengthens "may" to "must", loses a negation, or states the company's
reading of the law as the law. An entailment model accepts most of them. The fix is
upstream: before generation, every claim the answer may make is fixed as a CONTRACT —
read deterministically out of the evidence, one sentence at a time:

    subject · action · object      where the sentence's modal/verb divides it
    modality                       PROHIBITED · MANDATORY · ADVISORY · PERMITTED ·
                                   STATEMENT
    negated                        the sentence's own negation
    conditions · exceptions        "unless …", "where …", "subject to …", "except …"
    scope                          the document type the position is written for
    status                         CURRENT · HISTORICAL
    kind                           COMPANY_POSITION · LAW_READING · LAW ·
                                   HISTORICAL_EXCEPTION · CONTRACT — from the
                                   sentence's OWN label or heading, never from the
                                   excerpt as a whole (a Constitution section mixes
                                   policy, the company's reading of the law, historical
                                   evidence and illustrative drafting)
    text · citation                the exact supporting span and where it is

Gemini verbalises the contracts (`generation.generate_contract_answer`); it never reads
the raw evidence. `check` then holds each sentence to the contracts it cites, in code.
Illustrative drafting language ("not yet in any signed contract") and status lines are
never a contract. Relations keep sources apart: the same kind and scope saying different
things about the same action is a CONFLICT, shown as such and never averaged; different
kinds are separate LAYERS, never merged.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from legalmind.assist import evidence, guardrails, routing
from legalmind.assist import presentation as presentation_mod
from legalmind.assist import query_plan as qp
from legalmind.assist.verify import _HISTORY_LABEL, _READING_LABEL, _WRAP

POSITION, READING, LAW, HISTORY, CONTRACT = ("COMPANY_POSITION", "LAW_READING", "LAW",
                                             "HISTORICAL_EXCEPTION", "CONTRACT")
#: How each kind must be named in the answer — the attribution the reader sees.
SAY = {POSITION: "The company position", READING: "The company's reading of the law",
       LAW: "The law", HISTORY: "Historically (a past negotiated deal, not current "
       "policy)", CONTRACT: "The contract"}
#: The attribution each kind must carry in a sentence citing it (`check`).
ATTRIBUTION = {
    POSITION: re.compile(r"\b(?:company(?:'s)? (?:positions?|polic(?:y|ies)|standards?|"
                         r"sources?|rules?)|constitution|our "
                         r"(?:positions?|polic(?:y|ies)|standards?)|company standards?|"
                         r"current (?:policy|position)|established position|"
                         r"standard position|company requires)\b", re.I),
    READING: re.compile(r"\b(?:company's (?:own )?reading|reading of the law|the company "
                        r"reads|read by the company|in the company's view|constitution's "
                        r"reading|as the company reads)\b", re.I),
    LAW: re.compile(r"\b(?:the law|under (?:indian )?law|statut\w*|act\b|section|s\.|"
                    r"rules?)", re.I),
    HISTORY: re.compile(r"\b(?:histor\w*|past|previous|earlier|negotiated|exceptions?|"
                        r"not current)\b", re.I),
    CONTRACT: re.compile(r"\b(?:contract|agreement|document)\b", re.I),
}

MAX_CONTRACTS = 12
PER_SOURCE = 3
#: The answer's layers (`AM-107`) — what each claim is FOR in the answer the reader sees:
#: the direct answer, related context, a past negotiated deal, the law.
PRIMARY, RELATED, HISTORY_LAYER, LAW_LAYER = "PRIMARY", "RELATED", "HISTORY", "LAW"
#: Which kind leads when a part asks for several: the reader's own document, then the
#: company position, then the law, then history.
LANE_PRIORITY = (qp.CONTRACT, qp.COMPANY_POSITION, qp.LAW, qp.HISTORICAL_EXCEPTION)
_LAYER_KIND = {qp.CONTRACT: CONTRACT, qp.COMPANY_POSITION: POSITION, qp.LAW: LAW,
               qp.HISTORICAL_EXCEPTION: HISTORY}
#: How the prompt names each layer (`generation.CONTRACT_PROMPT_TEMPLATE` rule 7).
ROLE = {PRIMARY: "direct answer", RELATED: "related — only if it helps",
        HISTORY_LAYER: "historical context — only if it helps, said apart",
        LAW_LAYER: "legal background — only if it helps, said apart"}
#: A source whose best sentence scores this far (cross-encoder logits) below the best
#: source of its own kind for some part of the question gives the answer no claim. It
#: stays in the bundle — sufficiency is PHASE 9's and is not reopened — it only stops
#: crowding the direct answer: "what does our Constitution say about early
#: termination?" was given the Distribution and Vendor standards, the incident
#: register and Companies Act s. 466 beside §31.2, three claims each (2026-09-28).
FOCUS_MARGIN = 3.0
#: The anchor of a kind is the first such source in evidence order (PHASE 9's own
#: ranking) unless another scores this much higher; a source the reader named leads.
ANCHOR_MARGIN = 1.5
#: Claims a whole-document task is given (`AM-108`): one per section, the sections
#: on a ratified topic first.
DOCUMENT_WIDE_CLAIMS = 8
#: Claims from a source that is not the best of its kind for any part of the question,
#: and how many such sources the answer may draw on — the most relevant first.
RELATED_CLAIMS = 1
RELATED_SOURCES = 3
#: Historical-exception and company's-reading-of-the-law claims when the question did
#: not ask for that layer: kept as separate context, never the bulk of the answer.
UNASKED_LAYER_CLAIMS = 1

# Document families, in the Constitution's own terms: §31.4 sets "Partner, Reseller, and
# Distribution arrangements" apart from "MSA, NDA, SLA, or other normal/end-customer
# agreements", and a Vendor Agreement is paper the company signs as the customer. A
# question naming no type is read as about the company's own customer paper — so a
# Partner, Distribution or Vendor rule is never the direct answer to it, and gives a
# claim only when it scores as close as a source of an unasked kind must (`AM-107`).
# Priority only: what any position says is untouched.
_CHANNEL, _VENDOR, _CUSTOMER = "CHANNEL", "VENDOR", "CUSTOMER"
_ROLE_WORDS = re.compile(r"\b(?:(vendors?|suppliers?)|(distributors?|resellers?))\b",
                         re.I)
_APPLICABLE = re.compile(r"Applicable Document Types:\W*([^\n]+)", re.I)


def _families(types: set[str]) -> set[str]:
    return {_CHANNEL if t in ("PARTNER_AGREEMENT", "DISTRIBUTION_AGREEMENT") else
            _VENDOR if t == "VENDOR_AGREEMENT" else _CUSTOMER for t in types}


def _types_named(text: str) -> set[str]:
    from legalmind.assist import positions
    return {positions._TYPE_BY_PHRASE[m.group(1).lower()]
            for m in positions._TYPE_PATTERN.finditer(text)}


def question_families(question: str) -> set[str]:
    """The families the question names, or the customer family when it names none."""
    found = _families(_types_named(question))
    for vendor, _channel in _ROLE_WORDS.findall(question):
        found.add(_VENDOR if vendor else _CHANNEL)
    return found or {_CUSTOMER}


def source_families(source: evidence.Source) -> set[str]:
    """The families a source is written for — a standard's own type, a Constitution
    section's "Applicable Document Types" (before any "NOT applicable to") — or none
    for a general section, a statute or the reader's own document."""
    scope = _SCOPE_CODE.search(source.ref)
    if scope:
        return _families({scope.group(1)})
    m = _APPLICABLE.search(source.context) if source.ref.startswith("CONST:") else None
    if not m:
        return set()
    return _families(_types_named(re.split(r"\bNOT\b", m.group(1))[0]))

_MODAL = [
    ("PROHIBITED", re.compile(r"\b(?:must not|shall not|may not|cannot|can ?not|is not "
                              r"permitted|are not permitted|no [\w -]{1,30} is permitted|"
                              r"prohibited|not allowed|no right to)\b", re.I)),
    # "obligated" or "has an obligation to" binds; the NOUN does not — "the vendor
    # should provide ... flow-down obligations" was read as mandatory, so "requires"
    # passed as its restatement (run-9 E-02, 2026-09-27).
    ("MANDATORY", re.compile(r"\b(?:must|shall|is required|are required|required to|"
                             r"mandatory|obliged|obligated|(?:is|are) under (?:an |the )?"
                             r"obligation|(?:has|have) (?:an |the )?obligation to|"
                             r"remains? (?:fully )?liable|"
                             r"remains? payable|is payable|are payable)\b", re.I)),
    ("ADVISORY", re.compile(r"\b(?:should|recommended|consider\w*|appropriate|ought)\b",
                            re.I)),
    ("PERMITTED", re.compile(r"\b(?:may|can|is permitted|are permitted|entitled|allowed|"
                             r"has the right|have the right)\b", re.I)),
]
_NEGATION = re.compile(r"\b(?:not|no|never|none|nor|without|cannot)\b|n't\b", re.I)
_CONDITION = re.compile(
    r"\b(?:unless|provided that|provided|if|where|subject to|only if|only where|"
    r"in the absence of|for any reason not|to the extent|so long as|as long as|with a "
    r"fixed|within \d+|at least \d+|before the (?:end|expiry)|after (?:written )?notice)"
    # A token may keep an abbreviation's period when a number follows ("subject to
    # Cl. 5.1", "under s. 74"): read as "subject to Cl", the condition could never be
    # found in a sentence and every restatement of §31.2 was replaced (PHASE 13).
    r"\b(?:\s+(?:[A-Za-z]{1,4}\.(?=\s*\d)|[^\s,;.:()]+)){1,8}", re.I)
# An exception phrase ends at a modal: "other than international commercial
# arbitration shall be made …" swallowed s. 29A(1)'s "shall", so the proviso's "may"
# set its modality and "the tribunal shall make the award" failed (live, E-04; `AM-104`).
_EXCEPTION = re.compile(r"\b(?:except(?: for)?|other than|excluding|save for)\b"
                        r"(?:\s+(?!(?:shall|must|may|should|will|can)\b)[^\s;.:()]+){1,8}",
                        re.I)
_SKIP = re.compile(r"^(?:\*\*?STATUS|STATUS:|Applicable Document Types|Purpose:|Scope of "
                   r"Application:|\| ?:?-|Legal Mind —)|Conflicts Register|Stakeholder "
                   r"Version|^Evidence / Source:\W*$", re.I)
# A section's own statement of what it covers — every claim drawn from it carries it.
_SECTION_SCOPE = re.compile(r"\bThis section governs ([^.;]{4,160})", re.I)
#: Relevance bonus for a sentence under a "… Position …" heading — the position itself,
#: not its surrounding scope, law or drafting notes.
POSITION_BONUS = 2.0
# A ratified standard's chunk opens with "CODE §x Title (TYPE) " before its quote.
_POSITION_HEAD = re.compile(r"^[A-Z0-9_-]+-\d{3}\s.*?\((?:MSA|TOS|NDA|SLA|Partner "
                            r"Agreement|Vendor Agreement|Distribution Agreement|Order "
                            r"Form|Amendment)\)\s+")
_DRAFTING = re.compile(r"illustrative|drafting notes|not yet in any signed", re.I)
_INLINE_DRAFTING = re.compile(r"\[Illustrative clause:\].*$", re.I | re.M)
# Headings whose content is not a position: what the section is for, who it covers,
# where it came from, and notes addressed to counsel.
_NOT_POSITION = re.compile(r"purpose|entity|counsel|validation|source|notes?\b|"
                           r"trigger|conflict", re.I)
_SCOPE_CODE = re.compile(r"-(MSA|TOS|NDA|SLA|PARTNER_AGREEMENT|VENDOR_AGREEMENT|"
                         r"DISTRIBUTION_AGREEMENT|ORDER_FORM|AMENDMENT)-\d+")


@dataclass(frozen=True)
class Contract:
    n: int
    ref: str
    citation: str
    kind: str
    status: str
    text: str
    subject: str
    action: str
    object: str
    modality: str
    negated: bool
    conditions: tuple[str, ...]
    exceptions: tuple[str, ...]
    scope: str | None
    #: The heading that gives the sentence its meaning — "Acceptable position",
    #: "Unacceptable", "Negotiable / approval required". Without it, "A counterparty
    #: accepting the 30-day export window" reads as a fact, not as what is acceptable.
    frame: str | None = None
    #: PHASE 12 records (`AM-92`): where the claim sits, when it applies, what it is
    #: subject to, and what "this position" in it means — all from the source records.
    heading: tuple[str, ...] = ()
    temporal: str | None = None
    exceptions_text: str | None = None
    referent: str | None = None
    from_records: bool = False
    antecedents: tuple[tuple[str, str], ...] = ()
    #: PRIMARY · RELATED · HISTORY · LAW — where the claim sits in the answer.
    layer: str = PRIMARY
    #: Context the answer may leave out: a related source, or a historical or law
    #: layer the question did not ask for. A sentence restating it that fails a check
    #: is dropped rather than replaced by the record's text (`answer.repair_sentences`).
    optional: bool = False

    @property
    def authority(self) -> str:
        return {READING: "SECONDARY_REFERENCE", LAW: "PRIMARY_LAW",
                HISTORY: "HISTORICAL_EXCEPTION"}.get(self.kind, "COMPANY_CONSTITUTION")

    @property
    def plan_kind(self) -> str:
        """The PHASE 9 kind vocabulary the mechanical and entailment layers read."""
        return {READING: qp.LAW, LAW: qp.LAW, HISTORY: qp.HISTORICAL_EXCEPTION,
                CONTRACT: qp.CONTRACT}.get(self.kind, qp.COMPANY_POSITION)


def modality(text: str) -> tuple[str, bool]:
    """(the strongest modal class the sentence carries, whether it is negated) — read
    with its conditions and exceptions removed, so an "if the customer may …" does not
    set the claim's own modality."""
    core = _EXCEPTION.sub(" ", _CONDITION.sub(" ", text))
    for name, pattern in _MODAL:
        if pattern.search(core):
            return name, bool(_NEGATION.search(core))
    return "STATEMENT", bool(_NEGATION.search(core))


def _parts(text: str) -> tuple[str, str, str]:
    """subject · action · object, split at the first modal or verb-like word."""
    m = re.search(r"\b(?:must not|shall not|may not|must|shall|may|should|can(?:not)?|"
                  r"is|are|remains?|has|have|applies|apply|requires?|permits?|governs?|"
                  r"entitles?|renews?|survives?)\b", text, re.I)
    if not m:
        return text[:80], "", ""
    rest = text[m.end():].strip()
    verb = rest.split(" ", 1)[0] if rest else ""
    return (text[:m.start()].strip()[:120], f"{m.group(0)} {verb}".strip(),
            rest[len(verb):].strip()[:160])


def statements(source: evidence.Source) -> list[tuple[str, str]]:
    """(sentence, kind) for every claim-bearing sentence of a source, in order."""
    return [(s, k) for s, k, _, _ in _statements(source)]


# A context's header line — "Legal Constitution L1.10 · 31.14 Major Changes …",
# "The Companies Act, 2013 · Section 179 · Powers of Board".
# …and a document clause's heading, "7 · Limitation of Liability" (`AM-109`) — never a
# row whose recorded title is itself a clause sentence ("5.3 · Either party may …").
_HEADER = re.compile(r"^(?:Legal Constitution L[\d.]+ · |The [^·]{3,120} · (?:Section|"
                     r"Schedule|Rule|Regulation|Chapter)\b"
                     r"|\d+(?:\.\d+)* · [^.;:]{1,60}$)")
# What continues a statute's rule rather than starting a new one.
_STATUTE_TAIL = re.compile(r"^(?:\([a-z]{1,4}\)|\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)|"
                           r"Provided\b|Explanation\b)", re.I)
_SECTION_SCOPE_SENTENCE = re.compile(r"\s*This section governs [^.]*\.?", re.I)
_NEUTRAL_HEADING = re.compile(r"^(?:company position|standard position|established|"
                              r"confirmed|position|legal status|business status|"
                              r"applicable law|scope|status)\b", re.I)


def _subheading(label: str) -> str | None:
    """A sub-heading that scopes what follows ("A. Planned Full Service Discontinuation
    / Retirement", "Scenario 1 — Customer reports a breach"), or None."""
    text = re.sub(r"^[A-Z0-9][.)]\s+|\(.*?\)", "", label.rstrip(":")).strip(" *—-")
    if not text or _NEUTRAL_HEADING.match(text) or len(text.split()) > 10:
        return None
    return text


def _frame(label: str) -> str | None:
    """The meaning-bearing part of a heading, or None for a neutral one."""
    m = _FRAMES.search(label)
    return m.group(0).strip().rstrip(":").capitalize() if m else None


def _statements(source: evidence.Source) -> list[tuple[str, str, bool, str | None]]:
    """(sentence, kind, under a position heading, governing frame)."""
    from legalmind.assist import answer
    c = source.candidate
    heading_is_position = False
    frame: str | None = None
    base = {qp.CONTRACT: CONTRACT, qp.LAW: READING if c.authority == "SECONDARY_REFERENCE"
            else LAW, qp.HISTORICAL_EXCEPTION: HISTORY}.get(source.kind, POSITION)
    out: list[tuple[str, str, bool, str | None]] = []
    lead_in = False
    drafting = False
    labelled = _HISTORY_LABEL in source.context or _READING_LABEL in source.context
    if base == LAW and re.search(r"schedule|table [a-z]\b|\bform\b", source.ref + " "
                                 + source.context[:200], re.I):
        frame = "a model form in a Schedule — illustrative, not a requirement"
    # Header lines go BEFORE hard-wrapped lines are rejoined: rejoining first glued the
    # header to the heading after it ("… · 13. Termination" + "Acceptable Position:")
    # and the header skip then discarded the heading with it.
    body = "\n".join(x for x in source.context.split("\n")
                     if not _HEADER.match(x.strip()))
    # A standard file's chunk carries its drafting text INLINE, after "[Illustrative
    # clause:]" — never a position (`AM-92`'s known limitation, closed PHASE 13): the
    # marker and everything after it on that line is dropped before any sentence is read.
    body = _INLINE_DRAFTING.sub("", body)
    for raw in _WRAP.sub(" ", body).split("\n"):
        line = raw.strip().strip("*").strip()
        if not line or _SKIP.match(line):
            continue
        if line.endswith(":") and len(line) < 120:          # a heading
            drafting = bool(_DRAFTING.search(line) or _NOT_POSITION.search(line))
            heading_is_position = "position" in line.lower()
            frame = _frame(line) or _subheading(line)
            continue
        inline = re.match(r"^([A-Z][\w /()-]{2,40}):\s+(.+)$", line)
        if inline and _frame(inline.group(1)):              # "Unacceptable: X"
            frame, line = _frame(inline.group(1)), inline.group(2)
        if re.match(r"^(?:Standard|Established Company|Company) Position:", line):
            heading_is_position = True
            line = line.split(":", 1)[1].strip()
        if drafting or _DRAFTING.search(line[:80]) or re.match(
                r"^(?:Entity-wide|Legal Counsel|Counsel)\b", line):
            continue                                         # never a position
        kind = base
        if line.startswith(_HISTORY_LABEL):
            kind, line = HISTORY, line[len(_HISTORY_LABEL):].strip(" *")
        elif line.startswith(_READING_LABEL):
            kind, line = READING, line[len(_READING_LABEL):].strip(" *")
        elif labelled and base == HISTORY:
            kind = POSITION          # a labelled section's unlabelled lines are policy
        if line.startswith("|"):                            # a table row → a sentence
            cells = [x.strip(" *") for x in line.strip("|").split("|")]
            if len(cells) < 2 or cells[0].lower() in ("question", "category", "field"):
                continue
            line = " — ".join(x for x in cells if x)
        head = _POSITION_HEAD.match(line)
        if head:
            # A standard's own title is its scope: "A. Planned Full Service
            # Discontinuation / Retirement" — stripping it made the rule read general.
            title = re.sub(r"^[A-Z0-9_-]+-\d{3}\s+(?:§?[\d.]+\s+)?(?:[A-Z]\.\s+)?", "",
                           head.group(0)).rsplit("(", 1)[0].strip(" —-")
            frame = frame or (title if len(title.split()) <= 10 else None)
        line = _POSITION_HEAD.sub("", line).lstrip("—- ").removeprefix(
            "Evidence / Source:").strip(" *")
        # "This section governs …" is the section's scope: carried as a condition of
        # every claim drawn from it, never part of one (merged, it hid the scope).
        line = _SECTION_SCOPE_SENTENCE.sub("", line).strip()
        if not line:
            continue
        statute_tail = base == LAW and _STATUTE_TAIL.match(line)
        if out and ((raw.lstrip().startswith(("*", "-", "•")) and lead_in)
                    or statute_tail):
            # A scope-list item belongs to its lead-in; in a statute, the enumerated
            # items, the proviso and the Explanation belong to the rule they qualify
            # (run 4: s.179(1)'s first proviso, s.12(5)'s waiver, s.29A(3)'s extension
            # and "the earliest of the following dates" all reached readers dropped).
            prev = out[-1]
            out[-1] = (f"{prev[0].rstrip(';')} {line.rstrip(';')}".strip(), prev[1],
                       prev[2], prev[3])
            lead_in = line.rstrip().endswith((":", ";", "or", "and", "—"))
            continue
        lead_in = line.rstrip().endswith((":", ";", "or", "and"))
        merged: list[str] = []
        for sentence in answer._sentences(line):
            # A fragment ("It is recorded because …", "— a matter for Counsel …") keeps
            # its referent: it joins the sentence before it.
            if merged and re.match(r"^\W*(?:it|this|these|that|such|which|and|or|"
                                   r"provided(?: further)? that|provided)\b|^—",
                                   sentence, re.I):
                merged[-1] = f"{merged[-1]} {sentence}"
            else:
                merged.append(sentence)
        for sentence in merged:
            if len(sentence.split()) >= 5:
                out.append((sentence.strip(" *"), kind, heading_is_position, frame))
    return out


def section_scope(source: evidence.Source) -> str | None:
    """What the source's section says it covers ("ongoing, non-fixed-term
    arrangements") — first eight words, so a claim can carry it."""
    m = _SECTION_SCOPE.search(source.context)
    return " ".join(m.group(1).split()[:8]).rstrip(",") if m else None


def _contract(n: int, source: evidence.Source, text: str, kind: str,
              frame: str | None = None, unit=None, layer: str = PRIMARY,
              optional: bool = False) -> Contract:
    from legalmind.assist import answer
    mod, neg = modality(text)
    subject, action, obj = _parts(text)
    scope = _SCOPE_CODE.search(source.ref)
    conditions = [m.group(0).strip() for m in _CONDITION.finditer(text)]
    citation = answer.citation(source)
    if unit is not None:                               # PHASE 12 records (`AM-92`)
        words = guardrails._content_words(text)
        for covered in unit.scope:
            need = guardrails._content_words(covered)
            if kind != LAW and len(need & words) / max(1, len(need)) < 0.5:
                conditions.append(f"for {covered}{_SCOPE_TAG}")
        if not frame and unit.heading and _subheading(unit.heading[-1] + ":"):
            frame = re.sub(r"^[A-Z]\.\s+", "", unit.heading[-1])   # "A. MSA / Customer"
        citation += f"{unit.citation_suffix}" if unit.citation_suffix else ""
        if unit.heading and not unit.citation_suffix:
            citation += " — " + " > ".join(unit.heading)
    else:
        covered = section_scope(source)
        if covered and kind == POSITION:
            need = guardrails._content_words(covered)
            if len(need & guardrails._content_words(text)) / max(1, len(need)) < 0.5:
                conditions.append(f"for {covered}{_SCOPE_TAG}")   # PHASE 11's error
    return Contract(n, source.ref, citation, kind,
                    "HISTORICAL" if kind == HISTORY else "CURRENT", text, subject, action,
                    obj, mod, neg, tuple(conditions),
                    tuple(m.group(0).strip() for m in _EXCEPTION.finditer(text)),
                    scope.group(1) if scope else None, frame,
                    unit.heading if unit else (), unit.temporal if unit else None,
                    unit.exceptions if unit else None, unit.referent if unit else None,
                    unit is not None, unit.antecedents if unit else (), layer,
                    optional)


def build(bundle: evidence.Bundle, question: str, db=None) -> list[Contract]:
    """The approved claims, in answer order (`AM-107`).

    Every supporting source's sentences are scored against the whole question and each
    part of it (the local reranker; lexical overlap when it is absent). Then, per part
    and per source kind the part asks for, the best source is that part's ANCHOR and
    gives up to PER_SOURCE claims; another source of the same kind gives RELATED_CLAIMS
    only when it scores within FOCUS_MARGIN of that anchor, and a source of a kind the
    part did not ask for must come that close to the part's best source of any kind.
    Historical and reading-of-the-law sentences the question did not ask for give at
    most UNASKED_LAYER_CLAIMS each. The first part's first anchor leads, and every
    claim carries its LAYER — primary, related, historical, law — so the answer can put
    the direct answer first and keep the rest apart. Selection only: sufficiency,
    authority and version were decided by PHASE 9 and are not reopened."""
    from legalmind.assist import claim_records
    from legalmind.assist import rerank as cross_encoder

    words = guardrails._content_words(question)
    parts = bundle.parts or (evidence.Part(question, (), "", ()),)
    shape = bundle.presentation
    if shape.document_wide:
        return _document_wide(bundle, question, db, shape)
    queries = list(dict.fromkeys([question, *(p.question for p in parts)]))
    recorded: dict = {}
    per_source: list[tuple] = []
    for source in bundle.shown():
        if shape.document_task and source.kind != qp.CONTRACT and not (
                bundle.parts and any(qp.COMPANY_POSITION in p.lanes or qp.LAW in p.lanes
                                     for p in bundle.parts)):
            continue    # a task about the document: the document alone answers it
        units = claim_records.units(db, source) if db is not None else None
        if units:
            # One claim per SENTENCE of a record, each carrying the record's heading,
            # scope, status, referent and exceptions (`AM-107`). A whole paragraph as
            # one claim made every concise sentence "drop a condition" of a different
            # rule in it — §13's cure period, s. 74's illustrations — so a correct
            # answer was replaced by the paragraph itself (2026-09-28).
            rows = []
            for u in units:
                for piece in pieces(u.text):
                    labelled = _LABELLED_POSITION.match(piece)
                    # "Established Company Position: No early exit …" — the label is
                    # the claim's kind, said by its SAY AS phrase; left in, a repair
                    # read "states: Established Company Position: No early exit".
                    claim = piece[labelled.end():].strip() if labelled else piece
                    rows.append((claim, _kind_of_record(u), bool(u.frame) or
                                 "position" in " ".join(u.heading).lower()
                                 or bool(labelled), u.frame))
                    recorded[(source.ref, claim)] = u
        else:
            rows = _statements(source)
        if rows:
            per_source.append((source, rows))
    # ONE batched call for every (query, sentence) pair (PHASE 13, `AM-94`).
    every = [s for _, rows in per_source for s, _, _, _ in rows]
    scored = cross_encoder.scores_many(queries, every) if every else None
    at = 0
    table = []            # (source, rows, per-query sentence scores)
    for source, rows in per_source:
        n = len(rows)
        if scored is not None:
            by_q = [[scored[q][at + i] for i in range(n)] for q in range(len(queries))]
        else:
            lexical = [float(len(words & guardrails._content_words(r[0]))) for r in rows]
            by_q = [lexical for _ in queries]
        at += n
        by_q = [[x + (POSITION_BONUS if rows[i][2] else 0.0) for i, x in enumerate(q)]
                for q in by_q]
        table.append((source, rows, by_q))

    from legalmind.assist import retrieval
    asked_any = {lane for p in parts for lane in p.lanes}
    # What each source can serve — every authority among its matching records, not
    # only its label: §31.2 is labelled historical when its history paragraph matched,
    # yet holds the early-termination position (`retrieval.kinds_of`, `AM-94`).
    serves = [retrieval.kinds_of(src.candidate) | {src.kind} for src, _, _ in table]
    wanted = question_families(question)
    fits = [not (f := source_families(src)) or bool(f & wanted) for src, _, _ in table]
    anchors: list[int] = []
    in_focus: set[int] = set()
    # A SOURCE is ranked by its PHASE 9 relevance — the cross-encoder on its whole
    # context and breadcrumbs — never by its best bare sentence: out of context, §31.2's
    # "No early exit is permitted from a confirmed fixed-term commitment" scored -4.9
    # against the question it answers while a Distribution standard's one-line rule
    # scored 1.1 (2026-09-28). Sentence scores only choose sentences within a source.
    best = [src.relevance if src.relevance is not None else max(max(q) for q in by_q)
            for src, _, by_q in table]
    anchor_lane: dict[int, str] = {}
    for p in parts:
        lanes = [lane for lane in LANE_PRIORITY if lane in p.lanes]
        top = max(best) if best else 0.0
        lane_top: dict[str, float] = {}
        for lane in lanes:
            mine = [i for i in range(len(table)) if lane in serves[i]]
            if mine:
                mine = [i for i in mine if fits[i]] or mine
                if lane == qp.LAW:
                    # The law itself leads the law layer; the company's reading of it
                    # (a Constitution section) supports it — golden E-01's s. 74 was
                    # outranked by Constitution §14's reading of s. 74.
                    statute = routing.Domain.STATUTES.value
                    mine = [i for i in mine
                            if table[i][0].candidate.domain == statute] or mine
                named_here = [i for i in mine if table[i][0].named]
                strongest = max(mine, key=lambda i: best[i])
                anchor = (named_here[0] if named_here else strongest
                          if best[strongest] > best[mine[0]] + ANCHOR_MARGIN else mine[0])
                lane_top[lane] = max(best[i] for i in mine)
                if anchor not in anchors:
                    anchors.append(anchor)
                    anchor_lane[anchor] = lane
        for i, (src, _, _) in enumerate(table):
            # A source of a kind this part asks for, written for the paper the question
            # is about, always keeps one claim: its score is too noisy to cut on (golden
            # J-03's gold §16 scored 1.6 beside a 4.1 anchor). Any other source must
            # come within FOCUS_MARGIN of what it competes with.
            served = [lane for lane in serves[i] if lane in lane_top]
            if not fits[i]:
                continue          # another family's rule: in the bundle, never the answer
            # Another clause of the reader's document is not this clause's answer: the
            # liability question pasted force majeure, compliance and indemnity beside
            # §7.1 and §7.3 (all "in focus" by serving the contract lane; scores 1.65,
            # 1.2 against -2.7 to -4.9 — browser, 2026-09-29, `AM-109`).
            if src.candidate.domain == routing.Domain.DOCUMENT.value and \
                    best[i] < lane_top.get(qp.CONTRACT, top) - FOCUS_MARGIN:
                continue
            # A standard filed under a topic the question does not place (a Payment
            # Terms standard beside a termination question) earns no automatic claim.
            if (served and not evidence.off_topic(src.candidate, question)) \
                    or best[i] >= top - FOCUS_MARGIN:
                in_focus.add(i)
    in_focus |= {i for i, (src, _, _) in enumerate(table) if src.named}
    if not anchors and table:             # no part names a lane: the best source leads
        anchors = [max(range(len(table)), key=lambda i: (fits[i], best[i]))]
    in_focus |= set(anchors)
    if anchors and anchor_lane.get(anchors[0]) == qp.CONTRACT:
        # The reader's document IS the answer, and one clause spans several chunks:
        # every chunk of it in focus answers with it — §17.3's exclusions belong to
        # §17.2's cap. As related context they were one optional claim each, and the
        # liability answer lost its carve-outs (scenario 4, 2026-09-28).
        more = [i for i in sorted(in_focus)
                if i not in anchors and qp.CONTRACT in serves[i]]
        anchors += more
    else:
        more = []
    # What the direct answer IS: the kind of the first part's first anchor, in
    # LANE_PRIORITY order — the reader's own document, else the company position, else
    # the law, else history. A claim of that kind from an anchor is the direct answer;
    # from another source it is related; a claim of another kind is its own layer.
    lead = _LAYER_KIND[anchor_lane.get(anchors[0], qp.COMPANY_POSITION)] if anchors \
        else POSITION

    def layer_of(i: int, kind: str) -> str:
        own = (HISTORY if kind == HISTORY else LAW if kind in (LAW, READING)
               else CONTRACT if kind == CONTRACT else POSITION)
        if own == lead:
            return PRIMARY if i in anchors else RELATED
        return {HISTORY: HISTORY_LAYER, LAW: LAW_LAYER}.get(own, RELATED)

    # History is asked for when the plan asks, or when the reader's own figure is
    # stated only in a past negotiated deal — "their signed MSA mentions 6 months".
    history_asked = qp.HISTORICAL_EXCEPTION in asked_any or any(
        qp.HISTORICAL_EXCEPTION in a.stated_by for a in bundle.assertions)
    capped = {HISTORY_LAYER: not history_asked, LAW_LAYER: qp.LAW not in asked_any}
    used = {HISTORY_LAYER: 0, LAW_LAYER: 0}
    order = anchors + sorted((i for i in in_focus if i not in anchors),
                             key=lambda i: -best[i])[:RELATED_SOURCES]
    picked: list[tuple] = []
    said: list[set[str]] = []        # the content words of every claim chosen so far
    for i in order:
        source, rows, by_q = table[i]
        # A further chunk of the reader's document takes two claims, so a clause over
        # four chunks cannot fill MAX_CONTRACTS before the law the reader also asked.
        budget = (PER_SOURCE - 1 if i in more else PER_SOURCE if i in anchors
                  else RELATED_CLAIMS)
        score = [max(q[k] for q in by_q) for k in range(len(rows))]
        # A record's provenance ("Evidence / Source: Legal Conflicts Register, C-04 …")
        # and a statute's Illustrations are chosen last: the one names documents and
        # states nothing, the others are examples of the rule, not the rule — s. 74's
        # illustrations (a) and (f) were two of its three claims (2026-09-28).
        illustrative = next((k for k, r in enumerate(rows)
                             if re.match(r"^Illustrations?\b", r[0])), len(rows))
        cited_only = [k >= illustrative or bool(_TO_THE_TOOL.match(r[0])) or bool(
            getattr(recorded.get((source.ref, r[0])), "extra", {}).get("provenance"))
            for k, r in enumerate(rows)]
        chosen: list[int] = []
        # The one unasked historical sentence is the Constitution's own labelled summary
        # ("Historical exceptions: A review of actual signed MSAs found …") when there is
        # one: the cross-encoder scores such a summary -7.7 against a policy question,
        # below the clause-by-clause notes around it.
        later = [not (capped[HISTORY_LAYER] and r[1] == HISTORY and r[2]) for r in rows]
        for k in sorted(range(len(rows)),
                        key=lambda k: (cited_only[k], later[k], -score[k])):
            if len(chosen) == budget or (cited_only[k] and chosen):
                break                      # an example or a provenance line never pads
            # A related claim that says what an earlier one already said adds nothing:
            # §9 repeating LIABILITY-MSA-001 word for word under "Also relevant" read
            # as the same position twice (`AM-109`). The direct answer is never cut,
            # and neither is a ratified standard: it names the paper the rule is
            # ratified for (golden K-04, L-02 lost theirs to the Constitution's text).
            words = guardrails._content_words(rows[k][0])
            if i not in anchors and words and \
                    source.candidate.domain != routing.Domain.POSITIONS.value and any(
                        len(words & w) / len(words) >= RESTATES for w in said):
                continue
            layer = layer_of(i, rows[k][1])
            if layer in used and capped[layer]:
                # History nobody asked for is shown only as the direct answer's own
                # context — §31.2's past deals beside §31.2, never beside §13. Law is
                # kept to sources within FOCUS_MARGIN instead: golden E-04's tribunal
                # deadline IS s. 29A, though the plan asked for no law lane.
                if used[layer] >= UNASKED_LAYER_CLAIMS or (
                        layer == HISTORY_LAYER and i not in anchors):
                    continue
                used[layer] += 1
            chosen.append(k)
            said.append(words)
        picked += [(source, rows[k][0], rows[k][1], rows[k][3], layer_of(i, rows[k][1]))
                   for k in sorted(chosen)]
    return [_contract(n, s, t, k, f, recorded.get((s.ref, t)), layer,
                      layer == RELATED or capped.get(layer, False))
            for n, (s, t, k, f, layer) in enumerate(picked[:MAX_CONTRACTS], 1)]


#: Share of a related claim's content words an earlier claim must carry for it to add
#: nothing (`AM-109`).
RESTATES = 0.8


# A note the Constitution addresses to the product, not to the reader ("⚠ IMPORTANT —
# CORRECT READING OF …", "Legal Mind must not read a 90-day clause as …"), or a bare
# pointer ("See Section 27, Item 4."). Chosen last, and never to pad: shown alone the
# one reads as a rule about the reader's deal, the other says nothing.
_TO_THE_TOOL = re.compile(r"^\W*(?:⚠\s*)?(?:IMPORTANT\b|Legal ?Mind\s+(?:must|should|"
                          r"may|will|shall|states|treats|does)\b|See (?:also )?"
                          r"(?:Section|Appendix|§)[^.]{0,40}\.?$)", re.I)
# A sentence the Constitution labels as what it is — "Established Company Position:",
# "Historical exceptions:" — is its kind's own statement, preferred over its neighbours.
_LABELLED_POSITION = re.compile(r"^[^:]{0,40}\b(?:position|historical?)\b[^:]{0,20}:",
                                re.I)
_REFERS_BACK = re.compile(r"^\W*(?:it|this|these|that|such|which|and|or|provided(?: "
                          r"further)? that|provided|explanation)\b|^[—-]", re.I)


def pieces(text: str) -> list[str]:
    """A record's claims: its own sentences (`answer._record_sentences`), with a
    sentence that refers back ("This is the same position …", a proviso, an
    Explanation) kept with the one before it, and a fragment under five words ("74.")
    kept with the one after it."""
    from legalmind.assist import answer
    out: list[str] = []
    carry = ""
    # A statute's "Exception.—" is its own rule with its own modality ("shall be liable
    # … the whole sum"); glued to s. 74's "is entitled to … reasonable compensation" it
    # made a faithful restatement of the rule read as a change of modality.
    chunks = re.split(r"(?<=[.\]])\s+(?=Exception\.?\s?[—-])", text)
    for piece in (x for chunk in chunks for x in answer._record_sentences(chunk)):
        piece = f"{carry} {piece}".strip() if carry else piece
        carry = ""
        if len(piece.split()) < 5:
            carry = piece
        elif out and _REFERS_BACK.match(piece):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    if carry:
        if out:
            out[-1] = f"{out[-1]} {carry}"
        else:
            out.append(carry)
    return out


def _document_wide(bundle: evidence.Bundle, question: str, db,
                   shape) -> list[Contract]:
    """A whole-document task (`AM-108`): one claim per outline chunk — the clause's
    first substantive sentence, the operative statement a summary is made of — in
    document order, so the answer covers the document instead of restating one
    section. Sections that touch a ratified topic (the organization's own vocabulary,
    `planner.topics_in`) come first; a RISKS task takes only those. Up to
    MAX_CONTRACTS; the model then chooses which to say and every sentence is verified
    exactly as prose is."""
    from legalmind.assist import planner
    picked: list[tuple[evidence.Source, str]] = []
    for source in bundle.shown():
        if source.kind != qp.CONTRACT:
            continue
        first = next((t for t, _ in statements(source)
                      if len(t.split()) >= 8 and not t.rstrip(":").isupper()), None)
        if first:
            picked.append((source, first))
    topical = [(s, t) for s, t in picked if planner.topics_in(s.context)]
    if shape.task == presentation_mod.RISKS:
        picked = topical
    else:
        rest = [x for x in picked if x not in topical]
        picked = topical + rest if len(topical) < MAX_CONTRACTS else topical
    # Eight sections at most — a summary of twelve read as the document itself — and
    # four when the reader asked for a SHORT one: brevity set at the source, not
    # hoped for from the model.
    limit = (DOCUMENT_WIDE_CLAIMS // 2 if shape.length == presentation_mod.SHORT
             else DOCUMENT_WIDE_CLAIMS)
    return [_contract(n, s, t, CONTRACT, None, None, PRIMARY)
            for n, (s, t) in enumerate(picked[:limit], 1)]


def _kind_of_record(u) -> str:
    return {"SECONDARY_REFERENCE": READING, "HISTORICAL_EXCEPTION": HISTORY,
            "PRIMARY_LAW": LAW}.get(u.authority, POSITION)


@dataclass(frozen=True)
class Relation:
    a: int
    b: int
    kind: str          # CONFLICT · SEPARATE_LAYER
    reason: str


def relations(contracts: list[Contract]) -> list[Relation]:
    """The evidence/conflict map. Two CURRENT claims of the same kind and scope CONFLICT
    only when they say nearly the same thing (content-word Jaccard ≥ CONFLICT_SIMILAR,
    figures aside) yet differ in a figure or in polarity — "30 days" against "60 days"
    for the same notice. A different modality alone is a different rule (for convenience
    / for cause), not a conflict: the first live run flagged exactly that, and answers
    filled with "these positions differ". Different kinds on the same subject are
    SEPARATE LAYERS — named, never merged."""
    def core(c: Contract) -> set[str]:
        return {w for w in guardrails._content_words(c.text) if not w[0].isdigit()}
    out = []
    for i, x in enumerate(contracts):
        for y in contracts[i + 1:]:
            cx, cy = core(x), core(y)
            similar = len(cx & cy) / max(1, len(cx | cy))
            if similar < LAYER_SIMILAR:
                continue
            if x.kind != y.kind:
                out.append(Relation(x.n, y.n, "SEPARATE_LAYER",
                                    f"{x.kind} and {y.kind} on the same subject"))
                continue
            if x.status != "CURRENT" or y.status != "CURRENT" or x.scope != y.scope \
                    or similar < CONFLICT_SIMILAR:
                continue
            figures = set(guardrails.unstated_figures(x.text, [y.text]))
            if figures or x.negated != y.negated:
                why = "different figure" if figures else "opposite polarity"
                out.append(Relation(x.n, y.n, "CONFLICT", why))
    return out


#: Similarity (content-word Jaccard) for two claims to be about the same thing.
LAYER_SIMILAR = 0.35
CONFLICT_SIMILAR = 0.6


def render(contracts: list[Contract], rels: list[Relation]) -> str:
    lines = []
    for c in contracts:
        # A statute's claim is said as its Act — "Under the Indian Contract Act, 1872" —
        # since "this Act" must be resolved in the sentence; "The law provides …" failed
        # the check that holds it (live, s. 74, `AM-107`).
        say = (f"Under the {c.referent}" if c.kind == LAW and c.referent
               else SAY[c.kind])
        fields = [f"ROLE: {ROLE[c.layer]}", f"SAY AS: {say}",
                  f"MODALITY: {c.modality.lower()}",
                  f"NEGATED: {'yes' if c.negated else 'no'}"]
        own = [x for x in c.conditions if _SCOPE_TAG not in x]
        covered = [x.replace(_SCOPE_TAG, "")[4:] for x in c.conditions if _SCOPE_TAG in x]
        if own:
            fields.append("CONDITIONS: " + " | ".join(own))
        if covered:
            fields.append("APPLIES ONLY TO: " + covered[0] + " (say so)")
        if c.exceptions:
            fields.append("EXCEPTIONS: " + " | ".join(c.exceptions))
        if c.frame:
            fields.append(f"FRAME: {c.frame} (say so — it is what this claim means)")
        if c.scope:
            fields.append(f"SCOPE: {c.scope.replace('_', ' ')} agreements only (say so)")
        fields.append(f"STATUS: {c.status.lower()}")
        if c.temporal:
            fields.append(f"TEMPORAL STATUS: {c.temporal} (say so)"
                          if c.temporal != "REPEALED"
                          else "REPEALED — historical, not current law (say so)")
        if c.referent:
            fields.append(f"'THIS' REFERS TO: {c.referent} (name it)")
        if c.exceptions_text:
            fields.append(f"SUBJECT TO THESE EXCEPTIONS: {c.exceptions_text} (say so)")
        for said, meant in c.antecedents:
            fields.append(f"'{said.upper()}' MEANS: {meant} (say so)")
        lines.append(f"[{c.n}] {c.citation} · " + " · ".join(fields)
                     + f"\n    TEXT: {c.text}")
    conflict = [r for r in rels if r.kind == "CONFLICT"]
    if conflict:
        lines.append("CONFLICTS (state both, attributed, and say they differ — never "
                     "choose one or blend them): "
                     + "; ".join(f"[{r.a}] and [{r.b}] ({r.reason})" for r in conflict))
    return "APPROVED CLAIMS:\n" + "\n".join(lines)


def _verbatim(claim: str, c: Contract) -> bool:
    """The sentence's body is the record's own words (a repair, `answer.verbalise`):
    every run of four or more words between its separators occurs in the record."""
    body = claim.split(" states: ", 1)[1] if " states: " in claim else claim
    # The note verbalise appends, before the sentence's full stop; a commencement note
    # may hold its own "(Section 28)".
    body = re.sub(r"\s*\((?:in force|repealed|not yet in force|sub-section \(|clause \(|"
                  r"[^()]*\bbeing\b)(?:[^()]|\([^()]*\))*\)?"
                  r"[\s.]*$", "", body, flags=re.I)
    body = re.sub(r";\s*subject to these exceptions:.*$", "", body)
    own = " ".join(c.text.split())
    pieces = [x.strip(" .") for x in re.split(r";\s+|(?<=[.!?])(?<!\.\.\.)\s+", body)]
    pieces = [x for x in pieces if len(x.split()) >= 4]
    return bool(pieces) and all(x in own for x in pieces)


def attribution(c: Contract) -> tuple:
    """Who says a claim, and in what frame and scope — what a sentence must name.
    Claims sharing it are one voice: said once, then continued (`AM-109`)."""
    return (c.ref, c.kind, c.frame, c.scope)


def check(sentence: str, cited: list[Contract], preceding: str = "",
          carried: frozenset[tuple] = frozenset()) -> list[str]:
    """The sentence against the contracts it cites — deterministic (`AM-91` r4).
    `preceding` — the answer so far: a statute's Act, once named there, need not be
    named again in every later sentence (PHASE 13, `AM-94`).
    `carried` — the `attribution`s the previous sentence of the same paragraph named:
    a sentence citing only claims with those continues their attribution, frame and
    scope instead of repeating them ("The company position (Liability — …), for MSA
    agreements, states:" opened every sentence of one answer, `AM-109`). Every other
    check still applies to it."""
    from legalmind.assist import answer
    claim = answer._MARKER.sub("", sentence)
    failures = []
    kinds = {c.kind for c in cited}
    inherited = bool(cited) and all(attribution(c) in carried for c in cited)
    procedural = re.match(r"^\W*(?:the next step|to proceed|next,|you should|legal "
                          r"counsel should)", claim, re.I)
    for k in kinds if not (procedural or inherited) else ():
        if not ATTRIBUTION[k].search(claim):
            failures.append(f"source kind not named ({SAY[k]}): {sentence[:80]!r}")
    from legalmind.assist.verify import _LAW_SOURCE, _READING
    if _LAW_SOURCE.search(claim) and not _READING.search(claim) and LAW not in kinds:
        failures.append(f"law stated from the company's reading or position: "
                        f"{sentence[:80]!r}")
    if HISTORY in kinds and kinds == {HISTORY} and re.search(
            r"\b(?:current|today|now)\b", claim, re.I) and not re.search(
            r"\bnot (?:the )?current\b|\bno longer\b", claim, re.I):
        failures.append(f"a historical exception stated as current: {sentence[:80]!r}")
    # A sentence that stops at its modal has dropped what the modal governs: "the
    # Receiving Party shall not, directly or indirectly [4]." lost "solicit" (run 9,
    # C-04; `AM-104`) and passed as a verbatim prefix of the record.
    if _DANGLING_MODAL.search(claim):
        failures.append(f"stops at its modal, the act it governs dropped: "
                        f"{sentence[:80]!r}")
    # A section the sentence names is one its cited claims name — whole numbers, so
    # "commencing 13 May 2027 under Section 28" for the Constitution's "(Section
    # 28.2.1)" reads as the Act's s. 28 and fails (run 9, F-05; `AM-104`).
    own = {n for c in cited for n in _SECTION_REF.findall(
        " ".join((c.text, c.citation, c.temporal or "", c.frame or "", *c.heading)))}
    for n in dict.fromkeys(_SECTION_REF.findall(claim)):
        if cited and n not in own:
            failures.append(f"section {n} is not one its cited claims name: "
                            f"{sentence[:80]!r}")
    for c in cited:
        dates = "".join("|" + re.escape(d) for d in re.findall(r"\d{1,2} \w+ \d{4}",
                                                               c.temporal or ""))
        # A phrase that STATES a status: s. 33(2)'s own "proportionate and effective"
        # and "for the time being in force" passed as its commencement (run 9, J-04;
        # `AM-104`).
        if c.temporal and not re.search(r"\b(?:not yet in force|(?<!time being )in force|"
                                        r"commenc\w*|effective (?:from|on|date)|takes? "
                                        r"effect|with effect from|repeal\w*)\b" + dates,
                                        claim, re.I):
            failures.append(f"temporal status of [{c.n}] lost ({c.temporal[:40]!r}): "
                            f"{sentence[:80]!r}")
        if c.referent:
            need = guardrails._content_words(c.referent) - {"stakeholder", "confirmed"}
            named = guardrails._content_words(claim)
            if c.kind == LAW:                      # the Act, named anywhere before
                named |= guardrails._content_words(preceding)
            if need and len(need & named) / len(need) < CONDITION_KEPT:
                failures.append(f"'this' of [{c.n}] not resolved ({c.referent[:40]!r}): "
                                f"{sentence[:80]!r}")
        for said, meant in c.antecedents:
            need = guardrails._content_words(meant)
            if re.search(re.escape(said), claim, re.I) and need and len(
                    need & guardrails._content_words(claim)) / len(need) < CONDITION_KEPT:
                failures.append(f"antecedent of {said!r} in [{c.n}] lost "
                                f"({meant[:40]!r}): {sentence[:80]!r}")
        if c.exceptions_text and not re.search(r"\bexcept|\bexception|shorter notice|"
                                               r"immediate action|unless", claim, re.I):
            failures.append(f"exceptions of [{c.n}] not stated: {sentence[:80]!r}")
    # Roadmap §13: a sentence that speaks for the Constitution or the company position
    # cites a position claim — "The Legal Constitution does not specify 6 months …,
    # though historically … [10]" cited only a historical deal (live, GT-00). Words the
    # cited claim itself carries ("… not a fixed Constitution value") are its own.
    # [A] carries the code's own finding of what no position states, so it may be cited.
    if kinds and POSITION not in kinds and "[A]" not in sentence and \
            _SPEAKS_FOR_POSITION.search(claim) and not any(
                # …and so is a status the record carries ("the date Constitution
                # §28.2 states", `AM-104`).
                _SPEAKS_FOR_POSITION.search(f"{c.text} {c.temporal or ''}")
                for c in cited):
        failures.append(f"the company position stated without a position claim: "
                        f"{sentence[:80]!r}")
    if ATTRIBUTION[READING].search(claim) and READING not in kinds and kinds & {
            POSITION, HISTORY}:
        failures.append(f"a company position called the company's reading of the law: "
                        f"{sentence[:80]!r}")
    words = guardrails._content_words(claim)
    for c in cited:
        if c.frame and not inherited:
            meaning = _frame(c.frame)        # "acceptable", "unacceptable", …
            need = guardrails._content_words(c.frame) - {"position", "positions"}
            kept = (re.search(re.escape(meaning.split()[0]), claim, re.I) if meaning
                    else not need or len(need & words) / len(need) >= CONDITION_KEPT)
            if not kept:
                failures.append(f"drops the frame of [{c.n}] ({c.frame}): "
                                f"{sentence[:80]!r}")
        if c.scope and c.scope in _SCOPE_WORDS and not inherited and not re.search(
                _SCOPE_WORDS[c.scope], claim, re.I):
            failures.append(f"drops the scope of [{c.n}] ({c.scope}): {sentence[:80]!r}")
        for cond in (*c.conditions, *c.exceptions):
            need = guardrails._content_words(cond)
            if len(need) >= 2 and len(need & words) / len(need) < CONDITION_KEPT:
                failures.append(f"drops a condition of [{c.n}] ({cond[:50]!r}): "
                                f"{sentence[:80]!r}")
                break
        # The exceptions are the record's own words, carried beside the claim: their
        # "should" is not the claim's modality.
        bare = claim
        for part in re.split(r"(?<=[.!?])(?<!\.\.\.)\s+", c.exceptions_text or ""):
            bare = bare.replace(part.rstrip(".") or "\0", "")
        mod, neg = modality(bare)
        own = guardrails._content_words(c.text)
        restating = len(own & words) / max(1, len(own)) >= 0.5
        if _verbatim(claim, c):
            # The record's own sentences carry their own modality and polarity; the
            # contract's were read off its WHOLE text, which may hold several.
            continue
        if c.modality != "STATEMENT" and mod != "STATEMENT" and _STRENGTH[mod] != \
                _STRENGTH[c.modality]:
            failures.append(f"modality {c.modality.lower()} → {mod.lower()} of [{c.n}]: "
                            f"{sentence[:80]!r}")
        elif restating and (c.modality == "STATEMENT") != (mod == "STATEMENT"):
            # "shall provide" restated as "provides", "may authorise" as "authorises",
            # "are enforceable" as "must be enforced" — the obligation or permission
            # is part of the claim (four such sentences reached readers in run 4).
            failures.append(f"modality {c.modality.lower()} → {mod.lower()} of [{c.n}]: "
                            f"{sentence[:80]!r}")
        # Negation only where the sentence RESTATES the claim (half its words) and the
        # claim is short enough for its polarity to be one thing — a 60-word historical
        # note with a stray "not" is not a negated claim.
        if restating and len(c.text.split()) <= 40 and neg != c.negated and not (
                c.modality == "PROHIBITED" or mod == "PROHIBITED"):
            failures.append(f"negation of [{c.n}] not preserved: {sentence[:80]!r}")
    # Grounding: a factual sentence carries its cited claims' words. Below GROUNDED the
    # sentence is saying something the approved claims do not (run 4: garbled
    # fragments, a Purpose line turned into a permission, a specimen form turned into
    # a rule) — the sentence repair puts the approved text in its place.
    own_all = set().union(set(), *(guardrails._content_words(c.text) for c in cited))
    framing = set().union(set(), *(guardrails._content_words(
        f"{SAY[c.kind]} {c.frame or ''} {' '.join(c.conditions)} {c.scope or ''} "
        f"{c.exceptions_text or ''} {c.referent or ''} {c.temporal or ''} "
        f"{' '.join(m for _, m in c.antecedents)}")
        for c in cited))
    if words and len(words & (own_all | framing)) / len(words) < GROUNDED:
        failures.append(f"not grounded in its cited claims "
                        f"({len(words & (own_all | framing)) / len(words):.2f}): "
                        f"{sentence[:80]!r}")
    return failures


#: Share of a restating sentence's content words its cited claims (and their frame,
#: scope and conditions) must supply.
GROUNDED = 0.65


def check_answer(text: str, cited_by_sentence: list[list[Contract]]) -> list[str]:
    """Answer-level: a section's stated scope ("for ongoing, non-fixed-term
    arrangements") must appear once in an answer that uses that section."""
    words = guardrails._content_words(text)
    failures = []
    scopes = {c for cs in cited_by_sentence for x in cs for c in x.conditions
              if _SCOPE_TAG in c}
    for cond in scopes:
        plain = cond.replace(_SCOPE_TAG, "")[4:]
        need = guardrails._content_words(plain)
        if len(need & words) / max(1, len(need)) < CONDITION_KEPT:
            failures.append(f"the answer never states the scope {plain!r}")
    return failures


#: Marks a condition that came from a section's own scope statement.
_SCOPE_TAG = "\u200b"


#: Headings whose word carries the sentence's meaning.
_FRAMES = re.compile(r"\b(?:unacceptable(?: positions?)?|acceptable(?: positions?)?|"
                     r"negotiable(?: / approval required)?|approval required|not defined|"
                     r"prohibited)\b", re.I)
#: How a reader recognises each document type named as a claim's scope.
_SCOPE_WORDS = {
    "MSA": r"\bMSAs?\b|master services", "TOS": r"\bTOS\b|terms of service|\bterms\b",
    "NDA": r"\bNDAs?\b|non-disclosure|confidentiality agreement",
    "SLA": r"\bSLAs?\b|service level", "PARTNER_AGREEMENT": r"partner",
    "VENDOR_AGREEMENT": r"vendor", "DISTRIBUTION_AGREEMENT": r"distribut",
    "ORDER_FORM": r"order form|purchase order", "AMENDMENT": r"amendment|addend"}


_DANGLING_MODAL = re.compile(r"\b(?:(?:shall|must)(?:\s+not)?|(?:may|will|should)\s+not)"
                             r"(?:,?\s+(?:either\s+)?directly\s+or\s+indirectly)?"
                             r"[\s,;:.—-]*$", re.I)
_SECTION_REF = re.compile(r"(?:\bsections?|\bs\.|§)\s*(\d+(?:\.\d+)*[A-Z]?)\b", re.I)

#: Speaking for the organisation's current position — not "not current policy", which
#: is how a historical exception is named.
_SPEAKS_FOR_POSITION = re.compile(r"\b(?:legal )?constitution\b|\bcompany(?:'s)? "
                                  r"(?:position|policy)\b|\bour (?:position|policy)\b",
                                  re.I)

#: The source-kind failures of `check` — held to every sentence, context or not.
KIND_FAILURES = ("source kind not named", "law stated from the company's reading",
                 "a historical exception stated as current",
                 "a company position called the company's reading",
                 "the company position stated without a position claim")

#: A condition counts as kept when this share of its content words is in the sentence.
CONDITION_KEPT = 0.4
_STRENGTH = {"PROHIBITED": 3, "MANDATORY": 2, "ADVISORY": 1, "PERMITTED": 0}
