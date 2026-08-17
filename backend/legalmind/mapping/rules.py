"""Mapping rule configuration — locked Steps 28, 35.

Locked 35.3/35.11/35.20: Requirements carry structured mapping metadata, may use
different rules from one another, and those rules are versioned as part of Legal
Configuration (`mapping_rule_versions.rules` JSONB, locked 42.10).

**Scoring weights and thresholds are configuration, not code.** Locked 35.10:
"Numerical thresholds should be validated against a representative contract test
set before being locked." Step 35.8's illustrative weights are reproduced below
as *defaults*, explicitly marked provisional. Calibration is therefore a data
exercise (publish a new mapping rule version) rather than a code change.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# PROVISIONAL defaults from locked 35.8, which states: "These numbers are
# illustrative, not locked yet." They are starting values for calibration
# against a representative contract set (35.10 / B-11), not settled policy.
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS: dict[str, int] = {
    "exact_phrase": 5,
    "alias": 3,
    "keyword_group": 3,
    "section_heading": 2,
    "negative_pattern": -5,
}

# Also PROVISIONAL (35.9: "I recommend not locking numerical thresholds yet").
DEFAULT_CONFIRM_THRESHOLD = 5
# Two candidates whose scores differ by no more than this are treated as equally
# plausible, so neither may be silently chosen (locked Step 28 AMBIGUOUS).
DEFAULT_TIE_MARGIN = 0


@dataclass(frozen=True)
class MappingRules:
    """Deterministic mapping configuration for one Requirement version.

    Every field is data. Nothing here is an expression, a pattern language or a
    callable: locked 44.29 keeps comparison semantics and detection mechanics in
    tested code, and configuration to "patterns, terminology, thresholds, rule
    parameters".
    """

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
    confirm_threshold: int = DEFAULT_CONFIRM_THRESHOLD
    tie_margin: int = DEFAULT_TIE_MARGIN

    @classmethod
    def from_config(cls, config: dict) -> MappingRules:
        """Build from the `mapping_rule_versions.rules` JSONB payload (42.10)."""
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
            confirm_threshold=int(
                config.get("confirm_threshold", DEFAULT_CONFIRM_THRESHOLD)),
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
