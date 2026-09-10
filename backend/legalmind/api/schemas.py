"""Request bodies.

Pydantic is used for *requests* only — strict validation is what matters on the
way in. Responses are assembled as dicts so confidential fields can be **omitted
rather than nulled** (49.7 r4); see ``envelope.py``.

``extra="forbid"`` throughout: an unrecognised field is a 422, never silently
dropped. A silently ignored ``"required": false`` or ``"threshold": 0`` on a
configuration draft is exactly the class of mistake that would make a Legal
admin believe they had configured something they had not.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from legalmind.domain.client_profile import is_client_status, is_version_role
from legalmind.domain.document_types import is_document_source, is_document_type
from legalmind.domain.enums import (
    ContractStatus,
    DecisionType,
    EvaluatorType,
    RuleType,
    UserStatus,
)


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _validate_contract_type(value: str | None) -> str | None:
    """Locked Step 6 vocabulary, when a type is supplied at all.

    ``None`` stays legal at this boundary — the column is nullable and existing
    rows carry no type. The *requirement* to have one lands at analysis time,
    which refuses rather than evaluating everything (ENG-09); rejecting here
    would only break older clients without closing any gap.
    """
    if value is not None and not is_document_type(value):
        raise ValueError(
            f"unknown document type {value!r}; locked Step 6 defines the "
            "permitted values")
    return value


# ------------------------------------------------------------------ assist
class ConversationCreate(Body):
    """An assist-lane session, optionally scoped to a contract the requester can view."""

    contract_id: str | None = Field(default=None, max_length=64)


class AskRequest(Body):
    """One question, about ONE document version.

    Length-bounded at the boundary; content rules live server-side.

    ``document_version_id`` names the version the question is about — the one the
    reader has open. It is OPTIONAL and defaults to the contract's newest version,
    which is what every caller got before this field existed. Authorization is not
    weakened by naming it: the version is resolved through `guard.document_version`
    and additionally required to belong to the conversation's own contract, so this
    field can only ever narrow the scope, never widen it.
    """

    question: str = Field(min_length=1, max_length=2000)
    document_version_id: str | None = Field(default=None, max_length=64)


# ------------------------------------------------------------------ auth
class LoginRequest(Body):
    """Step 47 fallback password path. S-7: the response is identical for an
    unknown account, a wrong credential and a disabled account, so nothing here
    distinguishes those cases either."""

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


# ------------------------------------------------------------- contracts
class ContractCreate(Body):
    name: str = Field(min_length=1, max_length=500)
    contract_type: str | None = Field(default=None, max_length=200)
    #: Who this deal is with (2026-09-10, Client Profiles). Optional and absent
    #: for every existing caller. It exists so an upload started FROM a client
    #: profile lands linked in one call rather than as create-then-patch, which
    #: would leave an unlinked contract behind whenever the second call failed.
    #: The same AB-13 r2 rule applies as on update: an unknown id is refused
    #: rather than stored, because a dangling link is worse than no link.
    counterparty_id: UUID | None = None

    _contract_type = field_validator("contract_type")(_validate_contract_type)


class ContractUpdate(Body):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    contract_type: str | None = Field(default=None, max_length=200)
    #: AM-50 (2026-09-09): who determined `contract_type` — "HUMAN" (the default,
    #: an explicit choice) or "ASSIST_SUGGESTION" (the intake applied a confident
    #: suggestion so the reader did not have to). Audit-only; never a column.
    contract_type_source: Literal["HUMAN", "ASSIST_SUGGESTION"] | None = None
    status: ContractStatus | None = None
    #: Who this deal is with — AB-13 r2. Sent as null to unlink; left out,
    #: untouched. `model_fields_set` tells the two apart.
    counterparty_id: UUID | None = None

    _contract_type = field_validator("contract_type")(_validate_contract_type)


#: The Client Profile's free-text fields (2026-09-10) — every one optional on
#: both create and update, and every one trimmed to None when blank. Listed once
#: so create and update cannot drift apart, and so the trimming validator below
#: cannot be applied to some of them and forgotten on the rest.
_PROFILE_TEXT_FIELDS: tuple[str, ...] = (
    "legal_name", "website", "city", "state_region", "country",
    "primary_contact_name", "primary_contact_email", "primary_contact_phone",
    "legal_contact_name", "legal_contact_email",
)


def _validate_client_status(value: str | None) -> str | None:
    """`domain.client_profile.CLIENT_STATUSES`, when one is supplied at all.

    ``None`` stays legal: on create the column's own default applies, and on
    update an omitted field means "untouched". A value outside the list is
    refused rather than coerced — a status the list does not know is a filter
    that would quietly match nothing.
    """
    if value is not None and not is_client_status(value):
        raise ValueError(
            f"unknown client status {value!r}; permitted values are "
            "ACTIVE, PROSPECTIVE, INACTIVE")
    return value


class CounterpartyCreate(Body):
    """AB-13 r1's profile, widened by the owner's Client Profiles instruction
    (2026-09-10).

    Only `name` is required — it is the identity, and the owner's instruction
    says so directly ("Company Name should be the primary identifying field").
    Everything else is optional and stays empty unless a human types it: rule
    21 forbids inventing company information, and "not known yet" is the normal
    state of a client, not a gap for the system to fill.
    """
    name: str = Field(min_length=1, max_length=500)
    industry: str | None = Field(default=None, max_length=200)
    relationship_notes: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=40)
    legal_name: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=200)
    state_region: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=200)
    primary_contact_name: str | None = Field(default=None, max_length=200)
    primary_contact_email: str | None = Field(default=None, max_length=320)
    primary_contact_phone: str | None = Field(default=None, max_length=60)
    legal_contact_name: str | None = Field(default=None, max_length=200)
    legal_contact_email: str | None = Field(default=None, max_length=320)
    #: Who inside the organisation owns the relationship. Refused unless the id
    #: names a real user, and the router additionally holds it to the caller's
    #: own department — this field must not become a probe for other
    #: departments' accounts (the rule `contract.transfer` already follows).
    account_owner_id: UUID | None = None

    _status = field_validator("status")(_validate_client_status)

    @field_validator("name", "industry", "relationship_notes",
                     *_PROFILE_TEXT_FIELDS)
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        stripped = value.strip() if value is not None else None
        return stripped or None


class CounterpartyUpdate(Body):
    """Every field optional; a field left out is untouched, and one sent as
    null is cleared. `name` cannot be cleared — a company with no name is not
    an identity anyone can use — and neither can `status`, which is NOT NULL."""
    name: str | None = Field(default=None, min_length=1, max_length=500)
    industry: str | None = Field(default=None, max_length=200)
    relationship_notes: str | None = Field(default=None, max_length=5000)
    status: str | None = Field(default=None, max_length=40)
    legal_name: str | None = Field(default=None, max_length=500)
    website: str | None = Field(default=None, max_length=500)
    city: str | None = Field(default=None, max_length=200)
    state_region: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=200)
    primary_contact_name: str | None = Field(default=None, max_length=200)
    primary_contact_email: str | None = Field(default=None, max_length=320)
    primary_contact_phone: str | None = Field(default=None, max_length=60)
    legal_contact_name: str | None = Field(default=None, max_length=200)
    legal_contact_email: str | None = Field(default=None, max_length=320)
    account_owner_id: UUID | None = None

    _status = field_validator("status")(_validate_client_status)

    @field_validator("name", "industry", "relationship_notes",
                     *_PROFILE_TEXT_FIELDS)
    @classmethod
    def _trim(cls, value: str | None) -> str | None:
        stripped = value.strip() if value is not None else None
        return stripped or None


class DocumentVersionDeclare(Body):
    """Declared facts about one Document Version — Step 2's "should store"
    metadata (Counterparty, Effective date) and Step 6's source axis, kept in
    locked 42.4's `metadata` JSONB. All optional (owner, 2026-09-06). A field
    that is SENT changes the value; sent as null it clears it; a field left out
    is untouched — `model_fields_set` tells the two apart. Declared, never
    inferred: no date is ever read out of the document text."""
    source: str | None = None
    counterparty: str | None = Field(default=None, max_length=500)
    effective_date: date | None = None
    #: What this version IS in the negotiation — COMPANY_DRAFT (what we sent),
    #: CLIENT_MODIFIED (what came back), FINAL_SIGNED (what was executed).
    #: Owner's Client Profiles instruction, 2026-09-10.
    #:
    #: ⚠️ A THIRD axis, not a synonym for `source`. `source` says whose paper it
    #: is and is what the evaluator reasons about; this says where in the
    #: negotiation it sits and is filing only. In particular FINAL_SIGNED is not
    #: "the counterparty's version" and CLIENT_MODIFIED is emphatically not the
    #: signed one — the owner named that confusion as the thing to avoid.
    version_role: str | None = None

    @field_validator("version_role")
    @classmethod
    def _version_role(cls, value: str | None) -> str | None:
        if value is not None and not is_version_role(value):
            raise ValueError(
                f"unknown version role {value!r}; permitted values are "
                "COMPANY_DRAFT, CLIENT_MODIFIED, FINAL_SIGNED")
        return value

    @field_validator("source")
    @classmethod
    def _source(cls, value: str | None) -> str | None:
        if value is not None and not is_document_source(value):
            raise ValueError(
                f"unknown document source {value!r}; locked Step 6 names "
                "ORGANIZATION or COUNTERPARTY")
        return value

    @field_validator("counterparty")
    @classmethod
    def _counterparty(cls, value: str | None) -> str | None:
        # Whitespace-only is "nothing declared", not a counterparty called " ".
        stripped = value.strip() if value is not None else None
        return stripped or None


# --------------------------------------------------------------- reviews
class ReviewCreate(Body):
    """49.8 — creation is idempotent on the document version plus the
    configuration snapshot."""

    document_version_id: UUID
    configuration_snapshot_id: UUID


# -------------------------------------------------------------- findings
class EscalationCreate(Body):
    """Locked Step 4: an escalation means "this requires authorized review", NOT
    "I approve this deviation" — which is why it carries a reason and no
    disposition."""

    reason: str = Field(min_length=1, max_length=4000)


# ------------------------------------------------------------- decisions
class DecisionCreate(Body):
    """49.7 — supersession is a create, never an update.

    ``expected_version`` is the whole concurrency mechanism (N-1 Option C): the
    server writes ``expected_version + 1``, and a collision surfaces as 409
    through ``UNIQUE(evaluation_id, version_number)``. There is no ETag.
    """

    decision_type: DecisionType
    justification: str = Field(min_length=1, max_length=20000)
    expected_version: int | None = Field(default=None, ge=0)
    # Step 31 r15 / F-2. Whether a Requirement demands independent second-person
    # approval is Legal Configuration; until a configuration key for it is
    # specified, the caller states it and the server enforces co-signature.
    requires_second_person: bool = False


# --------------------------------------------------------- configuration
class RequirementCreate(Body):
    code: str = Field(min_length=1, max_length=100)


class RequirementVersionCreate(Body):
    """One draft version of a Requirement together with the configuration
    artifacts a snapshot needs (42.12 makes the company standard, mapping rules
    and evaluation rules NOT NULL in a snapshot item).

    Every ``configuration`` payload is accepted **opaquely**. LegalMind must never
    invent a legal threshold, tolerance or carve-out (rule 7/21), so this endpoint
    validates structure and provenance and nothing about legal content; the
    evaluators validate their own inputs at evaluation time and fail closed
    (ENG-09) when something they need is absent.
    """

    name: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20000)
    evaluator_type: EvaluatorType
    company_standard: dict[str, Any]
    mapping_rules: dict[str, Any]
    evaluation_rules: dict[str, Any]
    legal_rule: LegalRuleDraft | None = None


class LegalRuleDraft(Body):
    """Optional per Requirement — locked Step 20 r4: not every Clause requires a
    Pre-approved Legal Rule."""

    rule_type: RuleType
    configuration: dict[str, Any]


class CompanyStandardUpdate(Body):
    """Update a Requirement's Company Standard — by APPENDING, never editing.

    Locked rule 16: existing versions are never modified, which is what keeps a
    historical Review reproducible. This endpoint gives an admin the experience
    of "edit the value and save" while the mechanics append a new Requirement
    version carrying the previous mapping/evaluation/legal-rule artifacts
    forward unchanged. Rollback is the same operation with an older version's
    values. ``reason`` is mandatory — a standard change is a legal-position
    change, and the audit trail must say why.
    """

    company_standard: dict[str, Any]
    reason: str = Field(min_length=1, max_length=2000)


class ConfigurationPublish(Body):
    """Step 29 — publishing produces an immutable snapshot. Drafts never affect
    an existing Review (rule 16)."""

    requirement_codes: list[str] | None = Field(default=None, max_length=1000)


# ------------------------------------------------------ administration
class UserCreate(Body):
    """47.1.3 account resolution r3 — LegalMind does not self-provision. An
    account exists only because an authorized administrator created it, so its
    roles are always assigned deliberately and never inferred from a login.

    ``department_id`` and ``role_code`` are optional and change nothing about
    that: naming a role here still runs S-8, so an administrator can only start
    an account with authority they already hold themselves.
    """

    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)
    department_id: UUID | None = None
    role_code: str | None = Field(default=None, max_length=100)


class UserUpdate(Body):
    """`department_id` (AB-12 r3): present-and-null clears the department,
    absent leaves it alone — the router reads `model_fields_set` to tell the
    two apart, because both arrive here as ``None``."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: UserStatus | None = None
    department_id: UUID | None = None


class DepartmentCreate(Body):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class DepartmentUpdate(Body):
    """The name only — the code identifies the boundary in an append-only audit
    trail and does not change."""

    name: str = Field(min_length=1, max_length=200)


class ContractTransfer(Body):
    """AB-12 r5 — move a contract to a colleague in the same department. The
    reason is mandatory: a transfer is a custody change and the audit row
    should say why without anyone having to ask."""

    new_owner_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


class RoleGrant(Body):
    role_code: str = Field(min_length=1, max_length=100)


class RoleCreate(Body):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class RoleUpdate(Body):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    permissions: list[str] | None = Field(default=None, max_length=200)


RequirementVersionCreate.model_rebuild()
