"""Client-profile vocabularies — owner instruction, 2026-09-10.

Two controlled lists, both held here as code rather than as database enums, for
the reason `document_types.py` records at length: a controlled vocabulary
validated in tested code costs no migration to correct, and the locked physical
schema (42.x) defines no type for either of them.

Neither list is a legal vocabulary. **Neither may ever share a field with one of
the five legal-domain state axes** (`DECISION_STATE_MODEL.md`): a client's
relationship status is not a Review Lifecycle, and a version's role is not a
Finding Classification. They describe filing, not law.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Client status — the relationship state, in a non-legal reader's words.
# --------------------------------------------------------------------------
# Three values and no more. A fourth ("Churned", "On hold", …) is a CRM
# gradation, and the owner's instruction is explicit that Client Profiles is not
# a CRM: it exists to organise legal documents under the company they belong to.
CLIENT_STATUSES: tuple[str, ...] = (
    "ACTIVE",        # a live relationship
    "PROSPECTIVE",   # in discussion; paper may exist, the relationship is not signed
    "INACTIVE",      # dormant or ended — documents stay, profile stops being current
)

_CLIENT_STATUS_SET = frozenset(CLIENT_STATUSES)


class UnknownClientStatus(ValueError):
    """A value outside the list above. Raised, never coerced — the same posture
    `UnknownDocumentType` takes, for the same reason: a near-miss silently
    accepted becomes a filter that quietly matches nothing."""


def is_client_status(value: object) -> bool:
    return isinstance(value, str) and value in _CLIENT_STATUS_SET


def validate_client_status(value: object) -> str:
    if not is_client_status(value):
        raise UnknownClientStatus(
            f"unknown client status {value!r}; permitted values are: "
            + ", ".join(CLIENT_STATUSES))
    return value  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Version role — what THIS version of a document is, in the negotiation.
# --------------------------------------------------------------------------
# The owner's three named concepts. Stored in locked 42.4's `metadata` JSONB
# beside `source`/`counterparty`/`effective_date` — the `D-3` route owner
# decision Q2 chose, so no column and no migration.
#
# ⚠️ This is a THIRD axis, deliberately distinct from Step 6's `source`
# (ORGANIZATION / COUNTERPARTY), and the two must not be collapsed:
#
#   * `source` answers "whose paper is this?" — it is what the evaluator and the
#     calibration work reason about.
#   * `version_role` answers "where in the negotiation is this?" — filing.
#
# Collapsing them would lose exactly the distinction the owner asked for: a
# FINAL_SIGNED version is not thereby the counterparty's paper, and a
# CLIENT_MODIFIED version is emphatically NOT the signed one. Nothing here is
# ever inferred — a human declares it, exactly as they declare `source`.
VERSION_ROLES: tuple[str, ...] = (
    "COMPANY_DRAFT",    # what we sent
    "CLIENT_MODIFIED",  # what came back
    "FINAL_SIGNED",     # what was executed
)

_VERSION_ROLE_SET = frozenset(VERSION_ROLES)


class UnknownVersionRole(ValueError):
    """A value outside the list above."""


def is_version_role(value: object) -> bool:
    return isinstance(value, str) and value in _VERSION_ROLE_SET


def validate_version_role(value: object) -> str:
    if not is_version_role(value):
        raise UnknownVersionRole(
            f"unknown version role {value!r}; permitted values are: "
            + ", ".join(VERSION_ROLES))
    return value  # type: ignore[return-value]
