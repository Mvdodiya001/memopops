"""Reconstruct definition variables and the expected initial clause list.

This is checker-side validation, not a proof search. Certificate generators
must not import this module to author proofs.
"""

from __future__ import annotations

from dataclasses import dataclass

from proofcheck.formula import (
    Formula,
    atoms_of,
    canonical_json,
    canonical_formula,
    formula_hash,
)


@dataclass(frozen=True)
class Definition:
    variable: int
    op: str
    operands: tuple[int, ...]
    formula_hash: str


@dataclass(frozen=True)
class InitialClause:
    literals: tuple[int, ...]
    origin: str
    definition_variable: int | None = None
    assertion_id: str | None = None


@dataclass(frozen=True)
class Reconstruction:
    atom_variables: tuple[tuple[str, int], ...]
    definitions: tuple[Definition, ...]
    roots: tuple[tuple[str, int], ...]
    query_root: int
    clauses: tuple[InitialClause, ...]


def normalize_literals(literals: list[int]) -> tuple[int, ...] | None:
    unique = tuple(sorted(set(literals)))
    if any(-literal in unique for literal in unique if literal > 0):
        return None
    return unique


def definition_clause_literals(op: str, variable: int, operands: tuple[int, ...]) -> list[tuple[int, ...]]:
    if op == "not":
        (left,) = operands
        raw = [[-variable, -left], [variable, left]]
    elif op == "and":
        left, right = operands
        raw = [[-variable, left], [-variable, right], [variable, -left, -right]]
    elif op == "or":
        left, right = operands
        raw = [[variable, -left], [variable, -right], [-variable, left, right]]
    elif op == "implies":
        left, right = operands
        raw = [[-variable, -left, right], [variable, left], [variable, -right]]
    elif op == "iff":
        left, right = operands
        raw = [
            [-variable, -left, right],
            [-variable, left, -right],
            [variable, left, right],
            [variable, -left, -right],
        ]
    else:
        raise ValueError(f"unsupported operator {op}")
    clauses: list[tuple[int, ...]] = []
    for literals in raw:
        normalized = normalize_literals(literals)
        if normalized is not None:
            clauses.append(normalized)
    return clauses


def reconstruct(assertions: list[tuple[str, Formula]], query: Formula, result: str) -> Reconstruction:
    atom_ids = set()
    for _, formula in assertions:
        atom_ids.update(atoms_of(formula))
    atom_ids.update(atoms_of(query))
    ordered_atoms = tuple(sorted(atom_ids))
    atom_variables = {atom_id: index for index, atom_id in enumerate(ordered_atoms, start=1)}
    next_variable = len(ordered_atoms) + 1
    cache: dict[str, int] = {}
    definitions: list[Definition] = []

    def intern(formula: Formula) -> int:
        nonlocal next_variable
        if formula.op == "atom":
            assert formula.atom_id is not None
            return atom_variables[formula.atom_id]
        key = canonical_json(canonical_formula(formula))
        existing = cache.get(key)
        if existing is not None:
            return existing
        operands = tuple(intern(child) for child in formula.children)
        variable = next_variable
        next_variable += 1
        cache[key] = variable
        definitions.append(
            Definition(
                variable=variable,
                op=formula.op,
                operands=operands,
                formula_hash=formula_hash(formula),
            )
        )
        return variable

    roots = tuple((assertion_id, intern(formula)) for assertion_id, formula in assertions)
    query_root = intern(query)
    clauses: list[InitialClause] = []
    for definition in definitions:
        for literals in definition_clause_literals(definition.op, definition.variable, definition.operands):
            clauses.append(
                InitialClause(
                    literals=literals,
                    origin="definition",
                    definition_variable=definition.variable,
                )
            )
    for assertion_id, variable in roots:
        clauses.append(InitialClause(literals=(variable,), origin="premise", assertion_id=assertion_id))
    sign = -1 if result == "PROVED" else 1
    clauses.append(InitialClause(literals=(sign * query_root,), origin="query_assumption"))
    return Reconstruction(
        atom_variables=tuple((atom_id, atom_variables[atom_id]) for atom_id in ordered_atoms),
        definitions=tuple(definitions),
        roots=roots,
        query_root=query_root,
        clauses=tuple(clauses),
    )
