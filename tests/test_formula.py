import pytest

from memopops.formula import Binary, FormulaValidationError, canonical_json, formula_hash, parse_formula


def atom(atom_id: str = "p") -> dict[str, str]:
    return {"op": "atom", "id": atom_id}


@pytest.mark.parametrize("operator", [[], {}, ["and"], None, True, 17])
def test_parser_rejects_non_string_operators_without_crashing(operator):
    with pytest.raises(FormulaValidationError):
        parse_formula({"op": operator}, {"p"})


def test_parser_accepts_registered_atoms_and_canonicalizes_stably() -> None:
    value = {"op": "implies", "args": [atom("p"), atom("q")]}
    first = parse_formula(value, {"p", "q"})
    second = parse_formula({"args": [atom("p"), atom("q")], "op": "implies"}, {"p", "q"})

    assert isinstance(first, Binary)
    assert canonical_json(first) == '{"args":[{"id":"p","op":"atom"},{"id":"q","op":"atom"}],"op":"implies"}'
    assert formula_hash(first) == formula_hash(second)


@pytest.mark.parametrize(
    "value, registered",
    [
        ({"op": "eval", "source": "p"}, {"p"}),
        ({"op": "atom", "id": "P"}, {"P"}),
        ({"op": "atom", "id": "missing"}, {"p"}),
        ({"op": "atom", "id": "p", "extra": True}, {"p"}),
        ({"op": "and", "args": [{"op": "atom", "id": "p"}]}, {"p"}),
        ({"op": "not", "arg": {"op": "atom", "id": "p"}, "extra": 0}, {"p"}),
    ],
)
def test_parser_rejects_unregistered_atoms_and_malformed_shapes(value, registered) -> None:
    with pytest.raises(FormulaValidationError):
        parse_formula(value, registered)


def test_parser_enforces_depth_and_node_limits() -> None:
    nested = {"op": "not", "arg": {"op": "not", "arg": {"op": "atom", "id": "p"}}}
    with pytest.raises(FormulaValidationError, match="depth"):
        parse_formula(nested, {"p"}, max_depth=2)
    with pytest.raises(FormulaValidationError, match="nodes"):
        parse_formula({"op": "and", "args": [atom(), atom()]}, {"p"}, max_nodes=2)
