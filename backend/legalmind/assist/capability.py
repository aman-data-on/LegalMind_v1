"""The capability answer — `AM-68`, PROPOSED and not approved.

A question about what the PRODUCT does is not a legal question, and answering it from
the Constitution is how the reported defect looked: "What can you help me with?"
returned three unrelated Company Standards, because the POSITIONS fallback is
unconditional and a document-less Ask has no primary route at all.

Two properties make this route safe rather than merely useful:

**It reaches no legal corpus** (`AM-68` r2). `routing.plan` returns before any domain is
a candidate, so there is no later branch that could add one back. Nothing here imports
`store`, `positions` or `statutes`, and `tests/test_import_boundaries.py` can pin that.

**Its only evidence is the manifest** (r3). Every sentence a reader sees traces to an
entry in `config/capability_manifest.json`, and every entry names behaviour that is
built and covered by a test (r4). Rule 7's discipline carries over directly: an invented
capability is as bad as an invented legal rule, and "what can you help me with?" is
exactly the question a model will happily answer with features the product lacks.

NO GENERATION, BY DECISION. The owner chose option (b) when `AM-68` was locked on
2026-09-15: the manifest is RENDERED directly and no generation call is made. `AM-25`
r5 is therefore not engaged — there is no model output to ground and no payload
egresses — and the locked r3 amends it not at all. A generated variant would need a
further record; this module deliberately imports nothing that could make one.

Part of what decided that: `intent.is_verdict_statement` fires on the rendered
manifest, tripped by the entry naming the product's classification vocabulary and by
the DISCLAIMER itself. A generated answer over this text would likely be rejected by
the same screen and fall back here every time.
"""

from __future__ import annotations

import json
import pathlib

MANIFEST_PATH = (pathlib.Path(__file__).resolve().parents[2]
                 / "config" / "capability_manifest.json")

# Fixed, non-evidential framing — the same class of text as `REFUSAL_TEXT` and
# `EVALUATOR_ROUTE_TEXT`: it asserts nothing about the law and needs no citation.
_OPENING = "Here is what I can help you with."
_LIMITS_HEADING = "What I do not do:"


class CapabilityManifestUnavailable(Exception):
    """The manifest could not be read. Raised rather than substituted: a capability
    answer with no manifest behind it is precisely the invention r4 forbids."""


def load(path: pathlib.Path | None = None) -> dict:
    try:
        data = json.loads((path or MANIFEST_PATH).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityManifestUnavailable(str(exc)) from exc
    if not data.get("capabilities"):
        raise CapabilityManifestUnavailable("manifest lists no capabilities")
    return data


def render(manifest: dict) -> str:
    """The deterministic answer — `AM-68` r6.

    Plain prose, in the shape `AnswerProse` already renders: a paragraph, a bulleted
    list, a paragraph. No markdown is emitted, because the transcript renderer refuses
    to invent headings or emphasis from punctuation and this text should not fight it.
    """
    lines = [_OPENING, ""]
    lines += [f"- {c['text']}" for c in manifest["capabilities"]]
    if manifest.get("limits"):
        lines += ["", _LIMITS_HEADING, ""]
        lines += [f"- {limit['text']}" for limit in manifest["limits"]]
    return "\n".join(lines)


def answer(path: pathlib.Path | None = None) -> str:
    """The capability answer as a reader receives it. One call site, so a future
    generated variant (r5) replaces exactly one thing and the fallback stays put."""
    return render(load(path))
