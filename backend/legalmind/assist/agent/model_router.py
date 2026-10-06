"""The Ask model choice (owner, 2026-10-06; `AM-116`): one registry, validated
server-side, routed to a provider adapter — and never a silent fallback.

The reader picks a model in the composer; the request carries its id; the router
validates it here (`resolve`) before anything is stored; the agent is handed the
adapter for it (`provider`). An id outside `MODELS` is refused, never trusted, and a
model that is listed but not configured is refused with its own name — the answer is
never quietly written by Gemini instead.

Only Gemini has an adapter. DeepSeek, Qwen and Bonsai are listed so the composer can
offer them honestly as "not configured", and each has the one place its credential
will be read from. Serving one takes its adapter in `ADAPTERS` (an `agent.Provider`)
AND its key — and, because every provider is a new egress, an amendment to `AM-30`
first (t1 names generation as the ONE permitted egress, t6 the provider's
no-training terms, t8 the endpoint allow-list). No adapter is written ahead of that:
an untested integration that looks configured is exactly what the owner ruled out.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

from legalmind import config
from legalmind.assist.agent import agent
from legalmind.assist.agent.agent import Provider


@dataclass(frozen=True)
class Model:
    id: str
    label: str
    provider: str
    #: Where the provider's credential is read from once it has an adapter.
    key_env: str


MODELS: dict[str, Model] = {m.id: m for m in (
    Model("gemini", "Gemini", "gemini", "LEGALMIND_GEMINI_API_KEY"),
    Model("deepseek", "DeepSeek", "deepseek", "LEGALMIND_DEEPSEEK_API_KEY"),
    Model("qwen", "Qwen", "qwen", "LEGALMIND_QWEN_API_KEY"),
    Model("bonsai", "Bonsai", "bonsai", "LEGALMIND_BONSAI_API_KEY"),
)}
DEFAULT = "gemini"

#: The provider adapters that exist. Adding one is an `AM-30` amendment (module doc).
#: Looked up when called, so `agent.GeminiProvider` stays the one seam tests replace.
ADAPTERS: dict[str, Callable[[], Provider]] = {"gemini": lambda: agent.GeminiProvider()}


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
    return ADAPTERS[resolve(model_id).provider]()
