"""SQLAlchemy models — the locked LegalMind schema.

Sources: Step 42 (exact schema), Step 41 (design), Amendment Batch AB-1,
Step 47 (security). Each table cites the locked decision that fixes it.

Do not add, drop or retype a column here without an approved amendment.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import mapped_column

from legalmind.db.base import (
    TS,
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
class Department(Base):
    """The organisational boundary a Department Lead's oversight is scoped to —
    AB-12 r3 (2026-09-05). NEW TABLE, authorised by that record.

    Why a table and not a string on the user: the Lead's scope is a security
    boundary, and a boundary defined by matching free text is one typo away from
    either leaking or silently shrinking. A row with a unique code is something an
    administrator creates once and assigns deliberately.
    """

    __tablename__ = "departments"

    id = pk_uuid()
    code = mapped_column(String, nullable=False, unique=True)
    name = _str()
    created_at = ts_created()


class User(Base):
    """42.2. No credential or provider columns — see UserIdentity (Step 47).

    `department_id` (AB-12 r3) is nullable: an account outside any department has
    exactly its own contracts in scope, and `department.view` widens nothing for
    it. There is no "everyone" department and no global scope.
    """

    __tablename__ = "users"

    id = pk_uuid()
    email = mapped_column(String, nullable=False, unique=True)
    name = _str()
    status = mapped_column(_enum(E.UserStatus, "user_status"), nullable=False)
    department_id = fk_uuid("departments.id", nullable=True, ondelete="RESTRICT")
    created_at = ts_created()
    updated_at = ts_updated()

    __table_args__ = (
        Index("ix_users_department_id", "department_id"),
    )


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
    expires_at = mapped_column(TS, nullable=False)
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
    provider = mapped_column(_enum(E.IdentityProvider, "identity_provider"),
                             nullable=False)
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
class Counterparty(Base):
    """The company on the other side of a deal — AB-13 r1 (2026-09-06). NEW TABLE,
    authorised by that record.

    Why a table and not the free text Phase 3 already stores: that text is a
    DECLARATION about one version and carries no identity, so "Acme Ltd" and
    "Acme Limited" are two unrelated strings — nothing can be grouped by them and
    no attribute can hang off them. Identity is the whole point of this row.

    `industry` and `relationship_notes` are nullable and stay empty unless a human
    types them (r1): rule 21 forbids inventing company or industry information,
    and "not known yet" is the normal state of a counterparty, not a gap to fill.
    """

    __tablename__ = "counterparties"

    id = pk_uuid()
    name = _str()
    industry = _str(nullable=True)
    relationship_notes = mapped_column(Text, nullable=True)
    created_by = fk_uuid("users.id")
    created_at = ts_created()
    updated_at = ts_updated()

    # ------------------------------------------------------------------
    # Client Profile (owner, 2026-09-10) — migration e9f2b6c4a173.
    #
    # The profile screen's fields, and only those. Every one is NULLABLE and
    # stays empty unless a human types it: rule 21's discipline, applied to
    # company data. The serializer OMITS an empty field rather than nulling it,
    # so the screen can honestly say "Not available" instead of rendering a
    # dash that looks like something was checked.
    #
    # What is deliberately NOT here: anything a CRM would add. No pipeline, no
    # revenue, no activity scoring, no contact table. The owner's instruction
    # names that boundary explicitly, and a second contact is a schema decision
    # nobody has asked for.
    # ------------------------------------------------------------------
    #: The registered entity name, where it differs from the one people use.
    legal_name = _str(nullable=True)
    #: ACTIVE / PROSPECTIVE / INACTIVE — `domain.client_profile.CLIENT_STATUSES`.
    #: A validated string, not a PG enum (see that module, and `document_types`).
    #: NOT NULL with a server default, so a row inserted without it is still valid.
    status = mapped_column(String, nullable=False, server_default=text("'ACTIVE'"))
    website = _str(nullable=True)
    city = _str(nullable=True)
    state_region = _str(nullable=True)
    country = _str(nullable=True)
    primary_contact_name = _str(nullable=True)
    primary_contact_email = _str(nullable=True)
    primary_contact_phone = _str(nullable=True)
    legal_contact_name = _str(nullable=True)
    legal_contact_email = _str(nullable=True)
    #: Who inside the organisation owns this relationship. SET NULL on delete —
    #: a departed colleague must not make a client unmaintainable.
    account_owner_id = fk_uuid("users.id", nullable=True, ondelete="SET NULL")
    # `AM-286` r1 — the client's legal details, typed by a person, never inferred; the
    # CIN/LLPIN, PAN and GSTIN shapes are checked by the API schema (r3), not here.
    entity_type = _str(nullable=True)
    cin_or_llpin = _str(nullable=True)
    pan = _str(nullable=True)
    gstin = _str(nullable=True)
    registered_office = _str(nullable=True)
    notice_address = _str(nullable=True)
    notice_email = _str(nullable=True)
    signatory_name = _str(nullable=True)
    signatory_designation = _str(nullable=True)
    authority_reference = _str(nullable=True)

    __table_args__ = (
        Index("ix_counterparties_name", "name"),
        Index("ix_counterparties_status", "status"),
        Index("ix_counterparties_account_owner_id", "account_owner_id"),
    )


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
    # Archive marker — AB-12 r6 (the column AM-37 added as `deleted_at`). NOT a
    # sixth value on ContractStatus: that enum is the locked 42.3 / Step 2
    # vocabulary and archiving is a visibility state orthogonal to lifecycle.
    # Nothing is ever destroyed: an archived contract keeps its document,
    # versions, reviews, findings and audit trail, leaves every default list,
    # refuses every write, and stays readable by its owner and department lead.
    archived_at = ts_nullable()
    # Who this deal is WITH — AB-13 r2. Nullable: every contract predating this
    # record has none, and inventing one would be inventing data. The link is the
    # live identity; `document_versions.metadata.counterparty` stays the frozen
    # per-version declaration (r7), and the two answer different questions.
    counterparty_id = fk_uuid("counterparties.id", nullable=True, ondelete="RESTRICT")
    #: `AM-287` r1 — which brand issues this contract, chosen by a person; null for
    #: every contract before it (never inferred, r5).
    issuing_entity = mapped_column(String(16), nullable=True)
    #: `AM-267`/`AM-309` — the signed contract an AMENDMENT (or ORDER_FORM) amends: one
    #: parent pointer, RESTRICT; the rule (parent signed, never an amendment, the same
    #: client) is the trigger `legalmind_contract_governed_by`, whoever writes the row.
    governed_by_contract_id = fk_uuid("contracts.id", nullable=True, ondelete="RESTRICT")

    __table_args__ = (
        CheckConstraint("issuing_entity IN ('LEAPSWITCH', 'CLOUDPE')",
                        name="issuing_entity"),
        Index("ix_contracts_owner_id", "owner_id"),
        Index("ix_contracts_governed_by_contract_id", "governed_by_contract_id"),
        Index("ix_contracts_counterparty_id", "counterparty_id"),
        Index("ix_contracts_status", "status"),
        Index("ix_contracts_created_at", "created_at"),
        Index("ix_contracts_archived_at", "archived_at"),
    )


class DocumentVersion(Base):
    """42.4. Immutable once created (Step 26). file_hash is indexed but NOT
    unique — the same source file may legitimately appear in multiple
    contracts."""

    __tablename__ = "document_versions"

    id = pk_uuid()
    # CASCADE — AM-55: deleting the Contract deletes every version with it.
    contract_id = fk_uuid("contracts.id", ondelete="CASCADE")
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
    #: `AM-260` r4 — when this version went to the client and who sent it; written once.
    sent_at = ts_nullable()
    sent_by = fk_uuid("users.id", nullable=True)

    __table_args__ = (
        UniqueConstraint("contract_id", "version_number",
                         name="uq_document_versions_contract_version"),
        CheckConstraint("(sent_at IS NULL) = (sent_by IS NULL)", name="sent"),
        Index("ix_document_versions_contract_id", "contract_id"),
        Index("ix_document_versions_file_hash", "file_hash"),
        Index("ix_document_versions_uploaded_by", "uploaded_by"),
        Index("ix_document_versions_processing_status", "processing_status"),
    )


class DocumentProcessingRun(Base):
    """42.5. Attempt history is preserved, never overwritten."""

    __tablename__ = "document_processing_runs"

    id = pk_uuid()
    document_version_id = fk_uuid("document_versions.id", ondelete="CASCADE")
    run_type = mapped_column(_enum(E.ProcessingRunType, "processing_run_type"),
                             nullable=False)
    status = mapped_column(_enum(E.ProcessingRunStatus, "processing_run_status"),
                           nullable=False)
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
    document_version_id = fk_uuid("document_versions.id", ondelete="CASCADE")
    processing_run_id = fk_uuid("document_processing_runs.id", ondelete="CASCADE")
    page_number = mapped_column(Integer, nullable=True)
    section_number = _str(nullable=True)
    section_title = _text()
    content = mapped_column(Text, nullable=False)
    source_type = mapped_column(_enum(E.EvidenceSourceType, "evidence_source_type"),
                                nullable=False)
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
    evaluator_type = mapped_column(_enum(E.EvaluatorType, "evaluator_type"),
                                   nullable=False)
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
    contract_id = fk_uuid("contracts.id", ondelete="CASCADE")
    document_version_id = fk_uuid("document_versions.id", ondelete="CASCADE")
    configuration_snapshot_id = fk_uuid("configuration_snapshots.id")
    status = mapped_column(_enum(E.ReviewStatus, "review_status"), nullable=False)
    created_by = fk_uuid("users.id")
    created_at = ts_created()
    started_at = ts_nullable()
    completed_at = ts_nullable()
    #: AM-175 (2026-10-22): set when a finished Review reopened because a point needs work
    #: again; the stage reads it against the latest contract decision. Never cleared.
    reopened_at = ts_nullable()

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
    review_id = fk_uuid("reviews.id", ondelete="CASCADE")
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
    finding_id = fk_uuid("findings.id", ondelete="CASCADE")
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

    finding_id = fk_uuid("findings.id", primary_key=True, ondelete="CASCADE")
    evidence_id = fk_uuid("document_evidence.id", primary_key=True, ondelete="CASCADE")
    relationship_type = mapped_column(
        _enum(E.EvidenceRelationshipType, "evidence_relationship_type"), nullable=False)


class EvaluationEvidence(Base):
    """AB-1.5 — per-scope evidence attribution.

    NO minimum-row constraint. Zero rows is a VALID state: a MISSING arising
    from established absence legitimately carries no evidence (45C.15, N-34).
    Synthetic evidence must never be created to satisfy a cardinality rule.
    """

    __tablename__ = "evaluation_evidence"

    evaluation_id = fk_uuid("evaluations.id", primary_key=True, ondelete="CASCADE")
    evidence_id = fk_uuid("document_evidence.id", primary_key=True, ondelete="CASCADE")
    relationship_type = mapped_column(
        _enum(E.EvidenceRelationshipType, "evidence_relationship_type"), nullable=False)


class SemanticRecognitionCache(Base):
    """Memoizes an `AM-54` RECOGNITION verdict (`analysis/semantic.adjudicate`) —
    NOT an assist-lane table (it feeds Mapping State, and through it Finding
    classification, so `AM-27` r1's separate schema is for the assistive
    Ask/RAG lane and does not apply here).

    Live incident, 2026-09-22: the byte-identical NDA, re-uploaded and
    re-analyzed under the SAME configuration snapshot, got a different
    Gemini verdict on whether a clause addressed a Requirement — a real
    violation of rule 9's determinism guarantee, since `generate_raw` sets
    `temperature: 0.0` but a hosted model is not bit-reproducible on that
    alone. Keyed on the exact prompt text sent (hashed), the model that
    answered it, and the configuration snapshot it was asked under: a repeat
    analysis of the same content under the same snapshot AND the same pinned
    model reuses the recorded verdict rather than asking again. `model` is in
    the key, not just stored, because `MAPPING_PROMPT_VERSION` is a hardcoded
    constant independent of `LEGALMIND_GENERATION_MODEL` — an operator
    upgrading the pinned model (AM-30 t7) with no reason to also bump the
    prompt version must not have this cache silently keep serving the
    previous model's verdicts. UNIQUE on the key so a concurrent analysis
    race writes at most one row per (snapshot, prompt, model).
    """

    __tablename__ = "semantic_recognition_cache"

    id = pk_uuid()
    configuration_snapshot_id = fk_uuid("configuration_snapshots.id", ondelete="CASCADE")
    prompt_version = _str()
    prompt_sha256 = mapped_column(String(64), nullable=False)
    model = _str()
    response_text = mapped_column(Text, nullable=False)
    payload_sha256 = _str()
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("configuration_snapshot_id", "prompt_version", "prompt_sha256",
                         "model", name="uq_semantic_recognition_cache_key"),
    )


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
    finding_id = fk_uuid("findings.id", ondelete="CASCADE")
    evaluation_id = fk_uuid("evaluations.id", ondelete="CASCADE")
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
            ondelete="CASCADE",
        ),
        Index("ix_legal_decisions_evaluation_version",
              "evaluation_id", "version_number"),
        Index("ix_legal_decisions_decided_by", "decided_by"),
        Index("ix_legal_decisions_created_at", "created_at"),
    )


_OUTCOME = _enum(E.ContractOutcome, "contract_outcome")


class ContractOutcomeRecord(Base):
    """AM-174 — the reviewer's decision on the whole contract, after every point.

    APPEND-ONLY like ``legal_decisions``: the current outcome is the highest
    version_number; a change of mind is a new row. ``suggested`` is what the code
    proposed from the point decisions at that moment, kept beside what the person chose.
    """

    __tablename__ = "contract_outcomes"

    id = pk_uuid()
    review_id = fk_uuid("reviews.id", ondelete="CASCADE")
    outcome = mapped_column(_OUTCOME, nullable=False)
    suggested = mapped_column(_OUTCOME, nullable=False)
    justification = mapped_column(Text, nullable=False)
    decided_by = fk_uuid("users.id")
    version_number = mapped_column(Integer, nullable=False)
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("review_id", "version_number",
                         name="uq_contract_outcomes_review_version"),
    )


class UnmatchedProvision(Base):
    """AB-1.5 / REC-02. A document-level observation, NOT a Finding
    classification. Must never occupy a Finding's classification field."""

    __tablename__ = "unmatched_provisions"

    id = pk_uuid()
    review_id = fk_uuid("reviews.id", ondelete="CASCADE")
    evidence_id = fk_uuid("document_evidence.id", ondelete="CASCADE")
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
        # At most one ACTIVE escalation per Finding (43.28's idempotence, held by
        # the database since decision 339, 2026-09-29). History keeps every
        # withdrawn row. Migration c2d4e6f8a1b3.
        Index("uq_escalations_one_active", "finding_id", unique=True,
              postgresql_where="withdrawn_at IS NULL"),
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


class ComparisonChoice(Base):
    """A reader's drafting choice on one Diff-Talk difference — AB-81 / `AM-136`
    (2026-10-13), migration d3f7a1c9e5b2. NEW TABLE, authorised by that record.

    About WORDING only: never a Finding, Classification, Rule Outcome, Legal Decision
    or Review state (r2). APPEND-ONLY since `AM-253` r5' (migration f7c2a9e4b1d6): each
    answer is a new row, the current one the highest `version_number`, with who, when
    and an optional one-line `reason`; a cascade from a deleted version still passes
    (`AM-176` r1). A side is a document version or a website key — exactly one, by a
    CHECK. Not a relationship between documents: AB-13 r3 stands (r2).
    """

    __tablename__ = "comparison_choices"

    id = pk_uuid()
    left_version_id = fk_uuid("document_versions.id", nullable=True, ondelete="CASCADE")
    left_key = mapped_column(String(64), nullable=True)
    right_version_id = fk_uuid("document_versions.id", nullable=True, ondelete="CASCADE")
    right_key = mapped_column(String(64), nullable=True)
    row_key = mapped_column(String(200), nullable=False)
    choice = mapped_column(String(8), nullable=False)
    decided_by = fk_uuid("users.id")
    created_at = ts_created()
    updated_at = ts_updated()
    version_number = mapped_column(Integer, nullable=False, server_default=text("1"))
    reason = mapped_column(Text, nullable=True)
    # `AM-285` r1 (migration b4d1f8a2c6e3): "use our standard" pins the published clause;
    # "write our wording" keeps the typed text and its SHA-256 (the hash its Legal
    # Decision carries, `AM-284` r2); the two notes — client_note goes to the client as a
    # Word comment, internal_note never leaves LegalMind (r3: omitted, never nulled)
    clause_version_id = fk_uuid("clause_versions.id", nullable=True, ondelete="RESTRICT")
    wording = mapped_column(Text, nullable=True)
    wording_sha256 = mapped_column(String(64), nullable=True)
    client_note = mapped_column(Text, nullable=True)
    internal_note = mapped_column(Text, nullable=True)

    __table_args__ = (
        # AM-290 r2: a client-paper-first row (`N|THEIRS|…`) may have no left side
        CheckConstraint("num_nonnulls(left_version_id, left_key) = 1 OR "
                        "(num_nonnulls(left_version_id, left_key) = 0 "
                        "AND row_key LIKE 'N|THEIRS|%')",
                        name="left_side"),
        CheckConstraint("num_nonnulls(right_version_id, right_key) = 1",
                        name="right_side"),
        CheckConstraint("choice IN ('ours', 'theirs', 'standard', 'custom')",
                        name="choice"),
        CheckConstraint("char_length(reason) <= 200", name="reason"),
        CheckConstraint("choice <> 'standard' OR clause_version_id IS NOT NULL",
                        name="standard_clause"),
        CheckConstraint("choice <> 'custom' OR (wording IS NOT NULL "
                        "AND wording_sha256 IS NOT NULL)", name="custom_wording"),
        CheckConstraint("char_length(wording) <= 5000 AND char_length(client_note) "
                        "<= 500 AND char_length(internal_note) <= 1000",
                        name="note_lengths"),
        # The read index too: every read names a pair (see the migration).
        UniqueConstraint("right_version_id", "right_key", "left_version_id", "left_key",
                         "row_key", "version_number",
                         name="uq_comparison_choices_pair_row_version",
                         postgresql_nulls_not_distinct=True),
        Index("ix_comparison_choices_left_version_id", "left_version_id",
              postgresql_where=text("left_version_id IS NOT NULL")),
    )


class ContractCollaborator(Base):
    """`AM-259` r1 (AB-150, 2026-11-02), migration f7c2a9e4b1d6 — a colleague who may
    answer a contract's changes beside its owner, and read that contract (`AM-280`,
    amending r3); archive, delete and transfer stay with the owner and the Lead."""

    __tablename__ = "contract_collaborators"

    contract_id = fk_uuid("contracts.id", ondelete="CASCADE", primary_key=True)
    user_id = fk_uuid("users.id", ondelete="CASCADE", primary_key=True)
    added_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (Index("ix_contract_collaborators_user_id", "user_id"),)


class Notification(Base):
    """`AM-273` m3 (AB-150), migration f7c2a9e4b1d6 — an in-app notification: a fixed
    `kind` and a `link` resolved through normal authorization, never clause text, a
    position or a counterparty name."""

    __tablename__ = "notifications"

    id = pk_uuid()
    user_id = fk_uuid("users.id", ondelete="CASCADE")
    kind = mapped_column(String(64), nullable=False)
    contract_id = fk_uuid("contracts.id", nullable=True, ondelete="CASCADE")
    link = mapped_column(Text, nullable=False)
    created_at = ts_created()
    read_at = ts_nullable()

    __table_args__ = (
        Index("ix_notifications_user_id_created_at", "user_id", text("created_at DESC")),
        Index("ix_notifications_contract_id", "contract_id",
              postgresql_where=text("contract_id IS NOT NULL")),
    )


# ---------------------------------------------------------------------------
# Clause library, templates and generated drafts — `AM-279` (AB-150, 2026-11-02)
# collects the tables; `AM-265` d1 fixes `draft_answers`; migration a3c9e7f1b5d2.
# A clause or template version is FROZEN once it leaves DRAFT (trigger
# `legalmind_frozen_once_approved`): only its status may move, forward, and the approval
# columns be written with that move. A draft record is insert-only (append-only trigger,
# a cascade from its contract passing — `AM-176` r1).
# ---------------------------------------------------------------------------
class ClauseVersion(Base):
    """One approved-or-not version of one clause of the library: a Block tree whose text
    is fixed except its ``{var}`` / ``{xref:key}`` slots (`drafting.model`)."""

    __tablename__ = "clause_versions"

    id = pk_uuid()
    clause_key = mapped_column(String(40), nullable=False)
    version = mapped_column(Integer, nullable=False)
    status = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    title = mapped_column(Text, nullable=False)
    body = jsonb_col(nullable=False)
    #: what the clause is FOR: Constitution section + requirement codes
    realises = jsonb_col(nullable=False)
    stance = mapped_column(String(16), nullable=True)
    #: who supplied the text, from which file (sha256) and approval reference (`AM-272`)
    source = jsonb_col(nullable=False)
    content_hash = mapped_column(String(64), nullable=False)
    created_by = fk_uuid("users.id")
    approved_by = fk_uuid("users.id", nullable=True)
    approved_at = ts_nullable()
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("clause_key", "version", name="uq_clause_versions_key_version"),
        CheckConstraint("status IN ('DRAFT', 'APPROVED', 'RETIRED')", name="status"),
        CheckConstraint("stance IN ('NON_NEGOTIABLE', 'PREFERRED', 'FLEXIBLE')",
                        name="stance"),
        CheckConstraint("(status = 'DRAFT') OR (approved_by IS NOT NULL)",
                        name="approved"),
    )


class TemplateVersion(Base):
    """One version of one contract template: ordered clause pins, variables, annexures,
    brand assets. One PUBLISHED version per key (partial unique index); a contract in
    progress stays pinned to the version it was drafted from."""

    __tablename__ = "template_versions"

    id = pk_uuid()
    template_key = mapped_column(String(64), nullable=False)
    version = mapped_column(Integer, nullable=False)
    status = mapped_column(String(16), nullable=False, server_default=text("'DRAFT'"))
    doc_type = mapped_column(String(32), nullable=False)
    brand = mapped_column(String(32), nullable=True)
    #: title, short title, preamble, parties, recitals, execution, check values
    layout = jsonb_col(nullable=False)
    #: [{clause_key, version, when?}]
    clauses = jsonb_col(nullable=False)
    #: [{key, type, group, class M|O|C|AO, when, allowed|range|locked_value, help}]
    variables = jsonb_col(nullable=False)
    annexures = jsonb_col(nullable=False)
    #: {"logo:<BRAND>" | name: {media_type, sha256, data_b64, alt}}
    assets = jsonb_col(nullable=False)
    source = jsonb_col(nullable=False)
    content_hash = mapped_column(String(64), nullable=False)
    #: the configuration snapshot the publish check ran against (`drafting.publish`)
    checked_snapshot_id = fk_uuid("configuration_snapshots.id", nullable=True)
    created_by = fk_uuid("users.id")
    approved_by = fk_uuid("users.id", nullable=True)
    approved_at = ts_nullable()
    published_by = fk_uuid("users.id", nullable=True)
    published_at = ts_nullable()
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("template_key", "version",
                         name="uq_template_versions_key_version"),
        CheckConstraint("status IN ('DRAFT', 'APPROVED', 'PUBLISHED', 'RETIRED')",
                        name="status"),
        CheckConstraint("(status <> 'PUBLISHED') OR (checked_snapshot_id IS NOT NULL "
                        "AND published_by IS NOT NULL)", name="published"),
        Index("uq_template_versions_one_published", "template_key", unique=True,
              postgresql_where=text("status = 'PUBLISHED'")),
    )


class ContractDraft(Base):
    """A contract version LegalMind generated: which template version, the answers,
    the model hash (the determinism key) and the tools that made the files."""

    __tablename__ = "contract_drafts"

    id = pk_uuid()
    contract_id = fk_uuid("contracts.id", ondelete="CASCADE")
    document_version_id = fk_uuid("document_versions.id", ondelete="CASCADE")
    template_version_id = fk_uuid("template_versions.id")
    values = jsonb_col(nullable=False)
    model_hash = mapped_column(String(64), nullable=False)
    renderer_version = mapped_column(String(64), nullable=False)
    libreoffice_version = mapped_column(String(128), nullable=True)
    clean_storage_key = mapped_column(Text, nullable=True)
    pdf_storage_key = mapped_column(Text, nullable=True)
    created_by = fk_uuid("users.id")
    created_at = ts_created()

    __table_args__ = (
        UniqueConstraint("document_version_id",
                         name="uq_contract_drafts_document_version_id"),
        Index("ix_contract_drafts_contract_id", "contract_id"),
    )


class DraftAnswers(Base):
    """`AM-265` d1 — a person's answers before "Save as v1": not a contract (d2), the
    owner's (and collaborators') only, swept after ``expires_at`` (d3)."""

    __tablename__ = "draft_answers"

    id = pk_uuid()
    template_version_id = fk_uuid("template_versions.id")
    counterparty_id = fk_uuid("counterparties.id", nullable=True, ondelete="SET NULL")
    answers = jsonb_col(nullable=False)
    owner_id = fk_uuid("users.id")
    created_by = fk_uuid("users.id")
    created_at = ts_created()
    updated_at = ts_updated()
    expires_at = mapped_column(TS, nullable=False)
    #: the `expected_version` a PATCH must name (N-1 Option C)
    version = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (Index("ix_draft_answers_owner_id", "owner_id"),)


class Execution(Base):
    """`AM-292` / `AM-297` — how a contract was executed: stamp duty, who signed and
    their authority, the signed copy. APPEND-ONLY: each save is a new row, the current
    record the highest ``version_number``; the row carrying ``signed_at`` is the last.
    Everything here is what a person recorded — no duty, article or rate is computed."""

    __tablename__ = "executions"

    id = pk_uuid()
    contract_id = fk_uuid("contracts.id", ondelete="RESTRICT")
    version_number = mapped_column(Integer, nullable=False)
    stamp_method = mapped_column(String(16), nullable=True)
    stamp_reference = _text()
    stamp_state = _text()
    duty_paid = _text()
    stamped_on = mapped_column(Date, nullable=True)
    not_stamped_ack_by = fk_uuid("users.id", nullable=True, ondelete="RESTRICT")
    signatories = jsonb_col(nullable=False)
    seal_used = mapped_column(Boolean, nullable=True)
    witnesses = jsonb_col()
    signed_document_version_id = fk_uuid("document_versions.id", nullable=True,
                                         ondelete="RESTRICT")
    differences_accepted_by = fk_uuid("users.id", nullable=True, ondelete="RESTRICT")
    differences_reason = _text()
    comparison = jsonb_col()
    signed_at = ts_nullable()
    recorded_by = fk_uuid("users.id", ondelete="RESTRICT")
    created_at = ts_created()
    #: `AM-298`: IN_LEGALMIND (closed by "Mark signed") or SIGNED_OUTSIDE (filed signed)
    origin = mapped_column(String(16), nullable=False,
                           server_default=text("'IN_LEGALMIND'"))

    __table_args__ = (
        UniqueConstraint("contract_id", "version_number",
                         name="uq_executions_contract_version"),
    )
