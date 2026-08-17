"""Controlled vocabularies.

EVERY value here is fixed by a locked decision. Do not add, rename or remove a
member without an approved amendment.

The five-axis separation (REC-06) is load-bearing: Mapping State, Finding
Classification, Rule Outcome, Legal Decision and Review Lifecycle are distinct
axes and MUST NOT share an enum type. ``AMBIGUOUS`` in particular means three
different things on three different layers, which is why three separate types
below each declare their own member.
"""

from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    """String-valued enum; the DB type name is set explicitly at each column."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# --------------------------------------------------------------------------
# Axis 1 — Mapping State (Step 28, REC-03)
# --------------------------------------------------------------------------
class MappingState(StrEnum):
    CONFIRMED = "CONFIRMED"
    AMBIGUOUS = "AMBIGUOUS"      # more than one plausible mapping
    UNRESOLVED = "UNRESOLVED"    # mapping cannot be established reliably
    NONE = "NONE"                # mapping completed, no provision mapped (45D)


# --------------------------------------------------------------------------
# Axis 2 — Finding Classification (Step 36, canonical per REC-01)
# --------------------------------------------------------------------------
class FindingClassification(StrEnum):
    MATCH = "MATCH"
    DEVIATION = "DEVIATION"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"
    AMBIGUOUS = "AMBIGUOUS"          # candidates found, position undeterminable
    UNRESOLVED = "UNRESOLVED"        # no usable answer establishable (AM-7)
    UNABLE_TO_EVALUATE = "UNABLE_TO_EVALUATE"


# Roll-up derivation order (Step 45B re-lock record).
# The TIER SPLIT is derived from ENG-09 fail-closed: a Finding must never read
# MATCH while any scope is unevaluable, contradictory or absent.
# The ORDERING WITHIN TIER 1 IS AN ENGINEERING DETERMINISM CONVENTION ONLY.
# It is NOT a legal hierarchy — all four route to human review and are legally
# equivalent in consequence. The order exists solely to satisfy ENG-11.
ROLLUP_TIER_1: tuple[FindingClassification, ...] = (
    FindingClassification.UNABLE_TO_EVALUATE,
    FindingClassification.CONFLICT,
    FindingClassification.AMBIGUOUS,
    FindingClassification.UNRESOLVED,
)
ROLLUP_TIER_2: tuple[FindingClassification, ...] = (
    FindingClassification.MISSING,
    FindingClassification.DEVIATION,
    FindingClassification.MATCH,
)
ROLLUP_PRECEDENCE: tuple[FindingClassification, ...] = ROLLUP_TIER_1 + ROLLUP_TIER_2


# --------------------------------------------------------------------------
# Axis 3 — Rule Outcome (Steps 27, 31, 45B.14). Evaluation level ONLY (J-2).
# --------------------------------------------------------------------------
class RuleOutcome(StrEnum):
    ACCEPTABLE = "ACCEPTABLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    UNACCEPTABLE = "UNACCEPTABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"   # never NULL (45B.26)


# --------------------------------------------------------------------------
# Axis 4 — Legal Decision (Step 31). REQUIRE_COMPANY_STANDARD is canonical;
# 41.21's REQUIRE_STANDARD was illustrative and is superseded.
# --------------------------------------------------------------------------
class DecisionType(StrEnum):
    ACCEPT_DEVIATION = "ACCEPT_DEVIATION"
    REQUIRE_COMPANY_STANDARD = "REQUIRE_COMPANY_STANDARD"
    APPROVE_CUSTOMIZATION = "APPROVE_CUSTOMIZATION"
    REJECT = "REJECT"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"


# --------------------------------------------------------------------------
# Axis 5 — Review Lifecycle (Step 30)
# --------------------------------------------------------------------------
class ReviewStatus(StrEnum):
    DRAFT = "DRAFT"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    ANALYSIS_COMPLETE = "ANALYSIS_COMPLETE"
    LEGAL_REVIEW = "LEGAL_REVIEW"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    ANALYSIS_FAILED = "ANALYSIS_FAILED"   # distinct from UNABLE_TO_EVALUATE
    CANCELLED = "CANCELLED"


# --------------------------------------------------------------------------
# Finding status — per-Finding workflow position (J-4).
# NOT one of the five axes. Finding.RESOLVED and Review.RESOLVED are different
# values on different objects and deliberately do not share a type.
# --------------------------------------------------------------------------
class FindingStatus(StrEnum):
    OPEN = "OPEN"
    DECISION_REQUIRED = "DECISION_REQUIRED"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"
    RESOLVED = "RESOLVED"


# --------------------------------------------------------------------------
# Evaluator vocabulary (AM-16). Exactly two values; both exercised in V1.
# Additional types are additive amendments when a Requirement needs one.
# --------------------------------------------------------------------------
class EvaluatorType(StrEnum):
    NUMERIC_COMPARISON = "NUMERIC_COMPARISON"
    PRESENCE = "PRESENCE"


class EvaluationKind(StrEnum):
    """AM-8'. Generalized from liability's GENERAL/EXCEPTION (N-19)."""

    PRIMARY = "PRIMARY"
    EXCEPTION = "EXCEPTION"


class ExtractionStatus(StrEnum):
    """45B.7 — fact-quality signal on evaluator input, not an axis."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"   # distinct from MappingState/Classification
    FAILED = "FAILED"


class EvidenceRelationshipType(StrEnum):
    """42.16 / AB-1.5."""

    PRIMARY = "PRIMARY"
    SUPPORTING = "SUPPORTING"
    CONFLICTING = "CONFLICTING"


class EvidenceSourceType(StrEnum):
    """42.6."""

    NATIVE_TEXT = "NATIVE_TEXT"
    OCR = "OCR"
    TABLE = "TABLE"
    OTHER = "OTHER"


class UserStatus(StrEnum):
    """42.2."""

    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"


class ContractStatus(StrEnum):
    """42.3 — Step 2 vocabulary."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class ConfigStatus(StrEnum):
    """42.7 — Step 29 configuration lifecycle."""

    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"


class ProcessingStatus(StrEnum):
    """42.4 — document-level processing state."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessingRunType(StrEnum):
    """42.5."""

    PARSE = "PARSE"
    OCR = "OCR"
    REPROCESS = "REPROCESS"


class ProcessingRunStatus(StrEnum):
    """42.5 — preserves attempt history rather than overwriting."""

    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RuleType(StrEnum):
    """42.9 legal_rule_versions.rule_type."""

    THRESHOLD = "THRESHOLD"
    ALLOWED_VALUES = "ALLOWED_VALUES"
    PRESENCE = "PRESENCE"


class IdentityProvider(StrEnum):
    """Step 47 / OD-9 — OIDC primary, password fallback."""

    OIDC = "OIDC"
    PASSWORD = "PASSWORD"
