"""Template conditions — a JSON-Logic-shaped expression, evaluated by our own code.

A template author writes ``{"==": [{"var": "processes_personal_data"}, true]}``; nothing
is ``eval``-ed and no expression language is imported. Operators: ``and`` ``or`` ``not``
``==`` ``!=`` ``in`` ``<`` ``>`` ``<=`` ``>=`` and the operand ``var`` (a DECLARED
variable). Anything else is refused when the template is checked (`names`), never
guessed at render time.
"""

from __future__ import annotations

import operator
from collections.abc import Mapping
from typing import Any

_COMPARE = {"==": operator.eq, "!=": operator.ne, "<": operator.lt, ">": operator.gt,
            "<=": operator.le, ">=": operator.ge, "in": lambda a, b: a in b}


class ConditionError(ValueError):
    """An operator or shape the language does not have."""


def evaluate(expr: Any, values: Mapping[str, Any]) -> Any:
    """The expression's value; a missing variable reads as None (so a comparison with
    it is simply False), never an error."""
    if not isinstance(expr, dict):
        if isinstance(expr, list):
            return [evaluate(e, values) for e in expr]
        return expr
    if len(expr) != 1:
        raise ConditionError(f"a condition has exactly one operator, not {sorted(expr)}")
    (op, args), = expr.items()
    if op == "var":
        return values.get(args)
    args = args if isinstance(args, list) else [args]
    if op == "and":
        return all(bool(evaluate(a, values)) for a in args)
    if op == "or":
        return any(bool(evaluate(a, values)) for a in args)
    if op in ("not", "!"):
        return not evaluate(args[0], values)
    if op in _COMPARE and len(args) == 2:
        left, right = evaluate(args[0], values), evaluate(args[1], values)
        try:
            return bool(_COMPARE[op](left, right))
        except TypeError:                   # None < 3, 3 in None: not true
            return False
    raise ConditionError(f"unknown operator {op!r}")


def names(expr: Any) -> set[str]:
    """Every variable the expression reads — and a dry evaluation, so an unknown
    operator is refused when the template is checked."""
    found: set[str] = set()

    def walk(e: Any) -> None:
        if isinstance(e, list):
            for x in e:
                walk(x)
        elif isinstance(e, dict):
            if "var" in e and len(e) == 1:
                found.add(str(e["var"]))
            else:
                for x in e.values():
                    walk(x)
    walk(expr)
    evaluate(expr, {})
    return found
