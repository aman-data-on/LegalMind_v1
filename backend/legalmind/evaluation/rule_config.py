"""`rule_configuration` — locked J-5 minimum shape.

Locked 44.29 is the governing constraint: configuration controls "thresholds,
allowed values, patterns, terminology, rule parameters"; Python controls
"comparison semantics ... conflict detection mechanics". Nothing here is an
expression, DSL or callable — an admin-editable rule language would put legal
evaluation logic outside tested code and destroy the ENG-10 guarantee.

**Every absence is a fail-closed instruction, never a default** (ENG-09, 45C.22,
45C.23):

    no precedence_rules   -> CONFLICT              (never pick a winner)
    no conversion_rules   -> UNABLE_TO_EVALUATE    (never convert)
    scope unknown + scope_required -> UNABLE_TO_EVALUATE  (never assume)
    basis not in comparable_bases  -> UNABLE_TO_EVALUATE  (never equate)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from legalmind.domain.enums import RuleOutcome

# 45C.3 / 45C.4 — how carve-outs affect the outcome. No default: locked 45A §7
# forbids concluding "6 months = fully compliant" without considering whether
# the configured criteria address the exceptions.
EVALUATE_SEPARATELY = "EVALUATE_SEPARATELY"
IGNORE_FOR_GENERAL_CAP = "IGNORE_FOR_GENERAL_CAP"

#: The ONE approved Legal Rule (owner approval, 2026-08-20, confirming the
#: manager's zero-tolerance ruling of 2026-08-19): MATCH is acceptable, ANY
#: deviation — unlimited included — is UNACCEPTABLE and goes to Legal. No
#: tolerance band exists BY POLICY, so `acceptable_max` and
#: `approval_required_above` remain forbidden on every pre-NORMATIVE tier: the
#: approved rule is admitted EXACTLY as stated, never approximated. The importer,
#: the configuration API and publish all refuse any other (QA-004, 2026-10-29).
APPROVED_ZERO_TOLERANCE_RULE = {
    "deviation_outcome": "UNACCEPTABLE",
    "unlimited_outcome": "UNACCEPTABLE",
}

#: `AM-239` (AB-139, owner 2026-10-30) — the second approved form, amending `AM-33` r3:
#: a DEVIATION on the side the Company Standard itself names as LeapSwitch's
#: (`favourable_direction`, declared from a source, never inferred) is ACCEPTABLE. It
#: stays classified DEVIATION (rule 14); a standard carrying `favourable_counsel_check`
#: (Contract Act s.28 / s.74) is never accepted by it, and the evaluator applies it only
#: on paper where LeapSwitch is established as the provider.
FAVOURABLE_OUTCOME = "favourable_outcome"
FAVOURABLE_DIRECTION = "favourable_direction"
FAVOURABLE_COUNSEL_CHECK = "favourable_counsel_check"
APPROVED_FAVOURABLE_RULE = {**APPROVED_ZERO_TOLERANCE_RULE,
                            FAVOURABLE_OUTCOME: "ACCEPTABLE"}
APPROVED_RULES = (APPROVED_ZERO_TOLERANCE_RULE, APPROVED_FAVOURABLE_RULE)


def in_our_favour(value, unit: str | None, standard: dict) -> bool:
    """The measured value sits on the side of the standard the standard names as
    LeapSwitch's (`AM-165` r3, `AM-239`) — same unit, or working days against a
    calendar-day standard where the answer cannot depend on the conversion."""
    direction, preferred = standard.get(FAVOURABLE_DIRECTION), standard.get("preferred")
    if (direction not in ("LOWER", "HIGHER") or not isinstance(preferred, (int, float))
            or not isinstance(value, (int, float))):
        return False
    if unit == standard.get("unit"):
        return value < preferred if direction == "LOWER" else value > preferred
    if unit == "WORKING_DAYS" and standard.get("unit") == "DAYS":
        # N working days span at least N calendar days and, with weekends (x1.4) and
        # room for public holidays, at most 2N (`AM-154`: never converted, only bounded).
        # ponytail: 2N is the ceiling; a holiday run over N calendar days breaks it.
        return 2 * value < preferred if direction == "LOWER" else value > preferred
    return False


def accepts_favourable(legal_rule) -> bool:
    return ((getattr(legal_rule, "configuration", None) or {}).get(FAVOURABLE_OUTCOME)
            == RuleOutcome.ACCEPTABLE.value)


def configured_outcome(legal_rule, key: str) -> RuleOutcome:
    """The Legal Rule's disposition of a DEVIATION under ``key``. No rule, no key or
    an unrecognised value is NOT_APPLICABLE — the deviation stands and a human
    decides. So is ACCEPTABLE: `AM-33` r3 makes it reachable only from MATCH, so a
    rule that would accept a deviation is treated as unruled (QA-004)."""
    raw = (getattr(legal_rule, "configuration", None) or {}).get(key)
    try:
        outcome = RuleOutcome(raw)
    except ValueError:
        return RuleOutcome.NOT_APPLICABLE
    return RuleOutcome.NOT_APPLICABLE if outcome is RuleOutcome.ACCEPTABLE else outcome


@dataclass(frozen=True)
class PrecedenceRule:
    """Declarative only (D-5.1/D-5.2). Named sources, never an expression."""

    winning_source: str
    losing_source: str


@dataclass(frozen=True)
class ConversionRule:
    """Declares that a conversion is PERMITTED and what data it needs.

    Its presence does not perform the conversion: if any required input is
    unavailable the evaluation still fails closed (45C.9, 45C.23).
    """

    from_basis: str
    to_basis: str
    required_inputs: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RuleConfiguration:
    scope_required: bool = True
    comparable_scopes: tuple[str, ...] = ()
    comparable_bases: tuple[str, ...] = ()
    exception_handling: str = EVALUATE_SEPARATELY
    precedence_rules: tuple[PrecedenceRule, ...] = ()
    conversion_rules: tuple[ConversionRule, ...] = ()

    @classmethod
    def from_config(cls, config: dict | None) -> RuleConfiguration:
        config = config or {}
        return cls(
            scope_required=bool(config.get("scope_required", True)),
            comparable_scopes=tuple(config.get("comparable_scopes") or ()),
            comparable_bases=tuple(config.get("comparable_bases") or ()),
            exception_handling=config.get("exception_handling", EVALUATE_SEPARATELY),
            precedence_rules=tuple(
                PrecedenceRule(**r) for r in (config.get("precedence_rules") or ())),
            conversion_rules=tuple(
                ConversionRule(
                    from_basis=r["from_basis"], to_basis=r["to_basis"],
                    required_inputs=tuple(r.get("required_inputs") or ()))
                for r in (config.get("conversion_rules") or ())),
        )

    def scope_is_comparable(self, scope: str, standard_scope: str | None) -> bool:
        """A scope is comparable only when configuration says so (45C.5/45C.6)."""
        if standard_scope is None:
            return False
        return scope == standard_scope or scope in self.comparable_scopes

    def basis_is_comparable(self, basis: str | None,
                            standard_basis: str | None) -> bool:
        """Locked 45B.4: "We should not assume equivalence between different
        bases." Identical bases are comparable; anything else must be declared."""
        if basis is None or standard_basis is None:
            return False
        if basis == standard_basis:
            return True
        return basis in self.comparable_bases

    def conversion_for(self, from_basis: str | None,
                       to_basis: str | None) -> ConversionRule | None:
        for rule in self.conversion_rules:
            if rule.from_basis == from_basis and rule.to_basis == to_basis:
                return rule
        return None

    def precedence_between(self, source_a: str | None,
                           source_b: str | None) -> str | None:
        """Return the winning source, or None => CONFLICT (45C.22, F-6).

        Only CONFIGURED precedence applies. In-document precedence language is
        detected, evidenced and reported — never applied (45C.27).
        """
        for rule in self.precedence_rules:
            if {rule.winning_source, rule.losing_source} == {source_a, source_b}:
                return rule.winning_source
        return None
