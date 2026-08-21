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

# The ten initial V1 types, exactly as locked Step 6 lists them. Order matters
# only for error messages; membership is what is enforced.
DOCUMENT_TYPES: tuple[str, ...] = (
    "MSA",            # Master Services Agreement
    "NDA",            # Non-Disclosure Agreement
    "TOS",            # Terms of Service
    "SLA",            # Service Level Agreement
    "DPA",            # Data Processing Agreement
    "AUP",            # Acceptable Use Policy
    "PRIVACY_POLICY",
    "ORDER_FORM",
    "AMENDMENT",      # Amendment / Addendum
    "OTHER",
)

_DOCUMENT_TYPE_SET = frozenset(DOCUMENT_TYPES)


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
