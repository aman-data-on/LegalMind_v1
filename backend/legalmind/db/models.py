"""SQLAlchemy models — the locked LegalMind schema.

Sources: Step 42 (exact schema), Step 41 (design), Amendment Batch AB-1,
Step 47 (security). Each table cites the locked decision that fixes it.

Do not add, drop or retype a column here without an approved amendment.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Enum as SAEnum,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import mapped_column

from legalmind.db.base import (
    Base,
    UUIDType,
    fk_uuid,
    jsonb_col,
    pk_uuid,
    ts_created,
    ts_nullable,
    ts_updated,
)
from legalmind.domain import enums as E


def _enum(py_enum: Any, name: str) -> SAEnum:
    """Native PG enum. Each axis gets its OWN type name (REC-06) — no axis
    may share an enum type with another."""
    return SAEnum(
        py_enum,
        name=name,
        native_enum=True,
        values_callable=lambda ec: [m.value for m in ec],
    )


def _str(nullable: bool = False):
    return mapped_column(String, nullable=nullable)


def _text(nullable: bool = True):
    return mapped_column(Text, nullable=nullable)


# ==========================================================================
# Identity & Access — 42.2, 42.3, Step 47
# ==========================================================================
class User(Base):
    """42.2. No credential or provider columns — see UserIdentity (Step 47)."""

    __tablename__ = "users"

    id = pk_uuid()
    email = mapped_column(String, nullable=False, unique=True)
    name = _str()
    status = mapped_column(_enum(E.UserStatus, "user_status"), nullable=False)
    created_at = ts_created()
    updated_at = ts_updated()


class Role(Base):
    """42.3. Step 23 defines the canonical role set."""

    __tablename__ = "roles"

    id = pk_uuid()
    code = mapped_column(String, nullable=False, unique=True)
    name = _str()


class UserRole(Base):
    """42.3 — many-to-many, "This keeps role assignment flexible."

    SEC-03: multi-role with union semantics. Legal Decision Authority is
    carried as an ADDITIONAL role assignment, which is how two users holding
    the same primary role can differ in legal authority (Step 4).
    """

    __tablename__ = "user_roles"

    user_id = fk_uuid("users.id", ondelete="CASCADE", primary_key=True)
    role_id = fk_uuid("roles.id", ondelete="RESTRICT", primary_key=True)


class Permission(Base):
    """Step 47 / SEC-04 permission catalogue."""

    __tablename__ = "permissions"

    id = pk_uuid()
    name = mapped_column(String, nullable=False, unique=True)
    permission_group = _str()
    description = _text()
    created_at = ts_created()


class RolePermission(Base):
    """Step 47. Replacement is transactional (S-10, locked 43.26)."""

    __tablename__ = "role_permissions"

    role_id = fk_uuid("roles.id", ondelete="CASCADE", primary_key=True)
    permission_id = fk_uuid("permissions.id", ondelete="CASCADE", primary_key=True)


class UserSession(Base):
    """Step 47 / SEC-01. Server-side sessions; the stateless JWT model is rejected.

    The session carries IDENTITY ONLY. Roles, permissions and legal authority
    are resolved fresh from the database on every request (S-1).
    """

    __tablename__ = "sessions"

    id = pk_uuid()
    user_id = fk_uuid("users.id", ondelete="CASCADE")
    created_at = ts_created()
    last_seen_at = ts_created()
    expires_at = mapped_column(__import__("legalmind.db.base", fromlist=["TS"]).TS, nullable=False)
    revoked_at = ts_nullable()
    revoked_reason = _str(nullable=True)

    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )


class UserIdentity(Base):
    """Step 47 / OD-9. OIDC primary, password fallback.

    credential_hash is selected by exactly one repository method and excluded
    from every other query (S-4).
    """

    __tablename__ = "user_identities"

    id = pk_uuid()
    user_id = fk_uuid("users.id", ondelete="CASCADE")
    provider = mapped_column(_enum(E.IdentityProvider, "identity_provider"), nullable=False)
    provider_subject = _str(nullable=True)
    credential_hash = _str(nullable=True)
    created_at = ts_created()
    last_used_at = ts_nullable()

    __table_args__ = (
        UniqueConstraint("provider", "provider_subject",
                         name="uq_user_identities_provider_subject"),
        UniqueConstraint("user_id", "provider",
                         name="uq_user_identities_user_provider"),
        Index("ix_user_identities_user_id", "user_id"),
    )


# ==========================================================================
# Contracts & Documents — 42.3 - 42.6
# ==========================================================================
class Contract(Base):
    """42.3. owner_id makes ownership traversable (41.23) for 41.24 checks."""

    __tablename__ = "contracts"

    id = pk_uuid()
    owner_id = fk_uuid("users.id")
    name = _str()
    contract_type = _str(nullable=True)
    status = mapped_column(_enum(E.ContractStatus, "contract_status"), nullable=False)
    created_at = ts_created()
    updated_at = ts_updated()

    __table_args__ = (
        Index("ix_contracts_owner_id", "owner_id"),
        Index("ix_contracts_status", "status"),
        Index("ix_contracts_created_at", "created_at"),
    )


class DocumentVersion(Base):
    """42.4. Immutable once created (Step 26). file_hash is indexed but NOT
    unique — the same source file may legitimately appear in multiple
    contracts."""

    __tablename__ = "document_versions"

    id = pk_uuid()
    contract_id = fk_uuid("contracts.id")
    version_number = mapped_column(Integer, nullable=False)
    original_filename = _str()
    mime_type = _str()
    file_size_bytes = mapped_column(BigInteger, nullable=False)
    file_hash = _str()
    storage_key = _str()
    processing_status = mapped_column(
        _enum(E.ProcessingStatus, "processing_status"), nullable=False)
    extraction_status = mapped_column(
        _enum(E.ExtractionStatus, "extraction_status"), nullable=True)
    uploaded_by = fk_uuid("users.id")
    created_at = ts_created()
    doc_metadata = jsonb_col(name="metadata")

    __table_args__ = (
        UniqueConstraint("contract_id", "version_number",
                         name="uq_document_versions_contract_version"),
        Index("ix_document_versions_contract_id", "contract_id"),
        Index("ix_document_versions_file_hash", "file_hash"),
        Index("ix_document_versions_uploaded_by", "uploaded_by"),
        Index("ix_document_versions_processing_status", "processing_status"),
    )


class DocumentProcessingRun(Base):
    """42.5. Attempt history is preserved, never overwritten."""

    __tablename__ = "document_processing_runs"

    id = pk_uuid()
    document_version_id = fk_uuid("document_versions.id")
    run_type = mapped_column(_enum(E.ProcessingRunType, "processing_run_type"), nullable=False)
    status = mapped_column(_enum(E.ProcessingRunStatus, "processing_run_status"), nullable=False)
    processor_version = _str(nullable=True)
    started_at = ts_nullable()
    completed_at = ts_nullable()
    error_code = _str(nullable=True)
    error_message = _text()
    created_at = ts_created()
    run_metadata = jsonb_col(name="metadata")

    __table_args__ = (
        Index("ix_document_processing_runs_document_version_id", "document_version_id"),
        Index("ix_document_processing_runs_status", "status"),
        Index("ix_document_processing_runs_created_at", "created_at"),
    )


class DocumentEvidence(Base):
    """42.6. Evidence is tied to the processing run that produced it (41.10)."""

    __tablename__ = "document_evidence"

    id = pk_uuid()
    document_version_id = fk_uuid("document_versions.id")
    processing_run_id = fk_uuid("document_processing_runs.id")
    page_number = mapped_column(Integer, nullable=True)
    section_number = _str(nullable=True)
    section_title = _text()
    content = mapped_column(Text, nullable=False)
    source_type = mapped_column(_enum(E.EvidenceSourceType, "evidence_source_type"), nullable=False)
    start_offset = mapped_column(BigInteger, nullable=True)
    end_offset = mapped_column(BigInteger, nullable=True)
    created_at = ts_created()
    evidence_metadata = jsonb_col(name="metadata")

    __table_args__ = (
        Index("ix_document_evidence_document_version_id", "document_version_id"),
        Index("ix_document_evidence_processing_run_id", "processing_run_id"),
        Index("ix_document_evidence_docver_page", "document_version_id", "page_number"),
    )


# ==========================================================================
# Legal Configuration — 42.7 - 42.12. Versioned; never mutated in place (Step 29).
# ==========================================================================
class Requirement(Base):
    """42.7."""

    __tablename__ = "requirements"

    id = pk_uuid()
    code = mapped_column(String, nullable=False, unique=True)
    status = mapped_column(_enum(E.ConfigStatus, "config_status"), nullable=False)
    created_at = ts_created()
    updated_at = ts_updated()


class RequirementVersion(Base):
    """42.7. evaluator_type is SINGULAR — a Requirement version has exactly one
    evaluator type. This is why a presence condition plus value criteria are
    modelled as two Requirements over the same clause (N-36, Step 28 r1)."""

    __tablename__ = "requirement_versions"

    id = pk_uuid()
    requirement_id = fk_uuid("requirements.id")
    version_number = mapped_column(Integer, nullable=False)
    name = _str()
    description = _text()
    evaluator_type = mapped_column(_enum(E.EvaluatorType, "evaluator_type"), nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("requirement_id", "version_number",
                         name="uq_requirement_versions_requirement_version"),
    )


class CompanyStandardVersion(Base):
    """42.8. `configuration` holds evaluator-specific values — which is why
    AM-18 (`standard_kind`) was withdrawn as redundant: the kind is already
    determined by requirement_versions.evaluator_type."""

    __tablename__ = "company_standard_versions"

    id = pk_uuid()
    requirement_version_id = fk_uuid("requirement_versions.id")
    version_number = mapped_column(Integer, nullable=False)
    configuration = jsonb_col(nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("requirement_version_id", "version_number",
                         name="uq_company_standard_versions_reqver_version"),
    )


class LegalRuleVersion(Base):
    """42.9. Optional per Requirement — Step 20 r4: not every Clause requires a
    Pre-approved Legal Rule."""

    __tablename__ = "legal_rule_versions"

    id = pk_uuid()
    requirement_version_id = fk_uuid("requirement_versions.id")
    version_number = mapped_column(Integer, nullable=False)
    rule_type = mapped_column(_enum(E.RuleType, "rule_type"), nullable=False)
    configuration = jsonb_col(nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("requirement_version_id", "version_number",
                         name="uq_legal_rule_versions_reqver_version"),
    )


class MappingRuleVersion(Base):
    """42.10. Mapping Rules != Evaluation Rules (ENG-03)."""

    __tablename__ = "mapping_rule_versions"

    id = pk_uuid()
    requirement_version_id = fk_uuid("requirement_versions.id")
    version_number = mapped_column(Integer, nullable=False)
    rules = jsonb_col(nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("requirement_version_id", "version_number",
                         name="uq_mapping_rule_versions_reqver_version"),
    )


class EvaluationRuleVersion(Base):
    """42.11."""

    __tablename__ = "evaluation_rule_versions"

    id = pk_uuid()
    requirement_version_id = fk_uuid("requirement_versions.id")
    version_number = mapped_column(Integer, nullable=False)
    evaluator_type = mapped_column(_enum(E.EvaluatorType, "evaluator_type"),
                                   nullable=False)
    rules = jsonb_col(nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("requirement_version_id", "version_number",
                         name="uq_evaluation_rule_versions_reqver_version"),
    )


class ConfigurationSnapshot(Base):
    """42.12. Pins the exact configuration a Review used (Step 30, AUD-04)."""

    __tablename__ = "configuration_snapshots"

    id = pk_uuid()
    snapshot_hash = mapped_column(String, nullable=False, unique=True)
    created_by = fk_uuid("users.id")
    created_at = ts_created()


class ConfigurationSnapshotItem(Base):
    """42.12. The Company Standard version used by an Evaluation is derived
    through this table (which is why AM-21 was withdrawn)."""

    __tablename__ = "configuration_snapshot_items"

    snapshot_id = fk_uuid("configuration_snapshots.id", primary_key=True)
    requirement_version_id = fk_uuid("requirement_versions.id", primary_key=True)
    company_standard_version_id = fk_uuid("company_standard_versions.id")
    legal_rule_version_id = fk_uuid("legal_rule_versions.id", nullable=True)
    mapping_rule_version_id = fk_uuid("mapping_rule_versions.id")
    evaluation_rule_version_id = fk_uuid("evaluation_rule_versions.id")


# ==========================================================================
# Reviews, Findings, Evaluations, Decisions — 42.13 - 42.18 + AB-1
# ==========================================================================
class Review(Base):
    """42.13. Tied to exactly one Document Version and one configuration
    snapshot (Step 26 r2, Step 30)."""

    __tablename__ = "reviews"

    id = pk_uuid()
    contract_id = fk_uuid("contracts.id")
    document_version_id = fk_uuid("document_versions.id")
    configuration_snapshot_id = fk_uuid("configuration_snapshots.id")
    status = mapped_column(_enum(E.ReviewStatus, "review_status"), nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()
    started_at = ts_nullable()
    completed_at = ts_nullable()

    __table_args__ = (
        Index("ix_reviews_contract_id", "contract_id"),
        Index("ix_reviews_document_version_id", "document_version_id"),
        Index("ix_reviews_created_by", "created_by"),
        Index("ix_reviews_status", "status"),
        Index("ix_reviews_created_at", "created_at"),
    )


class Finding(Base):
    """42.14 + AB-1.6.

    `classification` is a DERIVED, NON-AUTHORITATIVE SUMMARY of the Finding's
    Evaluations (45B re-lock, D-1.1). The scoped Evaluation results are
    authoritative. There is deliberately NO Finding-level rule_outcome (J-2).

    UNIQUE(review_id, requirement_version_id): exactly one Finding per
    Requirement per Review (A-4.1).
    """

    __tablename__ = "findings"

    id = pk_uuid()
    review_id = fk_uuid("reviews.id")
    requirement_version_id = fk_uuid("requirement_versions.id")
    classification = mapped_column(
        _enum(E.FindingClassification, "finding_classification"), nullable=False)
    status = mapped_column(_enum(E.FindingStatus, "finding_status"), nullable=False)
    created_at = ts_created()
    updated_at = ts_updated()

    __table_args__ = (
        UniqueConstraint("review_id", "requirement_version_id",
                         name="uq_findings_review_requirement_version"),
        Index("ix_findings_review_id", "review_id"),
        Index("ix_findings_status", "status"),
    )


class Evaluation(Base):
    """42.15 + AM-8', AM-19, AM-20.

    One Evaluation per governed scope. EV-MIN: every Finding has >= 1
    Evaluation, enforced by a deferred constraint trigger (AB-1.6).

    UNIQUE(id, finding_id) exists to support the composite FK from
    legal_decisions, which keeps a decision and its Evaluation on the same
    Finding declaratively rather than by service check.
    """

    __tablename__ = "evaluations"

    id = pk_uuid()
    finding_id = fk_uuid("findings.id")
    evaluator_type = mapped_column(_enum(E.EvaluatorType, "evaluator_type"),
                                   nullable=False)
    evaluator_version = _str()                       # AM-19 (locked 45B.10)
    scope_key = _str()                               # AM-8' (per-Requirement vocab)
    scope_label = _str(nullable=True)
    evaluation_kind = mapped_column(
        _enum(E.EvaluationKind, "evaluation_kind"), nullable=False)
    classification = mapped_column(
        _enum(E.FindingClassification, "finding_classification"), nullable=False)
    rule_outcome = mapped_column(
        _enum(E.RuleOutcome, "rule_outcome"), nullable=False)   # never NULL (45B.26)
    expected_value = jsonb_col()
    actual_value = jsonb_col()
    operator = _str(nullable=True)
    result = jsonb_col(nullable=False)               # carries diagnostics (REC-07)
    rule_version_id = fk_uuid("evaluation_rule_versions.id", nullable=True)
    legal_rule_version_id = fk_uuid("legal_rule_versions.id", nullable=True)  # AM-20
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("id", "finding_id", name="uq_evaluations_id_finding_id"),
        Index("ix_evaluations_finding_id", "finding_id"),
    )


class FindingEvidence(Base):
    """42.16. Finding-level roll-up, retained unchanged by AB-1."""

    __tablename__ = "finding_evidence"

    finding_id = fk_uuid("findings.id", primary_key=True)
    evidence_id = fk_uuid("document_evidence.id", primary_key=True)
    relationship_type = mapped_column(
        _enum(E.EvidenceRelationshipType, "evidence_relationship_type"), nullable=False)


class EvaluationEvidence(Base):
    """AB-1.5 — per-scope evidence attribution.

    NO minimum-row constraint. Zero rows is a VALID state: a MISSING arising
    from established absence legitimately carries no evidence (45C.15, N-34).
    Synthetic evidence must never be created to satisfy a cardinality rule.
    """

    __tablename__ = "evaluation_evidence"

    evaluation_id = fk_uuid("evaluations.id", primary_key=True)
    evidence_id = fk_uuid("document_evidence.id", primary_key=True)
    relationship_type = mapped_column(
        _enum(E.EvidenceRelationshipType, "evidence_relationship_type"), nullable=False)


class LegalDecision(Base):
    """42.17 + AM-1, AM-12, AM-15.

    A decision resolves EXACTLY ONE Evaluation and never implicitly disposes of
    another under the same Finding (AB-1.1).

    Supersession is APPEND-ONLY: the current decision is the row with the
    highest version_number. Prior rows are never updated or deleted, which is
    what makes Step 31 r14 and r20 implementable as written.
    """

    __tablename__ = "legal_decisions"

    id = pk_uuid()
    finding_id = fk_uuid("findings.id")
    evaluation_id = fk_uuid("evaluations.id")
    decision_type = mapped_column(_enum(E.DecisionType, "decision_type"), nullable=False)
    justification = mapped_column(Text, nullable=False)     # AM-15 (Step 31 r11)
    decided_by = fk_uuid("users.id")
    version_number = mapped_column(Integer, nullable=False)
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("evaluation_id", "version_number",
                         name="uq_legal_decisions_evaluation_version"),
        ForeignKeyConstraint(
            ["finding_id", "evaluation_id"],
            ["evaluations.finding_id", "evaluations.id"],
            name="fk_legal_decisions_evaluation_same_finding",
        ),
        Index("ix_legal_decisions_evaluation_version",
              "evaluation_id", "version_number"),
        Index("ix_legal_decisions_decided_by", "decided_by"),
        Index("ix_legal_decisions_created_at", "created_at"),
    )


class UnmatchedProvision(Base):
    """AB-1.5 / REC-02. A document-level observation, NOT a Finding
    classification. Must never occupy a Finding's classification field."""

    __tablename__ = "unmatched_provisions"

    id = pk_uuid()
    review_id = fk_uuid("reviews.id")
    evidence_id = fk_uuid("document_evidence.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("review_id", "evidence_id",
                         name="uq_unmatched_provisions_review_evidence"),
    )


class ReviewAssignment(Base):
    """Legal Reviewer assignment — locked Step 24 r6 requires it.

    NEW TABLE, no locked table amended. Step 24 rules 5, 6, 16 and 17 make
    assignment the mechanism by which Legal gains access to a Review, and no
    locked table represents it.

    r16/r17: assignment grants access for Legal work; it does NOT transfer
    business ownership from the original User.
    """

    __tablename__ = "review_assignments"

    id = pk_uuid()
    review_id = fk_uuid("reviews.id", ondelete="CASCADE")
    user_id = fk_uuid("users.id", ondelete="CASCADE")
    assigned_by = fk_uuid("users.id")
    created_at = ts_created()
    revoked_at = ts_nullable()

    __table_args__ = (
        UniqueConstraint("review_id", "user_id",
                         name="uq_review_assignments_review_user"),
        Index("ix_review_assignments_user_id", "user_id"),
        Index("ix_review_assignments_review_id", "review_id"),
    )


class Escalation(Base):
    """User escalation of a Finding — locked Steps 4, 22; F-3.

    NEW TABLE, no locked table amended. Locked Step 4 makes escalation a
    first-class concept ("This requires authorized review", explicitly NOT
    approval) and Step 24 r5 makes it the trigger for Legal availability, but no
    locked table represents it.

    Recorded at FINDING level, preserving the locked user-facing vocabulary
    ("escalate the contract/finding"), and marking every Evaluation under that
    Finding as requiring a decision (F-3, D-3.5 clause d).
    """

    __tablename__ = "escalations"

    id = pk_uuid()
    finding_id = fk_uuid("findings.id", ondelete="CASCADE")
    raised_by = fk_uuid("users.id")
    reason = mapped_column(Text, nullable=False)
    created_at = ts_created()
    withdrawn_at = ts_nullable()

    __table_args__ = (
        Index("ix_escalations_finding_id", "finding_id"),
        Index("ix_escalations_raised_by", "raised_by"),
    )


class AuditEvent(Base):
    """42.18. APPEND-ONLY (AUD-01). actor_id is nullable so pre-authentication
    events (a failed login for an unknown account) can be recorded (Step 47)."""

    __tablename__ = "audit_events"

    id = pk_uuid()
    actor_id = fk_uuid("users.id", nullable=True)
    action = _str()
    entity_type = _str()
    entity_id = mapped_column(UUIDType, nullable=True)
    timestamp = ts_created()
    before_state = jsonb_col()
    after_state = jsonb_col()
    event_metadata = jsonb_col(name="metadata")     # carries request_id (49.9)

    __table_args__ = (
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_entity", "entity_type", "entity_id"),
        Index("ix_audit_events_timestamp", "timestamp"),
    )
