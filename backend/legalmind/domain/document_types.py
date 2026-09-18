"""Document Type vocabulary — locked Step 6.

Step 6 fixes the initial V1 Document Types and distinguishes them from
Legal/Regulatory References ("These are not contract types"). A document is
additionally classified by source — ``Organization`` or ``Counterparty`` — and
Step 28's Requirement Model gives every Requirement a ``Document Type``, which is
what scopes a Requirement to the kind of paper it applies to. The worked example
in the locked comparison model is exactly this pairing: *"ABC MSA — Compared with
→ LeapSwitch Standard MSA."*

Why this is code and not a database enum: the locked physical schema (42.7) gives
the ``requirements`` table no document-type column and defines no
``document_types`` table, while Step 28 and Step 23 lock Document Type as a
concept and an admin-managed configuration area. That divergence is registered as
**C-13** and is not resolved here. Owner decision Q2 (2026-08-19) chose the
`D-3` route — the value lives in the Company Standard's ``configuration`` JSONB,
validated against this vocabulary in tested code, so no locked table changes.
A DB enum would be a schema change and would pre-empt C-13's resolution.
"""

from __future__ import annotations

# Locked Step 6's ten types, EXTENDED by the three Section 31 types (owner,
# 2026-09-18 — see below). Order matters only for error messages; membership is what
# is enforced.
#
# THE SECTION 31 EXTENSION.
#
# Legal Constitution L1.10 §31 "extends the Constitution's clause-wise structure to
# Partner Agreements, Vendor Agreements, Distribution Agreements, Purchase Orders,
# Amendments/Addenda, and Other Agreements", and tags each position with an
# "Applicable Document Types" line naming them. Locked Step 6 carried none of the
# first three, so no Company Standard could be typed to them and the importer refused
# every attempt: the Constitution stated positions the system had no vocabulary to
# hold.
#
# The visible consequence was a live defect (2026-09-18): "what is written about
# partner agreement in the constitution" was answered with three MSA standards,
# because no Partner Agreement position existed anywhere in the corpus. Registered as
# C-23 and resolved by the owner the same day — Constitution-final text is ratified,
# and every type the Constitution carries text for must answer from its own positions.
#
# Two of §31's six types needed nothing added:
#   * Purchase Order -> ORDER_FORM, already here and already how this repository
#     models it (the two proposed §31.11 standards are typed ORDER_FORM and coded
#     `PO-*`). A separate PURCHASE_ORDER type would have split one concept in two.
#   * Amendment/Addendum -> AMENDMENT, already here.
# "Other Agreements" (§31.13) adds no clauses of its own — it routes to the existing
# general sections — so it stays OTHER.
#
# EVIDENTIARY GRADE IS NOT CARRIED HERE. It lives in each standard's
# `configuration.constitution.basis`, whose vocabulary already distinguishes
# COMPANY_APPROVED from LEGALMIND_RULE (§31.9/§31.10's practice-based rules, "never
# Acceptable by guess") and NOT_ADOPTED (§31.6a, "never a current rule"). A document
# type says which paper a position governs; it never says how well evidenced that
# position is, and adding a type here asserts nothing about the text behind it.
DOCUMENT_TYPES: tuple[str, ...] = (
    "MSA",            # Master Services Agreement
    "NDA",            # Non-Disclosure Agreement
    "TOS",            # Terms of Service
    "SLA",            # Service Level Agreement
    "DPA",            # Data Processing Agreement
    "AUP",            # Acceptable Use Policy
    "PRIVACY_POLICY",
    "ORDER_FORM",     # also Constitution §31.11's Purchase Order (PO)
    "AMENDMENT",      # Amendment / Addendum — Constitution §31.12
    "PARTNER_AGREEMENT",       # Constitution §31.3-§31.8 (owner, 2026-09-18)
    "VENDOR_AGREEMENT",        # Constitution §31.9
    "DISTRIBUTION_AGREEMENT",  # Constitution §31.10
    "OTHER",
)

_DOCUMENT_TYPE_SET = frozenset(DOCUMENT_TYPES)


def readable(document_type: str) -> str:
    """The type as a reader sees it: `PARTNER_AGREEMENT` -> "Partner Agreement";
    `MSA` stays `MSA`.

    Needed the moment Step 6 gained a multi-word code (`AM-72`). A raw code composed
    into reader-facing text is not just ugly — `position_chunks` carries the type into
    the chunk body, and the Domain A egress screen reads any `WORD_WORD` token as an
    internal locator (an env var or a repo path), so `(PARTNER_AGREEMENT)` made the
    whole corpus refuse to egress. `ORDER_FORM` and `PRIVACY_POLICY` were the same
    landmine, unarmed only because no ratified standard was typed to either.

    Initialisms stay initialisms because that is what people call them.
    """
    return (document_type if document_type.isupper() and "_" not in document_type
            else document_type.replace("_", " ").title())


class UnknownDocumentType(ValueError):
    """A value outside locked Step 6's vocabulary.

    Raised rather than coerced: a wrong document type silently accepted would
    load the wrong baseline against a counterparty document, which is exactly
    the class of quiet error ENG-09 exists to prevent.
    """


def is_document_type(value: object) -> bool:
    return isinstance(value, str) and value in _DOCUMENT_TYPE_SET


def validate_document_type(value: object) -> str:
    """Return the value if it is a locked Step 6 type; raise otherwise.

    No normalisation is performed — ``"msa"`` is refused, not upcased. The
    vocabulary is a controlled legal classification, and a caller supplying a
    near-miss should be corrected at the boundary rather than guessed at.
    """
    if not is_document_type(value):
        raise UnknownDocumentType(
            f"unknown document type {value!r}; locked Step 6 defines exactly: "
            + ", ".join(DOCUMENT_TYPES))
    return value  # type: ignore[return-value]  # narrowed by is_document_type


# Document SOURCE — the second axis locked Step 6 names beside Type: "A document
# can be classified by source: Organization / Counterparty" (all_lock.md:535).
# "Can", not "must": the axis is optional, and DOC-06 leaves it "untouched", so
# this is the vocabulary only. Declared by the uploader, never inferred (the same
# reasoning as Q9 for Type), and stored in `document_versions.metadata` — the
# locked 42.4 JSONB — because a document's source can differ between versions:
# v1 our template, v2 the counterparty's redline.
DOCUMENT_SOURCES: tuple[str, ...] = ("ORGANIZATION", "COUNTERPARTY")

_DOCUMENT_SOURCE_SET = frozenset(DOCUMENT_SOURCES)


def is_document_source(value: object) -> bool:
    return isinstance(value, str) and value in _DOCUMENT_SOURCE_SET
