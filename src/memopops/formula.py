"""Strict parser and canonical representation for the v1 Boolean formula AST."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import TypeAlias


SEMANTICS_VERSION = "boolean-v1"
ATOM_ID_PATTERN = re.compile(r"[a-z][a-z0-9_]{0,63}", re.ASCII)
DEFAULT_MAX_DEPTH = 16
DEFAULT_MAX_NODES = 64


class FormulaValidationError(ValueError):
    """Raised when input is not a valid formula in the v1 language."""


@dataclass(frozen=True, slots=True)
class Atom:
    id: str


@dataclass(frozen=True, slots=True)
class Not:
    arg: Formula


@dataclass(frozen=True, slots=True)
class Binary:
    op: str
    left: Formula
    right: Formula


Formula: TypeAlias = Atom | Not | Binary
_BINARY_OPS = {"and", "or", "implies", "iff"}


def parse_formula(
    value: object,
    registered_atoms: set[str] | frozenset[str],
    *,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_nodes: int = DEFAULT_MAX_NODES,
) -> Formula:
    """Parse a JSON-shaped AST, enforcing shape and resource limits before descent."""
    if max_depth < 1 or max_nodes < 1:
        raise ValueError("formula limits must be positive")

    node_count = 0

    def visit(node: object, depth: int) -> Formula:
        nonlocal node_count
        node_count += 1
        if node_count > max_nodes:
            raise FormulaValidationError(f"formula exceeds {max_nodes} nodes")
        if depth > max_depth:
            raise FormulaValidationError(f"formula exceeds depth {max_depth}")
        if not isinstance(node, dict) or not all(isinstance(k, str) for k in node):
            raise FormulaValidationError("each formula node must be an object with string keys")

        op = node.get("op")
        if not isinstance(op, str):
            raise FormulaValidationError("formula op must be a string")
        if op == "atom":
            if node.keys() != {"op", "id"}:
                raise FormulaValidationError("atom nodes require exactly 'op' and 'id'")
            atom_id = node["id"]
            if not isinstance(atom_id, str) or ATOM_ID_PATTERN.fullmatch(atom_id) is None:
                raise FormulaValidationError("atom id must match [a-z][a-z0-9_]{0,63}")
            if atom_id not in registered_atoms:
                raise FormulaValidationError(f"unregistered atom: {atom_id}")
            return Atom(atom_id)

        if op == "not":
            if node.keys() != {"op", "arg"}:
                raise FormulaValidationError("not nodes require exactly 'op' and 'arg'")
            return Not(visit(node["arg"], depth + 1))

        if op in _BINARY_OPS:
            if node.keys() != {"op", "args"}:
                raise FormulaValidationError(f"{op} nodes require exactly 'op' and 'args'")
            args = node["args"]
            if not isinstance(args, list) or len(args) != 2:
                raise FormulaValidationError(f"{op} requires exactly two ordered arguments")
            return Binary(op, visit(args[0], depth + 1), visit(args[1], depth + 1))

        raise FormulaValidationError("op must be atom, not, and, or, implies, or iff")

    return visit(value, 1)


def formula_to_json(formula: Formula) -> dict[str, object]:
    """Return the canonical JSON-compatible AST for an already parsed formula."""
    if isinstance(formula, Atom):
        return {"op": "atom", "id": formula.id}
    if isinstance(formula, Not):
        return {"op": "not", "arg": formula_to_json(formula.arg)}
    if isinstance(formula, Binary):
        return {
            "op": formula.op,
            "args": [formula_to_json(formula.left), formula_to_json(formula.right)],
        }
    raise TypeError(f"unsupported formula node: {type(formula).__name__}")


def formula_atoms(formula: Formula) -> set[str]:
    """Return all atom IDs appearing in a formula."""
    if isinstance(formula, Atom):
        return {formula.id}
    if isinstance(formula, Not):
        return formula_atoms(formula.arg)
    if isinstance(formula, Binary):
        return formula_atoms(formula.left) | formula_atoms(formula.right)
    raise TypeError(f"unsupported formula node: {type(formula).__name__}")


def canonical_json(formula: Formula) -> str:
    """Serialize with the v1 stable encoding while preserving argument order."""
    return json.dumps(
        formula_to_json(formula),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def formula_hash(formula: Formula) -> str:
    """Hash semantics version and canonical AST to prevent cross-semantics reuse."""
    envelope = {"semantics_version": SEMANTICS_VERSION, "formula": formula_to_json(formula)}
    encoded = json.dumps(
        envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
