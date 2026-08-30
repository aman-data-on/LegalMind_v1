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

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from legalmind.domain.document_types import is_document_type
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
    """One question. Length-bounded at the boundary; content rules live server-side."""

    question: str = Field(min_length=1, max_length=2000)


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

    _contract_type = field_validator("contract_type")(_validate_contract_type)


class ContractUpdate(Body):
    name: str | None = Field(default=None, min_length=1, max_length=500)
    contract_type: str | None = Field(default=None, max_length=200)
    status: ContractStatus | None = None

    _contract_type = field_validator("contract_type")(_validate_contract_type)


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
    roles are always assigned deliberately and never inferred from a login."""

    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)


class UserUpdate(Body):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: UserStatus | None = None


class RoleGrant(Body):
    role_code: str = Field(min_length=1, max_length=100)


class RoleCreate(Body):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class RoleUpdate(Body):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    permissions: list[str] | None = Field(default=None, max_length=200)


RequirementVersionCreate.model_rebuild()
