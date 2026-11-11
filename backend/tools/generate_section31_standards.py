"""Emit Company Standard files from Legal Constitution L1.10 §31, verbatim — and, since
`AM-322` (2026-11-09), the single-sentence positions of §12, §15 and §31.14 that had no
standard file, from the canonical L1.16 (`POSITIONS` below; L1.15 until AM-322 r14).

WHY A GENERATOR RATHER THAN THIRTY-FIVE HAND-WRITTEN FILES (owner, 2026-09-18).

The owner ruled that everything in the Constitution is ratified: "Any document type,
section, or position that exists in the Constitution is approved and LegalMind must
answer questions about it using that text, with exact section citations… Do NOT hold
anything back as 'subject to legal review', 'industry-practice', 'draft', or
'proposed'." §31.9–§31.12 carry about thirty-five separate positions.

Transcribing thirty-five legal positions by hand is precisely where a paraphrase slips
in, and a paraphrased legal position is rule 7's failure mode wearing a copy-editor's
hat. Generating them makes `source_quote` verbatim BY CONSTRUCTION — the text is sliced
out of the Constitution, never retyped — and makes the provenance of every file
reproducible: re-run this and the same files come back.

WHAT THIS TOOL DOES NOT DECIDE.

* It never writes a position. `source_quote` is the Constitution's own sentence.
* It never invents a number. Nothing here parses or emits a numeric threshold; every
  standard it writes is PRESENCE, because §31.9–§31.12 state qualitative expectations.
  A numeric position in §31 (§31.3's 30 days) is hand-written and calibrated instead.
* It never grades the text. `constitution.basis` is read from the Constitution's own
  "Company-approved" / "LegalMind Rule" marking — `COMPANY_APPROVED` where it says so,
  `LEGALMIND_RULE` otherwise. `AM-72` r4 and the owner's 2026-09-18 ruling agree on
  this: the grade records PROVENANCE and never suppresses an answer. Ratified means it
  answers; the basis says where the position came from.
* **It never emits §31.6a.** The Constitution says that section "is NOT a current
  company position", "must not be presented to LegalMind… as an existing company
  position", and that LegalMind "must NOT flag the absence of an L1/L2/L3 structure as
  a deviation in any document". The owner's 2026-09-18 ruling carves it out explicitly.
  `_SKIP_SECTIONS` enforces it, and a test pins that no ratified standard carries it.

The mapping terms ARE this tool's own work, derived from each position's own QUOTE (and
its heading as a fallback). They are an implementation detail and are uncalibrated
against counterparty paper — every generated file says so (`AM-72` r6, 35.10, rule 21).

They are not arbitrary, though: `tools.verify_terminology` requires every standard to
find the very clause it cites, so terminology that cannot reproduce its own Constitution
section fails CI job 12. A first pass used heading words alone, scored 3 against the
threshold of 5, and failed all 34 — a standard that cannot find its own source clause
can never produce a Finding.

    python -m tools.generate_section31_standards            # write the files
    python -m tools.generate_section31_standards --check     # CI: fail if stale
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from legalmind.assist.knowledge.positions import RATIFIED_STANDARDS_DIR

CONSTITUTION = (Path(__file__).resolve().parents[2]
                / "docs" / "02-legal-domain" / "LEGAL_CONSTITUTION_L1.10.md")

#: The Constitution disclaims this section in its own words. Never ratified.
_SKIP_SECTIONS = frozenset({"31.6a"})

#: Which §31 sections this tool owns, and the document type each governs.
#: `table` sections state their positions as a markdown table; `rules` sections as
#: `### heading` + a "LegalMind Rule" paragraph.
SECTIONS: dict[str, dict] = {
    "31.9": {"document_type": "VENDOR_AGREEMENT", "shape": "rules"},
    "31.10": {"document_type": "DISTRIBUTION_AGREEMENT", "shape": "rules"},
    "31.11": {"document_type": "ORDER_FORM", "shape": "table"},
    "31.12": {"document_type": "AMENDMENT", "shape": "table"},
}

#: Appendix B clause categories, matched on the position's heading. Appendix B has no
#: category for several §31 subjects (non-circumvention, territory, subcontractors), so
#: those fall back to the section's own heading — a routing label, never a position.
_TOPICS: tuple[tuple[str, str], ...] = (
    ("liability", "Liability"),
    ("indemnif", "Indemnification"),
    ("service level", "SLA / Service Levels"),
    ("data protection", "Data Protection & Privacy"),
    ("security", "Data Protection & Privacy"),
    ("confidential", "Confidentiality & Intellectual Property"),
    ("intellectual property", "Confidentiality & Intellectual Property"),
    ("trademark", "Confidentiality & Intellectual Property"),
    ("payment", "Payment Terms & Taxes"),
    ("pricing", "Payment Terms & Taxes"),
    ("termination", "Termination & Suspension"),
    ("governing law", "Governing Law & Dispute Resolution"),
    ("precedence", "Orders / Purchase Orders / Order Forms"),
    ("acceptance", "Orders / Purchase Orders / Order Forms"),
)

_STOPWORDS = frozenset({
    "and", "or", "the", "a", "an", "of", "to", "with", "for", "in", "on", "by",
    "vs", "what", "can", "be", "is", "when", "each", "its", "their",
})


#: Headings whose significant words make a useless code. "What can be changed" reduces
#: to CHANGED and "When required" to REQUIRED — neither says what the position is.
#: §31.11 positions whose SHAPE is more than presence (2026-10-23, the first real PO):
#: "By reference to the governing MSA … — not restated independently" holds only where
#: the PO's own section on the topic points to the MSA; "Every PO should explicitly
#: reference the MSA" holds where the document names it anywhere. Every word is the
#: Constitution's own: the topic is the position's element, the reference is "the MSA"
#: (and "NDA", which §31.11 names beside it for confidentiality).
_MSA = ["master services agreement", "master service agreement", "msa"]
_POSITION_FORMS: dict[str, dict] = {
    "PAYMENT-TERMS-ORDER_FORM-001": {
        "form": "BY_REFERENCE", "topic_headings": ["payment"], "refers_to": _MSA},
    "CONFIDENTIALITY-DATA-PROTECTION-ORDER_FORM-001": {
        "form": "BY_REFERENCE", "topic_headings": ["confidentiality", "data protection"],
        "refers_to": [*_MSA, "non-disclosure agreement", "nda"]},
    "REFERENCE-GOVERNING-MSA-ORDER_FORM-001": {
        "form": "NAMES_DOCUMENT", "refers_to": _MSA},
}

_CODE_OVERRIDES: dict[str, str] = {
    "When required": "AMENDMENT-WHEN-REQUIRED",
    "What can be changed": "AMENDMENT-LIMITED-SCOPE",
}


#: The Constitution is Markdown, and its converter escaped punctuation inside prose —
#: "(Section 16\)" rather than "(Section 16)". That backslash is a rendering artifact of
#: the FILE, not a character of the position, and a reader shown the raw quote sees
#: "Section 16\)". Un-escaping recovers the sentence the Constitution actually states; it
#: is the opposite of altering the quote, and is the only transform applied to it.
_MD_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|&])")


def _unescape(text: str) -> str:
    return _MD_ESCAPE.sub(r"\1", text)


def _slug(heading: str, *, words: int = 3) -> str:
    """`Security, Data Protection & Confidentiality` -> `SECURITY-DATA-PROTECTION`."""
    if heading in _CODE_OVERRIDES:
        return _CODE_OVERRIDES[heading]
    tokens = [t for t in re.split(r"[^A-Za-z0-9]+", heading) if t]
    kept = [t.upper() for t in tokens if t.lower() not in _STOPWORDS][:words]
    return "-".join(kept) or "POSITION"


#: Words too common in legal prose to distinguish one position from another. "LegalMind
#: Rule" is the worst of them: it prefixes EVERY §31.9/§31.10 sub-rule, so using it would
#: map every standard to every clause in its section.
_FILLER = frozenset({
    "legalmind", "rule", "should", "shall", "must", "will", "would", "may", "party",
    "parties", "agreement", "agreements", "company", "section", "constitution",
    "this", "that", "where", "which", "there", "here", "such", "from", "into", "than",
    "been", "being", "have", "has", "had", "are", "was", "were", "not", "any", "all",
    "other", "otherwise", "unless", "under", "over", "also", "both", "each", "more",
    "less", "own", "per", "position", "positions", "applied", "applicable",
})


def _content_words(text: str) -> list[str]:
    """Distinctive lower-cased words of a position, in order, de-duplicated."""
    stripped = re.sub(r"^LegalMind Rule[^:]*:\s*", "", text)
    out: list[str] = []
    seen: set[str] = set()
    for word in (w.lower() for w in re.findall(r"[A-Za-z][A-Za-z-]{3,}", stripped)):
        if word in _FILLER or word in _STOPWORDS or word in seen:
            continue
        seen.add(word)
        out.append(word)
    return out


def _phrase(text: str) -> str:
    """The first run of three distinctive words that are ADJACENT IN THE TEXT.

    Adjacency is the whole point, and getting it wrong is silent.
    `scoring.contains_phrase` matches the phrase as a literal on word boundaries, so a
    phrase rebuilt from tokens scores zero the moment punctuation sat between them:
    "liability should be capped, structured consistently" yielded the alias "capped
    structured consistently", which appears nowhere, and nineteen standards scored 3
    instead of 6. So the words must be separated by a single space in the source, and
    the returned string is the source's own span.
    """
    stripped = re.sub(r"^LegalMind Rule[^:]*:\s*", "", text)
    matches = list(re.finditer(r"[A-Za-z][A-Za-z-]*", stripped))
    # Three adjacent words first, then two. A short position — "Must be signed by an
    # authorized representative of each party" — has no three distinctive words in a
    # row and only three in total, so it could reach neither a second keyword group nor
    # a three-word alias. "authorized representative" is still a phrase from the text.
    for width in (3, 2):
        for i in range(len(matches) - width + 1):
            run = matches[i:i + width]
            # Adjacent means exactly one space between each pair — no comma, no bracket.
            if any(stripped[run[k].end():run[k + 1].start()] != " "
                   for k in range(width - 1)):
                continue
            if all(m.group().lower() not in _FILLER
                   and m.group().lower() not in _STOPWORDS
                   and len(m.group()) > 3 for m in run):
                return stripped[run[0].start():run[-1].end()].lower()
    return ""




def _description(heading: str, quote: str) -> str:
    """A one-line label that actually says what the position is.

    THE DESCRIPTION IS A RETRIEVAL SURFACE, not decoration. The first pass wrote
    "<heading> — the Constitution's position for this document type." for all 34, so 33
    of the 34 words were identical and only the heading discriminated: nine positions
    could not be found from their own description, measured by
    `test_every_ratified_position_is_still_reachable_by_its_own_description`.

    Built from the position's own first sentence, so it carries that position's words.
    NO DIGITS: `test_no_description_states_the_standards_value` forbids them, because a
    description is a label and must never restate the standard's VALUE — where the
    sentence carries a figure, the heading alone is used rather than a doctored
    sentence.
    """
    sentence = re.sub(r"^LegalMind Rule[^:]*:\s*", "", quote).split(". ")[0].strip(" .")
    # A "(Section 16)" cross-reference is a POINTER, never this standard's value, but the
    # digit guard cannot tell them apart — so drop the pointer from the LABEL rather than
    # lose the sentence to boilerplate. `source_quote` keeps it, verbatim and untouched.
    sentence = re.sub(r"\s*\((?:Sections?|see)\s+[^)]*\)", "", sentence).strip(" .,;")
    if not sentence or re.search(r"\d", sentence):
        return f"{heading} — the Constitution's position for this document type."
    sentence = sentence[0].lower() + sentence[1:]
    # `test_every_ratified_standard_has_a_one_sentence_description` caps a description at
    # 200 characters. Shorten at a CLAUSE boundary rather than slicing, which left
    # "…consistent in structure with the Constitution's general Indemnification position"
    # cut mid-thought. A description is read by a person; a truncated one is worse than a
    # shorter true one.
    for candidate in (sentence, *(sentence.split(";")[0], sentence.split(",")[0])):
        line = f"{heading} — {candidate.strip(' ,;')}."
        if len(line) <= 200:
            return line
    return f"{heading} — the Constitution's position for this document type."


def _topic(heading: str, section: str, fallback_heading: str) -> str:
    lowered = heading.lower()
    for needle, topic in _TOPICS:
        if needle in lowered:
            return topic
    return f"Section {section} — {fallback_heading}"


def _basis(status_text: str) -> str:
    """The Constitution's own marking. `COMPANY_APPROVED` only where it says so."""
    return ("COMPANY_APPROVED" if "company-approved" in status_text.lower()
            else "LEGALMIND_RULE")


def _section_body(text: str, section: str) -> str:
    """Everything under `## **<section> ...**` up to the next `## ` heading."""
    start = re.search(rf"^## \*\*{re.escape(section)} [^\n]*\*\*\s*$", text, re.M)
    if not start:
        raise SystemExit(f"section {section} not found in {CONSTITUTION.name}")
    rest = text[start.end():]
    nxt = re.search(r"^## ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def _parse_rules(body: str) -> list[tuple[str, str, str]]:
    """`### **Heading**` + its `LegalMind Rule…` paragraph -> (heading, quote, status)."""
    out: list[tuple[str, str, str]] = []
    parts = re.split(r"^### \*\*(.+?)\*\*\s*$", body, flags=re.M)
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        for para in (p.strip() for p in parts[i + 1].split("\n\n")):
            if para.startswith("LegalMind Rule"):
                # These sections carry one STATUS line for the whole section, and it
                # never says "Company-approved" — hence LEGALMIND_RULE throughout.
                out.append(
                    (heading, _unescape(re.sub(r"\s+", " ", para)), "LegalMind Rule"))
                break
    return out


def _parse_table(body: str) -> list[tuple[str, str, str]]:
    """`| Element | Standard Position | Status |` -> (element, position, status)."""
    out: list[tuple[str, str, str]] = []
    for line in body.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 3 or set(cells[0]) <= {":", "-"} or not cells[1]:
            continue
        if cells[0].lower() in ("element", "po element"):
            continue
        out.append((cells[0], _unescape(re.sub(r"\s+", " ", cells[1])), cells[2]))
    return out


def _standard(*, section: str, document_type: str, heading: str, quote: str,
              status: str, section_heading: str) -> tuple[str, dict]:
    code = f"{_slug(heading)}-{document_type}-001"
    terms = [t.lower() for t in re.split(r"[^A-Za-z0-9]+", heading)
             if t and t.lower() not in _STOPWORDS]
    quote_terms = _content_words(quote)
    payload = {
        "_about": [
            "RATIFIED Company Standard — approved THROUGH THE LEGAL CONSTITUTION L1.10.",
            "Owner ruling 2026-09-18: everything in the Constitution is ratified; a",
            "document type, section or position that exists there is the organization's",
            "official position and must answer with exact section citations.",
            "GENERATED by tools/generate_section31_standards.py — `source_quote` is",
            "sliced from the section verbatim, never retyped (rules 7, 21).",
        ],
        "requirement_code": code,
        "description": _description(heading, quote),
        "ratified": "2026-09-18",
        "approval": {
            "basis": "CONSTITUTION",
            "section": section,
            "ruling": ("owner, 2026-09-18 — everything in the Constitution is ratified; "
                       "this standard restates the cited position without changing it"),
            "calibration": ("35.10 — NOT calibrated against counterparty paper. The "
                            "mapping terms are derived from the position's own heading "
                            "and must be re-calibrated when a document of this type is "
                            "supplied (rule 21)."),
        },
        "source_document": ("Legal Constitution, Lawyer Review Version L1.10 — "
                            "docs/02-legal-domain/LEGAL_CONSTITUTION_L1.10.md"),
        "source_clause": f"§{section}",
        "source_quote": quote,
        "configuration": {
            "document_type": document_type,
            "constitution": {
                "version": "L1.10",
                "section": section,
                "topic": _topic(heading, section, section_heading),
                "basis": _basis(status),
            },
            "expected_presence": "PRESENT",
            "scope_key": _slug(heading, words=4).replace("-", "_"),
            "applicability": "REQUIRED",
            **_POSITION_FORMS.get(code, {}),
        },
        "evaluator_type": "PRESENCE",
        "evaluation_rules": {
            "evaluator": "PRESENCE",
            "_note": "presence is established by the mapping layer alone (45D)",
        },
        # THE TERMS COME FROM THE POSITION'S OWN QUOTE, NOT ITS HEADING.
        #
        # A first pass used heading words alone and every generated standard scored 3
        # against the very Constitution section it cites — below the confirm threshold
        # of 5 — so `tools.verify_terminology` failed all 34: a standard that cannot
        # find its own source clause can never produce a Finding. Caught by CI job 12,
        # which exists for exactly this (an invariant re-checked by a different
        # mechanism from the unit tests).
        #
        # One alias (3) plus one keyword group (3) clears the threshold at 6, and both
        # are drawn from the quote, so each reproduces its own section by construction.
        # `exact_phrases` stays EMPTY: a 5-point phrase is the mapper's strongest claim
        # and is a calibration judgement made against real paper, not something to
        # synthesise from a sentence.
        "mapping_rules": {
            "exact_phrases": [],
            "aliases": [phrase] if (phrase := _phrase(quote)) else [],
            # TWO groups, not one, and that is what makes this reliable. An alias needs
            # three DISTINCTIVE words adjacent in the source, which 17 of the 34
            # positions simply do not contain — those were left on a single group worth
            # 3, under the threshold of 5, and failed verification. Two groups score 6
            # on their own, so a position reproduces whether or not it happens to
            # contain a quotable phrase.
            # Quote groups first, then the heading as a third candidate, capped at two.
            # A short table position — "Each amendment should reference the version/date
            # of the agreement it amends" — yields only five distinctive words and no
            # adjacent pair, so neither a second quote group nor an alias. Its ROW text
            # begins with the element name, so the heading group matches there. In the
            # prose sections the heading sits in a `###` line outside the paragraph, so
            # this group simply never fires and costs nothing.
            "keyword_groups": [g for g in (quote_terms[:3], quote_terms[3:6],
                                           terms[:3]) if len(g) == 3][:2],
            "negative_patterns": [],
            "section_heading_terms": terms[:3],
            "confirm_threshold": 5,
        },
        "_calibration": [
            "GENERATED, and the mapping terms are this tool's work, not the "
            "Constitution's: they come from the position's own heading. The POSITION is "
            "the Constitution's and is verbatim; the terms are an implementation detail "
            "(`AM-72` r6) and are uncalibrated until a document of this type is supplied.",
            f"The Constitution marks this position: {status}. That grade is recorded in "
            "`constitution.basis` and records PROVENANCE only — the owner ruled on "
            "2026-09-18 that it never suppresses an answer.",
        ],
        "legal_rule": {
            "rule_type": "THRESHOLD",
            "configuration": {
                "deviation_outcome": "UNACCEPTABLE",
                "unlimited_outcome": "UNACCEPTABLE",
            },
        },
    }
    return code, payload


# ---------------------------------------------------------------------------------------
# AM-322 (owner go, 2026-11-09) — positions OUTSIDE §31.9-§31.12, one sentence or one
# bullet each, sliced from the CANONICAL Constitution. `starts` are the first words of
# the sentence (or bullet) as the Constitution writes them; the quote runs to its full
# stop (a bullet: to its line end), and several are joined by " ... " as the existing
# §31.14 standard joins its two. Nothing is retyped. Mapping terms are configured per
# position and every term is a word of the cited section (or, for the MSA trade-secret
# copy, the ratified terminology of the SAME §15 position in TRADE-SECRET-CARVEOUT-NDA-001),
# except the §12 finding terms the owner approved on 2026-11-11 (AM-322 r13,
# `approved_terms`), which each file names apart from §12's own words (`_provenance`).
# Numeric positions (§31.14's 30 days for a vendor or distributor) stay hand-written.
# AM-322 r14: re-cited to L1.16 (AM-300) — §12, §15 and §31.14 are byte-identical to L1.15
CANONICAL = CONSTITUTION.with_name("LEGAL_CONSTITUTION_L1.16.md")
_CANONICAL_VERSION = "L1.16"

_S12_TYPES = ("MSA", "VENDOR_AGREEMENT")
_S12_ACCEPTABLE = "A vendor or client-facing document that commits to India data residency"
_S12_UNACCEPTABLE = "A vendor or client-facing document with no data-residency commitment"
_S12_POSITION = "Data residency is maintained within India for all India-designated"
_ASSIGN = ["assignment"]


def _s12(code_stem: str, types: tuple[str, ...], **spec) -> dict[str, dict]:
    return {f"{code_stem}-{t}-001": {"section": "12", "document_type": t,
                                     "topic": "Data Protection & Privacy",
                                     "basis": "STAKEHOLDER_CONFIRMED",
                                     "unacceptable": _S12_UNACCEPTABLE,
                                     # AM-73 r1: a published policy states no position of
                                     # its own; our Privacy Policy's breach and
                                     # sub-processor wording is not a contract to measure
                                     # DPA: until the owner rules C-31 (§12.2 vs AM-73
                                     # r1/AM-244), a standalone DPA stays unmeasured
                                     "not_applicable_to": ["PRIVACY_POLICY", "AUP", "DPA"],
                                     # AM-322 r11: only absence is automatic; a clause
                                     # found is read by a person, never MATCH (rule 15)
                                     "found_clause_for_a_person": True,
                                     **spec}
            for t in types}


def _terms(mapping: dict) -> list[str]:
    """Every mapping term once, in configured order; a keyword group as "a + b"."""
    out = [*mapping.get("exact_phrases", []), *mapping.get("aliases", []),
           *(" + ".join(g) for g in mapping.get("keyword_groups", [])),
           *mapping.get("section_heading_terms", [])]
    return list(dict.fromkeys(out))


def _provenance(spec: dict, mapping: dict, plain: str) -> str:
    """Where the mapping terms come from, true per file. `plain` is the file's wording
    when every term is the cited section's own; a §12 file carrying AM-322 r13's terms
    (owner, 2026-11-11, from our own paper) names them apart from §12's words."""
    approved = spec.get("approved_terms") or []
    if not approved:
        return plain
    own = [t for t in _terms(mapping) if t not in approved]
    return (f"the section's own words ({'; '.join(own)}) plus terms the owner approved "
            f"on 2026-11-11 from our own paper, AM-322 r13 ({'; '.join(approved)})")


POSITIONS: dict[str, dict] = {
    # §12 Company Position + Unacceptable Position: "no data-residency commitment for
    # India-designated services". A client-facing MSA or a vendor; the published TOS is
    # left out (AM-322 r3).
    **_s12("DATA-RESIDENCY", _S12_TYPES, starts=[_S12_POSITION],
           scope_key="DATA_RESIDENCY",
           description=("Data for India-designated services stays within India, and the "
                        "document commits to that."),
           # AM-322 r13 (owner, 2026-11-11): R1/R2 of AM322-PROPOSED-TERMS — finding-only
           # terms from our MSA.pdf 11.5 ("Cross-Border Data Transfers: If Personal Data is
           # transferred outside the jurisdiction … cross-border transfers from India …")
           mapping={"exact_phrases": ["data residency", "data-residency"],
                    "aliases": ["cross-border transfers"],
                    "keyword_groups": [["residency", "india"],
                                       ["transferred outside", "india"]],
                    "negative_patterns": ["system logs"],
                    "section_heading_terms": ["data residency",
                                              "cross-border data transfers"]},
           approved_terms=["cross-border transfers", "cross-border data transfers",
                           "transferred outside + india"]),
    # §12 Acceptable / Unacceptable: "a defined breach-notification timeline". §12.3: no
    # contractual deadline is assumed, so no figure — but a timeline must be STATED, so
    # no single term confirms: the breach and a timeline ("without undue delay", the
    # Drafting Notes' words, or an hours figure) must appear together to FIND the
    # clause; what it commits to is read by a person (§12.3, AM-322 r11).
    **_s12("BREACH-NOTIFICATION", ("MSA", "TOS"), starts=[_S12_ACCEPTABLE],
           scope_key="BREACH_NOTIFICATION",
           description=("The other party is told of a personal data breach within a "
                        "defined timeline."),
           # AM-322 r13 (owner, 2026-11-11): B1/B2 — our TOS "Breach Notification:" and
           # Privacy Policy "Data Breach Notification" headings; "data breach" only beside
           # "notify" (alone it is in our MSA's disclaimers and customer indemnities)
           mapping={"exact_phrases": [],
                    "aliases": ["personal data breach"],
                    "keyword_groups": [["personal data breach", "without undue delay"],
                                       ["personal data breach", "hours"],
                                       ["data breach", "notify"]],
                    "negative_patterns": [],
                    "section_heading_terms": ["breach notification",
                                              "data breach notification"]},
           approved_terms=["data breach + notify", "breach notification",
                           "data breach notification"]),
    # §12 Company Position (and §19's row): sub-processors disclosed and bound.
    **_s12("SUB-PROCESSORS", ("MSA", "TOS"), starts=[_S12_POSITION],
           scope_key="SUB_PROCESSORS", unacceptable=None,
           description=("Sub-processors are disclosed and bound to obligations no less "
                        "protective than the company's own."),
           # AM-322 r13 (owner, 2026-11-11): S1/S2/S4 — our MSA.pdf 11.4 "Third-Party
           # Processors", the executed MSA (2026-07-30) 18.2 "engage a subcontractor", our MSA's "Third Party
           # Service Providers: Leapswitch may use third-party service providers". S1 is
           # also an alias: the parser keeps 11.4's "Third-Party Processors:" label in the
           # body, not as a section title, so a heading term alone never reads it.
           mapping={"exact_phrases": ["sub-processors", "sub-processor"],
                    "aliases": ["engage a subcontractor", "third-party service providers",
                                "third-party processors"],
                    "keyword_groups": [], "negative_patterns": [],
                    "section_heading_terms": ["sub-processors", "third-party processors"]},
           approved_terms=["engage a subcontractor", "third-party service providers",
                           "third-party processors"]),
    # §15: "except that obligations relating to trade secrets survive for as long as the
    # information remains a trade secret" — entity-wide; the NDA copy exists, the MSA's
    # did not. Same position, so the same scope key and terminology as the NDA copy.
    "TRADE-SECRET-CARVEOUT-MSA-001": {
        "section": "15", "document_type": "MSA",
        "topic": "Confidentiality & Intellectual Property",
        "basis": "STAKEHOLDER_CONFIRMED",
        "starts": ["Obligations survive termination or expiry for 3 years"],
        "scope_key": "TRADE_SECRET_CARVE_OUT",
        "expected_when": ["CONF-SURVIVAL-MSA-001", "CONF-SURVIVAL-NDA-001"],
        "description": ("Confidentiality obligations for trade secrets continue for as "
                        "long as the information remains a trade secret."),
        "copy_from": "TRADE-SECRET-CARVEOUT-NDA-001",
    },
    # §31.14 Change of Ownership / Control.
    "CHANGE-OF-CONTROL-TERMINATION-PARTNER_AGREEMENT-001": {
        "section": "31.14", "document_type": "PARTNER_AGREEMENT",
        "topic": "Major Changes — Change of Control", "basis": "COMPANY_APPROVED",
        "starts": ["Termination right: either party may terminate a Partner Agreement"],
        "whole_line": True, "scope_key": "PARTNER_CHANGE_OF_CONTROL_TERMINATION",
        "description": ("Either party may end a Partner Agreement when the other's change "
                        "of control would harm its ability to perform."),
        "mapping": {"exact_phrases": [], "aliases": [],
                    "keyword_groups": [["change of control", "terminate"],
                                       ["change of control", "immediately"]],
                    "negative_patterns": [], "section_heading_terms": []},
    },
    "ASSIGNMENT-PARTNER_AGREEMENT-001": {
        "section": "31.14", "document_type": "PARTNER_AGREEMENT",
        "topic": "Major Changes — Assignment", "basis": "COMPANY_APPROVED",
        "starts": ["Assignment on M&A:"], "whole_line": True,
        "scope_key": "PARTNER_ASSIGNMENT",
        "description": ("The partner assigns only with the company's prior written "
                        "consent; the company may assign to an affiliate or acquirer."),
        "mapping": {"exact_phrases": [], "aliases": [],
                    "keyword_groups": [[*_ASSIGN, "prior written consent"],
                                       [*_ASSIGN, "affiliate"], [*_ASSIGN, "acquirer"]],
                    "negative_patterns": [], "section_heading_terms": _ASSIGN},
    },
    "ASSIGNMENT-MSA-001": {
        "section": "31.14", "document_type": "MSA",
        "topic": "Major Changes — Assignment", "basis": "COMPANY_APPROVED",
        "starts": ["Company-side assignment should be permitted to an affiliate"],
        "scope_key": "COMPANY_ASSIGNMENT",
        "description": ("LeapSwitch may assign the agreement to an affiliate, successor or "
                        "acquirer, or in a merger or restructuring, on notice."),
        "mapping": {"exact_phrases": [], "aliases": [],
                    "keyword_groups": [[*_ASSIGN, "affiliate"], [*_ASSIGN, "successor"],
                                       [*_ASSIGN, "acquirer"]],
                    "negative_patterns": [], "section_heading_terms": _ASSIGN},
    },
    "ASSIGNMENT-VENDOR_AGREEMENT-001": {
        "section": "31.14", "document_type": "VENDOR_AGREEMENT",
        "topic": "Major Changes — Assignment", "basis": "COMPANY_APPROVED",
        "starts": ["Vendor assignment should remain subject to Company consent",
                   "Company-side assignment to an affiliate/successor/acquirer"],
        "scope_key": "VENDOR_ASSIGNMENT",
        "description": ("The vendor assigns only with the company's consent, and the "
                        "company may assign to an affiliate, successor or acquirer."),
        "mapping": {"exact_phrases": [], "aliases": [],
                    "keyword_groups": [[*_ASSIGN, "consent"], [*_ASSIGN, "affiliate"],
                                       [*_ASSIGN, "successor"]],
                    "negative_patterns": [], "section_heading_terms": _ASSIGN},
    },
    "ASSIGNMENT-DISTRIBUTION_AGREEMENT-001": {
        "section": "31.14", "document_type": "DISTRIBUTION_AGREEMENT",
        "topic": "Major Changes — Assignment", "basis": "COMPANY_APPROVED",
        "starts": ["Assignment and successor rights should be clearly addressed"],
        "scope_key": "DISTRIBUTOR_ASSIGNMENT",
        "description": ("The distribution agreement clearly addresses assignment and "
                        "successor rights."),
        "mapping": {"exact_phrases": [], "aliases": [],
                    "keyword_groups": [[*_ASSIGN, "successor"], [*_ASSIGN, "rights"]],
                    "negative_patterns": [], "section_heading_terms": _ASSIGN},
    },
}


def _span(text: str, section: str) -> str:
    r"""`# **12\. …**` or `## **31.14 …**` up to the next heading of the same level."""
    start = re.search(rf"^(#{{1,2}}) \*\*{re.escape(section)}\\?\.? ", text, re.M)
    if not start:
        raise SystemExit(f"section {section} not found in {CANONICAL.name}")
    rest = text[start.end():]
    end = re.search(rf"^#{{1,{len(start.group(1))}}} \*\*", rest, re.M)
    return _unescape(rest[: end.start()] if end else rest)


def _slice(body: str, start: str, *, whole_line: bool) -> str:
    """The sentence (or bullet line) beginning with `start`, verbatim. Exactly once."""
    if body.count(start) != 1:
        raise SystemExit(f"{start!r} occurs {body.count(start)} times, not once")
    i = body.index(start)
    end = (body.find("\n", i) if whole_line
           else re.compile(r"\.(?=\s|$)").search(body, i).end())  # type: ignore[union-attr]
    return body[i:end if end != -1 else None].strip()


def _position(code: str, spec: dict, text: str) -> dict:
    body = _span(text, spec["section"])
    whole = spec.get("whole_line", False)
    quote = " ... ".join(_slice(body, s, whole_line=whole) for s in spec["starts"])
    if spec.get("copy_from"):
        source = json.loads((RATIFIED_STANDARDS_DIR / f"{spec['copy_from']}.json")
                            .read_text())
        mapping = source["mapping_rules"]
        extra = {k: source["configuration"][k] for k in ("waiver_patterns",)
                 if k in source["configuration"]}
    else:
        mapping = {**spec["mapping"], "confirm_threshold": 5}
        extra = {}
    constitution: dict = {"version": _CANONICAL_VERSION, "section": spec["section"],
                          "topic": spec["topic"], "basis": spec["basis"]}
    if spec.get("expected_when"):
        constitution["expected_when"] = {"confirmed_any": spec["expected_when"]}
    configuration: dict = {"document_type": spec["document_type"],
                           "constitution": constitution,
                           "expected_presence": "PRESENT",
                           "scope_key": spec["scope_key"],
                           "applicability": "REQUIRED",
                           "position_statement": quote}
    if spec.get("unacceptable"):
        configuration["unacceptable_position"] = _slice(body, spec["unacceptable"],
                                                        whole_line=False)
    if spec.get("found_clause_for_a_person"):
        configuration["found_clause_for_a_person"] = True
    if spec.get("not_applicable_to"):
        configuration["not_applicable_to"] = spec["not_applicable_to"]
    configuration.update(extra)
    return {
        "_about": [
            f"RATIFIED Company Standard — approved THROUGH THE LEGAL CONSTITUTION "
            f"{_CANONICAL_VERSION} (AM-73: everything in the Constitution is ratified "
            "except what it disclaims itself; owner go 2026-11-09, AM-322).",
            "GENERATED by tools/generate_section31_standards.py — `source_quote` is "
            "sliced from the section verbatim, never retyped (rules 7, 21).",
        ],
        "requirement_code": code,
        "description": spec["description"],
        "ratified": "2026-11-09",
        "approval": {
            "basis": "CONSTITUTION",
            "section": spec["section"],
            "ruling": ("owner, 2026-09-18 (AM-73) and 2026-11-09 (AM-322) — this "
                       "standard restates the cited position without changing it"),
            "calibration": ("35.10 — NOT calibrated against counterparty paper; the "
                            + (f"mapping terms are {spec['copy_from']}'s ratified "
                               "terminology for the same position"
                               if spec.get("copy_from") else "mapping terms are "
                               + _provenance(spec, mapping, "the section's own words"))
                            + " (rule 21)."),
        },
        "source_document": (f"Legal Constitution, Lawyer Review Version "
                            f"{_CANONICAL_VERSION} — docs/02-legal-domain/"
                            f"{CANONICAL.name}"),
        "source_clause": f"§{spec['section']}",
        "source_quote": quote,
        "configuration": configuration,
        "evaluator_type": "PRESENCE",
        "evaluation_rules": {
            "evaluator": "PRESENCE",
            "_note": "presence is established by the mapping layer alone (45D)",
        },
        "mapping_rules": mapping,
        "_calibration": [
            "GENERATED; the mapping terms are configuration (35.4), "
            + (f"copied from {spec['copy_from']} (the same position)"
               if spec.get("copy_from") else
               _provenance(spec, mapping, "each a word of the cited section"))
            + ", uncalibrated until a document of this type is supplied.",
            f"The Constitution marks this position {spec['basis']}; `constitution.basis` "
            "records PROVENANCE only and never suppresses an answer (AM-73 r4).",
        ],
        "legal_rule": {
            "rule_type": "THRESHOLD",
            "configuration": {
                "deviation_outcome": "UNACCEPTABLE",
                "unlimited_outcome": "UNACCEPTABLE",
            },
        },
    }


def build() -> dict[str, dict]:
    text = CONSTITUTION.read_text()
    built: dict[str, dict] = {}
    canonical = CANONICAL.read_text()
    for code, spec in POSITIONS.items():
        built[code] = _position(code, spec, canonical)
    for section, spec in SECTIONS.items():
        if section in _SKIP_SECTIONS:
            continue
        body = _section_body(text, section)
        heading_match = re.search(
            rf"^## \*\*{re.escape(section)} ([^\n]*?)\*\*\s*$", text, re.M)
        section_heading = heading_match.group(1).strip() if heading_match else section
        items = (_parse_rules(body) if spec["shape"] == "rules" else _parse_table(body))
        if not items:
            raise SystemExit(f"section {section}: no positions parsed")
        for heading, quote, status in items:
            code, payload = _standard(
                section=section, document_type=spec["document_type"], heading=heading,
                quote=quote, status=status, section_heading=section_heading)
            if code in built:
                raise SystemExit(f"duplicate requirement_code {code}")
            built[code] = payload
    return built


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit non-zero if any file is missing or stale")
    args = ap.parse_args()
    built = build()
    stale: list[str] = []
    for code, payload in sorted(built.items()):
        path = RATIFIED_STANDARDS_DIR / f"{code}.json"
        rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if args.check:
            if not path.exists() or path.read_text() != rendered:
                stale.append(code)
        else:
            path.write_text(rendered)
    if args.check and stale:
        print("stale or missing generated standards:\n  " + "\n  ".join(stale),
              file=sys.stderr)
        return 1
    print(f"{'checked' if args.check else 'wrote'} {len(built)} standards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
