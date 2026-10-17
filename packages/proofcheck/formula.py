"""Boolean AST parsing, canonical hashes, and evaluation.

Formula hashes match the published memory-service envelope: sorted-key compact
JSON of {"formula": <canonical AST>, "semantics_version": "boolean-v1"}.
Knowledge hashes use {"assertions": [[id, formula_hash], ...], "semantics_version":
"boolean-v1"} with assertion ids sorted. Evidence is not part of either hash.
Query hashes are formula hashes of the query AST. This module does not import
the memory service.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from proofcheck.limits import MAX_DEPTH, MAX_ID_LENGTH, MAX_NODES_PER_FORMULA

SEMANTICS_VERSION = "boolean-v1"
CERTIFICATE_VERSION = "resolution-v1"
ATOM_ID = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
BINARY_OPS = frozenset({"and", "or", "implies", "iff"})


class FormulaRejected(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Formula:
    op: str
    atom_id: str | None = None
    children: tuple[Formula, ...] = ()


def parse_formula(value: object) -> Formula:
    nodes = 0

    def walk(node: object, depth: int) -> Formula:
        nonlocal nodes
        if depth > MAX_DEPTH:
            raise FormulaRejected("limit_exceeded", f"Formula depth exceeds {MAX_DEPTH}.")
        nodes += 1
        if nodes > MAX_NODES_PER_FORMULA:
            raise FormulaRejected(
                "limit_exceeded",
                f"Formula has more than {MAX_NODES_PER_FORMULA} nodes.",
            )
        if not isinstance(node, dict):
            raise FormulaRejected("malformed", "Formula must be an object.")
        allowed = {"op", "id", "arg", "args"}
        extra = set(node) - allowed
        if extra:
            raise FormulaRejected("malformed", "Formula contains unknown properties.")
        op = node.get("op")
        if op == "atom":
            if set(node) != {"op", "id"}:
                raise FormulaRejected("malformed", "Atom formulas require op and id only.")
            atom_id = node.get("id")
            if not isinstance(atom_id, str) or ATOM_ID.fullmatch(atom_id) is None:
                raise FormulaRejected("undefined_atom", "Atom id is missing or not canonical.")
            return Formula(op="atom", atom_id=atom_id)
        if op == "not":
            if set(node) != {"op", "arg"}:
                raise FormulaRejected("malformed", "Negation requires op and arg only.")
            return Formula(op="not", children=(walk(node.get("arg"), depth + 1),))
        if op in BINARY_OPS:
            if set(node) != {"op", "args"}:
                raise FormulaRejected("malformed", "Binary formulas require op and args only.")
            args = node.get("args")
            if not isinstance(args, list) or len(args) != 2:
                raise FormulaRejected("malformed", "Binary formulas require exactly two arguments.")
            return Formula(op=op, children=(walk(args[0], depth + 1), walk(args[1], depth + 1)))
        raise FormulaRejected("malformed", "Formula operator is not supported.")

    parsed = walk(value, 1)
    return parsed


def node_count(formula: Formula) -> int:
    return 1 + sum(node_count(child) for child in formula.children)


def depth_of(formula: Formula) -> int:
    if not formula.children:
        return 1
    return 1 + max(depth_of(child) for child in formula.children)


def atoms_of(formula: Formula) -> set[str]:
    if formula.op == "atom":
        assert formula.atom_id is not None
        return {formula.atom_id}
    found: set[str] = set()
    for child in formula.children:
        found.update(atoms_of(child))
    return found


def canonical_formula(formula: Formula) -> dict[str, object]:
    if formula.op == "atom":
        return {"id": formula.atom_id, "op": "atom"}
    if formula.op == "not":
        return {"arg": canonical_formula(formula.children[0]), "op": "not"}
    return {
        "args": [canonical_formula(child) for child in formula.children],
        "op": formula.op,
    }


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def formula_hash(formula: Formula | dict[str, object]) -> str:
    parsed = formula if isinstance(formula, Formula) else parse_formula(formula)
    envelope = {"formula": canonical_formula(parsed), "semantics_version": SEMANTICS_VERSION}
    return sha256_json(envelope)


def knowledge_hash(pairs: list[tuple[str, str]]) -> str:
    assertions = [[assertion_id, digest] for assertion_id, digest in sorted(pairs, key=lambda item: item[0])]
    return sha256_json({"assertions": assertions, "semantics_version": SEMANTICS_VERSION})


def evaluate_formula(formula: Formula | dict[str, object], assignment: dict[str, bool]) -> bool:
    parsed = formula if isinstance(formula, Formula) else parse_formula(formula)
    return _evaluate(parsed, assignment)


def _evaluate(formula: Formula, assignment: dict[str, bool]) -> bool:
    if formula.op == "atom":
        assert formula.atom_id is not None
        if formula.atom_id not in assignment:
            raise FormulaRejected("witness_invalid", f"Assignment omits atom {formula.atom_id}.")
        value = assignment[formula.atom_id]
        if type(value) is not bool:
            raise FormulaRejected("witness_invalid", f"Assignment for {formula.atom_id} is not boolean.")
        return value
    if formula.op == "not":
        return not _evaluate(formula.children[0], assignment)
    left = _evaluate(formula.children[0], assignment)
    right = _evaluate(formula.children[1], assignment)
    if formula.op == "and":
        return left and right
    if formula.op == "or":
        return left or right
    if formula.op == "implies":
        return (not left) or right
    if formula.op == "iff":
        return left == right
    raise FormulaRejected("malformed", "Formula operator is not supported.")


def require_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_ID_LENGTH:
        raise FormulaRejected("malformed", f"{label} must be a non-empty string.")
    if value.strip() != value or any(ord(char) < 32 for char in value):
        raise FormulaRejected("malformed", f"{label} contains unsupported characters.")
    return value
