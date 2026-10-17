"""Bounded Tseitin and resolution certificate generation.

This module creates proof bundles only. Validation belongs to the separately
implemented ``proofcheck`` package and must remain independent of this encoder.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import heapq
from itertools import count
import time
from typing import Iterable, Mapping

from memopops.formula import (
    SEMANTICS_VERSION,
    Atom,
    Binary,
    Formula,
    Not,
    canonical_json,
    formula_atoms,
    formula_hash,
    formula_to_json,
)
from memopops.store import AssertionRecord, Snapshot, calculate_knowledge_hash

CERTIFICATE_VERSION = "resolution-v1"
MAX_INITIAL_CLAUSES = 64
MAX_DERIVED_CLAUSES = 512
MAX_LITERALS_PER_CLAUSE = 64
MAX_VARIABLE = 16_384
MAX_CANDIDATE_PAIRS = 10_000
DEFAULT_TIME_BUDGET_SECONDS = 1.0


class CertificateGenerationError(ValueError):
    """The input context cannot produce a certificate for the declared result."""


class CertificateBudgetExceeded(RuntimeError):
    """The bounded proof search did not find a certificate within its limits."""


@dataclass(frozen=True, slots=True)
class _Definition:
    variable: int
    formula: Formula
    operands: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _Clause:
    literals: tuple[int, ...]
    origin: str
    definition_variable: int | None = None
    assertion_id: str | None = None
    parents: tuple[int, int] | None = None
    pivot: int | None = None


def _formula_atoms(formulas: Iterable[Formula]) -> set[str]:
    return set().union(*(formula_atoms(item) for item in formulas))


def _evaluate(formula: Formula, assignment: Mapping[str, bool]) -> bool:
    if isinstance(formula, Atom):
        return assignment[formula.id]
    if isinstance(formula, Not):
        return not _evaluate(formula.arg, assignment)
    if isinstance(formula, Binary):
        left, right = _evaluate(formula.left, assignment), _evaluate(formula.right, assignment)
        if formula.op == "and":
            return left and right
        if formula.op == "or":
            return left or right
        if formula.op == "implies":
            return not left or right
        if formula.op == "iff":
            return left == right
    raise TypeError(f"unsupported formula node: {type(formula).__name__}")


def _normalize(literals: Iterable[int]) -> tuple[int, ...] | None:
    normalized = tuple(sorted(set(literals)))
    if any(-literal in normalized for literal in normalized if literal > 0):
        return None
    return normalized


def _definition_clauses(op: str, variable: int, operands: tuple[int, ...]) -> list[tuple[int, ...]]:
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
        raise TypeError(f"unsupported Boolean operator: {op}")
    clauses = []
    for literals in raw:
        normalized = _normalize(literals)
        if normalized is not None:
            clauses.append(normalized)
    return clauses


def _resolve(left: tuple[int, ...], right: tuple[int, ...]) -> tuple[int, tuple[int, ...]] | None:
    left_set, right_set = set(left), set(right)
    pivots = sorted({abs(literal) for literal in left_set if -literal in right_set})
    if len(pivots) != 1:
        return None
    pivot = pivots[0]
    if pivot in left_set and -pivot in right_set:
        child = (left_set - {pivot}) | (right_set - {-pivot})
    else:
        child = (left_set - {-pivot}) | (right_set - {pivot})
    normalized = _normalize(child)
    return None if normalized is None else (pivot, normalized)


def generate_certificate(
    snapshot: Snapshot,
    query: Formula,
    result: str,
    knowledge_witness: Mapping[str, bool],
    evidence_ids: Mapping[str, Iterable[str]],
    *,
    max_derived_clauses: int = MAX_DERIVED_CLAUSES,
    max_candidate_pairs: int = MAX_CANDIDATE_PAIRS,
    time_budget_seconds: float = DEFAULT_TIME_BUDGET_SECONDS,
) -> dict[str, object]:
    """Create a bounded proof bundle for a solver-decisive result.

    ``evidence_ids`` must come from the trusted evidence records loaded for this
    exact snapshot. The returned bundle still requires independent checking and
    comparison with a separately constructed expected context before VERIFIED.
    """
    if result not in {"PROVED", "REFUTED"}:
        raise CertificateGenerationError("only PROVED and REFUTED results have resolution certificates")
    if max_derived_clauses < 0 or max_candidate_pairs < 1 or time_budget_seconds <= 0:
        raise ValueError("certificate budgets must be positive (derived clause budget may be zero)")
    assertions = tuple(sorted(snapshot.assertions, key=lambda item: item.id))
    if calculate_knowledge_hash(assertions) != snapshot.knowledge_hash:
        raise CertificateGenerationError("snapshot knowledge hash is invalid")
    if len(assertions) > 256:
        raise CertificateBudgetExceeded("assertion count exceeds the certificate bound")
    assertion_ids = {item.id for item in assertions}
    if set(evidence_ids) != assertion_ids:
        raise CertificateGenerationError("evidence IDs must match the snapshot assertion IDs")
    evidence_by_assertion: dict[str, list[str]] = {}
    for assertion_id, values in evidence_ids.items():
        ids = list(values)
        if not ids or any(not isinstance(item, str) or not item for item in ids) or len(ids) != len(set(ids)):
            raise CertificateGenerationError(f"assertion {assertion_id} requires unique evidence IDs")
        evidence_by_assertion[assertion_id] = sorted(ids)

    formulas = tuple(item.formula for item in assertions) + (query,)
    atoms = sorted(_formula_atoms(formulas))
    if len(atoms) > 128:
        raise CertificateBudgetExceeded("atom count exceeds the certificate bound")
    assignment = dict(knowledge_witness)
    if set(assignment) != set(atoms) or any(type(value) is not bool for value in assignment.values()):
        raise CertificateGenerationError("knowledge witness must assign every formula atom exactly")
    if any(not _evaluate(item.formula, assignment) for item in assertions):
        raise CertificateGenerationError("knowledge witness does not satisfy the complete snapshot")
    query_value = _evaluate(query, assignment)
    if (result == "PROVED" and not query_value) or (result == "REFUTED" and query_value):
        raise CertificateGenerationError("knowledge witness does not support the declared result")

    atom_variables = {atom_id: index for index, atom_id in enumerate(atoms, start=1)}
    next_variable = len(atoms) + 1
    definition_cache: dict[str, int] = {}
    definitions: list[_Definition] = []

    def intern(formula: Formula) -> int:
        nonlocal next_variable
        if isinstance(formula, Atom):
            return atom_variables[formula.id]
        key = canonical_json(formula)
        previous = definition_cache.get(key)
        if previous is not None:
            return previous
        if isinstance(formula, Not):
            operands = (intern(formula.arg),)
        elif isinstance(formula, Binary):
            operands = (intern(formula.left), intern(formula.right))
        else:
            raise TypeError(f"unsupported formula node: {type(formula).__name__}")
        variable = next_variable
        next_variable += 1
        if variable > MAX_VARIABLE:
            raise CertificateBudgetExceeded("variable count exceeds the certificate bound")
        definition_cache[key] = variable
        definitions.append(_Definition(variable, formula, operands))
        return variable

    roots = [(item.id, intern(item.formula)) for item in assertions]
    query_root = intern(query)
    initial: list[_Clause] = []
    for definition in definitions:
        op = "not" if isinstance(definition.formula, Not) else definition.formula.op
        for literals in _definition_clauses(op, definition.variable, definition.operands):
            initial.append(_Clause(literals, "definition", definition_variable=definition.variable))
    for assertion_id, variable in roots:
        initial.append(_Clause((variable,), "premise", assertion_id=assertion_id))
    query_sign = -1 if result == "PROVED" else 1
    initial.append(_Clause((query_sign * query_root,), "query_assumption"))
    if len(initial) > MAX_INITIAL_CLAUSES:
        raise CertificateBudgetExceeded("initial clause count exceeds the certificate bound")
    if any(len(item.literals) > MAX_LITERALS_PER_CLAUSE for item in initial):
        raise CertificateBudgetExceeded("initial clause width exceeds the certificate bound")

    clauses = list(initial)
    clause_ids = {item.literals: index + 1 for index, item in enumerate(clauses)}
    postings: dict[int, list[int]] = defaultdict(list)
    queue: list[tuple[int, int, int]] = []
    order = count()
    for clause_id, clause in enumerate(clauses, start=1):
        heapq.heappush(queue, (len(clause.literals), next(order), clause_id))
    processed: set[int] = set()
    seen_pairs: set[tuple[int, int]] = set()
    candidate_pairs = 0
    started = time.monotonic()
    deadline = started + time_budget_seconds
    empty_clause_id: int | None = None

    while queue and empty_clause_id is None:
        if time.monotonic() >= deadline:
            raise CertificateBudgetExceeded("resolution search exceeded its time budget")
        _, _, current_id = heapq.heappop(queue)
        if current_id in processed:
            continue
        processed.add(current_id)
        current = clauses[current_id - 1]
        for literal in current.literals:
            for other_id in tuple(postings[-literal]):
                pair = (min(current_id, other_id), max(current_id, other_id))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                candidate_pairs += 1
                if candidate_pairs > max_candidate_pairs:
                    raise CertificateBudgetExceeded("resolution pair budget exceeded")
                if time.monotonic() >= deadline:
                    raise CertificateBudgetExceeded("resolution search exceeded its time budget")
                left_id, right_id = pair
                resolved = _resolve(clauses[left_id - 1].literals, clauses[right_id - 1].literals)
                if resolved is None:
                    continue
                pivot, child_literals = resolved
                if len(child_literals) > MAX_LITERALS_PER_CLAUSE or child_literals in clause_ids:
                    continue
                if len(clauses) - len(initial) >= max_derived_clauses:
                    raise CertificateBudgetExceeded("derived clause budget exceeded")
                child_id = len(clauses) + 1
                child = _Clause(
                    child_literals,
                    "resolution",
                    parents=(left_id, right_id),
                    pivot=pivot,
                )
                clauses.append(child)
                clause_ids[child_literals] = child_id
                if not child_literals:
                    empty_clause_id = child_id
                    break
                heapq.heappush(queue, (len(child_literals), next(order), child_id))
            if empty_clause_id is not None:
                break
        for literal in current.literals:
            postings[literal].append(current_id)

    if empty_clause_id is None:
        raise CertificateBudgetExceeded("bounded resolution search found no empty clause")

    ancestors: set[int] = set()
    stack = [empty_clause_id]
    while stack:
        clause_id = stack.pop()
        if clause_id in ancestors:
            continue
        ancestors.add(clause_id)
        parents = clauses[clause_id - 1].parents
        if parents is not None:
            stack.extend(parents)
    selected_derived = [
        clause_id
        for clause_id in range(len(initial) + 1, len(clauses) + 1)
        if clause_id in ancestors
    ]
    remap = {clause_id: clause_id for clause_id in range(1, len(initial) + 1)}
    remap.update(
        {old_id: len(initial) + index for index, old_id in enumerate(selected_derived, start=1)}
    )
    bundle_clauses: list[dict[str, object]] = []
    for old_id, clause in enumerate(initial, start=1):
        row: dict[str, object] = {
            "id": old_id,
            "literals": list(clause.literals),
            "origin": clause.origin,
        }
        if clause.definition_variable is not None:
            row["definition_variable"] = clause.definition_variable
        if clause.assertion_id is not None:
            row["assertion_id"] = clause.assertion_id
        bundle_clauses.append(row)
    support_ids: set[str] = set()
    for old_id in selected_derived:
        clause = clauses[old_id - 1]
        assert clause.parents is not None and clause.pivot is not None
        bundle_clauses.append(
            {
                "id": remap[old_id],
                "literals": list(clause.literals),
                "origin": "resolution",
                "parents": [remap[clause.parents[0]], remap[clause.parents[1]]],
                "pivot": clause.pivot,
            }
        )
    for clause_id in ancestors:
        assertion_id = clauses[clause_id - 1].assertion_id
        if assertion_id is not None:
            support_ids.add(assertion_id)

    return {
        "certificate_version": CERTIFICATE_VERSION,
        "semantics_version": SEMANTICS_VERSION,
        "workspace_id": snapshot.workspace_id,
        "revision_id": snapshot.revision_id,
        "knowledge_hash": snapshot.knowledge_hash,
        "query_hash": formula_hash(query),
        "result": result,
        "assertions": [
            {
                "id": item.id,
                "formula": formula_to_json(item.formula),
                "evidence_ids": evidence_by_assertion[item.id],
            }
            for item in assertions
        ],
        "query": formula_to_json(query),
        "atom_variables": [
            {"atom_id": atom_id, "variable": variable}
            for atom_id, variable in atom_variables.items()
        ],
        "definitions": [
            {
                "variable": definition.variable,
                "op": "not" if isinstance(definition.formula, Not) else definition.formula.op,
                "operands": list(definition.operands),
                "formula_hash": formula_hash(definition.formula),
            }
            for definition in definitions
        ],
        "roots": [
            {"assertion_id": assertion_id, "variable": variable}
            for assertion_id, variable in roots
        ],
        "query_root": query_root,
        "knowledge_witness": assignment,
        "clauses": bundle_clauses,
        "empty_clause_id": remap[empty_clause_id],
        "support_assertion_ids": sorted(support_ids),
    }
