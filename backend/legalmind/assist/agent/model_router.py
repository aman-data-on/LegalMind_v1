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

import os
from collections.abc import Callable
from dataclasses import dataclass

from legalmind import config
from legalmind.assist.agent import agent
from legalmind.assist.agent.agent import Provider
from legalmind.assist.llm import generation


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


MODELS: dict[str, Model] = {m.id: m for m in (
    Model("gemini", "Gemini", "gemini", "LEGALMIND_GEMINI_API_KEY"),
    Model("deepseek", "DeepSeek", "openai", "LEGALMIND_INDIEROUTER_API_KEY",
          vendor="indierouter", base_url_env="LEGALMIND_INDIEROUTER_BASE_URL",
          api_model="deepseek-v4.1-flash"),
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
                                                   label=m.label),
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
    return ADAPTERS[model.provider](model)


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
