"""The template condition language — JSON-Logic-shaped, our own evaluator, no eval."""

import pytest

from legalmind.drafting.conditions import ConditionError, evaluate, names

V = {"a": 3, "b": "x", "flag": True, "none": None}


@pytest.mark.parametrize("expr,expected", [
    ({"==": [{"var": "a"}, 3]}, True),
    ({"!=": [{"var": "a"}, 3]}, False),
    ({"<": [{"var": "a"}, 4]}, True),
    ({">": [{"var": "a"}, 4]}, False),
    ({"<=": [{"var": "a"}, 3]}, True),
    ({">=": [{"var": "a"}, 4]}, False),
    ({"in": [{"var": "b"}, ["x", "y"]]}, True),
    ({"and": [{"var": "flag"}, {"==": [{"var": "b"}, "x"]}]}, True),
    ({"or": [False, {"var": "flag"}]}, True),
    ({"not": [{"var": "flag"}]}, False),
    ({"<": [{"var": "missing"}, 3]}, False),          # None < 3 is simply not true
    ({"in": [1, {"var": "none"}]}, False),
    (True, True),
])
def test_operators(expr, expected):
    assert evaluate(expr, V) is expected


@pytest.mark.parametrize("bad", [{"eval": ["1"]}, {"==": [1, 2], "!=": [1, 2]},
                                 {"==": [1]}, {"and": [{"import": "os"}]}])
def test_unknown_operator_or_shape_is_refused(bad):
    with pytest.raises(ConditionError):
        evaluate(bad, V)


def test_names_lists_variables_and_dry_runs():
    assert names({"and": [{"var": "a"}, {"in": [{"var": "b"}, ["x"]]}]}) == {"a", "b"}
    with pytest.raises(ConditionError):
        names({"exec": [{"var": "a"}]})
