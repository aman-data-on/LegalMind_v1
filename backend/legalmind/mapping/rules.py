"""Mapping rule configuration — locked Steps 28, 35.

Locked 35.3/35.11/35.20: Requirements carry structured mapping metadata, may use
different rules from one another, and those rules are versioned as part of Legal
Configuration (`mapping_rule_versions.rules` JSONB, locked 42.10).

**Scoring weights and thresholds are configuration, not code.** Locked 35.10:
"Numerical thresholds should be validated against a representative contract test
set before being locked." Calibration is therefore a data exercise (publish a new
mapping rule version) rather than a code change.

--------------------------------------------------------------------------
`confirm_threshold` is REQUIRED — there is deliberately no default (D-1)
--------------------------------------------------------------------------
An earlier revision defaulted it to 5. That was an `ENG-09` violation with real
consequence: a mapping rule version omitting the key silently received a number
nobody decided, and that number then produced `CONFIRMED` / `UNRESOLVED` mapping
states and therefore Findings. Locked 35.9 declines to lock thresholds at all, so
there is no value code may legitimately supply.

Absence now raises ``MappingMisconfigured``. Owner decision **D-1** puts the
refusal at *publish* time, so an incomplete Requirement can never enter a
configuration snapshot; this exception is the defence-in-depth check behind it. The
refusal therefore lands in the configuration workflow (Step 29) rather than
manufacturing `UNABLE_TO_EVALUATE` Findings — which, being Tier 1, would require a
Legal Decision under `D-3.5(b)` and put configuration debt into the Legal queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class MappingMisconfigured(Exception):
    """A mapping rule version cannot be used as written (ENG-09).

    Raised rather than defaulted: fail closed, so nothing is ever mapped — and no
    Finding is ever produced — on the strength of an undecided value.
    """


# ---------------------------------------------------------------------------
# PROVISIONAL weights from locked 35.8, which states: "These numbers are
# illustrative, not locked yet." They are starting values for calibration
# against a representative contract set (35.10 / B-11), not settled policy.
#
# Retained as defaults, unlike the threshold, because weights alone classify
# nothing: without a `confirm_threshold` no score can become a mapping state, so
# an unconfigured weight set is inert rather than silently authoritative.
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS: dict[str, int] = {
    "exact_phrase": 5,
    "alias": 3,
    "keyword_group": 3,
    "section_heading": 2,
    "negative_pattern": -5,
}

# ⚠️ CURRENTLY UNREAD. `tie_margin` was the tolerance of the tie-based ambiguity
# rule that owner decision **M-2** removed: tied supporting clauses are now
# CONFIRMED and all are retained (Step 28 r2, 35.12), so no tolerance is consulted.
#
# Retained deliberately, not by oversight. An audit found it in no lock record, no
# persisted configuration row, no fixture, no API schema and no migration — so
# removal is safe — but the owner asked that it not be deleted until that evidence
# was reviewed. Until then it is accepted, round-tripped and ignored.
DEFAULT_TIE_MARGIN = 0


@dataclass(frozen=True, kw_only=True)
class MappingRules:
    """Deterministic mapping configuration for one Requirement version.

    Every field is data. Nothing here is an expression, a pattern language or a
    callable: locked 44.29 keeps comparison semantics and detection mechanics in
    tested code, and configuration to "patterns, terminology, thresholds, rule
    parameters".

    ``kw_only`` so that ``confirm_threshold`` can be a **required** field despite
    sitting after optional ones. Constructing this object without a threshold is
    therefore a ``TypeError``, not a silent default — the guarantee holds for every
    construction route, not only for ``from_config``.
    """

    # 35.9 / D-1 — REQUIRED. No default anywhere; see the module docstring.
    confirm_threshold: int

    # 35.4 — exact phrases and controlled terminology
    exact_phrases: tuple[str, ...] = ()
    # 35.4 — aliases (Requirement may be worded differently)
    aliases: tuple[str, ...] = ()
    # 35.4 — keyword groups: a group scores when ALL of its terms appear
    keyword_groups: tuple[tuple[str, ...], ...] = ()
    # 35.5 — negative terms: presence subtracts, guarding against false positives
    negative_patterns: tuple[str, ...] = ()
    # 35.7/35.11 — section heading hints
    section_heading_terms: tuple[str, ...] = ()

    weights: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    # See DEFAULT_TIE_MARGIN: accepted and round-tripped, but no longer read (M-2).
    tie_margin: int = DEFAULT_TIE_MARGIN

    @classmethod
    def from_config(cls, config: dict | None) -> MappingRules:
        """Build from the `mapping_rule_versions.rules` JSONB payload (42.10).

        Raises ``MappingMisconfigured`` when ``confirm_threshold`` is absent or is
        not an integer — never substitutes a value (ENG-09, D-1).
        """
        config = config or {}
        if "confirm_threshold" not in config:
            raise MappingMisconfigured(
                "mapping rules omit confirm_threshold; locked 35.9 does not fix a "
                "value, so none may be assumed (ENG-09)")
        raw = config["confirm_threshold"]
        # bool is an int subclass, and `True` as a threshold is a configuration
        # mistake that would otherwise silently mean 1.
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise MappingMisconfigured(
                f"confirm_threshold must be an integer, got {type(raw).__name__}")

        weights = dict(DEFAULT_WEIGHTS)
        weights.update(config.get("weights") or {})
        return cls(
            exact_phrases=tuple(config.get("exact_phrases") or ()),
            aliases=tuple(config.get("aliases") or ()),
            keyword_groups=tuple(
                tuple(g) for g in (config.get("keyword_groups") or ())),
            negative_patterns=tuple(config.get("negative_patterns") or ()),
            section_heading_terms=tuple(config.get("section_heading_terms") or ()),
            weights=weights,
            confirm_threshold=raw,
            tie_margin=int(config.get("tie_margin", DEFAULT_TIE_MARGIN)),
        )

    def to_config(self) -> dict:
        return {
            "exact_phrases": list(self.exact_phrases),
            "aliases": list(self.aliases),
            "keyword_groups": [list(g) for g in self.keyword_groups],
            "negative_patterns": list(self.negative_patterns),
            "section_heading_terms": list(self.section_heading_terms),
            "weights": dict(self.weights),
            "confirm_threshold": self.confirm_threshold,
            "tie_margin": self.tie_margin,
        }
