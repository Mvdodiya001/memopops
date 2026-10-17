"""Hand-written certificate vectors.

Clause literals, pivots, and definition operands are written out here. Hashes
are filled through the documented canonical envelope so the vectors stay
readable. These are development test vectors, not live service responses.
"""

from __future__ import annotations

import copy

from proofcheck.formula import formula_hash, knowledge_hash


def atom(atom_id: str) -> dict[str, object]:
    return {"op": "atom", "id": atom_id}


def definition(variable: int, op: str, operands: list[int], formula: dict[str, object]) -> dict[str, object]:
    return {
        "variable": variable,
        "op": op,
        "operands": operands,
        "formula_hash": formula_hash(formula),
    }


def assemble(
    *,
    workspace_id: str,
    revision_id: str,
    result: str,
    assertions: list[tuple[str, dict[str, object], list[str]]],
    query: dict[str, object],
    atom_variables: list[dict[str, object]],
    definitions: list[dict[str, object]],
    roots: list[dict[str, object]],
    query_root: int,
    witness: dict[str, bool],
    clauses: list[dict[str, object]],
    empty_clause_id: int,
    support: list[str],
) -> dict[str, object]:
    records = [
        {"id": assertion_id, "formula": formula, "evidence_ids": evidence_ids}
        for assertion_id, formula, evidence_ids in assertions
    ]
    return {
        "certificate_version": "resolution-v1",
        "semantics_version": "boolean-v1",
        "workspace_id": workspace_id,
        "revision_id": revision_id,
        "knowledge_hash": knowledge_hash([(item["id"], formula_hash(item["formula"])) for item in records]),
        "query_hash": formula_hash(query),
        "result": result,
        "assertions": records,
        "query": query,
        "atom_variables": atom_variables,
        "definitions": definitions,
        "roots": roots,
        "query_root": query_root,
        "knowledge_witness": witness,
        "clauses": clauses,
        "empty_clause_id": empty_clause_id,
        "support_assertion_ids": support,
    }


def context_for(bundle: dict[str, object]) -> dict[str, object]:
    assertions = bundle["assertions"]
    assert isinstance(assertions, list)
    return {
        "workspace_id": bundle["workspace_id"],
        "revision_id": bundle["revision_id"],
        "semantics_version": bundle["semantics_version"],
        "knowledge_hash": bundle["knowledge_hash"],
        "query_hash": bundle["query_hash"],
        "assertions": [
            {
                "id": item["id"],
                "formula_hash": formula_hash(item["formula"]),
                "evidence_ids": list(item["evidence_ids"]),
            }
            for item in assertions
        ],
    }


def cloned(bundle: dict[str, object]) -> dict[str, object]:
    return copy.deepcopy(bundle)


def implies_query_bundle() -> dict[str, object]:
    """K contains P→Q and the query is that same formula."""
    left = atom("p")
    right = atom("q")
    formula = {"op": "implies", "args": [left, right]}
    clauses: list[dict[str, object]] = [
        {"id": 1, "literals": [-3, -1, 2], "origin": "definition", "definition_variable": 3},
        {"id": 2, "literals": [1, 3], "origin": "definition", "definition_variable": 3},
        {"id": 3, "literals": [-2, 3], "origin": "definition", "definition_variable": 3},
        {"id": 4, "literals": [3], "origin": "premise", "assertion_id": "a_rule"},
        {"id": 5, "literals": [-3], "origin": "query_assumption"},
        {"id": 6, "literals": [], "origin": "resolution", "parents": [4, 5], "pivot": 3},
    ]
    return assemble(
        workspace_id="workspace_demo",
        revision_id="rev_tiny",
        result="PROVED",
        assertions=[("a_rule", formula, ["ev_rule"])],
        query=formula,
        atom_variables=[{"atom_id": "p", "variable": 1}, {"atom_id": "q", "variable": 2}],
        definitions=[definition(3, "implies", [1, 2], formula)],
        roots=[{"assertion_id": "a_rule", "variable": 3}],
        query_root=3,
        witness={"p": True, "q": True},
        clauses=clauses,
        empty_clause_id=6,
        support=["a_rule"],
    )


def chain_proved_bundle() -> dict[str, object]:
    """P, P→Q, Q→R proves R."""
    p = atom("p")
    q = atom("q")
    r = atom("r")
    implies_pq = {"op": "implies", "args": [p, q]}
    implies_qr = {"op": "implies", "args": [q, r]}
    clauses: list[dict[str, object]] = [
        {"id": 1, "literals": [-4, -1, 2], "origin": "definition", "definition_variable": 4},
        {"id": 2, "literals": [1, 4], "origin": "definition", "definition_variable": 4},
        {"id": 3, "literals": [-2, 4], "origin": "definition", "definition_variable": 4},
        {"id": 4, "literals": [-5, -2, 3], "origin": "definition", "definition_variable": 5},
        {"id": 5, "literals": [2, 5], "origin": "definition", "definition_variable": 5},
        {"id": 6, "literals": [-3, 5], "origin": "definition", "definition_variable": 5},
        {"id": 7, "literals": [1], "origin": "premise", "assertion_id": "a_p"},
        {"id": 8, "literals": [4], "origin": "premise", "assertion_id": "a_pq"},
        {"id": 9, "literals": [5], "origin": "premise", "assertion_id": "a_qr"},
        {"id": 10, "literals": [-3], "origin": "query_assumption"},
        {"id": 11, "literals": [-4, 2], "origin": "resolution", "parents": [7, 1], "pivot": 1},
        {"id": 12, "literals": [2], "origin": "resolution", "parents": [11, 8], "pivot": 4},
        {"id": 13, "literals": [-5, 3], "origin": "resolution", "parents": [12, 4], "pivot": 2},
        {"id": 14, "literals": [3], "origin": "resolution", "parents": [13, 9], "pivot": 5},
        {"id": 15, "literals": [], "origin": "resolution", "parents": [14, 10], "pivot": 3},
    ]
    return assemble(
        workspace_id="workspace_chain",
        revision_id="rev_chain",
        result="PROVED",
        assertions=[
            ("a_p", p, ["ev_p"]),
            ("a_pq", implies_pq, ["ev_pq"]),
            ("a_qr", implies_qr, ["ev_qr"]),
        ],
        query=r,
        atom_variables=[
            {"atom_id": "p", "variable": 1},
            {"atom_id": "q", "variable": 2},
            {"atom_id": "r", "variable": 3},
        ],
        definitions=[
            definition(4, "implies", [1, 2], implies_pq),
            definition(5, "implies", [2, 3], implies_qr),
        ],
        roots=[
            {"assertion_id": "a_p", "variable": 1},
            {"assertion_id": "a_pq", "variable": 4},
            {"assertion_id": "a_qr", "variable": 5},
        ],
        query_root=3,
        witness={"p": True, "q": True, "r": True},
        clauses=clauses,
        empty_clause_id=15,
        support=["a_p", "a_pq", "a_qr"],
    )


def refuted_not_p_bundle() -> dict[str, object]:
    """K contains P, so NOT P is refuted."""
    p = atom("p")
    query = {"op": "not", "arg": p}
    clauses: list[dict[str, object]] = [
        {"id": 1, "literals": [-2, -1], "origin": "definition", "definition_variable": 2},
        {"id": 2, "literals": [1, 2], "origin": "definition", "definition_variable": 2},
        {"id": 3, "literals": [1], "origin": "premise", "assertion_id": "a_p"},
        {"id": 4, "literals": [2], "origin": "query_assumption"},
        {"id": 5, "literals": [-2], "origin": "resolution", "parents": [3, 1], "pivot": 1},
        {"id": 6, "literals": [], "origin": "resolution", "parents": [5, 4], "pivot": 2},
    ]
    return assemble(
        workspace_id="workspace_chain",
        revision_id="rev_chain",
        result="REFUTED",
        assertions=[("a_p", p, ["ev_p"])],
        query=query,
        atom_variables=[{"atom_id": "p", "variable": 1}],
        definitions=[definition(2, "not", [1], query)],
        roots=[{"assertion_id": "a_p", "variable": 1}],
        query_root=2,
        witness={"p": True},
        clauses=clauses,
        empty_clause_id=6,
        support=["a_p"],
    )


def _release_formulas() -> dict[str, dict[str, object]]:
    deployed = atom("api_v2")
    tests = atom("tests_pass")
    ready = atom("release_ready")
    not_tests = {"op": "not", "arg": tests}
    not_ready = {"op": "not", "arg": ready}
    both = {"op": "and", "args": [deployed, tests]}
    return {
        "deployed": deployed,
        "tests": tests,
        "ready": ready,
        "not_tests": not_tests,
        "not_ready": not_ready,
        "both": both,
        "block": {"op": "implies", "args": [not_tests, not_ready]},
        "allow": {"op": "implies", "args": [both, ready]},
    }


def _release_definitions(formulas: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    return [
        definition(4, "not", [3], formulas["not_tests"]),
        definition(5, "not", [2], formulas["not_ready"]),
        definition(6, "implies", [4, 5], formulas["block"]),
        definition(7, "and", [1, 3], formulas["both"]),
        definition(8, "implies", [7, 2], formulas["allow"]),
    ]


def _release_definition_clauses() -> list[dict[str, object]]:
    return [
        {"id": 1, "literals": [-4, -3], "origin": "definition", "definition_variable": 4},
        {"id": 2, "literals": [3, 4], "origin": "definition", "definition_variable": 4},
        {"id": 3, "literals": [-5, -2], "origin": "definition", "definition_variable": 5},
        {"id": 4, "literals": [2, 5], "origin": "definition", "definition_variable": 5},
        {"id": 5, "literals": [-6, -4, 5], "origin": "definition", "definition_variable": 6},
        {"id": 6, "literals": [4, 6], "origin": "definition", "definition_variable": 6},
        {"id": 7, "literals": [-5, 6], "origin": "definition", "definition_variable": 6},
        {"id": 8, "literals": [-7, 1], "origin": "definition", "definition_variable": 7},
        {"id": 9, "literals": [-7, 3], "origin": "definition", "definition_variable": 7},
        {"id": 10, "literals": [-3, -1, 7], "origin": "definition", "definition_variable": 7},
        {"id": 11, "literals": [-8, -7, 2], "origin": "definition", "definition_variable": 8},
        {"id": 12, "literals": [7, 8], "origin": "definition", "definition_variable": 8},
        {"id": 13, "literals": [-2, 8], "origin": "definition", "definition_variable": 8},
    ]


def _release_atoms() -> list[dict[str, object]]:
    return [
        {"atom_id": "api_v2", "variable": 1},
        {"atom_id": "release_ready", "variable": 2},
        {"atom_id": "tests_pass", "variable": 3},
    ]


def demo_r1_proved_bundle() -> dict[str, object]:
    formulas = _release_formulas()
    clauses = _release_definition_clauses() + [
        {"id": 14, "literals": [1], "origin": "premise", "assertion_id": "as_api_v2"},
        {"id": 15, "literals": [6], "origin": "premise", "assertion_id": "as_block_rule"},
        {"id": 16, "literals": [8], "origin": "premise", "assertion_id": "as_ready_rule"},
        {"id": 17, "literals": [3], "origin": "premise", "assertion_id": "as_tests_pass"},
        {"id": 18, "literals": [-2], "origin": "query_assumption"},
        {"id": 19, "literals": [-3, 7], "origin": "resolution", "parents": [14, 10], "pivot": 1},
        {"id": 20, "literals": [7], "origin": "resolution", "parents": [19, 17], "pivot": 3},
        {"id": 21, "literals": [-8, 2], "origin": "resolution", "parents": [20, 11], "pivot": 7},
        {"id": 22, "literals": [2], "origin": "resolution", "parents": [21, 16], "pivot": 8},
        {"id": 23, "literals": [], "origin": "resolution", "parents": [22, 18], "pivot": 2},
    ]
    return assemble(
        workspace_id="workspace_demo",
        revision_id="rev_001",
        result="PROVED",
        assertions=[
            ("as_api_v2", formulas["deployed"], ["ev_api"]),
            ("as_block_rule", formulas["block"], ["ev_block"]),
            ("as_ready_rule", formulas["allow"], ["ev_ready"]),
            ("as_tests_pass", formulas["tests"], ["ev_tests"]),
        ],
        query=formulas["ready"],
        atom_variables=_release_atoms(),
        definitions=_release_definitions(formulas),
        roots=[
            {"assertion_id": "as_api_v2", "variable": 1},
            {"assertion_id": "as_block_rule", "variable": 6},
            {"assertion_id": "as_ready_rule", "variable": 8},
            {"assertion_id": "as_tests_pass", "variable": 3},
        ],
        query_root=2,
        witness={"api_v2": True, "release_ready": True, "tests_pass": True},
        clauses=clauses,
        empty_clause_id=23,
        support=["as_api_v2", "as_ready_rule", "as_tests_pass"],
    )


def demo_r2_refuted_bundle() -> dict[str, object]:
    formulas = _release_formulas()
    clauses = _release_definition_clauses() + [
        {"id": 14, "literals": [1], "origin": "premise", "assertion_id": "as_api_v2"},
        {"id": 15, "literals": [6], "origin": "premise", "assertion_id": "as_block_rule"},
        {"id": 16, "literals": [8], "origin": "premise", "assertion_id": "as_ready_rule"},
        {"id": 17, "literals": [4], "origin": "premise", "assertion_id": "as_tests_fail"},
        {"id": 18, "literals": [2], "origin": "query_assumption"},
        {"id": 19, "literals": [-4, 5], "origin": "resolution", "parents": [15, 5], "pivot": 6},
        {"id": 20, "literals": [5], "origin": "resolution", "parents": [19, 17], "pivot": 4},
        {"id": 21, "literals": [-2], "origin": "resolution", "parents": [20, 3], "pivot": 5},
        {"id": 22, "literals": [], "origin": "resolution", "parents": [21, 18], "pivot": 2},
    ]
    return assemble(
        workspace_id="workspace_demo",
        revision_id="rev_002",
        result="REFUTED",
        assertions=[
            ("as_api_v2", formulas["deployed"], ["ev_api"]),
            ("as_block_rule", formulas["block"], ["ev_block"]),
            ("as_ready_rule", formulas["allow"], ["ev_ready"]),
            ("as_tests_fail", formulas["not_tests"], ["ev_tests_corrected"]),
        ],
        query=formulas["ready"],
        atom_variables=_release_atoms(),
        definitions=_release_definitions(formulas),
        roots=[
            {"assertion_id": "as_api_v2", "variable": 1},
            {"assertion_id": "as_block_rule", "variable": 6},
            {"assertion_id": "as_ready_rule", "variable": 8},
            {"assertion_id": "as_tests_fail", "variable": 4},
        ],
        query_root=2,
        witness={"api_v2": True, "release_ready": False, "tests_pass": False},
        clauses=clauses,
        empty_clause_id=22,
        support=["as_block_rule", "as_tests_fail"],
    )
