"""The STRUCTURAL placeholder template (`config/templates/placeholder/`), loaded as the
import tool loads it — synthetic text only, no legal content (rule 21)."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from legalmind.drafting import model as model_
from legalmind.drafting import render_contract
from tools.import_template import load_json

PLACEHOLDER = Path(__file__).resolve().parents[2] / "config" / "templates" / "placeholder" / "template.json"


@pytest.fixture(scope="session")
def _loaded():
    return load_json(PLACEHOLDER)


@pytest.fixture
def placeholder(_loaded):
    """(template, clauses) — a fresh copy per test."""
    return copy.deepcopy(_loaded)


@pytest.fixture
def answers(placeholder):
    return dict(placeholder[0]["layout"]["check_values"])


def build(template, clauses, answers):
    """(model, model_hash, docx)"""
    m = model_.resolve(template, clauses, answers)
    digest = model_.model_hash(m)
    return m, digest, render_contract.render(m, template["assets"], contract_ref="TEST",
                                             version_number=1, model_hash=digest)


@pytest.fixture
def rendered(placeholder, answers):
    return build(*placeholder, answers)
