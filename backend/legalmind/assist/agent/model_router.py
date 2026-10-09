"""The Ask model choice (owner, 2026-10-06; `AM-116`): one registry, validated
server-side, routed to a provider adapter — and never a silent fallback.

The reader picks a model in the composer; the request carries its id; the router
validates it here (`resolve`) before anything is stored; the agent is handed the
adapter for it (`provider`). An id outside `MODELS` is refused, never trusted, and a
model that is listed but not configured is refused with its own name — the answer is
never quietly written by Gemini instead.

`AM-117` (owner, 2026-10-07) amends `AM-30` for two providers, on this path only:
DeepSeek through IndieRouter and Bonsai on the company's own inference endpoint, both
OpenAI-compatible (`agent.OpenAICompatProvider`, translated in `generation`). Each is
served only with its adapter, its key AND its base URL in the environment. Qwen was
listed until IndieRouter withdrew it from its platform (owner, 2026-10-07, `AM-120`):
an id the registry does not hold is refused as unknown. An untested integration that
looks configured is exactly what the owner ruled out, so a model is added here only
after it has been measured.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field

from legalmind import config
from legalmind.assist.agent import agent
from legalmind.assist.agent.agent import Provider
from legalmind.assist.llm import generation
from legalmind.observability.logs import log_event


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    #: The adapter that serves it: "gemini", "openai" (OpenAI-compatible), or "" for a
    #: model listed but not yet servable.
    provider: str
    #: Where the provider's credential is read from.
    key_env: str
    #: OpenAI-compatible only: who serves it (the audit row), where, and its model id.
    vendor: str = ""
    base_url_env: str = ""
    api_model: str = ""
    #: Request fields the provider needs, and whether it runs the lean profile (a slow
    #: endpoint: ranked context, no decision steps, its own time budget — agent.py).
    extras: tuple[tuple[str, object], ...] = ()
    lean: bool = False
    #: Whether, once its first searches returned records, the loop asks the model a
    #: second time if it wants to search again. DeepSeek never did in 41 logged turns
    #: (2026-10-08) and the call cost a median 3.3 s, up to 9.5 s, on a 46k-token prompt —
    #: time its 40 s turn needs for the answer. Gemini does in about a third of turns.
    done_check: bool = True


MODELS: dict[str, Model] = {m.id: m for m in (
    Model("gemini", "Gemini", "gemini", "LEGALMIND_GEMINI_API_KEY"),
    Model("deepseek", "DeepSeek", "openai", "LEGALMIND_INDIEROUTER_API_KEY",
          vendor="indierouter", base_url_env="LEGALMIND_INDIEROUTER_BASE_URL",
          api_model="deepseek-v4.1-flash", done_check=False),
    Model("bonsai", "Bonsai", "openai", "LEGALMIND_BONSAI_API_KEY",
          vendor="bonsai", base_url_env="LEGALMIND_BONSAI_BASE_URL",
          api_model="bonsai-2-27b",
          # measured 2026-10-07: ~700 prompt and ~18-26 output tokens/s; its gateway
          # closes a request silent for 50 s (streamed, a 1,184-token answer arrived
          # whole in 66 s); and it reasons unless told not to (reasoning_effort ignored)
          extras=(("chat_template_kwargs", {"enable_thinking": False}),
                  ("stream", True), ("stream_options", {"include_usage": True})),
          lean=True),
)}
DEFAULT = "gemini"


def endpoint(model: Model) -> generation.Endpoint:
    return generation.Endpoint(provider=model.vendor,
                               base_url=os.environ.get(model.base_url_env, "").strip(),
                               key=os.environ.get(model.key_env, "").strip(),
                               model=model.api_model, extras=dict(model.extras))


#: The provider adapters that exist (`AM-117` added the OpenAI-compatible one). Looked
#: up when called, so `agent.GeminiProvider` stays the one seam tests replace.
ADAPTERS: dict[str, Callable[[Model], Provider]] = {
    "gemini": lambda m: agent.GeminiProvider(),
    "openai": lambda m: agent.OpenAICompatProvider(endpoint(m), lean=m.lean,
                                                   label=m.label,
                                                   done_check=m.done_check),
}


class UnknownModel(ValueError):
    pass


class ModelNotConfigured(ValueError):
    pass


def configured(model: Model) -> bool:
    """Gemini keeps its own handling of a missing key (the agent's floor answer), so
    the default is always served exactly as before. Any other model needs its adapter,
    its key, and the agent path — the only path routed by provider; the older pipeline
    calls Gemini directly and would otherwise answer in its place."""
    if model.id == DEFAULT:
        return True
    return (model.provider in ADAPTERS and bool(os.environ.get(model.key_env, "").strip())
            and (not model.base_url_env
                 or bool(os.environ.get(model.base_url_env, "").strip()))
            and config.ask_agent_mode() == "on")


def resolve(model_id: str | None) -> Model:
    """The validated choice; no id is the default. Raises rather than substitutes."""
    model = MODELS.get(model_id or DEFAULT)
    if model is None:
        raise UnknownModel(model_id)
    if not configured(model):
        raise ModelNotConfigured(model.label)
    return model


def provider(model_id: str) -> Provider:
    model = resolve(model_id)
    first = ADAPTERS[model.provider](model)
    if not config.ask_failover():
        return first
    # Forward only (`AM-124` r2): an OpenAI-compatible turn cannot hand its parts back to
    # Gemini, so a reader who chose DeepSeek falls on to Bonsai, never back to Gemini.
    order = list(MODELS)
    later = [m for m in (MODELS[i] for i in order[order.index(model.id) + 1:])
             if m.provider in ADAPTERS and configured(m) and m.id != DEFAULT]
    if not later:
        return first
    return FailoverProvider([(model, first)]
                            + [(m, ADAPTERS[m.provider](m)) for m in later])


def answered_by(identity: str | None) -> dict | None:
    """The model an answer row records (`ai_answers.model_identity`, the provider's own
    id) as a reader names it — {"label": "DeepSeek", "model": "deepseek-v4.1-flash"};
    None when no model answered (a fixed reply)."""
    if not identity:
        return None
    label = next((m.label for m in MODELS.values() if m.api_model == identity),
                 "Gemini" if identity.startswith("gemini") else identity)
    return {"label": label, "model": identity}


def egress_hosts() -> list[str]:
    """The provider hosts this deployment can reach — for the `AM-30` t8 register."""
    # Not `urllib.parse`: only `generation` may import a network module
    # (`test_import_boundaries`), and a host is the text between "//" and the next "/".
    return [os.environ[m.base_url_env].split("//", 1)[-1].split("/", 1)[0]
            for m in MODELS.values() if m.base_url_env and configured(m)]


# ------------------------------------------------------------------------- failover
#: An infrastructure failure, and only that (owner, 2026-10-08): a 429, a 5xx, a
#: timeout or a dropped connection. A refused payload (`GenerationRefused`), another 4xx
#: or a malformed reply is never failed over — quality is routing, not failover.
_INFRA_STATUS = re.compile(r"HTTP (?:429|5\d\d)\b")
_INFRA_ERRORS = frozenset({
    "TimeoutError", "URLError", "ConnectionError", "ConnectionResetError",
    "ConnectionRefusedError", "ConnectionAbortedError", "BrokenPipeError",
    "RemoteDisconnected", "IncompleteRead"})
#: The provider-health signal: failovers per provider call, over the last 200 calls.
FAILOVER_ALERT_SHARE, _WINDOW = 0.05, 200
#: A hop needs time for the next provider to answer; less than this and the turn fails
#: over to nothing and lands on the floor, as without failover.
MIN_HOP_S = 4.0
# ponytail: per process; production runs one uvicorn process. Move to log aggregation
# once Step 53's monitoring stack is specified (53.6).
_RECENT: deque[bool] = deque(maxlen=_WINDOW)


def is_infra(exc: Exception) -> bool:
    message = str(exc)
    return isinstance(exc, generation.GenerationUnavailable) and (
        bool(_INFRA_STATUS.search(message)) or message in _INFRA_ERRORS)


def context_tokens(model: Model) -> int | None:
    """A model's context window, from `LEGALMIND_<ID>_CONTEXT_TOKENS`; None unknown."""
    raw = os.environ.get(f"LEGALMIND_{model.id.upper()}_CONTEXT_TOKENS", "").strip()
    return int(raw) if raw.isdigit() else None


def _usd(model: Model, prompt: int | None, output: int | None) -> float | None:
    """What a call cost, from `LEGALMIND_<ID>_USD_PER_M_IN/OUT`; None when unpriced."""
    rates = [os.environ.get(f"LEGALMIND_{model.id.upper()}_USD_PER_M_{k}", "").strip()
             for k in ("IN", "OUT")]
    if not all(rates) or prompt is None or output is None:
        return None
    try:
        return (prompt * float(rates[0]) + output * float(rates[1])) / 1e6
    except ValueError:
        return None


def _observe(failed_over: bool) -> None:
    _RECENT.append(failed_over)
    share = sum(_RECENT) / len(_RECENT)
    if failed_over and len(_RECENT) >= 20 and share > FAILOVER_ALERT_SHARE:
        log_event("assist.provider_failover_rate", level=logging.WARNING,
                  signal="assist.provider_failover_rate", share=round(share, 3),
                  window=len(_RECENT))


@dataclass
class FailoverProvider:
    """The chosen model first, then the next configured ones in `MODELS` order, moved
    on to only on an infrastructure failure (`AM-124`). One-way and sticky for the rest
    of the turn; each provider keeps its own one retry (`agent._retrying`). A failed
    stream is never resumed elsewhere: `generation` folds a stream whole, so a failure
    discards what arrived and the next provider starts the call clean. The turn keeps
    the first model's profile (`lean`, `done_check`), so its time budget never changes
    mid-turn, and the answer names the model that actually wrote it."""
    chain: list[tuple[Model, Provider]]
    at: int = 0
    hops: list[dict] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.chain[0][0].label

    @property
    def lean(self) -> bool:
        return self.chain[0][0].lean

    @property
    def done_check(self) -> bool:
        return self.chain[0][0].done_check

    def turn(self, system, contents, *, tools, schema, timeout_s, request_id,
             force_tool=False, answer_tokens=None):
        # ponytail: four characters a token, the usual estimate for mixed English and
        # JSON; use the provider's own count if a window ever sits close to it.
        need = (len(system) + len(json.dumps(contents))) // 4
        started, hopped = time.monotonic(), False
        while True:
            model, current = self.chain[self.at]
            left = timeout_s - (time.monotonic() - started)
            try:
                result = current.turn(system, contents, tools=tools, schema=schema,
                                      timeout_s=left, request_id=request_id,
                                      force_tool=force_tool, answer_tokens=answer_tokens)
            except generation.GenerationUnavailable as exc:
                nxt = next((i for i in range(self.at + 1, len(self.chain))
                            if (context_tokens(self.chain[i][0]) or 0) >= need), None)
                spent = time.monotonic() - started
                if not is_infra(exc) or nxt is None or timeout_s - spent < MIN_HOP_S:
                    _observe(hopped)
                    raise
                hopped = True
                self.hops.append({"from": model.id, "to": self.chain[nxt][0].id,
                                  "reason": str(exc)})
                self.at = nxt
                log_event("assist.agent.failover", level=logging.WARNING,
                          request_id=request_id, chosen=self.chain[0][0].id,
                          failed=model.id, answering=self.chain[nxt][0].id,
                          reason=str(exc), latency_added_ms=int(spent * 1000),
                          prompt_tokens=need)
                continue
            _observe(hopped)
            if hopped:
                chosen = self.chain[0][0]
                cost, would = (_usd(m, result.prompt_tokens, result.output_tokens)
                               for m in (model, chosen))
                log_event("assist.agent.failover_answered", request_id=request_id,
                          chosen=chosen.id, answered=model.id,
                          latency_added_ms=int((time.monotonic() - started) * 1000
                                               - result.latency_ms),
                          cost_delta_usd=(None if cost is None or would is None
                                          else round(cost - would, 6)))
            return result
