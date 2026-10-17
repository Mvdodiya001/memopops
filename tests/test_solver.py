import pytest
from itertools import product

from memopops.formula import Formula, parse_formula
from memopops.solver import (
    BoundedSolverExecutor,
    QueryStatus,
    SolverQueueFullError,
    classify,
)


def parse(value: dict[str, object], atoms: set[str]) -> Formula:
    return parse_formula(value, atoms)


def atom(atom_id: str) -> dict[str, str]:
    return {"op": "atom", "id": atom_id}


def neg(value: dict[str, object]) -> dict[str, object]:
    return {"op": "not", "arg": value}


def implies(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    return {"op": "implies", "args": [left, right]}


def test_classifies_entailment_against_the_complete_snapshot() -> None:
    registered = {"api_v2", "tests_pass", "release_ready"}
    premises = [
        parse(atom("api_v2"), registered),
        parse(atom("tests_pass"), registered),
        parse(implies({"op": "and", "args": [atom("api_v2"), atom("tests_pass")]}, atom("release_ready")), registered),
    ]

    result = classify(premises, parse(atom("release_ready"), registered))

    assert result.result is QueryStatus.PROVED
    assert result.witnesses["knowledge"] == {"api_v2": True, "release_ready": True, "tests_pass": True}


def test_refutation_requires_accepted_negative_rule() -> None:
    registered = {"tests_pass", "release_ready"}
    premises = [
        parse(neg(atom("tests_pass")), registered),
        parse(implies(neg(atom("tests_pass")), neg(atom("release_ready"))), registered),
    ]

    result = classify(premises, parse(atom("release_ready"), registered))

    assert result.result is QueryStatus.REFUTED
    assert result.witnesses["query_false"] == {"release_ready": False, "tests_pass": False}


def test_unknown_returns_total_witnesses_for_both_query_polarities() -> None:
    registered = {"api_v2", "docs_signed"}
    premises = [parse(atom("api_v2"), registered)]

    result = classify(premises, parse(atom("docs_signed"), registered))

    assert result.result is QueryStatus.UNKNOWN
    assert set(result.witnesses["knowledge"]) == registered
    assert result.witnesses["knowledge"]["api_v2"] is True
    assert result.witnesses["query_true"] == {"api_v2": True, "docs_signed": True}
    assert result.witnesses["query_false"] == {"api_v2": True, "docs_signed": False}


def test_inconsistent_memory_is_not_explosive_proof() -> None:
    registered = {"p", "q"}
    premises = [parse(atom("p"), registered), parse(neg(atom("p")), registered)]

    result = classify(premises, parse(atom("q"), registered))

    assert result.result is QueryStatus.INCONSISTENT_MEMORY
    assert result.witnesses == {"knowledge": None, "query_true": None, "query_false": None}


def test_empty_memory_makes_query_unknown_with_explicit_total_models() -> None:
    registered = {"docs_signed"}

    result = classify([], parse(atom("docs_signed"), registered))

    assert result.result is QueryStatus.UNKNOWN
    assert result.witnesses["query_true"] == {"docs_signed": True}
    assert result.witnesses["query_false"] == {"docs_signed": False}


def test_solver_matches_independent_truth_table_oracle_for_all_v1_operators() -> None:
    registered = {"p", "q"}
    p = parse(atom("p"), registered)
    q = parse(atom("q"), registered)
    formulas = [p, q, parse(neg(atom("p")), registered), parse(neg(atom("q")), registered)]
    formulas.extend(
        parse({"op": operator, "args": [left, right]}, registered)
        for operator in ("and", "or", "implies", "iff")
        for left in (atom("p"), atom("q"))
        for right in (atom("p"), atom("q"))
    )

    def evaluate(formula: Formula, assignment: dict[str, bool]) -> bool:
        from memopops.formula import Atom, Not

        if isinstance(formula, Atom):
            return assignment[formula.id]
        if isinstance(formula, Not):
            return not evaluate(formula.arg, assignment)
        left = evaluate(formula.left, assignment)
        right = evaluate(formula.right, assignment)
        if formula.op == "and":
            return left and right
        if formula.op == "or":
            return left or right
        if formula.op == "implies":
            return not left or right
        if formula.op == "iff":
            return left == right
        raise AssertionError(f"unexpected operator {formula.op}")

    assignments = [dict(zip(sorted(registered), values)) for values in product((False, True), repeat=2)]
    for premise in formulas:
        for query in formulas:
            valid = [assignment for assignment in assignments if evaluate(premise, assignment)]
            if not valid:
                expected = QueryStatus.INCONSISTENT_MEMORY
            elif all(evaluate(query, assignment) for assignment in valid):
                expected = QueryStatus.PROVED
            elif all(not evaluate(query, assignment) for assignment in valid):
                expected = QueryStatus.REFUTED
            else:
                expected = QueryStatus.UNKNOWN

            actual = classify([premise], query)
            assert actual.result is expected, (premise, query, expected, actual.result)
            for witness_name, expected_query_value in (("query_true", True), ("query_false", False)):
                witness = actual.witnesses[witness_name]
                if witness is not None:
                    assert evaluate(premise, witness)
                    assert evaluate(query, witness) is expected_query_value


def test_solver_executor_rejects_when_worker_and_queue_are_full(monkeypatch):
    import threading

    import memopops.solver as solver_module

    started = threading.Event()
    release = threading.Event()

    def blocked_classify(*_args, **_kwargs):
        started.set()
        if not release.wait(timeout=2):
            raise TimeoutError("test worker was not released")
        return None

    monkeypatch.setattr(solver_module, "classify", blocked_classify)
    executor = BoundedSolverExecutor(workers=1, queue_capacity=0)
    try:
        future = executor.submit((), None, timeout_ms=100)
        assert started.wait(timeout=1)
        with pytest.raises(SolverQueueFullError):
            executor.submit((), None, timeout_ms=100)
        release.set()
        assert future.result(timeout=1) is None
    finally:
        release.set()
        executor.shutdown()
