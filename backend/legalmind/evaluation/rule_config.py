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

# 45C.3 / 45C.4 — how carve-outs affect the outcome. No default: locked 45A §7
# forbids concluding "6 months = fully compliant" without considering whether
# the configured criteria address the exceptions.
EVALUATE_SEPARATELY = "EVALUATE_SEPARATELY"
IGNORE_FOR_GENERAL_CAP = "IGNORE_FOR_GENERAL_CAP"


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
