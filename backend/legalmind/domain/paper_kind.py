"""Is this paper a contract or policy at all? — the first layer of classify-then-route.

Anyone can upload a resume, an invoice, a slide deck or a photo. Run through the
contract engine, such a file produces a "review" with nothing applicable that reads
as clean, and `AM-54` recognition would send its paragraphs out for nothing. This
gate reads the parsed text deterministically and says one of three things:

* ``CONTRACT_OR_POLICY`` — a recognised legal title (``title_type``) or clear legal
  structure: parties/recitals, obligation modals, numbered clauses, definitions,
  governing law, an execution block. Statutes are legal paper too.
* ``NOT_A_CONTRACT`` — strong markers of a CV or an invoice/receipt AND no legal
  structure AND no commercial commitment (agreement/order wording, acceptance, a
  term, a price per period, "will provide/pay"). An email, a letter or a slide-like
  shape alone never refuses: OCR lines and table cells look exactly like slides.
* ``UNSURE`` — everything else, including no extractable text (OCR's job, not this
  gate's).

The bias is deliberate: refusing a real contract is the worse error, so one legal or
commitment signal is enough to keep a paper out of ``NOT_A_CONTRACT``. The signals
are recorded for the audit and the log; nothing here is a score, and none is ever
shown to a reader as confidence (rule 12).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from legalmind.domain.document_types import title_type

CONTRACT_OR_POLICY = "CONTRACT_OR_POLICY"
NOT_A_CONTRACT = "NOT_A_CONTRACT"
UNSURE = "UNSURE"


@dataclass(frozen=True)
class PaperKind:
    kind: str
    #: what decided it, for the audit and the log — never rendered as confidence
    signals: tuple[str, ...]


#: Fewer words than this is no text to judge (a scan or a photo): UNSURE.
_MIN_WORDS = 20
#: Obligation modals: at least this many, and this many per 1,000 words.
_MODALS_MIN, _MODALS_PER_1000 = 3, 4.0

_LEGAL = {
    "parties": re.compile(r"\bby and between\b|\bentered into\b|\bhereinafter\b"
                          r"|\bthe parties\b|\beach party\b", re.I),
    "recitals": re.compile(r"\bwhereas\b|\bnow,? therefore\b|\bwitnesseth\b", re.I),
    "definitions": re.compile(r"\bdefinitions\b|[\"“][^\"”]{1,40}[\"”]\s+"
                              r"(?:shall\s+)?means?\b", re.I),
    "governing_law": re.compile(r"\bgoverning law\b|\bgoverned by the laws?\b"
                                r"|\bexclusive jurisdiction\b|\barbitration\b", re.I),
    "execution": re.compile(r"\bin witness whereof\b|\bauthori[sz]ed signatory\b"
                            r"|\bexecuted\b.{0,40}\bagreement\b", re.I),
    "enactment": re.compile(r"\bbe it enacted\b|\bsub-section\b"
                            r"|\bin exercise of the powers\b", re.I),
    "legal_terms": re.compile(r"\bindemnif|\blimitation of liability\b"
                              r"|\bwarrant(?:y|ies)\b|\bterminat(?:e|ion)\b"
                              r"|\bconfidential information\b|\bforce majeure\b", re.I),
}
_MODAL = re.compile(r"\bshall\b|\bagrees? to\b|\bundertakes? to\b|\bis liable\b"
                    r"|\bmust not\b", re.I)

#: A commercial commitment. Any one keeps a paper out of NOT_A_CONTRACT: an email
#: accepting a quotation, an untitled PO, a letter agreement or an OCR'd service order
#: has no contract structure and is still a deal a person must read.
_COMMITMENT = {
    "deal_words": re.compile(r"\bagreements?\b|\bcontracts?\b|\bstatement of work\b"
                             r"|\bscope of work\b|(?<!in )\border\b(?! to\b)", re.I),
    "acceptance": re.compile(r"\baccept(?:s|ed|ance)?\b|\bagree(?:s|d)?\b"
                             r"|\bsign and return\b|\bsignature\b", re.I),
    "term": re.compile(r"\b(?:term|period|validity|valid for)\b[^.\n]{0,40}?"
                       r"\b\d+\s*(?:days?|weeks?|months?|years?)\b", re.I),
    "price_per_period": re.compile(
        r"(?:₹|\bRs\.?|\bINR)\s*\d[\d,]*(?:\.\d+)?[^.\n]{0,40}?"
        r"(?:\bper\b|/\s*(?:month|mo|year|yr|annum)\b|\b\d+\s*(?:months?|years?)\b)",
        re.I),
    "will_commit": re.compile(r"\bwill (?:provide|pay|deliver|supply|render|perform)\b"
                              r"|\bpayable\b|\bbe paid\b|\bpayment will be made\b", re.I),
}

#: Strong evidence a paper is something else — the only markers that can refuse.
_CV_HEADING = re.compile(
    r"^\s*(curriculum vitae|resume|r[ée]sum[ée]|education(?:al qualifications?)?"
    r"|(?:work |professional )?experience|(?:technical |key )?skills"
    r"|(?:career )?objective|professional summary|certifications?|hobbies"
    r"|languages known|personal details|projects|achievements)\s*:?\s*$", re.I)
_CV_PERSONAL = re.compile(r"\bc?gpa\b|\bdate of birth\b|\blinkedin\.com/in/"
                          r"|\bcurriculum vitae\b|\bobjective\b", re.I)
_INVOICE = re.compile(
    r"\b(tax invoice|invoice (?:no|number|#|date)|receipt (?:no|number)|gstin"
    r"|amount due|balance due|bill to|ship to|hsn|sac code|sub-?total|grand total"
    r"|total amount|[cs]gst\b|igst\b|amount in words)", re.I)
_CV_HEADINGS_MIN, _INVOICE_MIN = 3, 4


def _distinct(pattern: re.Pattern[str], lines: list[str]) -> set[str]:
    return {m.group(0).strip().lower().rstrip(":") for line in lines
            for m in pattern.finditer(line)}


def classify_paper(segments) -> PaperKind:
    """Classify parsed segments (anything with ``.content``: a parser Segment, an
    evidence row, a clause). Deterministic: same segments, same answer."""
    segments = list(segments)  # read three times: text, title, numbering
    text = "\n".join(s.content or "" for s in segments)
    words = len(text.split())
    if words < _MIN_WORDS:
        return PaperKind(UNSURE, (f"words:{words}",))

    if titled := title_type(segments):
        return PaperKind(CONTRACT_OR_POLICY, (f"title:{titled}",))

    legal = [name for name, pattern in _LEGAL.items() if pattern.search(text)]
    modals = len(_MODAL.findall(text))
    if modals >= _MODALS_MIN and modals * 1000 / words >= _MODALS_PER_1000:
        legal.append(f"modals:{modals}")
    numbered = sum(1 for s in segments if getattr(s, "section_number", None))
    if numbered >= 3:
        legal.append(f"numbered:{numbered}")
    if len(legal) >= 2:
        return PaperKind(CONTRACT_OR_POLICY, tuple(legal))

    commitment = [name for name, pattern in _COMMITMENT.items() if pattern.search(text)]
    lines = [line for line in text.splitlines() if line.strip()]
    other = []
    headings, personal = _distinct(_CV_HEADING, lines), _distinct(_CV_PERSONAL, lines)
    if len(headings) >= _CV_HEADINGS_MIN and personal:
        other.append(f"cv:{','.join(sorted(headings | personal))}")
    if len(invoice := _distinct(_INVOICE, lines)) >= _INVOICE_MIN:
        other.append(f"invoice:{','.join(sorted(invoice))}")

    if other and not legal and not commitment:
        return PaperKind(NOT_A_CONTRACT, tuple(other))
    return PaperKind(UNSURE, tuple(legal + commitment + other) or (f"words:{words}",))
