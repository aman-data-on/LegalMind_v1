"""The Ask agent's verifier, response ladder, deterministic floor and renderer — Phase 4
(Ask plan 4.1–4.5, architecture v2.1 §5.6–5.9), with the owner's Phase 3 review (P1–P11).

Local and model-free. Runs on every agent answer before it could be shown; checks each
block against the rule for its kind, with the evidence the turn actually showed.

  V1  a sourced block cites ≥ 1 key, every key is one this turn showed, and (P4) every
      cited key has a location; at most two cites per claim; no duplicates; a key named
      inline in the prose is moved into the cite list, an unknown one is a violation
  V2  every figure in a sourced block is in the text it cites (words and digits alike)
  V3  negation parity: a sourced block that negates must cite text that negates
  V4  the block shares ≥ half its content words with the text it cites
  V5  a block that cites nothing makes no authority attribution
  V6  a user_stated block cites the user's material (U…) only and attributes it
  V7  (P9) a reasoning block that states a legal conclusion frames it conditionally
  V8  at most one clarify block, and (P7) only when nothing else answers
  P2  a cited record's agreement scope is kept ("MSA agreements only" → the sentence
      names the MSA); a scoped record never supports "all contracts"; a company
      position is never presented as the reader's agreement
  P10 a figure the selected document states is cited to the document
  V9  explanation (reasoning, next_step, clarify, general) is in the language of the
      user's current message — English to English, Devanagari to Hindi (A-58).
      Presentation, not truth: reported and repaired, never a reason to drop a block
  V10 no internal vocabulary reaches the reader: retrieval signals ("weak hits",
      "non-weak", "gate_open") or evidence keys in the prose ("D1-D5")
  V11 a draft (text the user asked you to write) carries no citation and no internal
      company position; authority, framing and citation rules do not apply to it
  X1  a claim from ANOTHER document (A-65) names that document — it never passes for
      the selected one ("this agreement")
  V12 (owner review 2026-10-04, C1) a statement that relies on an exception or a
      condition keeps whose conduct and which condition the clause names: an exception
      the clause gives for the Customer's conduct is never the provider's; a rule the
      clause states "arising from …" is never stated without that condition
  V4R a lead or summary sentence stating what a document provides is checked against
      the answer's cited clauses like a sourced claim: a contradiction fails it
  V13 no certainty the evidence does not give ("we are certain", "definitely")
  V14 when a company position and the governing document state different figures for
      the same measure, the answer states both (answer-level: repaired, never cut)
  F12 an unsigned selected document is never called signed or executed (plan 1.15) —
      the reader's own claim, attributed, and a conditional or negated sentence are not
      a label
  P1  with a document selected, what it says reaches the reader through a block that
      cites it: a reasoning or general sentence stating the document's content, in an
      answer where no sourced block cites the document, is a violation (an absence —
      "the document does not state…" — is a plain statement, never one)
  P5  the assessment is computed, not taken: `supported`/`contradicted` need a verified
      sourced block on non-weak evidence; `n/a` when the user asserted nothing

Every rule is about the block's relation to its evidence — no answer is special-cased.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from legalmind.assist import guardrails, query_plan

ANSWERING = {"sourced", "user_stated", "reasoning", "general", "draft"}
MAX_CITES = 2
GENERAL_LABEL = "General explanation, not a company position"
DRAFT_LABEL = "Draft for review — not approved company wording"
# A draft the user will send must not carry the company's internal positions (spec v2,
# C1.5: "no internal positions quoted").
_INTERNAL_POSITION = re.compile(
    r"\b(?:company|our|internal)\s+(?:position|standard|policy)|\bconstitution\b", re.I)
NO_DOCUMENT_NOTE = "This answer does not cite a clause of the selected document."
_NOTES = {
    "searched": {"en": "Searched in this turn: {}.",
                 "hinglish": "Is turn mein search kiya: {}.",
                 "hi": "इस बार खोजा गया: {}।"},
    # the floor's one line (owner, 2026-10-05): transparent, short, no internal wording
    "floor": {"en": "I couldn't write a full explanation just now. The clause that "
                    "answers this most directly is quoted below.",
              "hinglish": "Abhi poora explanation nahi likh paya. Jo clause is sawaal "
                          "ka sabse seedha jawab deta hai, wo neeche quote hai.",
              "hi": "अभी पूरा explanation नहीं लिख पाया। जो clause इस सवाल का सबसे सीधा "
                    "जवाब देता है, वह नीचे quote है।"},
    "floor_empty": {"en": "I couldn't answer that just now. Please ask again in a "
                          "moment.",
                    "hinglish": "Abhi iska jawab nahi de paya. Thodi der mein phir "
                                "poochiye.",
                    "hi": "अभी इसका जवाब नहीं दे पाया। थोड़ी देर में फिर पूछिए।"},
    "no_document": {"en": NO_DOCUMENT_NOTE,
                    "hinglish": "Yeh answer selected document ke kisi clause ko cite "
                                "nahi karta.",
                    "hi": "यह उत्तर चयनित दस्तावेज़ के किसी clause का हवाला नहीं देता।"},
}


_ABSENCE = re.compile(r"\b(?:no|not|nahi|nahin|lacks?|absent|missing|without)\b"
                      r".{0,60}\b(?:clause|provision|term|terms|precedence|mention|state[sd]?|"
                      r"specif\w*|contain\w*|include\w*|found)\b", re.I)


def searched_line(blocks: list[dict], searches: list[tuple[str, str]],
                  language: str = "en") -> str | None:
    """"What was searched", in code (owner review 2026-10-04, C3.2/C3.5): when the
    answer says something is absent, the turn's own searches are named."""
    if not any(b["kind"] in ANSWERING and _ABSENCE.search(b["text"]) for b in blocks):
        return None
    queries = list(dict.fromkeys(q for tool, q in searches
                                 if q and tool not in {"find_documents", "ask_user"}))
    if not queries:
        return None
    shown = ", ".join(f"\u201c{q[:70]}\u201d" for q in queries[:4])
    return note("searched", language).format(shown)


def note(name: str, language: str = "en") -> str:
    """A fixed line in the language of the user's message (V9's rule for code too)."""
    return _NOTES[name].get(language, _NOTES[name]["en"])


DIFFERENT_FIGURES = ("a company position and the governing document state different "
                     "figures for the same measure — state both, name the difference "
                     "and say which applies")

_INLINE = re.compile(r"\s*\[\s*([CPSHDU]\d{1,3}(?:\s*[,;]\s*[CPSHDU]\d{1,3})*)\s*\]")
_KEY = re.compile(r"[CPSHDU]\d{1,3}")
_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
                 "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
                 "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
                 "thirty": "30", "forty": "40", "forty-five": "45", "sixty": "60",
                 "ninety": "90", "hundred": "100"}
_FIGURE = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*(%|percent|per cent)?|\b(" + "|".join(
    sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")\b", re.I)
_NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|without|exclude[sd]?|"
                       r"excluding|cannot|can't|won't|shall not|must not|may not)\b",
                       re.I)
_AUTHORITY = re.compile(
    r"\b(?:(?:the|our) constitution (?:says|states|provides|requires)|our (?:policy|"
    r"position|standard) (?:is|requires|says|states)|company "
    r"(?:standard|position|policy) "
    r"(?:requires|says|states|provides|is)|as per (?:our|the company'?s?) (?:standards?|"
    r"policy|position)|the (?:msa|agreement|contract|nda|sla) (?:provides|states|says|"
    r"requires)|under (?:our|the company'?s?) (?:standard|policy|position))\b", re.I)
_ATTRIBUTION = re.compile(r"\b(?:your|you|the (?:email|message|note|paste|material|"
                          r"customer|client|user|text|attachment)|states?|says?|"
                          r"claims?|writes?|according to|mentions?)\b", re.I)
_CONCLUSION = re.compile(
    r"\b(?:is|are|would be|will be|becomes?) (?:not )?(?:liable|enforceable|"
    r"unenforceable|void|binding|in breach|barred|uncapped|unlimited|excluded)|bars? "
    r"recovery|uncapped (?:risk|liability|exposure)|unlimited (?:liability|exposure)|"
    r"(?:excluded|barred) altogether|cannot (?:recover|claim|sue)|no liability (?:at all|"
    r"whatsoever)|has no (?:claim|remedy)\b", re.I)
_CONDITIONAL = re.compile(r"\b(?:if|unless|on the facts|on these facts|assuming|"
                          r"subject to|would|could|may|might|likely|depends|provided "
                          r"that|where|as described|appears?|seems?)\b", re.I)
_ALL_CONTRACTS = re.compile(r"\b(?:all|every|any|each) (?:contracts?|agreements?|"
                            r"customers?|deals?)\b", re.I)
_AS_AGREEMENT = re.compile(r"\b(?:the|this|your) (?:msa|agreement|contract)\b[^.]{0,30}"
                           r"\b(?:states?|provides?|says?|requires?|caps?|excludes?)\b",
                           re.I)
_ABOUT_DOCUMENT = re.compile(
    r"\b(?:(?:selected|draft|this|is|iss|yeh|ye) (?:draft )?(?:document|agreement|"
    r"contract|msa|sla|nda|clause)|draft (?:document|agreement|clause))\b", re.I)
_CALLED_EXECUTED = re.compile(
    r"\b(?:(?:this|the|selected|yeh|ye|is)\s+(?:selected\s+)?(?:draft\s+)?(?:agreement|"
    r"document|contract|msa|sla|nda)\s+(?:is|was|has been|hai|ho chuka hai)\s+"
    r"(?:already\s+|fully\s+|duly\s+)?(?:signed|executed)|(?:this|the selected)\s+"
    r"(?:signed|executed)\s+(?:agreement|document|contract|msa|sla|nda)|"
    # romanised Hindi order: "yeh agreement (already) signed hai / ho chuka hai"
    r"(?:yeh|ye|is)\s+(?:agreement|document|contract|msa|sla|nda)\s+(?:already\s+|"
    r"fully\s+)?(?:signed|executed)\s+(?:hai|ho chuka hai|ho gaya hai))\b", re.I)
_NOT_A_LABEL = re.compile(
    r"\b(?:if|whether|unless|once|until|agar|yadi|verify|confirm|you (?:say|state|said|"
    r"stated|mention)|the user states?|according to you|your (?:statement|correction))\b",
    re.I)
_INTERNAL = re.compile(
    r"\b(?:weak|unweakened|non-weak)\s+(?:hits?|records?|results?|evidence|excerpts?|"
    r"matches?)\b|\bunweakened\b|\bnon-weak\b|\bevidence_id\b|\bgate_open\b|\b(?:"
    r"records?|results?|hits?)\s+(?:were|are|was|is)\s+(?:marked\s+)?weak\b|"
    r"\bweak\s+mark|\b[CPSHDU]\d{1,3}\s*[-\u2013]\s*[CPSHDU]?\d{1,3}\b", re.I)
_BARE_KEY = re.compile(r"\b[CPSHDU]\d{1,3}\b")
# ponytail: a phrase list — catches instructions addressed to the assistant in the usual
# wording; a paraphrased injection still meets the verifier (V5/V6), which is what
# keeps it out of the answer. Widen the list when a missed phrasing is seen.
_INSTRUCTION = re.compile(
    r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+|the\s+)?(?:previous|"
    r"prior|earlier|above|preceding|your)\s+(?:instructions?|rules?|prompts?|guidelines?)"
    r"|\b(?:note|message|instructions?)\s+(?:to|for)\s+(?:the\s+)?(?:assistant|ai|"
    r"model|chatbot|bot|llm)\b|\bsystem prompt\b|\byou are now\b", re.I)
INJECTION_NOTE = ("Your material contains text addressed to the assistant (\"{}\"). I "
                  "treated it as part of the material and did not follow it; the answer "
                  "rests only on the cited sources.")
_ABSENT = re.compile(r"\bnah[iī]n?\b", re.I)          # romanised नहीं
_SCOPE_WORDS = {"MSA": ("msa", "master services", "master service"),
                "TOS": ("tos", "terms of service", "terms of use"),
                "SLA": ("sla", "service level"), "NDA": ("nda", "non-disclosure",
                                                         "confidentiality agreement"),
                "VENDOR_AGREEMENT": ("vendor",), "PARTNER_AGREEMENT": ("partner",),
                "DISTRIBUTION_AGREEMENT": ("distribution", "distributor"),
                "ORDER_FORM": ("order form", "purchase order"),
                "AMENDMENT": ("amendment", "addendum")}


@dataclass
class Evidence:
    """What the verifier needs to know about one key the turn showed."""
    key: str
    text: str
    location: str | None
    scope: str | None
    weak: bool
    source: str           # constitution · positions · statutes · documents · attachments


@dataclass(frozen=True)
class Violation:
    block: int
    check: str
    detail: str

    def line(self) -> str:
        return f"block {self.block + 1}: {self.check} — {self.detail}"


# --------------------------------------------------------------------------- normalise
def normalise(blocks: list[dict]) -> list[dict]:
    """Inline `[C1, P2]` markers move into the block's cite list (P4: every key in the
    prose is a cited key); cites are de-duplicated in order; text is trimmed. The
    words of the block are never changed otherwise."""
    out = []
    for b in blocks:
        cites = list(b.get("cites") or [])
        text = b.get("text", "")
        for m in _INLINE.finditer(text):
            cites += _KEY.findall(m.group(1))
        text = _INLINE.sub("", text).strip()
        out.append({"kind": b.get("kind"), "text": text,
                    "cites": list(dict.fromkeys(c.strip() for c in cites if c.strip()))})
    return out


_KIND = {"documents": "CONTRACT", "positions": "COMPANY_POSITION",
         "constitution": "COMPANY_POSITION", "statutes": "LAW"}


def _entailed(text: str, known: list[Evidence]) -> str | None:
    """V4 by the shipped claim verifier (`verify.judge`, `AM-90`): the local NLI model
    reads each sentence against the cited records under their kinds' frames. SUPPORTED
    only when every sentence is; CONTRADICTED when any is; None when the model is not
    available (the lexical rule then decides alone). Nothing leaves the machine."""
    from legalmind.assist import verify
    kinds = [("HISTORICAL_EXCEPTION" if e.key.startswith("H")
              else _KIND.get(e.source, "CONTRACT")) for e in known]
    marks = "".join(f"[{n}]" for n in range(1, len(known) + 1))
    verdicts = []
    for sent in (x.strip() for x in guardrails._SENTENCES.split(text) if x.strip()):
        j = verify.judge(f"{sent} {marks}", [e.text for e in known], kinds,
                         [""] * len(known))
        if j.reason == "verifier unavailable":
            return None
        verdicts.append(j.verdict)
    if "CONTRADICTED" in verdicts:
        return "CONTRADICTED"
    return "SUPPORTED" if verdicts and all(x == "SUPPORTED" for x in verdicts) else \
        "UNSUPPORTED"


def _overlap_words(text: str) -> set[str]:
    """Content words for V4's lexical share, with a contract's spellings made
    comparable (A-83): "six (6) month" is "6 month", "6-month" is "6 month", a blank
    ("__________ months") is "blank" — F1.1's true "17.2 provides a 6-month cap; 17.7
    leaves the period blank" shared a third of its words with the clauses."""
    text = re.sub(r"_{3,}", " blank ", text)
    for word, digit in sorted(_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf"\b{word}\b\s*(?:\(\s*\d+\s*\))?", f"{digit} ", text, flags=re.I)
    words = guardrails._content_words(re.sub(r"(\d)-(?=[a-z])", r"\1 ", text, flags=re.I))
    return {w.rstrip(".,") for w in words}            # "17.2." heading is "17.2"


def _figures(text: str) -> set[str]:
    found = set()
    for m in _FIGURE.finditer(text or ""):
        if m.group(1):
            found.add(m.group(1).replace(",", ""))
        elif m.group(3):
            found.add(_NUMBER_WORDS[m.group(3).lower()])
    return found


def _scope_type(scope: str | None) -> str | None:
    if scope and scope.endswith(" agreements only"):
        return scope[: -len(" agreements only")]
    return None


# ------------------------------------------------------------------------------ verify
def verify(blocks: list[dict], shown: dict[str, Evidence], *,
           document_selected: bool, assessment: str,
           doc_cited: bool | None = None,
           document_executed: bool = False,
           reply_language: str | None = None,
           instruments: frozenset[str] = frozenset(),
           answer: list[dict] | None = None) -> list[Violation]:
    """Every violation, block by block. `shown` is every key the turn showed.
    `doc_cited` — does the WHOLE answer cite the selected document — is computed from
    `blocks` unless given (`settle` re-verifies one block at a time)."""
    v: list[Violation] = []
    answering = any(b["kind"] in ANSWERING for b in blocks)
    clarify = [i for i, b in enumerate(blocks) if b["kind"] == "clarify"]
    for i in clarify[1:]:
        v.append(Violation(i, "V8", "more than one clarifying question"))
    if clarify and answering and assessment != "undeterminable":
        v.append(Violation(clarify[0], "V8", "a clarifying question beside an answer — "
                                             "ask only when the answer would change"))
    doc_texts = [e.text for e in shown.values() if _selected(e)]
    if doc_cited is None:
        doc_cited = cites_document(blocks, shown)
    for i, b in enumerate(blocks):
        kind, text, cites = b["kind"], b["text"], b["cites"]
        if _INTERNAL.search(text) or set(_BARE_KEY.findall(text)) & set(shown):
            v.append(Violation(i, "V10", "internal vocabulary or evidence keys in the "
                                         "prose — say it in the reader's words"))
        if (document_selected and not document_executed and kind != "user_stated"
                and calls_executed(text)):
            v.append(Violation(i, "F12", "calls the selected document signed or "
                                         "executed; it is recorded as draft or unsigned"))
        unknown = [c for c in cites if c not in shown]
        if unknown:
            v.append(Violation(i, "V1", f"cites {unknown} that this turn never showed"))
        known = [shown[c] for c in cites if c in shown]
        if kind == "sourced":
            if not known:
                v.append(Violation(i, "V1", "a sourced claim with no shown citation"))
                continue
            if len(cites) > MAX_CITES:
                v.append(Violation(i, "P4", f"{len(cites)} citations for one claim; "
                                            f"use the one or two that state it"))
            for e in known:
                if e.source != "attachments" and not e.location:
                    v.append(Violation(i, "P4", f"{e.key} has no location to cite"))
            cited_text = " ".join(e.text for e in known)
            missing = _figures(text) - _figures(cited_text)
            if missing:
                v.append(Violation(i, "V2", f"figures {sorted(missing)} are not in "
                                            f"{[e.key for e in known]}"))
            if _NEGATION.search(text) and not _NEGATION.search(cited_text):
                v.append(Violation(i, "V3", "the claim negates; its source does not"))
            verdict = _entailed(text, known)
            words = _overlap_words(text)
            lexical = not words or len(words & _overlap_words(cited_text)) \
                >= 0.5 * len(words)
            if verdict == "CONTRADICTED":
                v.append(Violation(i, "V4", "its source contradicts the claim"))
            elif verdict != "SUPPORTED" and not lexical:
                v.append(Violation(i, "V4", "the claim says more than its source"))
            # B5 (A-80): a weak record is a ranking signal, not falsehood. The gate stays
            # only for corpus-wide semantic-only hits; a document record (selected or
            # named, searched by version) or a lexical match is held to V4 alone.
            if all(e.weak and e.source != "documents" for e in known) and not lexical:
                v.append(Violation(i, "B5", "cites only weak corpus-wide evidence"))
            for e in known:
                t = _scope_type(e.scope)
                if t and not any(w in text.lower() for w in _SCOPE_WORDS.get(
                        t, (t.lower().replace("_", " "),))):
                    v.append(Violation(i, "P2", f"{e.key} applies to {e.scope}; the "
                                                f"sentence drops that scope"))
                if t and _ALL_CONTRACTS.search(text):
                    v.append(Violation(i, "P2", f"{e.key} applies to {e.scope}, not to "
                                                f"every contract"))
                if (t and instruments and t not in instruments
                        and e.source in {"positions", "constitution"}):
                    v.append(Violation(i, "P2", f"{e.key} applies to {e.scope}; this "
                                                f"conversation concerns "
                                                f"{', '.join(sorted(instruments))}"))
            if (not any(_selected(e) for e in known)
                    and _AS_AGREEMENT.search(text)):
                v.append(Violation(i, "P2", "a company source presented as the reader's "
                                            "agreement"))
            others = [e for e in known if _other(e)]
            if others and not any(_selected(e) for e in known) and not any(
                    _names(e, text) for e in others):
                v.append(Violation(i, "X1", f"{others[0].key} is {others[0].scope}; the "
                                            f"sentence must name that document"))
            if document_selected and not any(_selected(e) for e in known):
                in_doc = {f for f in _figures(text)
                          if any(f in _figures(d) for d in doc_texts)}
                # a sentence that names itself the company position is stating it
                # ("same as our MSA?" needs the standard's 12 months — A-83)
                if in_doc and in_doc <= _figures(cited_text) and any(
                        e.source in {"constitution", "positions"} for e in known) \
                        and not _COMPANY_WORDS.search(text):
                    v.append(Violation(i, "P10", f"figures {sorted(in_doc)} are stated "
                                                 f"in the selected document — cite it"))
        elif kind == "user_stated":
            if len(cites) > MAX_CITES:
                v.append(Violation(i, "P4", f"{len(cites)} citations for one claim; "
                                            f"use the one or two that state it"))
            if any(e.source != "attachments" for e in known):
                v.append(Violation(i, "V6", "user_stated cites a non-user source"))
            if not _ATTRIBUTION.search(text):
                v.append(Violation(i, "V6", "user material not attributed"))
        else:
            written = query_plan.language(text) if reply_language else None
            if (reply_language == "en" and written != "en") or (
                    reply_language == "hi" and written != "hi"):
                v.append(Violation(i, "V9", f"written in {written}; the user wrote "
                                            f"{reply_language} — reply in that language"))
            if kind in {"general", "draft"} and cites:
                v.append(Violation(i, "V5", f"a {kind} block carries citations"))
            if kind == "draft":
                # Text the user will send, not a claim to them: authority, framing and
                # citation rules do not apply; internal positions never appear in it.
                if _INTERNAL_POSITION.search(text):
                    v.append(Violation(i, "V11", "a draft quotes an internal company "
                                                 "position"))
                continue
            if not cites and _AUTHORITY.search(text):
                v.append(Violation(i, "V5", "an authority attribution with no citation"))
            if (document_selected and not doc_cited and kind in {"reasoning", "general"}
                    and any(about_document(x) == "states"
                            for x in guardrails._SENTENCES.split(text))):
                v.append(Violation(i, "P1", "states what the selected document says "
                                            "without citing it — make it a sourced "
                                            "block that cites the D record"))
            if kind == "reasoning" and _CONCLUSION.search(text) \
                    and not _CONDITIONAL.search(text):
                v.append(Violation(i, "V7", "a legal conclusion stated without "
                                            "conditional framing"))
    v += _answer_checks(blocks, shown, answer or blocks)
    return v


def _answer_checks(blocks: list[dict], shown: dict[str, Evidence],
                   answer: list[dict]) -> list[Violation]:
    """V12, V4R, V13, V14 — checks that read a block against the whole answer's
    evidence (owner review, 2026-10-04)."""
    v: list[Violation] = []
    documents = [e for e in shown.values() if e.source == "documents"]
    cited = [shown[c] for b in answer for c in b.get("cites") or [] if c in shown]
    cited_docs = [e for e in cited if e.source == "documents"]
    for i, b in enumerate(blocks):
        if b["kind"] in {"user_stated", "draft", "next_step", "prerouted"}:
            continue
        mine = [shown[c] for c in b["cites"] if c in shown] or cited_docs
        for x in guardrails._SENTENCES.split(b["text"]):
            detail = _party_and_condition(x, documents, mine)
            if detail:
                v.append(Violation(i, "V12", detail))
                break
        if _CERTAIN.search(b["text"]):
            v.append(Violation(i, "V13", "certainty the evidence does not give"))
        if b["kind"] in {"reasoning", "general"} and cited_docs:
            for x in guardrails._SENTENCES.split(b["text"]):
                # a sentence about the document alone — one that also speaks of the
                # company's standard is a comparison, not a summary of the document
                if (about_document(x) == "states" or _SAYS_DOCUMENT.search(x)) \
                        and not _COMPANY_WORDS.search(x) \
                        and _entailed(x, cited_docs) == "CONTRADICTED":
                    v.append(Violation(i, "V4R", "a summary of the document its cited "
                                                 "clauses contradict"))
                    break
    # V14: the company figure and the governing document's, for the same measure
    company = _measures(" ".join(e.text for e in cited
                                 if e.source in {"positions", "constitution"}))
    governing = [e for e in shown.values() if e.source == "documents" and not e.weak]
    named = [e for e in governing if _other(e)]
    gov = _measures(" ".join(e.text for e in (named or governing)))
    said = " ".join(b["text"] for b in answer)
    for unit, numbers in company.items():
        theirs = gov.get(unit, set())
        if theirs and numbers - theirs and not (theirs - numbers) & set(_said_figures(
                said)):
            at = next((i for i, b in enumerate(blocks) if any(
                c in shown and shown[c].source in {"positions", "constitution"}
                for c in b["cites"])), 0)
            v.append(Violation(at, "V14", DIFFERENT_FIGURES))
            break
    return v


def _said_figures(text: str) -> set[str]:
    return {n for ns in _measures(text).values() for n in ns}


def instructions_in(shown: dict[str, Evidence]) -> list[str]:
    """G5 / architecture §8: sentences of the user's material, as shown this turn, that
    address the assistant — reported to the reader, never followed."""
    found: list[str] = []
    for e in shown.values():
        if e.source == "attachments":
            found += [" ".join(x.split())[:200]
                      for x in guardrails._SENTENCES.split(e.text)
                      if _INSTRUCTION.search(x)]
    return list(dict.fromkeys(found))


_EXCEPTION = re.compile(r"gross\s+negligence|wil+ful\s+misconduct|\bfraud\b", re.I)
_POSSESSOR = re.compile(r"\b([A-Za-z-]+)(?:'|\u2019)s\b")
_CUSTOMER_SIDE = {"customer", "client", "partner", "licensee", "subscriber"}
_PROVIDER_SIDE = {"leapswitch", "cloudpe", "provider", "company", "supplier", "vendor"}
_LAW = re.compile(r"\b(?:law|statute|statutory|court|public policy|enforceab\w*|"
                  r"non-excludable)\b", re.I)
#: an open question put to counsel ("legal review should consider whether …") states
#: no attribution of a clause's exception; a consequence after it still does (V12)
_FOR_COUNSEL = re.compile(r"\b(?:legal review|counsel|lawyer|legal team)\b[^.;]*"
                          r"\bwhether\b(?![^.;]*\b(?:cap|exclusion|limit\w*)\b"
                          r"[^.;]*\b(?:not|no longer|would|will)\b)", re.I)
_CONDITION = re.compile(r"\b(?:arising (?:out of|from)|caused by|resulting from|due to|"
                        r"attributable to)\b([^.;]{5,200})", re.I)
_FRAGMENT = re.compile(r"[,;:]|\b(?:unless|but|while|whereas|because|however)\b", re.I)
_CERTAIN = re.compile(r"\b(?:we are|we're|i am|i'm)\s+(?:certain|sure|confident)\b|"
                      r"\bdefinitely\b|\bwithout (?:any )?doubt\b|\bno doubt\b", re.I)
_COMPANY_WORDS = re.compile(r"\b(?:company|our|internal)\s+(?:standard|position|policy)|"
                            r"\bconstitution\b|\bstandard\s+position\b", re.I)
_SAYS_DOCUMENT = re.compile(r"\b(?:clause|section)\s+\d|\bunder the (?:selected |draft )?"
                            r"(?:document|agreement|contract|msa|sla)\b", re.I)


def _exception_parties(records: list[Evidence]) -> dict[str, set[str]]:
    """Whose conduct each exception names in the clauses themselves: "the Customer's
    fraud, willful misconduct, or gross negligence" → customer."""
    out: dict[str, set[str]] = {}
    for e in records:
        for m in _EXCEPTION.finditer(e.text):
            owners = _POSSESSOR.findall(e.text[max(0, m.start() - 90):m.start()])
            word = owners[-1].lower() if owners else ""
            if word in _CUSTOMER_SIDE | _PROVIDER_SIDE:
                out.setdefault(m.group(0).lower().split()[0], set()).add(word)
            elif word in {"party", "parties"}:
                out.setdefault(m.group(0).lower().split()[0], set()).add("*")
    return out


def _party_and_condition(sentence: str, documents: list[Evidence],
                         cited: list[Evidence]) -> str | None:
    """V12 for one sentence; the detail, or None."""
    if _LAW.search(sentence) or _FOR_COUNSEL.search(sentence):
        return None
    parties = _exception_parties(documents)
    for m in _EXCEPTION.finditer(sentence):
        owner = parties.get(m.group(0).lower().split()[0], set())
        # The clause names ONE party's conduct (the Customer's, the Partner's): the
        # sentence must name that party too — an exception left unattributed, or given
        # to the other side, misstates the clause (C1.1–C1.4, C1.6).
        if len(owner) == 1 and "*" not in owner and owner <= _CUSTOMER_SIDE \
                and not re.search(rf"\b{next(iter(owner))}", sentence, re.I):
            who = next(iter(owner)).capitalize()
            return (f"the clause gives the {m.group(0).lower()} exception for the "
                    f"{who}'s conduct only — the sentence must keep that party")
    for piece in _FRAGMENT.split(sentence):
        words = guardrails._content_words(piece)
        if len(words) < 3:
            continue
        # the sentence of each cited clause this piece draws on — a condition binds the
        # rule it is written into, not every rule in the same record
        drawn, conditions = [], {}
        for e in cited:
            parts = [x for x in guardrails._SENTENCES.split(e.text) if x.strip()]
            best = max(parts, key=lambda x: len(words & guardrails._content_words(x)),
                       default="")
            if len(words & guardrails._content_words(best)) >= 3:
                drawn.append(e)
                conditions[e.key] = [guardrails._content_words(c.group(1))
                                     for c in _CONDITION.finditer(best)]
        sentence_words = guardrails._content_words(sentence)
        if drawn and all(conditions[e.key] and not any(c & sentence_words
                                                       for c in conditions[e.key])
                         for e in drawn):
            found = _CONDITION.search(" ".join(
                x for x in guardrails._SENTENCES.split(drawn[0].text)
                if _CONDITION.search(x)
                and len(words & guardrails._content_words(x)) >= 3))
            condition = found.group(0)[:80].strip() if found else "its condition"
            return f"states {drawn[0].key}'s rule without its condition (\"{condition}\")"
    return None


_UNIT = re.compile(r"\b(\d+(?:\.\d+)?)[\s-]*(?:\(\s*\d+\s*\)\s*)?"
                   r"(?:calendar\s+|business\s+|working\s+)?(day|month|year|hour)s?\b|"
                   r"\b(\d+(?:\.\d+)?)\s*(%|percent|per cent)", re.I)


def _measures(text: str) -> dict[str, set[str]]:
    """Figures by unit (days, months, years, hours, percent), number words read."""
    for word, digit in sorted(_NUMBER_WORDS.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf"\b{word}\b", digit, text, flags=re.I)
    out: dict[str, set[str]] = {}
    for m in _UNIT.finditer(text):
        n, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), "%")
        out.setdefault(unit.lower() if unit != "%" else "%", set()).add(n)
    return out


INSTRUMENTS = {"MSA", "TOS", "SLA", "NDA", "VENDOR_AGREEMENT", "PARTNER_AGREEMENT",
               "DISTRIBUTION_AGREEMENT", "ORDER_FORM", "AMENDMENT"}


def instruments_in(*texts: str) -> frozenset[str]:
    """The kinds of agreement a conversation is about, read from its words (P2b)."""
    found = set()
    for t in texts:
        low = f" {t.lower()} "
        for kind, words in _SCOPE_WORDS.items():
            if any(re.search(rf"\b{re.escape(w)}\b", low) for w in words):
                found.add(kind)
    return frozenset(found)


_ANOTHER = re.compile(r"\b(?:another|other|separate|second)\s+(?:document|agreement|"
                      r"contract|sla|msa)\b", re.I)


def _names(e: Evidence, text: str) -> bool:
    """Does the sentence name the other document `e` comes from — a distinctive word
    of its name, or plainly "another document"?"""
    from legalmind.assist.tools import name_tokens
    name = (e.scope or "").split(":", 1)[-1]
    return bool(_ANOTHER.search(text)) or any(t in text.lower()
                                               for t in name_tokens(name))


def calls_executed(text: str) -> bool:
    """F12: does a sentence of `text` label the selected document signed or executed —
    not a condition, a negation or the reader's attributed claim?"""
    return any(_CALLED_EXECUTED.search(x) and not _NEGATION.search(x)
               and not _NOT_A_LABEL.search(x) for x in guardrails._SENTENCES.split(text))


SELECTED = "the selected document"


def _selected(e: Evidence) -> bool:
    """A record of the SELECTED document — not of another document the reader named."""
    return e.source == "documents" and (e.scope or SELECTED) == SELECTED


def _other(e: Evidence) -> bool:
    return e.source == "documents" and not _selected(e)


def cites_document(blocks: list[dict], shown: dict[str, Evidence],
                   which=None) -> bool:
    which = which or _selected
    return any(b["kind"] == "sourced" and any(
        c in shown and which(shown[c]) for c in b["cites"]) for b in blocks)


def says_absent(blocks: list[dict]) -> bool:
    """Does the answer say plainly that the selected document does not address it?"""
    return any(about_document(x) == "absent" for b in blocks if b["kind"] in ANSWERING
               for x in guardrails._SENTENCES.split(b["text"]))


def about_document(sentence: str) -> str | None:
    """Does the sentence speak about the selected document — "states" what it says,
    "absent" (it does not say), or None."""
    if not _ABOUT_DOCUMENT.search(sentence):
        return None
    return "absent" if _NEGATION.search(sentence) or _ABSENT.search(sentence) \
        else "states"


def assessment(blocks: list[dict], shown: dict[str, Evidence], *, claim_made: bool,
               proposed: str) -> str:
    """P5: computed, not taken. A claim is assessed only when the user made one; then
    `supported`/`contradicted` need a sourced block citing non-weak evidence."""
    if not claim_made:
        return "n/a"
    grounded = any(b["kind"] == "sourced" and any(
        c in shown and not shown[c].weak for c in b["cites"]) for b in blocks)
    if proposed in {"supported", "contradicted"} and not grounded:
        return "not_established"
    return proposed if proposed in {"supported", "contradicted", "not_established",
                                    "undeterminable"} else "not_established"


# ------------------------------------------------------------- settle after one repair
def settle(blocks: list[dict], shown: dict[str, Evidence], violations: list[Violation],
           *, document_selected: bool = True, document_executed: bool = False
           ) -> tuple[list[dict], int]:
    """What persists after the one repair call (Ask plan 4.2). The deterministic fixes
    come first — a cite with no location removed, too many cites cut to the two that
    best state the claim, an unframed legal conclusion framed — and THEN each block is
    verified again as it now stands: only what still fails is dropped (a scope
    violation that came from a cite the trim removed no longer counts). A question
    flagged V8 is dropped. Returns (blocks, dropped)."""
    flagged: dict[int, set[str]] = {}
    for x in violations:
        flagged.setdefault(x.block, set()).add(x.check)
    kept, dropped = [], 0
    for i, b in enumerate(blocks):
        b = dict(b)
        if "V8" in flagged.get(i, set()):
            dropped += 1
            continue
        if b["kind"] == "sourced":
            # The selected document first (P1), then by how much of the claim each
            # record states; a further cite is kept only if the block still verifies
            # with it, so a cite never turns a sound claim into a violation.
            words = guardrails._content_words(b["text"])
            ranked = sorted(
                (c for c in b["cites"] if c in shown and (
                    shown[c].location or shown[c].source == "attachments")),
                key=lambda c: (not (document_selected and _selected(shown[c])),
                               -len(words & guardrails._content_words(shown[c].text))))
            chosen: list[str] = []
            for c in ranked:
                if len(chosen) == MAX_CITES:
                    break
                trial = {**b, "cites": [*chosen, c]}
                if not chosen or not verify([trial], shown,
                                            document_selected=document_selected,
                                            assessment="n/a", doc_cited=True):
                    chosen.append(c)
            b["cites"] = chosen
        if b["kind"] == "user_stated":
            words = guardrails._content_words(b["text"])
            b["cites"] = sorted((c for c in b["cites"] if c in shown), key=lambda c: -len(
                words & guardrails._content_words(shown[c].text)))[:MAX_CITES]
        if "V7" in flagged.get(i, set()):
            b["text"] = ("On the facts as described, and subject to the signed "
                         "agreement, " + b["text"][:1].lower() + b["text"][1:])
        kept.append(b)
    # Each block again as it now stands, against the whole answer: whether the
    # document is cited anywhere is the answer's property, not the block's. An answer
    # that still cites no document keeps its company claims — they are true; the
    # missing document claim is the repair's to add, and is reported, not dropped.
    def fails(b: dict, whole: bool) -> bool:
        return bool([x for x in verify([b], shown, document_selected=document_selected,
                                       assessment="n/a", doc_cited=whole,
                                       document_executed=document_executed,
                                       answer=kept)
                     if x.check not in {"V8", "V9", "V14"}])
    # Whether the answer cites the document is judged on what SURVIVES: a block citing
    # the document that is itself dropped cites nothing (C5.3 kept an uncited sentence
    # about the SLA because a dropped block had cited it).
    first = [b for b in kept if not fails(b, True)]
    whole = cites_document(first, shown)
    out = [b for b in first if not fails(b, whole)]
    return out, dropped + len(kept) - len(out)


# ------------------------------------------------------------- ladder, floor, renderer
def floor(shown: dict[str, Evidence], *, document_selected: bool, message: str = "",
          language: str = "en", n: int = 2) -> list[dict]:
    """The deterministic floor (Ask plan 4.4; P11): when the model cannot answer, the
    one or two passages that answer the question most directly — the selected document
    first, then company sources — after one short line in the reader's language. Never
    a dump of loosely related clauses, never internal wording (owner, 2026-10-05)."""
    order = (("documents", "attachments", "positions", "constitution", "statutes")
             if document_selected else
             ("positions", "constitution", "statutes", "documents", "attachments"))
    asked = _stems(message)
    # a whole document arrives in document order: rank by the question's words, and
    # never quote a passage that shares none of them (the title page, D1.1/D3.1)
    pool = [e for e in shown.values() if not e.weak and e.text.strip()]
    stems = {e.key: _stems(e.text) for e in pool}
    # a word every clause shares ("agreement") says little; a rare one ("cap") a lot
    weight = {w: math.log((1 + len(pool)) / (1 + sum(w in s for s in stems.values())))
              + 1e-6 for w in asked}
    score = {e.key: sum(weight[w] for w in asked & stems[e.key]) for e in pool}
    ranked = sorted((e for e in pool if not asked or score[e.key] > 0),
                    key=lambda e: (not (document_selected and _selected(e)),
                                   order.index(e.source) if e.source in order else 9,
                                   -score[e.key]))
    best = score[ranked[0].key] if ranked else 0
    strong = [e for e in ranked[:n] if score[e.key] >= 0.7 * best]
    blocks = [{"kind": "next_step", "cites": [],
               "text": note("floor" if strong else "floor_empty", language)}]
    return blocks + [{"kind": "sourced", "text": _quote(e.text, asked), "cites": [e.key]}
                     for e in strong]


def _stems(text: str) -> set[str]:
    """Content words with plural and tense endings cut ("capped" ~ "cap", "months" ~
    "month"), for the floor's ranking only — the verifier's checks stay exact.
    ponytail: crude suffix rules; a real stemmer if the floor ever ranks badly."""
    out = set()
    for w in guardrails._content_words(text):
        w = re.sub(r"ies$", "y", w)
        w = re.sub(r"(?<=\w{3})(?:ed|ing)$", "", w)
        w = re.sub(r"(?<=\w{2})s$", "", w) if not w.endswith("ss") else w
        out.add(re.sub(r"([b-df-hj-np-tv-z])\1$", r"\1", w))
    return out


def _quote(text: str, asked: set[str]) -> str:
    """The record's opening, and — when the question's words sit in a later sentence —
    that sentence too, verbatim, joined by " … " (D2.2: the 10% was in 4.2's second
    sentence and the quote stopped at the first)."""
    lead = _lead(text)
    rest = [x for x in re.split(r"(?<=[.;])\s", " ".join(text.split())[len(lead):])
            if x.strip()]
    best = max(rest, key=lambda x: len(asked & _stems(x)), default="")
    if best and len(asked & _stems(best)) > len(asked & _stems(lead)) // 2:
        return f"{lead} … {best.strip()}"
    return lead


def _lead(text: str, limit: int = 400) -> str:
    """A record's opening sentence(s), verbatim, about `limit` characters — never a
    bare heading ("17.2. Monetary Cap on Liability:" was quoted without its rule)."""
    text = " ".join(text.split())
    out = ""
    for piece in re.split(r"(?<=[.;:])\s", text):
        if len(out) >= 120 and len(out) + len(piece) > limit:
            break
        out = f"{out} {piece}".strip()
    if len(out) > limit + 200:                 # one very long sentence: cut at a word
        out = out[:limit + 200].rsplit(" ", 1)[0] + " …"
    return out


def document_first(blocks: list[dict], shown: dict[str, Evidence]) -> list[dict]:
    """P1: with a document selected, the sourced blocks that cite it come before the
    sourced blocks that cite company sources — reordered among themselves, no word
    changed; when none cites it, the block saying so plainly comes first."""
    slots = [i for i, b in enumerate(blocks) if b["kind"] == "sourced"]
    ordered = sorted((blocks[i] for i in slots), key=lambda b: not any(
        c in shown and _selected(shown[c]) for c in b["cites"]))
    out = list(blocks)
    for i, b in zip(slots, ordered, strict=True):
        out[i] = b
    # No claim cites the document: the sentence saying it does not address the
    # question opens the answer (G11.1), before any company source.
    if not cites_document(out, shown):
        absent = next((b for b in out if b["kind"] in ANSWERING and says_absent([b])),
                      None)
        if absent is not None:
            out.remove(absent)
            out.insert(0, absent)
    return out


def ladder(blocks: list[dict], shown: dict[str, Evidence], *, document_selected: bool,
           message: str = "", language: str = "en") -> tuple[list[dict], str]:
    """The response ladder (Ask plan 4.3): never a bare "not found". L1/L2 when the
    blocks answer; L3 when only a question is left; otherwise the floor's quotes."""
    if any(b["kind"] == "sourced" for b in blocks):
        return blocks, "L1" if not any(b["kind"] == "next_step" for b in blocks) else "L2"
    if any(b["kind"] in ANSWERING for b in blocks):
        return blocks, "L2" if any(b["kind"] != "general" for b in blocks) else "L4"
    if any(b["kind"] == "clarify" for b in blocks):
        return blocks, "L3"
    return floor(shown, document_selected=document_selected, message=message,
                 language=language), "floor"


def render(blocks: list[dict], shown: dict[str, Evidence]) -> str:
    """Natural prose with light labels (Ask plan 4.5): each claim followed once by its
    markers, a general explanation labelled, a question as a plain sentence, and one
    Sources list naming each cited key once with its location and scope."""
    parts, cited = [], []
    merged: list[dict] = []
    for b in blocks:
        # C4.2: consecutive claims resting on the same clauses read as one paragraph
        # with one marker group — never the same citation twice in a row.
        if (merged and b["kind"] == "sourced" and merged[-1]["kind"] == "sourced"
                and b["cites"] and b["cites"] == merged[-1]["cites"]):
            merged[-1] = {**merged[-1], "text": f"{merged[-1]['text']} {b['text']}"}
        else:
            merged.append(b)
    for b in merged:
        text = b["text"]
        if b["kind"] == "general" and not text.startswith(GENERAL_LABEL):
            text = f"{GENERAL_LABEL}: {text}"
        if b["kind"] == "draft" and not text.startswith(DRAFT_LABEL):
            text = f"{DRAFT_LABEL}:\n\n{text}"
        if b["cites"]:
            text = f"{text} [{', '.join(b['cites'])}]"
            cited += [c for c in b["cites"] if c not in cited]
        parts.append(text)
    if cited:
        parts.append("Sources\n\n" + "\n".join(
            f"- {c}: " + (", ".join(x for x in (shown[c].location, shown[c].scope) if x)
                          or ("your material, not a company source"
                              if shown[c].source == "attachments" else "no location"))
            for c in cited if c in shown))
    return "\n\n".join(parts)
