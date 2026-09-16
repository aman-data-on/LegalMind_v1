"""The evidence-rescue judge — a second look at a refusal, never at an answer.

MEASURED 2026-09-16 on the ratified 77-question set. Of 64 answerable questions the
calibrated gate refuses 21, and **15 of those 21 already have the gold chunk in the
retrieved list**. Retrieval found the answer and the gate discarded it. Only 6 are
genuine retrieval misses. Recall is 0.625; fixing the DECISION alone would reach 0.859.

Why no cheaper fix exists, and this was established before writing any of this:

  * Threshold sweep, 35 combinations of floor and peak margin: no configuration
    improves recall without raising wrongly-answered. The frontier is monotonic.
  * A second independent feature (IDF-weighted question/chunk overlap) does not
    separate the two groups — false refusals median 0.185, unanswerable 0.196, with
    top-cosine 0.443 against 0.447. Statistically identical.
  * A different embedding model does not either: the 2026-08-26 bake-off has
    gte-small at 11/13 · 45/64 against MiniLM's 12/13 · 41/64 — the same trade.

`calibration.py` already said why: "those score INSIDE the answerable distribution, so
no similarity feature separates them, for any candidate." The distinguishing signal
requires READING the chunk, which is what this does.

THE SAFETY ARGUMENT, which is the whole design:

    The judge can only turn a REFUSAL into an ATTEMPT. It never turns an answer into a
    refusal, never ranks, never writes, and never reaches the reader.

An attempt still passes every existing mechanical screen unchanged — evidence
sufficiency, citation verification, the grounding floor, the verdict screen. So
`AM-25` r5 holds exactly as before: no claim reaches a user without resolving to
retrieved evidence, and enforcement stays mechanical and outside the model. What the
judge changes is whether generation is ATTEMPTED on evidence that was already
retrieved and already authorised — not whether its output is trusted.

EGRESS: this sends the question and the retrieved chunk spans, which is precisely what
`AM-30` t2 already permits for generation. No new category of data leaves. It is a new
PURPOSE for that egress and one extra call per refused question, which is why it ships
behind `LEGALMIND_EVIDENCE_RESCUE`, unset.
"""

from __future__ import annotations

import re

from legalmind import config
from legalmind.assist import generation
from legalmind.observability.logs import log_event

RESCUE_PROMPT_VERSION = "evidence-rescue-1"
RESCUE_PROMPT_TEMPLATE = """You are deciding ONE thing: do any of the numbered excerpts \
below contain the information needed to answer the question? Judge only what the \
excerpts say. Do not answer the question itself.

Reply with exactly one line:
  YES <numbers>   - the excerpts contain it; name the useful ones, e.g. "YES 1 3"
  NO              - if they do not

Be strict. An excerpt merely about the same topic, which does not state the answer, \
is NO. A near-miss is NO.

EXCERPTS:
{evidence}

QUESTION: {question}

DECISION:"""

_YES = re.compile(r"^\s*YES\b([\d\s,]*)", re.IGNORECASE)


def rescue_indices(question: str, chunk_texts: list[str], *,
                   request_id: str | None = None) -> list[int]:
    """Zero-based indices of excerpts the judge says answer the question; [] for none.

    Returns [] on every failure path — disabled, no evidence, provider unavailable,
    refused payload, unparseable reply. [] means the refusal stands, which is the
    behaviour that ships today, so nothing degrades when this cannot run.
    """
    if not config.evidence_rescue_enabled() or not chunk_texts:
        return []
    numbered = "\n".join(f"[{i}] {t}" for i, t in enumerate(chunk_texts, start=1))
    prompt = RESCUE_PROMPT_TEMPLATE.format(evidence=numbered, question=question)
    try:
        result = generation.generate_raw(
            prompt, prompt_version=RESCUE_PROMPT_VERSION,
            environment=config.environment(), request_id=request_id,
            evidence_count=len(chunk_texts), max_output_tokens=32)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        log_event("assist.rescue.unavailable", request_id=request_id,
                  reason=type(exc).__name__)
        return []
    match = _YES.match((result.text or "").strip())
    if not match:
        return []
    picked = [int(n) - 1 for n in re.findall(r"\d+", match.group(1))]
    # A YES naming nothing means the whole set; a number outside the set is dropped
    # rather than trusted, because an index the judge invented is not evidence.
    chosen = ([i for i in picked if 0 <= i < len(chunk_texts)]
              or list(range(len(chunk_texts))))
    log_event("assist.rescue.opened", request_id=request_id, chosen=str(len(chosen)))
    return chosen
